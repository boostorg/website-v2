from django.contrib import admin

from reports.models import WebsiteStatReport, WebsiteStatItem


class StatInline(admin.StackedInline):
    model = WebsiteStatItem
    extra = 0
    fields = ("value",)
    readonly_fields = fields
    can_delete = False


@admin.register(WebsiteStatReport)
class WebsiteStatReportAdmin(admin.ModelAdmin):
    inlines = (StatInline,)
    list_display = ("version", "pageviews", "unique_visitors", "period")
    ordering = ("-version",)

    # def get_queryset(self, request):
    #     qs = super().get_queryset(request)
    #     return qs.prefetch_related("stats")

    def pageviews(self, obj):
        return f"{int(obj.stats.get(code_name='pageviews').value):,}"

    def unique_visitors(self, obj):
        return f"{int(obj.stats.get(code_name='visitors').value):,}"


@admin.register(WebsiteStatItem)
class WebsiteStatItemAdmin(admin.ModelAdmin): ...
