from django.contrib.auth import get_user_model
from django.db import models

from mailing_list.managers import EmailDataManager


class EmailData(models.Model):
    author = models.ForeignKey("libraries.CommitAuthor", on_delete=models.CASCADE)
    version = models.ForeignKey("versions.Version", on_delete=models.CASCADE)
    count = models.IntegerField()

    @property
    def display_name(self):
        if (
            self.author.user
            and self.author.user.is_commit_author_name_overridden
            and self.author.user.display_name
        ):
            return self.author.user.display_name

    @property
    def user(self):
        User = get_user_model()
        return User.get_user_by_github_url(self.author.github_profile_url)

    objects = EmailDataManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["author", "version"],
                name="%(app_label)s_%(class)s_author_version_unique",
            ),
        ]

    def __str__(self):
        return self.author.name


class PostingData(models.Model):
    name = models.CharField(max_length=255)
    post_time = models.DateTimeField()

    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} {self.post_time}"


class SubscriptionData(models.Model):
    subscription_dt = models.DateTimeField()
    email = models.EmailField(max_length=255)
    entry_type = models.CharField(max_length=24)
    list = models.CharField(max_length=24)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["subscription_dt", "email", "list"]
