"""Tests for the backfill, recalculate and reconcile management commands."""

import re

import pytest
from django.core.management import call_command, load_command_class
from django.core.management.base import CommandError
from django.utils import timezone
from model_bakery import baker

from badges.enums import AchievementSlug
from badges.models import (
    Achievement,
    AchievementSyncRun,
    RevocationSource,
    SourceType,
    UserAchievement,
    UserBadge,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def test_backfill_grants_achievement_and_badge(plain_user):
    """Backfill turns existing source data into achievements and badges."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)  # no live signal grants it
    assert UserAchievement.objects.count() == 0

    call_command("backfill_achievements", "--source", "code-commits")

    assert (
        UserAchievement.objects.filter(
            user=plain_user, achievement__slug="code-commits"
        ).count()
        == 1
    )
    assert UserBadge.objects.filter(
        user=plain_user, badge__achievement__slug="code-commits"
    ).exists()  # bronze threshold is 1


def test_backfill_is_idempotent(plain_user):
    """Running backfill twice does not create duplicate rows."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)

    call_command("backfill_achievements", "--source", "code-commits")
    call_command("backfill_achievements", "--source", "code-commits")

    assert (
        UserAchievement.objects.filter(
            user=plain_user, achievement__slug="code-commits"
        ).count()
        == 1
    )


def test_backfill_skips_recalculation_without_new_rows(plain_user):
    """A re-run with no new source data does not recalculate badges."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    UserBadge.objects.all().delete()  # would be restored by a recalculation

    call_command("backfill_achievements", "--source", "code-commits")

    assert not UserBadge.objects.exists()


def test_backfill_fails_loudly_on_an_explicit_unseeded_source(plain_user):
    """A named source with no Achievement row is a deploy bug, not a skip."""
    Achievement.objects.filter(slug=AchievementSlug.CODE_COMMITS).delete()

    with pytest.raises(CommandError, match="code-commits"):
        call_command("backfill_achievements", "--source", "code-commits")


def test_backfill_fails_when_no_source_is_seeded(plain_user):
    """Nothing to back fill at all is still worth a non-zero exit."""
    Achievement.objects.all().delete()

    with pytest.raises(CommandError, match="No wired source"):
        call_command("backfill_achievements")


@pytest.mark.parametrize(
    "command_name", ["backfill_achievements", "reconcile_achievements"]
)
@pytest.mark.parametrize("batch_size", ["0", "-1"])
def test_sync_commands_reject_non_positive_batch_sizes(command_name, batch_size):
    """Invalid batch sizes fail in argument parsing, before either command runs."""
    command = load_command_class("badges", command_name)
    parser = command.create_parser("manage.py", command_name)

    with pytest.raises(CommandError, match="must be a positive integer"):
        parser.parse_args(["--batch-size", batch_size])


def _grant(user, slug):
    """One valid manual grant, which is all a threshold of 1 needs.

    Built directly rather than through a source iterator: recalculation reads
    ``UserAchievement`` rows and does not care where they came from.
    """
    return UserAchievement.objects.create(
        user=user,
        achievement=Achievement.objects.get(slug=slug),
        source_type=SourceType.MANUAL,
    )


def test_recalculate_rebuilds_badges(plain_user):
    """The recalculate command restores badge rows from achievement counts."""
    _grant(plain_user, AchievementSlug.LIBRARY_AUTHORING)
    UserBadge.objects.all().delete()  # wipe derived state

    call_command("recalculate_badges")

    assert UserBadge.objects.filter(
        user=plain_user,
        badge__achievement__slug=AchievementSlug.LIBRARY_AUTHORING,
    ).exists()


def test_recalculate_revokes_when_every_achievement_is_invalid(plain_user):
    """A pair with no valid achievements left must still be recalculated.

    ``update()`` skips the post_save signal, mimicking data fixed outside the
    admin - exactly the case this command exists to repair.
    """
    _grant(plain_user, AchievementSlug.LIBRARY_AUTHORING)
    UserAchievement.objects.filter(user=plain_user).update(is_valid=False)
    assert UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()

    call_command("recalculate_badges")

    assert not UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()


def test_recalculate_revokes_badges_whose_achievements_are_gone(plain_user):
    """A badge orphaned by a signal-free delete is revoked, not left standing.

    Bulk deletes, data migrations and raw SQL never fire ``post_delete``, so the
    full recalculation is the only thing that can clean up after them.
    """
    _grant(plain_user, AchievementSlug.LIBRARY_REVIEW)
    badge = UserBadge.objects.get(user=plain_user)
    assert badge.revoked_at is None

    # Delete the rows the way a bulk path would: no post_delete receivers run.
    UserAchievement.objects.filter(user=plain_user)._raw_delete(using="default")

    call_command("recalculate_badges")

    badge.refresh_from_db()
    assert badge.revoked_at is not None


def test_reconcile_deletes_a_grant_the_source_no_longer_yields(
    plain_user, commit_by_someone_else, stale_commit_grant
):
    """The case the command exists for: attribution moved, the grant did not."""
    call_command("reconcile_achievements", "--source", "code-commits")

    assert not UserAchievement.objects.filter(user=plain_user).exists()
    revoked = UserBadge.objects.get(
        user=plain_user, badge__achievement__slug="code-commits", tier__rank="bronze"
    )
    assert revoked.revoked_at is not None
    assert revoked.revocation_source == "cascade"


def test_reconcile_removes_a_grant_whose_source_row_is_gone(
    plain_user, commit_by_someone_else, stale_commit_grant
):
    """A deleted source row leaves the same dangling grant, and is cleaned up too.

    The generic foreign key carries no referential integrity, so nothing else
    notices. ``discard_source_achievements`` covers the callers that delete rows
    deliberately; this covers everything that did not.
    """
    stale_commit_grant.delete()

    call_command("reconcile_achievements", "--source", "code-commits")

    assert not UserAchievement.objects.filter(user=plain_user).exists()


def test_reconcile_leaves_manual_grants_alone(
    plain_user, commit_by_someone_else, stale_commit_grant
):
    """A manual grant has no source to disagree with, so it must survive."""
    achievement = Achievement.objects.get(slug=AchievementSlug.CODE_COMMITS)
    manual = UserAchievement.objects.create(
        user=plain_user, achievement=achievement, source_type=SourceType.MANUAL
    )

    call_command("reconcile_achievements", "--source", "code-commits")

    assert UserAchievement.objects.filter(pk=manual.pk).exists()
    assert not UserAchievement.objects.filter(
        user=plain_user, source_type=SourceType.AUTOMATIC
    ).exists()
    # The manual grant is still worth one achievement, which is still bronze.
    assert UserBadge.objects.filter(
        user=plain_user, badge__achievement__slug="code-commits", revoked_at=None
    ).exists()


def test_reconcile_leaves_an_attributed_grant_alone(plain_user):
    """A source that still yields the member changes nothing, however often."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    badge = UserBadge.objects.get(user=plain_user, tier__rank="bronze")

    call_command("reconcile_achievements", "--source", "code-commits")
    call_command("reconcile_achievements", "--source", "code-commits")

    assert UserAchievement.objects.filter(user=plain_user).count() == 1
    badge.refresh_from_db()
    assert badge.revoked_at is None


def test_reconcile_dry_run_writes_nothing(
    plain_user, commit_by_someone_else, stale_commit_grant, capsys
):
    """A dry run reports the stale grant and leaves it, and the badge, in place."""
    call_command("reconcile_achievements", "--source", "code-commits", "--dry-run")

    output = capsys.readouterr().out
    assert "Dry run" in output
    assert "would remove 1 grant(s)" in output
    assert UserAchievement.objects.filter(user=plain_user).count() == 1
    assert UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()


def test_reconcile_scopes_to_the_named_member(
    plain_user, commit_by_someone_else, stale_commit_grant
):
    """``--user`` must not clean up a member it was not pointed at."""
    other = baker.make("users.User", email="other-stale@example.com")
    other_author = baker.make("libraries.CommitAuthor", user=other)
    baker.make("libraries.Commit", author=other_author)
    call_command("backfill_achievements", "--source", "code-commits")
    other_author.user = None
    other_author.save()

    call_command("reconcile_achievements", "--user", plain_user.email)

    assert not UserAchievement.objects.filter(user=plain_user).exists()
    assert UserAchievement.objects.filter(user=other).exists()


def test_reconcile_scoped_to_a_member_does_not_add_for_anyone_else(
    plain_user, stale_commit_grant
):
    """``--user`` bounds the additive half too, not only the deletions.

    A member outside the scope is absent from the stored keys, which on the
    additive side looks exactly like a grant that needs creating - so the walk has
    to know about the scope as well.
    """
    other = baker.make("users.User", email="other-missing@example.com")
    baker.make(
        "libraries.Commit", author=baker.make("libraries.CommitAuthor", user=other)
    )

    call_command(
        "reconcile_achievements", "--source", "code-commits", "--user", plain_user.email
    )

    assert not UserAchievement.objects.filter(user=plain_user).exists()
    assert not UserAchievement.objects.filter(user=other).exists()


def test_reconcile_accepts_a_member_by_primary_key(
    plain_user, commit_by_someone_else, stale_commit_grant
):
    """An id is as good as an email, because an admin URL only carries the id."""
    call_command("reconcile_achievements", "--user", str(plain_user.pk))

    assert not UserAchievement.objects.filter(user=plain_user).exists()


def test_reconcile_rejects_an_unknown_member(plain_user):
    """A typo in ``--user`` must not silently widen the run to everybody."""
    with pytest.raises(CommandError, match=re.escape("nobody@example.com")):
        call_command("reconcile_achievements", "--user", "nobody@example.com")


def test_reconcile_refuses_a_source_that_yields_nothing(
    plain_user, stale_commit_grant, capsys
):
    """An empty source is a broken source until proven otherwise.

    Without this, one failed import would revoke every badge the source feeds.
    """
    call_command("reconcile_achievements", "--source", "code-commits")

    captured = capsys.readouterr()
    assert "REFUSED" in captured.out
    assert "--allow-empty" in captured.err
    assert UserAchievement.objects.filter(user=plain_user).count() == 1
    assert UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()


def test_backfill_grants_a_deactivated_member_nothing(plain_user):
    """A deactivated account is skipped however loudly the source names it.

    Deleting an account scrubs its grants but leaves the commits and libraries
    behind it whole, so without this the next sweep would award them all back.
    """
    plain_user.is_active = False
    plain_user.save(update_fields=["is_active"])
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)

    call_command("backfill_achievements", "--source", "code-commits")

    assert not UserAchievement.objects.filter(user=plain_user).exists()
    assert not UserBadge.objects.filter(user=plain_user).exists()


def test_reconcile_takes_back_what_a_deactivated_member_holds(
    plain_user, commit_by_someone_else
):
    """Grants earned before deactivation read as stale, and the badge is revoked.

    Which is what cleans up an account deleted before this rule existed, and an
    account whose deletion never scrubbed the grants in the first place.
    """
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    badge = UserBadge.objects.get(user=plain_user, tier__rank="bronze")

    plain_user.is_active = False
    plain_user.save(update_fields=["is_active"])
    call_command("reconcile_achievements", "--source", "code-commits")

    assert not UserAchievement.objects.filter(user=plain_user).exists()
    badge.refresh_from_db()
    assert badge.revoked_at is not None
    assert badge.revocation_source == "cascade"


def test_a_source_naming_only_deactivated_members_is_not_an_empty_source(plain_user):
    """The refusal asks whether the source read empty, not who survived it.

    A source that named nobody at all is a broken import. A source that named one
    member who has since been deactivated is working exactly as it should, and its
    stale grant has to go.
    """
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    plain_user.is_active = False
    plain_user.save(update_fields=["is_active"])

    call_command("reconcile_achievements", "--source", "code-commits")

    run = AchievementSyncRun.objects.first()
    assert run.refused is False
    assert run.removed == 1
    assert not UserAchievement.objects.filter(user=plain_user).exists()


def test_reconcile_allow_empty_overrides_the_refusal(plain_user, stale_commit_grant):
    """The emptiness is sometimes real, and then the operator says so."""
    call_command("reconcile_achievements", "--source", "code-commits", "--allow-empty")

    assert not UserAchievement.objects.filter(user=plain_user).exists()
    assert not UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()


def test_reconcile_does_not_refuse_a_source_with_nothing_to_do(plain_user, capsys):
    """An empty source with no stale grants is not a refusal, it is a no-op."""
    call_command("reconcile_achievements", "--source", "code-commits")

    captured = capsys.readouterr()
    assert "nothing to change" in captured.out
    assert "REFUSED" not in captured.out
    assert captured.err == ""


def test_reconcile_creates_the_grants_a_source_supports(plain_user):
    """The additive half: a source that gained a pair gets a row and a badge."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)
    assert not UserAchievement.objects.filter(user=plain_user).exists()

    call_command("reconcile_achievements", "--source", "code-commits")

    assert UserAchievement.objects.filter(user=plain_user).count() == 1
    assert UserBadge.objects.filter(
        user=plain_user, badge__achievement__slug="code-commits", revoked_at=None
    ).exists()


def test_reconcile_restores_a_grant_whose_source_supports_it_again(
    plain_user, commit_by_someone_else, stale_commit_grant
):
    """Unbind an author, reconcile, rebind, reconcile: the badge comes back.

    The whole reason this command is two-way. A one-directional prune leaves no
    way to undo itself, so a mistaken unbinding was permanent.
    """
    call_command("reconcile_achievements", "--source", "code-commits")
    assert not UserAchievement.objects.filter(user=plain_user).exists()
    bronze = UserBadge.objects.get(user=plain_user, tier__rank="bronze")
    assert bronze.revocation_source == RevocationSource.CASCADE

    author = stale_commit_grant.author
    author.user = plain_user
    author.save()

    call_command("reconcile_achievements", "--source", "code-commits")

    assert UserAchievement.objects.filter(user=plain_user).count() == 1
    bronze.refresh_from_db()
    assert bronze.revoked_at is None


def test_reconcile_does_not_undo_a_manual_revocation(
    plain_user, commit_by_someone_else
):
    """An admin's deliberate revocation outlives the achievement being re-created."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    bronze = UserBadge.objects.get(user=plain_user, tier__rank="bronze")
    bronze.revoked_at = timezone.now()
    bronze.revocation_source = RevocationSource.MANUAL
    bronze.save()
    # The grant goes missing the way a bulk path loses one: no post_delete, so the
    # revocation is not overwritten with a cascade before the run being tested.
    UserAchievement.objects.filter(user=plain_user)._raw_delete(using="default")

    call_command("reconcile_achievements", "--source", "code-commits")

    assert UserAchievement.objects.filter(user=plain_user).count() == 1
    bronze.refresh_from_db()
    assert bronze.revoked_at is not None
    assert bronze.revocation_source == RevocationSource.MANUAL


def test_reconcile_adds_and_removes_in_one_run(plain_user, commit_by_someone_else):
    """Both halves at once, for different members, off one walk of the source."""
    gaining = baker.make("users.User", email="gaining@example.com")
    baker.make(
        "libraries.Commit", author=baker.make("libraries.CommitAuthor", user=gaining)
    )
    losing_author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=losing_author)
    call_command("backfill_achievements", "--source", "code-commits")
    UserAchievement.objects.filter(user=gaining).delete()
    losing_author.user = None
    losing_author.save()

    call_command("reconcile_achievements", "--source", "code-commits")

    assert UserAchievement.objects.filter(user=gaining).count() == 1
    assert not UserAchievement.objects.filter(user=plain_user).exists()


def test_reconcile_clears_every_sourceless_automatic_grant(
    plain_user, commit_by_someone_else
):
    """All of them, not one per run: they collapse to a single key.

    An automatic row with no source pointer can never be matched against anything
    an iterator yields, so each is stale. They also share one key - the pointer is
    nullable, so nothing distinguishes them - and keying the stored rows one-to-one
    left every duplicate behind for a later run that would never come.
    """
    achievement = Achievement.objects.get(slug=AchievementSlug.CODE_COMMITS)
    for _ in range(3):
        UserAchievement.objects.create(
            user=plain_user, achievement=achievement, source_type=SourceType.AUTOMATIC
        )

    call_command("reconcile_achievements", "--source", "code-commits")

    assert not UserAchievement.objects.filter(user=plain_user).exists()


def test_reconcile_remove_only_skips_the_additive_half(plain_user):
    """The one-directional behaviour is still reachable, by asking for it."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)

    call_command("reconcile_achievements", "--source", "code-commits", "--remove-only")

    assert not UserAchievement.objects.filter(user=plain_user).exists()


def test_backfill_never_removes_anything(plain_user, commit_by_someone_else):
    """The weekly pipeline's command must stay additive whatever else changes."""
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    author.user = None
    author.save()

    call_command("backfill_achievements", "--source", "code-commits")

    assert UserAchievement.objects.filter(user=plain_user).count() == 1


def test_reconcile_fails_on_an_unseeded_source(plain_user):
    """No Achievement row means the catalogue is broken, which is not a skip."""
    Achievement.objects.filter(slug=AchievementSlug.CODE_COMMITS).delete()

    with pytest.raises(CommandError, match="code-commits"):
        call_command("reconcile_achievements", "--source", "code-commits")
