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
