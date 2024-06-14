from django.db import models


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

    def version_dropdown(self):
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
        exclude_branches = True

        if include_beta:
            beta_queryset = self.active().filter(models.Q(name=most_recent_beta.name))
            queryset = (all_versions | beta_queryset).order_by("-name")
        else:
            queryset = all_versions.order_by("-name")

        if exclude_branches:
            queryset = queryset.exclude(name__in=["develop", "master", "head"])

        return queryset

    def version_dropdown_strict(self):
        """Returns the versions to be shown in the drop-down, but does not include
        the development branches"""
        versions = self.version_dropdown()
        # exclude if full_release is False and beta is False
        return versions.exclude(full_release=False, beta=False)


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
