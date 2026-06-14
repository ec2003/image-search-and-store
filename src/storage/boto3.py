from storages.backends.s3boto3 import S3Boto3Storage

from django.conf import settings

from storage.custom_s3 import ExternalS3Storage

class ImageStorage(ExternalS3Storage):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = 'images'

class StaticfilesStorage(S3Boto3Storage):
    location = 'static'
    default_acl = 'public-read'
    file_overwrite = False
