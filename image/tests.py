from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from .embeddings import EfficientNetV2EmbeddingProvider, clear_embedding_provider_cache, get_embedding_provider
from .models import ImageAsset, ImageStatus, ImageVisibility
from .storage import ObjectMetadata
from .tasks import index_image_asset
from .vector import QdrantVectorIndex, VectorIndexError, VectorMatch


User = get_user_model()


def make_jpeg_bytes(size=(32, 32), color=(120, 80, 40)) -> bytes:
    from PIL import Image

    image = Image.new("RGB", size, color=color)
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


class ImageApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.other = User.objects.create_user(username="other", password="password")
        self.client.force_authenticate(self.user)

    def make_asset(self, *, owner=None, visibility=ImageVisibility.PRIVATE, status=ImageStatus.INDEXED, filename="a.jpg"):
        owner = owner or self.user
        return ImageAsset.objects.create(
            owner=owner,
            object_key=f"users/{owner.id}/images/{filename}",
            filename=filename,
            content_type="image/jpeg",
            size_bytes=100,
            visibility=visibility,
            status=status,
        )

    @patch("image.views.get_storage_client")
    def test_upload_request_returns_presigned_url(self, storage_factory):
        storage = Mock()
        storage.build_object_key.return_value = "users/1/images/test.jpg"
        storage.create_presigned_upload.return_value = Mock(
            url="http://storage/upload",
            headers={"Content-Type": "image/jpeg"},
        )
        storage_factory.return_value = storage

        response = self.client.post(
            "/api/images/",
            {
                "filename": "test.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 100,
                "tags": ["sku-1"],
                "visibility": "private",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["upload_url"], "http://storage/upload")
        self.assertEqual(ImageAsset.objects.count(), 1)
        self.assertEqual(ImageAsset.objects.first().status, ImageStatus.UPLOAD_REQUESTED)

    def test_list_is_limited_to_owned_and_public_indexed_images(self):
        owned = self.make_asset(filename="owned.jpg")
        public = self.make_asset(owner=self.other, visibility=ImageVisibility.PUBLIC, filename="public.jpg")
        self.make_asset(owner=self.other, visibility=ImageVisibility.PRIVATE, filename="private.jpg")

        response = self.client.get("/api/images/")

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {str(owned.id), str(public.id)})

    @patch("image.views.index_image_asset.delay")
    @patch("image.views.get_storage_client")
    def test_complete_upload_marks_pending_and_queues_task(self, storage_factory, delay):
        asset = self.make_asset(status=ImageStatus.UPLOAD_REQUESTED)
        storage = Mock()
        storage.object_exists.return_value = True
        storage_factory.return_value = storage

        response = self.client.post(f"/api/images/{asset.id}/complete/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        asset.refresh_from_db()
        self.assertEqual(asset.status, ImageStatus.EMBEDDING_PENDING)
        delay.assert_called_once_with(str(asset.id))

    def test_text_search_is_disabled_for_image_only_embeddings(self):
        response = self.client.post("/api/search/text/", {"query": "shoe", "limit": 5}, format="json")

        self.assertEqual(response.status_code, 501)
        self.assertIn("image-only", response.data["detail"])

    @patch("image.views.get_vector_index")
    @patch("image.views.get_embedding_provider")
    @patch("image.views.get_storage_client")
    def test_image_search_rechecks_database_permissions(self, storage_factory, provider_factory, vector_factory):
        owned = self.make_asset(filename="owned.jpg")
        public = self.make_asset(owner=self.other, visibility=ImageVisibility.PUBLIC, filename="public.jpg")
        private = self.make_asset(owner=self.other, visibility=ImageVisibility.PRIVATE, filename="private.jpg")

        storage = Mock()
        storage.get_object_bytes.return_value = make_jpeg_bytes()
        storage_factory.return_value = storage
        provider = Mock()
        provider.embed_image_bytes.return_value = [0.1, 0.2]
        provider_factory.return_value = provider
        vector_index = Mock()
        vector_index.search.return_value = [
            VectorMatch(str(private.id), 0.99, {}),
            VectorMatch(str(owned.id), 0.9, {}),
            VectorMatch(str(public.id), 0.8, {}),
        ]
        vector_factory.return_value = vector_index

        response = self.client.post("/api/search/image/", {"image_id": str(owned.id), "limit": 5}, format="json")

        self.assertEqual(response.status_code, 200)
        ids = [item["image"]["id"] for item in response.data["results"]]
        self.assertEqual(ids, [str(owned.id), str(public.id)])

    @override_settings(IMAGE_MAX_SIZE_BYTES=10)
    def test_image_search_rejects_oversized_uploaded_query_image(self):
        response = self.client.post(
            "/api/search/image/",
            {
                "image": SimpleUploadedFile("query.jpg", make_jpeg_bytes(), content_type="image/jpeg"),
                "limit": 5,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)

    @patch("image.views.get_vector_index")
    @patch("image.views.get_storage_client")
    def test_delete_marks_asset_deleted_and_cleans_external_stores(self, storage_factory, vector_factory):
        asset = self.make_asset(filename="delete.jpg")
        storage = Mock()
        vector = Mock()
        storage_factory.return_value = storage
        vector_factory.return_value = vector

        response = self.client.delete(f"/api/images/{asset.id}/")

        self.assertEqual(response.status_code, 204)
        asset.refresh_from_db()
        self.assertEqual(asset.status, ImageStatus.DELETED)
        storage.delete_objects.assert_called_once()
        vector.delete_image.assert_called_once_with(str(asset.id))


class EmbeddingProviderTests(TestCase):
    def tearDown(self):
        clear_embedding_provider_cache()

    @override_settings(
        EMBEDDING_PROVIDER="image.embeddings.HashEmbeddingProvider",
        EMBEDDING_MODEL_ID="hash-v1",
        EMBEDDING_DIMENSIONS=8,
    )
    def test_get_embedding_provider_is_cached(self):
        first = get_embedding_provider()
        second = get_embedding_provider()

        self.assertIs(first, second)
        self.assertEqual(len(first.embed_image_bytes(b"image")), 8)

    @override_settings(
        EMBEDDING_MODEL_ID="efficientnetv2-s-imagenet1k-v1",
        EMBEDDING_DIMENSIONS=1280,
        EMBEDDING_DEVICE="cpu",
        EMBEDDING_TORCH_THREADS=1,
    )
    @patch("torchvision.models.efficientnet_v2_s")
    @patch("torchvision.models.EfficientNet_V2_S_Weights")
    def test_efficientnet_provider_returns_normalized_vector(self, weights_enum, model_factory):
        import torch

        class FakeModel(torch.nn.Module):
            def forward(self, tensor):
                output = torch.zeros((1, 1280), dtype=torch.float32)
                output[0, 0] = 3.0
                output[0, 1] = 4.0
                return output

        weights = Mock()
        weights.transforms.return_value = lambda image: torch.ones((3, 384, 384), dtype=torch.float32)
        weights_enum.DEFAULT = weights
        model_factory.return_value = FakeModel()

        provider = EfficientNetV2EmbeddingProvider()
        vector = provider.embed_image_bytes(make_jpeg_bytes())

        self.assertEqual(provider.model_id, "efficientnetv2-s-imagenet1k-v1")
        self.assertEqual(len(vector), 1280)
        self.assertAlmostEqual(vector[0], 0.6, places=6)
        self.assertAlmostEqual(vector[1], 0.8, places=6)
        self.assertAlmostEqual(sum(value * value for value in vector), 1.0, places=6)


class IndexImageTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")

    def make_asset(self, *, content: bytes, checksum: str = ""):
        return ImageAsset.objects.create(
            owner=self.user,
            object_key="users/1/images/test.jpg",
            filename="test.jpg",
            content_type="image/jpeg",
            size_bytes=len(content),
            checksum=checksum,
            status=ImageStatus.UPLOADED,
        )

    @patch("image.tasks.get_vector_index")
    @patch("image.tasks.get_embedding_provider")
    @patch("image.tasks.get_storage_client")
    def test_index_image_asset_writes_metadata_thumbnail_and_vector(self, storage_factory, provider_factory, vector_factory):
        import hashlib

        content = make_jpeg_bytes(size=(40, 24))
        asset = self.make_asset(content=content, checksum=hashlib.sha256(content).hexdigest())
        storage = Mock()
        storage.get_object_metadata.return_value = ObjectMetadata(
            content_length=len(content),
            content_type="image/jpeg",
            etag="etag",
        )
        storage.get_object_bytes.return_value = content
        storage_factory.return_value = storage
        provider = Mock(model_id=settings.EMBEDDING_MODEL_ID, dimensions=1280)
        provider.embed_image_bytes.return_value = [0.0] * 1280
        provider_factory.return_value = provider
        vector_index = Mock()
        vector_factory.return_value = vector_index

        result = index_image_asset(str(asset.id))

        self.assertEqual(result, str(asset.id))
        asset.refresh_from_db()
        self.assertEqual(asset.status, ImageStatus.INDEXED)
        self.assertEqual(asset.width, 40)
        self.assertEqual(asset.height, 24)
        self.assertEqual(asset.embedding_dimensions, 1280)
        self.assertEqual(asset.embedding_model, settings.EMBEDDING_MODEL_ID)
        self.assertTrue(asset.thumbnail_key.endswith(".webp"))
        storage.put_object.assert_called_once()
        vector_index.upsert_image.assert_called_once()

    @patch("image.tasks.get_vector_index")
    @patch("image.tasks.get_embedding_provider")
    @patch("image.tasks.get_storage_client")
    def test_index_image_asset_marks_failure_on_validation_error(self, storage_factory, provider_factory, vector_factory):
        content = make_jpeg_bytes()
        asset = self.make_asset(content=content)
        storage = Mock()
        storage.get_object_metadata.return_value = ObjectMetadata(
            content_length=len(content) + 1,
            content_type="image/jpeg",
            etag="etag",
        )
        storage_factory.return_value = storage
        provider_factory.return_value = Mock(model_id="model", dimensions=1280)
        vector_factory.return_value = Mock()

        with self.assertRaises(ValueError):
            index_image_asset(str(asset.id))

        asset.refresh_from_db()
        self.assertEqual(asset.status, ImageStatus.FAILED)
        self.assertIn("size", asset.failure_reason)


class QdrantVectorIndexTests(TestCase):
    def test_ensure_collection_creates_missing_collection(self):
        client = Mock()
        client.collection_exists.return_value = False
        index = QdrantVectorIndex(url="http://qdrant", api_key=None, collection_name="images", timeout=5)
        index._client = client

        index.ensure_collection(1280)

        client.create_collection.assert_called_once()
        kwargs = client.create_collection.call_args.kwargs
        self.assertEqual(kwargs["collection_name"], "images")
        self.assertEqual(kwargs["vectors_config"].size, 1280)

    def test_ensure_collection_rejects_dimension_mismatch(self):
        client = Mock()
        client.collection_exists.return_value = True
        client.get_collection.return_value = SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=32)))
        )
        index = QdrantVectorIndex(url="http://qdrant", api_key=None, collection_name="images", timeout=5)
        index._client = client

        with self.assertRaises(VectorIndexError):
            index.ensure_collection(1280)


class ManagementCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")

    @patch("image.management.commands.warm_embedding_model.get_embedding_provider")
    def test_warm_embedding_model_command_embeds_probe_image(self, provider_factory):
        provider = Mock(model_id="efficientnetv2-s-imagenet1k-v1")
        provider.embed_image_bytes.return_value = [0.0] * 1280
        provider_factory.return_value = provider
        output = StringIO()

        call_command("warm_embedding_model", stdout=output)

        provider.embed_image_bytes.assert_called_once()
        self.assertIn("1280", output.getvalue())

    @patch("image.management.commands.reindex_images.index_image_asset.delay")
    @override_settings(
        EMBEDDING_MODEL_ID="efficientnetv2-s-imagenet1k-v1",
        EMBEDDING_DIMENSIONS=1280,
    )
    def test_reindex_images_queues_stale_uploaded_assets(self, delay):
        stale = ImageAsset.objects.create(
            owner=self.user,
            object_key="users/1/images/stale.jpg",
            filename="stale.jpg",
            content_type="image/jpeg",
            size_bytes=100,
            status=ImageStatus.INDEXED,
            embedding_model="hash-v1",
            embedding_dimensions=32,
        )
        ImageAsset.objects.create(
            owner=self.user,
            object_key="users/1/images/current.jpg",
            filename="current.jpg",
            content_type="image/jpeg",
            size_bytes=100,
            status=ImageStatus.INDEXED,
            embedding_model=settings.EMBEDDING_MODEL_ID,
            embedding_dimensions=settings.EMBEDDING_DIMENSIONS,
        )
        ImageAsset.objects.create(
            owner=self.user,
            object_key="users/1/images/not-uploaded.jpg",
            filename="not-uploaded.jpg",
            content_type="image/jpeg",
            size_bytes=100,
            status=ImageStatus.UPLOAD_REQUESTED,
        )

        call_command("reindex_images")

        delay.assert_called_once_with(str(stale.id))
