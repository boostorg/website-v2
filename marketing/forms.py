from django import forms

from .models import CapturedEmail


class CapturedEmailForm(forms.ModelForm):
    class Meta:
        model = CapturedEmail
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "your@email.com",
                    "autocomplete": "email",
                }
            )
        }
