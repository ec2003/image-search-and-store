from django.conf import settings

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse


class QdrantService:
    """Thin wrapper around QdrantClient for image vector storage and search."""

    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=settings.QDRANT_TIMEOUT_SECONDS,
        )
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = settings.EMBEDDING_DIMENSIONS

    def ensure_collection(self):
        """Create the collection if it does not exist."""
        try:
            self.client.get_collection(self.collection_name)
        except (UnexpectedResponse, ValueError):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )

    def upsert_vector(self, point_id: str, vector: list[float], payload: dict | None = None) -> None:
        """Insert or update a single vector point."""
        self.client.upsert(
            collection_name=self.collection_name,
            points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload or {})],
        )

    def search(
        self,
        vector: list[float],
        limit: int = 20,
    ) -> list[tuple[str, float, dict]]:
        """Search for the most similar vectors. Returns list of (point_id, score, payload)."""
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
        ).points
        return [(str(r.id), r.score, r.payload or {}) for r in results]

    def delete_vector(self, point_id: str) -> None:
        """Delete a vector point by ID."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.PointIdsList(points=[point_id]),
        )