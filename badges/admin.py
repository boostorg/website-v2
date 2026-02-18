from django.contrib import admin
from django.utils.safestring import mark_safe
from django.templatetags.static import static

from .models import Badge, UserBadge


class NFTUnapprovedFilter(admin.SimpleListFilter):
    title = "NFT approval status"
    parameter_name = "nft_approval"

    def lookups(self, request, model_admin):
        return (
            ("unapproved", "NFT enabled - Not approved"),
            ("approved", "NFT enabled - Approved"),
            ("not_nft", "Not NFT enabled"),
        )

    def queryset(self, request, queryset):
        if self.value() == "unapproved":
            return queryset.filter(badge__is_nft_enabled=True, approved=False)
        if self.value() == "approved":
            return queryset.filter(badge__is_nft_enabled=True, approved=True)
        if self.value() == "not_nft":
            return queryset.filter(badge__is_nft_enabled=False)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = (
        "calculator_class_reference",
        "image_preview",
        "display_name",
        "title",
        "created",
        "updated",
    )
    search_fields = (
        "title",
        "display_name",
        "calculator_class_reference",
        "description",
    )
    list_filter = ("is_nft_enabled",)

    readonly_fields = (
        "description",
        "title",
        "display_name",
        "calculator_class_reference",
        "image_light",
        "image_dark",
        "image_small_light",
        "image_small_dark",
        "image_preview_large",
        "created",
        "updated",
    )
    fields = (
        "calculator_class_reference",
        "title",
        "display_name",
        "description",
        "image_light",
        "image_dark",
        "image_small_light",
        "image_small_dark",
        "image_preview_large",
        "created",
        "updated",
    )

    class Media:
        css = {"all": ("admin/css/badge_theme_images.css",)}

    def has_add_permission(self, request):
        """Disable adding badges through admin - they should be created via update_badges task."""
        return False

    @admin.display(description="Badge")
    def image_preview(self, obj):
        html = ""
        if obj.image_light:
            image_url_light = static(f"img/badges/{obj.image_light}")
            html += f'<img src="{image_url_light}" width="30" height="30" class="badge-light-mode" />'
        if obj.image_dark:
            image_url_dark = static(f"img/badges/{obj.image_dark}")
            html += f'<img src="{image_url_dark}" width="30" height="30" class="badge-dark-mode" />'
        return mark_safe(html) if html else "-"

    @admin.display(description="Badge Preview")
    def image_preview_large(self, obj):
        html = ""
        if obj.image_light:
            image_url = static(f"img/badges/{obj.image_light}")
            html += (
                "<div><strong>Light mode:</strong><br>"
                '<div style="display: inline-block; background-color: #fff; padding: 10px;">'
                f'<img src="{image_url}" width="100" height="100" />'
                "</div></div>"
            )
        if obj.image_dark:
            image_url = static(f"img/badges/{obj.image_dark}")
            html += (
                '<div style="margin-top: 10px;"><strong>Dark mode:</strong><br>'
                '<div style="display: inline-block; background-color: #000; padding: 10px;">'
                f'<img src="{image_url}" width="100" height="100" />'
                "</div></div>"
            )
        if obj.image_small_light:
            image_url = static(f"img/badges/{obj.image_small_light}")
            html += (
                '<div style="margin-top: 10px;"><strong>Small light mode:</strong><br>'
                '<div style="display: inline-block; background-color: #fff; padding: 10px;">'
                f'<img src="{image_url}" width="100" height="100" />'
                "</div></div>"
            )
        if obj.image_small_dark:
            image_url = static(f"img/badges/{obj.image_small_dark}")
            html += (
                '<div style="margin-top: 10px;"><strong>Small dark mode:</strong><br>'
                '<div style="display: inline-block; background-color: #000; padding: 10px;">'
                f'<img src="{image_url}" width="100" height="100" />'
                "</div></div>"
            )
        return mark_safe(html) if html else "-"


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "created", "updated")
    list_filter = (
        NFTUnapprovedFilter,
        "badge",
        "created",
        "badge__calculator_class_reference",
        "badge__display_name",
    )
    search_fields = ("user__email", "user__display_name")
    readonly_fields = ("badge", "grade", "unclaimed", "created", "updated")
    fields = (
        "user",
        "badge",
        "grade",
        "approved",
        "unclaimed",
        "nft_minted",
        "published",
        "created",
        "updated",
    )
    autocomplete_fields = ["user"]

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            # make these readonly if already True
            if obj.approved:
                readonly.append("approved")
            if obj.nft_minted:
                readonly.append("nft_minted")
            # make nft_minted readonly if badge doesn't have NFT enabled
            if not obj.badge.is_nft_enabled and "nft_minted" not in readonly:
                readonly.append("nft_minted")
        return readonly
