"""Signal wiring for `pages`. Imported from `PagesConfig.ready()`."""

import threading

from django.db import transaction
from django.dispatch import receiver
from wagtail.signals import page_published, workflow_approved

from pages.models import PostPage
from pages.notifications import record_published_post
from pages.tasks import send_post_published_email

# Wagtail's `WorkflowState.finish()` publishes the revision (firing
# `page_published`) *before* sending `workflow_approved`, both inside the same
# atomic block. This thread-local lets the `workflow_approved` handler below
# tell the deferred `page_published` handler "this exact publish was that
# same approval", even though it fires second, so the two never race across
# unrelated requests on other threads.
_local = threading.local()


@receiver(page_published, sender=PostPage, dispatch_uid="post_notification_published")
def raise_post_notification(sender, instance, **kwargs):
    """Light up the Posts nav dot and email the author once a post goes live.

    Wagtail fires `page_published` for every publish, including edits to a post
    that is already live, and also for a scheduled publish that has not reached
    its go-live time. Only the first publication of a live page counts: Wagtail
    stamps `first_published_at` and `last_published_at` with the same timestamp
    on that publish and only moves the latter afterwards.

    Wagtail's own workflow-approved notice (branded, see
    templates/wagtailadmin/notifications/workflow_state_approved.html)
    already tells the author moderation cleared; this is the separate "you're
    live" notice for when the page actually goes live, which isn't always the
    same moment -- a workflow can finish without auto-publishing the page. When
    it *is* the same moment (the common single-task workflow, which auto-
    publishes on approval), sending both is two emails for one click, so the
    `workflow_approved` handler below flags that case and this skips its send.
    """
    if not instance.live:
        return
    if instance.first_published_at != instance.last_published_at:
        return

    record_published_post(instance.pk)

    author = instance.author
    if not (author and author.email):
        return

    page_id = instance.pk

    def _send_unless_just_approved():
        if page_id in getattr(_local, "approved_page_ids", ()):
            _local.approved_page_ids.discard(page_id)
            return
        send_post_published_email.delay(page_id)

    transaction.on_commit(_send_unless_just_approved)


@receiver(
    workflow_approved, dispatch_uid="post_notification_skip_duplicate_on_auto_publish"
)
def flag_post_as_just_approved(sender, instance, **kwargs):
    """Mark a `PostPage` so the handler above skips its own "you're live"
    email when the page auto-published as a direct result of this same
    approval, per the docstring above.

    Approving a workflow is not the same as the page going live: a `PostPage`
    with a future `go_live_at` still gets `workflow_approved` here, but stays
    unpublished (Wagtail's `PublishPageRevisionAction` fires `page_published`
    unconditionally, and the handler above returns before registering an
    `on_commit` send for a page that isn't live yet). Left unattended, that
    flag would leak past this transaction and could wrongly suppress the real
    "you're live" email once the scheduled go-live actually publishes the
    page later, on its own, unrelated transaction. So this always schedules
    its own cleanup, whether or not the flag ends up consumed above.
    """
    page = instance.content_object
    if not isinstance(page, PostPage):
        page = getattr(page, "specific", None)
    if not isinstance(page, PostPage):
        return

    if not hasattr(_local, "approved_page_ids"):
        _local.approved_page_ids = set()
    _local.approved_page_ids.add(page.pk)

    page_id = page.pk
    transaction.on_commit(lambda: _local.approved_page_ids.discard(page_id))
