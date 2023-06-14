from datetime import date

import pytest
from django.core import mail
from django.urls import reverse

from ..models import NEWS_MODELS
from ..notifications import send_email_after_approval, send_email_news_needs_moderation
from users.models import Preferences


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_after_approval(rf, tp, make_entry, model_class):
    entry = make_entry(model_class, approved=True, created_at=date(2023, 5, 31))
    assert entry.tag in entry.author.preferences.allow_notification_own_news_approved

    request = rf.get("")

    result = send_email_after_approval(request, entry)

    assert result == 1
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert "news entry approved" in msg.subject.lower()
    assert entry.title in msg.body
    assert "May 31st, 2023" in msg.body
    assert request.build_absolute_uri(entry.get_absolute_url()) in msg.body
    assert msg.recipients() == [entry.author.email]


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_after_approval_author_email_preferences_do_not_notify_all_types(
    rf, tp, make_entry, model_class, make_user
):
    entry = make_entry(model_class, approved=True)
    entry.author.preferences.notifications[Preferences.OWNS_NEWS_APPROVED] = []
    assert (
        entry.tag not in entry.author.preferences.allow_notification_own_news_approved
    )
    request = rf.get("")

    result = send_email_after_approval(request, entry)

    assert result is False


def test_send_email_after_approval_author_email_preferences_do_not_notify_other_type(
    rf, tp, make_entry, make_user
):
    entry = make_entry(model_class=NEWS_MODELS[0], approved=True)
    entry.author.preferences.notifications[Preferences.OWNS_NEWS_APPROVED] = [
        NEWS_MODELS[1].news_type
    ]
    assert (
        entry.tag not in entry.author.preferences.allow_notification_own_news_approved
    )
    request = rf.get("")

    result = send_email_after_approval(request, entry)

    assert result is False


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_news_needs_moderation(
    rf,
    tp,
    make_entry,
    model_class,
    make_user,
    moderator_user,
    superuser,
):
    entry = make_entry(model_class, approved=True)

    # Other moderator with default email notifications preferences
    other_moderator = make_user(groups={"moderator": ["news.*"]}, email="other@x.com")
    # Third moderator that does not allow any email notifications
    third = make_user(groups={"editors": ["news.*"]}, email="thrid@x.com")
    third.preferences.notifications[Preferences.OTHERS_NEWS_NEEDS_MODERATION] = []
    third.preferences.save()
    # Forth moderator that do allow email notifications for this news type
    forth = make_user(perms=["news.*"], email="forth@example.com")
    forth.preferences.notifications[Preferences.OTHERS_NEWS_NEEDS_MODERATION] = [
        entry.tag
    ]
    forth.preferences.save()

    request = rf.get("")

    with tp.assertNumQueriesLessThan(2, verbose=True):
        result = send_email_news_needs_moderation(request, entry)

    assert result == 1
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert "news entry needs moderation" in msg.subject.lower()
    assert entry.title in msg.body
    assert entry.author.get_display_name in msg.body
    assert entry.author.email in msg.body
    assert request.build_absolute_uri(entry.get_absolute_url()) in msg.body
    assert request.build_absolute_uri(reverse("news-moderate")) in msg.body
    assert msg.recipients() == sorted(
        [other_moderator.email, moderator_user.email, superuser.email, forth.email]
    )


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_news_needs_moderation_no_moderator_match(
    rf, tp, make_entry, model_class, moderator_user
):
    moderator_user.preferences.notifications[
        Preferences.OTHERS_NEWS_NEEDS_MODERATION
    ] = []
    moderator_user.preferences.save()
    entry = make_entry(model_class, approved=True)
    request = rf.get("")

    with tp.assertNumQueriesLessThan(2, verbose=True):
        result = send_email_news_needs_moderation(request, entry)

    assert result is False
