from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _


User = get_user_model()


class EntryManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(
                approved=models.Q(moderator__isnull=False, approved_at__lte=now())
            )
            .annotate(published=models.Q(publish_at__lte=now(), approved=True))
        )


class Entry(models.Model):
    """A news entry.

    Please note that this is a concrete class with its own DB table. Children
    of this class have their own table with their own attributes, plus a 1-1
    relationship with their parent.

    """

    class AlreadyApprovedError(Exception):
        """The entry cannot be approved again."""

    slug = models.SlugField()
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
    external_url = models.URLField(_("URL"), blank=True, default="")
    image = models.ImageField(upload_to="news/%Y/%m/", null=True, blank=True)
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

    # XXX: These may need moving to an ACL-dedicated module? (nessita)

    def can_view(self, user):
        return (
            self.is_published
            or user == self.author
            or (user is not None and user.has_perm("news.view_entry"))
        )

    @classmethod
    def can_approve(cls, user):
        return user is not None and user.has_perm("news.change_entry")

    def can_edit(self, user):
        return (not self.is_approved and user == self.author) or (
            user is not None and user.has_perm("news.change_entry")
        )

    def can_delete(self, user):
        return user is not None and user.has_perm("news.delete_entry")

    def author_needs_moderation(self):
        # Every author's news should be moderated except for moderators or
        # explicitely allowlisted users.
        return not (
            self.can_approve(self.author)
            or self.author.email in settings.NEWS_MODERATION_ALLOWLIST
            or self.author.pk in settings.NEWS_MODERATION_ALLOWLIST
        )


class BlogPost(Entry):
    abstract = models.CharField(max_length=256)
    # Possible extra fields: RSS feed? banner? keywords? tags?


class Link(Entry):
    pass


class Video(Entry):
    pass
    # Possible extra fields: length? quality?


class Poll(Entry):
    pass
    # Possible extra fields: voting expiration date?


class PollChoice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    wording = models.CharField(max_length=200)
    order = models.PositiveIntegerField()
    votes = models.ManyToManyField(User)
