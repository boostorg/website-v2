"""Tests for the backfill iterators and the uniqueness they rely on.

There are no live signals; ingestion happens via the backfill command (see
test_commands.py) and manual grants. These tests cover the iterator logic
(filtering) and the constraint that makes re-running a backfill a no-op.
"""

import pytest
from model_bakery import baker

from badges import sources
from badges.models import Achievement, UserAchievement
from badges.tests.fixtures import grant_from_source

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def test_catalogue_seeded():
    """The catalogue helper populates the achievement registry."""
    assert Achievement.objects.filter(slug="library-authoring").exists()
    assert Achievement.objects.filter(slug="code-commits").exists()


def test_an_automatic_grant_is_idempotent(plain_user):
    """Granting the same (user, achievement, source) twice creates one row.

    Which is what lets the weekly backfill re-walk every source without
    double-counting - see ``unique_automatic_user_achievement_source``.
    """
    achievement = Achievement.objects.get(slug="library-authoring")
    library = baker.make("libraries.Library")

    _, created_first = grant_from_source(plain_user, achievement, library)
    _, created_second = grant_from_source(plain_user, achievement, library)

    assert created_first is True
    assert created_second is False
    assert (
        UserAchievement.objects.filter(user=plain_user, achievement=achievement).count()
        == 1
    )


def test_iter_library_authoring(plain_user):
    """The authoring iterator yields each (author, library) pair."""
    library = baker.make("libraries.Library")
    library.authors.add(plain_user)
    pairs = list(sources._iter_library_authoring())
    assert (plain_user, library) in pairs


def test_iter_library_authoring_skips_sub_libraries(plain_user):
    """A sub-library is its parent's, so authoring one alone counts for nothing.

    ``math/quaternion`` and the rest of ``SUB_LIBRARIES`` are subdivisions of a
    parent library's documentation, and the badge counts parent libraries.
    """
    sub = baker.make("libraries.Library", key="math/quaternion")
    sub.authors.add(plain_user)

    assert list(sources._iter_library_authoring()) == []


def test_iter_library_maintenance_dedupes_versions(plain_user):
    """Maintaining many versions of one library yields a single pair."""
    library = baker.make("libraries.Library")
    for _ in range(3):
        version = baker.make("libraries.LibraryVersion", library=library)
        version.maintainers.add(plain_user)

    pairs = list(sources._iter_library_maintenance())
    assert pairs == [(plain_user, library)]


def test_iter_code_commits_skips_unlinked(plain_user):
    """Only commits whose author has a linked user are yielded."""
    linked = baker.make("libraries.CommitAuthor", user=plain_user)
    unlinked = baker.make("libraries.CommitAuthor", user=None)
    baker.make("libraries.Commit", author=linked)
    baker.make("libraries.Commit", author=unlinked)

    pairs = list(sources._iter_code_commits())
    assert [u for u, _ in pairs] == [plain_user]
