from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def large_static(file_path: str):
    """
    Automatically handles serving large static content based on development vs. production.

    Serves specified content from the local large static file is LOCAL_DEVELOPMENT is True, else serves
    from the static content in S3.
    """
    # Strip any leading slashes to avoid footguns
    file_path = file_path.lstrip("/")
    if settings.LOCAL_DEVELOPMENT:
        return f"{settings.STATIC_URL}static-large/{file_path}"
    else:
        return f"{settings.STATIC_CONTENT_AWS_S3_ENDPOINT_URL}/{settings.STATIC_CONTENT_BUCKET_NAME}/static/{file_path}"
