from django.db import models


class VersionQuerySet(models.QuerySet):
    def active(self):
        """Return active versions"""
        return self.filter(active=True)

    def most_recent(self):
        """Return most recent active non-beta version"""
        return self.active().filter(beta=False).order_by("-name").first()

    def most_recent_beta(self):
        """Return most recent active beta version.

        Note: There should only ever be one beta version in the database, as
        old ones are generally deleted. But just in case."""
        return self.active().filter(beta=True).order_by("-name").first()


class VersionManager(models.Manager):
    def get_queryset(self):
        return VersionQuerySet(self.model, using=self._db)

    def active(self):
        """Return active versions"""
        return self.get_queryset().active()

    def most_recent(self):
        """Return most recent active non-beta version"""
        return self.get_queryset().most_recent()

    def most_recent_beta(self):
        """Return most recent active beta version"""
        return self.get_queryset().most_recent_beta()


class VersionFileQuerySet(models.QuerySet):
    def active(self):
        """Return files for active versions"""
        return self.filter(version__active=True)


class VersionFileManager(models.Manager):
    def get_queryset(self):
        return VersionFileQuerySet(self.model, using=self._db)

    def active(self):
        """Return files active versions"""
        return self.get_queryset().active()
