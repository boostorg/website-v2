import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import trafilatura

# Hostnames that should never be fetched server-side, regardless of resolution.
_BLOCKED_HOSTNAMES = {"localhost"}

# Hard cap on a fetched body. Generous for an article, but bounds the memory and
# worker time a single (possibly hostile) response can consume.
MAX_FETCH_BYTES = 2_000_000  # 2 MB


class UnsafeURLError(Exception):
    """Raised when a URL (or a redirect target) points at a non-public host."""


def _is_public_ip(ip_str: str) -> bool:
    """True only for globally routable addresses. ``is_global`` rejects
    loopback, private, link-local, multicast, reserved and unspecified ranges
    (e.g. 127.0.0.1, 10.x, 169.254.169.254, ::1) in one check."""
    try:
        return ipaddress.ip_address(ip_str).is_global
    except ValueError:
        return False


def _url_host_is_safe(url: str) -> bool:
    """True if ``url`` is an http(s) URL whose host resolves only to public IPs.

    Blocks SSRF to internal/loopback/link-local targets. Resolves the hostname
    and requires *every* returned address to be public, so a name that maps to
    a private IP is rejected. IP-literal hosts are checked directly.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname
    if host.lower() in _BLOCKED_HOSTNAMES:
        return False
    # IP literal: check it directly without a DNS lookup.
    try:
        ipaddress.ip_address(host)
        return _is_public_ip(host)
    except ValueError:
        pass
    # Hostname: resolve and require ALL addresses to be public.
    try:
        infos = socket.getaddrinfo(host, parsed.port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(_is_public_ip(addr) for addr in addresses)


def safe_get(
    url: str, *, timeout: float = 10, max_redirects: int = 5
) -> requests.Response:
    """GET ``url`` with SSRF protection.

    Redirects are followed manually so each hop's host is re-validated — a
    public URL can otherwise 302 to an internal one. The response body is capped
    at ``MAX_FETCH_BYTES`` (checked against ``Content-Length`` and again while
    streaming, since the header can be absent or wrong). Raises ``UnsafeURLError``
    if the URL or any redirect target isn't a public http(s) host, or the body
    exceeds the cap; network failures propagate as ``requests.RequestException``.

    Residual gap: DNS rebinding (host resolves public at check time, private at
    connect time) is not closed — that needs pinning the validated IP into the
    connection. TODO: the calling endpoint is not yet login-gated or
    rate-limited; close this gap (or add those controls) before relying on it.
    """
    for _ in range(max_redirects + 1):
        if not _url_host_is_safe(url):
            raise UnsafeURLError(url)
        resp = requests.get(url, timeout=timeout, allow_redirects=False, stream=True)
        if resp.is_redirect:
            location = resp.headers.get("Location")
            resp.close()
            if not location:
                resp._content = b""
                return resp
            url = urljoin(url, location)
            continue
        # Reject early if the server declares an oversized body, then enforce the
        # cap while streaming in case Content-Length is missing or understated.
        declared = resp.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > MAX_FETCH_BYTES:
            resp.close()
            raise UnsafeURLError(f"response too large: {url}")
        chunks, total = [], 0
        for chunk in resp.iter_content(8192):
            total += len(chunk)
            if total > MAX_FETCH_BYTES:
                resp.close()
                raise UnsafeURLError(f"response too large: {url}")
            chunks.append(chunk)
        # Populate the body so callers can use resp.text/.content normally despite
        # stream=True (which otherwise defers — and would bypass — the read).
        resp._content = b"".join(chunks)
        return resp
    raise UnsafeURLError(f"too many redirects: {url}")


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
