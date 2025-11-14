from django.conf import settings
from django.contrib import admin
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, Count, OuterRef, Window
from django.db.models.functions import RowNumber
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django import forms

from core.admin_filters import StaffUserCreatedByFilter
from libraries.forms import CreateReportForm, CreateReportFullForm
from versions.models import Version
from versions.tasks import import_all_library_versions
from .filters import ReportConfigurationFilter
from .models import (
    Category,
    Commit,
    CommitAuthor,
    CommitAuthorEmail,
    Issue,
    Library,
    LibraryVersion,
    PullRequest,
    ReleaseReport,
    WordcloudMergeWord,
)
from .tasks import (
    generate_library_report,
    update_authors_and_maintainers,
    update_commit_author_github_data,
    update_commits,
    update_issues,
    update_libraries,
    update_library_version_documentation_urls_all_versions,
    generate_release_report,
    synchronize_commit_author_user_data,
)
from .utils import generate_release_report_filename


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ["library_version", "sha", "author"]
    autocomplete_fields = ["author", "library_version"]
    list_filter = ["library_version__library", "library_version__version"]
    search_fields = ["sha", "author__name"]
    change_list_template = "admin/commit_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "update_commits/",
                self.admin_site.admin_view(self.update_commits),
                name="update_commits",
            ),
        ]
        return my_urls + urls

    def update_commits(self, request):
        update_commits.delay(clean=True)
        self.message_user(
            request,
            """
            Commits for all libraries are being imported.
            """,
        )
        return HttpResponseRedirect("../")


class CommitAuthorEmailInline(admin.TabularInline):
    model = CommitAuthorEmail
    extra = 0


@admin.register(CommitAuthor)
class CommitAuthorAdmin(admin.ModelAdmin):
    list_display = ["name", "emails"]
    search_fields = ["name", "commitauthoremail__email"]
    actions = ["merge_authors"]
    inlines = [CommitAuthorEmailInline]
    change_list_template = "admin/commit_author_change_list.html"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("commitauthoremail_set")

    def emails(self, obj):
        return ", ".join(x.email for x in obj.commitauthoremail_set.all())

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "update_github_data/",
                self.admin_site.admin_view(self.update_github_data),
                name="commit_author_update_github_data",
            ),
            path(
                "synchronize_ca_user_data/",
                self.admin_site.admin_view(self.synchronize_ca_user_data),
                name="synchronize_ca_user_data",
            ),
        ]
        return my_urls + urls

    def update_github_data(self, request):
        update_commit_author_github_data.delay(clean=True)
        self.message_user(
            request,
            """
            Updating CommitAuthor Github data.
            """,
        )
        return HttpResponseRedirect("../")

    def synchronize_ca_user_data(self, request):
        synchronize_commit_author_user_data.delay()
        self.message_user(
            request,
            "Synchronizing CommitAuthor and User data",
        )
        return HttpResponseRedirect("../")

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


class LibraryVersionInline(admin.TabularInline):
    model = LibraryVersion
    extra = 0
    ordering = ["-version__name"]
    fields = ["version", "documentation_url"]


class ReleaseReportView(TemplateView):
    polling_template = "admin/report_polling.html"
    form_template = "admin/library_report_form.html"
    form_class = CreateReportForm
    report_type = "release report"

    def get_template_names(self):
        if not self.request.GET.get("submit", None):
            return [self.form_template]
        form = self.get_form()
        if not form.is_valid():
            return [self.form_template]
        if form.cleaned_data["no_cache"]:
            return [self.form_template]
        return [self.polling_template]

    def get_form(self):
        data = None
        if self.request.GET.get("submit", None):
            data = self.request.GET
        return self.form_class(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report_type"] = self.report_type
        context["form"] = self.get_form()
        return context

    def generate_report(self):
        base_scheme = "http" if settings.LOCAL_DEVELOPMENT else "https"
        generate_release_report.delay(
            user_id=self.request.user.id,
            params=self.request.GET,
            base_uri=f"{base_scheme}://{self.request.get_host()}",
        )

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            if form.cleaned_data["no_cache"]:
                params = request.GET.copy()
                form.cache_clear()
                del params["no_cache"]
                return redirect(request.path + f"?{params.urlencode()}")
            content = form.cache_get()
            if not content:
                # Ensure a RenderedContent exists so the task is not re-queued
                form.cache_set("")
                self.generate_report()
            elif content.content_html:
                return HttpResponse(content.content_html)
        return TemplateResponse(
            request,
            self.get_template_names(),
            self.get_context_data(),
        )


class LibraryReportView(ReleaseReportView):
    form_class = CreateReportFullForm
    report_type = "library report"

    def generate_report(self):
        generate_library_report.delay(self.request.GET)


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
                "update_authors_and_maintainers/",
                self.update_authors_and_maintainers,
                name="update_authors_and_maintainers",
            ),
            path(
                "<int:pk>/stats/",
                self.admin_site.admin_view(self.library_stat_detail),
                name="library_stat_detail",
            ),
            path(
                "release-report/",
                self.admin_site.admin_view(ReleaseReportView.as_view()),
                name="release_report",
            ),
            path(
                "library-report/",
                self.admin_site.admin_view(LibraryReportView.as_view()),
                name="library_report_full",
            ),
        ]
        return my_urls + urls

    def view_stats(self, instance):
        url = reverse("admin:library_stat_detail", kwargs={"pk": instance.pk})
        return mark_safe(f"<a href='{url}'>View Stats</a>")

    def update_authors_and_maintainers(self, request):
        update_authors_and_maintainers.delay()
        self.message_user(request, "Authors and Maintainers are being updated.")
        return HttpResponseRedirect("../")

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
            "commits_per_release": self.get_commits_per_release(pk),
            "commits_per_author": self.get_commits_per_author(pk),
            "commits_per_author_release": self.get_commits_per_author_release(pk),
            "new_contributor_counts": self.get_new_contributor_counts(pk),
        }
        return TemplateResponse(request, "admin/library_stat_detail.html", context)

    def get_commits_per_release(self, pk):
        return (
            LibraryVersion.objects.filter(
                library_id=pk, version__in=Version.objects.minor_versions()
            )
            .annotate(count=Count("commit"), version_name=F("version__name"))
            .order_by("-version__name")
            .filter(count__gt=0)
        )[:10]

    def get_commits_per_author(self, pk):
        return (
            CommitAuthor.objects.filter(commit__library_version__library_id=pk)
            .annotate(count=Count("commit"))
            .order_by("-count")[:20]
        )

    def get_commits_per_author_release(self, pk):
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

    def get_new_contributor_counts(self, pk):
        return (
            LibraryVersion.objects.filter(
                library_id=pk, version__in=Version.objects.minor_versions()
            )
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
    list_filter = ["library", "version", "missing_docs", "cpp20_module_support"]
    ordering = ["library__name", "-version__name"]
    search_fields = ["library__name", "version__name"]
    change_list_template = "admin/libraryversion_change_list.html"
    autocomplete_fields = ["authors", "maintainers", "dependencies"]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "update_docs_urls/",
                self.admin_site.admin_view(self.update_docs_urls),
                name="update_docs_urls",
            ),
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
    change_list_template = "admin/issue_change_list.html"

    readonly_fields = [
        "title",
        "number",
        "github_id",
        "created",
        "modified",
        "closed",
    ]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "update_issues/",
                self.admin_site.admin_view(self.update_issues),
                name="update_issues",
            ),
        ]
        return my_urls + urls

    def update_issues(self, request):
        update_issues.delay(clean=True)
        self.message_user(request, "Issues are being updated.")
        return HttpResponseRedirect("../")


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


@admin.register(WordcloudMergeWord)
class WordcloudMergeWordAdmin(admin.ModelAdmin):
    search_fields = ["from_word", "to_word"]
    fieldsets = [
        (
            "Word Cloud Merging",
            {
                "fields": ("from_word", "to_word"),
                "description": "Words that should be merged together in the release report."
                ' e.g. "Boost" and "boost" to "Boost Foundation" or vice versa. Use in '
                'combination with "Wordcloud ignore" under SiteSettings.',
            },
        ),
    ]


class ReleaseReportAdminForm(forms.ModelForm):
    class Meta:
        model = ReleaseReport
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and not self.instance.published:
            file_name = generate_release_report_filename(
                self.instance.report_configuration.get_slug()
            )
            published_filename = f"{ReleaseReport.upload_dir}{file_name}"
            if default_storage.exists(published_filename):
                # we require users to intentionally manually delete existing reports
                self.fields["published"].disabled = True
                self.fields["published"].help_text = (
                    f"⚠️ A published '{file_name}' already exists. To prevent accidents "
                    "you must manually delete that file before publishing this report."
                )


@admin.register(ReleaseReport)
class ReleaseReportAdmin(admin.ModelAdmin):
    form = ReleaseReportAdminForm
    list_display = ["__str__", "created_at", "published", "published_at"]
    list_filter = ["published", ReportConfigurationFilter, StaffUserCreatedByFilter]
    search_fields = ["file"]
    readonly_fields = ["created_at", "created_by"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
