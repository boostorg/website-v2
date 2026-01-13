from django.contrib import admin


class FilterByReleaseDates(admin.SimpleListFilter):
    """Filter slack activity by Boost version release periods.

    The release date is considered the END of the development period for that version.
    Messages are attributed to the version they were leading up to, not the one just released.
    """

    title = "release"
    parameter_name = "release"

    def lookups(self, request, model_admin):
        from versions.models import Version

        versions = Version.objects.filter(
            release_date__isnull=False, active=True, full_release=True
        ).order_by("-release_date")[:20]

        # Add special entries for ongoing development
        choices = [
            ("master", "master (after latest release)"),
            ("develop", "develop (after latest release)"),
        ]

        # Add version entries
        choices.extend([(v.id, f"{v.name} ({v.release_date})") for v in versions])

        return choices

    def queryset(self, request, queryset):
        if self.value() in ("master", "develop"):
            # Get messages after the latest release
            from versions.models import Version

            latest_version = (
                Version.objects.filter(
                    release_date__isnull=False, active=True, full_release=True
                )
                .order_by("-release_date")
                .first()
            )

            if latest_version and latest_version.release_date:
                return queryset.filter(day__gt=latest_version.release_date)

        elif self.value():
            from versions.models import Version

            try:
                version = Version.objects.get(id=self.value())
                if version.release_date:
                    # Get the previous version's release date (this is the start of the period)
                    previous_version = (
                        Version.objects.filter(
                            release_date__lt=version.release_date,
                            active=True,
                            full_release=True,
                        )
                        .order_by("-release_date")
                        .first()
                    )

                    if previous_version and previous_version.release_date:
                        # Filter messages between previous release and current release
                        return queryset.filter(
                            day__gt=previous_version.release_date,
                            day__lte=version.release_date,
                        )
                    else:
                        # No previous version, so filter up to this release
                        return queryset.filter(day__lte=version.release_date)
            except Version.DoesNotExist:
                pass
        return queryset
