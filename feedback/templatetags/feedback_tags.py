from django import template

from feedback.models import IMAGE_MAX_BYTES, Feedback

register = template.Library()


@register.inclusion_tag("v3/includes/_feedback_widget.html", takes_context=True)
def feedback_widget(context):
    """Render the site-wide floating feedback widget.

    An inclusion tag rather than a plain include because the widget needs the
    type choices, which no page view supplies. `csrf_token` is forwarded so the
    widget's `{% csrf_token %}` still resolves inside the isolated tag context.
    """
    return {
        "request": context["request"],
        "csrf_token": context.get("csrf_token"),
        "feedback_type_options": Feedback.Type.choices,
        # Shared with the server-side validator so the widget can reject an
        # oversized file before spending the upload.
        "image_max_bytes": IMAGE_MAX_BYTES,
    }
