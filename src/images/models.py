from django.db import models

from uuid import uuid4

from storage.boto3 import ImageStorage


class ImageMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255)
    image = models.FileField(storage=ImageStorage())
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return self.name