from django.db import models
from django.db.models import Sum, F


class EmailDataQuerySet(models.QuerySet):
    def with_total_counts(self):
        """Annotate total post count per author."""
        return self.annotate(
            name=F("author__name"),
            avatar_url=F("author__avatar_url"),
            github_profile_url=F("author__avatar_url"),
            total_count=Sum("count"),
        )


class EmailDataManager(models.Manager):
    def get_queryset(self):
        return EmailDataQuerySet(self.model, using=self._db)

    def with_total_counts(self):
        return self.get_queryset().with_total_counts()
