from django.db import models
from django.db.models import Func, Value
from django.db.models.functions import Replace
from django.contrib.postgres.fields import ArrayField


class VersionQuerySet(models.QuerySet):
    def active(self):
        """Return active versions"""
        return self.filter(active=True)

    def most_recent(self):
        """Return most recent active non-beta version"""
        return (
            self.active()
            .filter(beta=False, full_release=True)
            .order_by("-name")
            .first()
        )

    def most_recent_beta(self):
        """Return most recent active beta version.

        Note: There should only ever be one beta version in the database, as
        old ones are generally deleted. But just in case."""
        return self.active().filter(beta=True).order_by("-name").first()

    def with_version_split(self):
        """Separates name into an array of [major, minor, patch].

        Anything not matching the regex is removed from the queryset.

        Example:
            name = boost-1.85.0
            version_array -> [1, 85, 0]
            major -> 1
            minor -> 85
            patch -> 0

        """
        return self.filter(name__regex=r"^(boost-)?\d+\.\d+\.\d+$").annotate(
            simple_version=Replace("name", Value("boost-"), Value("")),
            version_array=Func(
                "simple_version",
                Value(r"\."),
                function="regexp_split_to_array",
                template="(%(function)s(%(expressions)s)::int[])",
                arity=2,
                output_field=ArrayField(models.IntegerField()),
            ),
            major=models.F("version_array__0"),
            minor=models.F("version_array__1"),
            patch=models.F("version_array__2"),
        )


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

    def minor_versions(self):
        """Filters for versions with patch = 0

        Beta versions are removed.

        """
        return self.get_queryset().with_version_split().filter(patch=0)

    def version_dropdown(self, exclude_branches=True):
        """Return the versions that should show in the version drop-down"""
        all_versions = self.active().filter(beta=False)
        most_recent = self.most_recent()
        most_recent_beta = self.most_recent_beta()

        def should_show_beta(most_recent, most_recent_beta):
            """Returns bool for whether to show beta version in dropdown"""
            if not most_recent_beta or most_recent is None:
                return False

            return (
                most_recent_beta.cleaned_version_parts
                > most_recent.cleaned_version_parts
            )

        include_beta = should_show_beta(most_recent, most_recent_beta)

        if include_beta:
            beta_queryset = self.active().filter(models.Q(name=most_recent_beta.name))
            queryset = all_versions | beta_queryset
        else:
            queryset = all_versions

        if exclude_branches:
            queryset = queryset.exclude(name__in=["develop", "master", "head"])

        return queryset.order_by("-name")

    def version_dropdown_strict(self, *, exclude_branches=True):
        """Returns the versions to be shown in the drop-down, but does not include
        the development branches"""
        versions = self.version_dropdown(exclude_branches=exclude_branches)
        # exclude if full_release is False and beta is False
        versions = versions.exclude(full_release=False, beta=False)

        return versions


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
