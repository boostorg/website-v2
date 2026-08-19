from pathlib import Path

from structlog import get_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, ExpressionWrapper, FloatField, F, Func, Value, When
from django.db.models.functions import Greatest, Now, Power
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.log_actions import log

from core.validators import (
    attachment_validator,
    image_validator,
    large_file_max_size_validator,
    downscale_image_file_size_validator,
)

from . import acl
from .constants import (
    AI_DESCRIPTION_LIMIT_CHANGED_ACTION,
    BYPASS_DESCRIPTION_LIMIT_PERMISSION,
    CONTENT_SUMMARIZATION_THRESHOLD,
    DAILY_LIMIT_MIN_MESSAGE,
    RATELIMIT_EXEMPT_GROUP,
)
from .panels import AIDescriptionUsagePanel
from .tasks import summary_dispatcher
from .tasks import set_thumbnail_for_video_entry

User = get_user_model()
logger = get_logger(__name__)

# Single source of truth for the `category` label shown on V3 post cards.
# Used by `Entry.to_v3_post_card_dict()`; tags not listed here fall back
# to title-case (so "news"/"link"/"video"/"poll" render as themselves).
POST_CARD_TAG_LABELS = {"blogpost": "Blog"}


class ExtractEpoch(Func):
    function = "EXTRACT"
    template = "%(function)s(EPOCH FROM %(expressions)s)"
    output_field = FloatField()


class EntryManager(models.Manager):
    def get_queryset(self):
        result = (
            super()
            .get_queryset()
            .annotate(
                approved=models.Q(moderator__isnull=False, approved_at__lte=now())
            )
            .annotate(published=models.Q(publish_at__lte=now(), approved=True))
        )
        if self.model == Entry:
            result = result.annotate(
                _tag=Case(
                    When(
                        blogpost__entry_ptr__isnull=False,
                        then=Value(BlogPost.news_type),
                    ),
                    When(link__entry_ptr__isnull=False, then=Value(Link.news_type)),
                    When(news__entry_ptr__isnull=False, then=Value(News.news_type)),
                    When(poll__entry_ptr__isnull=False, then=Value(Poll.news_type)),
                    When(video__entry_ptr__isnull=False, then=Value(Video.news_type)),
                    default=Value(""),
                )
            )
        return result

    def published(self):
        return self.get_queryset().filter(published=True)

    def ranked(self):
        gravity = float(getattr(settings, "POSTS_RANKING_GRAVITY", 2.0))
        age_in_hours = ExpressionWrapper(
            Greatest(ExtractEpoch(Now() - F("publish_at")), Value(0.0)) / Value(3600.0),
            output_field=FloatField(),
        )
        score = ExpressionWrapper(
            F("page_views") / Power(age_in_hours + Value(2.0), Value(gravity)),
            output_field=FloatField(),
        )
        return (
            self.get_queryset().annotate(ranking_score=score).order_by("-ranking_score")
        )


class Entry(models.Model):
    """A news entry.

    Please note that this is a concrete class with its own DB table. Children
    of this class have their own table with their own attributes, plus a 1-1
    relationship with their parent.

    """

    class AlreadyApprovedError(Exception):
        """The entry cannot be approved again."""

    news_type = ""
    slug = models.SlugField(unique=True, max_length=300)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default="")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    moderator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_entries_set",
    )
    external_url = models.URLField(_("URL"), blank=True, default="", max_length=500)
    image = models.ImageField(
        upload_to="news/%Y/%m/",
        null=True,
        blank=True,
        validators=[image_validator, downscale_image_file_size_validator],
    )
    created_at = models.DateTimeField(default=now)
    approved_at = models.DateTimeField(null=True, blank=True)
    modified_at = models.DateTimeField(auto_now=True)
    publish_at = models.DateTimeField(default=now)
    summary = models.TextField(
        blank=True, default="", help_text="AI generated summary. Delete to regenerate."
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_entries",
    )
    page_views = models.PositiveIntegerField(default=0)

    objects = EntryManager()

    class Meta:
        verbose_name_plural = "Entries"

    def __str__(self):
        # avoid printing author information that cause extra queries
        return f"{self.title}"

    # do not cache since it compares against now()
    @property
    def is_approved(self):
        return (
            self.moderator is not None
            and self.approved_at is not None
            and self.approved_at <= now()
        )

    # do not cache since it compares against now()
    @property
    def is_published(self):
        return self.is_approved and self.publish_at <= now()

    @property
    def video_thumbnail(self):
        try:
            result = self.video.thumbnail
        except Video.DoesNotExist:
            result = None
        return result

    @property
    def image_url(self):
        if not self.image:
            return ""
        else:
            return self.image.url

    @property
    def needs_approval(self):
        return not self.approved_at and not self.deleted_at

    @cached_property
    def tag(self):
        return getattr(self, "_tag", self.news_type)

    @cached_property
    def is_blogpost(self):
        try:
            result = self.blogpost is not None
        except BlogPost.DoesNotExist:
            result = False
        return result

    @cached_property
    def is_link(self):
        try:
            result = self.link is not None
        except Link.DoesNotExist:
            result = False
        return result

    @cached_property
    def is_news(self):
        try:
            result = self.news is not None
        except News.DoesNotExist:
            result = False
        return result

    @cached_property
    def is_poll(self):
        try:
            result = self.poll is not None
        except Poll.DoesNotExist:
            result = False
        return result

    @cached_property
    def is_video(self):
        try:
            result = self.video is not None
        except Video.DoesNotExist:
            result = False
        return result

    @cached_property
    def determined_news_type(self):
        if self.is_blogpost:
            return "blogpost"
        elif self.is_link:
            return "link"
        elif self.is_news:
            return "news"
        elif self.is_poll:
            return "poll"
        elif self.is_video:
            return "video"
        else:
            return None

    def approve(self, user, commit=True):
        """Mark this entry as approved by the given `user`."""
        if self.is_approved:
            raise self.AlreadyApprovedError()
        self.moderator = user
        self.approved_at = now()
        if commit:
            self.save(update_fields=["moderator", "approved_at", "modified_at"])

    def get_content(self):
        return self.content

    @cached_property
    def use_summary(self):
        return self.summary and (
            not self.content or len(self.content) > CONTENT_SUMMARIZATION_THRESHOLD
        )

    @cached_property
    def visible_content(self):
        if self.use_summary:
            return self.summary
        return self.content

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        result = super().save(*args, **kwargs)

        if not self.summary:
            logger.info(f"Passing {self.pk=} to dispatcher")
            summary_dispatcher.delay(self.pk)

        return result

    def get_absolute_url(self):
        return reverse("news-detail", args=[self.slug])

    def to_v3_post_card_dict(self):
        """Dict shape consumed by `v3/includes/_post_card.html` items."""
        category = ""

        if self.tag:
            tag_key = str(self.tag).lower()
            category = POST_CARD_TAG_LABELS.get(tag_key, self.tag.capitalize())

        return {
            "title": self.title,
            "url": self.get_absolute_url(),
            "date": self.publish_at,
            "category": category,
            "tag": "",
            "author": self.author.to_v3_profile_dict(),
        }

    def can_view(self, user):
        return acl.can_view(user, self)

    @classmethod
    def can_approve(cls, user):
        return acl.can_approve(user)

    def can_edit(self, user):
        return acl.can_edit(user, self)

    def can_delete(self, user):
        return acl.can_delete(user, self)

    def author_needs_moderation(self):
        return acl.author_needs_moderation(self)

    def edit_url(self):
        return reverse("news-update", kwargs={"slug": self.slug})

    def delete_url(self):
        return reverse("news-delete", kwargs={"slug": self.slug})


class News(Entry):
    news_type = "news"
    attachment = models.FileField(
        upload_to="news/files/%Y/%m/",
        null=True,
        blank=True,
        validators=[large_file_max_size_validator, attachment_validator],
    )

    @property
    def attachment_filename(self):
        return Path(self.attachment.name).name

    class Meta:
        verbose_name = "News"
        verbose_name_plural = "News Items"


class BlogPost(Entry):
    news_type = "blogpost"
    abstract = models.CharField(max_length=256)
    # Possible extra fields: RSS feed? banner? keywords? tags?


class Link(Entry):
    news_type = "link"


class Video(Entry):
    news_type = "video"
    thumbnail = models.ForeignKey(
        "wagtailimages.Image",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    # Possible extra fields: length? quality?

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        if not self.thumbnail:
            logger.info(f"Getting thumbnail for {self.title}")
            set_thumbnail_for_video_entry.delay(self.pk)
        return result


class Poll(Entry):
    news_type = "poll"
    # Possible extra fields: voting expiration date?


class PollChoice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    wording = models.CharField(max_length=200)
    order = models.PositiveIntegerField()
    votes = models.ManyToManyField(User)


NEWS_MODELS = [BlogPost, Link, News, Poll, Video]


class DescriptionInputType(models.TextChoices):
    """Which generator produced an attempt: the post body, or a linked page."""

    CONTENT = "content", _("Content")
    LINK = "link", _("Link")


class DescriptionGenerationOutcome(models.TextChoices):
    """How a generation attempt ended."""

    # Reserved before the model call, so a row that never leaves this state is
    # a request that died mid-flight. Pending still consumes quota: the call
    # was made and billed even if we never saw the answer.
    PENDING = "pending", _("Pending")
    SUCCESS = "success", _("Success")
    RATE_LIMITED = "rate_limited", _("Rate limited")
    UPSTREAM_ERROR = "upstream_error", _("Upstream error")


class DescriptionGenerationAttempt(models.Model):
    """One AI description generation attempt, successful or not.

    Doubles as the daily counter behind `AIDescriptionSettings.daily_limit`, so
    the number an admin sees and the number the limit enforces can never drift
    apart. Rows are cheap: the cap keeps them to a couple of dozen per user
    per day.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="description_generation_attempts",
    )
    input_type = models.CharField(max_length=16, choices=DescriptionInputType)
    input_size = models.PositiveIntegerField(
        help_text=(
            "Characters of text sent to the model. For a link this is the "
            "extracted article body, not the URL."
        )
    )
    outcome = models.CharField(max_length=16, choices=DescriptionGenerationOutcome)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["user", "created_at"])]
        permissions = [
            (
                BYPASS_DESCRIPTION_LIMIT_PERMISSION,
                "Can bypass the AI description daily limit",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} {self.input_type} {self.outcome} {self.created_at}"


class AIDescriptionSettingsForm(WagtailAdminModelForm):
    """Validates the limit and records who changed it, from what, to what.

    Wagtail's settings edit view logs a bare `wagtail.edit` entry with no field
    values, and registers no history UI for settings, so the old -> new pair is
    logged here under a dedicated action the usage panel can read back.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Captured before validation binds cleaned data onto `self.instance`,
        # which would otherwise overwrite the value we want to report.
        self._original_daily_limit = (
            self.instance.daily_limit if self.instance.pk else None
        )
        # `PositiveIntegerField.formfield()` hands the form a minimum of 0 and
        # does not carry the model's `MinValueValidator(1)` across, so a
        # negative value would be refused in Django's default wording while 0
        # got ours. Rebuild the field at the real minimum so every value below
        # one reads the same and the widget stops at 1 too.
        self.fields["daily_limit"] = self.instance._meta.get_field(
            "daily_limit"
        ).formfield(
            min_value=1,
            error_messages={"min_value": DAILY_LIMIT_MIN_MESSAGE},
        )

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        if self._original_daily_limit != instance.daily_limit:
            log(
                instance=instance,
                action=AI_DESCRIPTION_LIMIT_CHANGED_ACTION,
                user=self.for_user,
                data={
                    "daily_limit": {
                        "old": self._original_daily_limit,
                        "new": instance.daily_limit,
                    }
                },
            )
        return instance


@register_setting
class AIDescriptionSettings(BaseGenericSetting):
    """Admin-managed cap on AI description generation, set in the Wagtail admin.

    Lives in the CMS beside the posts it governs. Read per request via
    `load(request_or_site=request)`, which caches on the request only, so an
    edit applies from the next request with no deploy or restart.
    """

    base_form_class = AIDescriptionSettingsForm

    # The default is the cap in force wherever nobody has edited the setting
    # yet, so it is a real starting value rather than a placeholder - but it is
    # read only when the settings row is first created, and editing the screen
    # is what changes it after that.
    daily_limit = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(1)],
        help_text=(
            "Maximum AI description generations per user per day. Resets at "
            "midnight UTC. Applies to both the content and link generators. "
            "Superusers and members of the "
            f"'{RATELIMIT_EXEMPT_GROUP}' group are exempt."
        ),
    )

    panels = ["daily_limit", AIDescriptionUsagePanel()]

    class Meta:
        verbose_name = "AI Description Settings"
