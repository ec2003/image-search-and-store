from rest_framework import serializers

from images.models import ImageMetadata


class ImageMetadataSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ImageMetadata
        fields = ["id", "name", "image", "image_url", "uploaded_at", "file_size"]
        read_only_fields = ["id", "uploaded_at", "file_size"]

    def get_image_url(self, obj):
        try:
            return obj.image.url
        except Exception:
            return None


class ImageUploadSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    image = serializers.ImageField()