"""Beta feedback captured from the site-wide floating widget."""

from pathlib import Path
from uuid import uuid4

from django import forms
from django.conf import settings
from django.db import models
from django.utils import timezone

from core.validators import MaxFileSizeValidator, image_validator

MESSAGE_MAX_LENGTH = 4000
USER_AGENT_MAX_LENGTH = 400
PAGE_URL_MAX_LENGTH = 1000

IMAGE_MAX_BYTES = 2 * 1024 * 1024
feedback_image_size_validator = MaxFileSizeValidator(max_size=IMAGE_MAX_BYTES)


def feedback_image_path(instance, filename):
    """Give every screenshot its own name.

    Media storage runs with `file_overwrite = True`, so keeping the submitted
    filename would let two members who both upload `image.png` in the same month
    clobber each other, leaving one report showing the other's screenshot. The
    extension is preserved because the validators already restrict it to PNG/JPEG.
    """
    return (
        f"feedback/{timezone.now():%Y/%m}/{uuid4().hex}{Path(filename).suffix.lower()}"
    )


class Feedback(models.Model):
    class Type(models.TextChoices):
        BUG = "bug", "Bug"
        SUGGESTION = "suggestion", "Suggestion"
        QUESTION = "question", "Question"
        USABILITY = "usability", "Usability"
        INCORRECT_INFORMATION = "incorrect_information", "Incorrect information"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NEW = "new", "New"
        TRIAGED = "triaged", "Triaged"
        ACTIONED = "actioned", "Actioned"
        WONT_FIX = "wont_fix", "Won't fix"

    class Source(models.TextChoices):
        WIDGET = "widget", "Widget"
        PAGE = "page", "Feedback page"
        PAGE_NO_JS = "page_no_js", "Feedback page (no JS)"

    feedback_type = models.CharField(
        max_length=30, choices=Type.choices, default=Type.OTHER
    )
    message = models.TextField(max_length=MESSAGE_MAX_LENGTH)
    image = models.ImageField(
        upload_to=feedback_image_path,
        null=True,
        blank=True,
        validators=[image_validator, feedback_image_size_validator],
        help_text="Optional screenshot showing the problem.",
    )
    # Set on every submission; only goes null if the account is later deleted.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="feedback",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    # CharField, not URLField: URLValidator rejects single-label internal hosts.
    # The view enforces an http(s) scheme, which is what makes this safe to link.
    page_url = models.CharField(max_length=PAGE_URL_MAX_LENGTH, blank=True, default="")
    # Derived server-side from page_url so reports group by route, not by URL string.
    url_name = models.CharField(max_length=100, blank=True, default="")
    boost_version = models.CharField(max_length=100, blank=True, default="")
    user_agent = models.CharField(
        max_length=USER_AGENT_MAX_LENGTH, blank=True, default=""
    )
    # Browser-only context: viewport, device, search query, console/network errors.
    diagnostics = models.JSONField(blank=True, default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    # Derived server-side, so it records which form was actually used rather than
    # what the client claims. Tells us whether the no-JS fallback is being exercised.
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.WIDGET
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "feedback"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(message=""),
                name="feedback_requires_message",
            ),
        ]

    def __str__(self):
        return f"{self.get_feedback_type_display()} from {self.submitter}"

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.pk}): {self}>"

    @property
    def submitter(self):
        return str(self.user) if self.user else "(deleted account)"


class FeedbackForm(forms.ModelForm):
    # Declared explicitly so the model's fallback default is not offered as a
    # pre-selected answer — submitters pick a type deliberately.
    feedback_type = forms.ChoiceField(choices=Feedback.Type.choices)

    class Meta:
        model = Feedback
        fields = ["feedback_type", "message", "image"]
