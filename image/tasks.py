import hashlib

from django.conf import settings
from celery import shared_task

from .embeddings import get_embedding_provider
from .image_processing import create_thumbnail, inspect_image
from .models import ImageAsset, ImageStatus
from .storage import get_storage_client
from .vector import get_vector_index


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def index_image_asset(self, image_id: str) -> str:
    image = ImageAsset.objects.select_related("owner").get(pk=image_id)
    if image.status == ImageStatus.DELETED:
        return image_id

    storage = get_storage_client()
    provider = get_embedding_provider()
    vector_index = get_vector_index()

    try:
        image.status = ImageStatus.EMBEDDING_PENDING
        image.failure_reason = ""
        image.save(update_fields=["status", "failure_reason", "updated_at"])

        metadata = storage.get_object_metadata(image.object_key)
        if metadata.content_length and metadata.content_length != image.size_bytes:
            raise ValueError("Uploaded object size does not match metadata.")
        if metadata.content_length > settings.IMAGE_MAX_SIZE_BYTES:
            raise ValueError("Uploaded object exceeds configured image size limit.")
        if metadata.content_type and metadata.content_type != image.content_type:
            raise ValueError("Uploaded object content type does not match metadata.")

        content = storage.get_object_bytes(image.object_key)
        if len(content) != image.size_bytes:
            raise ValueError("Uploaded object byte length does not match metadata.")
        if len(content) > settings.IMAGE_MAX_SIZE_BYTES:
            raise ValueError("Uploaded object exceeds configured image size limit.")
        if image.checksum:
            expected_checksum = image.checksum.lower().removeprefix("sha256:")
            actual_checksum = hashlib.sha256(content).hexdigest()
            if actual_checksum != expected_checksum:
                raise ValueError("Uploaded object checksum does not match metadata.")

        info = inspect_image(content)
        if info.content_type != image.content_type:
            raise ValueError("Uploaded object content type does not match metadata.")

        thumbnail_key = f"users/{image.owner_id}/thumbnails/{image.id}.webp"
        thumbnail = create_thumbnail(content)
        storage.put_object(object_key=thumbnail_key, body=thumbnail, content_type="image/webp")

        vector = provider.embed_image_bytes(content)
        if len(vector) != provider.dimensions:
            raise ValueError("Embedding provider returned an unexpected vector size.")
        image.mark_indexed(
            model_id=provider.model_id,
            dimensions=provider.dimensions,
            width=info.width,
            height=info.height,
            thumbnail_key=thumbnail_key,
        )
        image.save()
        vector_index.upsert_image(image, vector)
    except Exception as exc:
        image.mark_failed(str(exc))
        image.save(update_fields=["status", "failure_reason", "updated_at"])
        raise

    return image_id
