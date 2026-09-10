"""Background page conversion work.

The command wrappers exist so the admin changelist buttons can start a long-running
command on a worker instead of holding the request open.
"""

import logging
from urllib.parse import urlsplit

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task
def convert_news_entries_task():
    """
    Run the `convert_news_entries` management command as a one-off request.

    Fundamentally idempotent, this command can be run several times without causing a problem
    so long as entries are still the source of truth (aka post launch)
    """
    call_command("convert_news_entries")


@shared_task
def update_index_task():
    """
    Run the `wagtail_update_index` management command as a one-off request.

    Needs to be run after the convert_news_entry task is run in order to ensure wagtail indexing
    is up to date for searching. Not `update_index`: haystack takes that name
    and its command is a no-op that exits successfully.
    """
    call_command("wagtail_update_index")


@shared_task
def send_post_published_email(page_id):
    """Tell a PostPage's author their post is live.

    Fired from pages.signals in response to Wagtail's `page_published` signal,
    which carries no request, so scheme/host come from the page's own
    absolute URL instead. Takes an id rather than the page itself since
    Celery arguments must serialize to JSON; the page is refetched fresh on
    the worker.
    """
    from pages.models import PostPage

    page = PostPage.objects.get(pk=page_id)
    action_url = page.get_full_url()
    parts = urlsplit(action_url)
    context = {
        "page": page,
        "action_url": action_url,
        "scheme": parts.scheme,
        "host": parts.netloc,
    }
    prefix = "v3/pages/email/post_published"
    msg = EmailMultiAlternatives(
        subject=render_to_string(f"{prefix}_subject.txt", context).strip(),
        body=render_to_string(f"{prefix}.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[page.author.email],
    )
    msg.attach_alternative(render_to_string(f"{prefix}.html", context), "text/html")
    msg.send(fail_silently=False)
