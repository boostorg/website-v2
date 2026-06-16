from urllib.parse import quote, urlsplit

from allauth.account.adapter import DefaultAccountAdapter
from allauth.utils import build_absolute_uri
from django.urls import reverse
from waffle import flag_is_active


class AccountAdapter(DefaultAccountAdapter):
    """Send allauth's transactional emails with the branded templates.

    The canonical branded templates live in ``templates/emails/`` (shared
    with the ``send_test_emails`` preview command); thin wrappers in
    ``templates/account/email/`` map them to the names allauth renders.
    This adapter supplies the extra context those templates expect.
    """

    def _v3_active(self):
        # Emails can be sent outside a request (e.g. a management command or
        # Celery task), in which case there's no request to read the flag from.
        return self.request is not None and flag_is_active(self.request, "v3")

    def send_mail(self, template_prefix, email, context):
        # The branded base template (emails/base_email.html) builds absolute
        # links from scheme/host.
        parts = urlsplit(build_absolute_uri(self.request, "/"))
        context.setdefault("scheme", parts.scheme)
        context.setdefault("host", parts.netloc)
        if template_prefix == "account/email/unknown_account":
            # Sent when a password reset is requested for an address with no
            # account; the call site only provides a signup URL, so point the
            # email's CTA at it.
            if self._v3_active():
                context["signup_url"] = build_absolute_uri(
                    self.request, reverse("v3-signup")
                )
            context.setdefault("action_url", context.get("signup_url"))
        super().send_mail(template_prefix, email, context)

    def send_password_reset_mail(self, user, email, context):
        context.update(
            {
                "first_name": getattr(user, "first_name", ""),
                "user_email": email,
                "action_url": context["password_reset_url"],
            }
        )
        return super().send_password_reset_mail(user, email, context)

    def get_reset_password_from_key_url(self, key):
        """Point the emailed reset link at the V3 flow when the flag is on."""
        if self._v3_active():
            path = reverse(
                "v3-password-reset-from-key", kwargs={"uidb36": "UID", "key": "KEY"}
            ).replace("UID-KEY", quote(key))
            return build_absolute_uri(self.request, path)
        return super().get_reset_password_from_key_url(key)
