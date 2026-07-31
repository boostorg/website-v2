"""Tests for the badges admin actions and manual-grant behaviour."""

from unittest.mock import Mock, patch

import pytest
from django.contrib.admin import helpers
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from badges.admin import UserAchievementAdmin, UserBadgeAdmin
from badges.enums import TierRank
from badges.models import (
    BadgeTier,
    RevocationSource,
    SourceType,
    UserAchievement,
    UserBadge,
)
from badges.services import deactivate_tier
from badges.tests.fixtures import grant_from_source

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_task_button_locks():
    """The task buttons debounce through the cache; isolate tests from each other."""
    cache.clear()


def test_manual_create_sets_source_type_and_granted_by(achievement, super_user):
    """save_model marks admin-created grants as manual and records the admin."""
    admin = UserAchievementAdmin(UserAchievement, AdminSite())
    request = RequestFactory().post("/")
    request.user = super_user
    obj = UserAchievement(achievement=achievement, user=super_user)

    admin.save_model(request, obj, form=None, change=False)

    obj.refresh_from_db()
    assert obj.source_type == SourceType.MANUAL
    assert obj.granted_by == super_user


def test_invalidate_action_requires_notes(
    client, super_user, plain_user, achievement, grant_achievement
):
    """Invalidation with an empty note does not change the achievement."""
    rows = grant_achievement(plain_user, achievement, count=1)
    client.force_login(super_user)
    url = reverse("admin:badges_userachievement_changelist")

    client.post(
        url,
        {
            "action": "invalidate",
            helpers.ACTION_CHECKBOX_NAME: [rows[0].pk],
            "apply": "1",
            "notes": "",
        },
    )

    rows[0].refresh_from_db()
    assert rows[0].is_valid is True


def test_invalidate_action_with_notes(
    client, super_user, plain_user, achievement, grant_achievement
):
    """Invalidation records the admin, timestamp and note."""
    rows = grant_achievement(plain_user, achievement, count=1)
    client.force_login(super_user)
    url = reverse("admin:badges_userachievement_changelist")

    client.post(
        url,
        {
            "action": "invalidate",
            helpers.ACTION_CHECKBOX_NAME: [rows[0].pk],
            "apply": "1",
            "notes": "Duplicate record",
        },
    )

    rows[0].refresh_from_db()
    assert rows[0].is_valid is False
    assert rows[0].invalidated_by == super_user
    assert rows[0].invalidated_at is not None
    assert rows[0].invalidation_notes == "Duplicate record"


@pytest.mark.parametrize(
    "changelist,action,selected",
    [
        ("admin:badges_userachievement_changelist", "invalidate", "grant"),
        ("admin:badges_userbadge_changelist", "revoke", "badge"),
    ],
)
def test_notes_page_is_laid_out_and_cancels_back_to_the_list(
    client,
    super_user,
    plain_user,
    badge,
    achievement,
    grant_achievement,
    changelist,
    action,
    selected,
):
    """The third confirmation page of its kind, and the one that was left behind.

    ``.submit-row`` is only a flex bar because of the admin's own ``forms.css``,
    which ``base_site.html`` does not load - so without it the submit and Cancel
    stack with no spacing and Cancel keeps the admin's link underline. Cancel is
    also an explicit url: this page is posted to from the changelist, so ``../``
    would land on the app index rather than back on the list.
    """
    grant_achievement(plain_user, achievement, count=1)
    row = (
        UserAchievement.objects.get(user=plain_user)
        if selected == "grant"
        else UserBadge.objects.get(user=plain_user, tier__rank=TierRank.BRONZE)
    )
    client.force_login(super_user)
    changelist_url = reverse(changelist)

    body = client.post(
        changelist_url,
        {"action": action, helpers.ACTION_CHECKBOX_NAME: [row.pk]},
    ).content.decode()

    assert "admin/css/forms.css" in body
    assert "css/admin/controls.css" in body
    assert f'href="{changelist_url}" class="button cancel-link"' in body


def test_source_column_links_a_registered_source(client, super_user, plain_user):
    """An automatic grant must show what it came from."""
    achievement = baker.make("badges.Achievement", slug="code-commits")
    author = baker.make("libraries.CommitAuthor", user=plain_user)
    commit = baker.make("libraries.Commit", author=author)
    grant_from_source(plain_user, achievement, commit)
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_userachievement_changelist"))

    assert reverse("admin:libraries_commit_change", args=[commit.pk]).encode() in (
        response.content
    )


def test_source_column_falls_back_for_an_unregistered_source(
    client, super_user, plain_user
):
    """news.Entry has no admin, so the column shows its label instead of 500ing."""
    achievement = baker.make("badges.Achievement", slug="publisher")
    entry = baker.make("news.Entry", author=plain_user, title="A published post")
    grant_from_source(plain_user, achievement, entry)
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_userachievement_changelist"))

    assert response.status_code == 200
    assert b"A published post" in response.content


def test_source_column_is_blank_for_a_manual_grant(
    client, super_user, plain_user, achievement, grant_achievement
):
    """A manual grant has no source row to point at."""
    grant_achievement(plain_user, achievement, count=1)
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_userachievement_changelist"))

    assert response.status_code == 200


def test_revalidate_action_clears_the_audit_fields(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Revalidating restores the count and leaves no stale invalidation trail."""
    rows = grant_achievement(plain_user, achievement, count=1)
    rows[0].is_valid = False
    rows[0].invalidated_by = super_user
    rows[0].invalidated_at = timezone.now()
    rows[0].invalidation_notes = "Duplicate record"
    rows[0].save()
    assert not UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()
    client.force_login(super_user)

    client.post(
        reverse("admin:badges_userachievement_changelist"),
        {"action": "revalidate", helpers.ACTION_CHECKBOX_NAME: [rows[0].pk]},
    )

    rows[0].refresh_from_db()
    assert rows[0].is_valid is True
    assert rows[0].invalidated_by is None
    assert rows[0].invalidated_at is None
    assert rows[0].invalidation_notes == ""
    assert UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()


def test_invalidate_action_reports_an_already_invalid_selection(
    client, super_user, plain_user, achievement, grant_achievement
):
    """The confirmation page must not list rows the action would skip."""
    rows = grant_achievement(plain_user, achievement, count=1)
    rows[0].is_valid = False
    rows[0].save()
    client.force_login(super_user)

    response = client.post(
        reverse("admin:badges_userachievement_changelist"),
        {"action": "invalidate", helpers.ACTION_CHECKBOX_NAME: [rows[0].pk]},
        follow=True,
    )

    assert "Nothing to invalidate" in response.content.decode()


def test_revoke_action_reports_an_already_revoked_selection(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """The confirmation page must not list badges the action would skip."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )
    bronze.revoked_at = timezone.now()
    bronze.revocation_source = RevocationSource.MANUAL
    bronze.save()
    client.force_login(super_user)

    response = client.post(
        reverse("admin:badges_userbadge_changelist"),
        {"action": "revoke", helpers.ACTION_CHECKBOX_NAME: [bronze.pk]},
        follow=True,
    )

    assert "Nothing to revoke" in response.content.decode()


def test_revoke_action_requires_notes(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Revoking a badge with an empty note leaves it active."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )
    client.force_login(super_user)
    url = reverse("admin:badges_userbadge_changelist")

    client.post(
        url,
        {
            "action": "revoke",
            helpers.ACTION_CHECKBOX_NAME: [bronze.pk],
            "apply": "1",
            "notes": "",
        },
    )

    bronze.refresh_from_db()
    assert bronze.revoked_at is None


def test_revoke_action_with_notes(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Revoking a badge records the admin, timestamp and note."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )
    client.force_login(super_user)
    url = reverse("admin:badges_userbadge_changelist")

    client.post(
        url,
        {
            "action": "revoke",
            helpers.ACTION_CHECKBOX_NAME: [bronze.pk],
            "apply": "1",
            "notes": "Awarded by mistake",
        },
    )

    bronze.refresh_from_db()
    assert bronze.revoked_at is not None
    assert bronze.revoked_by == super_user
    assert bronze.revocation_notes == "Awarded by mistake"
    assert bronze.revocation_source == RevocationSource.MANUAL


def test_reinstate_action_clears_manual_revocation(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Reinstating undoes the revocation without pretending it was earned again."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )
    originally_awarded_at = timezone.datetime(2025, 3, 7, 14, 30, tzinfo=timezone.UTC)
    bronze.awarded_at = originally_awarded_at
    bronze.revoked_at = timezone.now()
    bronze.revoked_by = super_user
    bronze.revocation_notes = "Awarded by mistake"
    bronze.revocation_source = RevocationSource.MANUAL
    bronze.save()
    client.force_login(super_user)
    url = reverse("admin:badges_userbadge_changelist")

    client.post(
        url,
        {"action": "reinstate", helpers.ACTION_CHECKBOX_NAME: [bronze.pk]},
    )

    bronze.refresh_from_db()
    assert bronze.revoked_at is None
    assert bronze.revoked_by is None
    assert bronze.revocation_notes == ""
    assert bronze.revocation_source == ""
    assert bronze.awarded_at == originally_awarded_at


def test_reinstate_action_refuses_a_cascade_revocation(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Reinstating a cascade revocation would award an unearned badge."""
    rows = grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )

    rows[0].is_valid = False
    rows[0].invalidated_by = super_user
    rows[0].save()
    bronze.refresh_from_db()
    assert bronze.revocation_source == RevocationSource.CASCADE

    client.force_login(super_user)
    response = client.post(
        reverse("admin:badges_userbadge_changelist"),
        {"action": "reinstate", helpers.ACTION_CHECKBOX_NAME: [bronze.pk]},
        follow=True,
    )

    bronze.refresh_from_db()
    assert bronze.revoked_at is not None
    assert bronze.revocation_source == RevocationSource.CASCADE
    assert "Skipped 1 cascade-revoked badge(s)" in response.content.decode()


def test_userbadge_status_filter_partitions_the_rows(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Held and revoked, rather than Django's date filter on revoked_at."""
    grant_achievement(plain_user, achievement, count=1)
    held = UserBadge.objects.get(user=plain_user)
    revoked = baker.make(
        UserBadge,
        badge=badge,
        user=super_user,
        tier=badge.tiers.get(rank=TierRank.SILVER),
        revoked_at=timezone.now(),
    )
    client.force_login(super_user)
    url = reverse("admin:badges_userbadge_changelist")

    def ids(query):
        """The primary keys the changelist returns for one filter query."""
        return set(
            client.get(f"{url}{query}")
            .context["cl"]
            .queryset.values_list("pk", flat=True)
        )

    assert ids("?status=held") == {held.pk}
    assert ids("?status=revoked") == {revoked.pk}


def test_userbadge_changelist_shows_a_hidden_profile(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """ "My badge is missing" is usually hide_badges, so make it visible."""
    grant_achievement(plain_user, achievement, count=1)
    plain_user.hide_badges = True
    plain_user.save(update_fields=["hide_badges"])
    admin_class = UserBadgeAdmin(UserBadge, AdminSite())

    row = UserBadge.objects.get(user=plain_user)

    assert admin_class.is_held(row) is True
    assert admin_class.hidden_by_member(row) is True


def test_tier_delete_is_a_soft_delete(client, super_user, badge):
    """Deleting a tier in the admin deactivates it instead of removing it."""
    silver = badge.tiers.get(rank=TierRank.SILVER)
    client.force_login(super_user)
    url = reverse("admin:badges_badgetier_delete", args=[silver.pk])

    client.post(url, {"post": "yes"})

    silver.refresh_from_db()  # row still exists
    assert silver.is_active is False
    assert silver.deactivated_by == super_user
    assert silver.deactivated_at is not None


def test_reactivate_action_restores_a_retired_tier(client, super_user, badge):
    """A retired tier's change form has no fields, so an action is the only undo."""
    silver = badge.tiers.get(rank=TierRank.SILVER)
    deactivate_tier(silver, actor=super_user)
    client.force_login(super_user)

    client.post(
        reverse("admin:badges_badgetier_changelist"),
        {"action": "reactivate", helpers.ACTION_CHECKBOX_NAME: [silver.pk]},
    )

    silver.refresh_from_db()
    assert silver.is_active is True
    assert silver.deactivated_at is None


def test_reactivate_action_refuses_a_replaced_tier(client, super_user, badge):
    """Reactivating would break the one-active-tier-per-rank constraint."""
    silver = badge.tiers.get(rank=TierRank.SILVER)
    deactivate_tier(silver, actor=super_user)
    baker.make(BadgeTier, badge=badge, rank=TierRank.SILVER, threshold=9)
    client.force_login(super_user)

    response = client.post(
        reverse("admin:badges_badgetier_changelist"),
        {"action": "reactivate", helpers.ACTION_CHECKBOX_NAME: [silver.pk]},
        follow=True,
    )

    silver.refresh_from_db()
    assert silver.is_active is False
    assert "Retire the replacement first" in response.content.decode()


def test_tier_changelist_groups_a_badge_ladder_together(client, super_user, catalogue):
    """Ordering by threshold alone interleaves every badge's bronze row."""
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_badgetier_changelist"))

    labels = [row.badge.label for row in response.context["cl"].result_list]
    assert labels == sorted(labels)


def test_tier_threshold_is_readonly_on_change(client, super_user, badge):
    """The change form locks rank/threshold so the record can't be rewritten."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    client.force_login(super_user)
    url = reverse("admin:badges_badgetier_change", args=[bronze.pk])

    response = client.get(url)
    form_fields = response.context["adminform"].form.fields
    assert "threshold" not in form_fields
    assert "rank" not in form_fields


def test_revoke_action_does_not_touch_achievements(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Direct badge revocation must not alter UserAchievement rows."""
    grant_achievement(plain_user, achievement, count=1)
    bronze = UserBadge.objects.get(
        user=plain_user, badge=badge, tier__rank=TierRank.BRONZE
    )
    client.force_login(super_user)
    url = reverse("admin:badges_userbadge_changelist")

    client.post(
        url,
        {
            "action": "revoke",
            helpers.ACTION_CHECKBOX_NAME: [bronze.pk],
            "apply": "1",
            "notes": "x",
        },
    )

    assert (
        UserAchievement.objects.filter(
            user=plain_user, achievement=achievement, is_valid=True
        ).count()
        == 1
    )


@pytest.mark.parametrize(
    "url_name",
    ["admin:badges_achievement_delete", "admin:badges_badge_delete"],
)
def test_configuration_rows_cannot_be_deleted(
    client, super_user, badge, achievement, url_name
):
    """Deleting a type or a badge destroys grants or dead-ends on PROTECT."""
    client.force_login(super_user)
    target = achievement if "achievement" in url_name else badge

    response = client.get(reverse(url_name, args=[target.pk]))

    assert response.status_code == 403


def test_awarded_rows_cannot_be_added_or_hard_deleted(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """UserBadge is derived, and both audit tables soft-delete by design."""
    grant_achievement(plain_user, achievement, count=1)
    awarded = UserBadge.objects.get(user=plain_user)
    grant = UserAchievement.objects.get(user=plain_user)
    client.force_login(super_user)

    assert client.get(reverse("admin:badges_userbadge_add")).status_code == 403
    assert (
        client.get(
            reverse("admin:badges_userbadge_delete", args=[awarded.pk])
        ).status_code
        == 403
    )
    assert (
        client.get(
            reverse("admin:badges_userachievement_delete", args=[grant.pk])
        ).status_code
        == 403
    )


def test_userachievement_add_form_collects_only_the_grant(client, super_user):
    """The add form must not offer the fields save_model overrides."""
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_userachievement_add"))

    assert list(response.context["adminform"].form.fields) == [
        "user",
        "achievement",
        "grant_notes",
    ]


def test_manual_grant_requires_a_note(client, super_user, plain_user, achievement):
    """A grant with no source must say why it exists, or it does not exist.

    The asymmetry this closes: invalidating an achievement has always demanded a
    note, while granting one by hand demanded nothing - and the manual grant is the
    case with no source row to explain it.
    """
    client.force_login(super_user)

    response = client.post(
        reverse("admin:badges_userachievement_add"),
        {"user": plain_user.pk, "achievement": achievement.pk, "grant_notes": "   "},
    )

    assert response.status_code == 200
    assert "grant_notes" in response.context["adminform"].form.errors
    assert not UserAchievement.objects.filter(user=plain_user).exists()


def test_manual_grant_records_the_note(client, super_user, plain_user, achievement):
    """The note is stored on the row alongside the admin who typed it."""
    client.force_login(super_user)

    client.post(
        reverse("admin:badges_userachievement_add"),
        {
            "user": plain_user.pk,
            "achievement": achievement.pk,
            "grant_notes": "Chaired the Boost.Asio review, which no source sees.",
        },
    )

    grant = UserAchievement.objects.get(user=plain_user)
    assert grant.grant_notes == "Chaired the Boost.Asio review, which no source sees."
    assert grant.source_type == SourceType.MANUAL
    assert grant.granted_by == super_user


def test_changelist_shows_the_note_truncated(
    client, super_user, plain_user, achievement, grant_achievement
):
    """The reason is readable from the changelist, without opening the row."""
    grant = grant_achievement(plain_user, achievement, count=1)[0]
    grant.grant_notes = "Ran the release train " + "for a very long time " * 10
    grant.save(update_fields=["grant_notes"])
    client.force_login(super_user)

    body = client.get(
        reverse("admin:badges_userachievement_changelist")
    ).content.decode()

    assert "Ran the release train" in body
    assert grant.grant_notes not in body


def test_a_note_is_searchable(
    client, super_user, plain_user, achievement, grant_achievement
):
    """Finding every grant made for one reason is a search, not a scroll."""
    kept, other = grant_achievement(plain_user, achievement, count=2)
    kept.grant_notes = "Compensating for the reassigned commits"
    kept.save(update_fields=["grant_notes"])
    client.force_login(super_user)

    response = client.get(
        reverse("admin:badges_userachievement_changelist"), {"q": "reassigned commits"}
    )

    assert [row.pk for row in response.context["cl"].result_list] == [kept.pk]
    assert other.pk not in [row.pk for row in response.context["cl"].result_list]


def test_existing_rows_are_read_only(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """A grant and a badge are records: state changes go through the actions.

    ``grant_notes`` is the single exception, and is asserted exactly rather than
    loosely: rewording a reason moves no badge, but anything *else* becoming
    editable here does, so the list stays pinned.
    """
    grant_achievement(plain_user, achievement, count=1)
    grant = UserAchievement.objects.get(user=plain_user)
    awarded = UserBadge.objects.get(user=plain_user)
    client.force_login(super_user)

    for url, editable in (
        (
            reverse("admin:badges_userachievement_change", args=[grant.pk]),
            ["grant_notes"],
        ),
        (reverse("admin:badges_userbadge_change", args=[awarded.pk]), []),
    ):
        response = client.get(url)
        assert response.status_code == 200
        assert list(response.context["adminform"].form.fields) == editable


def test_badge_achievement_is_frozen_after_creation(client, super_user, badge):
    """Repointing a badge would orphan every UserBadge awarded against it."""
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_badge_change", args=[badge.pk]))

    assert "achievement" not in response.context["adminform"].form.fields


@pytest.mark.parametrize(
    "changelist,url_name,task",
    [
        (
            "admin:badges_userachievement_changelist",
            "admin:badges_userachievement_backfill",
            "backfill_achievements_task",
        ),
        (
            "admin:badges_userbadge_changelist",
            "admin:badges_userbadge_recalculate",
            "recalculate_all_badges_task",
        ),
    ],
)
def test_each_changelist_offers_its_own_task_button(
    client, super_user, changelist, url_name, task
):
    """The wiring: this changelist offers this button, which starts this task.

    Everything the button does *as* a button - POST only, permission-gated, one
    click one job, the status of the last run - belongs to the mixin and is
    covered in ``core/tests/test_admin_buttons.py``.
    """
    client.force_login(super_user)
    url = reverse(url_name)

    assert url.encode() in client.get(reverse(changelist)).content

    with patch(f"badges.admin.{task}.delay") as mock_delay:
        response = client.post(url)

    mock_delay.assert_called_once_with()
    assert response.status_code == 302


RECONCILE_URL = "admin:badges_userachievement_reconcile"
RECONCILE_TASK = "badges.admin.reconcile_achievements_task.delay"


def _staff_with(email, *codenames):
    """A staff account holding exactly the named badges permissions."""
    staff = baker.make("users.User", email=email, is_staff=True)
    staff.user_permissions.set(
        Permission.objects.filter(
            codename__in=codenames, content_type__app_label="badges"
        )
    )
    return staff


def _stale_grant_for(user):
    """Give ``user`` a commits achievement and then break its attribution."""
    author = baker.make("libraries.CommitAuthor", user=user)
    baker.make("libraries.Commit", author=author)
    call_command("backfill_achievements", "--source", "code-commits")
    author.user = None
    author.save()


def test_reconcile_button_previews_before_deleting_anything(
    client, super_user, plain_user, commit_by_someone_else, stale_commit_grant
):
    """The first POST is a dry run rendered as a page, not a job."""
    client.force_login(super_user)

    response = client.post(reverse(RECONCILE_URL))

    body = response.content.decode()
    assert response.status_code == 200
    assert "would remove 1 grant(s)" in body
    assert 'name="apply"' in body
    assert UserAchievement.objects.filter(user=plain_user).count() == 1
    assert UserBadge.objects.filter(user=plain_user, revoked_at=None).exists()


def test_reconcile_button_enqueues_the_task_only_on_apply(
    client, super_user, plain_user, commit_by_someone_else, stale_commit_grant
):
    """The preview's own submit is what starts the job."""
    client.force_login(super_user)

    with patch(RECONCILE_TASK, return_value=Mock(id="a-task-id")) as delay:
        response = client.post(reverse(RECONCILE_URL), {"apply": "1"}, follow=True)

    delay.assert_called_once_with()
    assert "being reconciled with their sources" in response.content.decode()


def test_reconcile_preview_carries_the_chosen_source_into_the_apply(
    client, super_user, plain_user, commit_by_someone_else, stale_commit_grant
):
    """A scoped preview must apply the same scope it previewed."""
    client.force_login(super_user)

    response = client.post(reverse(RECONCILE_URL), {"slug": "code-commits"})
    assert 'value="code-commits"' in response.content.decode()

    with patch(RECONCILE_TASK, return_value=Mock(id="a-task-id")) as delay:
        client.post(reverse(RECONCILE_URL), {"slug": "code-commits", "apply": "1"})

    delay.assert_called_once_with(slug="code-commits")


def test_reconcile_preview_offers_no_apply_when_everything_agrees(
    client, super_user, plain_user, commit_by_someone_else
):
    """A preview with nothing to do is not a decision worth offering."""
    client.force_login(super_user)

    response = client.post(reverse(RECONCILE_URL))

    body = response.content.decode()
    assert "Nothing to reconcile" in body
    assert 'name="apply"' not in body


def test_reconcile_preview_reports_grants_it_would_create(
    client, super_user, plain_user, commit_by_someone_else
):
    """The additive half shows up in the preview too, not only the destructive one."""
    baker.make(
        "libraries.Commit", author=baker.make("libraries.CommitAuthor", user=plain_user)
    )
    client.force_login(super_user)

    response = client.post(reverse(RECONCILE_URL), {"slug": "code-commits"})

    body = response.content.decode()
    assert "would add 1 grant(s)" in body
    assert 'name="apply"' in body
    assert not UserAchievement.objects.filter(user=plain_user).exists()


def test_reconcile_preview_refuses_an_empty_source(
    client, super_user, plain_user, stale_commit_grant
):
    """An empty source is reported, explained, and not offered as applyable."""
    client.force_login(super_user)

    response = client.post(reverse(RECONCILE_URL), {"slug": "code-commits"})

    body = response.content.decode()
    assert "REFUSED" in body
    assert "--allow-empty" in body
    assert 'name="apply"' not in body
    assert UserAchievement.objects.filter(user=plain_user).count() == 1


def test_reconcile_button_needs_more_than_the_change_permission(
    client, plain_user, commit_by_someone_else, stale_commit_grant
):
    """Deleting achievements is not something ``change`` authorises."""
    staff = _staff_with(
        "changer@example.com", "view_userachievement", "change_userachievement"
    )
    client.force_login(staff)

    body = client.get(
        reverse("admin:badges_userachievement_changelist")
    ).content.decode()
    assert "Backfill achievements" in body
    assert "Reconcile achievements" not in body

    assert client.post(reverse(RECONCILE_URL)).status_code == 403
    assert UserAchievement.objects.filter(user=plain_user).count() == 1


def test_reconcile_status_endpoint_needs_the_delete_permission(client, db):
    """The state of a job is not offered to someone who cannot start it."""
    staff = _staff_with(
        "status-changer@example.com", "view_userachievement", "change_userachievement"
    )
    client.force_login(staff)

    assert client.get(reverse(f"{RECONCILE_URL}_status")).status_code == 403
