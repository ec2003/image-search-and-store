# Image Vector Search and Storage

A production-ready web application for uploading, storing, and searching images by visual similarity. Powered by deep learning embeddings and a fully containerized microservices architecture.

## Table of Contents

- [Image Vector Search and Storage](#image-vector-search-and-storage)
  - [Table of Contents](#table-of-contents)
  - [1. Introduction](#1-introduction)
    - [What This Project Is](#what-this-project-is)
    - [Tech Stack](#tech-stack)
    - [System Design](#system-design)
      - [Image Upload Flow (Async)](#image-upload-flow-async)
      - [Image Search Flow (Sync)](#image-search-flow-sync)
  - [2. Installation \& Usage](#2-installation--usage)
    - [Prerequisites](#prerequisites)
    - [Installation Guide](#installation-guide)
    - [Usage Example](#usage-example)
  - [3. License](#3-license)
  - [4. Special Thanks](#4-special-thanks)

---

## 1. Introduction

### What This Project Is

This system allows you to upload images and search for visually similar images using **content-based image retrieval (CBIR)**. Instead of relying on tags or metadata, each image is represented by a **feature vector** extracted from a pre-trained ResNet50 neural network. These vectors are stored in a dedicated vector database, enabling fast similarity search via cosine distance.

**Key features:**

- Upload images via a REST API (with a web frontend).
- Asynchronous embedding generation using Celery workers.
- Store images in MinIO (S3-compatible object storage).
- Search for similar images by uploading a query image.
- Presigned URLs for secure image access through an Nginx reverse proxy.
- Fully containerized with Docker Compose for easy deployment.

### Tech Stack

| Component            | Technology                                              |
| -------------------- | ------------------------------------------------------- |
| **Backend**          | Django 6.x, Django REST Framework                       |
| **Frontend**         | HTML + Vanilla JavaScript (served by Django)            |
| **ML Model**         | PyTorch ResNet50 (pre-trained on ImageNet, 2048-dim embedding) |
| **Vector Database**  | Qdrant                                                  |
| **Object Storage**   | MinIO (S3-compatible)                                   |
| **Relational DB**    | PostgreSQL 16                                           |
| **Message Broker**   | Redis 7 (for Celery)                                    |
| **Task Queue**       | Celery 5.x                                              |
| **Reverse Proxy**    | Nginx (with SSL termination)                            |
| **Containerization** | Docker Compose                                          |
| **Python Deps**      | `uv` (astral-sh), Python 3.14                           |

### System Design

```mermaid
graph TB
    subgraph "Internet"
        USER["Client Browser / curl"]
    end

    subgraph "Docker Network"
        subgraph "Reverse Proxy"
            NGINX["Nginx<br/>Port 443 HTTPS<br/>Port 80 HTTP → HTTPS"]
        end

        subgraph "Application Tier"
            DJANGO["Django API<br/>Gunicorn :8000<br/>REST API + Frontend"]
            CELERY["Celery Worker<br/>ml_tasks queue<br/>Embedding generation"]
        end

        subgraph "Data Tier"
            PG[("PostgreSQL 16<br/>Image Metadata")]
            QDRANT[("Qdrant<br/>Vector DB")]
            REDIS[("Redis 7<br/>Broker + Backend")]
        end

        subgraph "Object Storage"
            MINIO["MinIO<br/>S3 API :9000"]
            MINIO_INIT["minio-init<br/>Bucket bootstrap"]
        end

        %% External connections
        USER -->|"HTTPS :443"| NGINX

        %% Nginx → Backend
        NGINX -->|"/ → http://api:8000"| DJANGO
        NGINX -->|"/pictures → http://minio:9000"| MINIO

        %% Django → Data
        DJANGO -->|"Metadata CRUD"| PG
        DJANGO -->|"Vector search"| QDRANT
        DJANGO -->|"Async task dispatch"| REDIS

        %% Celery → Data
        CELERY -->|"Read image bytes"| MINIO
        CELERY -->|"Store embedding"| QDRANT
        CELERY -->|"Mark vectorized"| PG
        CELERY -->|"Task broker"| REDIS

        %% MinIO init
        MINIO_INIT --->|"Create bucket"| MINIO
    end

    style USER fill:#4a9eff,stroke:#2d7dd2,color:#fff
    style NGINX fill:#009639,stroke:#006b27,color:#fff
    style DJANGO fill:#092e20,stroke:#061f15,color:#fff
    style CELERY fill:#37814a,stroke:#255d34,color:#fff
    style PG fill:#336791,stroke:#244e6a,color:#fff
    style QDRANT fill:#e2007a,stroke:#b3005f,color:#fff
    style REDIS fill:#a41e11,stroke:#7a1410,color:#fff
    style MINIO fill:#c72c48,stroke:#a12238,color:#fff
    style MINIO_INIT fill:#c72c48,stroke:#a12238,color:#fff
```

#### Image Upload Flow (Async)

```mermaid
sequenceDiagram
    participant Client
    participant Nginx
    participant Django
    participant MinIO
    participant PostgreSQL
    participant Redis
    participant Celery
    participant Qdrant

    Client->>Nginx: POST /api/v1/images/upload/ (image + name)
    Nginx->>Django: Reverse proxy
    Django->>MinIO: Save image file
    Django->>PostgreSQL: INSERT metadata (vectorized=False)
    Django->>Redis: Dispatch generate_embedding task
    Django-->>Nginx: 201 Created (metadata + presigned URL)
    Nginx-->>Client: JSON response

    Note over Celery,Qdrant: Async (seconds later)
    Celery->>Redis: Pick up task
    Celery->>MinIO: Read image bytes
    Celery->>Celery: ResNet50 → 2048-dim vector
    Celery->>Qdrant: Upsert vector
    Celery->>PostgreSQL: UPDATE vectorized=True
```

#### Image Search Flow (Sync)

```mermaid
sequenceDiagram
    participant Client
    participant Nginx
    participant Django
    participant MinIO
    participant Qdrant
    participant PostgreSQL

    Client->>Nginx: POST /api/v1/images/search/ (query_image + limit)
    Nginx->>Django: Reverse proxy
    Django->>MinIO: Save query image (temp, for display)
    Note over Django: ResNet50 → 2048-dim vector (synchronous)
    Django->>Qdrant: Cosine similarity search
    Django->>PostgreSQL: SELECT metadata WHERE id IN (matched_ids)
    Django-->>Nginx: 200 OK (results + presigned URLs)
    Nginx-->>Client: JSON response
```

> **Why the custom S3 storage (`ExternalS3Storage`)?**
>
> MinIO runs inside the Docker network at `http://minio:9000`. Clients cannot reach that address from outside. Nginx reverse-proxies MinIO at `https://minio.localhost`. The custom storage backend generates presigned URLs using the internal endpoint and then substitutes the host portion with the external one — without mutating shared state, which eliminates race conditions in multi-worker Gunicorn environments.
---

## 2. Installation & Usage

### Prerequisites

- [Docker](https://docs.docker.com/engine/install/) (with Compose plugin or standalone `docker-compose`)
- Git
- At least **2 GB RAM** available for containers (PyTorch + Qdrant + PostgreSQL)

### Installation Guide

**1. Clone the repository**

```bash
git clone https://github.com/ec2003/image-search-and-storage.git
cd image-search-and-storage
```

**2. Configure environment variables**

Copy the sample environment file (or create `.env` from the table below):

```bash
DEBUG=True # True/False
DJANGO_SECRET_KEY=your-django-secret-key
DJANGO_ALLOWED_HOSTS=your-django-allowed-host-names # Split them with commas
CSRF_TRUSTED_ORIGINS=your-django-allowed-host-names # Split them with commas

DJANGO_SUPERUSER_USERNAME=your-superuser-username
DJANGO_SUPERUSER_PASSWORD=your-superuser-password
DJANGO_SUPERUSER_EMAIL=your-superuser-email # Optional

EMBEDDING_DIMENSIONS=2048
EMBEDDING_TORCH_THREADS=1
TORCH_HOME=/opt/torch-cache

USE_SQLITE=True # True/False
POSTGRES_DB=your-postgres-database-name
POSTGRES_USER=your-postgres-user
POSTGRES_PASSWORD=your-postgres-password 
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=your-minio-access-key
S3_SECRET_ACCESS_KEY=your-minio-secret-key
S3_BUCKET_NAME=pictures
S3_REGION_NAME=us-east-1

# External S3 endpoint for presigned URLs (via Nginx reverse proxy)
# In dev: https://minio.localhost
# In prod: https://minio.example.com
S3_EXTERNAL_ENDPOINT_URL=https://minio.localhost

QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=image_assets_resnet50_2048
QDRANT_TIMEOUT_SECONDS=5

# ── Nginx Reverse Proxy ─────────────────────────
# NGINX_PROXY_ENVIRONMENT: False=dev (self-signed certs, localhost)
#                          True=prod (real certs, custom domain)
NGINX_PROXY_ENVIRONMENT=False
NGINX_SERVER_NAME=localhost
MINIO_SERVER_NAME=minio.localhost
```

| Variable                     | Default                              | Description                                 |
| ---------------------------- | ------------------------------------ | ------------------------------------------- |
| `DEBUG`                      | `True`                               | Django debug mode                          |
| `DJANGO_SECRET_KEY`          | *(auto-generated in `.env`)*         | Django secret key                          |
| `USE_SQLITE`                 | `True`                               | Use SQLite instead of PostgreSQL           |
| `POSTGRES_DB`                | `image_search`                       | PostgreSQL database name                   |
| `POSTGRES_USER`              | `image_search`                       | PostgreSQL user                            |
| `POSTGRES_PASSWORD`          | `image_search_password`              | PostgreSQL password                        |
| `S3_ENDPOINT_URL`            | `http://minio:9000`                  | Internal MinIO endpoint                    |
| `S3_EXTERNAL_ENDPOINT_URL`   | `https://minio.localhost`            | External MinIO endpoint (via Nginx)        |
| `S3_ACCESS_KEY_ID`           | `minioadmin`                         | MinIO access key                           |
| `S3_SECRET_ACCESS_KEY`       | `minioadmin`                         | MinIO secret key                           |
| `S3_BUCKET_NAME`             | `pictures`                           | MinIO bucket name                          |
| `QDRANT_URL`                 | `http://qdrant:6333`                 | Qdrant endpoint                            |
| `QDRANT_COLLECTION`          | `image_assets_resnet50_2048`         | Qdrant collection name                     |
| `EMBEDDING_DIMENSIONS`       | `2048`                               | ResNet50 feature vector dimension           |
| `CELERY_BROKER_URL`          | `redis://redis:6379/0`               | Celery Redis broker                        |
| `CELERY_RESULT_BACKEND`      | `redis://redis:6379/1`               | Celery Redis result backend                |
| `NGINX_SERVER_NAME`          | `localhost`                          | Nginx server name                          |
| `MINIO_SERVER_NAME`          | `minio.localhost`                    | MinIO external hostname                    |

**3. Start the services**

```bash
docker compose up --build -d
```

This will build and start all containers:

| Container          | Purpose                                                       |
| ------------------ | ------------------------------------------------------------- |
| `nginx-proxy`      | Reverse proxy with SSL, serves static files                   |
| `postgres`         | Image metadata database                                       |
| `redis`            | Celery message broker and result backend                      |
| `qdrant`           | Vector database for image embeddings                          |
| `minio`            | S3-compatible object storage for image files                  |
| `minio-init`       | One-shot bootstrap — creates the S3 bucket                    |
| `django-api`       | Django REST API + frontend                                    |
| `celery-worker`    | Celery worker processing `ml_tasks` queue                     |

**4. Create a superuser (if needed)**

The `api` container automatically attempts to create a superuser from `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` on startup. To create one manually:

```bash
docker compose exec api python manage.py createsuperuser
```

**5. Access the application**

| Service                          | URL                              |
| -------------------------------- | -------------------------------- |
| Web frontend + API               | `https://localhost`              |
| Django REST browsable API        | `https://localhost/api/v1/`      |
| Swagger / OpenAPI docs           | `https://localhost/api/docs/`    |
| MinIO web console                | *(not exposed externally)*       |
| MinIO S3 API (via proxy)         | `https://minio.localhost`        |
| PostgreSQL                       | `localhost:5432` (if exposed)    |

> **Note:** Self-signed SSL certificates are generated on first startup, so your browser will show a security warning. This is expected for local development. For production, see the `NGINX_PROXY_ENVIRONMENT` and certificate configuration.

### Usage Example

**Upload an image:**

```bash
curl -k -X POST https://localhost/api/v1/images/upload/ \
  -F "image=@/path/to/sunset.jpg" \
  -F "name=Beautiful Sunset"
```

Response (truncated):

```json
{
  "id": "0190f1a2-...",
  "name": "Beautiful Sunset",
  "image_url": "https://minio.localhost/pictures/images/sunset.jpg?...",
  "uploaded_at": "2026-06-15T14:30:00+07:00",
  "file_size": 1048576,
  "vectorized": false
}
```

The embedding will be generated asynchronously by the Celery worker. Poll the image detail endpoint until `vectorized` becomes `true`:

```bash
curl -k https://localhost/api/v1/images/<id>/
```

**Search for similar images:**

```bash
curl -k -X POST https://localhost/api/v1/images/search/ \
  -F "image=@/path/to/query.jpg" \
  -F "limit=5"
```

Response:

```json
{
  "query_image_url": "https://minio.localhost/pictures/images/search_queries/...",
  "results": [
    {
      "id": "...",
      "name": "Beautiful Sunset",
      "image_url": "https://minio.localhost/pictures/images/sunset.jpg?...",
      "score": 0.9123
    },
    {
      "id": "...",
      "name": "Golden Hour",
      "image_url": "...",
      "score": 0.8841
    }
  ]
}
```

**View the frontend:**

Open `https://localhost` in your browser. The page provides a simple UI for uploading images and searching by similarity.

---

## 3. License

```
Copyright [2026] [ec2003]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

See the [LICENSE](LICENSE) file for details.

---

## 4. Special Thanks

Special thanks to my friend [truong51972](https://github.com/truong51972) for supervising and supporting by providing system design knowledges in order to complete this project.
