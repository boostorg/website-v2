"""News app.

The goal is to be able to have several different types of News items that can
be displayed differently on the site (likely on /news/)

The types are:

    video
    blog post
    news / announcement
    link
    poll

We will have a posting form/interface on the site for logged in users (likely
restricted to a certain Group, but that can be done in a later ticket) so the
Django admin won't be the primary UI for people on this FYI.

There are really two ways to model this. One News model that has all of the
various fields (and related model for poll questions/votes) or we build a
separate model for each type and aggregate them only on the display view. I
think we want to do the later.

Each will need these fields:

    title
    optional description
    publish datetime (date the news goes live, defaults to now)
    author FK

Then video obviously needs a video URL, probably a key frame image.

Polls will need a M2M on questions and who voted. Only logged in users will
vote.

"""

from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.timezone import now


User = get_user_model()


class News(models.Model):
    slug = models.SlugField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    external_url = models.URLField(blank=True, default="")
    image = models.ImageField(upload_to='news')
    created = models.DateTimeField(default=now)
    published = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.title} by {self.author}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)

    def is_published(self):
        return self.published <= now()

    def get_absolute_url(self):
        return reverse("news-detail", args=[self.slug])


class BlogPost(News):
    body = models.TextField()
    abstract = models.CharField(max_length=256)
    # Possible extra fields: RSS feed? banner? keywords?


class Link(News):
    pass


class Video(News):
    pass
    # Possible extra fields: length? quality?


class Poll(News):
    pass
    # Possible extra fields: voting expiration date?


class PollChoice(models.Model):
    question = models.ForeignKey(Poll, on_delete=models.CASCADE)
    wording = models.CharField(max_length=200)
    order = models.PositiveIntegerField()
    votes = models.ManyToManyField(User)
