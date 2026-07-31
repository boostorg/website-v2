"""Celery tasks for the versions app.

Covers Boost release ingestion (versions, library-versions, downloads, release
notes) and the AI-generated "What's New" summary pipeline. The AI tasks
(``generate_whats_new`` / ``save_whats_new`` / ``dispatch_whats_new``) live at
the bottom of this module.
"""

import re
from textwrap import dedent

from django.db import transaction
import requests
import structlog

from celery import group, chain

from config.celery import app
from config.settings import OPENROUTER_API_KEY, OPENROUTER_URL, WHATS_NEW_MODEL
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from django.utils.html import strip_tags
from fastcore.xtras import obj2dict
from openai import OpenAI, OpenAIError

from core.githubhelper import GithubAPIClient, GithubDataParser
from libraries.constants import SKIP_LIBRARY_VERSIONS
from libraries.github import LibraryUpdater
from libraries.models import Library, LibraryVersion
from libraries.website_adoc import fetch_website_adoc_fields
from libraries.tasks import get_and_store_library_version_documentation_urls_for_version
from libraries.utils import version_within_range
from versions.exceptions import BoostImportedDataException
from versions.models import Version
from versions.releases import (
    store_release_notes_for_in_progress,
    store_release_notes_for_version,
)

logger = structlog.get_logger()


def _upsert_version_from_tag(
    tag,
    base_url,
    beta=False,
    full_release=True,
):
    name = tag["name"]

    # Save the response we got from Github, if present
    if tag:
        data = obj2dict(tag)
    else:
        data = {}

    version, created = Version.objects.with_partials().update_or_create(
        name=name,
        defaults={
            "github_url": f"{base_url}{name}",
            "beta": beta,
            "full_release": full_release,
            "data": data,
        },
    )
    return version, created


def _import_missing_versions(
    delete_versions=False, new_versions_only=False, token=None
):
    """
    Imports missing Boost releases from github and updates the local database.

    Retrieves the boost release tags from the main github repo, excluding beta releases and release candidates.

    It then creates or updates a Version instance for each tag, then returns those tags for additional task processing.

    Args:
        delete_versions (bool): If True, deletes all existing Version instances before
            importing.
        new_versions_only (bool): If True, only imports versions that do not already
            exist in the database.
        token (str): Github API token, if you need to use something other than the
            setting.
    """

    if delete_versions:
        Version.objects.with_partials().all().delete()
        logger.info("import_versions_deleted_all_versions")

    # delete any versions that were only partially imported so they are re-imported
    Version.objects.with_partials().filter(fully_imported=False).delete()

    # Get all Boost tags from Github
    client = GithubAPIClient(token=token)
    tags = client.get_tags()

    r_tags = []
    base_url = "https://github.com/boostorg/boost/releases/tag/"
    for tag in tags:
        name = tag["name"]

        if skip_tag(name, new_versions_only):
            continue

        logger.info(f"import_versions importing version {name=}")
        _upsert_version_from_tag(tag, base_url)
        r_tags.append(tag)

    return r_tags


@app.task
def import_versions(
    delete_versions=False, new_versions_only=False, token=None, purge_after=True
):
    """Imports Boost release information from Github and updates the local database.

    The function retrieves Boost tags from the main Github repo, excluding beta releases
    and release candidates.

    It then creates or updates a Version instance in the local database for each tag.

    Args:
        delete_versions (bool): If True, deletes all existing Version instances before
            importing.
        new_versions_only (bool): If True, only imports versions that do not already
            exist in the database.
        token (str): Github API token, if you need to use something other than the
            setting.
        purge_after (bool): If True, call purge_fastly_release_cache after the version
            imports are finished.
    """

    tags = _import_missing_versions(
        delete_versions=delete_versions,
        new_versions_only=new_versions_only,
        token=token,
    )

    import_version_task_group = []
    for tag in tags:
        name = tag["name"]
        import_version_task_group.append(
            import_version.s(name, tag=tag, token=token, perform_upsert=False)
        )

    if import_version_task_group:
        task_group = group(*import_version_task_group)
        logger.info(f"{purge_after=}")
        if purge_after:
            logger.info("linking fastly purge")
            task_group.link(purge_fastly_release_cache.s())
        task_group.link(mark_fully_completed.s(full_release_only=True))
        task_group()
    import_release_notes.delay()


@app.task
def import_release_notes(new_versions_only=True):
    """Imports release notes from the existing rendered
    release notes in the repository."""
    # Include both the most recent full release and the most recent beta (if
    # one exists). `most_recent()` filters out betas, so without this a
    # freshly-imported beta would be silently skipped when running with
    # ``new_versions_only=True`` (e.g. ``./manage.py import_release_notes``).
    qs = Version.objects.with_partials()
    versions = [v for v in (qs.most_recent(), qs.most_recent_beta()) if v is not None]
    if not new_versions_only:
        versions = (
            Version.objects.exclude(name__in=["master", "develop"])
            .active()
            .order_by("name")
        )

    logger.info(f"import_release_notes {[v.name for v in versions]}")
    for version in versions:
        logger.info(f"retrieving release notes for {version.name=} {version.pk=}")
        store_release_notes_task(version.pk)
    store_release_notes_in_progress_task.delay()


@app.task
def store_release_notes_task(version_pk):
    """Stores the release notes for a single version."""
    try:
        Version.objects.with_partials().get(pk=version_pk)
    except Version.DoesNotExist:
        logger.error(f"store_release_notes_task_version_does_not_exist {version_pk=}")
        return
    store_release_notes_for_version(version_pk)


@app.task
def store_release_notes_in_progress_task():
    """Fetches and store in-progress release notes in RenderedContent."""
    store_release_notes_for_in_progress()


@app.task
def import_version(
    name,
    tag=None,
    token=None,
    beta=False,
    full_release=True,
    base_url="https://github.com/boostorg/boost/releases/tag/",
    get_release_date=True,
    perform_upsert=True,
):
    """Imports a single Boost version from Github and updates the local
    database. Also runs import_release_downloads and import_library_versions
    for the version.

    base_url: Most base_url values will be for tags, but we do save some
    Version objects that are branches and not tags (mainly master and develop).

    perform_upsert: in most contexts, this should save the version, but in the import
    versions workflow we don't want to double save the versions so set this flag to false
    """
    # Save the response we got from Github, if present
    if perform_upsert:
        version, created = _upsert_version_from_tag(tag, base_url, beta, full_release)
    else:
        # The version was already upserted by the caller (import_versions flow).
        version = Version.objects.with_partials().get(name=name)
        created = False

    logger.info(f"import_versions_version {created=} {name=} {version.pk} ")

    # Get the release date for the version
    if get_release_date and not version.release_date:
        commit_sha = tag["commit"]["sha"]
        get_release_date_for_version(version.pk, commit_sha, token=token)

    # Load release downloads
    import_release_downloads(version.pk)

    # Load library-versions
    import_library_versions(version.name, token=token)


@app.task
def import_development_versions():
    """Imports the `master` and `develop` branches as Versions"""
    base_url = "https://github.com/boostorg/boost/tree/"

    import_version_tasks = []
    import_library_version_tasks = []
    for branch in settings.BOOST_BRANCHES:
        import_version_tasks.append(
            import_version.s(
                branch,
                branch,
                beta=False,
                full_release=False,
                get_release_date=False,
                base_url=base_url,
            )
        )

        import_library_version_tasks.append(
            import_library_versions.s(branch, version_type="branch")
        )

    task_chain = chain(
        group(*import_version_tasks),
        group(*import_library_version_tasks),
        mark_fully_completed.s(),
    )
    task_chain()


@app.task
def import_most_recent_beta_release(token=None, delete_old=False):
    """Imports the most recent beta release from Github and updates the local database.
    Also runs import_release_downloads and import_library_versions for the version.

    Args:
        token (str): Github API token, if you need to use something other than the
            setting.
        delete_old (bool): If True, deletes all existing beta Version instances
            before importing.
    """
    most_recent_version = Version.objects.most_recent()
    # Get all Boost tags from Github
    client = GithubAPIClient(token=token)
    tags = client.get_tags()

    with transaction.atomic():
        if delete_old:
            Version.objects.filter(beta=True).delete()
            logger.info("import_most_recent_beta_release_deleted_all_versions")

        for tag in tags:
            name = tag["name"]
            # Get the most recent beta version that is at least as recent as
            # the most recent stable version
            if "beta" in name and name >= most_recent_version.name:
                logger.info(f"calling import_version with {name=} {tag=}")
                import_version(name, tag, token=token, beta=True, full_release=False)
                logger.info(f"completed import_version with {name=} {tag=}")
                mark_fully_completed(beta_only=True)
                # new_versions_only='False' otherwise will only be full releases
                import_release_notes(new_versions_only=False)
                return


LIBRARY_KEY_EXCEPTIONS = {
    "utility/string_ref": [
        {
            "new_key": "utility/string_view",
            "new_name": "String View",
            "min_version": "boost-1.78.0",  # Apply change for versions >= boost-1.78.0
        }
    ],
}


@app.task
def import_all_library_versions(token=None, version_type="tag"):
    """Run import_library_versions for all versions"""
    for version in Version.objects.active():
        import_library_versions.delay(
            version.name, token=token, version_type=version_type
        )


def skip_library_version(library_slug, version_slug):
    """Returns True if the given library-version should be skipped."""
    skipped_records = SKIP_LIBRARY_VERSIONS.get(library_slug, [])
    if not skipped_records:
        return False

    for exception in skipped_records:
        if version_within_range(
            version_slug,
            min_version=exception.get("min_version"),
            max_version=exception.get("max_version"),
        ):
            return True

    return False


@app.task
def gc_removed_submodules(library_keys: list[str], branch: str) -> None:
    """Remove libraries that are not in the library_keys from the
    library_versions list for the current version."""
    library_version_keys = LibraryVersion.objects.filter(
        version__name=branch
    ).values_list("library__key", flat=True)
    for k in library_version_keys:
        if k not in library_keys:
            LibraryVersion.objects.filter(version__name=branch, library__key=k).delete()
            logger.info(f"{k=} library_version link to {branch=} garbage collected.")


@app.task
def import_library_versions(version_name, token=None, version_type="tag"):
    """For a specific version, imports all LibraryVersions using GitHub data"""
    # todo: this needs to be refactored and tests added
    try:
        version = Version.objects.with_partials().get(name=version_name)
    except Version.DoesNotExist:
        logger.info(
            "import_library_versions_version_not_found", version_name=version_name
        )

    client = GithubAPIClient(token=token)
    updater = LibraryUpdater(client=client)
    parser = GithubDataParser()

    # Get the gitmodules file for the version, which contains library data
    # The master and develop branches are not tags, so we retrieve their data
    # from the heads/ namespace instead of tags/
    ref_s = f"tags/{version_name}" if version_type == "tag" else f"heads/{version_name}"
    try:
        ref = client.get_ref(ref=ref_s)
    except ValueError:
        logger.info(f"import_library_versions_invalid_ref {ref_s=}")
        return

    raw_gitmodules = client.get_gitmodules(ref=ref)
    if not raw_gitmodules:
        logger.info(
            "import_library_versions_invalid_gitmodules", version_name=version_name
        )
        return

    gitmodules = parser.parse_gitmodules(raw_gitmodules.decode("utf-8"))

    # For each gitmodule, gets its libraries.json file and save the libraries
    # to the version
    library_keys = []
    for gitmodule in gitmodules:
        library_name = gitmodule["module"]
        if library_name in updater.skip_modules:
            continue

        if skip_library_version(library_name, version_name):
            continue

        try:
            libraries_json = client.get_libraries_json(
                repo_slug=library_name, tag=version_name
            )
        except (
            requests.exceptions.JSONDecodeError,
            requests.exceptions.HTTPError,
            Exception,
        ):
            # Can happen with older releases
            library_version = save_library_version_by_library_key(
                library_name, version, gitmodule
            )

            logger.info(
                f"import_library_versions_by_library {version_name=} "
                f"{library_name=} {library_version=} "
            )

            continue

        if not libraries_json:
            # Can happen with older releases -- we try to catch all exceptions
            # so this is just in case
            library_version = save_library_version_by_library_key(
                library_name, version, gitmodule
            )

            if not library_version:
                logger.info(
                    f"import_library_versions_skipped_library "
                    f"{version_name=} {library_name=}"
                )
            continue

        libraries = (
            libraries_json if isinstance(libraries_json, list) else [libraries_json]
        )
        parsed_libraries = [parser.parse_libraries_json(lib) for lib in libraries]
        for lib_data in parsed_libraries:
            if lib_data["key"] in updater.skip_libraries:
                continue
            # tracking this 'key' because the gitmodule name doesn't directly match,
            # e.g. interval in gitmodule, numericinterval in db/here
            library_keys.append(lib_data["key"])

            # Handle exceptions based on version and library key
            exceptions = LIBRARY_KEY_EXCEPTIONS.get(lib_data["key"], [])
            for exception in exceptions:
                if version_within_range(
                    version_name,
                    min_version=exception.get("min_version"),
                    max_version=exception.get("max_version"),
                ):
                    lib_data["key"] = exception["new_key"]
                    lib_data["name"] = exception.get("name", lib_data["name"])
                    break  # Stop checking exceptions if a match is found

            library, _ = Library.objects.get_or_create(
                key=lib_data["key"],
                defaults={
                    "name": lib_data.get("name"),
                    "description": lib_data.get("description"),
                    "data": lib_data,
                },
            )
            library_version, _ = LibraryVersion.objects.update_or_create(
                version=version,
                library=library,
                defaults={
                    "data": lib_data,
                    "cpp_standard_minimum": lib_data.get("cxxstd"),
                    "cpp_standard_maximum": lib_data.get("cxxstd_max"),
                    "cpp20_module_support": lib_data.get("cpp20_module_support"),
                    "description": lib_data.get("description"),
                    **fetch_website_adoc_fields(client, library_name, version_name),
                },
            )
            if not library.github_url:
                github_data = client.get_repo(repo_slug=library_name)
                library.github_url = github_data.get("html_url", "")
                library.save()

    # For any libraries no longer in gitmodules we want to remove master and develop
    #  references from the library_versions list.
    if version_name in ["master", "develop"]:
        logger.info("Triggering removed submodules garbage collection")
        gc_removed_submodules.delay(library_keys, version_name)

    # Retrieve and store the docs url for each library-version in this release
    get_and_store_library_version_documentation_urls_for_version(version.pk)

    # Load maintainers for library-versions
    call_command("update_maintainers", "--release", version.name)


@app.task
def import_reviews_task():
    """Imports Boost formal-review results and milestones from boost.org."""
    call_command("import_reviews")
    # Reviews are the only source of the library-review achievement, and this is
    # the only thing that writes them, so it owns keeping the grants in step.
    call_command("backfill_achievements", "--source", "library-review")


@app.task
def import_release_downloads(version_pk):
    logger.info(f"import_release_downloads w/ {version_pk=}")
    version = Version.objects.with_partials().get(pk=version_pk)
    version_num = version.name.replace("boost-", "")
    if version_num < "1.63.0":
        # Downloads are in Sourceforge for older versions, and that has
        # not been implemented yet
        logger.info(f"import_release_downloads_skipped {version.name=}")
        return
    logger.info(f"import_release_downloads starting {version.name=}")
    call_command("import_archives_release_data", release=version_num)
    logger.info(f"import_release_downloads_complete {version.name=}")


@app.task
def get_release_date_for_version(version_pk, commit_sha, token=None):
    """
    Gets and stores the release date for a Boost version using the given commit SHA.

    :param version_pk: The primary key of the version to get the release date for.
    :param commit_sha: The SHA of the commit to get the release date for.
    """
    try:
        version = Version.objects.with_partials().get(pk=version_pk)
    except Version.DoesNotExist:
        logger.error(f"get_release_date_for_version_no_version_found {version_pk=}")
        return

    if not token:
        token = settings.GITHUB_TOKEN

    parser = GithubDataParser()
    client = GithubAPIClient(token=token)

    try:
        commit = client.get_commit_by_sha(commit_sha=commit_sha)
    except Exception as e:
        logger.error(
            "get_release_date_for_version_failed",
            version_pk=version_pk,
            commit_sha=commit_sha,
            e=str(e),
        )
        return

    commit_data = parser.parse_commit(commit)
    release_date = commit_data.get("release_date")

    if release_date:
        version.release_date = release_date
        version.save()
        logger.info("get_release_date_for_version_success", version_pk=version_pk)
    else:
        logger.error("get_release_date_for_version_error", version_pk=version_pk)


@app.task
def purge_fastly_release_cache():
    logger.info("Purging Fastly cache for release pages.")
    if not settings.FASTLY_API_TOKEN or settings.FASTLY_API_TOKEN == "empty":
        logger.warning("FASTLY_API_TOKEN not found. Not purging cache.")
        return

    headers = {
        "Fastly-Key": settings.FASTLY_API_TOKEN,
        "Fastly-Soft-Purge": "1",
        "Accept": "application/json",
    }
    fastly_services = [settings.FASTLY_SERVICE, settings.FASTLY_SERVICE2]
    logger.info(f"{fastly_services=}")
    for service in fastly_services:
        logger.info(f"Purging Fastly cache for release pages against {service=}")
        if not service or service == "empty":
            logger.warning(f"Fastly {service=} not found. Not purging cache.")
            continue
        url = f"https://api.fastly.com/service/{service}/purge/release"
        logger.info(f"Purging Fastly cache for {service=} at {url=}")
        requests.post(url, headers=headers)
        logger.info(f"Sent fastly purge request for {service=}.")


@app.task
def mark_fully_completed(beta_only=False, full_release_only=False):
    """Marks all versions as fully imported"""
    qs = Version.objects.with_partials().filter(fully_imported=False)
    if full_release_only:
        logger.info("Marking active as fully imported")
        qs = qs.filter(full_release=True)
    elif beta_only:
        logger.info("Marking beta as fully imported")
        qs = qs.filter(beta=True)
    versions = [v.name for v in qs.order_by("name").all()]
    qs.update(fully_imported=True)
    logger.info(f"Marked {versions=} as fully imported.")


# Helper functions


def save_library_version_by_library_key(library_key, version, gitmodule={}):
    """Saves a LibraryVersion instance by library key and version."""
    try:
        library = Library.objects.get(key=library_key)
        library_version, _ = LibraryVersion.objects.update_or_create(
            version=version, library=library, defaults={"data": gitmodule}
        )
        return library_version
    except Library.DoesNotExist:
        return


def skip_tag(name, new=False):
    """Returns True if the given tag should be skipped."""
    # Skip beta releases, release candidates, and pre-1.0 versions
    EXCLUSIONS = ["beta", "-rc", "-bgl"]

    # If we are only importing new versions, and we already have this one, skip
    if new and Version.objects.with_partials().filter(name=name).exists():
        return True

    # If this version falls in our exclusion list, skip it
    if any(pattern in name.lower() for pattern in EXCLUSIONS):
        return True

    # If this version is too old, skip it
    version_num = name.replace("boost-", "")
    if version_num < settings.MINIMUM_BOOST_VERSION:
        return True

    return False


# ---------------------------------------------------------------------------
# AI tasks: "What's New" release-note summarization
# ---------------------------------------------------------------------------


# Guardrail to keep the LLM call comfortably under the model's context window
# (gpt-oss-120b is ~131K tokens; ~100K chars leaves headroom for the system
# prompt + output). Inputs above this are truncated. The model name itself
# is configured via the WHATS_NEW_MODEL setting (env-driven; see settings.py).
WHATS_NEW_MAX_INPUT_CHARS = 100_000

WHATS_NEW_SYSTEM_PROMPT = dedent("""
    You are a technical writer for the Boost C++ library ecosystem. Your job is
    to read a Boost release note and generate a "What's New" summary for the
    Boost website.

    Rules:

    Return the output as a Markdown unordered list: every line must begin
    with "- " and there must be no other lines
    Return a maximum of 5 bullets, each with a bold category label,
    and a single sentence of no more than 20 words
    Do not use emoji anywhere in the output
    Wrap every code identifier (variable, function, type, macro, or template
    name) you mention from the release note in Markdown inline code with
    single backticks — apply it to each identifier on each occurrence, in
    any bullet, with no per-section or per-bullet cap; do not backtick
    library names or general phrases
    Do not name or highlight specific libraries — speak to the ecosystem as a
    whole. The Dependencies bullet may name up to two libraries when one or
    two libraries clearly drive the story; otherwise stay ecosystem-level.
    Only include a bullet if there is relevant content in the release note to
    support it
    Omit any category that has no relevant content — do not pad or fabricate
    Follow this rubric and order where content exists:

    New libraries — how many new libraries were added and what they broadly cover
    Performance improvements — notable speed, memory, or compile time gains across the release
    Dependencies — notable changes to library dependencies, removals, or newly introduced requirements. Leverage precomputed dependency stats when available.
    Security & reliability — bug fixes, security updates, and stability improvements
    Developer experience — constexpr support, tooling improvements, or better error handling

    Inputs:
    - "release note" — plain-text release note (always provided)
    - "Dependency stats" — optional precomputed counts of added/removed
      dependencies and the number of libraries affected; when present, use
      these numbers verbatim in the Dependencies bullet

    Output: Return only the Markdown unordered list. No preamble, no
    explanation, no additional commentary.
    """).strip()


def _dependency_stats_block(version: Version) -> str | None:
    """Return a short text block describing dep-add/remove counts, or None.

    Skipped when imported library data is missing or every diff is empty so
    the prompt does not surface a "0 added, 0 removed" bullet.
    """
    try:
        stats = version.get_dependency_stats()
    except BoostImportedDataException:
        return None

    if stats["added"] == 0 and stats["removed"] == 0:
        return None

    return dedent(f"""
        Dependency stats (precomputed from imported data):
        - Added: {stats["added"]} dependency additions across {stats["increased_dep_lib_count"]} libraries
        - Removed: {stats["removed"]} dependency removals across {stats["decreased_dep_lib_count"]} libraries
        """).strip()


def _release_note_text(rendered_content) -> str:
    """Extract the plain-text release note used as the LLM input.

    AsciiDoc originals are passed through directly (LLMs handle the markup);
    HTML originals are stripped of tags. Whitespace is collapsed either way.
    """
    if (
        rendered_content.content_type == "text/asciidoc"
        and rendered_content.content_original
    ):
        raw = rendered_content.content_original
    else:
        raw = strip_tags(rendered_content.content_html or "")
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", raw)).strip()


@app.task(bind=True, max_retries=3, autoretry_for=(OpenAIError,))
def generate_whats_new(self, version_pk: int) -> str | None:
    """Generate a draft What's New summary for the given Version's release notes."""
    from core.models import RenderedContent

    try:
        version = Version.objects.with_partials().get(pk=version_pk)
    except Version.DoesNotExist:
        logger.error("generate_whats_new_version_not_found", version_pk=version_pk)
        return None

    rendered_content = RenderedContent.objects.filter(
        cache_key=version.release_notes_cache_key
    ).first()
    if not rendered_content or not (
        rendered_content.content_html or rendered_content.content_original
    ):
        logger.info(
            "generate_whats_new_no_release_notes",
            version_pk=version_pk,
            cache_key=version.release_notes_cache_key,
        )
        return None

    release_note_text = _release_note_text(rendered_content)
    if len(release_note_text) > WHATS_NEW_MAX_INPUT_CHARS:
        logger.warning(
            "generate_whats_new_truncating_input",
            version_pk=version_pk,
            original_chars=len(release_note_text),
            max_chars=WHATS_NEW_MAX_INPUT_CHARS,
        )
        release_note_text = release_note_text[:WHATS_NEW_MAX_INPUT_CHARS]

    dep_stats_block = _dependency_stats_block(version)
    if dep_stats_block:
        user_content = f"release note:\n\n{release_note_text}" f"\n\n{dep_stats_block}"
    else:
        user_content = release_note_text

    logger.info(
        "generate_whats_new_dispatching",
        version_pk=version_pk,
        version_name=version.name,
        input_chars=len(release_note_text),
        dep_stats_included=bool(dep_stats_block),
    )

    messages = [
        {"role": "system", "content": WHATS_NEW_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    client = OpenAI(base_url=OPENROUTER_URL, api_key=OPENROUTER_API_KEY)
    try:
        response = client.chat.completions.create(
            model=WHATS_NEW_MODEL, messages=messages
        )
        content = response.choices[0].message.content
    except OpenAIError:
        # Let autoretry_for=(OpenAIError,) on the task handle retries.
        logger.exception("generate_whats_new_openai_error", version_pk=version_pk)
        raise
    except (AttributeError, IndexError) as e:
        logger.error("generate_whats_new_response_error", error=str(e))
        return None

    logger.info(
        "generate_whats_new_received",
        version_pk=version_pk,
        output_chars=len(content) if content else 0,
    )
    return content


@app.task
def save_whats_new(markdown_text: str | None, version_pk: int):
    """Persist a generated summary on the Version.

    Resets ``whats_new_approved`` to False so regenerated content goes back
    through admin moderation before it becomes visible on the public site.
    """
    if not markdown_text:
        logger.info("save_whats_new_empty_skip", version_pk=version_pk)
        return

    Version.objects.filter(pk=version_pk).update(
        whats_new=markdown_text,
        whats_new_generated_at=timezone.now(),
        whats_new_approved=False,
    )
    logger.info("save_whats_new_saved", version_pk=version_pk)


def dispatch_whats_new(version_pk: int) -> None:
    """Queue the generate→save chain for a single Version."""
    generate_whats_new.apply_async(
        args=[version_pk],
        link=save_whats_new.s(version_pk),
    )
