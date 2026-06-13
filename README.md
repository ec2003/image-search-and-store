# Image Search and Store

A Django/DRF system for storing inventory images and searching them with local EfficientNetV2 image embeddings and Qdrant vector similarity.

## Local Development

```powershell
uv sync
$env:DEBUG='True'
uv run python manage.py migrate
uv run python manage.py warm_embedding_model
uv run python manage.py runserver
```

The default embedding provider is `image.embeddings.EfficientNetV2EmbeddingProvider`, using TorchVision EfficientNetV2-S ImageNet weights on CPU. For fast tests or experiments, set `EMBEDDING_PROVIDER=image.embeddings.HashEmbeddingProvider`, `EMBEDDING_MODEL_ID=hash-v1`, and `EMBEDDING_DIMENSIONS=32`.

## Docker Compose

Create a local environment file first:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The image build preloads EfficientNetV2 weights into `TORCH_HOME=/opt/torch-cache`, so API and worker containers do not need an external embedding service.

Useful commands:

```powershell
docker compose exec api python manage.py createsuperuser
docker compose exec api python manage.py test
docker compose exec api python manage.py warm_embedding_model
docker compose exec api python manage.py reindex_images --dry-run
docker compose exec api python manage.py reindex_images
docker compose logs -f worker
docker compose down
```

Default ports:

- API: `http://localhost:8000`
- Public home console: `http://localhost:8000/`
- Admin-only Swagger UI: `http://localhost:8000/swagger/`
- OpenAPI JSON/YAML: `http://localhost:8000/swagger.json`, `http://localhost:8000/swagger.yaml`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- Qdrant: `http://localhost:6333`
- RabbitMQ management: `http://localhost:15672`

## API Overview

- `GET /health/`
- `POST /api/v1/images/` creates image metadata and returns a presigned upload URL.
- `POST /api/v1/images/{id}/complete/` confirms upload and queues indexing.
- `GET /api/v1/images/{id}/status/` returns ingestion status.
- `POST /api/v1/search/image/` searches by uploaded query image or existing `image_id`.
- `POST /api/v1/search/text/` returns `501 Not Implemented`; this deployment uses image-only EfficientNetV2 embeddings.

The home console is public. Anonymous uploads and searches use the internal `PUBLIC_WEB_USERNAME` owner, which defaults to `public-web-user`. API docs are restricted to admin users, and the DRF browsable API renderer is disabled so direct API routes return JSON.

The API uses DRF URL-path versioning. Version `v1` is the default, and the legacy `/api/` routes remain available as compatibility aliases for `/api/v1/`.

When changing embedding models or dimensions, use a new `QDRANT_COLLECTION` or recreate the existing collection, then run `reindex_images`. EfficientNetV2 uses `image_assets_effnetv2_s_1280` by default.
