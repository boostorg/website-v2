from time import sleep
from datetime import timedelta

import structlog

from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings

from celery import shared_task
from oauth2_provider.models import clear_expired

from config.celery import app
from core.githubhelper import GithubAPIClient
from users.constants import UNVERIFIED_CLEANUP_DAYS, UNVERIFIED_CLEANUP_BEGIN

logger = structlog.getLogger(__name__)

User = get_user_model()


class UserMissingGithubUsername(Exception):
    pass


@app.task
def update_user_github_photo(user_pk):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        logger.exception("users_tasks_update_gh_photo_no_user_found", user_pk=user_pk)
        raise

    if not user.github_username:
        logger.info("users_tasks_update_gh_photo_no_github_username", user_pk=user_pk)
        raise UserMissingGithubUsername

    client = GithubAPIClient()
    response = client.get_user_by_username(user.github_username)
    # response can be None if the user does not exist on GitHub
    if not response:
        return
    avatar_url = response["avatar_url"]
    user.save_image_from_provider(avatar_url)
    logger.info("users_tasks_update_gh_photo_finished", user_pk=user_pk)


@app.task
def refresh_users_github_photos():
    """
    Refreshes the GitHub photos for all users who have a GitHub username and haven't
     uploaded an image manually.
    This is intended to be run periodically to ensure user photos are up-to-date.
    """
    users = User.objects.exclude(Q(github_username="") | Q(image_uploaded=True))
    for user in users:
        try:
            logger.info(f"updating {user.pk=}")
            update_user_github_photo.delay(user.pk)
            # not strictly necessary, but helps to avoid hammering the GitHub API
            sleep(0.5)
        except UserMissingGithubUsername:
            logger.warning(
                "users_tasks_refresh_gh_photos_no_github_username",
                user_pk=user.pk,
                github_username=user.github_username,
            )


# OAuth2 Tasks


@shared_task
def clear_tokens():
    """Clears all expired tokens"""
    clear_expired()


@shared_task
def do_scheduled_user_deletions():
    # Reuse the scrub mode captured when the deletion was scheduled: V3
    # requests set deletion_extended_scrub so the grace-period delete applies
    # the same extended PII scrub as the V3 immediate delete; legacy requests
    # leave it False and keep the narrow scrub.
    users = User.objects.filter(delete_permanently_at__lte=timezone.now())
    for user in users:
        user.delete_account(extended_scrub=user.deletion_extended_scrub)


@shared_task
def send_account_deleted_email(email):
    send_mail(
        "Your boost.org account has been deleted",
        "Your account on boost.org has been deleted.",
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )


@shared_task
def send_account_deletion_scheduled_email(
    email, first_name, grace_days, login_url, scheme, host
):
    """Confirm a scheduled deletion and explain how to cancel it.

    Absolute URLs (login CTA, logo link) are built in the view where the
    request is available and passed in, since a Celery task has no request.
    """
    context = {
        "first_name": first_name,
        "grace_days": grace_days,
        "action_url": login_url,
        "postorius_url": settings.POSTORIUS_URL,
        "scheme": scheme,
        "host": host,
    }
    subject = render_to_string(
        "emails/account_deletion_scheduled_subject.txt", context
    ).strip()
    text_body = render_to_string("emails/account_deletion_scheduled.txt", context)
    html_body = render_to_string("emails/account_deletion_scheduled.html", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()


@shared_task
def remove_unverified_users():
    """
    Removes users that have accounts with unverified email addresses after some time
    """
    logger.info("Starting remove_unverified_users task")

    try:
        cutoff_date = timezone.now() - timedelta(days=UNVERIFIED_CLEANUP_DAYS)
        logger.info(f"Joined after {UNVERIFIED_CLEANUP_BEGIN} and before {cutoff_date}")

        unverified_users = User.objects.filter(
            claimed=True,
            emailaddress__verified=False,
            date_joined__gte=UNVERIFIED_CLEANUP_BEGIN,
            date_joined__lt=cutoff_date,
        ).order_by("date_joined")

        user_count = unverified_users.count()
        logger.info(f"Found {user_count} unverified users for deletion")

        if user_count == 0:
            return

        for user in unverified_users:
            logger.info(f"Del user: {user.id=}, {user.email=}, {user.date_joined=}")
            user.delete()
        logger.info(f"Successfully processed {user_count} unverified users")

    except Exception as e:
        logger.exception(f"Error occurred processing unverified users for removal: {e}")


@app.task
def recompute_displayed_profile_roles():
    """Recompute every user's auto-derived top library role.

    Writes `User.resolved_profile_role` (the fallback shown when a user has
    chosen neither a library role nor holds an internal title) and clears any
    user-selected `displayed_profile_role` that is no longer valid. Enqueued
    after author/maintainer and commit imports, with a daily safety run via beat.
    """
    from collections import defaultdict

    from libraries.models import Commit, Library, LibraryVersion
    from users.models import ProfileRole

    # (user_id, library_id) pairs per role: author / maintainer / contributor.
    valid = {
        ProfileRole.AUTHOR.value: set(
            Library.authors.through.objects.values_list("user_id", "library_id")
        ),
        ProfileRole.MAINTAINER.value: set(
            LibraryVersion.maintainers.through.objects.values_list(
                "user_id", "libraryversion__library_id"
            ).distinct()
        ),
        ProfileRole.CONTRIBUTOR.value: set(
            Commit.objects.filter(author__user_id__isnull=False)
            .values_list("author__user_id", "library_version__library_id")
            .distinct()
        ),
    }
    held_any = {role: {uid for uid, _ in pairs} for role, pairs in valid.items()}

    # Each user's highest-precedence role. Iterating high-to-low, setdefault
    # keeps the first (highest) seen.
    top = {}
    for role in ProfileRole.library_role_precedence():
        for uid in held_any[role]:
            top.setdefault(uid, role)
    by_role = defaultdict(list)
    for uid, role in top.items():
        by_role[role].append(uid)

    # Clear explicit user choices the latest import has revoked, so `.role`
    # falls through instead of displaying a role the user no longer holds.
    stale_ids = []
    choosers = User.objects.exclude(displayed_profile_role="").values_list(
        "id", "displayed_profile_role", "displayed_profile_role_library_id"
    )
    for uid, role, lib_id in choosers:
        if lib_id:
            ok = (uid, lib_id) in valid.get(role, set())
        else:
            ok = uid in held_any.get(role, set())
        if not ok:
            stale_ids.append(uid)

    with transaction.atomic():
        User.objects.exclude(id__in=top).exclude(resolved_profile_role="").update(
            resolved_profile_role=""
        )
        for role, ids in by_role.items():
            User.objects.filter(id__in=ids).update(resolved_profile_role=role)
        if stale_ids:
            User.objects.filter(id__in=stale_ids).update(
                displayed_profile_role="", displayed_profile_role_library=None
            )
    logger.info(
        "recompute_displayed_profile_roles finished",
        resolved=len(top),
        cleared_choices=len(stale_ids),
    )
