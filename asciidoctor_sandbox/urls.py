from django.urls import path
from . import views

app_name = "asciidoctor_sandbox"

urlpatterns = [
    path("admin-preview/", views.admin_preview, name="admin_preview"),
]
