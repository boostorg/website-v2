"""Automatic achievement sources (backfill only).

Maps each automatic achievement type to the existing model it is derived from,
as backfill iterators that yield ``(user, source_object)`` pairs over all
historical data. There are deliberately **no live signals**: achievement data is
processed in batch by ``backfill_achievements`` (run after the weekly
``release_tasks``), and ad hoc by manual admin grants. Developers accept that
automatic achievements are not real-time.

Not wired here (no clean per-record, per-user source in this codebase):
* ``documentation`` - no model tracks doc contributions per user.
* ``mailing-list`` (Regular) - posts live in the external Hyperkitty DB and
  ``EmailData`` only stores aggregate counts, not per-post rows.
Both can still be granted manually until a source is available.
"""

from badges.enums import AchievementSlug


def _iter_library_authoring():
    """Yield (user, library) for every library authorship."""
    from libraries.models import Library

    for library in Library.objects.prefetch_related("authors").iterator(chunk_size=500):
        for user in library.authors.all():
            yield user, library


def _iter_library_maintenance():
    """Yield (user, library) once per library the user maintains.

    Maintainers are recorded per ``LibraryVersion``, but the badge counts
    *libraries* maintained (thresholds 1/2/5/...), so pairs are deduplicated
    across versions and the ``Library`` is the achievement source.
    """
    from libraries.models import LibraryVersion

    seen = set()
    versions = LibraryVersion.objects.select_related("library").prefetch_related(
        "maintainers"
    )
    for version in versions.iterator(chunk_size=500):
        for user in version.maintainers.all():
            key = (user.pk, version.library_id)
            if key not in seen:
                seen.add(key)
                yield user, version.library


def _iter_library_versioning():
    """Yield (user, library_version) for every per-version authorship."""
    from libraries.models import LibraryVersion

    for version in LibraryVersion.objects.prefetch_related("authors").iterator(
        chunk_size=500
    ):
        for user in version.authors.all():
            yield user, version


def _iter_code_commits():
    """Yield (user, commit) for every attributed commit."""
    from libraries.models import Commit

    commits = (
        Commit.objects.filter(author__user__isnull=False)
        .select_related("author__user")
        .iterator(chunk_size=1000)
    )
    for commit in commits:
        yield commit.author.user, commit


def _iter_library_review():
    """Yield (user, review) for every review submission with a linked user."""
    from versions.models import Review

    for review in Review.objects.prefetch_related("submitters__user").iterator(
        chunk_size=500
    ):
        for commit_author in review.submitters.all():
            if commit_author.user_id:
                yield commit_author.user, review


def _iter_publisher():
    """Yield (user, entry) for every live published news entry.

    Reuses ``Entry.objects.published()`` rather than restating its predicate, and
    excludes soft-deleted entries the same way the news views do - a post the
    author removed must not keep counting toward their badge.
    """
    from news.models import Entry

    entries = (
        Entry.objects.published()
        .filter(deleted_at__isnull=True)
        .select_related("author")
    )
    for entry in entries.iterator(chunk_size=1000):
        yield entry.author, entry


BACKFILL_ITERATORS = {
    AchievementSlug.LIBRARY_AUTHORING: _iter_library_authoring,
    AchievementSlug.LIBRARY_MAINTENANCE: _iter_library_maintenance,
    AchievementSlug.LIBRARY_VERSIONING: _iter_library_versioning,
    AchievementSlug.CODE_COMMITS: _iter_code_commits,
    AchievementSlug.LIBRARY_REVIEW: _iter_library_review,
    AchievementSlug.PUBLISHER: _iter_publisher,
}

# Derived, so the CLI choices can never drift from the wired iterators.
AUTOMATIC_SLUGS = [slug.value for slug in BACKFILL_ITERATORS]
