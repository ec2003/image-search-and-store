from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from .models import ImageAsset, ImageStatus, ImageVisibility


@dataclass(frozen=True)
class VectorMatch:
    image_id: str
    score: float
    payload: dict


class VectorIndexError(RuntimeError):
    pass


class QdrantVectorIndex:
    def __init__(self, *, url: str, api_key: str | None, collection_name: str, timeout: int):
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.timeout = timeout
        self._client = None

    @classmethod
    def from_settings(cls):
        return cls(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            collection_name=settings.QDRANT_COLLECTION,
            timeout=settings.QDRANT_TIMEOUT_SECONDS,
        )

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.url, api_key=self.api_key, timeout=self.timeout)
        return self._client

    def ensure_collection(self, dimensions: int) -> None:
        from qdrant_client import models

        if self.client.collection_exists(self.collection_name):
            existing_dimensions = self._collection_dimensions()
            if existing_dimensions != dimensions:
                raise VectorIndexError(
                    f"Qdrant collection {self.collection_name!r} has vector size "
                    f"{existing_dimensions}, but the active embedding provider emits "
                    f"{dimensions}. Use a model-specific QDRANT_COLLECTION or re-create "
                    "the collection before reindexing."
                )
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
        )

    def _collection_dimensions(self) -> int:
        collection = self.client.get_collection(collection_name=self.collection_name)
        vectors = collection.config.params.vectors
        if hasattr(vectors, "size"):
            return int(vectors.size)
        if isinstance(vectors, dict) and vectors:
            first_vector = next(iter(vectors.values()))
            if hasattr(first_vector, "size"):
                return int(first_vector.size)
        raise VectorIndexError(f"Unable to determine vector size for collection {self.collection_name!r}.")

    def upsert_image(self, image: ImageAsset, vector: list[float]) -> None:
        from qdrant_client import models

        self.ensure_collection(len(vector))
        payload = {
            "image_id": str(image.id),
            "owner_id": str(image.owner_id),
            "visibility": image.visibility,
            "status": image.status,
            "tags": image.tags,
            "content_type": image.content_type,
            "embedding_model": image.embedding_model,
            "embedding_dimensions": image.embedding_dimensions,
            "created_at": image.created_at.isoformat(),
        }
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=str(image.id),
                    vector=vector,
                    payload=payload,
                )
            ],
            wait=True,
        )

    def delete_image(self, image_id: str) -> None:
        from qdrant_client import models

        if not self.client.collection_exists(self.collection_name):
            return
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=[str(image_id)]),
            wait=True,
        )

    def search(self, *, vector: list[float], user_id: int, limit: int) -> list[VectorMatch]:
        from qdrant_client import models

        self.ensure_collection(len(vector))
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="status",
                        match=models.MatchValue(value=ImageStatus.INDEXED),
                    )
                ],
                should=[
                    models.FieldCondition(
                        key="owner_id",
                        match=models.MatchValue(value=str(user_id)),
                    ),
                    models.FieldCondition(
                        key="visibility",
                        match=models.MatchValue(value=ImageVisibility.PUBLIC),
                    ),
                ],
            ),
            limit=limit,
            with_payload=True,
        )
        return [
            VectorMatch(image_id=str(point.id), score=float(point.score), payload=point.payload or {})
            for point in result.points
        ]


def get_vector_index() -> QdrantVectorIndex:
    return QdrantVectorIndex.from_settings()
