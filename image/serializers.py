from django.conf import settings
from rest_framework import serializers

from .image_processing import inspect_image
from .models import ImageAsset, ImageStatus, ImageVisibility
from .storage import StorageError, get_storage_client


class ImageAssetSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = ImageAsset
        fields = [
            "id",
            "filename",
            "content_type",
            "size_bytes",
            "width",
            "height",
            "checksum",
            "tags",
            "visibility",
            "status",
            "embedding_model",
            "embedding_version",
            "embedding_dimensions",
            "failure_reason",
            "indexed_at",
            "created_at",
            "updated_at",
            "download_url",
            "thumbnail_url",
        ]
        read_only_fields = [
            "id",
            "content_type",
            "size_bytes",
            "width",
            "height",
            "checksum",
            "status",
            "embedding_model",
            "embedding_version",
            "embedding_dimensions",
            "failure_reason",
            "indexed_at",
            "created_at",
            "updated_at",
            "download_url",
            "thumbnail_url",
        ]

    def get_download_url(self, obj: ImageAsset) -> str | None:
        if obj.status == ImageStatus.DELETED:
            return None
        try:
            return get_storage_client().create_presigned_download(obj.object_key)
        except StorageError:
            return None

    def get_thumbnail_url(self, obj: ImageAsset) -> str | None:
        if not obj.thumbnail_key or obj.status == ImageStatus.DELETED:
            return None
        try:
            return get_storage_client().create_presigned_download(obj.thumbnail_key)
        except StorageError:
            return None


class ImageUploadCreateSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.ChoiceField(choices=[])
    size_bytes = serializers.IntegerField(min_value=1)
    checksum = serializers.CharField(max_length=128, required=False, allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(max_length=64), required=False, default=list)
    visibility = serializers.ChoiceField(choices=ImageVisibility.choices, default=ImageVisibility.PRIVATE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content_type"].choices = [(value, value) for value in settings.IMAGE_ALLOWED_CONTENT_TYPES]

    def validate_size_bytes(self, value: int) -> int:
        if value > settings.IMAGE_MAX_SIZE_BYTES:
            raise serializers.ValidationError(f"Image exceeds max size of {settings.IMAGE_MAX_SIZE_BYTES} bytes.")
        return value


class UploadRequestResponseSerializer(serializers.Serializer):
    image = ImageAssetSerializer()
    upload_url = serializers.URLField()
    upload_headers = serializers.DictField(child=serializers.CharField())


class UploadCompleteSerializer(serializers.Serializer):
    pass


class ImageStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageAsset
        fields = ["id", "status", "failure_reason", "indexed_at", "updated_at"]


class TextSearchSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)


class ImageSearchSerializer(serializers.Serializer):
    image_id = serializers.UUIDField(required=False)
    image = serializers.ImageField(required=False)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)

    def validate_image(self, value):
        if value.size > settings.IMAGE_MAX_SIZE_BYTES:
            raise serializers.ValidationError(f"Image exceeds max size of {settings.IMAGE_MAX_SIZE_BYTES} bytes.")
        position = value.tell()
        content = value.read()
        value.seek(position)
        try:
            inspect_image(content)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def validate(self, attrs):
        if not attrs.get("image_id") and not attrs.get("image"):
            raise serializers.ValidationError("Provide either image_id or image.")
        if attrs.get("image_id") and attrs.get("image"):
            raise serializers.ValidationError("Provide either image_id or image, not both.")
        return attrs


class SearchResultSerializer(serializers.Serializer):
    score = serializers.FloatField()
    image = ImageAssetSerializer()
