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

Sub-libraries (``math/quaternion``, ``functional/hash``, and the rest of
``SUB_LIBRARIES``) are excluded from every library-shaped source. They are
subdivisions of a parent library's documentation rather than libraries of their
own, so only the parent counts, and authorship of a sub-library alone earns
nothing here. Recognising that work would take a badge of its own.
"""

from badges.enums import AchievementSlug
from libraries.constants import SUB_LIBRARIES


def _iter_library_authoring():
    """Yield (user, library) for every authorship of a parent library."""
    from libraries.models import Library

    libraries = Library.objects.exclude(key__in=SUB_LIBRARIES).prefetch_related(
        "authors"
    )
    for library in libraries.iterator(chunk_size=500):
        for user in library.authors.all():
            yield user, library


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
    AchievementSlug.CODE_COMMITS: _iter_code_commits,
}

# Derived, so the CLI choices can never drift from the wired iterators.
AUTOMATIC_SLUGS = [slug.value for slug in BACKFILL_ITERATORS]
