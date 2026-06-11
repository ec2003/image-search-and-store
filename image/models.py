from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class ImageStatus(models.TextChoices):
    UPLOAD_REQUESTED = "upload_requested", "Upload requested"
    UPLOADED = "uploaded", "Uploaded"
    EMBEDDING_PENDING = "embedding_pending", "Embedding pending"
    INDEXED = "indexed", "Indexed"
    FAILED = "failed", "Failed"
    DELETED = "deleted", "Deleted"


class ImageVisibility(models.TextChoices):
    PRIVATE = "private", "Private"
    PUBLIC = "public", "Public"


class ImageAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="image_assets", on_delete=models.CASCADE)
    object_key = models.CharField(max_length=512, unique=True)
    thumbnail_key = models.CharField(max_length=512, blank=True)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    tags = models.JSONField(default=list, blank=True)
    visibility = models.CharField(
        max_length=16,
        choices=ImageVisibility.choices,
        default=ImageVisibility.PRIVATE,
    )
    status = models.CharField(
        max_length=32,
        choices=ImageStatus.choices,
        default=ImageStatus.UPLOAD_REQUESTED,
        db_index=True,
    )
    embedding_model = models.CharField(max_length=128, blank=True)
    embedding_version = models.CharField(max_length=128, blank=True)
    embedding_dimensions = models.PositiveIntegerField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"], name="img_asset_owner_status_idx"),
            models.Index(fields=["visibility", "status"], name="img_asset_visibility_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.filename} ({self.status})"

    @property
    def is_searchable(self) -> bool:
        return self.status == ImageStatus.INDEXED

    def mark_indexed(self, *, model_id: str, dimensions: int, width: int, height: int, thumbnail_key: str = "") -> None:
        self.status = ImageStatus.INDEXED
        self.embedding_model = model_id
        self.embedding_version = model_id
        self.embedding_dimensions = dimensions
        self.width = width
        self.height = height
        if thumbnail_key:
            self.thumbnail_key = thumbnail_key
        self.failure_reason = ""
        self.indexed_at = timezone.now()

    def mark_failed(self, reason: str) -> None:
        self.status = ImageStatus.FAILED
        self.failure_reason = reason[:2000]
