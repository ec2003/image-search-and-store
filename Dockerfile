FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# Set environment variables
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=0
ENV TORCH_HOME=/opt/torch-cache
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

RUN mkdir -p /app/static /app/staticfiles /app/media /opt/torch-cache

FROM python:3.14-slim-bookworm AS runtime

ENV PATH="/app/venv/bin:${PATH}"
ENV PYTHONPATH="/app/src:/app"
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TORCH_HOME=/opt/torch-cache

WORKDIR /app/src

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 nonroot \
    && useradd --uid 1000 --gid nonroot --shell /usr/sbin/nologin --create-home nonroot

COPY --from=builder --chown=nonroot:nonroot /app /app
COPY --from=builder --chown=nonroot:nonroot /app/.venv /app/venv
COPY --from=builder --chown=nonroot:nonroot /opt/torch-cache /opt/torch-cache

# Collect static files
RUN python -m django collectstatic --noinput --settings=config.settings 2>/dev/null || true

USER nonroot

# Expose port
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
