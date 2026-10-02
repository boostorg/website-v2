import pytest
from model_bakery import baker

from core.models import LatestPathMatchIndicator, RenderedContent
from libraries.path_matcher import PathMatchResult


def test_rendered_content_creation(rendered_content):
    assert rendered_content.cache_key is not None


def test_rendered_content_save():
    content = baker.make(
        "core.RenderedContent",
        content_original=b"Sample original content",
        content_html=b"<p>Sample HTML content</p>",
        content_type=b"text/html",
    )
    content.save()
    content.refresh_from_db()
    assert isinstance(content.content_original, str)
    assert isinstance(content.content_html, str)
    assert isinstance(content.content_type, str)


@pytest.mark.parametrize("version_path", ["1_86_0", "1_90_beta1", "master", "develop"])
def test_rendered_content_direct_match_latest_path(version_path):
    content = RenderedContent(
        cache_key=f"static_content_{version_path}/libs/algorithm/doc/html/index.html",
        latest_path_matched_indicator=LatestPathMatchIndicator.DIRECT_MATCH,
        latest_path_match_class="DirectMatcher",
    )

    assert content.latest_path_match() == PathMatchResult(
        True, "doc/libs/latest/libs/algorithm/doc/html/index.html", "DirectMatcher"
    )
