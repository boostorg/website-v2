from ..boostrenderer import get_content_type, get_s3_keys


def test_get_content_type():
    assert get_content_type("/marshmallow/index.html", "text/html"), "text/html"
    assert get_content_type("/rst.css", "text/css"), "text/css"
    assert get_content_type("/site/develop/help.adoc", "text/html"), "text/asciidoc"
    assert get_content_type(
        "/site/develop/doc/html/scripts.js", "text/html"
    ), "application/javascript"


def test_get_s3_keys():
    """
    Test cases:

    - "/marshmallow/index.html" -> "site/develop/tools/auto_index/index.html"
    - "/marshmallow/about.html" -> "site/develop/doc/html/about.html"
    - "/rst.css" -> "site/develop/rst.css"
    - "/site/develop/doc/html/about.html" -> "site/develop/doc/html/about.html"
    """

    assert "/site-docs/develop/user-guide/index.html" in get_s3_keys(
        "/doc/user-guide/index.html"
    )
    assert "/site-docs/develop/contributor-guide/index.html" in get_s3_keys(
        "/doc/contributor-guide/index.html"
    )
    assert "/site-docs/develop/formal-reviews/index.html" in get_s3_keys(
        "/doc/formal-reviews/index.html"
    )
    assert "/site-docs/develop/release-process/index.html" in get_s3_keys(
        "/doc/release-process/index.html"
    )
