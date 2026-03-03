import structlog
from datetime import date
from django.conf import settings
from django.contrib import admin, messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Count, OuterRef, Window
from django.db.models.functions import RowNumber
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django import forms
from celery import chain, group
from celery.result import AsyncResult

from core.admin_filters import StaffUserCreatedByFilter
from config.celery import app
from libraries.forms import CreateReportForm, CreateReportFullForm
from reports.generation import determine_versions
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
    count_mailinglist_contributors,
    count_commit_contributors_totals,
    generate_library_report,
    generate_mailinglist_cloud,
    generate_release_report_with_stats,
    generate_search_cloud,
    get_mailing_list_stats,
    get_new_contributors_count,
    get_new_subscribers_stats,
    synchronize_commit_author_user_data,
    update_authors_and_maintainers,
    update_commit_author_github_data,
    update_commits,
    update_issues,
    update_libraries,
    update_library_version_documentation_urls_all_versions,
)
from .utils import generate_release_report_filename


logger = structlog.get_logger()


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
    polling_widget_template = "admin/task_polling_widget.html"
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

    def check_task_status(self, cache_key=""):
        """
        Check the status of celery tasks stored in the cache from the generate report function.

        Returns a list of task items containing their name and status, as well as a flag
        of whether all the list tasks have completed.
        """
        DEFAULT_STATUS_TEXT = "QUEUED"

        class TaskStruct:
            name = ""
            value = DEFAULT_STATUS_TEXT
            error = None

            def __init__(self, name=""):
                self.name = name

        task_dict = {
            count_mailinglist_contributors.name: TaskStruct(
                "Count Mailing List Contributors"
            ),
            get_mailing_list_stats.name: TaskStruct("Get Mailing List Stats"),
            count_commit_contributors_totals.name: TaskStruct(
                "Count Commit Contributors Totals"
            ),
            get_new_subscribers_stats.name: TaskStruct("Get New Subscriber Stats"),
            generate_mailinglist_cloud.name: TaskStruct("Generate Mailing List Cloud"),
            generate_search_cloud.name: TaskStruct("Generate Search Cloud"),
            get_new_contributors_count.name: TaskStruct("Get New Contributors Count"),
        }
        all_tasks_ready = True
        if workflow_ids := cache.get(cache_key):
            for id in workflow_ids:
                task: AsyncResult = app.AsyncResult(id)
                if task.name and task.name in task_dict:
                    task_dict[task.name].value = task.status
                    if task.failed():
                        task_dict[task.name].error = task.result
                if not task.ready():
                    all_tasks_ready = False
        return task_dict, all_tasks_ready

    def render_task_widget(self, task_dict):
        """
        Takes a dict of {"task_signature_name": TaskStruct} and returns a rendered widget.
        """
        return render_to_string(
            self.polling_widget_template, context={"tasks": task_dict}
        )

    def update_context_with_workflow_state(self, context={}, cache_key=""):
        task_dict, _ = self.check_task_status(cache_key=cache_key)
        context["task_widget"] = self.render_task_widget(task_dict=task_dict)
        request = self.request
        params = self.request.GET.copy()
        if "render_widget" not in params:
            params["render_widget"] = True
        context["widget_endpoint"] = f"{request.path}?{params.urlencode()}"
        return context

    def generate_report(self):
        uri = f"{settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL}://{self.request.get_host()}"
        logger.info("Queuing release report workflow")

        # Get the report configuration to determine version parameters
        form = self.get_form()
        if not form.is_valid():
            return

        report_configuration = form.cleaned_data["report_configuration"]

        # NOTE TO FUTURE DEVS: remember to account for the fact that a report
        #  configuration may not match with a real version in frequent cases where
        #  reports are generated before the release version has been created.
        (report_before_release, prior_version, version) = determine_versions(
            report_configuration.version
        )

        # trigger stats tasks first to run in parallel using group, then chain the final
        #  report generation task
        stats_tasks = group(
            [
                count_mailinglist_contributors.s(prior_version.pk, version.pk),
                get_mailing_list_stats.s(prior_version.pk, version.pk),
                count_commit_contributors_totals.s(version.pk, prior_version.pk),
                get_new_subscribers_stats.s(
                    prior_version.release_date, version.release_date or date.today()
                ),
                generate_mailinglist_cloud.s(prior_version.pk, version.pk),
                # if the report is based on a live version, look for stats for that
                # version, otherwise use the stats for the prior (live) version
                generate_search_cloud.s(
                    prior_version.pk if report_before_release else version.pk
                ),
                get_new_contributors_count.s(version.pk),
            ]
        )

        # chain stats collection with final report generation
        workflow = chain(
            stats_tasks,
            generate_release_report_with_stats.s(
                self.request.user.id,
                self.request.GET,
                uri,
            ),
        )
        m: AsyncResult = workflow.apply_async()

        def unpack_node_ids(node: AsyncResult):
            """
            Return the ID of a given Celery Async Result, along with any parents or children
            as a list. Used to cache these ids for report generation.
            """
            local_ids = []
            if node.parent:
                local_ids += unpack_node_ids(node.parent)
            if not node.children:
                local_ids.append(node.id)
            else:
                for c_node in node.children:
                    local_ids += unpack_node_ids(c_node)
            return local_ids

        task_ids = unpack_node_ids(m)

        # After beginning the report generation, cache the key for an hour
        # for polling purposes
        cache.set(form.cache_key, task_ids, 60 * 60)

    def locked_publish_check(self):
        form = self.get_form()
        form.is_valid()
        publish = form.cleaned_data["publish"]
        report_configuration = form.cleaned_data["report_configuration"]
        if publish and ReleaseReport.latest_published_locked(report_configuration):
            msg = (
                f"A release report already exists with locked status for "
                f"{report_configuration.display_name}. Delete or unlock the most "
                f"recent report."
            )
            raise ValueError(msg)

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        context = self.get_context_data()
        if form.is_valid():
            try:
                self.locked_publish_check()
            except ValueError as e:
                messages.error(request, str(e))
                return TemplateResponse(
                    request,
                    self.form_template,
                    self.get_context_data(),
                )

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
                response = HttpResponse(content.content_html)
                response.status_code = 286
                return response
            # If this flag is set, the page is being request via htmx and should only
            # return the task widget
            if self.request.GET.get("render_widget", None):
                task_dict, all_tasks_ready = self.check_task_status(form.cache_key)
                status_code = 200
                if all_tasks_ready:
                    # magic number for htmx to stop polling
                    status_code = 286
                response = HttpResponse(self.render_task_widget(task_dict))
                response.status_code = status_code
                return response
            context = self.update_context_with_workflow_state(context, form.cache_key)
        return TemplateResponse(
            request,
            self.get_template_names(),
            context=context,
        )


class LibraryReportView(ReleaseReportView):
    form_class = CreateReportFullForm
    report_type = "library report"

    def generate_report(self):
        # For library reports, we don't need a complex stats workflow since
        #  CreateReportFullForm doesn't use the same async stats pattern
        generate_library_report.delay(self.request.GET)


class TierFilter(admin.SimpleListFilter):
    title = "tier"
    parameter_name = "tier"

    def lookups(self, request, model_admin):
        from libraries.models import Tier

        choices = [
            ("unassigned", "Unassigned"),
        ]
        choices.extend([(tier.value, tier.label) for tier in Tier])
        return choices

    def queryset(self, request, queryset):
        if self.value() == "unassigned":
            return queryset.filter(tier__isnull=True)
        elif self.value() is not None:
            return queryset.filter(tier=self.value())
        return queryset


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ["name", "key", "tier", "github_url", "view_stats"]
    search_fields = ["name", "description"]
    list_filter = [TierFilter, "categories"]
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

        if not self.is_publish_editable():
            # we require users to intentionally manually delete existing reports
            self.fields["published"].disabled = True
            self.fields["published"].help_text = (
                "⚠️ A published PDF already exists for this Report Configuration. See "
                '"Publishing" notes at the top of this page.'
            )

    def is_publish_editable(self) -> bool:
        # in play here are currently published and previously published rows because of
        # filename collision risk.
        if self.instance.published:
            return True

        published_filename = generate_release_report_filename(
            version_slug=self.instance.report_configuration.get_slug(),
            published_format=True,
        )
        reports = ReleaseReport.objects.filter(
            report_configuration=self.instance.report_configuration,
            file=f"{ReleaseReport.upload_dir}{published_filename}",
        )

        if reports.count() == 0 or reports.latest("created_at") == self.instance:
            return True

        return False

    def clean(self):
        cleaned_data = super().clean()
        if not self.is_publish_editable():
            raise ValidationError("This file is not publishable.")
        if cleaned_data.get("published"):
            report_configuration = cleaned_data.get("report_configuration")
            if ReleaseReport.latest_published_locked(
                report_configuration, self.instance
            ):
                raise ValidationError(
                    f"A release report already exists with locked status for "
                    f"{report_configuration.display_name}. Delete or unlock the most "
                    f"recent report."
                )

        return cleaned_data


@admin.register(ReleaseReport)
class ReleaseReportAdmin(admin.ModelAdmin):
    form = ReleaseReportAdminForm
    list_display = ["__str__", "created_at", "published", "published_at", "locked"]
    list_filter = [
        "published",
        "locked",
        ReportConfigurationFilter,
        StaffUserCreatedByFilter,
    ]
    search_fields = ["file"]
    readonly_fields = ["created_at", "created_by"]
    ordering = ["-created_at"]
    change_list_template = "admin/releasereport_change_list.html"
    change_form_template = "admin/releasereport_change_form.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "release_tasks/",
                self.admin_site.admin_view(self.release_tasks),
                name="release_tasks",
            ),
        ]
        return my_urls + urls

    def release_tasks(self, request):
        from libraries.tasks import release_tasks

        release_tasks.delay(
            base_uri=f"{settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL}://{request.get_host()}",
            user_id=request.user.id,
            generate_report=False,
        )
        self.message_user(
            request,
            "release_tasks has started, you will receive an email when the task finishes.",  # noqa: E501
        )
        return HttpResponseRedirect("../")

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @staticmethod
    def clear_other_report_files(release_report: ReleaseReport):
        if release_report.file:
            other_reports = ReleaseReport.objects.filter(
                file=release_report.file.name
            ).exclude(pk=release_report.pk)

            if other_reports.exists():
                release_report.file = None
                release_report.save()

    def delete_model(self, request, obj):
        # check if another report uses the same file
        self.clear_other_report_files(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # clear file reference, prevents deletion of the file if it's linked elsewhere
        for obj in queryset:
            self.clear_other_report_files(obj)
        super().delete_queryset(request, queryset)
