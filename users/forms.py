import os

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django import forms

from allauth.account.forms import ResetPasswordKeyForm

from .models import Preferences
from news.models import NEWS_MODELS
from news.acl import can_approve

User = get_user_model()

NEWS_ENTRY_CHOICES = [(m.news_type, m._meta.verbose_name.title()) for m in NEWS_MODELS]


class CustomResetPasswordFromKeyForm(ResetPasswordKeyForm):
    def save(self, **kwargs):
        """Override default reset password form so we can mark unclaimed
        users as claimed once they have reset their passwords."""
        result = super().save(**kwargs)
        self.user.claim()
        return result


class PreferencesForm(forms.ModelForm):
    allow_notification_own_news_approved = forms.MultipleChoiceField(
        choices=NEWS_ENTRY_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="Your own news is approved after moderation",
        required=False,
    )
    allow_notification_others_news_posted = forms.MultipleChoiceField(
        choices=NEWS_ENTRY_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="Other users publish their news",
        required=False,
    )
    allow_notification_others_news_needs_moderation = forms.MultipleChoiceField(
        choices=NEWS_ENTRY_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="There are new entries pending moderation",
        required=False,
    )
    allow_notification_terms_changed = forms.BooleanField(
        label="The site's Terms of Use or Privacy Policy are changed",
        required=False,
    )

    def __init__(self, *args, instance=None, **kwargs):
        if instance is not None:
            is_moderator = can_approve(instance.user)
            initial = kwargs.pop("initial", {})
            for field in self.Meta.fields:
                initial[field] = getattr(instance, field)
            kwargs["initial"] = initial
        else:
            is_moderator = False
            all_news = Preferences.ALL_NEWS_TYPES
            kwargs["initial"] = {i: all_news for i in self.Meta.fields}
            # Use default for terms changed field
            kwargs["initial"][
                "allow_notification_terms_changed"
            ] = Preferences().allow_notification_terms_changed

        super().__init__(*args, instance=instance, **kwargs)

        if not is_moderator:
            self.fields.pop("allow_notification_others_news_needs_moderation")
            self.initial.pop("allow_notification_others_news_needs_moderation")

    def save(self, *args, **kwargs):
        for field, value in self.cleaned_data.items():
            setattr(self.instance, field, value)
        return super().save(*args, **kwargs)

    class Meta:
        model = Preferences
        fields = [
            "allow_notification_own_news_approved",
            "allow_notification_others_news_posted",
            "allow_notification_others_news_needs_moderation",
            "allow_notification_terms_changed",
        ]


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "email",
            "display_name",
            "indicate_last_login_method",
            "is_commit_author_name_overridden",
        ]
        labels = {
            "display_name": "Username",
            "is_commit_author_name_overridden": "Override commit author name",
        }
        override_msg = (
            "Globally replaces your git commit author name with Username "
            "value set above."
        )
        help_texts = {
            "display_name": "Your name as it will be displayed across the site.",
            "is_commit_author_name_overridden": override_msg,
        }


class CustomClearableFileInput(forms.ClearableFileInput):
    """
    Overrides the template for clearable file input so that we can display
    the widget without the filename/path displayed and change the checkbox
    to clear the field.
    """

    template_name = "users/clearable_file_input.html"


class UserProfilePhotoForm(forms.ModelForm):
    profile_image = forms.FileField(widget=CustomClearableFileInput, required=False)

    class Meta:
        model = User
        fields = ["profile_image"]

    def clean(self):
        """Ensure a user can't update their photo if they
        don't have permission."""
        cleaned_data = super().clean()
        if not self.instance.can_update_image:
            raise forms.ValidationError(
                "You do not have permission to update your profile photo."
            )
        return cleaned_data

    def save(self, commit=True):
        old_image = self.instance.profile_image
        old_image_name = old_image.name if old_image else None
        new_image_data = self.cleaned_data.get("profile_image")
        has_new_upload = isinstance(new_image_data, UploadedFile)

        # Save the new image
        user = super().save(commit=False)
        if not old_image:
            # reset image on image delete checked
            user.image_uploaded = False
        elif has_new_upload and old_image_name:
            # Delete the old file directly from storage (not via FieldFile.delete(),
            # which closes file handles and interferes with the pending upload)
            old_image.storage.delete(old_image_name)

        if has_new_upload:
            _, file_extension = os.path.splitext(new_image_data.name)
            file_extension = file_extension.lstrip(".")
            new_image_data.name = f"{user.profile_image_filename_root}.{file_extension}"
            user.profile_image = new_image_data
            user.image_uploaded = True

        if commit:
            user.save()

        # Invalidate the cached thumbnail so ImageKit regenerates it
        if has_new_upload:
            user.delete_cached_thumbnail()

        return user


class DeleteAccountForm(forms.Form):
    verify = forms.CharField(help_text='To verify, type "delete my account" above.')

    def clean_verify(self):
        verify = self.cleaned_data["verify"]
        if self.cleaned_data["verify"] != "delete my account":
            raise forms.ValidationError('Please enter "delete my account"')
        return verify


class UserBioForm(forms.Form):
    bio = forms.CharField(max_length=4096, required=False)
    one_line_bio = forms.CharField(max_length=80, required=False)
    github_profile = forms.CharField(max_length=80, required=False)
    website = forms.CharField(max_length=80, required=False)
    email = forms.CharField(max_length=80, required=False)
    slack = forms.CharField(max_length=80, required=False)
    role = forms.ChoiceField()


class V3ProfileLinkChoices(models.TextChoices):
    GITHUB = "github"
    WEBSITE = "website"
    EMAIL = "email"
    SLACK = "slack"


class V3ProfileLinkForm(forms.Form):
    type = forms.ChoiceField(
        choices=V3ProfileLinkChoices.choices, disabled=True, label=""
    )
    value = forms.CharField(max_length=80, label="")


V3ProfileLinkFormset = forms.formset_factory(V3ProfileLinkForm, extra=0)


class V3CommitEmailForm(forms.Form):
    email = forms.EmailField(max_length=80)


V3CommitEmailFormSet = forms.formset_factory(V3CommitEmailForm, extra=0)


class V3UserProfileForm(forms.Form):
    # Left Column Fields
    tagline = forms.CharField(
        max_length=70,
        help_text="This tagline is displayed next to your avatar on your profile & across the site",
        widget=forms.TextInput(attrs={"placeholder": "Placeholder"}),
    )
    bio = forms.CharField(
        max_length=4000,
        help_text="This text field supports Markdown and this content is what will appear on your public profile",
        widget=forms.Textarea(),
    )
    link_formset = V3ProfileLinkFormset(
        initial=[{"type": x, "value": ""} for x in V3ProfileLinkChoices.values],
    )
    role = forms.ChoiceField(
        choices=[(0, "C++ Alliance Board Member")], label="Your Role"
    )
    select_title = forms.ChoiceField(
        choices=[],
        disabled=True,
        widget=forms.Select(attrs={"placeholder": "Unlock a badge to pick a title"}),
    )
    hide_github = forms.BooleanField(
        label="Hide GitHub activity from your profile",
        help_text="Links your login to an existing commit-author email after verification",
    )
    hide_ml = forms.BooleanField(
        label="Hide mailing list activity from your profile",
        help_text="Links your login to an existing commit-author email after verification",
    )
    hide_ach = forms.BooleanField(
        label="Hide achievements & badges from your profile",
        help_text="Links your login to an existing commit-author email after verification",
    )

    # Top Right Column
    username = forms.CharField(
        max_length=80, widget=forms.TextInput(attrs={"placeholder": "Placeholder"})
    )
    email = forms.EmailField(
        max_length=80, widget=forms.TextInput(attrs={"placeholder": "Placeholder"})
    )
    country = forms.ChoiceField(choices=[])
    indicate_last_login_method = forms.BooleanField(
        help_text="The login page will indicate the last method you used to login"
    )
    override_commit_author_name = forms.BooleanField(
        help_text="Globally replaces your git commit author name with username value set above"
    )
    ovverride_commit_author_email = forms.BooleanField(
        help_text="Links your login to an existing commit-author email after verification"
    )

    # Commit Emails
    commit_email_formset = V3CommitEmailFormSet(
        initial=[
            {
                "email": "abc@example.com",
            },
        ],
    )

    # Email Alerts
    allow_notification_own_news_approved = forms.MultipleChoiceField(
        choices=NEWS_ENTRY_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="Your own news is approved after moderation",
        required=False,
    )
    allow_notification_others_news_posted = forms.MultipleChoiceField(
        choices=NEWS_ENTRY_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="Other users publish their news",
        required=False,
    )
    allow_notification_terms_updated = forms.BooleanField(
        label="The sites terms of use or privacy policy are changed"
    )
