from allauth.account.signals import user_logged_in
from django.db import transaction
from django.dispatch import receiver
from django.db.models.signals import post_delete, post_save

from allauth.socialaccount.models import SocialAccount

from users.constants import LOGIN_METHOD_SESSION_FIELD_NAME
from users.models import UserProfileRoutingKey

GITHUB = "github"
GOOGLE = "google"


@receiver(post_save, sender=SocialAccount)
def import_social_profile_data(sender, instance, created, **kwargs):
    """
    When a new SocialAccount is created, get the data from that account for the
    user's profile
    """
    if not created:
        # for display name to save this needs to be resaved after the redirect.
        instance.user.save()
        return

    if instance.provider not in [GITHUB, GOOGLE]:
        return

    avatar_url = None
    provider_name = instance.extra_data.get("name")
    if instance.provider == GITHUB:
        instance.user.github_username = instance.extra_data.get("login")
        avatar_url = instance.extra_data.get("avatar_url")
        # A GitHub name is optional, so fall back to the handle rather than
        # leaving a new user with no display name at all.
        provider_name = provider_name or instance.extra_data.get("login")
    elif instance.provider == GOOGLE:
        avatar_url = instance.extra_data.get("picture")

    if avatar_url and not instance.user.image_uploaded:
        instance.user.save_image_from_provider(avatar_url)

    # Only fill a blank display name. Connecting an account must not overwrite
    # a name the user chose themselves.
    if not instance.user.display_name:
        instance.user.display_name = provider_name

    instance.save()
    # This is the one point where a social signup gets a name, and most users
    # never open the edit form, so without this their public URL keeps the
    # placeholder key minted back when they had no name at all.
    UserProfileRoutingKey.objects.sync_for(instance.user)

    if instance.provider == GITHUB:
        # Deferred to on_commit so the worker sees the github_username that the
        # instance.save() above persists via this receiver's created=False pass.
        from . import tasks

        user_pk = instance.user.pk
        transaction.on_commit(lambda: tasks.refresh_github_activity.delay(user_pk))


@receiver(post_delete, sender=SocialAccount)
def delete_github_activity(sender, instance, **kwargs):
    """Drop stored GitHub activity when a user disconnects their account."""
    if instance.provider != GITHUB:
        return

    from .models import GithubActivity, User

    # Locking the user row serialises this against refresh_github_activity, so
    # an in-flight refresh cannot write the row back after we delete it.
    with transaction.atomic():
        User.objects.select_for_update().filter(pk=instance.user_id).first()
        GithubActivity.objects.filter(user_id=instance.user_id).delete()


@receiver(user_logged_in)
def user_logged_in_handler(request, user, **kwargs):
    # We trigger this here as well as on the profile update in case there are two users
    #  on one machine, we need to reflag for the cookie update
    try:
        method = request.session["account_authentication_methods"][0].get("provider")
    except (KeyError, IndexError):
        method = None
    request.session[LOGIN_METHOD_SESSION_FIELD_NAME] = method or "email"

    if not user.data.get("ml_post_auth_seen"):
        request.session["show_ml_post_auth_modal"] = True
