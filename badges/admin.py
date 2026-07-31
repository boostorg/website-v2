"""Django admin for the achievements and badges system.

Superusers (and anyone with the relevant per-model permissions) can manage
achievement types, configure badge tiers, manually grant achievements, and
invalidate / revoke with a required audit note.
"""

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import Truncator

from badges.forms import NotesActionForm
from badges.models import (
    Achievement,
    RevocationSource,
    SourceType,
    UserAchievement,
    UserBadge,
)
from badges.services import recalculate_badges, sync_source
from badges.sources import AUTOMATIC_SLUGS
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


def reconcile_results(slugs, user_ids=None, dry_run=False):
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
        sync_source(slug, achievements[slug], user_ids=user_ids, dry_run=dry_run)
        for slug in sorted(slugs)
        if slug in achievements
    ]
    return results, sorted(set(slugs) - set(achievements))


def reconcile_apply(slugs, user_ids=None):
    """Sync the named sources for real, then recalculate the members that moved.

    ``sync_source`` deliberately leaves the recalculation to its caller. Deletions
    have already recalculated themselves through ``post_delete``; additions have
    not, and revisiting a pair is idempotent.
    """
    results, _ = reconcile_results(slugs, user_ids=user_ids)
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


@admin.register(UserAchievement)
class UserAchievementAdmin(NotesActionMixin, TaskButtonAdminMixin, admin.ModelAdmin):
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
        "user",
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
class UserBadgeAdmin(NotesActionMixin, TaskButtonAdminMixin, admin.ModelAdmin):
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
        "user",
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
    )
    actions = ["revoke", "reinstate"]

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
