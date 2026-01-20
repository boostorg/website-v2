from django.contrib import admin

from slack.filters import FilterByReleaseDates
from slack.models import Channel, SlackActivityBucket


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "last_update_ts_readable"]
    search_fields = ["name", "id"]
    readonly_fields = ["id", "name", "topic", "purpose", "last_update_ts"]
    ordering = ["name"]

    @admin.display(description="Last Update")
    def last_update_ts_readable(self, obj):
        """Display last_update_ts in a human-readable format."""
        if obj.last_update_ts:
            from slack.models import parse_ts

            return parse_ts(obj.last_update_ts).strftime("%Y-%m-%d %H:%M:%S UTC")
        return "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SlackActivityBucket)
class SlackActivityBucketAdmin(admin.ModelAdmin):
    list_display = ["day", "channel_name", "user_name", "count"]
    search_fields = ["channel__name", "user__name", "user__real_name"]
    list_filter = ["day", "channel__name", FilterByReleaseDates]
    readonly_fields = ["day", "user", "channel", "count"]
    raw_id_fields = ["user", "channel"]
    date_hierarchy = "day"
    ordering = ["-day"]

    @admin.display(
        description="Channel",
        ordering="channel__name",
    )
    def channel_name(self, obj):
        """Display channel name instead of Channel object."""
        return obj.channel.name if obj.channel else "-"

    @admin.display(
        description="User",
        ordering="user__name",
    )
    def user_name(self, obj):
        """Display user name instead of SlackUser object."""
        return obj.user.real_name or obj.user.name if obj.user else "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
