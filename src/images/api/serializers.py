from rest_framework import serializers

from images.models import ImageMetadata


class ImageMetadataSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ImageMetadata
        fields = ["id", "name", "image", "image_url", "uploaded_at", "file_size", "vectorized"]
        read_only_fields = ["id", "uploaded_at", "file_size", "vectorized"]

    def get_image_url(self, obj):
        try:
            return obj.image.url
        except Exception:
            return None


class ImageUploadSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    image = serializers.ImageField()


class ImageSearchSerializer(serializers.Serializer):
    image = serializers.ImageField()
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)


class SearchResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    image_url = serializers.URLField()
    uploaded_at = serializers.DateTimeField()
    file_size = serializers.IntegerField(allow_null=True)
    score = serializers.FloatField()
