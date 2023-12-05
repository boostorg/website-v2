from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, send_mail
from django.template import Template, Context
from django.urls import reverse
from django.utils.safestring import mark_safe

from .acl import moderators

User = get_user_model()


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


def send_email_news_needs_moderation(request, entry):
    recipient_list = sorted(
        u.email
        for u in moderators().select_related("preferences").only("email")
        if entry.tag in u.preferences.allow_notification_others_news_needs_moderation
    )
    if not recipient_list:
        return False

    template = Template(
        "Hello! You are receiving this email because you are a Boost news moderator.\n"
        "The user {{ user.get_display_name|default:user.email }} has submitted a "
        "new {{ newstype }} that requires moderation:\n\n"
        "{{ title }}\n\n"
        "You can view, approve or delete this item at: {{ detail_url }}.\n\n"
        "The complete list of news pending moderation can be found at: {{ url }}\n\n"
        "Thank you, the Boost moderator team."
    )

    body = template.render(
        Context(
            {
                "entry": entry,
                "user": entry.author,
                "newstype": entry.tag,
                "detail_url": mark_safe(
                    request.build_absolute_uri(entry.get_absolute_url())
                ),
                "url": mark_safe(request.build_absolute_uri(reverse("news-moderate"))),
                "title": mark_safe(entry.title),
            }
        )
    )

    subject = "Boost.org: News entry needs moderation"
    return send_mail(
        subject=subject,
        message=body,
        from_email=None,
        recipient_list=recipient_list,
    )


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
    return EmailMessage(
        subject=subject,
        body=body,
        from_email=None,
        bcc=recipient_list,
    ).send()
