import structlog

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings

from celery import shared_task
from oauth2_provider.models import clear_expired

from config.celery import app
from core.githubhelper import GithubAPIClient
from libraries.models import CommitAuthorEmail, CommitAuthor

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


@shared_task
def do_scheduled_user_deletions():
    users = User.objects.filter(delete_permanently_at__lte=timezone.now())
    for user in users:
        user.delete_account()


@shared_task
def send_account_deleted_email(email):
    send_mail(
        "Your boost.io account has been deleted",
        "Your account on boost.io has been deleted.",
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )


def update_users_githubs():
    logger.info("Linking contributors to users")
    for user in User.objects.filter(github_username="", email="dave@sixfeetup.com"):
        logger.info(f"Linking attempt: {user.email}")
        update_user_github_username.delay(user.pk)


@shared_task
def update_user_github_username(user_id: int):
    logger.debug(f"{user_id=}")
    user = User.objects.get(pk=user_id)
    email = CommitAuthorEmail.objects.prefetch_related("author").get(email=user.email)
    if not email:
        logger.info(f"No commit author email found for {user.pk=} {user.email=}")
        return
    commit_author = email.author
    logger.debug(f"Found {user.pk=} for {commit_author=}")
    if not commit_author.github_profile_url:
        logger.info(f"No github username found on {commit_author.pk=}")
        return
    github_username = commit_author.github_profile_url.rstrip("/").split("/")[-1]
    logger.debug(f"Linking {user.pk=} to {email.author.pk=} using {github_username=}")
    user.github_username = github_username
    user.save()
    logger.info(f"Linked {user.pk=} to {commit_author.pk=} by github_username")


def update_commit_authors_users():
    logger.info("Linking commit authors to users")
    for commit_author in CommitAuthor.objects.filter(user__isnull=True):
        logger.info(f"Linking attempt: {commit_author=}")
        update_commit_author_user(commit_author.pk)
    logger.info("Finished linking commit authors to users.")


def update_commit_author_user(author_id: int):
    logger.info(f"{author_id=}")
    commit_author_emails = CommitAuthorEmail.objects.prefetch_related("author").filter(
        author_id=author_id
    )

    if not commit_author_emails:
        logger.info(f"No emails found for {author_id=}")
        return

    for email in commit_author_emails:
        user = User.objects.filter(email=email.email).first()
        if not user:
            logger.info(f"No user found for {email.pk=} {email.email=}")
            continue
        email.author.user = user
        email.author.save()
        logger.info(f"Linked {user=} {user.pk=} to {email=} {email.author.pk=}")
