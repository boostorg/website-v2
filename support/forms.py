from django import forms
from django.utils.translation import gettext_lazy as _


class ContactForm(forms.Form):

    TOPIC_CHOICES = (
        ("Sponsorship", "sponsorship"),
        ("Security", "security"),
        ("General", "general"),
    )

    first_name = forms.CharField(label=_("first name"), max_length=50)
    last_name = forms.CharField(label=_("last name"), max_length=50)
    email = forms.CharField(label=_("email"), max_length=150)
    message = forms.CharField(label=_("message"), widget=forms.Textarea)
    phone_number = forms.CharField(
        label=_("phone number"), max_length=30, required=False
    )
    topic = forms.ChoiceField(label="topic", required=False, choices=TOPIC_CHOICES)
