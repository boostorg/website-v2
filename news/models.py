from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.timezone import now


User = get_user_model()


class Entry(models.Model):
    """A news entry.

    Please note that this is a concrete class with its own DB table. Children
    of this class have their own table with their own attributes, plus a 1-1
    relationship with their parent.

    """

    slug = models.SlugField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    external_url = models.URLField(blank=True, default="")
    image = models.ImageField(upload_to="news", null=True, blank=True)
    created_at = models.DateTimeField(default=now)
    publish_at = models.DateTimeField(default=now)

    class Meta:
        verbose_name_plural = "Entries"

    def __str__(self):
        return f"{self.title} by {self.author}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)

    @property
    def published(self):
        return self.publish_at <= now()

    def get_absolute_url(self):
        return reverse("news-detail", args=[self.slug])


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
