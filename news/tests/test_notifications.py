from datetime import date

from django.core import mail
from django.urls import reverse

from ..notifications import send_email_after_approval, send_email_news_needs_moderation


def test_send_email_after_approval(rf, tp, make_entry):
    entry = make_entry(approved=True, created_at=date(2023, 5, 31))
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


def test_send_email_news_needs_moderation(
    rf,
    tp,
    make_entry,
    make_user,
    moderator_user,
    superuser,
):
    other_moderator = make_user(groups={"moderator": ["news.*"]})
    entry = make_entry(approved=True)
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
        [other_moderator.email, moderator_user.email, superuser.email]
    )
