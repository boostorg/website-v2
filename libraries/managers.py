from datetime import date

from django.db import models
from django.db.models import Q, Count

from libraries.bots import is_bot_name


class CommitAuthorQuerySet(models.QuerySet):
    def exclude_bots(self):
        return self.exclude(is_bot=True)

    def bulk_create(self, objs, *args, **kwargs):
        # Mirror CommitAuthor.save()'s auto-flag, which bulk_create bypasses.
        for obj in objs:
            if not obj.is_bot and is_bot_name(obj.name):
                obj.is_bot = True
        return super().bulk_create(objs, *args, **kwargs)


CommitAuthorManager = models.Manager.from_queryset(CommitAuthorQuerySet)


class HumanCommitAuthorManager(CommitAuthorManager):
    def get_queryset(self):
        return super().get_queryset().exclude_bots()


class IssueQuerySet(models.QuerySet):
    def closed_during_release(self, version, prior_version):
        """Get the issues that were closed during a specific version.

        Uses the release dates of the version and the prior version and queries for
        issues closed in that timeframe.

        """
        release_date = version.release_date
        if version.name == "master":
            release_date = date.today()
        return self.filter(
            closed__gte=prior_version.release_date, closed__lt=release_date
        )

    def opened_during_release(self, version, prior_version):
        """Get the issues that were created during a specific version release.

        Uses the release dates of the version and the prior version and queries for
        issues created in that timeframe.

        """
        release_date = version.release_date
        if version.name == "master":
            release_date = date.today()
        return self.filter(
            created__gte=prior_version.release_date, created__lt=release_date
        )


class IssueManager(models.Manager):
    def get_queryset(self):
        return IssueQuerySet(self.model, using=self._db)

    def closed_during_release(self, version, prior_version):
        return self.get_queryset().closed_during_release(version, prior_version)

    def opened_during_release(self, version, prior_version):
        return self.get_queryset().opened_during_release(version, prior_version)

    def count_opened_closed_during_release(self, version, prior_version):
        if version is None:
            return self.get_queryset().none()
        qs = self.get_queryset()
        release_date = version.release_date
        if version.name == "master":
            release_date = date.today()
        return qs.values("library_id").annotate(
            opened=Count(
                "id",
                filter=Q(
                    created__gte=prior_version.release_date,
                    created__lt=release_date,
                ),
            ),
            closed=Count(
                "id",
                filter=Q(
                    closed__gte=prior_version.release_date,
                    closed__lt=release_date,
                ),
            ),
        )
