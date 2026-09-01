"""The release tools admin page.

One page, because these jobs are operator tooling rather than the
administration of any single model, and because the destructive alternative
sits on the Library changelist: an operator who has to choose between them
should be able to read what each one does without leaving the page.
"""

from django.conf import settings
from django.contrib import admin
from django.db.models import Count, F, Q
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils.html import format_html

from core.admin_buttons import TaskButton, TaskButtonAdminMixin
from libraries.tasks import synchronize_release_library_data
from .models import ReleaseLibraryData


def syncable_releases():
    """The releases the scoped synchronization may be pointed at.

    One definition, so the table on the page and the select beside the button
    cannot disagree about what is on offer. The moving branches are left out:
    importing one garbage-collects the library versions that have left its
    .gitmodules, and this job is offered on the promise that it deletes nothing.
    """
    return (
        ReleaseLibraryData.objects.with_partials()
        .active()
        .exclude(slug__in=settings.BOOST_BRANCHES)
    )


def release_choices():
    """The select's pairs, read per request.

    A release imported this morning has to be selectable this afternoon.
    """
    return [
        (version.name, version.display_name)
        for version in syncable_releases().order_by("-name")
    ]


SYNCHRONIZE_RELEASE_LIBRARY_DATA_BUTTON = TaskButton(
    name="synchronize_release_library_data",
    label="Synchronize Release Library Data",
    task=synchronize_release_library_data,
    success_message="The release is being synchronized in the background.",
    busy_message=(
        "That release is already queued or running; not starting another one."
    ),
    argument="release",
    choice_label="Release",
    choices=release_choices,
    require_choice=True,
    description=(
        "Takes a few minutes: it reads the release from GitHub before it can bind "
        "anything."
    ),
)


@admin.register(ReleaseLibraryData)
class ReleaseLibraryDataAdmin(TaskButtonAdminMixin, admin.ModelAdmin):
    """Release maintenance jobs, one row per release.

    The job is offered on the release it would act on rather than through a
    select, so the release an operator reads the numbers for is the release they
    press. `Needs synchronizing` counts only what this job can actually repair;
    a library whose upstream metadata names no author is counted separately,
    because no amount of synchronizing will give it one.
    """

    change_list_template = "admin/release_tools/change_list.html"
    task_buttons = (SYNCHRONIZE_RELEASE_LIBRARY_DATA_BUTTON,)
    list_display_links = None
    ordering = ("-name",)
    search_fields = ("name",)

    # A library version can only be given an author if its imported metadata
    # names one. An absent `authors` key means the import never read that far, so
    # synchronizing is the thing to try; a key that is present and empty means
    # upstream declares no author at all and never will.
    UNBOUND = Q(library_version__authors__isnull=True)
    NO_UPSTREAM_AUTHOR = Q(library_version__data__has_key="authors") & (
        Q(library_version__data__authors="") | Q(library_version__data__authors=[])
    )

    def get_list_display(self, request):
        """Built per request, because the action column needs a CSRF token."""
        return (
            "display_name",
            "release_date",
            "needs_synchronizing",
            "no_author_upstream",
            self._synchronize_column(request),
        )

    def get_queryset(self, request):
        """Annotate the counts, so no per-row query is needed to show them.

        Both filters match positively and the difference is taken afterwards. A
        `~Q` over a JSON key would read as NOT NULL for every row whose `data`
        does not carry the key at all, which SQL evaluates as unknown rather than
        true, and those rows would fall out of both counts. They are the ones that
        matter most: an absent key is what a failed import leaves behind.
        """
        return (
            syncable_releases()
            .annotate(
                _libraries=Count("library_version", distinct=True),
                _unbound=Count("library_version", filter=self.UNBOUND, distinct=True),
                _no_upstream=Count(
                    "library_version",
                    filter=self.UNBOUND & self.NO_UPSTREAM_AUTHOR,
                    distinct=True,
                ),
            )
            .annotate(_repairable=F("_unbound") - F("_no_upstream"))
        )

    @admin.display(description="Needs synchronizing", ordering="_repairable")
    def needs_synchronizing(self, obj):
        if not obj._libraries:
            return "no libraries imported"
        if not obj._repairable:
            return "none"
        return f"{obj._repairable} of {obj._libraries}"

    @admin.display(description="No author upstream", ordering="_no_upstream")
    def no_author_upstream(self, obj):
        """Libraries this job cannot help, kept out of the column beside it."""
        return obj._no_upstream or ""

    def _synchronize_column(self, request):
        """A submit button per row, posting that row's release.

        A closure rather than a method so the CSRF token and the permission
        check are taken from this request; a `ModelAdmin` instance is shared
        between them and must not carry either.
        """
        button = SYNCHRONIZE_RELEASE_LIBRARY_DATA_BUTTON
        allowed = self._task_button_allows(request, button)
        url = reverse(f"admin:{self._task_button_url_name(button)}")
        token = get_token(request)
        # One cache read for the whole page: per row would be one read and one
        # result-backend call each, on a list of every release.
        status = self._task_button_status(button)
        running = status["scope"] if status["poll"] else ""

        def synchronize(obj):
            if not allowed:
                return ""
            if running and obj.display_name == running:
                return format_html(
                    '<span class="release-tools-running">{}</span>', status["label"]
                )
            return format_html(
                '<form action="{}" method="post" class="release-tools-action">'
                '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
                '<input type="hidden" name="release" value="{}">'
                '<button type="submit">Synchronize</button>'
                "</form>",
                url,
                token,
                obj.name,
            )

        synchronize.short_description = "Action"
        return synchronize

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
