"""Context captured alongside a feedback submission.

Route, library and version are derived server-side by resolving the URL the
submitter was on, so they cannot be spoofed and need no client cooperation.
Everything the browser alone knows — viewport, console errors, failed requests —
arrives as a JSON blob from the client and is treated as untrusted input.

Server-side exceptions are recorded separately: the 500 page cannot render the
widget, so an error has to outlive its request and wait for the member to report
from wherever they land next.
"""

import json
import sys
from urllib.parse import urlsplit

import structlog
from django.core.cache import cache
from django.urls import Resolver404, resolve
from django.utils import timezone

from libraries.utils import get_version_from_cookie

logger = structlog.get_logger()

DIAGNOSTICS_MAX_CHARS = 20_000
RING_BUFFER_LIMIT = 10
_TEXT_MAX_CHARS = 200
_ENTRY_MAX_CHARS = 500

_TEXT_KEYS = ("viewport", "device", "platform", "search_query")
_LIST_KEYS = ("console_errors", "failed_requests")

SERVER_ERROR_LIMIT = 5
# Long enough to hit a 500, navigate somewhere the widget renders, and write it up.
SERVER_ERROR_TIMEOUT = 900  # seconds


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


def _server_error_key(user_pk):
    return f"feedback_server_errors:user:{user_pk}"


def record_server_error(sender, request=None, **kwargs):
    """Remember an unhandled exception against the member who hit it.

    Connected to `got_request_exception`, which fires while the request is already
    failing, so this swallows everything: a feedback tool must never turn one error
    into two. Django sends no exception with the signal, hence `sys.exc_info()`.

    The read-modify-write below is not atomic, so two exceptions raised at the same
    instant can cost one entry. Left that way on purpose and ultimately and this is
    a best-effort buffer rather than an audit log.
    """
    try:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return

        exc_type, exc, _ = sys.exc_info()
        if exc is None:
            return

        key = _server_error_key(user.pk)
        entries = cache.get(key) or []
        entries.append(
            {
                "type": exc_type.__name__,
                # Clipped: exception text can carry query fragments and personal data.
                "message": str(exc)[:_ENTRY_MAX_CHARS],
                "path": str(getattr(request, "path", ""))[:_TEXT_MAX_CHARS],
                "view": str(getattr(request.resolver_match, "view_name", "") or "")[
                    :_TEXT_MAX_CHARS
                ],
                "request_id": str(getattr(request, "id", ""))[:_TEXT_MAX_CHARS],
                "at": timezone.now().isoformat(timespec="seconds"),
            }
        )
        cache.set(key, entries[-SERVER_ERROR_LIMIT:], timeout=SERVER_ERROR_TIMEOUT)
    except Exception:
        logger.debug("Could not record a server error for feedback", exc_info=True)


def recent_server_errors(user):
    """Server errors this member hit recently, oldest first.

    Left in the cache rather than consumed, so a second report about the same
    failure still carries it. Each entry is timestamped, so triage can tell
    whether the error actually relates to the message.
    """
    try:
        if not user or not user.is_authenticated:
            return {}
        entries = cache.get(_server_error_key(user.pk))
    except Exception:
        # Losing the error context is a far better outcome than losing the report.
        logger.debug("Could not read server errors for feedback", exc_info=True)
        return {}
    return {"server_errors": entries} if entries else {}


def _resolve(page_url):
    path = urlsplit(page_url).path
    if not path:
        return None
    try:
        return resolve(path)
    except Resolver404:
        return None
