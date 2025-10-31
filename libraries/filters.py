from django.contrib import admin

from versions.models import ReportConfiguration


class ReportConfigurationFilter(admin.SimpleListFilter):
    title = "report configuration"
    parameter_name = "report_configuration"

    def lookups(self, request, model_admin):
        # get only ReportConfigurations that have associated ReleaseReports
        configs = (
            ReportConfiguration.objects.filter(releasereport__isnull=False)
            .distinct()
            .order_by("version")
        )
        return [(config.id, str(config)) for config in configs]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(report_configuration_id=self.value())
        return queryset
