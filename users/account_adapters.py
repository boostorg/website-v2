# Custom Account adapter for all auth to customize error messages
# https://codeberg.org/allauth/django-allauth/src/branch/main/allauth/account/adapter.py

from datetime import timedelta
from urllib.parse import quote, urlsplit

from allauth.account.adapter import DefaultAccountAdapter
from allauth.utils import build_absolute_uri
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from waffle import flag_is_active

from users.utils import humanize_link_lifetime


class AccountAdapter(DefaultAccountAdapter):
    error_messages = {
        "account_inactive": _("This account is currently inactive."),
        "cannot_remove_primary_email": _(
            "You cannot remove your primary email address."
        ),
        "duplicate_email": _(
            "This email address is already associated with this account."
        ),
        "email_password_mismatch": _(
            "The email and/or password you entered does not match our records."
        ),
        "phone_password_mismatch": _(
            "The phone number and/or password you specified are not correct."
        ),
        "email_taken": _("A user is already registered with this email address."),
        "enter_current_password": _("Please type your current password."),
        "incorrect_code": _("Incorrect code."),
        "incorrect_password": _("Incorrect password."),
        "invalid_or_expired_key": _("Invalid or expired key."),
        "invalid_login": _("Invalid login."),
        "invalid_password_reset": _("The password reset token was invalid."),
        "max_email_addresses": _("You cannot add more than %d email addresses."),
        "phone_taken": _("A user is already registered with this phone number."),
        "too_many_login_attempts": _(
            "Too many failed login attempts. Try again later."
        ),
        "unknown_email": _("The email address is not assigned to any user account."),
        "unknown_phone": _("The phone number is not assigned to any user account."),
        "unverified_primary_email": _("Your primary email address must be verified."),
        "username_blacklisted": _(
            "Username can not be used. Please use other username."
        ),
        "username_password_mismatch": _(
            "The username and/or password you specified are not correct."
        ),
        "username_taken": AbstractUser._meta.get_field("username").error_messages[
            "unique"
        ],
        "select_only_one": _("Please select only one."),
        "same_as_current": _("The new value must be different from the current one."),
        "rate_limited": _("Be patient, you are sending too many requests."),
    }

    # Messages that are suppressed in V3: the page the user lands on already says it. Legacy keeps them.
    V3_SUPPRESSED_MESSAGES = {
        "account/messages/logged_in.txt",
        "account/messages/logged_out.txt",
        "account/messages/email_confirmation_sent.txt",
    }

    def add_message(self, request, level, message_template=None, *args, **kwargs):
        # The passed request, not self.request, which is unset outside a request.
        if message_template in self.V3_SUPPRESSED_MESSAGES and flag_is_active(
            request, "v3"
        ):
            return
        return super().add_message(request, level, message_template, *args, **kwargs)

    def _v3_active(self):
        # Emails can be sent outside a request (e.g. a management command or
        # Celery task), in which case there's no request to read the flag from.
        return self.request is not None and flag_is_active(self.request, "v3")

    def save_user(self, request, user, form, commit=True):
        """Store the signup form's username as the user's display name.

        allauth only copies fields it knows about, and it has no notion of
        display_name, so the signup page's Username box needs writing
        by hand.

        Set before the first save, so the routing key minted when the
        row is created carries the chosen name rather than a placeholder.
        """
        user = super().save_user(request, user, form, commit=False)
        display_name = form.cleaned_data.get("display_name")
        if display_name:
            user.display_name = display_name
        if commit:
            user.save()
        return user

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
                    self.request, reverse("account_signup")
                )
            context.setdefault("action_url", context.get("signup_url"))
        super().send_mail(template_prefix, email, context)

    def send_password_reset_mail(self, user, email, context):
        context.update(
            {
                "first_name": getattr(user, "first_name", ""),
                "user_email": email,
                "action_url": context["password_reset_url"],
                "password_reset_link_lifetime": humanize_link_lifetime(
                    timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT)
                ),
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
