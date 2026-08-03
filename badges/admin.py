"""Django admin for the achievements and badges system.

Superusers (and anyone with the relevant per-model permissions) can manage
achievement types, configure badge tiers, manually grant achievements, and
invalidate / revoke with a required audit note.
"""

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Prefetch, Q
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import NoReverseMatch, path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import Truncator

from badges.enums import TierRank
from badges.forms import NotesActionForm
from badges.models import (
    RANK_LADDER_ORDER,
    Achievement,
    AchievementSyncRun,
    Badge,
    BadgeTier,
    RevocationSource,
    SourceType,
    SyncTrigger,
    UserAchievement,
    UserBadge,
    ladder_order_error,
)
from badges.services import (
    achievement_pairs,
    deactivate_tier,
    reactivate_tier,
    recalculate_badges,
    recalculate_many,
    replace_tier,
    sync_source,
)
from badges.sources import AUTOMATIC_SLUGS
from badges.summary import user_badge_summary
from badges.tasks import (
    backfill_achievements_task,
    recalculate_all_badges_task,
    reconcile_achievements_task,
)
from core.admin_buttons import TaskButton, TaskButtonAdminMixin

# Derived from the wired iterators, so the options cannot drift from what the
# commands will accept. The slugs match the catalogue's names.
SOURCE_CHOICES = tuple(
    (slug, slug.replace("-", " ").title()) for slug in sorted(AUTOMATIC_SLUGS)
)

RECONCILE_PERMISSION = "badges.delete_userachievement"

# Wraps the object tools in the left-aligned cluster below the page title. The
# task-button template extends the same one, so a page that grows a button later
# keeps the layout it already had.
ADMIN_ACTIONS_CHANGE_LIST = "admin/admin_actions_change_list.html"


def reconcile_results(slugs, user_ids=None, dry_run=False, actor=None):
    """Sync each named source, skipping any the catalogue has no row for.

    Returns ``(results, unseeded)``. The management command refuses to run at all
    on an unseeded slug; an admin page has to be gentler than that, because a page
    that raises is worse than one that says the catalogue is incomplete.
    """
    achievements = {
        achievement.slug: achievement
        for achievement in Achievement.objects.filter(slug__in=slugs)
    }
    results = [
        sync_source(
            slug,
            achievements[slug],
            user_ids=user_ids,
            dry_run=dry_run,
            trigger=SyncTrigger.ADMIN,
            actor=actor,
        )
        for slug in sorted(slugs)
        if slug in achievements
    ]
    return results, sorted(set(slugs) - set(achievements))


def reconcile_apply(slugs, user_ids=None, actor=None):
    """Sync the named sources for real, then recalculate the members that moved.

    ``sync_source`` deliberately leaves the recalculation to its caller. Deletions
    have already recalculated themselves through ``post_delete``; additions have
    not, and revisiting a pair is idempotent.
    """
    results, _ = reconcile_results(slugs, user_ids=user_ids, actor=actor)
    achievements = {
        achievement.slug: achievement.pk
        for achievement in Achievement.objects.filter(
            slug__in=[result.slug for result in results]
        )
    }
    for result in results:
        for user_id in result.changed:
            recalculate_badges(user_id, achievements[result.slug])
    return (
        sum(result.added for result in results),
        sum(result.removed for result in results if not result.refused),
    )


def reconcile_preview(slugs, user_ids=None, scope_label=""):
    """Dry-run the named sources and describe what a real run would change.

    Shared by the changelist button and the per-member page so that both show the
    same numbers, arrived at the same way. The walk is the expensive part and it
    happens in the request: measured at a few seconds against a full copy of the
    Boost data, where the commits table is the long pole.
    """
    results, unseeded = reconcile_results(slugs, user_ids=user_ids, dry_run=True)
    rows = [
        {"label": result.slug, "detail": result.describe(), "warning": result.refused}
        for result in results
    ]
    rows += [
        {
            "label": slug,
            "detail": "No achievement row: the catalogue is incomplete.",
            "warning": True,
        }
        for slug in unseeded
    ]

    added = sum(result.added for result in results)
    removed = sum(result.removed for result in results if not result.refused)
    refused = [result.slug for result in results if result.refused]
    where = scope_label or "every member"

    if added or removed:
        changes = []
        if added:
            changes.append(f"add {added} automatic achievement(s)")
        if removed:
            changes.append(f"remove {removed}")
        summary = (
            f"This would {' and '.join(changes)} for {where}. Manual grants are not "
            "touched. Badges follow in both directions: a tier left below its "
            "threshold is revoked as a cascade, and one back above it is re-earned."
        )
    elif refused:
        summary = f"Nothing can be removed for {where} - see the warning below."
    else:
        summary = (
            f"Nothing to reconcile for {where}: every automatic achievement already "
            "agrees with its source."
        )

    warning = ""
    if unseeded:
        warning = (
            "Not safe to run: no achievement row for "
            f"{', '.join(unseeded)}. Run migrations first."
        )
    elif refused:
        warning = (
            f"{', '.join(refused)} yielded nothing at all, which is more likely a "
            "broken import than a source that is genuinely empty, so those grants "
            "are left alone. Use the reconcile_achievements command with "
            "--allow-empty if the emptiness is real."
        )

    return {
        "title": "Reconcile achievements",
        "summary": summary,
        "rows": rows,
        "warning": warning,
        # Nothing to apply is not a decision worth offering, and an incomplete
        # catalogue is one the command would refuse anyway.
        "can_apply": bool(added or removed) and not unseeded,
    }


def _reconcile_button_preview(request, slug):
    """Dry-run whichever sources the changelist button was pointed at."""
    return reconcile_preview([slug] if slug else AUTOMATIC_SLUGS)


BACKFILL_BUTTON = TaskButton(
    name="backfill",
    label="Backfill achievements",
    task=backfill_achievements_task,
    success_message="Achievements are being backfilled in the background.",
    busy_message="A backfill is already queued or running; not starting another one.",
    argument="slug",
    choice_label="Source",
    choices=SOURCE_CHOICES,
    all_label="All sources",
    description=(
        "Grants the automatic achievements the sources support and this site is "
        "missing, then awards any badge that reaches its threshold. It only ever "
        "adds, so it is safe to run at any time; this is what runs itself after "
        "each release. Use Reconcile instead if an achievement needs removing."
    ),
)
RECONCILE_BUTTON = TaskButton(
    name="reconcile",
    label="Reconcile achievements",
    task=reconcile_achievements_task,
    success_message=(
        "Achievements are being reconciled with their sources in the background."
    ),
    busy_message=(
        "A reconciliation is already queued or running; not starting another one."
    ),
    argument="slug",
    choice_label="Source",
    choices=SOURCE_CHOICES,
    all_label="All sources",
    # This one deletes rows, which the change permission does not cover.
    permission=RECONCILE_PERMISSION,
    confirm=_reconcile_button_preview,
    description=(
        "Makes the automatic achievements agree with their sources in both "
        "directions: it adds the ones a source now supports and removes the ones it "
        "no longer does, such as a commit reassigned to another author or a news "
        "post deleted. Badges follow either way. Manually granted achievements are "
        "never touched, and you see what would change before anything does."
    ),
)
RECALCULATE_BUTTON = TaskButton(
    name="recalculate",
    label="Recalculate badges",
    task=recalculate_all_badges_task,
    success_message="Badges are being recalculated in the background.",
    busy_message=(
        "A recalculation is already queued or running; not starting another one."
    ),
    description=(
        "Rebuilds every member's badges from the achievements already on record: it "
        "awards a tier whose threshold is met and revokes one that has fallen below "
        "it. No achievement is added, removed or changed, so this is the safe thing "
        "to run after editing a badge's thresholds."
    ),
)


def user_summary_url(user_id):
    """The per-user badge page, which three admins link to."""
    return reverse("admin:badges_userbadge_user_summary", args=[user_id])


class BadgeStatusFilter(admin.SimpleListFilter):
    """Held or revoked, which is the only question anyone asks of ``revoked_at``.

    Filtering the field directly gives Django's date filter ("Past 7 days", "This
    year"), which answers a question nobody has.
    """

    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        """The two states a badge can be in."""
        return (("held", "Held"), ("revoked", "Revoked"))

    def queryset(self, request, queryset):
        """Partition on the revocation timestamp."""
        if self.value() == "held":
            return queryset.filter(revoked_at__isnull=True)
        if self.value() == "revoked":
            return queryset.filter(revoked_at__isnull=False)
        return queryset


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """CRUD admin for achievement types, with the slug frozen after creation.

    The slug is the join key between an ``Achievement`` row and the code that
    refers to it (``badges.sources.BACKFILL_ITERATORS``, keyed by
    ``AchievementSlug``). Renaming one would silently detach its backfill source
    with no error anywhere, so it is only editable on the add form.
    """

    change_list_template = ADMIN_ACTIONS_CHANGE_LIST
    list_display = ("name", "slug", "badge", "grants", "created_at")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    def get_queryset(self, request):
        """The wiring columns, without a query per row."""
        return (
            super()
            .get_queryset(request)
            .prefetch_related("badges")
            .annotate(
                grant_count=Count(
                    "user_achievements",
                    filter=Q(user_achievements__is_valid=True),
                )
            )
        )

    @admin.display(description="Badge")
    def badge(self, obj):
        """The badge this type feeds, if any.

        An achievement with no badge accumulates grants that can never become
        anything, which is invisible from anywhere else in the admin.
        """
        labels = [badge.get_label_display() for badge in obj.badges.all()]
        return ", ".join(labels) if labels else "None - awards nothing"

    @admin.display(description="Valid grants", ordering="grant_count")
    def grants(self, obj):
        """How many valid grants exist, which is what thresholds count."""
        return obj.grant_count

    def has_delete_permission(self, request, obj=None):
        """Never delete an achievement type.

        With badges awarded it is a ``ProtectedError`` dead end anyway. Without
        them it cascades: every grant for the type is destroyed, and the wired
        backfill source loses the row it needs. Retire the badge's tiers instead.
        """
        return False

    def get_readonly_fields(self, request, obj=None):
        """Freeze the slug once the achievement exists."""
        if obj is None:
            return ()
        return ("slug",)

    def get_prepopulated_fields(self, request, obj=None):
        """Only prepopulate on the add form, where the slug is still editable."""
        if obj is None:
            return self.prepopulated_fields
        return {}


class ActiveBadgeTierInlineFormSet(BaseInlineFormSet):
    """Validate the ladder this request is about to save, not the stored one.

    Two things can only be judged across the whole submitted set: a rank claimed by
    two rows, and the thresholds' ordering. Shifting every rung up is legal even
    though each rung passes through a value that collides with a sibling's stored
    threshold, so the per-row model check is handed over here.
    """

    def add_fields(self, form, index):
        """Tell each row that this formset owns the ladder ordering check."""
        super().add_fields(form, index)
        form.instance.ladder_checked_by_caller = True

    def clean(self):
        """Add field errors before the conditional database constraint can fire."""
        super().clean()
        if any(self.errors):
            return

        seen = set()
        submitted = {}
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            rank = form.cleaned_data.get("rank")
            if not rank:
                continue
            if rank in seen:
                form.add_error(
                    "rank",
                    f"Only one active {TierRank(rank).label} tier is allowed "
                    "for a badge.",
                )
            seen.add(rank)
            threshold = form.cleaned_data.get("threshold")
            if threshold is not None:
                submitted[rank] = threshold

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            rank = form.cleaned_data.get("rank")
            threshold = form.cleaned_data.get("threshold")
            if not rank or threshold is None:
                continue
            error = ladder_order_error(
                rank, threshold, {r: t for r, t in submitted.items() if r != rank}
            )
            if error:
                form.add_error("threshold", error)


class ActiveBadgeTierInline(admin.TabularInline):
    """A badge's live ladder, edited in place.

    Tiers are append-only records, so an edit here never updates the row:
    ``BadgeAdmin.save_formset`` retires the old tier and creates a replacement,
    and removing a row retires it. Both are what preserve the members who
    already reached the old threshold - see ``badges.services.replace_tier``.
    """

    model = BadgeTier
    formset = ActiveBadgeTierInlineFormSet
    fields = ("rank", "threshold")
    # One blank row, because the "Add another" link needs JavaScript. Capped at
    # the number of ranks, which is also the point at which the constraint on
    # (badge, rank) would start rejecting additions.
    extra = 1
    max_num = len(TierRank)
    verbose_name = "active tier"
    verbose_name_plural = "active tiers"

    def get_queryset(self, request):
        """The live ladder only; retired tiers are linked from the badge form."""
        return (
            super()
            .get_queryset(request)
            .filter(is_active=True)
            .order_by(RANK_LADDER_ORDER)
        )


@admin.register(BadgeTier)
class BadgeTierAdmin(admin.ModelAdmin):
    """The tier record, kept for history and recovery rather than for tuning.

    Tiers are configured on the badge page. What is left here is what that page
    deliberately does not show: the retired rows, and the ``reactivate`` action
    that undoes a mistaken retirement. Rows stay immutable - ``rank`` and
    ``threshold`` cannot be edited, because updating one in place would revoke
    the members who reached the old threshold.
    """

    change_list_template = ADMIN_ACTIONS_CHANGE_LIST
    list_display = ("badge", "rank", "threshold", "is_active", "deactivated_at")
    list_filter = ("is_active", "rank", "badge")
    search_fields = ("badge__label", "rank")
    autocomplete_fields = ("badge",)
    actions = ["reactivate"]

    def get_ordering(self, request):
        """Group by badge, then up the ladder, then oldest threshold first.

        The model's default ordering is by threshold alone, which interleaves
        every badge's bronze row. Threshold is also not the ladder on this page in
        particular: it is the one that shows retired rows, so a badge that has been
        retuned has a bronze at 1 and a bronze at 6 sitting either side of its gold.

        Returned from here rather than set as ``ordering``, because the admin
        system check validates that attribute against real model fields and
        ``rank_order`` is an annotation.
        """
        return ("badge__label", "rank_order", "threshold")

    def get_queryset(self, request):
        """Annotate the ladder position, then order on it.

        Not ``super().get_queryset()`` plus an annotation: ``ModelAdmin`` applies
        the ordering itself, and ``order_by`` validates a plain name against the
        queryset it is handed, so the annotation has to exist first.
        """
        return (
            self.model._default_manager.get_queryset()
            .annotate(rank_order=RANK_LADDER_ORDER)
            .order_by(*self.get_ordering(request))
        )

    def get_model_perms(self, request):
        """Keep this off the index: tiers are configured on the badge page.

        Two entry points for the same thing is the confusion this layer removes.
        URLs, the badge page's retired-tier link and the ``reactivate`` action
        all keep working; only the index and sidebar listings drop it.
        """
        return {}

    def get_readonly_fields(self, request, obj=None):
        """Lock rank/threshold once the tier exists; status is always derived."""
        if obj is None:
            return ("is_active", "deactivated_at", "deactivated_by")
        return (
            "badge",
            "rank",
            "threshold",
            "is_active",
            "deactivated_at",
            "deactivated_by",
        )

    def get_deleted_objects(self, objs, request):
        """Report no cascade - deletion is soft, so nothing is actually removed.

        Without this, the protected ``UserBadge`` references would block the
        delete confirmation page before the soft delete can run.
        """
        return [str(obj) for obj in objs], {}, set(), []

    def delete_model(self, request, obj):
        """Soft-delete a single tier."""
        deactivate_tier(obj, actor=request.user)

    def delete_queryset(self, request, queryset):
        """Soft-delete tiers selected via the bulk delete action."""
        for tier in queryset:
            deactivate_tier(tier, actor=request.user)

    @admin.action(description="Reactivate selected retired tiers")
    def reactivate(self, request, queryset):
        """Undo a retirement, which the change form cannot do.

        A retired tier's form has no editable fields, so without this a mistaken
        retirement can only be undone by adding a replacement tier - which leaves
        the original's badges behind and duplicates the rank.
        """
        reactivated, refused = 0, []
        for tier in queryset.filter(is_active=False):
            try:
                reactivate_tier(tier)
            except ValidationError:
                refused.append(str(tier))
            else:
                reactivated += 1
        self.message_user(request, f"Reactivated {reactivated} tier(s).")
        if refused:
            self.message_user(
                request,
                "Skipped tiers whose rank already has an active tier: "
                f"{', '.join(refused)}. Retire the replacement first.",
                level=messages.WARNING,
            )


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    """The configuration page for a badge: its achievement and its ladder.

    A badge, its description and all five of its tiers are one form and one
    save. What is *not* an admin action is inventing a new category: ``label``
    is constrained to ``badges.enums.BadgeLabel`` because the label chooses the
    display asset, so an empty-looking dropdown means every category is already
    in use, not that something is broken. A genuinely new one needs an enum
    member and a ``badges.catalogue`` entry, which is a deploy.
    """

    change_list_template = ADMIN_ACTIONS_CHANGE_LIST
    list_display = ("label", "achievement", "ladder", "holders", "source_wired")
    list_filter = ("label",)
    search_fields = ("label", "achievement__name")
    autocomplete_fields = ("achievement",)
    inlines = [ActiveBadgeTierInline]

    def get_queryset(self, request):
        """Everything the health columns read, without a query per row.

        ``to_attr`` rather than filtering ``tiers`` in place, so the inline's own
        queryset is unaffected.
        """
        return (
            super()
            .get_queryset(request)
            .select_related("achievement")
            .prefetch_related(
                Prefetch(
                    "tiers",
                    queryset=BadgeTier.objects.filter(is_active=True).order_by(
                        RANK_LADDER_ORDER
                    ),
                    to_attr="active_tiers",
                )
            )
            .annotate(
                holder_count=Count(
                    "user_badges__user",
                    filter=Q(user_badges__revoked_at__isnull=True),
                    distinct=True,
                )
            )
        )

    @admin.display(description="Ladder")
    def ladder(self, obj):
        """The live thresholds, bronze to diamond.

        A badge with no active tiers is the silent misconfiguration: it is
        wired, it looks complete, and it can never award anything.
        """
        if not obj.active_tiers:
            return "No tiers - awards nothing"
        return " / ".join(str(tier.threshold) for tier in obj.active_tiers)

    @admin.display(description="Holders", ordering="holder_count")
    def holders(self, obj):
        """Members currently holding any tier of this badge, counted once each."""
        return obj.holder_count

    @admin.display(boolean=True, description="Automatic")
    def source_wired(self, obj):
        """Whether a backfill iterator feeds this badge's achievement.

        ``documentation`` and ``mailing-list`` deliberately have none, so they
        only ever move on a manual grant. That is worth seeing on the page
        rather than knowing.
        """
        return obj.achievement.slug in AUTOMATIC_SLUGS

    def save_formset(self, request, form, formset, change):
        """Apply the append-only tier rules: an edit replaces, a delete retires.

        ``formset.save(commit=False)`` fills in ``new_objects``,
        ``changed_objects`` and ``deleted_objects`` without writing or deleting
        anything, which is what lets a removed row become a retirement instead.
        The whole request is already wrapped in a transaction by
        ``ModelAdmin.changeform_view``.
        """
        if formset.model is not BadgeTier:
            super().save_formset(request, form, formset, change)
            return

        formset.save(commit=False)
        for tier in formset.deleted_objects:
            deactivate_tier(tier, actor=request.user)
            self.message_user(
                request,
                f"Retired {tier.get_rank_display()} (>= {tier.threshold}). It "
                "no longer awards badges; the members who earned it keep it.",
            )
        # The inline exposes only rank and threshold, and both are append-only,
        # so every changed row is a replacement rather than an update.
        for tier, _changed_fields in formset.changed_objects:
            retired, replacement = replace_tier(tier, actor=request.user)
            self.message_user(
                request,
                f"Retired {retired.get_rank_display()} (>= {retired.threshold}) "
                f"and created {replacement.get_rank_display()} "
                f"(>= {replacement.threshold}). Members who already earned "
                f"{retired.get_rank_display()} keep it; the new threshold "
                "applies from now on.",
            )
        for tier in formset.new_objects:
            tier.save()

    def has_delete_permission(self, request, obj=None):
        """Never delete a badge; retire its tiers instead.

        ``UserBadge.tier`` is protected, so this is a dead end once anything has
        been awarded, and a silent cascade over the tiers when it has not.
        """
        return False

    def get_fields(self, request, obj=None):
        """The retired-tier link needs a badge to scope itself to."""
        fields = ["label", "achievement", "description"]
        if obj is not None:
            fields.append("retired_tiers")
        return fields

    def get_readonly_fields(self, request, obj=None):
        """Freeze the achievement once the badge exists.

        Repointing a badge at a different achievement would leave every awarded
        ``UserBadge`` derived from a count that no longer feeds it, and nothing
        recalculates the members of the achievement it used to track.
        """
        if obj is None:
            return ()
        return ("achievement", "retired_tiers")

    @admin.display(description="Retired tiers")
    def retired_tiers(self, obj):
        """A link out to the history the live ladder deliberately hides.

        A second inline for the retired rows would be the obvious thing, but two
        inlines of the same model share a formset prefix and collide.
        """
        count = obj.tiers.filter(is_active=False).count()
        if not count:
            return "None."
        url = (
            f"{reverse('admin:badges_badgetier_changelist')}"
            f"?is_active__exact=0&badge__id__exact={obj.pk}"
        )
        return format_html(
            '<a href="{}">{} retired tier(s)</a> - kept because members still '
            "hold the badges earned against them.",
            url,
            count,
        )


class NotesActionMixin:
    """The confirmation page shared by the actions that require an audit note.

    Invalidating an achievement and revoking a badge are different writes, but
    both are "explain yourself first, then apply to the selection", and both used
    to restate the same eight-key template context - which is exactly the kind of
    pair that drifts.
    """

    def notes_action(self, request, queryset, *, title, action, submit_label, apply):
        """Collect a required note, then hand it to ``apply``.

        ``apply(notes)`` does the write and reports its own count, because what
        counts as applied differs: one of the two saves row by row so the
        ``post_save`` signal runs, the other updates in bulk.

        Returns ``None`` once the note is in and the work is done, which is how an
        admin action says "go back to the changelist".
        """
        if "apply" in request.POST:
            form = NotesActionForm(request.POST)
            if form.is_valid():
                apply(form.cleaned_data["notes"])
                return None
        else:
            form = NotesActionForm()

        opts = self.model._meta
        return render(
            request,
            "admin/badges/notes_action.html",
            {
                "title": title,
                "objects": queryset,
                "form": form,
                "action": action,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                "opts": opts,
                "submit_label": submit_label,
                # Named rather than left as "../": the action posts to the
                # changelist, so a relative hop lands on the app index instead of
                # back where the admin came from.
                "cancel_url": reverse(
                    f"admin:{opts.app_label}_{opts.model_name}_changelist"
                ),
            },
        )


class MemberSummaryLinkMixin:
    """A ``user`` column leading to the per-user badge page.

    On both of these changelists the question about a row is almost always a
    question about the member rather than the row. The row itself stays reachable
    through the first column, which is what the changelist links by default.
    """

    @admin.display(description="User", ordering="user__email")
    def user_link(self, obj):
        """The member, linking to why they hold what they hold."""
        return format_html(
            '<a href="{}">{}</a>', user_summary_url(obj.user_id), obj.user
        )


@admin.register(UserAchievement)
class UserAchievementAdmin(
    MemberSummaryLinkMixin, NotesActionMixin, TaskButtonAdminMixin, admin.ModelAdmin
):
    """Admin for per-user achievement grants.

    Manual creation auto-populates ``source_type`` and ``granted_by``, and requires
    a note. An existing row is then a record: the ``invalidate`` and ``revalidate``
    actions are the only way to change its state, both of which recalculate badges
    through the ``post_save`` signal. ``invalidate`` collects a required audit note
    of its own.
    """

    task_buttons = (BACKFILL_BUTTON, RECONCILE_BUTTON)
    list_display = (
        "achievement",
        "user_link",
        "source_type",
        "source_link",
        "grant_note",
        "is_valid",
        "created_at",
    )
    list_filter = ("is_valid", "source_type", "achievement")
    list_select_related = ("achievement", "user")
    search_fields = (
        "user__email",
        "user__display_name",
        "achievement__name",
        "grant_notes",
    )
    autocomplete_fields = ("achievement", "user")
    readonly_fields = (
        "created_at",
        "invalidated_by",
        "invalidated_at",
        "granted_by",
    )
    actions = ["invalidate", "revalidate"]
    add_fieldsets = ((None, {"fields": ("user", "achievement", "grant_notes")}),)

    def has_delete_permission(self, request, obj=None):
        """Invalidation is a soft delete on purpose; keep the audit trail."""
        return False

    def get_queryset(self, request):
        """Prefetch the generic source so the column costs one query per type."""
        return super().get_queryset(request).prefetch_related("source")

    @admin.display(description="Source")
    def source_link(self, obj):
        """The row that justified an automatic grant.

        Without this, 138 commit grants are 138 identical lines and there is no
        way to see what any of them came from. Not every source model is
        registered in the admin - ``news.Entry`` is not - so an unreachable one
        falls back to its own label.
        """
        source = obj.source
        if source is None:
            return "-"
        meta = source._meta
        try:
            url = reverse(
                f"admin:{meta.app_label}_{meta.model_name}_change", args=[source.pk]
            )
        except NoReverseMatch:
            return str(source)
        return format_html('<a href="{}">{}</a>', url, source)

    @admin.display(description="Note")
    def grant_note(self, obj):
        """The reason a manual grant was given, truncated to stay scannable.

        Sits beside ``source_link`` because the two answer the same question from
        opposite ends: an automatic grant is explained by the row it came from, a
        manual one only by whoever typed it. Truncated rather than omitted, because
        the alternative is opening every row to find out why it exists.
        """
        return Truncator(obj.grant_notes).chars(60) or "-"

    def get_form(self, request, obj=None, **kwargs):
        """Require the note on a manual grant, and only there.

        Not ``blank=False`` on the model: that would also bind the automatic rows,
        which are created by ``bulk_create`` (so unvalidated anyway) and already
        have a source record explaining them. Mutating ``base_fields`` is safe
        because ``modelform_factory`` builds a new class per call.
        """
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            form.base_fields["grant_notes"].required = True
        return form

    def get_fieldsets(self, request, obj=None):
        """Collect only what a manual grant means.

        ``save_model`` forces ``source_type`` and ``granted_by``, and the generic
        foreign key belongs to automatic grants: a manual row pointing at a source
        is not covered by the uniqueness constraint, so the same source would
        count twice.
        """
        if obj is None:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        """Make an existing grant a read-only record.

        Moving a grant to another user or achievement recalculates only the pair
        it moved *to*, so the pair it left keeps a badge nothing will revoke.
        State changes go through the ``invalidate`` action instead, which records
        who did it and why.

        ``grant_notes`` is the one field deliberately left editable: correcting the
        wording of a reason changes no badge state, and the rule above exists to
        protect badge state rather than to freeze the row for its own sake.
        """
        if obj is None:
            return self.readonly_fields
        return self.readonly_fields + (
            "user",
            "achievement",
            "is_valid",
            "invalidation_notes",
            "source_type",
            "source_content_type",
            "source_object_id",
        )

    def save_model(self, request, obj, form, change):
        """Mark admin-created grants as manual and record the granting admin."""
        if not change:
            obj.source_type = SourceType.MANUAL
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Invalidate selected achievements (with note)")
    def invalidate(self, request, queryset):
        """Soft-invalidate achievements after collecting a required note."""
        # Narrowed before the confirmation page too, so it never lists rows the
        # action would skip and then report having invalidated nothing.
        queryset = queryset.filter(is_valid=True)
        if not queryset.exists():
            self.message_user(
                request,
                "Nothing to invalidate: every selected achievement is already "
                "invalid.",
                level=messages.WARNING,
            )
            return None

        def apply(notes):
            """Save row by row, so the ``post_save`` signal revokes the badges."""
            count = 0
            for achievement in queryset:
                achievement.is_valid = False
                achievement.invalidated_by = request.user
                achievement.invalidated_at = timezone.now()
                achievement.invalidation_notes = notes
                achievement.save()
                count += 1
            self.message_user(request, f"Invalidated {count} achievement(s).")

        return self.notes_action(
            request,
            queryset,
            title="Invalidate achievements",
            action="invalidate",
            submit_label="Invalidate",
            apply=apply,
        )

    @admin.action(description="Revalidate selected achievements")
    def revalidate(self, request, queryset):
        """Undo an invalidation, clearing its audit trail.

        The counterpart to ``invalidate``, and the reason the change form does not
        expose ``is_valid``: flipping it there would leave the row reading
        "invalidated by X" while counting toward a threshold again. Saves one row
        at a time so the post_save signal re-awards the badges.
        """
        count = 0
        for achievement in queryset.filter(is_valid=False):
            achievement.is_valid = True
            achievement.invalidated_by = None
            achievement.invalidated_at = None
            achievement.invalidation_notes = ""
            achievement.save()
            count += 1
        self.message_user(request, f"Revalidated {count} achievement(s).")


@admin.register(UserBadge)
class UserBadgeAdmin(
    MemberSummaryLinkMixin, NotesActionMixin, TaskButtonAdminMixin, admin.ModelAdmin
):
    """Read-only admin for derived badge state.

    Badges are awarded and revoked by the recalculation service, so rows are
    neither added nor edited here. The ``revoke`` action lets an admin revoke one
    after collecting a required note; it does not touch any ``UserAchievement``
    records. Manual revocations are never re-earned by recalculation - use the
    ``reinstate`` action to undo one.
    """

    task_buttons = (RECALCULATE_BUTTON,)
    list_display = (
        "badge",
        "user_link",
        "tier",
        "is_held",
        "hidden_by_member",
        "awarded_at",
        "revoked_at",
    )
    list_filter = ("badge", "tier__rank", BadgeStatusFilter, "revocation_source")
    list_select_related = ("badge", "user", "tier")
    search_fields = ("user__email", "user__display_name", "badge__label")
    readonly_fields = (
        "badge",
        "user",
        "tier",
        "awarded_at",
        "revoked_by",
        "revoked_at",
        "revocation_source",
        "revocation_notes",
        "count_at_revocation",
    )
    actions = ["revoke", "reinstate"]

    def get_urls(self):
        """Register the per-user page ahead of the ``<object_id>/`` catch-all."""
        summary = [
            path(
                "user-summary/<int:user_id>/",
                self.admin_site.admin_view(self.user_summary_view),
                name="badges_userbadge_user_summary",
            )
        ]
        return summary + super().get_urls()

    def user_summary_view(self, request, user_id):
        """Why one member does or does not show each badge.

        The four causes of a missing badge live in three changelists otherwise,
        two of them only as arithmetic against a threshold. Every url the page
        renders is built here rather than in the template.

        ``admin_site.admin_view`` only asks whether the caller is staff. The page
        reads awarded badges *and* achievement grants, so it needs view
        permission on both.
        """
        if not (
            self.has_view_permission(request)
            and request.user.has_perm("badges.view_userachievement")
        ):
            raise PermissionDenied

        member = get_object_or_404(get_user_model(), pk=user_id)
        if request.method == "POST":
            if request.POST.get("action") == "reconcile":
                return self._reconcile_member(request, member)
            # Anything else is the recalculate form. Defaulting to it is safe
            # because it is the idempotent one: an unrecognised action costs a
            # recalculation, not a deletion.
            return self._recalculate_member(request, member)

        grants_changelist = reverse("admin:badges_userachievement_changelist")
        rows = [
            {
                "row": row,
                "grants_url": (
                    f"{grants_changelist}?user__id__exact={member.pk}"
                    f"&achievement__id__exact={row.achievement.pk}"
                ),
            }
            for row in user_badge_summary(member)
        ]
        context = {
            **self.admin_site.each_context(request),
            "title": f"Badges for {member}",
            "member": member,
            "rows": rows,
            "opts": self.model._meta,
            "index_url": reverse("admin:index"),
            "changelist_url": reverse("admin:badges_userbadge_changelist"),
            "recalculate_url": user_summary_url(member.pk),
            "can_recalculate": self.has_change_permission(request),
            "reconcile_url": user_summary_url(member.pk),
            "can_reconcile": request.user.has_perm(RECONCILE_PERMISSION),
            "grant_url": (
                f"{reverse('admin:badges_userachievement_add')}?user={member.pk}"
            ),
            "can_grant": request.user.has_perm("badges.add_userachievement"),
        }
        return render(request, "admin/badges/user_summary.html", context)

    def _recalculate_member(self, request, member):
        """Reconcile every one of this member's badges, synchronously.

        One member is at most a handful of achievement types at five queries
        each, so a Celery task would buy nothing and cost the admin the ability
        to see the result on the page they are already looking at.
        """
        if not self.has_change_permission(request):
            raise PermissionDenied
        count = recalculate_many(achievement_pairs(user_ids=[member.pk]))
        self.message_user(
            request, f"Recalculated {count} achievement type(s) for this member."
        )
        return HttpResponseRedirect(user_summary_url(member.pk))

    def _reconcile_member(self, request, member):
        """Preview, then on a second POST apply, this member's source disagreements.

        Synchronous for the same reason ``_recalculate_member`` is - the admin
        wants the outcome on the page they are already looking at - and the choice
        costs less than it looks: walking every source is the price whether the run
        is scoped to one member or not, and it is the same walk the preview just
        did.

        It can delete, so it is gated on ``delete_userachievement`` rather than on
        the change permission that guards the rest of this page.
        """
        if not request.user.has_perm(RECONCILE_PERMISSION):
            raise PermissionDenied

        if "apply" not in request.POST:
            return render(
                request,
                "admin/dry_run_confirm.html",
                {
                    **self.admin_site.each_context(request),
                    "opts": self.model._meta,
                    "title": f"Reconcile achievements for {member}",
                    "preview": reconcile_preview(
                        AUTOMATIC_SLUGS,
                        user_ids=[member.pk],
                        scope_label=str(member),
                    ),
                    "form_action": user_summary_url(member.pk),
                    "hidden_fields": [{"name": "action", "value": "reconcile"}],
                    "submit_label": "Reconcile this member",
                    "cancel_url": user_summary_url(member.pk),
                },
            )

        added, removed = reconcile_apply(
            AUTOMATIC_SLUGS, user_ids=[member.pk], actor=request.user
        )
        self.message_user(
            request,
            f"Reconciled this member with their sources: added {added} and removed "
            f"{removed} automatic achievement(s).",
        )
        return HttpResponseRedirect(user_summary_url(member.pk))

    def has_add_permission(self, request):
        """Badges are derived. Grant the achievement behind one instead.

        A hand-made row has no achievements supporting it, so the next
        recalculation cascade-revokes it and the badge silently disappears.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """Revocation is a soft delete on purpose; keep the audit trail."""
        return False

    @admin.display(boolean=True, description="Held", ordering="revoked_at")
    def is_held(self, obj):
        """Whether the member currently holds this badge."""
        return obj.is_active

    @admin.display(boolean=True, description="Hidden", ordering="user__hide_badges")
    def hidden_by_member(self, obj):
        """Whether the member has turned badge display off on their profile.

        Two of the reasons a badge does not appear are visible here; the other two
        - manual and cascade revocation - are the ``revocation_source`` column.
        """
        return obj.user.hide_badges

    @admin.action(description="Revoke selected badges (with note)")
    def revoke(self, request, queryset):
        """Directly revoke badges after collecting a required note."""
        # Narrowed before the confirmation page, like ``invalidate``, so it never
        # lists a badge it would skip and then report having revoked nothing.
        queryset = queryset.filter(revoked_at__isnull=True)
        if not queryset.exists():
            self.message_user(
                request,
                "Nothing to revoke: every selected badge is already revoked.",
                level=messages.WARNING,
            )
            return None

        def apply(notes):
            """One update: ``UserBadge`` has no signals to run per row."""
            count = queryset.update(
                revoked_at=timezone.now(),
                revoked_by=request.user,
                revocation_notes=notes,
                revocation_source=RevocationSource.MANUAL,
            )
            self.message_user(request, f"Revoked {count} badge(s).")

        return self.notes_action(
            request,
            queryset,
            title="Revoke badges",
            action="revoke",
            submit_label="Revoke",
            apply=apply,
        )

    @admin.action(description="Reinstate selected manually revoked badges")
    def reinstate(self, request, queryset):
        """Clear revocation on manually revoked badges, undoing a revoke action.

        Cascade revocations are skipped: they mean the achievement count is
        below the tier threshold, so reinstating one would award a badge the
        user has not earned. Nothing would take it away again either - per-pair
        recalculation only runs when a ``UserAchievement`` changes, and the
        achievement behind a cascade revocation is already invalid.
        """
        eligible = queryset.filter(
            revoked_at__isnull=False, revocation_source=RevocationSource.MANUAL
        )
        skipped = queryset.filter(revoked_at__isnull=False).count() - eligible.count()
        count = eligible.update(
            revoked_at=None,
            revoked_by=None,
            revocation_notes="",
            revocation_source="",
            count_at_revocation=None,
        )
        self.message_user(request, f"Reinstated {count} badge(s).")
        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} cascade-revoked badge(s): their achievement "
                "count is below the tier threshold. Grant or revalidate the "
                "achievements instead.",
                level=messages.WARNING,
            )


@admin.register(AchievementSyncRun)
class AchievementSyncRunAdmin(admin.ModelAdmin):
    """Read-only history of backfill and reconcile runs.

    This is what a cascade revocation note points at. When a member asks where
    their badge went, the run named in that note says what changed the count, when,
    and whether a person or the weekly pipeline started it.
    """

    list_display = (
        "id",
        "source_slug",
        "mode",
        "trigger",
        "triggered_by",
        "started_at",
        "added",
        "removed",
        "members_changed",
        "refused",
    )
    list_filter = ("mode", "trigger", "refused", "source_slug")
    list_select_related = ("triggered_by",)
    search_fields = ("source_slug", "triggered_by__email")
    date_hierarchy = "started_at"
    readonly_fields = tuple(
        field.name for field in AchievementSyncRun._meta.fields if field.name != "id"
    )

    def has_add_permission(self, request):
        """Runs are recorded by the sync itself, never entered by hand."""
        return False

    def has_change_permission(self, request, obj=None):
        """A run is history; editing one would defeat the point of keeping it."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Revocation notes point at these rows, so deleting one orphans a note."""
        return False
