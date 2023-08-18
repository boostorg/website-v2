import pytest
from pytest_django.asserts import assertHTMLEqual

from core.htmlhelper import (
    REMOVE_ALL,
    REMOVE_CSS_CLASSESS,
    REMOVE_TAGS,
    modernize_legacy_page,
    get_library_documentation_urls,
)


BASE_HEAD = """
    <link rel="stylesheet" href="mystyle.css" />
    <meta charset="utf-8" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <style>
      body {background-color: powderblue;}
      h1 {color: red;}
      p {color: blue;}
    </style>
    <meta name="description" content="Unit Test" />
    <meta name="keywords" content="HTML, CSS, JavaScript" />
"""
BASE_TOKEN = "<!-- Add your content here -->"
BASE_BODY = f"""
    <div id="boost-legacy-docs-header">The Header, Log In/Log Out, Menu</div>
    <h1>A very important heading</h1>
    <p>My first paragraph.</p>
    <div id="other-block-content-id">
      <p>My second paragraph.</p>
    </div>
    <div id="boost-legacy-docs-body">
      {BASE_TOKEN}
    </div>
"""
BASE_HTML = f"""<!DOCTYPE html>
    <head>{BASE_HEAD}</head>
    <html>
    <body>{BASE_BODY}</body>
    </html>
"""
LEGACY_HEAD = """
    <title>A Meaningful Page Title</title>
    <link rel="stylesheet" href="old.css" />
"""
LEGACY_BODY = """
   <h1>My Legacy Heading</h1>
   <p>My legacy paragraph.</p>
"""


def _build_tag(tag_name, tag_attrs, inner="Something"):
    return (
        f"<{tag_name}"
        + (" " if tag_attrs else "")
        + " ".join(f'{k}="{v}"' for k, v in tag_attrs.items())
        + (f">{inner}</{tag_name}>" if tag_name != "img" else "/>")
    )


def _build_expected_body(expected_body):
    return BASE_BODY.replace(
        BASE_TOKEN,
        f"""
        {BASE_TOKEN}
        {expected_body}
        """,
    )


def test_modernize_legacy_page_unchanged_empty():
    original = """Something else"""

    result = modernize_legacy_page(original, base_html=BASE_HTML)

    assertHTMLEqual(result, original)


def test_modernize_legacy_page_unchanged_simple():
    original = """<!DOCTYPE html>
    <html>
    </html>
    """

    result = modernize_legacy_page(original, base_html="")

    assertHTMLEqual(result, original)


def test_modernize_legacy_page_unchanged_no_head():
    original = f"""<!DOCTYPE html>
    <html>
    <body>
    {LEGACY_BODY}
    </body>
    </html>
    """

    result = modernize_legacy_page(original, base_html="")

    assertHTMLEqual(result, original)


def test_modernize_legacy_page_unchanged_no_body():
    original = f"""<!DOCTYPE html>
    <head>
    {LEGACY_HEAD}
    </head>
    <html>
    </html>
    """

    result = modernize_legacy_page(original, base_html="")

    assertHTMLEqual(result, original)


def test_modernize_legacy_page_adds_head_if_missing():
    original = """<!DOCTYPE html>
    <html>
    </html>
    """

    result = modernize_legacy_page(original, base_html=BASE_HTML)

    expected = f"""<!DOCTYPE html>
    <html>
    <head>
      <!-- BEGIN Manually appending items -->
      {BASE_HEAD}
      <!-- END Manually appending items -->
    </head>
    </html>
    """
    assertHTMLEqual(result, expected)


def test_modernize_legacy_page_appends_head_if_existing():
    original = f"""<!DOCTYPE html>
    <html>
    <head>
    {LEGACY_HEAD}
    </head>
    </html>
    """

    result = modernize_legacy_page(original, base_html=BASE_HTML)

    expected = f"""<!DOCTYPE html>
    <html>
    <head>
      {LEGACY_HEAD}
      <!-- BEGIN Manually appending items -->
      {BASE_HEAD}
      <!-- END Manually appending items -->
    </head>
    </html>
    """
    assertHTMLEqual(result, expected)


def test_modernize_legacy_page_mangles_body():
    original = f"""<!DOCTYPE html>
    <html>
    <body>
    {LEGACY_BODY}
    </body>
    </html>
    """

    result = modernize_legacy_page(original, base_html=BASE_HTML)

    expected = f"""<!DOCTYPE html>
    <html>
    <head>
      <!-- BEGIN Manually appending items -->
      {BASE_HEAD}
      <!-- END Manually appending items -->
    </head>
    <body>
      {_build_expected_body(LEGACY_BODY)}
    </body>
    </html>
    """
    assertHTMLEqual(result, expected)


@pytest.mark.parametrize("tag_name, tag_attrs", REMOVE_TAGS)
def test_modernize_legacy_page_remove_first_tag_found(tag_name, tag_attrs):
    tag = _build_tag(tag_name, tag_attrs)

    original = f"""<!DOCTYPE html>
    <html>
    <body>
      <h1>My Legacy Heading</h1>
      {tag}
      <p>My legacy paragraph.</p>
      {tag}
    </body>
    </html>
    """

    result = modernize_legacy_page(original, base_html=BASE_HTML)

    body = _build_expected_body(LEGACY_BODY + tag)
    expected = f"""<!DOCTYPE html>
    <html>
    <head>
      <!-- BEGIN Manually appending items -->
      {BASE_HEAD}
      <!-- END Manually appending items -->
    </head>
    <body>
      {body}
    </body>
    </html>
    """
    assertHTMLEqual(result, expected)


@pytest.mark.parametrize("tag_name, tag_attrs", REMOVE_ALL)
def test_modernize_legacy_page_remove_all_tags_found(tag_name, tag_attrs):
    tag = _build_tag(tag_name, tag_attrs)

    original = f"""<!DOCTYPE html>
    <html>
    <body>
      {tag}
      <h1>My Legacy Heading</h1>
      {tag}
      <p>My legacy paragraph.</p>
      {tag}
    </body>
    </html>
    """

    result = modernize_legacy_page(original, base_html=BASE_HTML)

    expected = f"""<!DOCTYPE html>
    <html>
    <head>
      <!-- BEGIN Manually appending items -->
      {BASE_HEAD}
      <!-- END Manually appending items -->
    </head>
    <body>
      {_build_expected_body(LEGACY_BODY)}
    </body>
    </html>
    """
    assertHTMLEqual(result, expected)


@pytest.mark.parametrize("tag_name, tag_attrs", REMOVE_CSS_CLASSESS)
def test_modernize_legacy_page_remove_only_css_class(tag_name, tag_attrs):
    tag_attrs = tag_attrs.copy()
    tag_attrs.setdefault("class", "something-to-remove")
    tag = _build_tag(tag_name, tag_attrs)

    original = f"""<!DOCTYPE html>
    <html>
    <body>
      {tag}
      <h1 class="some-class">My Legacy Heading</h1>
      {tag}
      <p>My legacy paragraph.</p>
      {tag}
      <div class="not-a-match"><p>Hello World</p></div>
      {tag}
    </body>
    </html>
    """

    result = modernize_legacy_page(original, base_html=BASE_HTML)

    # Build expected result
    tag_attrs.pop("class")
    tag_without_class = _build_tag(tag_name, tag_attrs)
    expected_body = f"""
      {tag_without_class}
      <h1 class="some-class">My Legacy Heading</h1>
      {tag_without_class}
      <p>My legacy paragraph.</p>
      {tag_without_class}
      <div class="not-a-match"><p>Hello World</p></div>
      {tag_without_class}
    """
    body = _build_expected_body(expected_body)
    expected = f"""<!DOCTYPE html>
    <html>
    <head>
      <!-- BEGIN Manually appending items -->
      {BASE_HEAD}
      <!-- END Manually appending items -->
    </head>
    <body>
      {body}
    </body>
    </html>
    """
    assertHTMLEqual(result, expected)


def test_get_library_documentation_urls():
    # HTML string for testing
    test_content = """
        <h2><a name="Alphabetically"></a></h2>
        <ul>
            <li><a href="/docs/path1">Library1</a></li>
            <li><a href="/docs/path2">Library2</a></li>
        </ul>
    """
    expected_output = [("Library1", "/docs/path1"), ("Library2", "/docs/path2")]
    result = get_library_documentation_urls(test_content)
    assert result == expected_output


def test_get_library_documentation_urls_no_library_section():
    # HTML string with no library section
    test_content = """
        <h2><a name="NotTheRightSection"></a></h2>
        <ul>
            <li><a href="/docs/path1">Library1</a></li>
            <li><a href="/docs/path2">Library2</a></li>
        </ul>
    """
    result = get_library_documentation_urls(test_content)
    assert result == []


def test_get_library_documentation_urls_no_libraries():
    # HTML string with a library section but no libraries
    test_content = """
        <h2><a name="Alphabetically"></a></h2>
        <ul>
            <!-- No libraries -->
        </ul>
    """
    result = get_library_documentation_urls(test_content)
    assert result == []


def test_get_library_documentation_urls_with_name_and_parent():
    # HTML string for testing
    test_content = """
        <div><a name="CustomSection"></a></div>
        <ul>
            <li><a href="/docs/path1">CustomLibrary1</a></li>
            <li><a href="/docs/path2">CustomLibrary2</a></li>
        </ul>
    """
    expected_output = [
        ("CustomLibrary1", "/docs/path1"),
        ("CustomLibrary2", "/docs/path2"),
    ]
    result = get_library_documentation_urls(
        test_content, name="CustomSection", parent="div"
    )
    assert result == expected_output
