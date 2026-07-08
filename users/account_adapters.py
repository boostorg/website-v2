# Custom Account adapter for all auth to customize error messages
# https://codeberg.org/allauth/django-allauth/src/branch/main/allauth/account/adapter.py

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


from allauth.account.adapter import DefaultAccountAdapter


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
