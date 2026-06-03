from bs4 import BeautifulSoup


def extract_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    non_visible_tags = ["style", "script", "head", "meta", "[document]"]
    for script_or_style in soup(non_visible_tags):
        script_or_style.decompose()
    text = soup.get_text(separator="\n")
    lines = (line.strip() for line in text.splitlines())
    # drop blank lines
    minimized = [line for line in lines if line]
    return "\n".join(minimized)


# Specific to the cppalliance.org blog template — the Auto-Generate Description
# button on Link posts is restricted to that domain (see linkUrlValid in
# templates/news/v3/create.html), so these selectors target that template
# exactly. If the site's template changes, both selectors need updating.
CPPALLIANCE_TITLE_SELECTOR = (
    "#body > div > div > section > article > div.title-section.center > h2"
)
CPPALLIANCE_BODY_SELECTOR = (
    "#body > div > div > section > article > "
    "div.text-xxs.content-text.generated-content"
)


def extract_cppalliance_post(html: str) -> tuple[str, str]:
    """Extract (title, body) text from a cppalliance.org blog post.

    Returns empty strings for either piece that's missing — callers should
    treat an empty body as "couldn't read the page" and surface that to the
    user as the inline error.
    """
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(CPPALLIANCE_TITLE_SELECTOR)
    body_el = soup.select_one(CPPALLIANCE_BODY_SELECTOR)
    title = title_el.get_text(strip=True) if title_el else ""
    body = body_el.get_text(separator="\n", strip=True) if body_el else ""
    return title, body
