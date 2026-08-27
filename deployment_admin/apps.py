from django.contrib.admin.apps import AdminConfig


class CustomDeploymentAdminConfig(AdminConfig):
    default_site = "deployment_admin.admin.CustomDeploymentAdmin"
