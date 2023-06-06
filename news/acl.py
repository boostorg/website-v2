"""ACL functions for news entries."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q


User = get_user_model()


def moderators():
    return User.objects.filter(
        Q(
            user_permissions__codename="change_entry",
            user_permissions__content_type__app_label="news",
        )
        | Q(
            groups__permissions__codename="change_entry",
            groups__permissions__content_type__app_label="news",
        )
        | Q(is_superuser=True),
        is_active=True,
    ).distinct()


def can_view(user, entry):
    return (
        entry.is_published
        or user == entry.author
        or (user is not None and user.has_perm("news.view_entry"))
    )


def can_approve(user, entry=None):
    # entry is ignored for now, approval depends only on permissions
    return user is not None and moderators().filter(pk=user.pk).exists()


def can_edit(user, entry):
    return (not entry.is_approved and user == entry.author) or (
        user is not None and user.has_perm("news.change_entry")
    )


def can_delete(user, entry):
    return user is not None and user.has_perm("news.delete_entry")


def author_needs_moderation(entry):
    # Every author's news should be moderated except for moderators or
    # explicitely allowlisted users.
    return not (
        can_approve(entry.author)
        or entry.author.email in settings.NEWS_MODERATION_ALLOWLIST
        or entry.author.pk in settings.NEWS_MODERATION_ALLOWLIST
    )
