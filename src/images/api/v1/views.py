import uuid

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from django.conf import settings

from images.api.serializers import (
    ImageMetadataSerializer,
    ImageUploadSerializer,
    ImageSearchSerializer,
)
from images.models import ImageMetadata
from embeddings.embed_model import EmbeddingModel
from embeddings.qdrant_service import QdrantService
from embeddings.tasks import generate_embedding


class ImagePagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100


class ImageViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ImageMetadata.objects.all().order_by("-uploaded_at")
    serializer_class = ImageMetadataSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # Public API — no auth needed, avoids CSRF check
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = ImagePagination

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._qdrant_service = None

    @property
    def qdrant_service(self):
        if self._qdrant_service is None:
            self._qdrant_service = QdrantService()
        return self._qdrant_service

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request, *args, **kwargs):
        """
        Upload a new image to the system.
        The image will be stored in MinIO, metadata saved in the database,
        and the image vector will be generated and stored in Qdrant.
        """
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        name = serializer.validated_data["name"]

        metadata = ImageMetadata(
            name=name,
            image=image_file,
            file_size=image_file.size,
            vectorized=False,
        )
        metadata.save()

        # Trigger async embedding generation via Celery
        generate_embedding.delay(str(metadata.id))

        return Response(
            ImageMetadataSerializer(metadata).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def search(self, request, *args, **kwargs):
        """
        Search for similar images by uploading a query image.
        The query image is temporarily stored in MinIO for display purposes
        but no metadata is saved in the database.
        """
        serializer = ImageSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        limit = serializer.validated_data.get("limit", 20)

        # Upload query image to MinIO under a temp prefix
        query_id = str(uuid.uuid7())
        query_name = f"search_queries/{query_id}_{image_file.name}"

        from storage.custom_s3 import ExternalS3Storage
        temp_storage = ExternalS3Storage()
        temp_storage.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        temp_storage.location = 'images'
        temp_path = temp_storage.save(query_name, image_file)
        query_image_url = temp_storage.url(temp_path)

        # Generate embedding from the query image
        try:
            image_file.seek(0)
            image_bytes = image_file.read()
            vector = EmbeddingModel().encode_from_bytes(image_bytes)

            # Search Qdrant
            self.qdrant_service.ensure_collection()
            results = self.qdrant_service.search(vector=vector.tolist(), limit=limit)

            # Fetch metadata from PostgreSQL for matched results
            matched_ids = [r[0] for r in results if r[2].get("name")]
            metadata_map = {}
            if matched_ids:
                qs = ImageMetadata.objects.filter(id__in=matched_ids)
                metadata_map = {str(m.id): m for m in qs}

            result_list = []
            for point_id, score, payload in results:
                meta = metadata_map.get(point_id)
                if meta:
                    try:
                        img_url = meta.image.url
                    except Exception:
                        img_url = None
                    result_list.append({
                        "id": str(meta.id),
                        "name": meta.name,
                        "image_url": img_url,
                        "uploaded_at": meta.uploaded_at.isoformat(),
                        "file_size": meta.file_size,
                        "score": round(float(score), 4),
                    })
                else:
                    # Fallback — image may have been deleted from DB
                    result_list.append({
                        "id": point_id,
                        "name": payload.get("name", "Unknown"),
                        "image_url": None,
                        "uploaded_at": payload.get("uploaded_at"),
                        "file_size": payload.get("file_size"),
                        "score": round(float(score), 4),
                    })

            return Response({
                "query_image_url": query_image_url,
                "results": result_list,
            })

        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Search failed: %s", exc)
            return Response(
                {"error": f"Search failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )