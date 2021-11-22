import logging
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


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
        "Returns the short name for the user."
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


class User(BaseUser):
    pass


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


@receiver(post_save, sender=User)
def create_last_seen_for_user(sender, instance, created, raw, **kwargs):
    """Create LastSeen row when a User is created"""
    if raw:
        return

    if created:
        LastSeen.objects.create(user=instance, at=timezone.now())
