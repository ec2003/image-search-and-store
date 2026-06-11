from django.db import transaction
from django.db.models import Q
from uuid import uuid4
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .embeddings import get_embedding_provider
from .models import ImageAsset, ImageStatus, ImageVisibility
from .permissions import IsOwnerOrPublicReadOnly
from .serializers import (
    ImageAssetSerializer,
    ImageSearchSerializer,
    ImageStatusSerializer,
    ImageUploadCreateSerializer,
    SearchResultSerializer,
    UploadCompleteSerializer,
)
from .storage import StorageError, get_storage_client
from .tasks import index_image_asset
from .vector import VectorMatch, get_vector_index


class ImageAssetViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsOwnerOrPublicReadOnly]
    filterset_fields = ["status", "visibility", "content_type"]
    search_fields = ["filename", "tags"]
    ordering_fields = ["created_at", "updated_at", "filename", "size_bytes"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        return ImageAsset.objects.filter(
            Q(owner=user)
            | Q(visibility=ImageVisibility.PUBLIC, status=ImageStatus.INDEXED)
        ).exclude(status=ImageStatus.DELETED)

    def get_serializer_class(self):
        if self.action == "create":
            return ImageUploadCreateSerializer
        if self.action == "status":
            return ImageStatusSerializer
        if self.action == "complete":
            return UploadCompleteSerializer
        return ImageAssetSerializer

    def perform_update(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        storage = get_storage_client()

        with transaction.atomic():
            image_id = uuid4()
            object_key = storage.build_object_key(
                owner_id=request.user.id,
                image_id=str(image_id),
                filename=serializer.validated_data["filename"],
            )
            image = ImageAsset.objects.create(
                id=image_id,
                owner=request.user,
                object_key=object_key,
                filename=serializer.validated_data["filename"],
                content_type=serializer.validated_data["content_type"],
                size_bytes=serializer.validated_data["size_bytes"],
                checksum=serializer.validated_data.get("checksum", ""),
                tags=serializer.validated_data.get("tags", []),
                visibility=serializer.validated_data.get("visibility", ImageVisibility.PRIVATE),
            )

        try:
            upload = storage.create_presigned_upload(
                object_key=image.object_key,
                content_type=image.content_type,
            )
        except StorageError as exc:
            image.mark_failed(str(exc))
            image.save(update_fields=["status", "failure_reason", "updated_at"])
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "image": ImageAssetSerializer(image, context=self.get_serializer_context()).data,
                "upload_url": upload.url,
                "upload_headers": upload.headers,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        image = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if image.owner_id != request.user.id:
            return Response({"detail": "Only the owner can complete this upload."}, status=status.HTTP_403_FORBIDDEN)
        if image.status not in {ImageStatus.UPLOAD_REQUESTED, ImageStatus.FAILED}:
            return Response({"detail": f"Upload cannot be completed from status {image.status}."}, status=status.HTTP_409_CONFLICT)

        storage = get_storage_client()
        try:
            exists = storage.object_exists(image.object_key)
        except StorageError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        if not exists:
            return Response({"detail": "Uploaded object was not found in storage."}, status=status.HTTP_400_BAD_REQUEST)

        image.status = ImageStatus.EMBEDDING_PENDING
        image.failure_reason = ""
        image.save(update_fields=["status", "failure_reason", "updated_at"])
        index_image_asset.delay(str(image.id))
        return Response(ImageStatusSerializer(image).data)

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        return Response(ImageStatusSerializer(self.get_object()).data)

    def destroy(self, request, *args, **kwargs):
        image = self.get_object()
        if image.owner_id != request.user.id:
            return Response({"detail": "Only the owner can delete this image."}, status=status.HTTP_403_FORBIDDEN)

        storage = get_storage_client()
        vector_index = get_vector_index()
        storage.delete_objects([image.object_key, image.thumbnail_key])
        vector_index.delete_image(str(image.id))
        image.status = ImageStatus.DELETED
        image.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


def serialize_matches(matches: list[VectorMatch], *, request) -> list[dict]:
    ids = [match.image_id for match in matches]
    assets = ImageAsset.objects.filter(id__in=ids, status=ImageStatus.INDEXED).filter(
        Q(owner=request.user) | Q(visibility=ImageVisibility.PUBLIC)
    )
    by_id = {str(asset.id): asset for asset in assets}
    ordered = [
        {"score": match.score, "image": by_id[match.image_id]}
        for match in matches
        if match.image_id in by_id
    ]
    return SearchResultSerializer(ordered, many=True, context={"request": request}).data


class TextSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {
                "detail": (
                    "Text search is not available because this deployment uses "
                    "EfficientNetV2 image-only embeddings. Use /api/search/image/."
                )
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class ImageSearchView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        serializer = ImageSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get("image_id"):
            image = ImageAsset.objects.filter(
                Q(owner=request.user) | Q(visibility=ImageVisibility.PUBLIC, status=ImageStatus.INDEXED),
                id=serializer.validated_data["image_id"],
            ).exclude(status=ImageStatus.DELETED).first()
            if image is None:
                return Response({"detail": "Image not found."}, status=status.HTTP_404_NOT_FOUND)
            content = get_storage_client().get_object_bytes(image.object_key)
        else:
            content = serializer.validated_data["image"].read()

        provider = get_embedding_provider()
        vector = provider.embed_image_bytes(content)
        matches = get_vector_index().search(
            vector=vector,
            user_id=request.user.id,
            limit=serializer.validated_data["limit"],
        )
        return Response({"results": serialize_matches(matches, request=request)})
