from django.db import models


class VersionQuerySet(models.QuerySet):
    def active(self):
        """Return active versions"""
        return self.filter(active=True)


class VersionManager(models.Manager):
    def get_queryset(self):
        return VersionQuerySet(self.model, using=self._db)

    def active(self):
        """Return active versions"""
        return self.get_queryset().active()


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
