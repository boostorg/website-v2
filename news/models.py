from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.timezone import now


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
    description = models.TextField(blank=True, default="")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    moderator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_entries_set",
    )
    external_url = models.URLField(blank=True, default="")
    image = models.ImageField(upload_to="news", null=True, blank=True)
    created_at = models.DateTimeField(default=now)
    approved_at = models.DateTimeField(null=True, blank=True)
    modified_at = models.DateTimeField(auto_now=True)
    publish_at = models.DateTimeField(default=now)

    objects = EntryManager()

    class Meta:
        verbose_name_plural = "Entries"

    def __str__(self):
        return f"{self.title} by {self.author}"

    @property
    def is_approved(self):
        return (
            self.moderator is not None
            and self.approved_at is not None
            and self.approved_at <= now()
        )

    @property
    def is_published(self):
        return self.is_approved and self.publish_at <= now()

    def approve(self, user):
        """Mark this entry as approved by the given `user`."""
        if self.is_approved:
            raise self.AlreadyApprovedError()
        self.moderator = user
        self.approved_at = now()
        self.save(update_fields=["moderator", "approved_at"])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news-detail", args=[self.slug])

    def can_view(self, user):
        return (
            self.is_published
            or user == self.author
            or (user is not None and user.has_perm("news.view_entry"))
        )

    def can_edit(self, user):
        return (not self.is_approved and user == self.author) or (
            user is not None and user.has_perm("news.change_entry")
        )

    def can_delete(self, user):
        return user is not None and user.has_perm("news.delete_entry")


class BlogPost(Entry):
    body = models.TextField()
    abstract = models.CharField(max_length=256)
    # Possible extra fields: RSS feed? banner? keywords?


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
