import boto3
from botocore.exceptions import ClientError
import json
import os
import re

from django.conf import settings

from mistletoe import HTMLRenderer
from mistletoe.span_token import SpanToken
from pygments import highlight
from pygments.styles import get_style_by_name as get_style
from pygments.lexers import get_lexer_by_name as get_lexer, guess_lexer
from pygments.formatters.html import HtmlFormatter


def get_content_from_s3(key=None, bucket_name=None):
    """Get content from S3

    Sample keys:
    - 'site/develop/README.md': Returns normally
    - 'site/develop/index.html': Returns normally
    - 'site/develop/INSTALL': Returns normally
    - 'site/develop/boost.css': Returns normally

    Returns the decoded file contents if able

    FIXME: This is a temporary solution to get the content from S3
    and does not handle errors or anything unexpected with grace.
    """

    if not key:
        raise

    if not bucket_name:
        bucket_name = settings.BUCKET_NAME

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name="us-east-1",
    )
    try:
        response = client.get_object(Bucket=bucket_name, Key=key)
        file_content = response["Body"].read().decode("utf-8")
        content_type = response["ContentType"]
        return file_content, content_type
    except ClientError as e:
        # todo: log
        return


# def get_s3_key(content_path, config_filename='stage_static_config.json'):
#     # Read the config file from the project root
#     project_root = settings.BASE_DIR
#     config_file_path = os.path.join(project_root, config_filename)

#     with open(config_file_path, 'r') as f:
#         config_data = json.load(f)

#     # Loop over the site paths in the config file
#     for item in config_data:
#         site_path = item['site_path']
#         s3_path = item['s3_path']

#         # Check if content_path starts with site_path
#         if content_path.startswith(site_path):
#             # Remove site_path from content_path and prepend s3_path
#             s3_key = s3_path + content_path[len(site_path):]
#             return s3_key

#     # Return None if no match is found
#     return None


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
        template = '<iframe width="560" height="315" src="https://www.youtube.com/embed/{target}" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'
        return template.format(target=token.target)
