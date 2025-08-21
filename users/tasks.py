from time import sleep

import structlog

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings

from celery import shared_task
from oauth2_provider.models import clear_expired

from config.celery import app
from core.githubhelper import GithubAPIClient

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
    Refreshes the GitHub photos for all users who have a GitHub username.
    This is intended to be run periodically to ensure user photos are up-to-date.
    """
    users = User.objects.exclude(github_username="")
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
    users = User.objects.filter(delete_permanently_at__lte=timezone.now())
    for user in users:
        user.delete_account()


@shared_task
def send_account_deleted_email(email):
    send_mail(
        "Your boost.org account has been deleted",
        "Your account on boost.org has been deleted.",
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
