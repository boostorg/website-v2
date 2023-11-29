from bs4 import BeautifulSoup
import pytest
from pytest_django.asserts import assertHTMLEqual

from core.htmlhelper import (
    REMOVE_ALL,
    REMOVE_CSS_CLASSES,
    REMOVE_TAGS,
    convert_h1_to_h2,
    get_library_documentation_urls,
    modernize_legacy_page,
    remove_css,
    remove_duplicate_tag,
    remove_first_tag,
    remove_ids,
    remove_release_classes,
    remove_tables,
    remove_tags,
    style_links,
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


@pytest.mark.parametrize("tag_name, tag_attrs", REMOVE_CSS_CLASSES)
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


def test_convert_h1_to_h2():
    html_content = """
    <html>
        <body>
            <h1>Title 1</h1>
            <h1>Title 2</h1>
            <p>Some text here</p>
        </body>
    </html>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    new_soup = convert_h1_to_h2(soup)

    # Check if there are no h1 tags left
    assert not new_soup.find_all("h1")

    # Check if the h2 tags have the correct content
    h2_tags = new_soup.find_all("h2")
    assert len(h2_tags) == 2
    assert h2_tags[0].get_text() == "Title 1"
    assert h2_tags[1].get_text() == "Title 2"


def test_remove_css():
    # Sample HTML content with specific classes for testing
    html_content = """
    <html>
        <body>
            <div class="body-0">Content 0</div>
            <div class="body-1">Content 1</div>
            <div class="body-2">Content 2</div>
            <p class="class3">Content 3</p>
        </body>
    </html>
    """

    # Parse HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # Call the function with the REMOVE_CSS_CLASSES constant
    soup = remove_css(soup, REMOVE_CSS_CLASSES)

    # Assertions
    # Check each tag in REMOVE_CSS_CLASSES to ensure its class has been removed
    for tag_name, tag_attrs in REMOVE_CSS_CLASSES:
        found_tag = soup.find(tag_name, tag_attrs)
        if found_tag:
            assert "class" not in found_tag.attrs
        else:
            # Handle the case where the tag wasn't found
            print(f"Tag not found: {tag_name} with attributes {tag_attrs}")

    # Check that other tags not in REMOVE_CSS_CLASSES are unaffected
    assert "class" in soup.find("p", {"class": "class3"}).attrs


def test_remove_duplicate_tag():
    # Sample HTML content with duplicate <h2> tags
    html_content = """
      <html>
          <body>
              <h2>Header 1</h2>
              <h2>Header 1</h2>  <!-- Duplicate -->
              <h2>Header 2</h2>
          </body>
      </html>
    """

    # Parse HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # Call the function
    soup = remove_duplicate_tag(soup, "h2")

    # Assertions
    h2_tags = soup.find_all("h2")
    assert len(h2_tags) == 2
    assert h2_tags[0].get_text(strip=True) == "Header 1"
    assert h2_tags[1].get_text(strip=True) == "Header 2"


def test_remove_first_tag():
    # Sample HTML content with multiple occurrences of certain tags
    html_content = """
      <html>
          <body>
              <div id="header1">Header 1</div>
              <div id="header2">Header 2</div>
              <div id="header1">Another Header 1</div>
          </body>
      </html>
      """

    # Parse HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # Tags to be removed
    tags_to_remove = [("div", {"id": "header1"}), ("div", {"id": "header2"})]

    # Call the function
    soup = remove_first_tag(soup, tags_to_remove)

    # Assertions
    # The first occurrence of each tag should be removed
    assert (
        soup.find("div", {"id": "header1"}).get_text(strip=True) == "Another Header 1"
    )
    assert (
        soup.find("div", {"id": "header2"}) is None
    )  # Second div with 'header2' should be removed


def test_remove_ids():
    # Sample HTML content with multiple tags having specific ids
    html_content = """
    <html>
        <body>
            <div id="remove1">Remove me</div>
            <div id="unwrap1"><p>Unwrap me</p></div>
            <div id="keep1">Keep me</div>
        </body>
    </html>
    """

    # Parse HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # Ids to be processed
    ids_to_process = ["remove1", "unwrap1"]

    # Call the function
    soup = remove_ids(soup, ids_to_process)

    # Assertions
    # The tag with id 'remove1' should be removed
    assert soup.find(id="remove1") is None

    # The tag with id 'unwrap1' should be unwrapped
    assert soup.find(id="unwrap1") is None
    assert soup.find("p").get_text(strip=True) == "Unwrap me"

    # The tag with id 'keep1' should not be affected
    assert soup.find(id="keep1") is not None
    assert soup.find(id="keep1").get_text(strip=True) == "Keep me"


def test_remove_release_classes():
    # Sample HTML content with multiple tags having specific classes
    html_content = """
    <html>
        <body>
            <div class="class-to-remove">Remove me</div>
            <div class="class-to-unwrap"><p>Unwrap me</p></div>
            <div class="class-to-keep">Keep me</div>
        </body>
    </html>
    """

    # Parse HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # Classes to be processed
    classes_to_process = ["class-to-remove", "class-to-unwrap"]

    # Call the function
    soup = remove_release_classes(soup, classes_to_process)

    # Assertions
    # The tag with class 'class-to-remove' should be removed
    assert soup.find(class_="class-to-remove") is None

    # The tag with class 'class-to-unwrap' should be unwrapped
    assert soup.find(class_="class-to-unwrap") is None
    assert soup.find("p").get_text(strip=True) == "Unwrap me"

    # The tag with class 'class-to-keep' should not be affected
    assert soup.find(class_="class-to-keep") is not None
    assert soup.find(class_="class-to-keep").get_text(strip=True) == "Keep me"


def test_remove_tables():
    # Sample HTML content with multiple tables
    html_content = """
    <html>
        <body>
            <table class="table-to-remove">Content 1</table>
            <table class="table-to-remove">Content 2</table>
            <table class="other-class">Content 3</table>
            <table>Content 4</table>
        </body>
    </html>
    """

    # Parse HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # The class name of the tables to be removed
    class_name_to_remove = "table-to-remove"

    # Call the function
    soup = remove_tables(soup, class_name_to_remove)

    # Assertions
    assert (
        soup.find_all("table", {"class": class_name_to_remove}) == []
    )  # All tables with class 'table-to-remove' should be removed
    assert (
        soup.find("table", {"class": "other-class"}).get_text(strip=True) == "Content 3"
    )  # This table should not be affected
    assert (
        soup.find("table", class_=False).get_text(strip=True) == "Content 4"
    )  # The table without a class should not be affected


def test_remove_tags():
    # Sample HTML content with multiple tags and attributes
    html_content = """
    <html>
        <body>
            <div class="class-to-remove">Content 1</div>
            <p id="id-to-remove">Content 2</p>
            <span custom-attr="value-to-remove">Content 3</span>
            <div>Content 4</div>
        </body>
    </html>
    """

    # Parse HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # Tags with attributes to be removed
    tags_to_remove = [
        ("div", {"class": "class-to-remove"}),
        ("p", {"id": "id-to-remove"}),
        ("span", {"custom-attr": "value-to-remove"}),
    ]

    # Call the function
    soup = remove_tags(soup, tags_to_remove)

    # Assertions
    assert soup.find("div", {"class": "class-to-remove"}) is None
    assert soup.find("p", {"id": "id-to-remove"}) is None
    assert soup.find("span", {"custom-attr": "value-to-remove"}) is None
    assert (
        soup.find("div").get_text(strip=True) == "Content 4"
    )  # The last div should not be affected


def test_style_links():
    # Sample HTML content with multiple links
    html_content = """
    <html>
        <body>
            <a href="link1.html">Link 1</a>
            <a href="link2.html">Link 2</a>
            <a href="link3.html">Link 3</a>
        </body>
    </html>
    """

    # Parse HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # Class name to be added to all links
    new_class_name = "styled-link"

    # Call the function
    soup = style_links(soup, new_class_name)

    # Assertions
    for a_tag in soup.find_all("a"):
        assert new_class_name in a_tag.get("class", []), "Class not added to link"
