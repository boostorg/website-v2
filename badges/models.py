from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Badge(models.Model):
    """Badge that can be awarded to users."""

    title = models.CharField(_("title"), max_length=200)
    display_name = models.CharField(_("display name"), max_length=100, blank=True)
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Description of what this badge represents"),
    )
    calculator_class_reference = models.CharField(
        _("calculator class reference"),
        max_length=255,
        unique=True,
        help_text=_(
            "lookup field for class_reference in badge Calculator implementations"
        ),
    )
    # Reference to a static file path (e.g., 'badges/github-contributor.svg')
    image_light = models.CharField(
        _("image path (light mode)"),
        max_length=255,
        help_text=_("Path to badge image for light mode in static directory"),
    )
    image_dark = models.CharField(
        _("image path (dark mode)"),
        max_length=255,
        help_text=_("Path to badge image for dark mode in static directory"),
    )
    image_small_light = models.CharField(
        _("small image path (light mode)"),
        max_length=255,
        help_text=_("Path to small badge image for light mode in static directory"),
    )
    image_small_dark = models.CharField(
        _("small image path (dark mode)"),
        max_length=255,
        help_text=_("Path to small badge image for dark mode in static directory"),
    )
    is_nft_enabled = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["calculator_class_reference"]

    def __str__(self):
        return self.display_name or self.calculator_class_reference

    def __repr__(self):
        return f"<Badge: {self.calculator_class_reference} (id={self.pk})>"


class UserBadge(models.Model):
    """Through table for User-Badge relationship with grade."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_badges",
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="user_badges",
    )
    grade = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Grade or level of this badge for the user"),
    )
    # all defaults below are for safety, for the NFT badges.
    approved = models.BooleanField(default=False)  # minting approved manually by admin
    nft_minted = models.BooleanField(default=False)  # is in common vault if unclaimed
    nft_transfer_url = models.TextField(blank=True, null=True)
    unclaimed = models.BooleanField(
        default=False,
        help_text=_("Default false, true when badge is_nft_enabled=True"),
    )
    published = models.BooleanField(
        default=False, help_text=_("Visible on the user's profile")
    )  # visible in the user's profile

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["user", "badge"]]
        ordering = ["-created"]

    def __str__(self):
        return f"{self.user.display_name} - {self.badge.display_name}, ({self.grade})"

    def __repr__(self):
        return f"<UserBadge: user_id={self.user_id}, badge_id={self.badge_id}>"
