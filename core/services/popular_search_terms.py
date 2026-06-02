"""Refresh PopularSearchTerm rows from Algolia analytics, gated by an LLM
quality check that drops typos / gibberish before any DB write.

Runs weekly via Celery beat (`config/celery.py`); each run looks back two
weeks so peaks survive one week beyond their crest.
"""

import json
import logging
from datetime import date, timedelta
from textwrap import dedent

from algoliasearch.analytics.client import AnalyticsClientSync
from django.conf import settings
from django.db import transaction
from django.db.models.functions import Lower
from openai import OpenAI, OpenAIError

from core.models import PopularSearchTerm, PopularSearchTermExclusion
from versions.models import Version

logger = logging.getLogger(__name__)

# Over-fetch from Algolia so filtering still leaves us enough to store.
ALGOLIA_FETCH_LIMIT = 100
STORED_TOP_N = 20
MIN_QUERY_LEN = 3
MIN_SEARCH_COUNT = 1
# 14-day window matches the weekly task cadence with one week of overlap, so a
# popular term doesn't immediately drop off the moment its peak rolls past.
LOOKBACK_DAYS = 14

# OpenRouter model used to vet candidate terms. Matches the model the news
# summarizer uses (news/tasks.py) so we have one OpenRouter model surface to
# evaluate, monitor cost on, and tune across the codebase.
POPULAR_TERMS_AI_MODEL = "gpt-oss-120b"

_AI_SYSTEM_PROMPT_TEMPLATE = dedent(
    """\
    You filter search queries submitted to boost.org, the C++ Boost libraries
    website. For each query decide KEEP (legitimate library, technical
    concept, or domain topic) or REJECT (typo, gibberish, personal name, test
    input).

    REJECT examples: "jooo", "sdsdsd", "asv", "ho", "joe", "julia",
    "john local", "test search key", "asdf".

    KEEP examples: "asio", "regex", "boost_check_equal", "shared_ptr",
    "concurrency", "data processing", "release process", "ipv6", "filesystem".

    Known Boost library names (case-insensitive). Any query that matches one
    of these — exactly or as an obvious prefix/suffix like "boost.asio" or
    "asio library" — must always be KEEP, regardless of how unfamiliar the
    name might look in isolation:
    {known_libraries}

    For KEEP queries return an all-lowercase display label:
    - Always lowercase ("Data Processing" -> "data processing")
    - Preserve technical identifiers verbatim ("boost_check_equal" stays as-is)
    - Preserve spaces inside multi-word phrases ("data processing" stays "data processing")
    Be deterministic: the same input must always produce the same output.

    Respond with JSON only in this shape:
    {{"kept": [{{"original": "<as-typed>", "label": "<display>"}}, ...]}}
    """
)


def get_known_library_names() -> list[str]:
    """Flagship + core Boost library names, sorted alphabetically.

    These names are sent to the AI as authoritative "always keep" entries and
    are also used as a tie-breaker when ranking equal-count terms (library
    matches sort above non-library terms at the same search count).
    """
    from libraries.models import Library, Tier

    return list(
        Library.objects.filter(tier__in=[Tier.FLAGSHIP, Tier.CORE])
        .order_by("name")
        .values_list("name", flat=True)
    )


def _build_client() -> AnalyticsClientSync:
    return AnalyticsClientSync(
        settings.ALGOLIA.get("app_id"),
        settings.ALGOLIA.get("analytics_api_key"),
        settings.ALGOLIA.get("region"),
    )


def _fetch_top_searches(client: AnalyticsClientSync, index: str) -> list[dict]:
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)
    raw = client.get_top_searches(
        index=index,
        limit=ALGOLIA_FETCH_LIMIT,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    ).to_json()
    return json.loads(raw).get("searches") or []


def _filter_searches(
    searches: list[dict], excluded: set[str]
) -> list[tuple[str, int]]:
    cleaned: list[tuple[str, int]] = []
    for row in searches:
        label = (row.get("search") or "").strip()
        count = row.get("count") or 0
        if len(label) < MIN_QUERY_LEN or count < MIN_SEARCH_COUNT:
            continue
        if label.lower() in excluded:
            continue
        cleaned.append((label, count))
    return cleaned[:STORED_TOP_N]


def ai_filter_terms(
    candidates: list[tuple[str, int]],
    known_libraries: list[str] | None = None,
) -> list[tuple[str, str, int]]:
    """LLM-classify Algolia candidates; return [(original, display_label, count), ...].

    `known_libraries` is rendered into the system prompt so the model never
    rejects a real library it doesn't recognize (e.g., "Asio", "Lockfree").

    Raises OpenAIError, ValueError, or JSONDecodeError on LLM failure — the
    task layer catches these and skips the DB write so last month's data
    stays in place.
    """
    if not candidates:
        return []
    known_libraries = known_libraries or []
    known_libs_block = ", ".join(n.lower() for n in known_libraries) or "(none)"
    system_prompt = _AI_SYSTEM_PROMPT_TEMPLATE.format(known_libraries=known_libs_block)

    client = OpenAI(
        base_url=settings.OPENROUTER_URL, api_key=settings.OPENROUTER_API_KEY
    )
    payload = [{"label": lbl, "count": c} for lbl, c in candidates]
    response = client.chat.completions.create(
        model=POPULAR_TERMS_AI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    data = json.loads(response.choices[0].message.content)
    kept = data.get("kept") or []

    # Defensive: only re-emit entries whose `original` was actually in our
    # payload, in case the model hallucinates a label we never sent.
    counts_by_original = {lbl: c for lbl, c in candidates}
    out: list[tuple[str, str, int]] = []
    for row in kept:
        original = (row.get("original") or "").strip()
        # Force lowercase Python-side so prompt drift can't leak title-cased
        # labels onto the homepage.
        display = (row.get("label") or original).strip().lower()
        if not original or not display or original not in counts_by_original:
            continue
        out.append((original, display, counts_by_original[original]))
    return out


def refresh_popular_search_terms() -> dict[str, int | bool]:
    """Fetch Algolia top searches, LLM-filter, and upsert into PopularSearchTerm.

    On any LLM failure (network / parse / unexpected shape) we log and return
    early with no DB writes, leaving the previous month's data intact.
    """
    version = Version.objects.most_recent()
    if not version:
        logger.warning("popular_search_terms.no_recent_version")
        return {"updated": 0, "new": 0, "ai_kept": 0, "skipped": False}

    searches = _fetch_top_searches(_build_client(), version.stripped_boost_url_slug)
    excluded = {
        t.lower()
        for t in PopularSearchTermExclusion.objects.values_list("term", flat=True)
    }
    cleaned = _filter_searches(searches, excluded)
    known_libraries = get_known_library_names()

    try:
        ai_kept = ai_filter_terms(cleaned, known_libraries=known_libraries)
    except (OpenAIError, ValueError, json.JSONDecodeError) as exc:
        logger.error("popular_search_terms.ai_filter_failed", error=str(exc))
        return {"updated": 0, "new": 0, "ai_kept": 0, "skipped": True}

    # Tie-break: at equal search_count, library-name matches outrank random
    # words. Alphabetical as a final stable tiebreaker.
    known_libs_lower = {n.lower() for n in known_libraries}

    def _sort_key(row):
        original, display_label, count = row
        is_library = (
            display_label.lower() in known_libs_lower
            or original.lower() in known_libs_lower
        )
        return (-count, not is_library, display_label)

    ai_kept.sort(key=_sort_key)

    updated = new = 0
    with transaction.atomic():
        for i, (_original, display_label, count) in enumerate(ai_kept, start=1):
            # AI may re-case the same input differently across months; match
            # case-insensitively so we update in place rather than fragment
            # the table into duplicate "asio" / "Asio" rows.
            existing = (
                PopularSearchTerm.objects.annotate(_lower=Lower("label"))
                .filter(_lower=display_label.lower())
                .first()
            )
            if existing:
                # Refresh the label too — lets historical title-cased rows
                # converge to the current lowercase convention on next match.
                existing.label = display_label
                existing.search_count = count
                existing.rank = i
                existing.save()
                updated += 1
            else:
                PopularSearchTerm.objects.create(
                    label=display_label, search_count=count, rank=i,
                )
                new += 1
    return {"updated": updated, "new": new, "ai_kept": len(ai_kept), "skipped": False}
