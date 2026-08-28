"""Tests for who recalculates after a bulk delete, and how many times.

A member's badges are derived from a count rather than adjusted by a delta, so
recalculating once after ten deletions reaches the same answer as recalculating
after each one. The ``post_delete`` signal cannot know that: it fires per row. A
bulk delete that knows which members it touched therefore takes the job on itself,
and these tests hold that arrangement in place - both halves of it, since a
suppression that outlives its block would leave badges silently over-awarded.
"""

from unittest.mock import patch

import pytest
from django.core.management import call_command
from model_bakery import baker

from badges import services, signals
from badges.enums import TierRank
from badges.models import AchievementSyncRun, UserAchievement, UserBadge
from badges.services import recalculate_badges

pytestmark = pytest.mark.django_db

SOURCE = "code-commits"


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def _spy_on(target):
    """Count calls to ``recalculate_badges`` through one module's reference.

    Each module binds the function at import time, so the counting has to name the
    reference under test: ``badges.signals`` for the per-row signal, and
    ``badges.services`` for the sync's own batched calls.
    """
    return patch(f"{target}.recalculate_badges", side_effect=recalculate_badges)


def _member_with_commits(email, count):
    """A member holding ``count`` attributed commits, and their author row."""
    user = baker.make("users.User", email=email)
    author = baker.make("libraries.CommitAuthor", user=user)
    for _ in range(count):
        baker.make("libraries.Commit", author=author)
    return user, author


def _orphan(author):
    """Break the attribution, leaving the member's grants stale."""
    author.user = None
    author.save()


def test_a_bulk_delete_recalculates_once_per_member_not_once_per_row():
    """Five stale grants for one member are one recalculation, not five.

    The regression this guards: ``QuerySet.delete()`` sends ``post_delete`` per
    row, so before the sync took ownership this member was recalculated five times
    over, at about seven queries each, for an answer that only the last one
    decided.
    """
    member, author = _member_with_commits("five-commits@example.com", 5)
    # Somebody the source still yields, so the run is not refused for reading empty.
    _member_with_commits("still-committing@example.com", 1)
    call_command("backfill_achievements", "--source", SOURCE)
    assert UserAchievement.objects.filter(user=member).count() == 5
    _orphan(author)

    with _spy_on("badges.signals") as from_signal, _spy_on(
        "badges.services"
    ) as batched:
        call_command("reconcile_achievements", "--source", SOURCE)

    assert not UserAchievement.objects.filter(user=member).exists()
    assert from_signal.call_count == 0
    assert batched.call_count == 1
    assert batched.call_args.args[0] == member.pk


def test_the_command_does_not_repeat_what_the_run_already_did():
    """The final pass covers what the run left owing, not what it finished.

    Both call sites used to recalculate every member in ``changed``, on the belief
    that the signal had done the removals - which it had, and then they did them
    again. ``outstanding`` is what makes that division of labour real.
    """
    member, author = _member_with_commits("outstanding@example.com", 2)
    _member_with_commits("still-committing@example.com", 1)
    call_command("backfill_achievements", "--source", SOURCE)
    _orphan(author)

    with _spy_on("badges.management.commands.reconcile_achievements") as final_pass:
        call_command("reconcile_achievements", "--source", SOURCE)

    assert final_pass.call_count == 0


def test_the_summary_still_counts_the_members_a_removal_touched(capsys):
    """What moved and what is left to do are different questions.

    The command recalculates what the run left owing, and reports what the run
    changed. Reading the summary off the first would tell an admin who just removed
    twenty grants that it happened across no members at all.
    """
    _, author = _member_with_commits("counted@example.com", 20)
    _member_with_commits("still-committing@example.com", 1)
    call_command("backfill_achievements", "--source", SOURCE)
    _orphan(author)
    capsys.readouterr()

    call_command("reconcile_achievements", "--source", SOURCE)

    output = capsys.readouterr().out
    assert "removed 20 grant(s) across 1 member(s)" in output
    assert "across 1 (user, achievement) pair(s)" in output


def test_a_delete_outside_a_bulk_run_still_recalculates():
    """The signal is suspended for a block, not disabled.

    Without this the suite would pass on a guard that leaked: an ad-hoc delete in a
    shell, or any future caller, would silently leave a badge awarded against
    grants that no longer exist.
    """
    member, _ = _member_with_commits("ad-hoc@example.com", 1)
    call_command("backfill_achievements", "--source", SOURCE)
    assert UserBadge.objects.filter(user=member, revoked_at=None).exists()

    with _spy_on("badges.signals") as from_signal:
        UserAchievement.objects.filter(user=member).delete()

    assert from_signal.call_count == 1
    assert not UserBadge.objects.filter(user=member, revoked_at=None).exists()


def test_the_guard_is_released_even_when_the_delete_raises():
    """A failure inside the block must not leave the signal suspended.

    Contextvars are per-task, so a leak would not cross into another request, but
    it would silently disarm every later delete in this one.
    """
    with pytest.raises(RuntimeError):
        with services.owns_recalculation():
            raise RuntimeError("boom")

    assert services.recalculation_is_owned() is False


def test_a_run_that_dies_is_a_run_to_repeat():
    """Each chunk deletes and recalculates together, or does neither.

    Two things would break this. Collecting every member and recalculating at the
    end of the run means a crash leaves nobody recalculated. Recalculating per
    chunk but outside the chunk's transaction means a crash leaves that chunk's
    members holding badges their count no longer supports - and *silently*, because
    a second reconcile sees their grants already gone, reports nothing changed, and
    recalculates nobody. Only a full recalculation would ever find them.

    So: the run dies recalculating the second chunk. The first member is settled,
    the second is untouched rather than half-done, the run says it failed, and
    re-running it finishes the job.
    """
    first, first_author = _member_with_commits("first-chunk@example.com", 1)
    second, second_author = _member_with_commits("second-chunk@example.com", 1)
    _member_with_commits("still-committing@example.com", 1)
    call_command("backfill_achievements", "--source", SOURCE)
    _orphan(first_author)
    _orphan(second_author)

    calls = []

    def die_on_the_second_chunk(user_id, achievement_id, **kwargs):
        calls.append(user_id)
        if len(calls) > 1:
            raise RuntimeError("the worker went away")
        return recalculate_badges(user_id, achievement_id, **kwargs)

    with patch.object(services, "recalculate_badges", die_on_the_second_chunk):
        with pytest.raises(RuntimeError):
            # One member per chunk, so the failure lands between two members
            # rather than inside one member's rows.
            call_command(
                "reconcile_achievements", "--source", SOURCE, "--batch-size", "1"
            )

    settled, rolled_back = (first, second) if calls[0] == first.pk else (second, first)
    assert not UserAchievement.objects.filter(user=settled).exists()
    assert not UserBadge.objects.filter(user=settled, revoked_at=None).exists()
    # Neither deleted nor recalculated: the chunk went back the way it came, so the
    # grant and the badge it justifies still agree with each other.
    assert UserAchievement.objects.filter(user=rolled_back).exists()
    assert UserBadge.objects.filter(user=rolled_back, revoked_at=None).exists()
    assert AchievementSyncRun.objects.get(source_slug=SOURCE, error__gt="").error

    call_command("reconcile_achievements", "--source", SOURCE)

    assert not UserAchievement.objects.filter(user=rolled_back).exists()
    assert not UserBadge.objects.filter(user=rolled_back, revoked_at=None).exists()


def test_discarding_a_source_row_recalculates_once_per_pair():
    """The same arrangement on the path that deletes a source object.

    ``discard_source_achievements`` knows its pairs before it deletes, so the
    per-row signal could only reach the same answer more slowly.
    """
    member, _ = _member_with_commits("discarded@example.com", 4)
    call_command("backfill_achievements", "--source", SOURCE)
    commits = list(
        UserAchievement.objects.filter(user=member).values_list(
            "source_object_id", flat=True
        )
    )
    from libraries.models import Commit

    with _spy_on("badges.signals") as from_signal, _spy_on(
        "badges.services"
    ) as batched:
        services.discard_source_achievements(Commit, commits)

    assert not UserAchievement.objects.filter(user=member).exists()
    assert from_signal.call_count == 0
    assert batched.call_count == 1


def test_discarding_more_rows_than_one_batch_still_recalculates_once():
    """A member whose grants straddle two chunks is still one answer to reach.

    The pairs are collected across every chunk and recalculated after the last
    one. Collecting them per chunk instead would undo the batching this module
    exists to hold in place, once per chunk the member appears in.
    """
    member, _ = _member_with_commits("straddling@example.com", 5)
    call_command("backfill_achievements", "--source", SOURCE)
    commits = list(
        UserAchievement.objects.filter(user=member).values_list(
            "source_object_id", flat=True
        )
    )
    assert len(commits) == 5
    from libraries.models import Commit

    with patch.object(services, "SYNC_BATCH_SIZE", 2):
        with _spy_on("badges.signals") as from_signal, _spy_on(
            "badges.services"
        ) as batched:
            services.discard_source_achievements(Commit, commits)

    assert not UserAchievement.objects.filter(user=member).exists()
    assert from_signal.call_count == 0
    assert batched.call_count == 1


def test_a_tier_the_member_no_longer_qualifies_for_is_still_revoked():
    """The end-to-end promise, independent of who does the recalculating.

    Everything above is about how many times the count is read. This is about the
    answer: a member whose grants go below a threshold loses the badge, and the
    revocation still names the run that moved the count.
    """
    member, author = _member_with_commits("revoked@example.com", 3)
    _member_with_commits("still-committing@example.com", 1)
    call_command("backfill_achievements", "--source", SOURCE)
    assert UserBadge.objects.filter(
        user=member, tier__rank=TierRank.BRONZE, revoked_at=None
    ).exists()
    _orphan(author)

    call_command("reconcile_achievements", "--source", SOURCE)

    revoked = UserBadge.objects.get(user=member, tier__rank=TierRank.BRONZE)
    assert revoked.revoked_at is not None
    assert revoked.count_at_revocation == 0
    run = AchievementSyncRun.objects.get(source_slug=SOURCE, removed=3)
    assert f"#{run.pk}" in revoked.revocation_notes


def test_the_signal_module_and_the_service_agree_on_the_guard():
    """``signals`` reads the guard through the function, not a copy of its value."""
    assert signals.recalculation_is_owned is services.recalculation_is_owned
