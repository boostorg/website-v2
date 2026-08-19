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
    double-counting - see ``unique_automatic_user_achievement_dedup``.
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
    library = baker.make("libraries.Library", key="mp11")
    library.authors.add(plain_user)
    assert list(sources._iter_library_authoring()) == [(plain_user, library, "mp11")]


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
    library = baker.make("libraries.Library", key="mp11")
    for _ in range(3):
        version = baker.make("libraries.LibraryVersion", library=library)
        version.maintainers.add(plain_user)

    assert list(sources._iter_library_maintenance()) == [(plain_user, library, "mp11")]


def test_iter_library_maintenance_skips_sub_libraries(plain_user):
    """Maintaining a sub-library is maintaining part of its parent's docs."""
    sub = baker.make("libraries.Library", key="math/quaternion")
    version = baker.make("libraries.LibraryVersion", library=sub)
    version.maintainers.add(plain_user)

    assert list(sources._iter_library_maintenance()) == []


def test_iter_library_versioning_skips_sub_libraries(plain_user):
    """A sub-library's releases belong to its parent, and count for nothing here."""
    sub = baker.make("libraries.Library", key="math/quaternion")
    version = baker.make("libraries.LibraryVersion", library=sub)
    version.authors.add(plain_user)

    assert list(sources._iter_library_versioning()) == []


def test_iter_code_commits_skips_unlinked(plain_user):
    """Only commits whose author has a linked user are yielded."""
    linked = baker.make("libraries.CommitAuthor", user=plain_user)
    unlinked = baker.make("libraries.CommitAuthor", user=None)
    baker.make("libraries.Commit", author=linked)
    baker.make("libraries.Commit", author=unlinked)

    pairs = list(sources._iter_code_commits())
    assert [u for u, _, _ in pairs] == [plain_user]


def test_iter_library_review_skips_unlinked(plain_user):
    """Review submitters without a linked user are skipped."""
    review = baker.make("versions.Review")
    review.submitters.add(
        baker.make("libraries.CommitAuthor", user=plain_user),
        baker.make("libraries.CommitAuthor", user=None),
    )
    pairs = list(sources._iter_library_review())
    assert [u for u, _, _ in pairs] == [plain_user]
