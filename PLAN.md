# Docker Compose Implementation Plan For Image Search And Store

## Summary

Implement the Django image storage/search system as a Docker Compose deployed stack. Django/DRF provides the API, PostgreSQL stores metadata, MinIO stores images, Qdrant stores embeddings, Redis handles cache/rate/task state, RabbitMQ brokers Celery jobs, and Celery workers handle async ingestion. The embedding layer stays pluggable.

## Key Changes

- Wire the existing `image` app into Django settings and project URLs.
- Replace the `django-rest-framework` dependency wrapper with `djangorestframework`; add PostgreSQL, Celery, Redis, boto3/S3, Qdrant, Pillow, and Gunicorn dependencies.
- Add Docker deployment files for the API, worker, PostgreSQL, MinIO, Qdrant, Redis, and RabbitMQ.
- Keep local SQLite optional for lightweight development; Docker Compose uses PostgreSQL.

## Implementation Phases

- Phase 1: Project foundation
  - Fix settings defaults so `manage.py check` works without hidden local assumptions.
  - Add environment-driven config for database, Redis, RabbitMQ, MinIO, Qdrant, media, auth, and debug mode.
  - Add health endpoints and basic DRF configuration.

- Phase 2: Metadata API
  - Create image metadata models with owner, object key, filename, MIME type, size, dimensions, checksum, tags, visibility, status, embedding model/version, and timestamps.
  - Add serializers, permissions, viewsets, pagination, filtering, and admin registration.
  - Implement multi-user access isolation from the beginning.

- Phase 3: Object storage
  - Add MinIO/S3 storage client abstraction.
  - Implement presigned upload creation, upload confirmation, signed download URLs, and deletion cleanup.
  - Validate upload metadata, size limits, MIME type, image dimensions, and object existence before indexing.

- Phase 4: Async ingestion
  - Add Celery app configuration and worker service.
  - Implement idempotent indexing tasks that validate objects, inspect images, generate thumbnails, call the embedding provider, upsert Qdrant, and update metadata status.
  - Use lifecycle states: `upload_requested`, `uploaded`, `embedding_pending`, `indexed`, `failed`, `deleted`.

- Phase 5: Search
  - Add embedding provider interface without locking in a concrete model.
  - Add Qdrant index abstraction and collection bootstrap.
  - Implement text search and image search endpoints.
  - Apply owner/visibility/status filters in Qdrant and re-check permissions against PostgreSQL before returning results.

- Phase 6: Docker Compose deployment
  - Compose services: `api`, `worker`, `postgres`, `minio`, `qdrant`, `redis`, `rabbitmq`.
  - Add persistent named volumes for PostgreSQL, MinIO, Qdrant, Redis, and RabbitMQ.
  - Add startup ordering with health checks where practical.
  - Document commands for build, migrate, create superuser, run tests, start services, and inspect worker logs.

## Test Plan

- Run `uv run python manage.py check`.
- Run Django unit/API tests for auth, ownership, metadata CRUD, upload URL creation, upload completion, status polling, delete behavior, and search permissions.
- Add mocked unit tests for storage, embedding, Qdrant, and Celery task behavior.
- Add Docker Compose smoke test:
  - `docker compose up --build`
  - run migrations
  - create a user
  - request presigned upload
  - confirm upload
  - process indexing task
  - search by text/image
  - verify unauthorized users cannot see private images.

## Assumptions

- Deployment target is Docker Compose, not Kubernetes or a managed PaaS.
- Compose is the default environment for integration testing and production-like local deployment.
- System remains multi-user with private image ownership.
- Embedding provider remains pluggable until a specific model/provider is chosen.
- PostgreSQL stores metadata only; Qdrant stores vectors; MinIO stores image files.
