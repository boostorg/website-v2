import structlog

from django.contrib.auth import get_user_model

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
    avatar_url = response["avatar_url"]
    user.save_image_from_github(avatar_url)
    logger.info("users_tasks_update_gh_photo_finished", user_pk=user_pk)


# OAuth2 Tasks


@shared_task
def clear_tokens():
    """Clears all expired tokens"""
    clear_expired()
