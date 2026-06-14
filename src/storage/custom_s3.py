"""
Custom S3 storage backend that generates presigned URLs using an external
endpoint when configured, so that clients can access objects through the
Nginx reverse proxy (e.g., https://minio.example.com/...) instead of
the internal MinIO address (http://minio:9000/...).

Usage in settings.py:
    DEFAULT_FILE_STORAGE = 'storage.custom_s3.ExternalS3Storage'
    S3_EXTERNAL_ENDPOINT_URL = os.getenv("S3_EXTERNAL_ENDPOINT_URL", None)
"""

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class ExternalS3Storage(S3Boto3Storage):
    """
    S3 storage that overrides the URL generation to use an external endpoint
    for presigned URLs, while keeping the internal endpoint for actual uploads.
    """

    def url(self, name, parameters=None, expire=None, http_method=None):
        """
        Generate a URL for the given object name.
        
        If S3_EXTERNAL_ENDPOINT_URL is set in Django settings, the presigned
        URL will use that endpoint (which should be the externally-accessible
        MinIO domain proxied through Nginx). Otherwise falls back to the
        default endpoint_url (internal MinIO address).
        """
        external_endpoint = getattr(settings, "S3_EXTERNAL_ENDPOINT_URL", None)
        original_endpoint = self.endpoint_url

        if external_endpoint:
            self.endpoint_url = external_endpoint

        try:
            return super().url(name, parameters, expire, http_method)
        finally:
            self.endpoint_url = original_endpoint