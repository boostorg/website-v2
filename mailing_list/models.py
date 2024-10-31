from django.db import models

from mailing_list.managers import EmailDataManager


class EmailData(models.Model):
    author = models.ForeignKey("libraries.CommitAuthor", on_delete=models.CASCADE)
    version = models.ForeignKey("versions.Version", on_delete=models.CASCADE)
    count = models.IntegerField()

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
