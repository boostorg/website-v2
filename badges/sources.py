"""Automatic achievement sources (backfill only).

Maps each automatic achievement type to the existing model it is derived from,
as backfill iterators that yield ``(user, source_object)`` pairs over all
historical data. There are deliberately **no live signals**: achievement data is
processed in batch by ``backfill_achievements`` (run after the weekly
``release_tasks``), and ad hoc by manual admin grants. Developers accept that
automatic achievements are not real-time.

One source is wired here; the rest arrive one per pull request. Two of the
catalogue's eight types will never be wired, there being no clean per-record,
per-user source for them in this codebase:
* ``documentation`` - no model tracks doc contributions per user.
* ``mailing-list`` (Regular) - posts live in the external Hyperkitty DB and
  ``EmailData`` only stores aggregate counts, not per-post rows.
Both can still be granted manually until a source is available.
"""

from badges.enums import AchievementSlug


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
    AchievementSlug.CODE_COMMITS: _iter_code_commits,
}

# Derived, so the CLI choices can never drift from the wired iterators.
AUTOMATIC_SLUGS = [slug.value for slug in BACKFILL_ITERATORS]
