"""Context captured alongside a feedback submission.

Route, library and version are derived server-side by resolving the URL the
submitter was on, so they cannot be spoofed and need no client cooperation.
Everything the browser alone knows — viewport, console errors, failed requests —
arrives as a JSON blob from the client and is treated as untrusted input.
"""

import json
from urllib.parse import urlsplit

from django.urls import Resolver404, resolve

from libraries.utils import get_version_from_cookie

DIAGNOSTICS_MAX_CHARS = 20_000
RING_BUFFER_LIMIT = 10
_TEXT_MAX_CHARS = 200
_ENTRY_MAX_CHARS = 500

_TEXT_KEYS = ("viewport", "device", "platform", "search_query")
_LIST_KEYS = ("console_errors", "failed_requests")


def page_context(request, page_url):
    """Resolve the page the feedback came from into route and version.

    The library is deliberately not stored: page_url already carries the slug,
    and the route is the axis worth grouping on.
    """
    context = {"url_name": "", "view_name": "", "boost_version": ""}

    match = _resolve(page_url)
    if match:
        context["url_name"] = match.url_name or ""
        context["view_name"] = match.view_name or ""
        context["boost_version"] = match.kwargs.get("version_slug") or ""

    if not context["boost_version"]:
        # Cookie mode: the version selector writes a cookie instead of navigating,
        # and that cookie rides along on the feedback POST.
        context["boost_version"] = get_version_from_cookie(request) or ""

    return context


def clean_client_diagnostics(raw):
    """Bound and normalise the browser-reported blob. Anything odd is dropped."""
    if not raw or len(raw) > DIAGNOSTICS_MAX_CHARS:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}

    cleaned = {}
    for key in _TEXT_KEYS:
        value = data.get(key)
        if isinstance(value, (str, int, float)) and str(value):
            cleaned[key] = str(value)[:_TEXT_MAX_CHARS]
    for key in _LIST_KEYS:
        entries = data.get(key)
        if isinstance(entries, list) and entries:
            cleaned[key] = [
                str(entry)[:_ENTRY_MAX_CHARS] for entry in entries[:RING_BUFFER_LIMIT]
            ]
    return cleaned


def _resolve(page_url):
    path = urlsplit(page_url).path
    if not path:
        return None
    try:
        return resolve(path)
    except Resolver404:
        return None
