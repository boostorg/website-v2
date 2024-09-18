from django.contrib import admin
from django.db import transaction
from django.db.models import F, Count, OuterRef, Window
from django.db.models.functions import RowNumber
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.shortcuts import redirect

from libraries.forms import CreateReportForm
from versions.tasks import import_all_library_versions
from .models import (
    Category,
    Commit,
    CommitAuthor,
    CommitAuthorEmail,
    CommitData,
    Issue,
    Library,
    LibraryVersion,
    PullRequest,
)
from .tasks import (
    update_commit_counts,
    update_libraries,
    update_library_version_documentation_urls_all_versions,
)


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ["library_version", "sha", "author"]
    autocomplete_fields = ["author", "library_version"]
    list_filter = ["library_version__library"]
    search_fields = ["sha", "author__name"]


class CommitAuthorEmailInline(admin.TabularInline):
    model = CommitAuthorEmail
    extra = 0


@admin.register(CommitAuthor)
class CommitAuthorAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    actions = ["merge_authors"]
    inlines = [CommitAuthorEmailInline]

    @admin.action(
        description="Combine 2 or more authors into one. References will be updated."
    )
    def merge_authors(self, request, queryset):
        objects = list(queryset)
        if len(objects) < 2:
            return
        author = objects[0]
        with transaction.atomic():
            for other in objects[1:]:
                author.merge_author(other)
        message = "Merged authors -- " + ", ".join([x.name for x in objects])
        self.message_user(request, message)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    ordering = ["name"]
    search_fields = ["name"]


@admin.register(CommitData)
class CommitDataAdmin(admin.ModelAdmin):
    list_display = (
        "library",
        "commit_count_formatted",
        "month_year_formatted",
        "branch",
        "library_link",
    )
    list_filter = ("library__name", "branch", "month_year")
    search_fields = ("library__name", "branch")
    date_hierarchy = "month_year"
    ordering = ("library__name", "-month_year")
    autocomplete_fields = ["library"]
    change_list_template = "admin/commit_data_change_list.html"

    def commit_count_formatted(self, obj):
        return f"{obj.commit_count:,}"

    commit_count_formatted.admin_order_field = "commit_count"
    commit_count_formatted.short_description = "Commit Count"

    def month_year_formatted(self, obj):
        return obj.month_year.strftime("%B %Y")

    month_year_formatted.admin_order_field = "month_year"
    month_year_formatted.short_description = "Month/Year"

    def library_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:libraries_library_change", args=(obj.library.pk,)),
            obj.library.name,
        )

    library_link.short_description = "Library Details"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "library":
            kwargs["queryset"] = Library.objects.order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "update_commit_data/",
                self.update_commit_data,
                name="update_commit_data",
            ),
        ]
        return my_urls + urls

    def update_commit_data(self, request):
        """Run the task to refresh the library data from GitHub"""
        update_commit_counts.delay()
        self.message_user(
            request,
            """
            Commit data is being refreshed.
        """,
        )
        return HttpResponseRedirect("../")


class LibraryVersionInline(admin.TabularInline):
    model = LibraryVersion
    extra = 0
    ordering = ["-version__name"]
    fields = ["version", "documentation_url"]


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ["name", "key", "github_url", "view_stats"]
    search_fields = ["name", "description"]
    list_filter = ["categories"]
    ordering = ["name"]
    change_list_template = "admin/library_change_list.html"
    inlines = [LibraryVersionInline]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("update_libraries/", self.update_libraries, name="update_libraries"),
            path(
                "<int:pk>/stats/",
                self.admin_site.admin_view(self.library_stat_detail),
                name="library_stat_detail",
            ),
            path(
                "report-form/",
                self.admin_site.admin_view(self.report_form_view),
                name="library_report_form",
            ),
            path(
                "report/",
                self.admin_site.admin_view(self.report_view),
                name="library_report",
            ),
        ]
        return my_urls + urls

    def report_form_view(self, request):
        form = CreateReportForm()
        context = {}
        if request.GET.get("version", None):
            form = CreateReportForm(request.GET)
            if form.is_valid():
                context.update(form.get_stats())
                return redirect(
                    reverse("admin:library_report") + f"?{request.GET.urlencode()}"
                )
        if not context:
            context["form"] = form
        return TemplateResponse(request, "admin/library_report_form.html", context)

    def report_view(self, request):
        form = CreateReportForm(request.GET)
        context = {"form": form}
        if form.is_valid():
            context.update(form.get_stats())
        else:
            return redirect("admin:library_report_form")
        return TemplateResponse(request, "admin/library_report_detail.html", context)

    def view_stats(self, instance):
        return mark_safe(
            f"<a href='{reverse('admin:library_stat_detail', kwargs={'pk': instance.pk})}'>View Stats</a>"
        )

    def update_libraries(self, request):
        """Run the task to refresh the library data from GitHub"""
        update_libraries.delay()
        import_all_library_versions.delay()
        self.message_user(
            request,
            """
            Library data is being refreshed.
        """,
        )
        return HttpResponseRedirect("../")

    def library_stat_detail(self, request, pk):
        context = {
            "object": self.get_object(request, pk),
            "commits_per_release": self._get_commits_per_release(pk),
            "commits_per_author": self._get_commits_per_author(pk),
            "commits_per_author_release": self._get_commits_per_author_release(pk),
            "new_contributor_counts": self._get_new_contributor_counts(pk),
        }
        return TemplateResponse(request, "admin/library_stat_detail.html", context)

    def _get_commits_per_release(self, pk):
        return (
            LibraryVersion.objects.filter(library_id=pk)
            .annotate(count=Count("commit"), version_name=F("version__name"))
            .order_by("-version__name")
            .filter(count__gt=0)
        )[:10]

    def _get_commits_per_author(self, pk):
        return (
            CommitAuthor.objects.filter(commit__library_version__library_id=pk)
            .annotate(count=Count("commit"))
            .order_by("-count")[:20]
        )

    def _get_commits_per_author_release(self, pk):
        return (
            LibraryVersion.objects.filter(library_id=pk)
            .filter(commit__author__isnull=False)
            .annotate(
                count=Count("commit"),
                row_number=Window(
                    expression=RowNumber(), partition_by=["id"], order_by=["-count"]
                ),
            )
            .values(
                "count",
                "commit__author",
                "commit__author__name",
                "version__name",
                "commit__author__avatar_url",
            )
            .order_by("-version__name", "-count")
            .filter(row_number__lte=3)
        )

    def _get_new_contributor_counts(self, pk):
        return (
            LibraryVersion.objects.filter(library_id=pk)
            .annotate(
                up_to_count=CommitAuthor.objects.filter(
                    commit__library_version__version__name__lte=OuterRef(
                        "version__name"
                    ),
                    commit__library_version__library_id=pk,
                )
                .values("commit__library_version__library")
                .annotate(count=Count("id", distinct=True))
                .values("count")[:1],
                before_count=CommitAuthor.objects.filter(
                    commit__library_version__version__name__lt=OuterRef(
                        "version__name"
                    ),
                    commit__library_version__library_id=pk,
                )
                .values("commit__library_version__library")
                .annotate(count=Count("id", distinct=True))
                .values("count")[:1],
                count=F("up_to_count") - F("before_count"),
            )
            .order_by("-version__name")
            .select_related("version")
        )


@admin.register(LibraryVersion)
class LibraryVersionAdmin(admin.ModelAdmin):
    list_display = ["library", "version", "missing_docs", "documentation_url"]
    list_filter = ["library", "version", "missing_docs"]
    ordering = ["library__name", "-version__name"]
    search_fields = ["library__name", "version__name"]
    change_list_template = "admin/libraryversion_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("update_docs_urls/", self.update_docs_urls, name="update_docs_urls"),
        ]
        return my_urls + urls

    def update_docs_urls(self, request):
        """Run the task to refresh the documentation URLS from S3"""
        update_library_version_documentation_urls_all_versions.delay()
        self.message_user(
            request,
            """
            Documentation links are being refreshed.
        """,
        )
        return HttpResponseRedirect("../")


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ["title", "number", "is_open", "closed"]
    search_fields = ["title"]
    list_filter = ["is_open", "library"]

    readonly_fields = [
        "title",
        "number",
        "github_id",
        "created",
        "modified",
        "closed",
    ]


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = ["title", "number", "is_open", "closed"]
    search_fields = ["title"]
    list_filter = ["is_open", "library"]

    readonly_fields = [
        "title",
        "number",
        "github_id",
        "created",
        "modified",
        "closed",
    ]
