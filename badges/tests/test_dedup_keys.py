"""Tests for the source key that identifies an automatic grant.

A grant used to be identified by the row it pointed at, which the commit importer
churns and which exists once per library version covering a commit. These cover
what keying on the source's own name for the evidence buys instead.
"""

import pytest
from django.core.management import call_command
from model_bakery import baker

from badges import sources
from badges.models import Achievement, SourceType, UserAchievement
from badges.tests.fixtures import grant_from_source

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def _commit(user, sha, library_version=None):
    """One commit attributed to ``user``, optionally under a given version."""
    author = baker.make("libraries.CommitAuthor", user=user)
    extra = {} if library_version is None else {"library_version": library_version}
    return baker.make("libraries.Commit", author=author, sha=sha, **extra)


def _grants(user):
    return UserAchievement.objects.filter(
        user=user, achievement__slug="code-commits", source_type=SourceType.AUTOMATIC
    )


def test_one_sha_under_two_versions_grants_once(plain_user):
    """The release ranges store a commit once per version they cover.

    Both rows are the same piece of work, so the member is credited once.
    """
    library = baker.make("libraries.Library", key="mp11")
    for name in ("1.88.0", "master"):
        version = baker.make("libraries.LibraryVersion", library=library)
        _commit(plain_user, "cafe1234", library_version=version)

    call_command("backfill_achievements", "--source", "code-commits")

    assert _grants(plain_user).count() == 1


def test_reimporting_with_new_ids_changes_nothing(plain_user):
    """The importer's clean mode deletes every commit row and re-inserts it.

    The shas survive that, so the grants do too: nothing to add, nothing stale.
    """
    from libraries.models import Commit

    commit = _commit(plain_user, "cafe1234")
    call_command("backfill_achievements", "--source", "code-commits")
    grant = _grants(plain_user).get()

    author = commit.author
    library_version = commit.library_version
    Commit.objects.all().delete()
    replacement = baker.make(
        "libraries.Commit",
        author=author,
        library_version=library_version,
        sha="cafe1234",
    )
    assert replacement.pk != commit.pk

    call_command("reconcile_achievements", "--source", "code-commits")

    assert _grants(plain_user).get().pk == grant.pk


def test_unkeyed_duplicates_collapse_to_one(plain_user):
    """One sha stored twice was credited twice before the key existed.

    Neither old row can be matched, so both go and one keyed grant replaces them.
    """
    library = baker.make("libraries.Library", key="mp11")
    achievement = Achievement.objects.get(slug="code-commits")
    for _ in range(2):
        commit = _commit(
            plain_user,
            "cafe1234",
            library_version=baker.make("libraries.LibraryVersion", library=library),
        )
        grant_from_source(plain_user, achievement, commit)
    assert _grants(plain_user).count() == 2

    call_command("reconcile_achievements", "--source", "code-commits")

    assert [g.dedup_info for g in _grants(plain_user)] == ["cafe1234"]


def test_a_grant_with_no_key_is_replaced(plain_user):
    """Grants written before a source was keyed are replaced, not adopted.

    Which is what makes emptying the tables and backfilling the way to convert an
    environment, rather than a healing pass nobody will run twice.
    """
    achievement = Achievement.objects.get(slug="code-commits")
    commit = _commit(plain_user, "cafe1234")
    grant_from_source(plain_user, achievement, commit)

    call_command("reconcile_achievements", "--source", "code-commits")

    grant = _grants(plain_user).get()
    assert grant.dedup_info == "cafe1234"


def test_a_source_that_names_nothing_fails_loudly(plain_user):
    """A missing key would be added every sweep and removed every reconcile."""
    from unittest.mock import patch

    commit = _commit(plain_user, "cafe1234")

    def unkeyed():
        yield plain_user, commit, None

    with patch.dict(sources.BACKFILL_ITERATORS, {"code-commits": unkeyed}):
        with pytest.raises(ValueError, match="no dedup key"):
            call_command("backfill_achievements", "--source", "code-commits")


def test_source_key_formats(plain_user):
    """The key format is a contract: changing one orphans every stored grant."""
    library = baker.make("libraries.Library", key="mp11")
    version = baker.make(
        "libraries.LibraryVersion",
        library=library,
        version=baker.make("versions.Version", name="boost-1.88.0"),
    )
    version.authors.add(plain_user)
    _commit(plain_user, "cafe1234")
    review = baker.make(
        "versions.Review",
        submission="Boost.MP11",
        submitter_raw="Peter Dimov",
        review_dates="April 1-10, 2017",
    )
    review.submitters.add(baker.make("libraries.CommitAuthor", user=plain_user))

    assert [key for _, _, key in sources._iter_library_versioning()] == [
        "mp11@boost-1.88.0"
    ]
    assert [key for _, _, key in sources._iter_code_commits()] == ["cafe1234"]
    assert [key for _, _, key in sources._iter_library_review()] == [
        "boostmp11|peterdimov|april1102017"
    ]
