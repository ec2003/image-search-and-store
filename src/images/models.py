from django.db import models

from uuid import uuid7


class ImageMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    name = models.CharField(max_length=255)
    image = models.FileField()  # Uses DEFAULT_FILE_STORAGE (ExternalS3Storage)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    vectorized = models.BooleanField(default=False)

    def __str__(self):
        return self.name
