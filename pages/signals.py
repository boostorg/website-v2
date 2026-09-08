"""Signal wiring for `pages`. Imported from `PagesConfig.ready()`."""

from django.dispatch import receiver
from wagtail.signals import page_published, workflow_approved

from pages.models import PostPage
from pages.notifications import record_published_post
from pages.tasks import send_post_approved_email


@receiver(page_published, sender=PostPage, dispatch_uid="post_notification_published")
def raise_post_notification(sender, instance, **kwargs):
    """Light up the Posts nav dot when a net new post goes live.

    Wagtail fires `page_published` for every publish, including edits to a post
    that is already live, and also for a scheduled publish that has not reached
    its go-live time. Only the first publication of a live page counts: Wagtail
    stamps `first_published_at` and `last_published_at` with the same timestamp
    on that publish and only moves the latter afterwards.
    """
    if not instance.live:
        return
    if instance.first_published_at != instance.last_published_at:
        return
    record_published_post(instance.pk)


@receiver(workflow_approved)
def notify_post_author_on_approval(sender, instance, user, **kwargs):
    """Email a PostPage's author once its moderation workflow fully approves.

    `workflow_approved` fires once per workflow (not per task), so a
    multi-stage moderation chain still only sends one email, matching the
    legacy news.Entry behavior of a single "approved" notice.
    """
    page = instance.content_object
    if not isinstance(page, PostPage):
        page = getattr(page, "specific", None)
    if not isinstance(page, PostPage):
        return

    author = page.author
    if not author or not author.email:
        return

    send_post_approved_email.delay(page.pk)
