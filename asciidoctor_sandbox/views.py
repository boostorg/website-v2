from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
import json

from core.asciidoc import convert_adoc_to_html


@staff_member_required
@require_POST
def admin_preview(request):
    """Preview asciidoc content for admin interface."""
    data = json.loads(request.body)
    rendered_content = convert_adoc_to_html(data.get("content", ""))
    rendered_html = f"<div class='preview-content'>{rendered_content}</div>"

    return JsonResponse({"success": True, "html": rendered_html})
