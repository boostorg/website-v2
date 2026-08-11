import datetime
from unittest.mock import patch

import pytest
import waffle.testutils
from model_bakery import baker

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from mailing_list.models import SubscriptionStatus, UserMailingListSubscription
from ..models import LastSeen, Preferences

User = get_user_model()


@pytest.mark.django_db
def test_delete_account_scrubs_pii_and_identity(
    user, django_capture_on_commit_callbacks
):
    """delete_account anonymizes the row in place and clears public PII."""
    user.github_username = "octocat"
    user.profile_links = {
        "github": "https://github.com/octocat",
        "email": "octo@example.com",
    }
    user.indicate_last_login_method = True
    user.image_uploaded = True
    user.save()
    user.hq_image.save("hq.png", ContentFile(b"hq-image-bytes"), save=True)
    tier = baker.make("badges.BadgeTier")
    baker.make("badges.UserAchievement", user=user, achievement=tier.badge.achievement)
    baker.make("badges.UserBadge", user=user, badge=tier.badge, tier=tier)

    original_email = user.email
    original_id = user.id

    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account(extended_scrub=True)

    user.refresh_from_db()
    # The row is preserved (authored content stays attributed to it).
    assert user.id == original_id
    assert user.is_active is False
    assert user.has_usable_password() is False
    assert user.display_name == "John Doe"
    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.email != original_email
    assert user.email.startswith("deleted-")
    # Extra fields scrubbed.
    assert user.github_username == ""
    assert user.profile_links == {}
    assert user.indicate_last_login_method is False
    assert user.image_uploaded is False
    assert not user.profile_image
    assert not user.hq_image
    # The grants go with the badges, or the next recalculation re-awards them.
    assert user.badges.count() == 0
    assert user.achievements.count() == 0
    assert user.delete_permanently_at is None


@pytest.mark.django_db
def test_extended_scrub_leaves_no_badges_behind_across_achievements(
    user, django_capture_on_commit_callbacks
):
    """Every badge goes, whatever the grant deletions recalculate on the way out.

    Dropping a ``UserAchievement`` recalculates that member's badges
    synchronously, and nothing constrains a tier's threshold above zero - a tier
    at 0 is met by a member with no grants at all. Deleting the badges last is
    what keeps such an award from landing in an account already scrubbed of them.
    """
    earned = baker.make("badges.BadgeTier", threshold=1)
    free = baker.make("badges.BadgeTier", threshold=0)
    for tier in (earned, free):
        baker.make(
            "badges.UserAchievement", user=user, achievement=tier.badge.achievement
        )
    assert user.badges.count() == 2

    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account(extended_scrub=True)

    assert user.achievements.count() == 0
    assert user.badges.count() == 0


@pytest.mark.django_db
def test_delete_account_removes_preferences(user, django_capture_on_commit_callbacks):
    """Preferences are removed on deletion in both flows."""
    assert Preferences.objects.filter(user=user).exists()

    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account()

    assert not Preferences.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_v3_delete_account_removes_last_seen(user, django_capture_on_commit_callbacks):
    """LastSeen is a V3-only addition to the scrub."""
    assert LastSeen.objects.filter(user=user).exists()

    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account(extended_scrub=True)

    assert not LastSeen.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_legacy_delete_account_keeps_last_seen(
    user, django_capture_on_commit_callbacks
):
    """Legacy behaviour is unchanged: LastSeen was never part of the scrub."""
    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account()

    assert LastSeen.objects.filter(user=user).exists()


def _make_subscriptions(user):
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id="dev.boost.org",
        email="active@example.com",
        status=SubscriptionStatus.ACTIVE,
    )
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id="users.boost.org",
        email="pending@example.com",
        status=SubscriptionStatus.PENDING,
    )


@pytest.mark.django_db
def test_v3_delete_deletes_mailing_list_rows_without_api_call(
    user, django_capture_on_commit_callbacks
):
    """Local subscription rows are deleted (PII removed); Mailman is not called.

    List membership is left to Postorius - we only drop our stored rows.
    """
    _make_subscriptions(user)

    with patch("mailing_list.client.MailmanClient") as MockClient:
        with django_capture_on_commit_callbacks(execute=True):
            user.delete_account(extended_scrub=True)
        MockClient.assert_not_called()

    assert not UserMailingListSubscription.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_legacy_delete_keeps_mailing_list_rows(
    user, django_capture_on_commit_callbacks
):
    """Legacy behaviour is unchanged: subscription rows were never dropped."""
    _make_subscriptions(user)

    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account()

    assert UserMailingListSubscription.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_delete_account_invalidates_hq_render_cache(
    user, django_capture_on_commit_callbacks
):
    """The cached full-size render goes with the source file, not after it."""
    user.hq_image.save("hq.png", ContentFile(b"hq-image-bytes"), save=True)

    with patch.object(User, "delete_cached_hq_render") as mock_invalidate:
        with django_capture_on_commit_callbacks(execute=True):
            user.delete_account(extended_scrub=True)

    mock_invalidate.assert_called_once()


@pytest.mark.django_db
def test_legacy_delete_leaves_hq_render_cache(user, django_capture_on_commit_callbacks):
    """Legacy deletion never touched hq_image, so its render is left alone."""
    user.hq_image.save("hq.png", ContentFile(b"hq-image-bytes"), save=True)

    with patch.object(User, "delete_cached_hq_render") as mock_invalidate:
        with django_capture_on_commit_callbacks(execute=True):
            user.delete_account()

    mock_invalidate.assert_not_called()


@pytest.mark.django_db
def test_delete_account_is_idempotent(user, django_capture_on_commit_callbacks):
    """A second run (e.g. immediate delete racing the scheduled task) is a no-op."""
    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account()
    with django_capture_on_commit_callbacks(execute=True):
        user.delete_account()  # must not raise

    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_delete_schedules_and_redirects_to_edit(user, tp):
    with tp.login(user):
        res = tp.post("profile-delete", data={"verify": "delete my account"})

    user.refresh_from_db()
    assert user.delete_permanently_at is not None
    assert res.status_code == 302
    assert "edit=true" in res.url


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_delete_sends_scheduled_email(
    user, tp, settings, mailoutbox, django_capture_on_commit_callbacks
):
    user.first_name = "Vinnie"
    user.save()

    with tp.login(user):
        with django_capture_on_commit_callbacks(execute=True):
            tp.post("profile-delete", data={"verify": "delete my account"})

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.subject == "Your account is scheduled for deletion"
    assert email.to == [user.email]
    grace = settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
    assert f"deletion in {grace} day" in email.body
    assert "Vinnie" in email.body
    # HTML alternative is attached and links out to Postorius.
    html_body, mimetype = email.alternatives[0]
    assert mimetype == "text/html"
    assert "Postorius" in html_body


@pytest.mark.django_db
def test_legacy_delete_does_not_send_scheduled_email(user, tp, mailoutbox):
    """The scheduling email is a V3-only addition; legacy behaviour is unchanged."""
    with tp.login(user):
        tp.post("profile-delete", data={"verify": "delete my account"})

    user.refresh_from_db()
    assert user.delete_permanently_at is not None
    assert not any(
        m.subject == "Your account is scheduled for deletion" for m in mailoutbox
    )


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_delete_invalid_confirmation_reopens_modal(user, tp):
    with tp.login(user):
        res = tp.post("profile-delete", data={"verify": "wrong"})

    user.refresh_from_db()
    assert user.delete_permanently_at is None
    assert res.status_code == 302
    assert "#delete-account-dialog" in res.url
    assert "delete_error=1" in res.url


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_delete_invalid_confirmation_renders_inline_error(user, tp):
    """The error is shown inline in the modal, not as a global message banner."""
    with tp.login(user):
        tp.post("profile-delete", data={"verify": "wrong"})
        res = tp.get("profile-account", data={"edit": "true", "delete_error": "1"})

    html = res.content.decode()
    # Inline field error rendered inside the modal (quotes are HTML-escaped).
    assert "Please enter" in html
    assert "field--error" in html
    assert 'class="field__error"' in html
    # No message was queued for the global (legacy) banner.
    assert list(res.context["messages"]) == []


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_cancel_deletion_clears_schedule(user, tp):
    user.delete_permanently_at = timezone.now() + datetime.timedelta(days=10)
    user.save()

    with tp.login(user):
        res = tp.post("profile-cancel-delete", data={})

    user.refresh_from_db()
    assert user.delete_permanently_at is None
    assert res.status_code == 302
    assert "edit=true" in res.url


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_v3_cancel_deletion_shows_no_success_banner(user, tp):
    """V3 relies on the edit-page state, so no legacy success banner is added."""
    user.delete_permanently_at = timezone.now() + datetime.timedelta(days=10)
    user.save()

    with tp.login(user):
        res = tp.post("profile-cancel-delete", data={}, follow=True)

    banners = [str(m) for m in res.context["messages"]]
    assert "Your account is no longer scheduled for deletion." not in banners


@pytest.mark.django_db
def test_legacy_cancel_deletion_keeps_success_banner(user, tp):
    """Legacy behaviour is unchanged: the success banner still fires."""
    user.delete_permanently_at = timezone.now() + datetime.timedelta(days=10)
    user.save()

    with tp.login(user):
        res = tp.post("profile-cancel-delete", data={}, follow=True)

    banners = [str(m) for m in res.context["messages"]]
    assert "Your account is no longer scheduled for deletion." in banners
