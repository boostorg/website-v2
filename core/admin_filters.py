from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


class StaffUserCreatedByFilter(admin.SimpleListFilter):
    title = "creator (staff only)"
    parameter_name = "created_by"

    def lookups(self, request, model_admin):
        staff_users = User.objects.filter(is_staff=True).order_by("display_name")
        return [(user.id, user.display_name or user.email) for user in staff_users]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(created_by=self.value())
        return queryset
