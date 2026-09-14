from django import template

from feedback.models import IMAGE_MAX_BYTES, MESSAGE_MAX_LENGTH, Feedback

register = template.Library()


@register.inclusion_tag("v3/includes/_feedback_widget.html", takes_context=True)
def feedback_widget(context):
    """Render the site-wide floating feedback widget.

    An inclusion tag rather than a plain include because the widget needs the
    type choices, which no page view supplies. No `csrf_token` is forwarded: a
    token in this markup would set a cookie on every page, so the widget fetches
    one only when somebody opens it.
    """
    return {
        "request": context["request"],
        "feedback_type_options": Feedback.Type.choices,
        # Shared with the server-side validator so the widget can reject an
        # oversized file before spending the upload.
        "image_max_bytes": IMAGE_MAX_BYTES,
        # Same limit the model enforces, so a long report is capped as it is typed
        # rather than rejected after the member has written it.
        "message_max_length": MESSAGE_MAX_LENGTH,
    }
