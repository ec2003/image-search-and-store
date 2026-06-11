from dataclasses import dataclass
from uuid import uuid4

from django.conf import settings
from django.utils.text import get_valid_filename


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObjectMetadata:
    content_length: int
    content_type: str
    etag: str


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    headers: dict[str, str]


class S3ImageStorage:
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region_name: str,
        use_ssl: bool,
        expires_in: int,
    ):
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.use_ssl = use_ssl
        self.expires_in = expires_in
        self._client = None

    @classmethod
    def from_settings(cls):
        return cls(
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            bucket_name=settings.S3_BUCKET_NAME,
            region_name=settings.S3_REGION_NAME,
            use_ssl=settings.S3_USE_SSL,
            expires_in=settings.S3_PRESIGNED_EXPIRE_SECONDS,
        )

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region_name,
                use_ssl=self.use_ssl,
            )
        return self._client

    def ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise StorageError(f"Unable to access bucket {self.bucket_name}: {exc}") from exc
            kwargs = {"Bucket": self.bucket_name}
            if self.region_name != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self.region_name}
            self.client.create_bucket(**kwargs)

    def build_object_key(self, *, owner_id: int, image_id: str, filename: str) -> str:
        safe_name = get_valid_filename(filename) or f"{uuid4()}.bin"
        return f"users/{owner_id}/images/{image_id}/{safe_name}"

    def create_presigned_upload(self, *, object_key: str, content_type: str) -> PresignedUpload:
        self.ensure_bucket()
        try:
            url = self.client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key,
                    "ContentType": content_type,
                },
                ExpiresIn=self.expires_in,
            )
        except Exception as exc:
            raise StorageError(f"Unable to create presigned upload URL: {exc}") from exc
        return PresignedUpload(url=url, headers={"Content-Type": content_type})

    def create_presigned_download(self, object_key: str) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=self.expires_in,
            )
        except Exception as exc:
            raise StorageError(f"Unable to create presigned download URL: {exc}") from exc

    def object_exists(self, object_key: str) -> bool:
        try:
            self.get_object_metadata(object_key)
        except StorageError as exc:
            if getattr(exc, "missing", False):
                return False
            raise
        return True

    def get_object_metadata(self, object_key: str) -> ObjectMetadata:
        from botocore.exceptions import ClientError

        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=object_key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                error = StorageError(f"Object {object_key} was not found.")
                error.missing = True
                raise error from exc
            raise StorageError(f"Unable to inspect object {object_key}: {exc}") from exc
        return ObjectMetadata(
            content_length=int(response.get("ContentLength") or 0),
            content_type=response.get("ContentType") or "",
            etag=(response.get("ETag") or "").strip('"'),
        )

    def get_object_bytes(self, object_key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            return response["Body"].read()
        except Exception as exc:
            raise StorageError(f"Unable to read object {object_key}: {exc}") from exc

    def put_object(self, *, object_key: str, body: bytes, content_type: str) -> None:
        self.ensure_bucket()
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=body,
                ContentType=content_type,
            )
        except Exception as exc:
            raise StorageError(f"Unable to write object {object_key}: {exc}") from exc

    def delete_objects(self, object_keys: list[str]) -> None:
        keys = [key for key in object_keys if key]
        if not keys:
            return
        try:
            self.client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": [{"Key": key} for key in keys]},
            )
        except Exception as exc:
            raise StorageError(f"Unable to delete objects: {exc}") from exc


def get_storage_client() -> S3ImageStorage:
    return S3ImageStorage.from_settings()
