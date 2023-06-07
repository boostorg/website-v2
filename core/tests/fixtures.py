import pytest
from model_bakery import baker


@pytest.fixture
def rendered_content(db):
    return baker.make(
        "core.RenderedContent",
        cache_key="cache-key",
        content_original="Sample content",
        content_html="<p>Sample content</p>",
    )
