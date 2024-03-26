from bs4 import BeautifulSoup

from core.boostrenderer import get_body_from_html


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
    ("header", {"class": "header"}),
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
REMOVE_CSS_CLASSES = [
    # /docs/libs/1_55_0/libs/exception/doc/boost_exception_all_hpp.html
    ("div", {"class": "body-0"}),
    ("div", {"class": "body-1"}),
    ("div", {"class": "body-2"}),
    # /docs/libs/1_82_0/libs/numeric/conversion/doc/html/index.html
    # ("div", {"class": "toc"}),
    # ("dl", {"class": "toc"}),
    # /doc/libs/boost_1_84_0/libs/container_hash/doc/html/hash.html
    ("div", {"class": "toc2"}),
]


def _insert_in_doc(target, elements, append=True):
    to_add = [
        BeautifulSoup("<!-- BEGIN Manually appending items -->"),
        *elements,
        BeautifulSoup("<!-- END Manually appending items -->"),
    ]
    if append:
        target.extend(to_add)
    else:
        for i in reversed(to_add):
            target.insert(0, i)


def _insert_head(result, head_adding):
    if result.head is None:
        result.html.insert(0, result.new_tag("head"))
    _insert_in_doc(result.head, head_adding)
    if result.head.head is not None:
        result.head.head.unwrap()


def _replace_body(result, original_body, base_body):
    base_body_content = base_body.find("div", {"id": "boost-legacy-docs-body"})
    if base_body_content is not None:
        result.body.replace_with(base_body)
        _insert_in_doc(base_body_content, [original_body])
        result.body.body.unwrap()


def modernize_legacy_page(content, base_html, head_selector="head", insert_body=True):
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
    for tag_name, tag_attrs in REMOVE_CSS_CLASSES:
        for tag in result.find_all(tag_name, tag_attrs):
            tag.attrs.pop("class")

    # Use the base HTML to later extract the <head> and (part of) the <body>
    placeholder = BeautifulSoup(base_html, "html.parser")
    if isinstance(head_selector, str):
        target_head = placeholder.find_all(head_selector)
    elif isinstance(head_selector, dict):
        target_head = placeholder.find_all(**head_selector)
    else:
        target_head = None

    if target_head:
        # Append the <head> taken from the base HTML to the existing (legacy) head
        _insert_head(result, target_head)

    original_body = result.body
    if original_body is None:
        pass
    elif placeholder.body is not None:
        if insert_body:
            # Beautify the legacy body with structure and classes from the
            # modern one, and embed the original body into a:
            # <div id="boost-legacy-docs-body"></div> block
            _replace_body(result, original_body, base_body=placeholder.body)
        else:
            _insert_in_doc(
                result.body,
                placeholder.find("div", {"id": "boost-legacy-docs-header"}),
                append=False,
            )

    content = str(result)

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


### Code to modernize legacy release notes ###


def convert_h1_to_h2(soup):
    """Convert all h1 tags to h2 tags."""
    for h1 in soup.find_all("h1"):
        h1.name = "h2"  # change h1 to h2

    return soup


def format_nested_lists(soup):
    """Flattens nested lists"""
    try:
        top_level_ul = soup.find_all("ul")
    except AttributeError:
        # If there are no ul tags, return soup
        return soup

    for ul in top_level_ul:
        list_items = ul.find_all("li", recursive=False)  # Only direct children of <ul>
        for li in list_items:
            # Extract and remove the non-<ul> contents from <li>
            non_ul_contents = [
                content for content in li.contents if not content.name == "ul"
            ]
            for content in non_ul_contents:
                content.extract()

            # Convert the extracted contents to a string and parse it as HTML
            text_content = "".join(str(content) for content in non_ul_contents).strip()
            if text_content:
                new_soup = BeautifulSoup(text_content, "html.parser")
                h4_tag = soup.new_tag("h4")
                h4_tag.append(new_soup)
                # decompose the li tag and append the new h4 tag
                li.decompose()
                ul.append(h4_tag)

    # Correct the HTML structure
    # Process <h4> and associated <ul> tags
    for h4 in soup.find_all("h4"):
        next_ul = h4.find_next_sibling("ul")
        if next_ul:
            # Clean up <ul> and <li> tags under <h4>
            for li in next_ul.find_all("li"):
                # Unwrap or clean <div> tags inside <li>
                for div in li.find_all("div"):
                    div.unwrap()

            # Reinsert the cleaned <ul> after the <h4>
            h4.insert_after(next_ul)  # remove the h4 tag but keep its content

    return soup


def process_new_libraries(soup):
    """Custom function to process the new libraries section
    of legacy release notes"""
    try:
        new_libraries_divs = soup.find_all(
            "div", class_=lambda x: x and "new_libraries" in x
        )
    except AttributeError:
        # No div found
        return soup

    for div in new_libraries_divs:
        h3_tag = div.find("h3")
        if h3_tag and h3_tag.span:
            # Extract text from h3 span and update h3 tag
            h3_text = h3_tag.span.get_text()
            h3_tag.clear()
            h3_tag.append(h3_text)

        ul_tag = div.find("ul")
        if ul_tag:
            list_items = ul_tag.find_all("li", recursive=False)
            for li in list_items:
                # Extract and restructure contents of div inside li
                inner_div = li.find("div")
                if inner_div:
                    # Move the anchor tag and text outside of the inner div
                    for content in inner_div.contents:
                        li.append(content)
                    # Remove the now-empty div
                    inner_div.decompose()

    return soup


def remove_css(soup, tags):
    """Remove all CSS classes from the given tags."""
    for tag_name, tag_attrs in tags:
        try:
            found_tags = soup.find_all(tag_name, **tag_attrs)
        except AttributeError:
            # No tags found
            continue
        for tag in found_tags:
            if "class" in tag.attrs:
                tag.attrs.pop("class")

    return soup


def remove_duplicate_tag(soup, tag_name):
    """Remove duplicate tags with identical content."""
    try:
        tags = soup.find_all(tag_name)
    except AttributeError:
        # no tags
        return soup

    for i in range(len(tags) - 1):
        current_tag = tags[i]
        next_tag = tags[i + 1]

        # Check if the next tag has the same text content
        if current_tag.get_text(strip=True) == next_tag.get_text(strip=True):
            next_tag.decompose()  # Remove the duplicate
            break

    return soup


def remove_first_tag(soup, tags):
    """Remove the first occurrence of legacy header(s) and other stuff."""
    for tag_name, tag_attrs in tags:
        tag = soup.find(tag_name, tag_attrs)
        if tag:
            tag.decompose()

    return soup


def remove_ids(soup, ids):
    """Remove all tags with the given id."""
    for id_value in ids:
        try:
            tag = soup.find(id=id_value)
        except AttributeError:
            # Tag not found
            continue
        if tag and not tag.get_text(strip=True) == "":
            tag.unwrap()
        elif tag:
            tag.decompose()

    return soup


def remove_release_classes(soup, classes):
    """Remove all tags with the given class name. Unwrap the tag if it has text."""
    for class_value in classes:
        try:
            tags = soup.find_all(class_=class_value)
        except AttributeError:
            # Tag not found
            continue
        for tag in tags:
            if tag and not tag.get_text(strip=True) == "":
                tag.unwrap()
            else:
                tag.decompose()

    return soup


def remove_tables(soup, class_name):
    """Remove all tables with the given class name."""
    for table in soup.find_all("table", class_=class_name):
        table.decompose()

    return soup


def remove_tags(soup, tags):
    """Remove all tags with the given tag name and attributes."""
    for tag_name, tag_attrs in tags:
        for tag in soup.find_all(tag_name, tag_attrs):
            tag.decompose()

    return soup


def style_links(soup, class_name):
    """Add the given class name to all links."""
    for a_tag in soup.find_all("a"):
        a_tag["class"] = class_name

    return soup


def modernize_release_notes(html_content):
    IDS_TO_REMOVE = ["heading", "body" "body-inner", "content"]
    CLASSES_TO_REMOVE = [
        "section",
        "section-0",
        "section-title",
        "section-body",
        "news-title",
        "news-date",
        "news-description",
        "description",
        "link",
        "identifier",
        "library",
    ]
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove unwanted tables
    soup = remove_tables(soup, "download-table")

    # Normalize headings
    soup = convert_h1_to_h2(soup)

    # Remove the first occurrence of legacy header(s) and other stuff
    soup = remove_first_tag(soup, REMOVE_TAGS)

    # Remove all navbar-like divs, if any
    soup = remove_tags(soup, REMOVE_ALL)

    # Remove CSS classes that produce visual harm
    soup = remove_css(soup, REMOVE_CSS_CLASSES)

    # Add custom class to all <a> tags
    soup = style_links(soup, "text-sky-600")

    # # Strip what's left of other things we don't want

    # Unwrap elements with specific IDs
    soup = remove_ids(soup, IDS_TO_REMOVE)

    # Unwrap elements with specific classes
    soup = remove_release_classes(soup, CLASSES_TO_REMOVE)

    # Process divs with class 'new_libraries'
    soup = process_new_libraries(soup)

    # Convert nested <ul>'s to <h4>s with single <ul> inside
    soup = format_nested_lists(soup)

    # Remove duplicate header tags
    soup = remove_duplicate_tag(soup, "h2")

    # Remove unnecessary divs
    try:
        excess_divs = soup.find_all("div")

    except AttributeError:
        # not found
        excess_divs = []

    for div in excess_divs:
        div.unwrap()

    result = str(soup)
    # Replace all links to boost.org with a local link
    content = result.replace("https://www.boost.org/doc/libs/", "/docs/libs/")
    return get_body_from_html(content)
