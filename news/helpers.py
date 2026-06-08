from bs4 import BeautifulSoup
import trafilatura


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


def extract_article(html: str, url: str | None = None) -> tuple[str, str]:
    """Extract ``(title, body)`` of the main article from an arbitrary web page.

    trafilatura isolates the main content and strips boilerplate (navigation,
    footers, comments, ads). That keeps the summarizer focused — and cheaper —
    versus feeding it the whole page. When trafilatura can't isolate an article
    (unusual template, very thin page) the body falls back to the naive
    visible-text dump in ``extract_content`` so server-rendered HTML still
    yields something.

    Returns ``("", "")`` only when even the fallback is empty — callers should
    treat an empty body as "couldn't read the page" and degrade gracefully
    (skip auto-summarization / surface an inline error) rather than summarizing
    junk. Note: pages rendered client-side (SPAs), paywalled, or behind anti-bot
    blocks won't yield text here regardless of which extractor runs.
    """
    body = (
        trafilatura.extract(html, url=url, include_comments=False, include_tables=False)
        or ""
    ).strip()
    if not body:
        body = extract_content(html)

    title = ""
    metadata = trafilatura.extract_metadata(html, default_url=url)
    if metadata and metadata.title:
        title = metadata.title.strip()

    return title, body
