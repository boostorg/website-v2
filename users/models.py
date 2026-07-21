import uuid
import logging
from contextlib import suppress

import requests
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from imagekit.exceptions import MissingSource
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill

from core.validators import (
    image_validator,
    large_file_max_size_validator,
    downscale_image_file_size_validator,
)
from core.templatetags.custom_static import large_static

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

    def find_contributor(self, email=None, display_name=None):
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
            display_name (str, optional): The display name of the user to search for.

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

        if not user and display_name:
            users = self.filter(display_name__iexact=display_name)
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

    # todo: remove first_name, last_name after May 2025
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

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def save(self, *args, **kwargs):
        """Ensure email is always lower case"""
        self.email = self.email.lower()

        return super().save(*args, **kwargs)


class ProfileRole(models.TextChoices):
    """Roles shown on profile surfaces.

    Library-derived roles are self-selectable by users who hold them (stored in
    `User.displayed_profile_role`); internal C++ Alliance titles are assignable
    via the Django admin only (stored in `User.internal_role`).
    """

    # Library-derived (user-selectable)
    AUTHOR = "Author", "Author"
    MAINTAINER = "Maintainer", "Maintainer"
    CONTRIBUTOR = "Contributor", "Contributor"

    # Internal C++ Alliance titles (admin-only)
    CHIEF_OF_STAFF = "chief_of_staff", "Chief of Staff, C++ Alliance"
    CEO = "ceo", "CEO, C++ Alliance"
    CTO = "cto", "CTO, C++ Alliance"
    CFO_COO = "cfo_coo", "CFO/COO, C++ Alliance"
    CMO = "cmo", "CMO, C++ Alliance"
    BOARD_MEMBER = "board_member", "Board Member, C++ Alliance"
    SENIOR_EXEC_ASSISTANT = (
        "senior_exec_assistant",
        "Senior Executive Assistant, C++ Alliance",
    )
    CREATIVE_PRODUCTION_COORDINATOR = (
        "creative_production_coordinator",
        "Creative Production Coordinator, C++ Alliance",
    )
    SOFTWARE_ENGINEER = "software_engineer", "Software Engineer, C++ Alliance"
    SENIOR_TECHNICAL_WRITER = (
        "senior_technical_writer",
        "Senior Technical Writer, C++ Alliance",
    )
    EXECUTIVE_TEAM_ALUMNI = (
        "executive_team_alumni",
        "Executive Team, C++ Alliance Alumni",
    )
    TECHNICAL_COMMITTEE_ALUMNI = (
        "technical_committee_alumni",
        "Technical Committee, C++ Alliance Alumni",
    )
    SOFTWARE_ENGINEER_ALUMNI = (
        "software_engineer_alumni",
        "Software Engineer, C++ Alliance Alumni",
    )
    FISCAL_COMMITTEE_MEMBER = (
        "fiscal_committee_member",
        "Fiscal Committee Member, C++ Alliance",
    )

    @classmethod
    def library_role_precedence(cls):
        """Library roles high-to-low, used to pick a default when a user holds several."""
        return [cls.AUTHOR.value, cls.MAINTAINER.value, cls.CONTRIBUTOR.value]

    @classmethod
    def library_roles(cls):
        return frozenset(cls.library_role_precedence())

    @classmethod
    def internal_roles(cls):
        return frozenset(cls.values) - cls.library_roles()

    @classmethod
    def singular_roles(cls):
        """Internal titles that at most one user may hold.

        Returns a sorted tuple so the migration constraint condition serializes
        deterministically.
        """
        return (
            cls.CEO.value,
            cls.CFO_COO.value,
            cls.CHIEF_OF_STAFF.value,
            cls.CMO.value,
            cls.CTO.value,
        )


# Sentinel dropdown value for "No Public Role": an explicit opt-out that hides
# the user's role on every profile surface (see `hide_public_role`). Distinct
# from an empty selection, which falls through to the auto-derived role.
NO_PUBLIC_ROLE_OPTION = "__no_public_role__"
NO_PUBLIC_ROLE_LABEL = (
    "No Public Role - Your role won't be linked to your name elsewhere on the site."
)

CONTRIBUTOR_DATA_CACHE_PREFIX = "contributor_data_"


def contributor_data_cache_key(user_id):
    """Redis key for a user's cached profile contribution data.

    Shared with the import-time cache invalidation in
    `recompute_displayed_profile_roles`.
    """
    return f"{CONTRIBUTOR_DATA_CACHE_PREFIX}{user_id}"


def encode_role_option(role, library_id):
    """Encode a (role, library) pair as a single dropdown option value.

    A falsy `library_id` encodes a generic, library-less role (e.g. "Author:").
    """
    return f"{role}:{library_id or ''}"


def decode_role_option(value):
    """Decode an encoded option value into (role, library_id).

    Returns (role, None) for an unscoped role and ("", None) for an empty value.
    """
    if not value:
        return "", None
    role, _, library_id = value.partition(":")
    return role, (int(library_id) if library_id.isdigit() else None)


def compose_role_label(role, library):
    """Human label for a (role, library) pair, e.g. "Boost.Beast Author".

    Without a library the plain role label is used (generic roles and titles).
    """
    label = ProfileRole(role).label
    return f"{library.display_name} {label}" if library is not None else label


class User(BaseUser):
    """
    Our custom user model.

    NOTE: See ./signals.py for signals that relate to this model.

    Achievements and badges live in the ``badges`` app and reference this model
    via ``UserAchievement`` / ``UserBadge`` (reverse accessors ``achievements``
    and ``badges``).
    """

    TAGLINE_MAX_LENGTH = 70
    BIOGRAPHY_MAX_LENGTH = 20000

    # todo: consider making this unique=True after checking user data for duplicates
    github_username = models.CharField(_("github username"), max_length=100, blank=True)
    is_commit_author_name_overridden = models.BooleanField(
        default=False, help_text="Select to override the commit author with Username"
    )
    profile_image = models.FileField(
        upload_to="profile-images",
        null=True,
        blank=True,
        validators=[image_validator, downscale_image_file_size_validator],
    )
    image_thumbnail = ImageSpecField(
        source="profile_image",
        processors=[ResizeToFill(100, 100)],
        format="JPEG",
        options={"quality": 90},
    )
    hq_image = models.FileField(
        upload_to="hiqh-quality-user-images",
        help_text="A high-quality image of the user - used in profiles/reports.",
        null=True,
        blank=True,
        validators=[image_validator, large_file_max_size_validator],
        verbose_name="High Quality Image",
    )
    hq_image_render = ImageSpecField(
        source="hq_image",
        processors=[ResizeToFill(4096, 4096)],
        format="JPEG",
        options={"quality": 90},
    )
    image_uploaded = models.BooleanField(
        default=False,
        help_text="Indicates if the user manually uploaded an image, prevents import overwrites",
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
    displayed_profile_role = models.CharField(
        max_length=64,
        choices=ProfileRole,
        blank=True,
        default="",
        help_text=_(
            "Library role the user has chosen to feature (or blank to use their "
            "default). User-controlled; C++ Alliance titles live in internal_role."
        ),
    )
    displayed_profile_role_library = models.ForeignKey(
        "libraries.Library",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_(
            "Optional library that scopes a library role, e.g. Beast -> "
            '"Boost.Beast Author". Leave blank for a generic role.'
        ),
    )
    internal_role = models.CharField(
        max_length=64,
        choices=[
            (r.value, r.label)
            for r in sorted(ProfileRole, key=lambda r: r.value)
            if r.value in ProfileRole.internal_roles()
        ],
        blank=True,
        default="",
        help_text=_(
            "C++ Alliance title, assigned by staff. This is the user's default "
            "displayed role; they may instead feature a library role they hold."
        ),
    )
    resolved_profile_role = models.CharField(
        max_length=64,
        blank=True,
        default="",
        editable=False,
        help_text=_(
            "Auto-derived top library role, recomputed on import. Used only when "
            "the user has set neither displayed_profile_role nor internal_role."
        ),
    )
    hide_public_role = models.BooleanField(
        default=False,
        help_text=_(
            "When set, the user has opted out of showing a role: it is hidden on "
            "every profile surface except their own public profile page, which "
            "still shows their best available role."
        ),
    )
    can_update_image = models.BooleanField(
        _("can_update_image"),
        default=True,
        help_text=_(
            "Designates whether the user can update their profile photo. To turn off "
            "a user's ability to update their own profile photo, uncheck this box."
        ),
    )
    indicate_last_login_method = models.BooleanField(
        default=False,
        help_text="Indicate on the login page the last login method used.",
    )
    country = CountryField(blank=True)
    hide_github_activity = models.BooleanField(
        default=False,
        help_text="Hide GitHub activity from the public profile.",
    )
    hide_mailing_list_activity = models.BooleanField(
        default=False,
        help_text="Hide mailing list activity from the public profile.",
    )
    hide_badges = models.BooleanField(
        default=False,
        help_text="Hide badges from the public profile.",
    )
    profile_links = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Public profile links keyed by type (github, website, email, slack). "
            "Slack stores the full canonical CPPLang Slack profile URL "
            "(https://cpplang.slack.com/team/<Member ID>) built from the "
            "user's Slack Member ID. The Member ID is derived for display in "
            "the edit form."
        ),
    )
    tagline = models.CharField(
        max_length=TAGLINE_MAX_LENGTH,
        blank=True,
        default="",
        help_text="Short plain-text tagline shown beside the avatar across the site.",
    )
    biography = models.TextField(
        max_length=BIOGRAPHY_MAX_LENGTH,
        blank=True,
        default="",
        help_text="Rich-text biography (stored as Markdown) shown on the public profile.",
    )
    # If non-null, the user has requested deletion but the grace period has not
    # elapsed.
    delete_permanently_at = models.DateTimeField(null=True, editable=False)
    # Remembers whether the pending deletion was requested through the V3 flow,
    # so the grace-period task can apply the same extended PII scrub the V3
    # immediate delete uses. Legacy requests leave this False.
    deletion_extended_scrub = models.BooleanField(default=False, editable=False)

    class Meta(BaseUser.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["internal_role"],
                condition=models.Q(internal_role__in=ProfileRole.singular_roles()),
                name="unique_singular_profile_role",
                violation_error_message=(
                    "This C++ Alliance title is already assigned to another user."
                ),
            )
        ]

    def _delete_cached_spec(self, source_field, spec_field):
        """Delete a cached ImageKit spec file so it regenerates on next access."""
        if not getattr(self, source_field):
            return
        try:
            from imagekit.cachefiles.backends import CacheFileState

            cache_file = getattr(self, spec_field)
            if cache_file.name:
                cache_file.storage.delete(cache_file.name)
            cache_file.cachefile_backend.set_state(
                cache_file, CacheFileState.DOES_NOT_EXIST
            )
        except (OSError, AttributeError):
            logger.debug("Failed to invalidate %s cache", spec_field, exc_info=True)

    def delete_cached_thumbnail(self):
        """Delete the cached ImageKit thumbnail so it regenerates on next access."""
        self._delete_cached_spec("profile_image", "image_thumbnail")

    def delete_cached_hq_render(self):
        """Delete the cached full-size render of the high-quality image."""
        self._delete_cached_spec("hq_image", "hq_image_render")

    def save_image_from_provider(self, avatar_url):
        from django.core.files.base import ContentFile

        self.delete_cached_thumbnail()
        response = requests.get(avatar_url)
        filename = f"{self.profile_image_filename_root}.png"
        self.profile_image.save(filename, ContentFile(response.content), save=True)

    @cached_property
    def profile_image_filename_root(self):
        """Returns the user's PK as part of the filename for their image.
        Does not include the file extension."""
        return f"profile-{self.pk}"

    @cached_property
    def year_joined(self):
        """Returns user year joined for display on profiles"""
        return self.date_joined.year

    def claim(self):
        """Claim the user"""
        if not self.claimed:
            self.claimed = True
            self.save()

    def get_thumbnail_url(self):
        # convenience method for templates
        if self.profile_image and self.image_thumbnail:
            with suppress(AttributeError, MissingSource, FileNotFoundError, OSError):
                return getattr(self.image_thumbnail, "url", None)

    def get_avatar_url(self):
        """Return the best available avatar URL.

        Tries the profile image thumbnail first, then falls back to
        the linked CommitAuthor avatar. Returns empty string when no
        image is available so the avatar template falls back to a
        colored initials circle.
        """
        if url := self.get_thumbnail_url():
            return url
        if (ca := getattr(self, "commitauthor", None)) and getattr(
            ca, "avatar_url", None
        ):
            return ca.avatar_url
        return ""

    def to_v3_profile_dict(self, role=None):
        """Dict shape consumed by `v3/includes/_user_profile.html`."""
        return {
            "name": self.display_name or str(self),
            "profile_url": None,
            "role": role if role is not None else self.role,
            "avatar_url": self.get_avatar_url(),
            "badge": None,
            "bio": None,
        }

    def get_hq_image_url(self):
        # convenience method for templates
        if self.hq_image and self.hq_image_render:
            with suppress(AttributeError, MissingSource, FileNotFoundError, OSError):
                return getattr(self.hq_image_render, "url", None)

    @property
    def github_profile_url(self):
        if not self.github_username:
            return None
        return f"https://github.com/{self.github_username}"

    @cached_property
    def name(self):
        return self.display_name

    @cached_property
    def avatar_url(self):
        return self.get_avatar_url()

    @cached_property
    def badge_url(self):
        """
        This is a placeholder value

        TODO: Replace this value
        """
        return large_static("img/v3/badges/badge-gold-medal.png")

    def _effective_role(self, ignore_hidden=False):
        """The (role_type, library) currently displayed, or (None, None).

        Reads only columns (no queries): user's chosen library role → internal
        C++ Alliance title → auto-derived top library role (`resolved_profile_role`,
        maintained by `recompute_displayed_profile_roles`).

        Returns (None, None) when the user has opted out via `hide_public_role`,
        unless `ignore_hidden` is set (the public profile page still shows a role).
        """
        if self.hide_public_role and not ignore_hidden:
            return None, None
        if self.displayed_profile_role in ProfileRole.library_roles():
            return self.displayed_profile_role, self.displayed_profile_role_library
        if self.internal_role:
            return self.internal_role, None
        if self.resolved_profile_role:
            return self.resolved_profile_role, None
        return None, None

    @cached_property
    def role(self):
        """Display role shown on profile surfaces (single source of truth).

        A library role is scoped to its library ("Boost.Beast Author") or generic
        ("Author"); a C++ Alliance title renders as-is. Empty when the user opted
        out via `hide_public_role`. See `_effective_role`.
        """
        role_type, library = self._effective_role()
        return compose_role_label(role_type, library) if role_type else ""

    @property
    def public_role(self):
        """Best available role for the user's own public profile page.

        Like `role`, but ignores `hide_public_role`: the opt-out hides the role
        everywhere else, while the profile page still shows the best available one.
        """
        role_type, library = self._effective_role(ignore_hidden=True)
        return compose_role_label(role_type, library) if role_type else ""

    @property
    def encoded_displayed_role(self):
        """Encoded option value used to preselect the edit-page dropdown.

        `NO_PUBLIC_ROLE_OPTION` when the user opted out; empty when there is no
        role to show; library-less roles encode as "role:".
        """
        if self.hide_public_role:
            return NO_PUBLIC_ROLE_OPTION
        role_type, library = self._effective_role()
        if not role_type:
            return ""
        return encode_role_option(role_type, library.id if library else "")

    def get_role_options(self):
        """Selectable role options for the edit-page dropdown.

        A generic, library-less option (e.g. "Author") is offered at the top for
        each role the user holds in at least one library, in precedence order,
        followed by the library-scoped options (e.g. "Boost.Beast Author"). A
        generic option carries `library=None`.

        Users can't assign internal C++ Alliance titles, but if an admin has
        assigned one (internal_role) it is the user's default displayed role:
        it is offered first and preselected. It is the only title a user may
        (re-)select.
        """
        scoped = self.get_role_library_options()
        generic, seen = [], set()
        for option in scoped:  # already precedence-ordered
            if option["role"] not in seen:
                seen.add(option["role"])
                generic.append({"role": option["role"], "library": None})
        options = generic + scoped
        if self.internal_role:
            options.insert(0, {"role": self.internal_role, "library": None})
        return options

    def get_role_library_options(self):
        """Eligible (role, library) pairs the user holds, ordered for selection.

        Sorted by role precedence (Author > Maintainer > Contributor), then
        commit count (most active first), then library name. Computed live
        per-user; consumed by the edit dropdown, admin display, and profile page.
        """
        precedence = {
            role: index
            for index, role in enumerate(ProfileRole.library_role_precedence())
        }

        def sort_key(pair):
            role, library, commit_count = pair
            return (
                precedence.get(role, len(precedence)),
                -commit_count,
                library.display_name,
            )

        pairs = sorted(self._role_library_pairs(), key=sort_key)
        return [{"role": role, "library": library} for role, library, _ in pairs]

    def get_contributor_data(self):
        """Library contributions grouped by role for the profile bio card.

        Returns an ordered dict {role_label: [library_short_name, ...]} in role
        precedence order; a role the user holds in no library is omitted, and an
        empty dict means no contributions at all. Backed by the same source of
        truth as the edit-page role dropdown (`get_role_library_options`).

        Cached per user. The underlying roles only change on library imports,
        which drop the entry via `recompute_displayed_profile_roles`; the TTL is
        a safety net. An empty dict is a real cached value (distinct from a
        cache miss, which returns None).
        """
        cache_key = contributor_data_cache_key(self.pk)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        data = {}
        for option in self.get_role_library_options():
            label = ProfileRole(option["role"]).label
            data.setdefault(label, []).append(option["library"].display_name_short)
        cache.set(cache_key, data, settings.CONTRIBUTOR_DATA_CACHE_TIMEOUT)
        return data

    def _role_library_pairs(self):
        """(role, library, commit_count) tuples the user holds, computed live."""
        from libraries.models import Library, Commit
        from django.db.models import Count

        commit_counts = dict(
            Commit.objects.filter(author__user_id=self.pk)
            .values_list("library_version__library_id")
            .annotate(n=Count("id"))
        )

        def count_for(library_id):
            return commit_counts.get(library_id, 0)

        pairs = []
        for library in Library.objects.filter(authors=self):
            pairs.append((ProfileRole.AUTHOR.value, library, count_for(library.id)))
        maintained = Library.objects.filter(
            library_version__maintainers=self
        ).distinct()
        for library in maintained:
            pairs.append((ProfileRole.MAINTAINER.value, library, count_for(library.id)))
        contributed = Library.objects.filter(id__in=commit_counts.keys())
        for library in contributed:
            pairs.append(
                (ProfileRole.CONTRIBUTOR.value, library, count_for(library.id))
            )
        return pairs

    @cached_property
    def flag_emoji(self):
        """Flag for the user's saved country, or "" when none is set.

        `unicode_flag` is already "" for a blank CountryField, which the
        user card treats as "hide the flag overlay".
        """
        return self.country.unicode_flag

    @staticmethod
    def get_user_by_github_url(url: str):
        if not url:
            return None
        github_user = url.rstrip("/").split("/")[-1]
        return User.objects.filter(github_username=github_user).first()

    @transaction.atomic
    def delete_account(self, extended_scrub=False):
        from . import tasks

        email = self.email
        transaction.on_commit(lambda: tasks.send_account_deleted_email.delay(email))

        # Remove linked auth + preference records. Manager-level deletes are
        # idempotent, so a second run (immediate delete racing the scheduled
        # task) is a harmless no-op.
        self.socialaccount_set.all().delete()
        self.emailaddress_set.all().delete()
        Preferences.objects.filter(user=self).delete()

        # Scrub credentials, profile identity and public PII.
        self.is_active = False
        self.set_unusable_password()
        self.first_name = "John"
        self.last_name = "Doe"
        self.display_name = "John Doe"
        self.email = "deleted-{}@example.com".format(uuid.uuid4())

        # Drop the cached avatar render while its source field is still set.
        self.delete_cached_thumbnail()
        image_fields = ["profile_image"]

        # These records, fields and files are only scrubbed for the V3 deletion
        # flow - gating them keeps legacy (flag-off) deletion byte-identical to
        # production.
        if extended_scrub:
            # The local mailing-list rows store the user's email. We
            # deliberately do NOT call the Mailman/Postorius API to unsubscribe
            # - list membership is left for the user to manage in Postorius.
            self.mailing_list_subscriptions.all().delete()
            LastSeen.objects.filter(user=self).delete()
            # Badges are derived from the grants, so both have to go - and the
            # grants first: dropping one recalculates badges synchronously, and
            # in the other order that award lands in an already-scrubbed account.
            self.achievements.all().delete()
            self.badges.all().delete()

            self.github_username = ""
            self.profile_links = {}
            self.indicate_last_login_method = False
            self.image_uploaded = False

            self.delete_cached_hq_render()
            image_fields.append("hq_image")

        # File deletes are deferred to on_commit so a rolled-back transaction
        # leaves them intact.
        for field_name in image_fields:
            image = getattr(self, field_name)
            if image:
                transaction.on_commit(lambda img=image: img.delete(save=False))
            setattr(self, field_name, None)

        self.delete_permanently_at = None
        self.deletion_extended_scrub = extended_scrub
        self.save()

    def __str__(self):
        return f"{self.display_name} <{self.email}>"


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
        # Terms preference stored as a single-item list for compatability with other
        # preferences. See special handling in associated property getter and setter.
        Preferences.TERMS_CHANGED: [False],
    }


class Preferences(models.Model):
    ALL_NEWS_TYPES = sorted({"blogpost", "link", "news", "poll", "video"})
    NEWS_TYPES_WILDCARD = "all"
    OWNS_NEWS_APPROVED = "own-news-approved"
    OTHERS_NEWS_POSTED = "others-news-posted"
    OTHERS_NEWS_NEEDS_MODERATION = "others-news-needs-moderation"
    TERMS_CHANGED = "terms-changed"

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

    @property
    def allow_notification_terms_changed(self) -> bool:
        """Note special handling for this single-item preference."""
        return self.notification_allowed(self.TERMS_CHANGED)[0]

    @allow_notification_terms_changed.setter
    def allow_notification_terms_changed(self, value: bool | list[bool]):
        """Note special handling for this single-item preference."""
        if isinstance(value, bool):
            value = [value]
        self.change_notification_allowed(self.TERMS_CHANGED, value)


@receiver(post_save, sender=User)
def create_last_seen_for_user(sender, instance, created, raw, **kwargs):
    """Create LastSeen row when a User is created"""
    if raw:
        return

    if created:
        LastSeen.objects.create(user=instance, at=timezone.now())
        Preferences.objects.create(user=instance)
