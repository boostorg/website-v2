"""Build Compiler Explorer (godbolt.org) "Edit in Compiler Explorer" links.

A library's website.adoc [#playground] code is encoded into a godbolt.org
``/clientstate/<base64>`` URL with Boost (matching the viewed release, or the
newest Compiler Explorer offers) pre-selected. Building the URL is a pure,
offline operation; only the Boost version→id lookup needs the CE libraries API,
which is cached.

Verified against Compiler Explorer:
  - ClientState: {sessions:[{id,language,source,compilers:[{id,options,libs}]}]}
  - libs entry: {"id": "boost", "version": "<version id>"}  (e.g. "190")
  - version ids come from /api/libraries/c++ -> boost.versions[].id
  - the base64 is URL-safe (decoded server-side via Buffer.from(x, "base64"))
"""

import base64
import json

import requests
import structlog
from django.core.cache import caches

logger = structlog.get_logger()

GODBOLT_BASE_URL = "https://godbolt.org"
GODBOLT_LIBRARIES_URL = f"{GODBOLT_BASE_URL}/api/libraries/c++"
GODBOLT_CLIENTSTATE_URL = f"{GODBOLT_BASE_URL}/clientstate/"

# A current, widely-available gcc on Compiler Explorer. If it is ever retired
# the playground still opens with the code pre-filled — only the preselected
# compiler is lost — so this is safe to bump when convenient.
DEFAULT_COMPILER_ID = "g142"  # gcc 14.2

_CACHE_ALIAS = "static_content"
_BOOST_VERSIONS_CACHE_KEY = "godbolt_boost_version_map"
_BOOST_VERSIONS_TTL = 60 * 60 * 24  # one day


def _fetch_boost_version_map():
    """Fetch {version_string: version_id} for Boost from the CE libraries API.

    e.g. {"1.90.0": "190", ...}. Returns {} on any failure.
    """
    try:
        response = requests.get(
            GODBOLT_LIBRARIES_URL,
            headers={"Accept": "application/json"},
            timeout=5,
        )
        response.raise_for_status()
        libraries = response.json()
    except (requests.RequestException, ValueError):
        logger.exception("godbolt_libraries_fetch_failed")
        return {}

    for library in libraries:
        if library.get("id") == "boost":
            return {
                version["version"]: version["id"]
                for version in library.get("versions", [])
                if version.get("version") and version.get("id")
            }
    return {}


def get_boost_version_map():
    """Return the cached Boost version→id map, fetching + caching on a miss."""
    cache = caches[_CACHE_ALIAS]
    version_map = cache.get(_BOOST_VERSIONS_CACHE_KEY)
    if version_map is None:
        version_map = _fetch_boost_version_map()
        cache.set(_BOOST_VERSIONS_CACHE_KEY, version_map, _BOOST_VERSIONS_TTL)
    return version_map


def _version_sort_key(version_string):
    return [int(part) if part.isdigit() else 0 for part in version_string.split(".")]


def resolve_boost_version_id(boost_version, version_map=None):
    """Map a Boost release (e.g. "1.90.0") to a CE version id (e.g. "190").

    Falls back to the newest version Compiler Explorer offers when there is no
    exact match (CE lags new Boost releases). Returns None when CE exposes no
    Boost versions.
    """
    if version_map is None:
        version_map = get_boost_version_map()
    if not version_map:
        return None
    if boost_version in version_map:
        return version_map[boost_version]
    newest = max(version_map, key=_version_sort_key)
    return version_map[newest]


def build_compiler_explorer_url(
    code, boost_version, version_map=None, compiler_id=DEFAULT_COMPILER_ID
):
    """Build a godbolt.org /clientstate/ URL with `code` pre-filled and Boost
    selected (matching `boost_version`, else the newest CE offers).

    Returns None when there is no code to load. Boost is omitted from the
    session (rather than blocking the link) if CE's version list is unavailable.
    """
    if not code:
        return None

    version_id = resolve_boost_version_id(boost_version, version_map=version_map)
    libs = [{"id": "boost", "version": version_id}] if version_id else []
    client_state = {
        "sessions": [
            {
                "id": 1,
                "language": "c++",
                "source": code,
                "compilers": [{"id": compiler_id, "options": "", "libs": libs}],
            }
        ]
    }
    payload = json.dumps(client_state, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{GODBOLT_CLIENTSTATE_URL}{encoded}"
