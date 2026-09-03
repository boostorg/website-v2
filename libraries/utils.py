import random
import string
import re
from itertools import islice
from types import SimpleNamespace
from typing import TYPE_CHECKING

import boto3
import structlog
import tempfile
from datetime import datetime, timezone

from botocore.client import BaseClient
from dateutil.relativedelta import relativedelta

from dateutil.parser import ParserError, parse
from django.conf import settings
from django.db.models import Count, F, QuerySet, prefetch_related_objects
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone as django_timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.timesince import timesince

from libraries.constants import (
    DEFAULT_LIBRARIES_LANDING_VIEW,
    SELECTED_BOOST_VERSION_COOKIE_NAME,
    SELECTED_LIBRARY_VIEW_COOKIE_NAME,
    LATEST_RELEASE_URL_PATH_STR,
    LEGACY_LATEST_RELEASE_URL_PATH_STR,
    DEVELOP_RELEASE_URL_PATH_STR,
    MASTER_RELEASE_URL_PATH_STR,
)
from versions.models import Version

logger = structlog.get_logger()

STATS_COMMITS_BAR_HEIGHT_MAX_PX = 120
STATS_COMMITS_BAR_HEIGHT_MIN_PX = 8

if TYPE_CHECKING:
    from libraries.models import Library, LibraryVersion


def get_commit_data_by_release_for_library(library, limit=20):
    """Return list of { release, commit_count } for a library, ordered by release (oldest first).

    Used by the library detail page and by the V3 examples “commits per release” lookup.
    """
    from .models import LibraryVersion

    qs = (
        LibraryVersion.objects.filter(
            library=library,
            version__in=Version.objects.minor_versions(),
        )
        .annotate(count=Count("commit"), version_name=F("version__name"))
        .order_by("-version__name")
    )[:limit]
    return [
        {"release": x.version_name.removeprefix("boost-"), "commit_count": x.count}
        for x in reversed(list(qs))
    ]


def get_commit_data_by_release(limit=10):
    """Return list of { release, commit_count } across all Boost libraries per
    minor release, ordered by release (oldest first).

    Used by the homepage "Boost in numbers" chart.
    """
    qs = (
        Version.objects.minor_versions()
        .annotate(count=Count("library_version__commit"))
        .order_by("-name")
    )[:limit]
    return [
        {"release": v.name.removeprefix("boost-"), "commit_count": v.count}
        for v in reversed(list(qs))
    ]


def commit_data_to_stats_bars(commit_data):
    """Convert commit_data_by_release (list of { release, commit_count }) to stats bar format.

    Returns list of { label, height_px, commit_count } with heights scaled to
    STATS_COMMITS_BAR_HEIGHT_*. commit_count is preserved for tooltip rendering.
    """
    if not commit_data:
        return []
    counts = [d["commit_count"] for d in commit_data]
    max_count = max(counts) or 1
    return [
        {
            "label": d["release"],
            "height_px": max(
                STATS_COMMITS_BAR_HEIGHT_MIN_PX,
                round(
                    (d["commit_count"] / max_count) * STATS_COMMITS_BAR_HEIGHT_MAX_PX
                ),
            ),
            "commit_count": d["commit_count"],
        }
        for d in commit_data
    ]


def decode_content(content):
    """Decode bytes to string."""
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return content


def generate_fake_email(val: str) -> str:
    """Slugify a string to make a fake email.

    Would not necessarily be unique -- this is a lazy way for us to avoid creating
    multiple new user records for one contributor who contributes to multiple libraries.
    """
    slug = slugify(val)
    local_email = slug.replace("-", "_")[:50]
    return f"{local_email}@example.com"


def generate_random_string(length=4):
    characters = string.ascii_letters
    random_string = "".join(random.choice(characters) for _ in range(length))
    return random_string


def format_duration(seconds: int) -> str:
    """Human label for a duration, e.g. 86400 -> "1 day".

    Mirrors the mailing-list confirm flow's formatting so expiry copy reads
    the same across both email verification flows.
    """
    now = django_timezone.now()
    return timesince(now - relativedelta(seconds=seconds), now, depth=1)


def version_within_range(
    version: str, min_version: str = None, max_version: str = None
):
    """Direct string comparison, assuming 'version', 'min_version', and 'max_version'
    follow the same format.

    Expects format `boost-1.84.0`
    """
    if min_version and version < min_version:
        return False
    if max_version and version > max_version:
        return False
    return True


def get_first_last_day_last_month():
    now = datetime.now()
    first_day_this_month = now.replace(day=1)
    last_day_last_month = first_day_this_month - relativedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)
    return first_day_last_month, last_day_last_month


def parse_date(date_str):
    """Parses a date string to a datetime. Does not return an error."""
    try:
        return parse(date_str)
    except ParserError:
        logger.info("parse_date_invalid_date", date_str=date_str)
        return None


def write_content_to_tempfile(content):
    """Accepts string or bytes content, writes it to a temporary file, and returns the
    file object."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        if isinstance(content, bytes):
            temp_file = open(temp_file.name, "wb")
        temp_file.write(content)
        temp_file.close()
    return temp_file


def get_version_from_url(request):
    return request.GET.get("version")


def get_version_from_cookie(request):
    return request.COOKIES.get(SELECTED_BOOST_VERSION_COOKIE_NAME)


def get_view_from_url(request):
    return request.resolver_match.kwargs.get("library_view_str")


def get_view_from_cookie(request):
    return request.COOKIES.get(SELECTED_LIBRARY_VIEW_COOKIE_NAME)


def set_view_in_cookie(response, view):
    allowed_views = {"grid", "list", "categorized"}
    if view not in allowed_views:
        return
    response.set_cookie(SELECTED_LIBRARY_VIEW_COOKIE_NAME, view)


def get_prioritized_version(request):
    """
    Version Priorities:
    1. URL parameter
    2. Cookie
    3. Default to latest version
    """
    url_version = get_version_from_url(request)
    cookie_version = get_version_from_cookie(request)
    default_version = LATEST_RELEASE_URL_PATH_STR
    return url_version or cookie_version or default_version


def get_prioritized_library_view(request):
    """
    View Priorities:
    1. URL parameter
    2. Cookie
    3. Default to grid view
    """
    url_view = get_view_from_url(request)
    cookie_view = get_view_from_cookie(request)
    return url_view or cookie_view or DEFAULT_LIBRARIES_LANDING_VIEW


def get_category(request):
    return request.GET.get("category", "")


def determine_selected_boost_version(request_value, request):
    # use the versions in the request if they are available otherwise fall back to DB
    version_slug = request_value or get_version_from_cookie(request)
    version_args = {}
    if version_slug in (DEVELOP_RELEASE_URL_PATH_STR, MASTER_RELEASE_URL_PATH_STR):
        version_args = {f"allow_{version_slug}": True}

    valid_versions = getattr(request, "extra_context", {}).get(
        "versions", Version.objects.get_dropdown_versions(**version_args)
    )
    if version_slug in [v.slug for v in valid_versions] + [LATEST_RELEASE_URL_PATH_STR]:
        return version_slug
    logger.warning(f"Invalid version slug in cookies: {version_slug}")
    return None


def modernize_boost_slug(version_slug: str) -> str:
    """Takes an old style slug e.g. 1_81_0 and gives a modern slug e.g. boost-1-81-0"""
    split_old_slug = version_slug.split("_")
    rejoined_slug = ("-").join(split_old_slug)
    return f"boost-{rejoined_slug}"


def set_selected_boost_version(version_slug: str, response) -> None:
    """Update the selected version in the cookies."""
    versions_kwargs = {}
    if version_slug in [MASTER_RELEASE_URL_PATH_STR, DEVELOP_RELEASE_URL_PATH_STR]:
        versions_kwargs[f"allow_{version_slug}"] = True

    valid_versions = Version.objects.get_dropdown_versions(**versions_kwargs)
    if version_slug in [v.slug for v in valid_versions]:
        response.set_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME, version_slug)
    elif version_slug == LATEST_RELEASE_URL_PATH_STR:
        response.delete_cookie(SELECTED_BOOST_VERSION_COOKIE_NAME)
    else:
        logger.warning(f"Attempted to set invalid version slug: {version_slug}")


def library_doc_latest_transform(url):
    p = re.compile(r"^(/doc/libs/)[0-9_]+(/\S+)$")
    if p.match(url):
        url = p.sub(rf"\1{LATEST_RELEASE_URL_PATH_STR}\2", url)
    return url


def generate_canonical_library_uri(uri):
    matches = re.match(
        r"https?://(?P<domainpath>[^/]+(?:/[^/]+){2}/?)(?P<version>[^/]+)(?P<docpath>/[\S]+)",
        uri,
    )
    if matches.group("version") == LATEST_RELEASE_URL_PATH_STR:
        return uri
    return f"https://{matches.group('domainpath')}{LATEST_RELEASE_URL_PATH_STR}{matches.group('docpath')}"


def get_documentation_url(library_version, latest):
    url = library_version.documentation_url
    if url and latest:
        url = library_doc_latest_transform(url)
    return url


def get_documentation_url_redirect(library_version, latest):
    """Get the documentation URL for the current library."""

    def find_documentation_url(library_version):
        # If we know the library-version docs are missing, return the version docs
        if library_version.missing_docs:
            return library_version.version.documentation_url
        # If we have the library-version docs and they are valid, return those
        elif library_version.documentation_url:
            return library_version.documentation_url
        # If we wind up here, return the version docs
        else:
            return library_version.version.documentation_url

    # Get the URL for the version.
    url = find_documentation_url(library_version)
    # Remove the "boost_" prefix from the URL.
    url = url.replace("boost_", "")
    if latest:
        url = library_doc_latest_transform(url)

    return url


def batched(iterable, n, *, strict=False):
    # batched('ABCDEFG', 3) → ABC DEF G
    # In python 3.12, this function can be deleted in favor of itertools.batched
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        if strict and len(batch) != n:
            raise ValueError("batched(): incomplete batch")
        yield batch


def conditional_batched(iterable, n: int, condition: callable, *, strict=False):
    """
    Batch items that pass a condition together, return items that fail individually.

    Args:
        iterable: Items to process
        n: Batch size for items that pass the condition
        condition: Function that returns True if item should be batched
        strict: If True, raise error for incomplete final batch

    Yields:
        Tuples of batched items or single-item tuples for items that fail condition
    """
    if n < 1:
        raise ValueError("n must be at least one")

    batch = []

    for item in iterable:
        if condition(item):
            # item passes condition - add to batch
            batch.append(item)
            if len(batch) == n:
                # batch is full - yield it and start new batch
                yield tuple(batch)
                batch = []
        else:
            # item fails condition - yield any pending batch first, then item alone
            if batch:
                yield tuple(batch)
                batch = []
            yield (item,)

    # handle any remaining items in batch
    if strict and batch and len(batch) != n:
        raise ValueError("conditional_batched(): incomplete batch")
    if batch:
        yield tuple(batch)


def legacy_path_transform(content_path):
    if content_path and content_path.startswith(LEGACY_LATEST_RELEASE_URL_PATH_STR):
        content_path = re.sub(r"([a-zA-Z0-9\.]+)/(\S+)", r"latest/\2", content_path)
    return content_path


def parse_boostdep_artifact(content: str):
    """Parse and return a generator which yields libraries and their dependencies.

    - `content` is a string of the artifact content given by the dependency_report
        GH action.
    - Iterate through the file and yield a tuple of
        (library_version: LibraryVersion, dependencies: list[Library])
    - Some library keys in the output do not match the names in our database exactly,
        so transform names when necessary
    - The boost database may not contain every library version found in this file,
        if we find a definition of dependencies for a library version we are not
        tracking, ignore it and continue to the next line.
    - example content can be found in
        libraries/tests/fixtures.py -> github_action_boostdep_output_artifact

    """
    from libraries.models import Library, LibraryVersion

    libraries = {x.key: x for x in Library.objects.all()}
    # these libraries do not exist in the DB, ignore them.
    ignore_libraries = ["disjoint_sets", "tr1"]

    def fix_library_key(name):
        """Transforms library key in boostdep report to match our library keys"""
        if name == "logic":
            return "logic/tribool"
        return name.replace("~", "/")

    def parse_line(line: str):
        parts = line.split("->")
        if len(parts) == 2:
            library_key, dependencies_string = [x.strip() for x in parts]
            library_key = fix_library_key(library_key)
            dependency_names = [fix_library_key(x) for x in dependencies_string.split()]
            dependencies = [
                libraries[x] for x in dependency_names if x not in ignore_libraries
            ]
        else:
            library_key = fix_library_key(parts[0].strip())
            dependencies = []
        return library_key, dependencies

    library_versions = {}
    version_name = ""
    skipped_library_versions = 0
    for line in content.splitlines():
        # each section is headed with 'Dependencies for version boost-x.x.0'
        if line.startswith("Dependencies for version"):
            version_name = line.split()[-1]
            library_versions = {
                x.library.key: x
                for x in LibraryVersion.objects.filter(
                    version__name=version_name
                ).select_related("library")
            }
        else:
            library_key, dependencies = parse_line(line)
            if library_key in ignore_libraries:
                continue
            library_version = library_versions.get(library_key, None)
            if not library_version:
                skipped_library_versions += 1
                logger.info(
                    f"LibraryVersion with {library_key=} {version_name=} not found."
                )
                continue
            yield library_version, dependencies
    if skipped_library_versions:
        logger.info(
            "Some library versions were skipped during artifact parsing.",
            skipped_library_versions=skipped_library_versions,
        )


def address_already_proven_by(email, user) -> bool:
    """True when `user` has already proven control of `email` somewhere other
    than the commit-email claim flow, so claiming it needs no second round-trip.

    Three routes count, each of which already required acting on a link sent to
    the address itself:
      - it is the account's own address. Email verification is mandatory
        (ACCOUNT_EMAIL_VERIFICATION) and this only ever runs for a signed-in
        user, so reaching here at all means it was confirmed at signup.
      - an allauth EmailAddress marked verified - covers secondary addresses
        added to the account later, and re-confirms the primary one.
      - an active mailing-list subscription. Mailman only flips a row to ACTIVE
        after the recipient opens a signed confirmation link (see
        mailing_list/views.py); `pending` rows prove nothing and are excluded.

    Every comparison is case-insensitive: CommitAuthorEmail rows are stored
    exactly as git reported them, so mixed case is common there, while
    User.email is lowercased on save. An exact match would miss those.
    """
    # local imports: this module is imported during app loading
    from allauth.account.models import EmailAddress
    from mailing_list.models import SubscriptionStatus, UserMailingListSubscription

    email = (email or "").strip().lower()
    if not email:
        return False

    if (user.email or "").lower() == email:
        return True

    if EmailAddress.objects.filter(
        user=user, verified=True, email__iexact=email
    ).exists():
        return True

    return UserMailingListSubscription.objects.filter(
        user=user, status=SubscriptionStatus.ACTIVE, email__iexact=email
    ).exists()


def patch_commit_authors(users):
    """Patch CommitAuthor data onto a list of User objects.

    For each user, looks up their email in CommitAuthorEmail and attaches
    the matching CommitAuthor (with avatar_url, github_profile_url,
    display_name) as user.commitauthor. Falls back to a SimpleNamespace
    stub when no match is found.
    """
    from libraries.models import CommitAuthorEmail

    commit_authors = {
        author_email.email: author_email
        for author_email in CommitAuthorEmail.objects.annotate(
            email_lower=Lower("email")
        )
        .filter(email_lower__in=[u.email.lower() for u in users])
        .select_related("author")
    }
    for user in users:
        if author_email := commit_authors.get(user.email.lower(), None):
            user.commitauthor = author_email.author
        else:
            user.commitauthor = SimpleNamespace(
                github_profile_url="",
                avatar_url="",
                display_name=f"{user.display_name}",
            )
    return users


GITHUB_PROFILE_PREFIX = "https://github.com/"


def prefer_boost_profile_links(author_dicts):
    """Repoint a contributor's GitHub link at their Boost profile, if they have one.

    `CommitAuthor.to_v3_profile_dict()` can only consult `CommitAuthor.user`,
    which `update_commit_authors_users` fills in by matching a commit email to
    an account email exactly. A contributor who commits under a different
    address than they signed up with keeps a GitHub link despite having a
    profile. GitHub username is a second signal for the same identity, and both
    records usually carry it.

    The badge travels with the link, for the same reason: a contributor we are
    confident enough to point at a Boost profile is that member, so showing
    their profile but not their badge would split one identity across two cards
    (issue #2708).

    Resolves the whole list in one query. Mutates each dict in place and returns
    the same list.
    """
    from badges.display import active_badges_prefetch
    from users.models import User

    by_username = {}
    for author in author_dicts:
        url = author.get("profile_url") or ""
        if not url.startswith(GITHUB_PROFILE_PREFIX):
            continue
        username = url.rstrip("/").rsplit("/", 1)[-1].lower()
        if username:
            by_username.setdefault(username, []).append(author)

    if not by_username:
        return author_dicts

    # Only claimed accounts are worth repointing to: an unclaimed stub's
    # profile_url is its GitHub page anyway, which is already the link here.
    users = (
        User.objects.filter(is_active=True, claimed=True)
        .annotate(github_username_lower=Lower("github_username"))
        .filter(github_username_lower__in=by_username)
        .prefetch_related("profile_routing_keys", active_badges_prefetch())
    )
    for user in users:
        profile_url = user.profile_url
        if not profile_url:
            continue
        for author in by_username.get(user.github_username.lower(), []):
            author["profile_url"] = profile_url
            author["badge"] = user.badge
            author["badge_label"] = user.badge_label

    return author_dicts


def apply_collective_author_overrides(author_dicts):
    """Normalize collective authors (e.g. "Various Authors") in V3 profile dicts.

    A collective author renders as a single labelled group icon with no profile
    link or role. Mutates each dict in place and returns the same list.
    """
    from users.templatetags.avatar_tags import (
        collective_author_label,
        is_collective_author,
    )

    for author in author_dicts:
        if is_collective_author(author["name"]):
            author["name"] = collective_author_label(author["name"])
            author["profile_url"] = None
            author["role"] = None
    return author_dicts


def designed_for_html(items):
    """Render website.adoc [#designed-for] items as an HTML fragment.

    Each item becomes an <h3> heading + optional <p> description, for display
    in the shared markdown card. Dynamic text is escaped via format_html.
    """
    if not items:
        return ""
    parts = []
    for item in items:
        parts.append(format_html("<h3>{}</h3>", item.get("heading") or ""))
        if item.get("description"):
            parts.append(format_html("<p>{}</p>", item["description"]))
    return mark_safe("".join(parts))


def benchmark_sets(benchmarks):
    """Map website.adoc [#benchmarks] charts to _stats_benchmarks `sets`.

    Each chart becomes a set; bar widths (`width_pct`, 0-100) are normalized to
    that chart's largest value. The chart's unit is folded into the set title
    since the component has no separate unit/caption slot.
    """
    sets = []
    for chart in benchmarks or []:
        rows_data = chart.get("data") or []
        max_value = max((row.get("value") or 0 for row in rows_data), default=0)
        rows = []
        for row in rows_data:
            value = row.get("value") or 0
            width_pct = round(value / max_value * 100, 2) if max_value else 0
            rows.append(
                {"label": row.get("label"), "value": value, "width_pct": width_pct}
            )
        title = chart.get("title") or ""
        if chart.get("unit"):
            title = f"{title} ({chart['unit']})"
        sets.append({"title": title, "rows": rows})
    return sets


def build_library_intro_context(
    library_version, *, max_authors=None, include_contributors=False
):
    """Build template context for the library intro card.

    Returns a dict with keys: library_name, description, authors, cta_url.

    Authors first, then maintainers (excluding duplicates). When
    `include_contributors` is True, top git contributors fill the remaining
    slots; set it False to show authors and maintainers only. `max_authors`
    caps the number shown; pass None to show all.
    """
    from badges.display import active_badges_prefetch
    from libraries.models import CommitAuthor

    library = library_version.library

    # Authors first, then maintainers (same order as ContributorMixin). Each row
    # links a profile, which reads the user's routing keys, so those are
    # prefetched rather than fetched per card.
    authors = list(library_version.authors.prefetch_related("profile_routing_keys"))
    author_ids = {a.id for a in authors}
    maintainers = list(
        library_version.maintainers.exclude(id__in=author_ids).prefetch_related(
            "profile_routing_keys"
        )
    )

    combined = (authors + maintainers)[:max_authors]
    if combined:
        prefetch_related_objects(combined, active_badges_prefetch())
    roles = {}
    for user in combined:
        roles[user.id] = "Author" if user.id in author_ids else "Maintainer"

    patch_commit_authors(combined)

    # Optionally fill remaining slots with top git contributors.
    top_contributors = []
    remaining = max_authors - len(combined) if max_authors is not None else 0
    if include_contributors and remaining > 0:
        exclude_commit_author_ids = [
            user.commitauthor.id
            for user in combined
            if getattr(user.commitauthor, "id", None)
        ]
        top_contributors = (
            CommitAuthor.humans.filter(commit__library_version=library_version)
            .exclude(id__in=exclude_commit_author_ids)
            .annotate(count=Count("commit"))
            # A claimed contributor links to their Boost profile and shows
            # their badge, which reads the user, their routing keys and their
            # badge rows. Badges are asked for through the path because `user`
            # is select_related - see `badges.display.active_badges_prefetch`.
            .select_related("user")
            .prefetch_related(
                "user__profile_routing_keys",
                active_badges_prefetch("user__badges"),
            )
            .order_by("-count")[:remaining]
        )

    author_dicts = []
    for user in combined:
        profile = user.to_v3_profile_dict(role=roles[user.id])
        profile["bio"] = user.tagline
        author_dicts.append(profile)
    author_dicts.extend(
        contributor.to_v3_profile_dict("Contributor")
        for contributor in top_contributors
    )

    apply_collective_author_overrides(prefer_boost_profile_links(author_dicts))

    return {
        "library_name": library.display_name,
        "description": library_version.description or library.description or "",
        "authors": author_dicts,
        "cta_url": reverse(
            "library-detail",
            kwargs={
                "version_slug": LATEST_RELEASE_URL_PATH_STR,
                "library_slug": library.slug,
            },
        ),
    }


def update_base_tag(html: str, base_uri: str):
    """
    Replace the base tag href with the new base_uri
    """
    pattern = r'<base\s+href="[^"]*">'
    replacement = f'<base href="{base_uri}">'
    return re.sub(pattern, replacement, html)


def generate_release_report_filename(version_slug: str, published_format: bool = False):
    filename_data = ["release-report", version_slug]
    if not published_format:
        filename_data.append(datetime.now(timezone.utc).isoformat())
    filename = f"{'-'.join(filename_data)}.pdf"
    return filename


def get_s3_client() -> BaseClient:
    return boto3.client(
        "s3",
        aws_access_key_id=settings.STATIC_CONTENT_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.STATIC_CONTENT_AWS_SECRET_ACCESS_KEY,
        region_name=settings.STATIC_CONTENT_REGION,
    )


def group_libraries_by_tier(
    libraries: QuerySet["LibraryVersion"] | QuerySet["Library"],
):
    """Group libraries or library versions into flagship, core, and other lists based on tier.

    Returns (flagship, core, other) tuple.
    """

    from libraries.models import Tier, Library, LibraryVersion

    flagship = []
    core = []
    other = []
    for lib in libraries:
        if isinstance(lib, Library):
            tier = lib.tier
        elif isinstance(lib, LibraryVersion):
            tier = lib.library.tier
        else:
            raise TypeError("Invalid Queryset passed")

        if tier == Tier.FLAGSHIP:
            flagship.append(lib)
        elif tier == Tier.CORE:
            core.append(lib)
        else:
            other.append(lib)

    return flagship, core, other


def library_filter_options() -> list[tuple[str, str]]:
    """(slug, label) pairs for the library filter dropdowns.

    Only libraries carried by a live post are offered. The dropdown exists to
    narrow the feed, and a library no post is tagged with can only narrow it to
    nothing, so listing every library buries the handful that lead somewhere.

    Posts reach a library through a `ContentTag` whose slug mirrors the library
    slug rather than through a relation, so the tagged slugs come back as a
    subquery instead of a join.

    Labelled with display_name so the dropdown matches the wording used in
    feed headers ("Boost.Beast" rather than "Beast").
    """

    from libraries.models import Library
    from pages.mixins import TaggedContent

    tagged_slugs = TaggedContent.objects.filter(content_object__live=True).values(
        "tag__slug"
    )

    return [
        (library.slug, library.display_name)
        for library in Library.objects.exclude(slug="")
        .exclude(slug__isnull=True)
        .filter(slug__in=tagged_slugs)
        .order_by("name")
    ]
