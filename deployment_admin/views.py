from django.views.generic import TemplateView


# Create your views here.
class DeployAdminChecklistView(TemplateView):
    template_name = "deployment_admin/deployment_admin_checklist.html"
