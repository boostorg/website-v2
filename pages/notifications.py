"""Cache-backed state for the "new posts" dot on the Posts nav item.

No database models are involved. Publishing a post writes that post's id under
one well-known key; every user carries one key holding the id they last
acknowledged. The dot is on whenever those two disagree, so a publish clears
everybody's acknowledgement implicitly and no bulk key deletion is ever needed.

Everything goes through Django's cache API (the ``default`` alias, backed by
Redis) rather than a raw Redis handle, so the state survives a backend swap and
is trivially fakeable in tests.
"""

from django.conf import settings
from django.core.cache import cache

LATEST_POST_KEY = "posts:notification:latest_post_id"
SEEN_KEY_PREFIX = "posts:notification:seen"


def _seen_key(user_id) -> str:
    return f"{SEEN_KEY_PREFIX}:{user_id}"


def _acknowledgeable_user(user):
    """The user we can store an acknowledgement for, or None.

    Anonymous visitors have no stable identity to dismiss the dot against, and
    giving them one would mean writing a session on every anonymous page view.
    They never see the dot.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user


def latest_notified_post_id():
    """Id of the post the dot currently advertises, or None when there is none."""
    return cache.get(LATEST_POST_KEY)


def record_published_post(post_id) -> None:
    """Turn the dot on for everyone, pointing it at `post_id`."""
    cache.set(LATEST_POST_KEY, int(post_id), timeout=None)


def has_unread_posts(user) -> bool:
    """Whether `user` should see the dot on the Posts nav item."""
    if _acknowledgeable_user(user) is None:
        return False
    latest = latest_notified_post_id()
    if latest is None:
        return False
    return cache.get(_seen_key(user.pk)) != latest


def _store_acknowledgement(user, latest) -> None:
    cache.set(
        _seen_key(user.pk),
        latest,
        timeout=settings.POST_NOTIFICATION_SEEN_TIMEOUT,
    )


def mark_posts_seen(user) -> None:
    """Dismiss the dot for `user`, whatever post it is advertising."""
    if _acknowledgeable_user(user) is None:
        return
    latest = latest_notified_post_id()
    if latest is None:
        return
    _store_acknowledgement(user, latest)


def mark_post_seen(user, post_id) -> None:
    """Dismiss the dot for `user`, but only on the post it advertises.

    Reading an older post says nothing about having seen the newest one, so it
    leaves the dot alone.
    """
    if _acknowledgeable_user(user) is None:
        return
    latest = latest_notified_post_id()
    if latest is None or latest != int(post_id):
        return
    _store_acknowledgement(user, latest)
