from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template import Template, Context
from django.urls import reverse

from .acl import moderators

User = get_user_model()


def send_email_after_approval(request, entry):
    if (
        entry.news_type
        not in entry.author.preferences.allow_notification_own_news_approved
    ):
        return False

    template = Template(
        'Congratulations! The news entry "{{ entry.title }}" that you submitted on '
        '{{ entry.created_at|date:"M jS, Y" }} was approved.\n'
        "You can view this news at {{ url }}.\n\n"
        "Thank you, the Boost moderator team."
    )
    body = template.render(
        Context(
            {
                "entry": entry,
                "url": request.build_absolute_uri(entry.get_absolute_url()),
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
        if entry.news_type
        in u.preferences.allow_notification_others_news_needs_moderation
    )
    if not recipient_list:
        return False

    template = Template(
        "Hello! You are receiving this email because you are a Boost news moderator.\n"
        "The user {{ user.get_display_name|default:user.email }} has submitted a "
        "new {{ newstype }} that requires moderation:\n\n"
        "{{ entry.title }}\n\n"
        "You can view, approve or delete this item at: {{ detail_url }}.\n\n"
        "The complete list of news pending moderation can be found at: {{ url }}\n\n"
        "Thank you, the Boost moderator team."
    )
    body = template.render(
        Context(
            {
                "entry": entry,
                "user": entry.author,
                "newstype": entry.__class__.__name__.lower(),
                "detail_url": request.build_absolute_uri(entry.get_absolute_url()),
                "url": request.build_absolute_uri(reverse("news-moderate")),
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
