from typing import NamedTuple

from django.db import models
from django.db.models import Func, Value, Count, Q
from django.db.models.functions import Replace
from django.contrib.postgres.fields import ArrayField

from libraries.constants import (
    MASTER_RELEASE_URL_PATH_STR,
    DEVELOP_RELEASE_URL_PATH_STR,
)


class HeaderVersionData(NamedTuple):
    """Consolidated data needed to render the navbar version dropdown."""

    options: list
    most_recent: "Version | None"  # noqa: F821
    most_recent_beta: "Version | None"  # noqa: F821


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
        return VersionQuerySet(self.model, using=self._db).filter(fully_imported=True)

    def with_partials(self):
        """Return all objects regardless of fully_imported status"""
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

    def get_dropdown_versions(
        self,
        *,
        allow_develop: bool = False,
        allow_master: bool = False,
        flag_versions_without_library: "Library" = None,  # noqa: F821
        order_by: str = "-name",
    ):
        """
        Returns the versions to be shown in the drop-down, basics:
        * does not include the development branches
        * includes the most recent beta if it is newer than the most recent full release
        * doesn't return versions where full_release=False and beta=False

        Args:
            allow_develop (bool): allow the develop branch version to show in result
            allow_master (bool): allow the master branch version to show in the result
            order_by (str): the field to order by
            flag_versions_without_library (Library): flag the version when it doesn't
                have the matching library - e.g. used for library detail page
        """
        all_versions = self.active().filter(beta=False)
        most_recent_beta = self.most_recent_beta()

        def should_show_beta(most_recent_beta):
            """
            Returns bool for whether to show beta version in dropdown. Returns True only
            when the most recent beta version is newer than the most recent full release
            """
            most_recent = self.most_recent()
            if not most_recent_beta or most_recent is None:
                return False

            return (
                most_recent_beta.cleaned_version_parts
                > most_recent.cleaned_version_parts
            )

        queryset = all_versions
        include_beta = should_show_beta(most_recent_beta)
        if include_beta:
            beta_queryset = self.active().filter(models.Q(name=most_recent_beta.name))
            queryset = queryset | beta_queryset

        # beta=False here is not redundant, it only applies to the exclusion while a
        # beta is allowed for most_recent_beta
        flag_exclusions = Q(full_release=False, beta=False)
        name_exclusions = [
            "head",
            MASTER_RELEASE_URL_PATH_STR,
            DEVELOP_RELEASE_URL_PATH_STR,
        ]
        if allow_master:
            flag_exclusions = flag_exclusions & ~Q(name="master")
            name_exclusions.remove(MASTER_RELEASE_URL_PATH_STR)
        if allow_develop:
            flag_exclusions = flag_exclusions & ~Q(name="develop")
            name_exclusions.remove(DEVELOP_RELEASE_URL_PATH_STR)

        queryset = (
            queryset.exclude(name__in=name_exclusions)
            .exclude(flag_exclusions)
            .defer("data")
        )

        if flag_versions_without_library:
            # Annotate each version with a flag `has_library` indicating if it has the
            # provided library version or not
            queryset = queryset.annotate(
                has_library=Count(
                    "library_version",
                    filter=models.Q(
                        library_version__library=flag_versions_without_library
                    ),
                )
            )

        return queryset.order_by(order_by)

    def get_header_dropdown_data(self) -> HeaderVersionData:
        """Single-query fetch for the navbar version dropdown.

        Replaces the 3-4 queries from calling `most_recent()`,
        `most_recent_beta()`, and `get_dropdown_versions()` separately. Dropdown
        list matches `get_dropdown_versions()` for the header's use case only —
        no develop/master, no library filtering.
        """
        name_exclusions = [
            "head",
            MASTER_RELEASE_URL_PATH_STR,
            DEVELOP_RELEASE_URL_PATH_STR,
        ]
        versions = list(
            self.active()
            .filter(Q(full_release=True) | Q(beta=True))
            .exclude(name__in=name_exclusions)
            .defer("data")
            .order_by("-name")
        )

        most_recent = next((v for v in versions if not v.beta and v.full_release), None)
        most_recent_beta = next((v for v in versions if v.beta), None)

        include_beta = (
            most_recent_beta is not None
            and most_recent is not None
            and most_recent_beta.cleaned_version_parts
            > most_recent.cleaned_version_parts
        )
        if include_beta:
            options = [
                v for v in versions if not v.beta or v.name == most_recent_beta.name
            ]
        else:
            options = [v for v in versions if not v.beta]

        return HeaderVersionData(
            options=options,
            most_recent=most_recent,
            most_recent_beta=most_recent_beta,
        )


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
