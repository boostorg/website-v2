import boto3
from botocore.exceptions import ClientError
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


def get_content_from_s3(key=None, bucket_name=None):
    """
    Get content from S3. Returns the decoded file contents if able
    """
    if not key:
        logger.info(
            "get_content_from_s3_no_key_provided",
            key=key,
            bucket_name=bucket_name,
            function_name="get_content_from_s3",
        )
        raise ValueError("No key provided.")

    if not bucket_name:
        bucket_name = settings.STATIC_CONTENT_BUCKET_NAME

    s3_keys = get_s3_keys(key)

    if not s3_keys:
        s3_keys = [key]

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.STATIC_CONTENT_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.STATIC_CONTENT_AWS_SECRET_ACCESS_KEY,
        region_name="us-east-1",
    )

    for s3_key in s3_keys:
        try:
            response = client.get_object(Bucket=bucket_name, Key=s3_key.lstrip("/"))
            file_content = response["Body"].read()
            content_type = get_content_type(s3_key, response["ContentType"])

            logger.info(
                "get_content_from_s3_success",
                key=key,
                bucket_name=bucket_name,
                s3_key=s3_key,
                function_name="get_content_from_s3",
            )
            return file_content, content_type
        except ClientError as e:
            # Log the error and continue with the next key in the list
            logger.exception(
                "get_content_from_s3_error",
                key=key,
                bucket_name=bucket_name,
                s3_key=s3_key,
                error=str(e),
                function_name="get_content_from_s3",
            )
            pass

        # Handle URLs that are directories looking for `index.html` files
        if s3_key.endswith("/"):
            try:
                original_key = s3_key.lstrip("/")
                index_html_key = f"{original_key}index.html"
                response = client.get_object(Bucket=bucket_name, Key=index_html_key)
                file_content = response["Body"].read()
                content_type = response["ContentType"]
                return file_content, content_type
            except ClientError as e:
                # Log the error and continue with the next key in the list
                logger.exception(
                    "get_content_from_s3_client_error",
                    key=key,
                    bucket_name=bucket_name,
                    s3_key=s3_key,
                    error=str(e),
                    function_name="get_content_from_s3",
                )
                pass

    # Return None if no valid object is found
    logger.info(
        "get_content_from_s3_no_valid_object",
        key=key,
        bucket_name=bucket_name,
        function_name="get_content_from_s3",
    )
    return None


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
