from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from images.api.serializers import ImageMetadataSerializer, ImageUploadSerializer
from images.models import ImageMetadata


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

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request, *args, **kwargs):
        """
        Upload a new image to the system.
        The image will be stored in MinIO and the metadata will be saved in the database.
        """
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        name = serializer.validated_data["name"]

        metadata = ImageMetadata(
            name=name,
            image=image_file,
            file_size=image_file.size,
        )
        metadata.save()

        return Response(
            ImageMetadataSerializer(metadata).data,
            status=status.HTTP_201_CREATED,
        )