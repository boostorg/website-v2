from ..boostrenderer import get_s3_keys


def test_get_s3_keys():
    """
    Test cases:

    - "/marshmallow/index.html" -> "site/develop/tools/auto_index/index.html"
    - "/marshmallow/about.html" -> "site/develop/doc/html/about.html"
    - "/rst.css" -> "site/develop/rst.css"
    - "/site/develop/doc/html/about.html" -> "site/develop/doc/html/about.html"
    """

    assert "/site/develop/tools/auto_index/index.html" in get_s3_keys(
        "marshmallow/index.html"
    )
    # assert "/site/develop/doc/html/about.html" in get_s3_keys("marshmallow/about.html")
    # assert "/site/develop/rst.css" in get_s3_keys("/rst.css")
    # assert "/site/develop/doc/html/about.html" in get_s3_keys("/doc/html/about.html")
