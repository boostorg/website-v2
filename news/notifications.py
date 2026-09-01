from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse
from itsdangerous.url_safe import URLSafeTimedSerializer

from .acl import moderators
from .constants import NEWS_APPROVAL_SALT, MAGIC_LINK_EXPIRATION

User = get_user_model()


def _base_context(request):
    """Context every news notification email needs.

    scheme/host resolve the branded template's images and logo link;
    preferences_url drives the footer's opt-out sentence, which the base
    template omits when it is absent.
    """
    return {
        "scheme": request.scheme,
        "host": request.get_host(),
        "preferences_url": request.build_absolute_uri(reverse("profile-account")),
    }


def _render_message(name, context, to):
    subject = render_to_string(f"news/emails/{name}_subject.txt", context).strip()
    msg = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string(f"news/emails/{name}.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    msg.attach_alternative(
        render_to_string(f"news/emails/{name}.html", context), "text/html"
    )
    return msg


def send_email_news_approved(request, entry):
    if entry.tag not in entry.author.preferences.allow_notification_own_news_approved:
        return False

    context = {
        **_base_context(request),
        "entry": entry,
        "action_url": request.build_absolute_uri(entry.get_absolute_url()),
    }
    return _render_message("approved", context, [entry.author.email]).send()


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
        for u in moderators().select_related("preferences").only("email", "preferences")
        if entry.tag in u.preferences.allow_notification_others_news_needs_moderation
    ]
    if not recipient_list:
        return False

    context = {
        **_base_context(request),
        "entry": entry,
        "detail_url": request.build_absolute_uri(entry.get_absolute_url()),
        "moderate_url": request.build_absolute_uri(reverse("news-moderate")),
        "expiration_hours": int(MAGIC_LINK_EXPIRATION / 3600),
    }

    # Each moderator gets their own message: the approval link is minted per
    # moderator so an approval is attributable.
    messages = []
    for moderator in recipient_list:
        magic_link_url = generate_magic_approval_link(
            entry_slug=entry.slug, moderator_id=moderator.id
        )
        context["approval_magic_link"] = request.build_absolute_uri(magic_link_url)
        messages.append(_render_message("needs_moderation", context, [moderator.email]))
    get_connection().send_messages(messages)
    return len(messages)


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

    context = {
        **_base_context(request),
        "entry": entry,
        "action_url": request.build_absolute_uri(entry.get_absolute_url()),
    }
    messages = [
        _render_message("posted", context, [user_email])
        for user_email in recipient_list
    ]
    return get_connection().send_messages(messages)
