from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import (
    EmailMessage,
    get_connection,
    send_mail,
    EmailMultiAlternatives,
)
from django.template import Template, Context
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe
from itsdangerous.url_safe import URLSafeTimedSerializer

from .acl import moderators

User = get_user_model()
NEWS_APPROVAL_SALT = "news-approval"


def send_email_news_approved(request, entry):
    if entry.tag not in entry.author.preferences.allow_notification_own_news_approved:
        return False

    template = Template(
        'Congratulations! The news entry "{{ title }}" that you submitted on '
        '{{ entry.created_at|date:"M jS, Y" }} was approved.\n'
        "You can view this news at {{ url }}.\n\n"
        "Thank you, the Boost moderator team."
    )
    body = template.render(
        Context(
            {
                "entry": entry,
                "url": request.build_absolute_uri(entry.get_absolute_url()),
                "title": mark_safe(entry.title),  # Mark the title as safe
            }
        )
    )
    subject = "Boost.org: News entry approved"
    return send_mail(
        subject=subject,
        message=body,
        from_email=None,
        recipient_list=[entry.author.email],
    )


def generate_magic_approval_link(entry_slug: str, moderator_id: int):
    """Generate a magic link token for approving a news entry."""
    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    token = serializer.dumps(
        {"entry_slug": entry_slug, "moderator_id": moderator_id},
        salt=NEWS_APPROVAL_SALT,
    )
    url = reverse("news-magic-approve", args=[token])
    return url


def send_email_news_needs_moderation(request, entry):
    recipient_list = [
        u
        for u in moderators().select_related("preferences").only("email")
        if entry.tag in u.preferences.allow_notification_others_news_needs_moderation
    ]
    if not recipient_list:
        return False

    context = {
        "entry": entry,
        "detail_url": request.build_absolute_uri(entry.get_absolute_url()),
        "moderate_url": request.build_absolute_uri(reverse("news-moderate")),
    }

    subject = "Boost.org: News entry needs moderation"
    from_address = settings.DEFAULT_FROM_EMAIL
    # Send each recipient their own email
    messages = []
    for moderator in recipient_list:
        magic_link_url = generate_magic_approval_link(
            entry_slug=entry.slug, moderator_id=moderator.id
        )
        context["approval_magic_link"] = request.build_absolute_uri(magic_link_url)
        text_body = render_to_string("news/emails/needs_moderation.txt", context)
        html_body = render_to_string("news/emails/needs_moderation.html", context)
        msg = EmailMultiAlternatives(
            subject, text_body, from_address, [moderator.email]
        )
        msg.attach_alternative(html_body, "text/html")
        messages.append(msg)
    get_connection().send_messages(messages)


def send_email_news_posted(request, entry):
    # Filter all users that have preferences such as they allow notifications
    # for when other users have their news entry posted.
    recipient_list = sorted(
        u.email
        for u in User.objects.allow_notification_others_news_posted(entry.tag).only(
            "email"
        )
    )
    if not recipient_list:
        return False

    template = Template(
        "Hello! A news entry was just posted:\n\n"
        "{{ title }}\n\n"
        "You can view this news at: {{ detail_url }}.\n\n"
        "If you no longer wish to receive these emails, please review your "
        "notifications preferences at {{ preferences_url }}.\n\n"
        "Thank you, the Boost news team."
    )
    body = template.render(
        Context(
            {
                "entry": entry,
                "detail_url": request.build_absolute_uri(entry.get_absolute_url()),
                "preferences_url": request.build_absolute_uri(
                    reverse("profile-account")
                ),
                "title": mark_safe(entry.title),
            }
        )
    )
    subject = "Boost.org: News entry posted"
    messages = [
        EmailMessage(
            subject=subject,
            body=body,
            from_email=None,
            to=[user_email],
        )
        for user_email in recipient_list
    ]
    return get_connection().send_messages(messages)
