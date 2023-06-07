import boto3
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup, Tag
import json
import os
import re
import structlog

from django.conf import settings

from mistletoe import HTMLRenderer
from mistletoe.span_token import SpanToken
from pygments import highlight
from pygments.styles import get_style_by_name as get_style
from pygments.lexers import get_lexer_by_name as get_lexer, guess_lexer
from pygments.formatters.html import HtmlFormatter

logger = structlog.get_logger()


def extract_file_data(response, s3_key):
    """Extracts the file content, content type, and last modified date from an S3
    response object."""
    file_content = response["Body"].read()
    content_type = get_content_type(s3_key, response["ContentType"])
    last_modified = response["LastModified"]
    return {
        "content": file_content,
        "content_type": content_type,
        "last_modified": last_modified,
    }


def get_body_from_html(html_string: str) -> str:
    """Use BeautifulSoup to get the body content from an HTML document, without
    the <body> tag.

    We strip out the <body> tag because we want to use our main Boost template,
    which includes its own <body> tag. Skip any tag with an id containing 'footer'.

    Args:
        html_string (str): The HTML document as a string

    Returns:
        str: The body content as a string
    """
    soup = BeautifulSoup(html_string, "html.parser")
    body = soup.find("body")
    body_content = ""
    if body:
        body_content = "".join(
            str(tag)
            for tag in body.contents
            if isinstance(tag, Tag)
            and not (tag.get("id") and "footer" in tag.get("id"))
        )
    return body_content


def get_content_from_s3(key=None, bucket_name=None):
    """
    Get content from S3. Returns the decoded file contents if able
    """
    if not key:
        raise ValueError("No key provided.")

    bucket_name = bucket_name or settings.STATIC_CONTENT_BUCKET_NAME
    s3_keys = get_s3_keys(key) or [key]
    client = get_s3_client()

    for s3_key in s3_keys:
        file_data = get_file_data(client, bucket_name, s3_key)
        if file_data:
            return file_data

        # Handle URLs that are directories looking for `index.html` files
        if s3_key.endswith("/"):
            original_key = s3_key.lstrip("/")
            index_html_key = f"{original_key}index.html"
            file_data = get_file_data(client, bucket_name, index_html_key)
            if file_data:
                return file_data

    logger.info(
        "get_content_from_s3_no_valid_object",
        key=key,
        bucket_name=bucket_name,
        function_name="get_content_from_s3",
    )
    return {}


def get_content_type(s3_key, content_type):
    """In some cases, manually set the content-type for a given S3 key based on the
    file extension. This is useful for files types that are not recognized by S3, or for
    cases where we want to override the default content-type.

    :param s3_key: The S3 key for the file
    :param content_type: The content-type returned by S3
    :return: The content-type for the file
    """
    if s3_key.endswith(".js"):
        content_type = "application/javascript"
    # adoc files come back from S3 with a generic content type, so we manually set
    # the content type to the (proposed) asciidoc content type:
    # https://docs.asciidoctor.org/asciidoc/latest/faq/
    elif s3_key.endswith(".adoc"):
        content_type = "text/asciidoc"
    return content_type


def get_file_data(client, bucket_name, s3_key):
    """Get the file data from S3. Returns the decoded file contents if able."""
    try:
        response = client.get_object(Bucket=bucket_name, Key=s3_key.lstrip("/"))
        return extract_file_data(response, s3_key)
    except ClientError as e:
        # Log the exception but ignore it otherwise, since it's not necessaruly an error
        logger.exception(
            "get_content_from_s3_error",
            s3_key=s3_key,
            error=str(e),
            function_name="get_content_from_s3",
        )
    return


def get_s3_client():
    """Get an S3 client."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.STATIC_CONTENT_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.STATIC_CONTENT_AWS_SECRET_ACCESS_KEY,
        region_name="us-east-1",
    )


def get_s3_keys(content_path, config_filename="stage_static_config.json"):
    """
    Get the S3 key for a given content path
    """
    # Get the config file for the static content URL settings.
    project_root = settings.BASE_DIR
    config_file_path = os.path.join(project_root, config_filename)

    if not content_path.startswith("/"):
        content_path = f"/{content_path}"

    with open(config_file_path, "r") as f:
        config_data = json.load(f)

    s3_keys = []
    for item in config_data:
        site_path = item["site_path"]
        s3_path = item["s3_path"]

        if site_path == "/" and content_path.startswith(site_path):
            if s3_path in content_path:
                s3_keys.append(content_path)
            else:
                s3_keys.append(os.path.join(s3_path, content_path.lstrip("/")))

        elif content_path.startswith(site_path):
            s3_keys.append(content_path.replace(site_path, s3_path))

    return s3_keys


class Youtube(SpanToken):
    """
    Span token for Youtube shortcodes
    Expected shortcode: `[[ youtube | U4VZ9DRdXAI ]]`
    youtube is thrown out but in the shortcode for readability
    """

    pattern = re.compile(r"\[\[ *(.+?) *\| *(.+?) *\]\]")

    def __init__(self, match):
        self.target = match.group(2)


class PygmentsRenderer(HTMLRenderer):
    formatter = HtmlFormatter()
    formatter.noclasses = True

    def __init__(self, *extras, style="solarized-dark"):
        super().__init__(*extras)
        self.formatter.style = get_style(style)

    def render_block_code(self, token):
        code = token.children[0].content
        lexer = get_lexer(token.language) if token.language else guess_lexer(code)
        return highlight(code, lexer, self.formatter)


class BoostRenderer(PygmentsRenderer):
    def __init__(self):
        super().__init__(Youtube)

    def render_youtube(self, token):
        template = '<iframe width="560" height="315" src="https://www.youtube.com/embed/{target}" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'  # noqa
        return template.format(target=token.target)
