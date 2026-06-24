"""Data models for the achievements and badges system.

A unified, event-driven design: every achievement a user earns is recorded as a
``UserAchievement`` row, regardless of whether it came from an automated source
(GitHub activity, mailing-list posts, ...) or a manual admin grant. Badge tier
state (``UserBadge``) is *derived* from the count of valid ``UserAchievement``
rows via ``badges.services.recalculate_badges`` - no code path should write to
``UserBadge`` directly outside of that service and the admin revocation action.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from badges.enums import BadgeLabel, TierRank

# Orders tiers up the ladder, bronze to diamond. Needed because the declared
# order of the ranks exists only in Python: ordering by the ``rank`` column
# sorts alphabetically (bronze, diamond, gold, platinum, silver), and ordering
# by threshold only agrees with the ladder while a badge has never been retuned
# - see ``badges.enums``.
RANK_LADDER_ORDER = models.Case(
    *[models.When(rank=rank, then=models.Value(rank.order)) for rank in TierRank],
    output_field=models.IntegerField(),
)


class SourceType(models.TextChoices):
    """How a ``UserAchievement`` was granted."""

    AUTOMATIC = "automatic", _("Automatic")
    MANUAL = "manual", _("Manual")


class Achievement(models.Model):
    """Registry of all possible achievement types in the system."""

    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=255, unique=True)
    description = models.TextField(_("description"), blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        """Human-readable label."""
        return self.name


class UserAchievement(models.Model):
    """One row per achievement instance earned by a user.

    Supports both automatic and manual grant sources. Automatic grants point at
    the originating record through a generic foreign key
    (``source_content_type`` + ``source_object_id``); manual grants instead
    record the admin who created them in ``granted_by`` and their reason in
    ``grant_notes``, there being no source row to click through to.

    Invalidation is a soft change: ``is_valid`` is set to ``False`` and the
    audit fields are populated rather than deleting the row.
    """

    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="user_achievements",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    is_valid = models.BooleanField(_("is valid"), default=True)
    invalidated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Admin who invalidated this achievement."),
    )
    invalidated_at = models.DateTimeField(_("invalidated at"), null=True, blank=True)
    invalidation_notes = models.TextField(_("invalidation notes"), blank=True)

    source_type = models.CharField(
        _("source type"),
        max_length=20,
        choices=SourceType,
        default=SourceType.AUTOMATIC,
    )
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("For automatic grants: the model that triggered the grant."),
    )
    # Big, not plain: every model a source iterator yields (Commit, Entry,
    # Review, Library, LibraryVersion) has a BigAutoField primary key.
    source_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    source = GenericForeignKey("source_content_type", "source_object_id")

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("For manual grants: the admin who created this achievement."),
    )
    # Blank at this level because the ~20,800 automatic rows are created by
    # ``bulk_create`` and have a source record to explain them. The admin add form
    # is where it becomes required, which is the only place a grant has no source.
    grant_notes = models.TextField(
        _("grant notes"),
        blank=True,
        help_text=_("For manual grants: why this was granted by hand."),
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "achievement",
                    "source_content_type",
                    "source_object_id",
                ],
                condition=models.Q(source_type="automatic"),
                name="unique_automatic_user_achievement_source",
            )
        ]

    def __str__(self):
        """Human-readable label."""
        return f"{self.achievement} for {self.user_id} ({self.source_type})"


class Badge(models.Model):
    """Maps a badge category to an achievement type, with a description."""

    label = models.CharField(
        _("label"),
        max_length=50,
        choices=BadgeLabel,
        unique=True,
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="badges",
        help_text=_("Which achievement type feeds this badge."),
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ("label",)

    def __str__(self):
        """Human-readable label."""
        return self.get_label_display()


class BadgeTier(models.Model):
    """Configures the threshold for a single rank within a badge.

    Tiers are append-only records: ``rank`` and ``threshold`` are fixed once
    created. Retuning a threshold means retiring the existing tier and creating
    a replacement, which ``badges.services.replace_tier`` does and the badge
    admin page presents as simply editing the number. Retiring is a *soft
    delete* (``is_active=False``) so the ``UserBadge`` rows that reference the
    tier - the record of why a member earned a badge - are preserved. Only one
    *active* tier may exist per (badge, rank).
    """

    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="tiers",
    )
    rank = models.CharField(
        _("rank"),
        max_length=20,
        choices=TierRank,
    )
    threshold = models.PositiveIntegerField(
        _("threshold"),
        help_text=_(
            "Number of valid achievements required to reach this rank. "
            "Changing it applies to new earners only: members who already "
            "reached the old threshold keep their badge."
        ),
    )

    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Retired tiers stop awarding badges but keep their history, "
            "including the badges already earned against them."
        ),
    )
    deactivated_at = models.DateTimeField(_("deactivated at"), null=True, blank=True)
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Admin who deactivated this tier."),
    )

    class Meta:
        ordering = ("threshold",)
        constraints = [
            models.UniqueConstraint(
                fields=["badge", "rank"],
                condition=models.Q(is_active=True),
                name="unique_active_badgetier_per_rank",
            )
        ]

    def __str__(self):
        """Human-readable label."""
        return f"{self.badge} - {self.get_rank_display()} (>= {self.threshold})"

    def clean(self):
        """Block a second *active* tier for the same badge and rank."""
        if self.badge_id and self.is_active:
            clash = BadgeTier.objects.filter(
                badge_id=self.badge_id, rank=self.rank, is_active=True
            )
            if self.pk:
                clash = clash.exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError(
                    {
                        "rank": _(
                            "An active %(rank)s tier already exists for this "
                            "badge. Change that tier's threshold instead of "
                            "adding a second %(rank)s tier."
                        )
                        % {"rank": self.get_rank_display()}
                    }
                )


class RevocationSource(models.TextChoices):
    """Why a ``UserBadge`` was revoked.

    Cascade revocations (the achievement count fell below the threshold) are
    automatically re-earned when the count recovers. Manual revocations (an
    admin used the revoke action) survive recalculation and only come back via
    the reinstate action.
    """

    CASCADE = "cascade", _("Cascade")
    MANUAL = "manual", _("Manual")


class UserBadgeQuerySet(models.QuerySet):
    """Queries over awarded badge tiers."""

    def active(self):
        """Badges the user currently holds, i.e. not revoked."""
        return self.filter(revoked_at__isnull=True)


class UserBadge(models.Model):
    """Records a user reaching a badge tier, with revocation audit fields.

    Revocation is a soft-delete: ``revoked_at`` is set rather than deleting the
    row, so the audit trail (who revoked, when, why) is preserved and badges can
    be re-earned by clearing the revocation fields.
    """

    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="user_badges",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="badges",
    )
    tier = models.ForeignKey(
        BadgeTier,
        on_delete=models.PROTECT,
        related_name="user_badges",
        help_text=_(
            "The tier that justified this badge. A tier with badges awarded "
            "against it cannot be hard-deleted."
        ),
    )
    awarded_at = models.DateTimeField(_("awarded at"), default=timezone.now)

    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Admin who revoked this badge."),
    )
    revocation_notes = models.TextField(_("revocation notes"), blank=True)
    revocation_source = models.CharField(
        _("revocation source"),
        max_length=20,
        choices=RevocationSource,
        blank=True,
        default="",
        help_text=_(
            "Manual revocations are not re-earned automatically; cascade "
            "revocations are, once the achievement count recovers."
        ),
    )

    objects = UserBadgeQuerySet.as_manager()

    class Meta:
        ordering = ("-awarded_at",)
        unique_together = ("badge", "user", "tier")

    def __str__(self):
        """Human-readable label."""
        return f"{self.badge} ({self.tier.get_rank_display()}) for {self.user_id}"

    @property
    def is_active(self):
        """Whether this badge is currently held (not revoked)."""
        return self.revoked_at is None
