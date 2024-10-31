from django.db import models
from django.db.models import Q, Count

from versions.models import Version


class IssueQuerySet(models.QuerySet):
    def closed_during_release(self, version):
        """Get the issues that were closed during a specific version.

        Uses the release dates of the version and the prior version and queries for
        issues closed in that timeframe.

        """
        prior_release = (
            Version.objects.minor_versions()
            .filter(release_date__lt=version.release_date)
            .order_by("-release_date")
            .first()
        )
        if not prior_release:
            return self.none()
        return self.filter(
            closed__gte=prior_release.release_date, closed__lt=version.release_date
        )

    def opened_during_release(self, version):
        """Get the issues that were created during a specific version release.

        Uses the release dates of the version and the prior version and queries for
        issues created in that timeframe.

        """
        prior_release = (
            Version.objects.minor_versions()
            .filter(release_date__lt=version.release_date)
            .order_by("-release_date")
            .first()
        )
        if not prior_release:
            return self.none()
        return self.filter(
            created__gte=prior_release.release_date, created__lt=version.release_date
        )


class IssueManager(models.Manager):
    def get_queryset(self):
        return IssueQuerySet(self.model, using=self._db)

    def closed_during_release(self, version):
        return self.get_queryset().closed_during_release(version)

    def opened_during_release(self, version):
        return self.get_queryset().opened_during_release(version)

    def count_opened_closed_during_release(self, version):
        qs = self.get_queryset()
        prior_release = (
            Version.objects.minor_versions()
            .filter(release_date__lt=version.release_date)
            .order_by("-release_date")
            .first()
        )
        if not prior_release:
            return qs.none()
        return qs.values("library_id").annotate(
            opened=Count(
                "id",
                filter=Q(
                    created__gte=prior_release.release_date,
                    created__lt=version.release_date,
                ),
            ),
            closed=Count(
                "id",
                filter=Q(
                    closed__gte=prior_release.release_date,
                    closed__lt=version.release_date,
                ),
            ),
        )
