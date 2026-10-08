from django.conf import settings

from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    bucket_name = settings.MEDIA_BUCKET_NAME
    default_acl = "public-read"
    # The buckets allow public reads, so plain URLs work. They stay the same
    # from one request to the next, which lets browsers cache the files, and
    # they never expire.
    querystring_auth = False
    file_overwrite = True
    custom_domain = False
