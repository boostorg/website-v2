from bs4 import BeautifulSoup


# List HTML elements (with relevant attributes) to remove the FIRST occurrence
REMOVE_TAGS = [
    # Remove custom headers, these vary from lib to lib, it's usually a table
    # /docs/libs/1_82_0/ (maps to index.html and has removable headers)
    (
        "table",
        {
            "bgcolor": "#D7EEFF",
            "border": "0",
            "bordercolor": "#111111",
            "cellpadding": "5",
            "cellspacing": "0",
            "style": "border-collapse: collapse",
        },
    ),
    # /doc/libs/1_82_0/libs/functional/index.html
    # /doc/libs/1_82_0/libs/functional/negators.html
    # /doc/libs/1_82_0/libs/functional/ptr_fun.html
    # /doc/libs/1_82_0/libs/functional/function_traits.html
    # /doc/libs/1_82_0/libs/functional/mem_fun.html
    # /doc/libs/1_82_0/libs/functional/binders.html
    # /doc/libs/1_82_0/libs/uuid/doc/index.html
    # /doc/libs/1_82_0/libs/rational/index.html
    # /doc/libs/1_82_0/libs/format/index.html
    ("table", {"bgcolor": "#007F7F", "border": "1", "cellpadding": "2"}),
    # /docs/libs/1_82_0/libs/multi_array/doc/index.html (lowercase)
    ("table", {"bgcolor": "#007f7f", "border": "1", "cellpadding": "2"}),
    # /docs/libs/1_82_0/libs/gil/doc/html/index.html
    (
        "table",
        {
            "summary": "header",
            "width": "100%",
            "cellspacing": "0",
            "cellpadding": "7",
            "border": "0",
        },
    ),
    # very prominent header
    # /docs/libs/1_82_0/libs/locale/doc/html/index.html
    ("div", {"id": "top"}),
    # almost every other page has this as a header
    ("table", {"cellpadding": "2", "width": "100%"}),
]

# List HTML elements (with relevant attributes) to remove ALL occurrences
REMOVE_ALL = [
    # the legacy logo referenced from multiple pages at different depths
    ("img", {"src": "../../../../boost.png"}),
    ("img", {"src": "../../../boost.png"}),
    ("img", {"src": "../../boost.png"}),
    ("img", {"src": "../boost.png"}),
    ("img", {"src": "boost.png"}),
    ("img", {"src": "images/boost.png"}),
    # These are navigation controls, like next/up/prev. Do not remove for now.
    # most pages, e.g. /docs/libs/1_82_0/libs/iterator/doc/html/index.html
    # ("div", {"class": "spirit-nav"}),
    # /docs/libs/1_82_0/libs/gil/doc/html/index.html
    # ("div", {"class": "navbar"}),
    # /docs/libs/1_82_0/libs/iostreams/doc/guide/generic_streams.html
    # ("div", {"class": "nav"}),
]

# List HTML elements (with relevant attributes) to remove ONLY their CSS class
REMOVE_CSS_CLASSESS = [
    # /docs/libs/1_55_0/libs/exception/doc/boost_exception_all_hpp.html
    ("div", {"class": "body-0"}),
    ("div", {"class": "body-1"}),
    ("div", {"class": "body-2"}),
    # /docs/libs/1_82_0/libs/numeric/conversion/doc/html/index.html
    ("div", {"class": "toc"}),
    ("dl", {"class": "toc"}),
]


def _insert_head(result, base_head):
    to_add = [
        BeautifulSoup("<!-- BEGIN Manually appending head -->"),
        base_head,
        BeautifulSoup("<!-- END Manually appending head -->"),
    ]
    if result.head is None:
        for i in reversed(to_add):
            result.html.insert(0, i)
    else:
        for i in to_add:
            result.head.append(i)
    if result.head.head is not None:
        result.head.head.unwrap()


def _replace_body(result, original_body, base_body):
    base_body_content = base_body.find("div", {"id": "boost-legacy-body"})
    to_add = [
        BeautifulSoup("<!-- BEGIN Manually appending body -->"),
        original_body,
        BeautifulSoup("<!-- END Manually appending body -->"),
    ]
    if base_body_content is not None:
        result.body.replace_with(base_body)
        for i in to_add:
            base_body_content.append(i)
        result.body.body.unwrap()


def modernize_legacy_page(content, base_html, insert_body=True, insert_head=True):
    result = BeautifulSoup(content, "html.parser")
    if result.html is None:
        # Not an HTML file we care about
        return content

    # Remove the first occurrence of legacy header(s) and other stuff
    for tag_name, tag_attrs in REMOVE_TAGS:
        tag = result.find(tag_name, tag_attrs)
        if tag:
            tag.decompose()

    # Remove all navbar-like divs, if any
    for tag_name, tag_attrs in REMOVE_ALL:
        for tag in result.find_all(tag_name, tag_attrs):
            tag.decompose()

    # Remove CSS classes that produce visual harm
    for tag_name, tag_attrs in REMOVE_CSS_CLASSESS:
        for tag in result.find_all(tag_name, tag_attrs):
            tag.attrs.pop("class")

    # Use the base HTML to later extract the <head> and (part of) the <body>
    placeholder = BeautifulSoup(base_html, "html.parser")

    if placeholder.head is not None and (insert_body or insert_head):
        # Append the <head> taken from the base HTML to the existing (legacy) head
        _insert_head(result, base_head=placeholder.head)

    original_body = result.body
    if original_body is None:
        pass
    elif placeholder.body is not None:
        if insert_body:
            # Beautify the legacy body with structure and classes from the new one,
            # and embed the original body into an "<div id="boost-legacy-body"> block
            _replace_body(result, original_body, base_body=placeholder.body)
        else:
            result.body.insert(
                0, placeholder.body.find("div", {"id": "boost-modern-header"})
            )

    content = result.prettify()

    # Replace all links to boost.org with a local link
    content = content.replace("https://www.boost.org/doc/libs/", "/docs/libs/")

    return content


def get_library_documentation_urls(content, name="Alphabetically", parent="h2"):
    """
    Takes HTML content and returns a list of tuples containing library
    names and the paths to those libraries' docs. This is used to
    update the documentation_url field on LibraryVersion objects.

    Args:
        content (str): HTML content from the libraries.htm file. For example, the
        HTML content from `/docs/libs/1_82_0/libs/libraries.htm`.
        name (str): The name of the section to search for. Defaults to "Alphabetically".
        parent (str): The parent tag of the section to search for. Defaults to "h2".
            Together, parent and string define what HTML tag to search for. For example,
            if parent="h2" and name="Alphabetically", this function will search for
            <h2 name="Alphabetically">.

    Returns:
        list: A list of tuples containing library names and the paths to those
        libraries' docs. For example, `[(library_name, path), ...]`.
    """
    soup = BeautifulSoup(content, "html.parser")

    # Find the tag that contains the list of libraries
    tag = soup.find("a", attrs={"name": name})

    if not tag:
        return []

    # Get the next <ul> tag, which contains the list of libraries
    library_list_tag = tag.find_parent(parent).find_next_sibling("ul")

    # Now get all the items in the list
    library_tags = library_list_tag.find_all("li")
    if not library_tags:
        return []

    results = []
    for library_tag in library_tags:
        # Get the url path for the documentation
        url_path = library_tag.find("a")["href"]
        # Get the library name
        library_name = library_tag.find("a").get_text()
        results.append((library_name, url_path))

    return results
