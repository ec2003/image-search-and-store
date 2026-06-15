"""
Celery shared task for generating image embeddings asynchronously.

Uses the same ``EmbeddingModel`` class as the synchronous views — the model
is cached per worker process via ``lru_cache`` inside ``embed_model.py``.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    queue="ml_tasks",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def generate_embedding(self, metadata_id: str):
    """
    Generate a ResNet50 embedding for the uploaded image identified by
    ``metadata_id``, store it in Qdrant, and mark the record as vectorised.
    """
    from images.models import ImageMetadata
    from embeddings.embed_model import EmbeddingModel
    from embeddings.qdrant_service import QdrantService

    # 1. Load the metadata & image bytes -----------------------------------
    try:
        metadata = ImageMetadata.objects.get(id=metadata_id)
    except ImageMetadata.DoesNotExist:
        logger.error("ImageMetadata %s not found — skipping.", metadata_id)
        return

    try:
        metadata.image.seek(0)
        image_bytes = metadata.image.read()
    except Exception as exc:
        logger.exception("Failed to read image %s from storage: %s",
                         metadata_id, exc)
        raise self.retry(exc=exc)

    # 2. Generate embedding ------------------------------------------------
    try:
        vector = EmbeddingModel().encode_from_bytes(image_bytes)
    except Exception as exc:
        logger.exception("Embedding generation failed for %s: %s",
                         metadata_id, exc)
        raise self.retry(exc=exc)

    # 3. Store in Qdrant ---------------------------------------------------
    try:
        qdrant = QdrantService()
        qdrant.ensure_collection()
        qdrant.upsert_vector(
            point_id=str(metadata.id),
            vector=vector.tolist(),
            payload={
                "name": metadata.name,
                "file_size": metadata.file_size,
                "uploaded_at": metadata.uploaded_at.isoformat(),
            },
        )
    except Exception as exc:
        logger.exception("Qdrant upsert failed for %s: %s",
                         metadata_id, exc)
        raise self.retry(exc=exc)

    # 4. Mark as vectorised ------------------------------------------------
    metadata.vectorized = True
    metadata.save(update_fields=["vectorized"])
    logger.info("Embedding generated and stored for image %s.", metadata_id)