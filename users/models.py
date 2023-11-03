import logging
import os

import requests
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.files import File
from django.core.mail import send_mail
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.validators import image_validator, max_file_size_validator

logger = logging.getLogger(__name__)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """
        Creates and saves a User with the given username, email and password.
        """
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        logger.info("Creating user with email='%s'", email)
        return self._create_user(email, password, **extra_fields)

    def create_staffuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", False)
        logger.info("Creating staff user with email='%s'", email)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        logger.info("Creating superuser with email='%s'", email)
        return self._create_user(email, password, **extra_fields)

    def create_stub_user(self, email, password=None, claimed=False, **extra_fields):
        """Creates a placeholder ("stub") user."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        logger.info("Creating stub user with email='%s'", email)
        return self._create_user(email, password, claimed=claimed, **extra_fields)

    def find_contributor(self, email=None, first_name=None, last_name=None):
        """
        Lazily finds a matching User record by email, or first name and last name.

        This method is intended to be used when uploading library contributors in
        situations where we might not have contributor's email address. It first checks
        if a user with the given email exists, and if found, returns that user. If no
        user is found with the given email, it checks if a user with the given first
        name and last name exists, and returns that user if found. Otherwise, it
        returns None.

        Args:
            email (str, optional): The email address of the user to search for.
                Assumes the email address is legitimate, and is not one we generated as
                a placeholder.
            first_name (str, optional): The first name of the user to search for.
            last_name (str, optional): The last name of the user to search for.

        Returns:
            User object or None: If a user is found based on the provided criteria, the
            user object is returned. Otherwise, None is returned.

        """
        user = None

        if email:
            try:
                user = self.get(email=email.lower())
            except self.model.DoesNotExist:
                pass

        if not user and first_name and last_name:
            users = self.filter(
                first_name__iexact=first_name, last_name__iexact=last_name
            )
            authors_or_maintainers = users.filter(
                models.Q(authors__isnull=False) | models.Q(maintainers__isnull=False)
            ).distinct()
            if authors_or_maintainers.count() == 1:
                user = authors_or_maintainers.first()

        return user

    def record_login(self, user=None, email=None):
        """
        Record a succesful login to last_login for the user by user
        obj or email
        """
        if email is None and user is None:
            raise ValueError("email and user cannot both be None")

        if email:
            this_user = self.get(email=email)
        else:
            this_user = user

        this_user.last_login = timezone.now()
        this_user.save()

    def allow_notification_others_news_posted(self, news_type):
        lookup = f"preferences__notifications__{Preferences.OTHERS_NEWS_POSTED}"
        allows_all_types = models.Q(**{lookup: ["all"]})
        allows_news_type = models.Q(**{f"{lookup}__contains": news_type})
        return self.filter(allows_all_types | allows_news_type)


class BaseUser(AbstractBaseUser, PermissionsMixin):
    """
    Our email for username user model
    """

    first_name = models.CharField(_("first name"), max_length=30, blank=True)
    last_name = models.CharField(_("last name"), max_length=30, blank=True)
    email = models.EmailField(_("email address"), unique=True, db_index=True)
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    data = models.JSONField(default=dict, blank=True, help_text="Arbitrary user data")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        swappable = "AUTH_USER_MODEL"
        abstract = True

    def get_full_name(self):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Returns the short name for the user."""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def save(self, *args, **kwargs):
        """Ensure email is always lower case"""
        self.email = self.email.lower()

        return super().save(*args, **kwargs)


class Badge(models.Model):
    name = models.CharField(_("name"), max_length=100, blank=True)
    display_name = models.CharField(_("display name"), max_length=100, blank=True)


class User(BaseUser):
    """
    Our custom user model.

    NOTE: See ./signals.py for signals that relate to this model.
    """

    badges = models.ManyToManyField(Badge)
    github_username = models.CharField(_("github username"), max_length=100, blank=True)
    image = models.FileField(
        upload_to="profile-images",
        null=True,
        blank=True,
        validators=[image_validator, max_file_size_validator],
    )
    claimed = models.BooleanField(
        _("claimed"),
        default=True,
        help_text=_("Designates whether this user has been claimed."),
    )
    valid_email = models.BooleanField(
        _("valid_email"),
        default=True,
        help_text=_(
            "Designates whether this user's email address is valid, to the best of our "
            "knowledge."
        ),
    )
    display_name = models.CharField(max_length=255, blank=True, null=True)
    can_update_image = models.BooleanField(
        _("can_update_image"),
        default=True,
        help_text=_(
            "Designates whether the user can update their profile photo. To turn off "
            "a user's ability to update their own profile photo, uncheck this box."
        ),
    )

    def save_image_from_github(self, avatar_url):
        response = requests.get(avatar_url)
        filename = f"profile-{self.pk}.png"
        os.path.join(settings.MEDIA_ROOT, "media", "profile-images", filename)

        with open(filename, "wb") as f:
            f.write(response.content)

        reopen = open(filename, "rb")
        django_file = File(reopen)
        self.image.save(filename, django_file, save=True)

    @property
    def get_display_name(self):
        """Returns the display name for the user."""
        if self.display_name:
            return self.display_name
        elif self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        else:
            return self.first_name or self.last_name

    def claim(self):
        """Claim the user"""
        if not self.claimed:
            self.claimed = True
            self.save()


class LastSeen(models.Model):
    """
    Last time we saw a user.  This differs from User.last_login in that
    a user may login on Monday and visit the site several times over the
    next week before their login cookie expires.  This tracks the last time
    they were actually on the web UI.

    So why isn't it on the User model? Well that would be a lot of database
    row churn and contention on the User table itself so I'm breaking this
    out into another table. Likely a pre-optimization on my part.

    Far Future TODO: Store and update this in Redis as it happens and daily
    sync that info to this table.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="last_seen",
        on_delete=models.CASCADE,
    )
    at = models.DateTimeField(default=timezone.now)

    def now(self, commit=True):
        """
        Update this row to be right now
        """
        self.at = timezone.now()
        if commit:
            self.save()


def get_empty_notifications():
    return {
        Preferences.OWNS_NEWS_APPROVED: [Preferences.NEWS_TYPES_WILDCARD],
        Preferences.OTHERS_NEWS_POSTED: [],
        Preferences.OTHERS_NEWS_NEEDS_MODERATION: [Preferences.NEWS_TYPES_WILDCARD],
    }


class Preferences(models.Model):
    ALL_NEWS_TYPES = sorted({"blogpost", "link", "news", "poll", "video"})
    NEWS_TYPES_WILDCARD = "all"
    OWNS_NEWS_APPROVED = "own-news-approved"
    OTHERS_NEWS_POSTED = "others-news-posted"
    OTHERS_NEWS_NEEDS_MODERATION = "others-news-needs-moderation"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="preferences",
        on_delete=models.CASCADE,
    )
    notifications = models.JSONField(default=get_empty_notifications)

    def __str__(self):
        return f"Preferences for user {self.user_id}: {self.notifications}"

    def notification_allowed(self, preference):
        result = self.notifications[preference]
        if self.NEWS_TYPES_WILDCARD in result:
            result = self.ALL_NEWS_TYPES
        return result

    def change_notification_allowed(self, preference, value):
        value = sorted(value)
        if value == self.ALL_NEWS_TYPES:
            value = [self.NEWS_TYPES_WILDCARD]
        self.notifications[preference] = value

    @property
    def allow_notification_own_news_approved(self):
        return self.notification_allowed(self.OWNS_NEWS_APPROVED)

    @allow_notification_own_news_approved.setter
    def allow_notification_own_news_approved(self, value):
        self.change_notification_allowed(self.OWNS_NEWS_APPROVED, value)

    @property
    def allow_notification_others_news_posted(self):
        return self.notification_allowed(self.OTHERS_NEWS_POSTED)

    @allow_notification_others_news_posted.setter
    def allow_notification_others_news_posted(self, value):
        self.change_notification_allowed(self.OTHERS_NEWS_POSTED, value)

    @property
    def allow_notification_others_news_needs_moderation(self):
        return self.notification_allowed(self.OTHERS_NEWS_NEEDS_MODERATION)

    @allow_notification_others_news_needs_moderation.setter
    def allow_notification_others_news_needs_moderation(self, value):
        self.change_notification_allowed(self.OTHERS_NEWS_NEEDS_MODERATION, value)


@receiver(post_save, sender=User)
def create_last_seen_for_user(sender, instance, created, raw, **kwargs):
    """Create LastSeen row when a User is created"""
    if raw:
        return

    if created:
        LastSeen.objects.create(user=instance, at=timezone.now())
        Preferences.objects.create(user=instance)
