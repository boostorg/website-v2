"""Tests for the source key that identifies an automatic grant.

A grant used to be identified by the row it pointed at, which the commit importer
churns and which exists once per library version covering a commit. These cover
what keying on the source's own name for the evidence buys instead.
"""

import pytest
from django.core.management import call_command
from model_bakery import baker

from badges import sources
from badges.models import Achievement, SourceType, UserAchievement, UserBadge
from badges.services import recalculate_badges, sync_source
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


def test_a_doc_commit_earns_the_documenter_badge(plain_user):
    """End to end: a doc commit grants and awards, a code-only commit does not."""
    from badges.models import UserBadge

    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author, sha="d0c1", docs_files_changed=3)
    baker.make("libraries.Commit", author=author, sha="c0de", docs_files_changed=0)

    call_command("backfill_achievements", "--source", "documentation")

    grants = UserAchievement.objects.filter(
        user=plain_user, achievement__slug="documentation"
    )
    assert [g.dedup_info for g in grants] == ["d0c1"]
    assert UserBadge.objects.filter(
        user=plain_user, badge__label="documenter", revoked_at__isnull=True
    ).exists()


def test_backfilling_documentation_twice_grants_once(plain_user):
    """The second sweep of the weekly pipeline must not double anyone's count."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author, sha="d0c1", docs_files_changed=3)

    call_command("backfill_achievements", "--source", "documentation")
    call_command("backfill_achievements", "--source", "documentation")

    assert (
        UserAchievement.objects.filter(
            user=plain_user, achievement__slug="documentation"
        ).count()
        == 1
    )


def test_documentation_is_selectable_as_a_source():
    """The CLI choices are derived from what is wired, so this cannot drift."""
    assert "documentation" in sources.AUTOMATIC_SLUGS


@pytest.fixture
def every_source(plain_user):
    """One piece of evidence for each of the six wired sources, all one member.

    A round-trip test is only worth anything if the source actually yielded
    something, so the tests assert on the backfill rather than trusting this.
    """
    library = baker.make("libraries.Library", key="mp11")
    library.authors.add(plain_user)
    version = baker.make(
        "libraries.LibraryVersion",
        library=library,
        version=baker.make("versions.Version", name="boost-1.88.0"),
    )
    version.authors.add(plain_user)
    version.maintainers.add(plain_user)
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make(
        "libraries.Commit",
        author=author,
        library_version=version,
        sha="cafe1234",
        docs_files_changed=2,
        is_merge=False,
    )
    review = baker.make(
        "versions.Review",
        submission="Boost.MP11",
        submitter_raw="Peter Dimov",
        review_dates="April 1-10, 2017",
    )
    review.submitters.add(author)


@pytest.mark.parametrize("slug", sources.AUTOMATIC_SLUGS)
def test_a_second_walk_recognises_everything_the_first_wrote(slug, every_source):
    """Walk a source twice over unchanged data and nothing may move.

    What this catches is a key the walk cannot reproduce - one built from a clock,
    a counter, or an unstable ordering rather than from the evidence itself. The
    count would climb on every sweep and the reconcile behind it would delete what
    it failed to recognise, neither of them raising anything.

    What it does *not* catch is a key that is merely fragile, a row id being the
    obvious one: nothing re-creates rows inside a single test, so a row id looks
    perfectly stable here. That property belongs to the two sources whose rows the
    importers actually delete and insert again - see
    ``test_reimporting_with_new_ids_changes_nothing`` for commits and
    ``test_reimporting_a_review_keeps_its_grant`` for reviews.

    Parametrised over the wired sources, so a source added later is covered by
    having been added rather than by somebody remembering.
    """
    achievement = Achievement.objects.get(slug=slug)

    backfill = sync_source(slug, achievement, remove=False)
    assert backfill.added > 0, f"the fixture fed '{slug}' nothing to grant"

    again = sync_source(slug, achievement, dry_run=True)

    assert (again.added, again.removed) == (0, 0)


def test_replacing_an_unkeyed_grant_never_moves_the_badge(plain_user):
    """Converting an environment must not disturb the badges on the way through.

    The walk inserts before it deletes, so the count never dips below the
    threshold and the tier is neither revoked nor re-earned. If that order ever
    changes, every member converted would have their award date reset to the day
    of the deploy.
    """
    achievement = Achievement.objects.get(slug="code-commits")
    commit = _commit(plain_user, "cafe1234")
    grant_from_source(plain_user, achievement, commit)
    recalculate_badges(plain_user.pk, achievement.pk)
    badges = set(UserBadge.objects.values_list("pk", "awarded_at", "revoked_at"))
    assert badges, "nothing was awarded, so the assertion below proves nothing"

    call_command("reconcile_achievements", "--source", "code-commits")

    assert _grants(plain_user).get().dedup_info == "cafe1234"
    assert (
        set(UserBadge.objects.values_list("pk", "awarded_at", "revoked_at")) == badges
    )


def test_one_sha_feeds_two_achievements_independently(plain_user):
    """Code Commits and Documenter both name a commit by its sha.

    The key is unique per achievement, not globally, so one doc-touching commit
    earns both. If those two are ever merged into one achievement, this is the
    test that says so.
    """
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author, sha="d0c1", docs_files_changed=3)

    call_command("backfill_achievements", "--source", "code-commits")
    call_command("backfill_achievements", "--source", "documentation")

    grants = UserAchievement.objects.filter(user=plain_user, dedup_info="d0c1")
    assert set(grants.values_list("achievement__slug", flat=True)) == {
        "code-commits",
        "documentation",
    }


def test_a_scoped_reconcile_leaves_other_members_alone(plain_user, super_user):
    """The per-member admin button reconciles one member, not the table.

    The scope is applied to the stored rows as well as inside the walk, and only
    the first of those stops another member's grants being read as stale - every
    key outside the scope is simply absent from the comparison.
    """
    achievement = Achievement.objects.get(slug="code-commits")
    _commit(super_user, "beef0001")
    call_command("backfill_achievements", "--source", "code-commits")
    untouched = set(
        UserAchievement.objects.filter(user=super_user).values_list("pk", "dedup_info")
    )
    assert untouched, "the other member holds nothing, so this proves nothing"

    orphan = _commit(plain_user, "dead0002")
    grant_from_source(plain_user, achievement, orphan, dedup_info="dead0002")
    orphan.delete()

    sync_source("code-commits", achievement, user_ids=[plain_user.pk])

    assert not _grants(plain_user).exists()
    assert (
        set(
            UserAchievement.objects.filter(user=super_user).values_list(
                "pk", "dedup_info"
            )
        )
        == untouched
    )


def test_reimporting_a_review_keeps_its_grant(plain_user):
    """A review's fingerprint survives the row being deleted and imported again.

    Reviews are the only source besides commits whose rows are genuinely
    re-created - ``import_reviews --clean`` empties the table first. This covers
    the key rather than the command: the command also discards its own grants
    before deleting, which is a separate question from whether the key holds.
    """
    from versions.models import Review

    author = baker.make("libraries.CommitAuthor", user=plain_user)
    fields = {
        "submission": "Boost.MP11",
        "submitter_raw": "Peter Dimov",
        "review_dates": "April 1-10, 2017",
    }
    baker.make("versions.Review", **fields).submitters.add(author)
    call_command("backfill_achievements", "--source", "library-review")
    grant = UserAchievement.objects.get(achievement__slug="library-review")

    Review.objects.all().delete()
    replacement = baker.make("versions.Review", **fields)
    replacement.submitters.add(author)
    assert replacement.pk != grant.source_object_id

    call_command("reconcile_achievements", "--source", "library-review")

    assert (
        UserAchievement.objects.get(achievement__slug="library-review").pk == grant.pk
    )
