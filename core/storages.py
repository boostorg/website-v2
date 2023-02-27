from django.conf import settings

from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    bucket_name = settings.MEDIA_BUCKET_NAME
    default_acl = "public-read"
    file_overwrite = True
    custom_domain = False
