import re
from django import template

register = template.Library()


@register.simple_tag
def doc_url_with_latest(documentation_url, version_str, latest_str):
    """
    Replace the version segment in a documentation URL with the latest string.
    Only replaces if version_str matches latest_str.

    Usage: {% doc_url_with_latest library_version.documentation_url version_str LATEST_RELEASE_URL_PATH_STR %}
    Example: /doc/libs/1_89_0/libs/accumulators/index.html -> /doc/libs/latest/libs/accumulators/index.html
    """
    if not documentation_url or version_str != latest_str:
        return documentation_url

    # Pattern matches /doc/libs/{version}/ where version is typically digits/underscores
    return re.sub(r"(doc/libs/)([^/]+)(\S+)", rf"\1{latest_str}\3", documentation_url)
