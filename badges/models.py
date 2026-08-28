"""Data models for achievements and badges.

Every achievement a member earns is a ``UserAchievement`` row, whether it came
from an automated source or an admin's hand. Badge state (``UserBadge``) is
*derived* from the count of valid rows by ``badges.services.recalculate_badges``,
which is the only thing that should write it.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from badges.enums import BadgeLabel, TierRank, rank_order

# Sorts tiers up the ladder. Needed because the rank order lives in Python only:
# the ``rank`` column sorts alphabetically, and ``threshold`` only agrees with the
# ladder until a badge is retuned.
RANK_LADDER_ORDER = models.Case(
    *[models.When(rank=rank, then=models.Value(rank.order)) for rank in TierRank],
    output_field=models.IntegerField(),
)


def ladder_order_error(rank, threshold, thresholds_by_rank):
    """Say how ``threshold`` breaks the ladder ordering, or return ``None``.

    Thresholds must climb with the ranks, so a rung may neither meet nor undercut
    the one below it, nor reach the one above.
    """
    order = rank_order(rank)
    below = [t for r, t in thresholds_by_rank.items() if rank_order(r) < order]
    above = [t for r, t in thresholds_by_rank.items() if rank_order(r) > order]
    if below and threshold <= max(below):
        return _(
            "Must be more than %(other)s, the threshold of the rank below this one."
        ) % {"other": max(below)}
    if above and threshold >= min(above):
        return _(
            "Must be less than %(other)s, the threshold of the rank above this one."
        ) % {"other": min(above)}
    return None


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
    """One row per achievement a member has earned.

    An automatic grant points at the record that justified it through a generic
    foreign key; a manual one records the admin and their reason instead, there
    being no source row to click through to.

    Invalidation is soft: ``is_valid`` goes to ``False`` and the audit fields are
    filled in rather than the row being deleted.
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
    # Big, not plain: the models these grants point at use BigAutoField keys.
    source_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    source = GenericForeignKey("source_content_type", "source_object_id")
    # The source's own name for the evidence, which a primary key is not: the
    # commit importer deletes and re-creates rows, and one commit is stored once
    # per library version covering it. Null for manual grants.
    dedup_info = models.TextField(
        _("dedup info"),
        null=True,
        blank=True,
        help_text=_("For automatic grants: the source's stable id for the evidence."),
    )

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("For manual grants: the admin who created this achievement."),
    )
    # Blank here because automatic rows are written in bulk and are explained by
    # their source. The admin add form requires it, being the only place a grant
    # is created without one.
    grant_notes = models.TextField(
        _("grant notes"),
        blank=True,
        help_text=_("For manual grants: why this was granted by hand."),
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "achievement", "dedup_info"],
                condition=models.Q(source_type="automatic", dedup_info__isnull=False),
                name="unique_automatic_user_achievement_dedup",
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
    """The threshold for one rank of a badge.

    Tiers are append-only: retuning a threshold means retiring the row and
    creating a replacement, which ``badges.services.replace_tier`` does. Retiring
    is a soft delete, so the ``UserBadge`` rows pointing at the tier - the record
    of why a member earned a badge - survive. Only one *active* tier may exist per
    (badge, rank), and a badge's active thresholds must climb with its ranks.
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
        """Reject a duplicate active rank, or a threshold out of ladder order."""
        if not self.badge_id or not self.is_active:
            return

        siblings = BadgeTier.objects.filter(badge_id=self.badge_id, is_active=True)
        if self.pk:
            siblings = siblings.exclude(pk=self.pk)

        if siblings.filter(rank=self.rank).exists():
            raise ValidationError(
                {
                    "rank": _(
                        "An active %(rank)s tier already exists for this badge. "
                        "Change that tier's threshold instead of adding a second "
                        "%(rank)s tier."
                    )
                    % {"rank": self.get_rank_display()}
                }
            )

        # Set by a caller that edits several rungs at once and therefore has to
        # check the ladder against what it is about to save, not what is stored:
        # shifting every threshold up is legal, but each rung passes through a
        # value that collides with a sibling's stored one.
        if self.threshold is None or getattr(self, "ladder_checked_by_caller", False):
            return
        error = ladder_order_error(
            self.rank, self.threshold, dict(siblings.values_list("rank", "threshold"))
        )
        if error:
            raise ValidationError({"threshold": error})


class RevocationSource(models.TextChoices):
    """Why a ``UserBadge`` was revoked.

    A cascade revocation (the count fell below the threshold) is re-earned when
    the count recovers. A manual one survives recalculation and only comes back
    through the reinstate action.
    """

    CASCADE = "cascade", _("Cascade")
    MANUAL = "manual", _("Manual")


class UserBadgeQuerySet(models.QuerySet):
    """Queries over awarded badge tiers."""

    def active(self):
        """Badges the user currently holds, i.e. not revoked."""
        return self.filter(revoked_at__isnull=True)


class UserBadge(models.Model):
    """A member reaching a badge tier.

    Revocation is a soft delete: ``revoked_at`` is set rather than the row being
    removed, so the audit trail survives and the badge can be re-earned by
    clearing the revocation fields.
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
    # The count as it was, because later churn makes it unrecoverable and it is
    # the first thing support needs when a member asks where their badge went.
    count_at_revocation = models.PositiveIntegerField(
        _("count at revocation"),
        null=True,
        blank=True,
        help_text=_("Valid achievement count at the moment of revocation."),
    )

    objects = UserBadgeQuerySet.as_manager()

    class Meta:
        ordering = ("-awarded_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["badge", "user", "tier"],
                name="unique_user_badge_tier",
            )
        ]

    def __str__(self):
        """Human-readable label."""
        return f"{self.badge} ({self.tier.get_rank_display()}) for {self.user_id}"

    @property
    def is_active(self):
        """Whether this badge is currently held (not revoked)."""
        return self.revoked_at is None


class SyncMode(models.TextChoices):
    """Which half of the sync a run was allowed to do."""

    BACKFILL = "backfill", _("Backfill")
    RECONCILE = "reconcile", _("Reconcile")


class SyncTrigger(models.TextChoices):
    """What started a sync run."""

    COMMAND = "command", _("Command")
    ADMIN = "admin", _("Admin")
    PIPELINE = "pipeline", _("Release pipeline")


class AchievementSyncRun(models.Model):
    """One row per source per backfill or reconcile run.

    A cascade revocation can say that a member's count fell below a threshold, but
    not what moved the count. This is the record it names: what ran, when, how it
    was started, and how many grants it added or removed. Without it, a member
    losing a badge after an upstream data correction is unexplainable.

    Dry runs are not recorded. A preview writes nothing, and the reconcile
    confirmation page previews every source each time it is opened.
    """

    source_slug = models.CharField(_("source slug"), max_length=255)
    mode = models.CharField(_("mode"), max_length=20, choices=SyncMode)
    trigger = models.CharField(
        _("trigger"),
        max_length=20,
        choices=SyncTrigger,
        default=SyncTrigger.COMMAND,
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("The admin who started this run, where a person started it."),
    )
    started_at = models.DateTimeField(_("started at"), default=timezone.now)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    added = models.PositiveIntegerField(_("grants added"), default=0)
    removed = models.PositiveIntegerField(_("grants removed"), default=0)
    members_changed = models.PositiveIntegerField(_("members changed"), default=0)
    refused = models.BooleanField(
        _("refused"),
        default=False,
        help_text=_("The source yielded nothing, so stale grants were left alone."),
    )
    error = models.TextField(
        _("error"),
        blank=True,
        help_text=_(
            "What the run raised, where it did not finish. Deletions are chunked "
            "rather than wrapped in one transaction, so a run that died part way "
            "left the grants it had already removed removed."
        ),
    )

    class Meta:
        ordering = ("-started_at",)
        verbose_name = _("achievement sync run")

    def __str__(self):
        """Human-readable label."""
        return f"{self.get_mode_display()} of '{self.source_slug}' #{self.pk}"
