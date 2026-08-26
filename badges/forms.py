"""Forms for the badges admin."""

from django import forms
from django.utils.translation import gettext_lazy as _


class NotesActionForm(forms.Form):
    """Intermediate form for admin actions that require an audit note.

    Used by the ``UserAchievement`` invalidation and ``UserBadge`` revocation
    actions, both of which require a non-empty note explaining the change.
    """

    notes = forms.CharField(
        label=_("Notes"),
        widget=forms.Textarea(attrs={"rows": 4, "cols": 60}),
        required=True,
        strip=True,
        help_text=_("Required. Explain why this action is being taken."),
    )
