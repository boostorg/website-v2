from django.contrib import admin
from django.urls import path
from .views import DeployAdminChecklistView

# Register your models here.


class CustomDeploymentAdmin(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "deployment/",
                self.admin_view(DeployAdminChecklistView.as_view()),
            )
        ]
        return my_urls + urls
