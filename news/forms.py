from django import forms
from .models import Entry


class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ["title", "description"]

    def save(self, *args, commit=True, **kwargs):
        instance = super().save(*args, commit=False, **kwargs)
        # Automatically approve unapproved news that do not require moderation
        if not instance.is_approved and not instance.author_needs_moderation():
            instance.approve(user=instance.author, commit=False)
        if commit:
            instance.save()
        return instance
