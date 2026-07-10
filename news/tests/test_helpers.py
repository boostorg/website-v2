import socket
from types import SimpleNamespace

import pytest
import responses

from ..helpers import (
    UnsafeURLError,
    _is_public_ip,
    _url_host_is_safe,
    extract_article,
    extract_content,
    safe_get,
)


def _getaddrinfo_returning(*addresses):
    # Build a socket.getaddrinfo stand-in that resolves any host to the given
    # IP string(s), shaped like the real (family, type, proto, canon, sockaddr)
    # tuples that _url_host_is_safe indexes into via info[4][0].
    def _fake(host, port, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (addr, 0))
            for addr in addresses
        ]

    return _fake


# ---------------------------------------------------------------------------
# _is_public_ip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700::1"])
def test_is_public_ip_true_for_globally_routable(ip):
    """Globally routable IPv4/IPv6 literals are accepted."""
    assert _is_public_ip(ip) is True


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.1",  # private
        "192.168.1.1",  # private
        "169.254.169.254",  # link-local (cloud metadata)
        "0.0.0.0",  # unspecified
        "::1",  # IPv6 loopback
    ],
)
def test_is_public_ip_false_for_non_public(ip):
    """Loopback, private, link-local and unspecified ranges are rejected."""
    assert _is_public_ip(ip) is False


def test_is_public_ip_false_for_garbage():
    """A non-IP string is rejected rather than raising."""
    assert _is_public_ip("not-an-ip") is False


# ---------------------------------------------------------------------------
# _url_host_is_safe
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url", ["ftp://example.com/x", "file:///etc/passwd", "javascript:alert(1)"]
)
def test_url_host_is_safe_rejects_non_http_schemes(url):
    """Only http(s) URLs are eligible; other schemes are rejected."""
    assert _url_host_is_safe(url) is False


def test_url_host_is_safe_rejects_localhost_hostname():
    """The literal hostname 'localhost' is blocked without a DNS lookup."""
    assert _url_host_is_safe("http://localhost/admin") is False


def test_url_host_is_safe_rejects_missing_host():
    """A URL with no host (e.g. a bare path) is rejected."""
    assert _url_host_is_safe("http:///just-a-path") is False


def test_url_host_is_safe_accepts_public_ip_literal():
    """A public IP literal passes without resolving DNS."""
    assert _url_host_is_safe("https://8.8.8.8/") is True


def test_url_host_is_safe_rejects_private_ip_literal():
    """A private IP literal is rejected without resolving DNS."""
    assert _url_host_is_safe("http://127.0.0.1/") is False
    assert _url_host_is_safe("http://169.254.169.254/latest/meta-data/") is False


def test_url_host_is_safe_accepts_hostname_resolving_public(monkeypatch):
    """A hostname that resolves only to public IPs is accepted."""
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_returning("93.184.216.34"))
    assert _url_host_is_safe("https://example.com/article") is True


def test_url_host_is_safe_rejects_hostname_resolving_private(monkeypatch):
    """A hostname that resolves to a private IP is rejected (SSRF guard)."""
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_returning("10.0.0.5"))
    assert _url_host_is_safe("http://internal.example.com/") is False


def test_url_host_is_safe_rejects_when_any_address_is_private(monkeypatch):
    """If a host resolves to a mix of public and private IPs, it is rejected."""
    monkeypatch.setattr(
        socket, "getaddrinfo", _getaddrinfo_returning("8.8.8.8", "127.0.0.1")
    )
    assert _url_host_is_safe("http://sneaky.example.com/") is False


def test_url_host_is_safe_rejects_on_dns_failure(monkeypatch):
    """A host that fails to resolve is treated as unsafe."""

    def _boom(*args, **kwargs):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    assert _url_host_is_safe("http://does-not-resolve.example/") is False


# ---------------------------------------------------------------------------
# safe_get
# ---------------------------------------------------------------------------


@responses.activate
def test_safe_get_returns_body_for_public_host():
    """A 200 from a public host returns a response whose body is populated."""
    responses.add(
        responses.GET, "http://8.8.8.8/", body="<html>hello</html>", status=200
    )
    resp = safe_get("http://8.8.8.8/")
    assert resp.status_code == 200
    assert resp.text == "<html>hello</html>"


def test_safe_get_rejects_unsafe_url_without_fetching():
    """A private target is rejected up front (no request is issued)."""
    # No responses registered: if safe_get tried to fetch, the test would error.
    with pytest.raises(UnsafeURLError):
        safe_get("http://127.0.0.1/secret")


@responses.activate
def test_safe_get_revalidates_redirect_target():
    """A public URL that redirects to an internal host is blocked on the hop."""
    responses.add(
        responses.GET,
        "http://8.8.8.8/",
        status=302,
        headers={"Location": "http://127.0.0.1/admin"},
    )
    with pytest.raises(UnsafeURLError):
        safe_get("http://8.8.8.8/")


@responses.activate
def test_safe_get_raises_on_too_many_redirects():
    """A redirect loop is bounded by max_redirects and raises rather than hangs."""
    responses.add(
        responses.GET,
        "http://8.8.8.8/",
        status=302,
        headers={"Location": "http://8.8.8.8/"},
    )
    with pytest.raises(UnsafeURLError):
        safe_get("http://8.8.8.8/", max_redirects=2)


@responses.activate
def test_safe_get_rejects_oversized_declared_content_length(monkeypatch):
    """A Content-Length larger than the cap is rejected before streaming."""
    monkeypatch.setattr("news.helpers.MAX_FETCH_BYTES", 100)
    responses.add(
        responses.GET,
        "http://8.8.8.8/",
        body="small",
        status=200,
        headers={"Content-Length": "999999"},
    )
    with pytest.raises(UnsafeURLError):
        safe_get("http://8.8.8.8/")


@responses.activate
def test_safe_get_caps_oversized_streamed_body(monkeypatch):
    """The body is capped while streaming when no Content-Length declares its size."""
    monkeypatch.setattr("news.helpers.MAX_FETCH_BYTES", 100)
    responses.add(
        responses.GET,
        "http://8.8.8.8/",
        body="x" * 500,
        status=200,
    )
    with pytest.raises(UnsafeURLError):
        safe_get("http://8.8.8.8/")


# ---------------------------------------------------------------------------
# extract_content
# ---------------------------------------------------------------------------


def test_extract_content_returns_visible_text():
    """Visible text is returned line by line with surrounding whitespace trimmed."""
    html = "<html><body><h1>Title</h1><p>Hello world</p></body></html>"
    assert extract_content(html) == "Title\nHello world"


def test_extract_content_strips_script_style_and_head():
    """script/style/head/meta content is removed from the extracted text."""
    html = (
        "<html><head><title>T</title><meta name='x' content='y'></head>"
        "<body><style>.a{color:red}</style>"
        "<script>var x = 1;</script>"
        "<p>Body text</p></body></html>"
    )
    assert extract_content(html) == "Body text"


def test_extract_content_drops_blank_lines():
    """Empty and whitespace-only lines are dropped from the output."""
    html = "<body><p>One</p><p>   </p><p></p><p>Two</p></body>"
    assert extract_content(html) == "One\nTwo"


# ---------------------------------------------------------------------------
# extract_article
# ---------------------------------------------------------------------------


def test_extract_article_returns_trafilatura_body_and_title(monkeypatch):
    """When trafilatura isolates an article, its body and title are returned."""
    monkeypatch.setattr(
        "news.helpers.trafilatura.extract", lambda *a, **k: "  Main article body  "
    )
    monkeypatch.setattr(
        "news.helpers.trafilatura.extract_metadata",
        lambda *a, **k: SimpleNamespace(title="  An Article  "),
    )
    title, body = extract_article("<html>...</html>", url="https://example.com/a")
    assert title == "An Article"
    assert body == "Main article body"


def test_extract_article_falls_back_to_visible_text(monkeypatch):
    """When trafilatura can't isolate an article, the visible-text dump is used."""
    monkeypatch.setattr("news.helpers.trafilatura.extract", lambda *a, **k: None)
    monkeypatch.setattr(
        "news.helpers.trafilatura.extract_metadata", lambda *a, **k: None
    )
    html = "<html><body><p>Fallback body</p></body></html>"
    title, body = extract_article(html)
    assert title == ""
    assert body == extract_content(html) == "Fallback body"


def test_extract_article_handles_missing_title(monkeypatch):
    """A present-but-titleless metadata object yields an empty title."""
    monkeypatch.setattr("news.helpers.trafilatura.extract", lambda *a, **k: "Body")
    monkeypatch.setattr(
        "news.helpers.trafilatura.extract_metadata",
        lambda *a, **k: SimpleNamespace(title=None),
    )
    title, body = extract_article("<html>...</html>")
    assert title == ""
    assert body == "Body"
