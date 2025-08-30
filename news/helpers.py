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
