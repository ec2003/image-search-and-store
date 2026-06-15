"""
Custom S3 storage backend that generates presigned URLs using an external
endpoint when configured, so that clients can access objects through the
Nginx reverse proxy (e.g., https://minio.example.com/...) instead of
the internal MinIO address (http://minio:9000/...).

This implementation avoids mutating shared instance state, preventing
race conditions in multi-threaded/worker environments.

Usage in settings.py:
    DEFAULT_FILE_STORAGE = 'storage.custom_s3.ExternalS3Storage'
    S3_EXTERNAL_ENDPOINT_URL = os.getenv("S3_EXTERNAL_ENDPOINT_URL", None)
"""

from urllib.parse import urlparse

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class ExternalS3Storage(S3Boto3Storage):
    """
    S3 storage that overrides the URL generation to use an external endpoint
    for presigned URLs, while keeping the internal endpoint for actual uploads.

    The key difference from a naive approach: instead of temporarily mutating
    ``self.endpoint_url`` (which is shared state across all requests in a
    worker process), we generate the presigned URL using the internal endpoint
    and then perform a string replacement of the internal host with the
    external host in the resulting URL string.
    """

    def url(self, name, parameters=None, expire=None, http_method=None):
        """
        Generate a presigned URL for the given object name.

        1. Generate the URL using the *internal* endpoint (self.endpoint_url).
        2. If S3_EXTERNAL_ENDPOINT_URL is set, replace the internal host
           (scheme + host + port) with the external host in the returned URL.
        3. Otherwise, return the internal URL as-is.
        """
        # Generate the presigned URL using the internal endpoint
        # This does NOT mutate self.endpoint_url, so there is no race condition.
        internal_url = super().url(name, parameters, expire, http_method)

        external_endpoint = getattr(settings, "S3_EXTERNAL_ENDPOINT_URL", None)
        if not external_endpoint:
            return internal_url

        # Parse the internal endpoint to extract the host part to replace
        internal_parsed = urlparse(self.endpoint_url)
        external_parsed = urlparse(external_endpoint)

        # Build the internal authority (scheme://host:port) and external authority
        internal_authority = f"{internal_parsed.scheme}://{internal_parsed.netloc}"
        external_authority = f"{external_parsed.scheme}://{external_parsed.netloc}"

        # Replace the internal authority with the external one in the URL
        # Using a simple replace is safe because the internal authority
        # only appears once (at the start of the URL path).
        return internal_url.replace(internal_authority, external_authority, 1)