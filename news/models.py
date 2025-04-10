from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Case, Value, When
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from core.validators import (
    attachment_validator,
    image_validator,
    max_file_size_validator,
    large_file_max_size_validator,
)

from . import acl

User = get_user_model()


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
        validators=[image_validator, max_file_size_validator],
    )
    created_at = models.DateTimeField(default=now)
    approved_at = models.DateTimeField(null=True, blank=True)
    modified_at = models.DateTimeField(auto_now=True)
    publish_at = models.DateTimeField(default=now)

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

    def approve(self, user, commit=True):
        """Mark this entry as approved by the given `user`."""
        if self.is_approved:
            raise self.AlreadyApprovedError()
        self.moderator = user
        self.approved_at = now()
        if commit:
            self.save(update_fields=["moderator", "approved_at", "modified_at"])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news-detail", args=[self.slug])

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
    # Possible extra fields: length? quality?


class Poll(Entry):
    news_type = "poll"
    # Possible extra fields: voting expiration date?


class PollChoice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    wording = models.CharField(max_length=200)
    order = models.PositiveIntegerField()
    votes = models.ManyToManyField(User)


NEWS_MODELS = [BlogPost, Link, News, Poll, Video]
