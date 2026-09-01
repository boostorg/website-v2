"""Signal wiring for `pages`. Imported from `PagesConfig.ready()`."""

from django.dispatch import receiver
from wagtail.signals import page_published

from pages.models import PostPage
from pages.notifications import record_published_post


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
