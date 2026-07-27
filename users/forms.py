import os

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django import forms

from allauth.account.forms import ResetPasswordKeyForm, SignupForm
from django_countries import countries

from .models import Preferences
from news.models import NEWS_MODELS
from news.acl import can_approve

User = get_user_model()

NEWS_ENTRY_CHOICES = [(m.news_type, m._meta.verbose_name.title()) for m in NEWS_MODELS]

# Email preference content types shown on the v3 edit-profile page. A subset of
# NEWS_ENTRY_CHOICES/ALL_NEWS_TYPES matching the Figma design (no Poll checkbox).
V3_EMAIL_PREFERENCE_CHOICES = [
    ("blogpost", "Blog posts"),
    ("link", "Links"),
    ("news", "News"),
    ("video", "Video"),
]


class CustomResetPasswordFromKeyForm(ResetPasswordKeyForm):
    def save(self, **kwargs):
        """Override default reset password form so we can mark unclaimed
        users as claimed once they have reset their passwords."""
        result = super().save(**kwargs)
        self.user.claim()
        return result


class CustomSignUpForm(SignupForm):
    accept_terms_of_use = forms.BooleanField(required=True)
    username = forms.CharField(max_length=255, required=True)

    def clean_email(self):
        email = super().clean_email()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists!")
        return email


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


class V3ProfileLinkChoices(models.TextChoices):
    GITHUB = ("github", "GitHub")
    WEBSITE = "website"
    EMAIL = "email"
    SLACK = "slack"


# Slack links persist as the public profile URL from the CPPLang Slack
# workspace (kept in sync with the frontend construction in
# user_profile_edit.html) — the same link produced by "Copy link to profile"
# in a user's Slack profile within the CPPLang workspace.
SLACK_PROFILE_URL_PREFIX = "https://cpplang.slack.com/team/"


class V3ProfileLinkForm(forms.Form):
    type = forms.ChoiceField(
        choices=V3ProfileLinkChoices.choices, disabled=True, label=""
    )
    value = forms.CharField(max_length=200, label="")


V3ProfileLinkFormset = forms.formset_factory(V3ProfileLinkForm, extra=0)


class V3CommitEmailForm(forms.Form):
    email = forms.EmailField(
        max_length=80, widget=forms.EmailInput(attrs={"placeholder": "abc@example.com"})
    )


V3CommitEmailFormSet = forms.formset_factory(V3CommitEmailForm, extra=0)


class V3UserProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        links = kwargs.pop("user_links", None)
        commit_emails = kwargs.pop("commit_emails", None)
        self._user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["country"].choices = [("", "No country")] + list(countries)
        if links:
            self.link_formset = V3ProfileLinkFormset(
                initial=[
                    {"type": x, "value": links.get(x, "")}
                    for x in V3ProfileLinkChoices.values
                ],
            )
        if commit_emails:
            self.commit_email_formset = V3CommitEmailFormSet(
                initial=[
                    {
                        "email": x,
                    }
                    for x in commit_emails
                ],
            )

        for form in self.link_formset:
            placeholder = ""
            field_value = form["type"].value()
            if field_value == V3ProfileLinkChoices.GITHUB:
                placeholder = "https://"
            elif field_value == V3ProfileLinkChoices.WEBSITE:
                placeholder = "https://"
            elif field_value == V3ProfileLinkChoices.EMAIL:
                placeholder = "example@example.com"
            elif field_value == V3ProfileLinkChoices.SLACK:
                placeholder = "CPPLang profile URL"
            form.fields["value"].widget.attrs["placeholder"] = placeholder

    def clean_username(self):
        username = self.cleaned_data["username"]
        if not username:
            return username
        existing = User.objects.filter(display_name__iexact=username)
        if self._user is not None:
            existing = existing.exclude(pk=self._user.pk)
        if existing.exists():
            raise forms.ValidationError("This username is already taken")
        return username

    # Left Column Fields
    tagline = forms.CharField(
        max_length=User.TAGLINE_MAX_LENGTH,
        widget=forms.TextInput(
            attrs={"placeholder": "Placeholder", "display_max_chars": True}
        ),
    )
    bio = forms.CharField(
        max_length=User.BIOGRAPHY_MAX_LENGTH,
        help_text="This text field supports Markdown and this content is what will appear on your public profile",
        widget=forms.Textarea(),
    )
    link_formset = V3ProfileLinkFormset(
        initial=[{"type": x, "value": ""} for x in V3ProfileLinkChoices.values],
    )
    avatar = forms.ImageField(required=False)
    delete_avatar = forms.BooleanField(required=False)

    role = forms.ChoiceField(
        choices=[(0, "C++ Alliance Board Member")], label="Your Role"
    )
    select_title = forms.ChoiceField(
        choices=[],
        disabled=True,
        widget=forms.Select(attrs={"placeholder": "Unlock a badge to pick a title"}),
        label="Select Title",
    )
    hide_github = forms.BooleanField(
        label="Hide your GitHub activity from your profile",
        required=False,
    )
    hide_ml = forms.BooleanField(
        label="Hide your mailing list activity from your profile",
        required=False,
    )
    hide_ach = forms.BooleanField(
        label="Hide badges on your profile",
        required=False,
    )

    # Top Right Column
    username = forms.CharField(
        max_length=80, widget=forms.TextInput(attrs={"placeholder": "Placeholder"})
    )
    email = forms.EmailField(
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": "Placeholder"}),
        disabled=True,
    )
    country = forms.ChoiceField(choices=[], required=False)
    indicate_last_login_method = forms.BooleanField(
        help_text="The login page will indicate the last method you used to login",
        required=False,
    )
    override_commit_author_name = forms.BooleanField(
        help_text="Globally replaces your git commit author name with username value set above",
        required=False,
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
        choices=V3_EMAIL_PREFERENCE_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="Your own news is approved after moderation",
        required=False,
    )
    allow_notification_others_news_posted = forms.MultipleChoiceField(
        choices=V3_EMAIL_PREFERENCE_CHOICES,
        widget=forms.widgets.CheckboxSelectMultiple,
        label="Other users publish their news",
        required=False,
    )
