from datetime import date

import pytest
from django.conf import settings
from django.core import mail
from django.utils.html import escape
from django.urls import reverse
from itsdangerous import URLSafeTimedSerializer

from ..models import NEWS_MODELS
from ..notifications import (
    send_email_news_approved,
    send_email_news_needs_moderation,
    send_email_news_posted,
    generate_magic_approval_link,
    NEWS_APPROVAL_SALT,
)
from users.models import Preferences


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_news_approved(rf, tp, make_entry, model_class):
    entry = make_entry(model_class, approved=True, created_at=date(2023, 5, 31))
    assert entry.tag in entry.author.preferences.allow_notification_own_news_approved

    request = rf.get("")

    result = send_email_news_approved(request, entry)

    assert result == 1
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert "news entry approved" in msg.subject.lower()
    assert entry.title in msg.body
    assert escape(entry.title) not in msg.body
    assert "May 31st, 2023" in msg.body
    assert request.build_absolute_uri(entry.get_absolute_url()) in msg.body
    assert msg.recipients() == [entry.author.email]


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_news_approved_author_email_preferences_do_not_notify_all_types(
    rf, tp, make_entry, model_class, make_user
):
    entry = make_entry(model_class, approved=True)
    entry.author.preferences.notifications[Preferences.OWNS_NEWS_APPROVED] = []
    assert (
        entry.tag not in entry.author.preferences.allow_notification_own_news_approved
    )
    request = rf.get("")

    result = send_email_news_approved(request, entry)

    assert result is False


def test_send_email_news_approved_author_email_preferences_do_not_notify_other_type(
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

    result = send_email_news_approved(request, entry)

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

    assert result == 4
    assert len(mail.outbox) == 4
    msg = mail.outbox[0]
    assert "news entry needs moderation" in msg.subject.lower()
    assert entry.title in msg.body
    assert escape(entry.title) not in msg.body
    assert entry.author.get_display_name in msg.body
    assert entry.author.email in msg.body
    assert request.build_absolute_uri(entry.get_absolute_url()) in msg.body
    assert request.build_absolute_uri(reverse("news-moderate")) in msg.body
    recipients = []
    for msg in mail.outbox:
        recipients.extend(msg.recipients())
    assert set(recipients) == {
        other_moderator.email,
        moderator_user.email,
        superuser.email,
        forth.email,
    }


def test_generate_magic_approval_link(make_entry, make_user):
    entry = make_entry()
    # entry = make_entry(NEWS_MODELS[0])
    moderator = make_user(groups={"moderator": ["news.*"]}, email="mod@x.com")
    url = generate_magic_approval_link(entry.slug, moderator.id)

    dummy_token = "dummy-token"
    expected_base_url = (
        reverse("news-magic-approve", kwargs={"token": dummy_token})
        .replace(dummy_token, "")
        .rstrip("/")
    )
    assert url.startswith(expected_base_url)

    token = url.split(expected_base_url)[-1].strip("/")
    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    data = serializer.loads(token, salt=NEWS_APPROVAL_SALT)

    assert data["entry_slug"] == entry.slug
    assert data["moderator_id"] == moderator.id


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


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_news_posted_no_other_user(rf, make_entry, model_class):
    entry = make_entry(model_class, approved=False)
    request = rf.get("")

    result = send_email_news_posted(request, entry)

    assert result is False


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_news_posted_no_other_user_allows(
    rf, make_entry, make_user, model_class
):
    entry = make_entry(model_class, approved=False)
    request = rf.get("")

    for _ in range(3):
        u = make_user()
        u.preferences.allow_notification_others_news_posted = []
        u.preferences.save()

    result = send_email_news_posted(request, entry)

    assert result is False


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_send_email_news_posted_many_users(rf, tp, make_entry, make_user, model_class):
    entry = make_entry(model_class, approved=False)
    request = rf.get("")

    recipients = {
        # user does not allow notifications
        "u1@example.com": [],
        # allows nofitications for all news type
        "u2@example.com": [m.news_type for m in NEWS_MODELS],
        # allows only for the same type as entry
        "u3@example.com": [entry.tag],
        # allows for any other type except entry's
        "u4@example.com": [
            m.news_type for m in NEWS_MODELS if m.news_type != entry.tag
        ],
    }

    for email, notifications in recipients.items():
        make_user(email=email, allow_notification_others_news_posted=notifications)

    with tp.assertNumQueriesLessThan(2, verbose=True):
        result = send_email_news_posted(request, entry)

    # We should send two emails - one to u2, one to u3
    assert result == len(mail.outbox) == 2
    for usr_num, msg in enumerate(mail.outbox, start=2):
        assert "news entry posted" in msg.subject.lower()
        assert entry.title in msg.body
        assert escape(entry.title) not in msg.body
        assert entry.author.email not in msg.body  # never disclose author email!
        assert request.build_absolute_uri(entry.get_absolute_url()) in msg.body
        assert request.build_absolute_uri(tp.reverse("profile-account")) in msg.body
        # do not share all emails among all recipients
        assert msg.to == [f"u{usr_num}@example.com"]
        assert msg.recipients() == [f"u{usr_num}@example.com"]
