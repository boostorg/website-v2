from django.contrib.auth.password_validation import (
    CommonPasswordValidator as DjangoCommonPasswordValidator,
)
from django.utils.translation import gettext as _


class CommonPasswordValidator(DjangoCommonPasswordValidator):
    """Django's common-password validator with an actionable error message."""

    def get_error_message(self):
        return _("This password is too common. Please choose a different one.")
