from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def large_static(file_path: str):
    """
    Automatically handles serving large static content based on development vs. production.

    Serves specified content from the local large static file if LOCAL_DEVELOPMENT is True, else serves
    from the static content in S3.
    """
    # Strip any leading slashes to avoid footguns
    file_path = file_path.lstrip("/")

    # Strip any trailing slashes to avoid assumptions
    static_url = settings.STATIC_URL.rstrip("/")
    static_aws_endpoint = settings.STATIC_CONTENT_AWS_S3_ENDPOINT_URL.rstrip("/")

    if settings.LOCAL_DEVELOPMENT:
        return f"{static_url}/static-large/{file_path}"
    else:
        return f"{static_aws_endpoint}/{settings.STATIC_CONTENT_BUCKET_NAME}/static/{file_path}"
