from allauth.account.signals import user_logged_in
from django.dispatch import receiver
from django.db.models.signals import post_save

from allauth.socialaccount.models import SocialAccount

from users.constants import LOGIN_METHOD_SESSION_FIELD_NAME

GITHUB = "github"


@receiver(post_save, sender=SocialAccount)
def import_social_profile_data(sender, instance, created, **kwargs):
    """
    When a new SocialAccount is created, get the data from that account for the
    user's profile
    """
    if not created:
        return

    if instance.provider != GITHUB:
        return

    github_username = instance.extra_data.get("login")
    avatar_url = instance.extra_data.get("avatar_url")
    if github_username:
        instance.user.github_username = github_username
        instance.save()

    if avatar_url:
        instance.user.save_image_from_github(avatar_url)


@receiver(user_logged_in)
def user_logged_in_handler(request, user, **kwargs):
    # We trigger this here as well as on the profile update in case there are two users
    #  on one machine, we need to reflag for the cookie update
    try:
        method = request.session["account_authentication_methods"][0].get("provider")
    except (KeyError, IndexError):
        method = None
    request.session[LOGIN_METHOD_SESSION_FIELD_NAME] = method or "email"
