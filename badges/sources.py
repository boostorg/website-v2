"""Automatic achievement sources.

Maps an automatic achievement type to the model it derives from, as an iterator
yielding ``(user, source_object)`` pairs over all historical data. There are
deliberately **no live signals**: this data is processed in batch by
``backfill_achievements`` and ad hoc by manual admin grants, so automatic
achievements are not real-time.

Three of the catalogue's eight types have no automatic source, there being no clean
per-record, per-user source for them here:

* ``documentation`` - no model tracks documentation contributions per user.
* ``mailing-list`` (Regular) - posts live in the external Hyperkitty database,
  which stores aggregate counts rather than per-post rows.
* ``publisher`` - news post storage is being reworked, so an iterator written
  against the current models would not survive it.

All three can still be granted by hand in the admin.
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


BACKFILL_ITERATORS = {
    AchievementSlug.LIBRARY_AUTHORING: _iter_library_authoring,
    AchievementSlug.LIBRARY_MAINTENANCE: _iter_library_maintenance,
    AchievementSlug.CODE_COMMITS: _iter_code_commits,
}

# Derived, so the CLI choices can never drift from the wired iterators.
AUTOMATIC_SLUGS = [slug.value for slug in BACKFILL_ITERATORS]
