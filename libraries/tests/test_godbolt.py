import base64
import json

from libraries.godbolt import (
    GODBOLT_CLIENTSTATE_URL,
    build_compiler_explorer_url,
    resolve_boost_version_id,
)

VERSION_MAP = {"1.88.0": "188", "1.89.0": "189", "1.90.0": "190"}


def _decode(url):
    assert url.startswith(GODBOLT_CLIENTSTATE_URL)
    encoded = url[len(GODBOLT_CLIENTSTATE_URL) :]
    padded = encoded + "=" * (-len(encoded) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def test_no_code_returns_none():
    assert build_compiler_explorer_url("", "1.90.0", version_map=VERSION_MAP) is None
    assert build_compiler_explorer_url(None, "1.90.0", version_map=VERSION_MAP) is None


def test_builds_clientstate_with_matching_boost_version():
    url = build_compiler_explorer_url(
        "int main() { return 0; }", "1.89.0", version_map=VERSION_MAP
    )
    state = _decode(url)
    session = state["sessions"][0]
    assert session["language"] == "c++"
    assert session["source"] == "int main() { return 0; }"
    compiler = session["compilers"][0]
    assert compiler["libs"] == [{"id": "boost", "version": "189"}]


def test_unknown_version_falls_back_to_newest():
    # CE lags: request a newer release than CE has -> newest available (190).
    assert resolve_boost_version_id("1.99.0", version_map=VERSION_MAP) == "190"
    url = build_compiler_explorer_url("x;", "1.99.0", version_map=VERSION_MAP)
    assert _decode(url)["sessions"][0]["compilers"][0]["libs"] == [
        {"id": "boost", "version": "190"}
    ]


def test_no_boost_versions_omits_lib_but_still_builds():
    url = build_compiler_explorer_url("x;", "1.90.0", version_map={})
    state = _decode(url)
    assert state["sessions"][0]["compilers"][0]["libs"] == []
    assert state["sessions"][0]["source"] == "x;"


def test_urlsafe_base64_has_no_path_breaking_chars():
    url = build_compiler_explorer_url(
        "auto x = 1 << 20; /* padding?? */", "1.90.0", version_map=VERSION_MAP
    )
    encoded = url[len(GODBOLT_CLIENTSTATE_URL) :]
    assert "+" not in encoded and "/" not in encoded and "=" not in encoded
