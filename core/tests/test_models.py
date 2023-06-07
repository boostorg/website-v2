from model_bakery import baker


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
