from structlog import get_logger
from datetime import date

from django import forms
from django.template.loader import render_to_string
from django.db.models import Q, Count, Sum
from django.forms import Form, ModelChoiceField, ModelForm, BooleanField

from core.models import RenderedContent
from reports.generation import (
    get_git_graph_data,
    get_library_data,
    get_library_full_counts,
    get_libraries_by_name,
    get_top_contributors_for_version,
    get_top_libraries,
    get_top_libraries_for_version,
    lines_changes_count,
    get_commit_counts,
    get_issues_counts,
    get_download_links,
    determine_versions,
    get_libraries,
    get_libraries_for_index,
    get_mailinglist_counts,
    get_slack_channels,
    get_slack_stats,
)
from versions.models import Version, ReportConfiguration
from .models import (
    Commit,
    CommitAuthor,
    Library,
    CommitAuthorEmail,
)
from libraries.constants import SUB_LIBRARIES, RELEASE_REPORT_AUTHORS_PER_PAGE_THRESHOLD
from mailing_list.models import EmailData
from .tasks import (
    count_mailinglist_contributors,
    generate_search_cloud,
    generate_mailinglist_cloud,
    get_mailing_list_stats,
    get_new_subscribers_stats,
    count_commit_contributors_totals,
    get_new_contributors_count,
)
from .utils import conditional_batched

logger = get_logger(__name__)


class LibraryForm(ModelForm):
    class Meta:
        model = Library
        fields = ["categories"]


class CreateReportFullForm(Form):
    """Form for creating a report over all releases."""

    html_template_name = "admin/library_report_full_detail.html"

    library_queryset = Library.objects.exclude(key__in=SUB_LIBRARIES).order_by("name")
    library_1 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
        help_text="If none are selected, the top 5 will be auto-selected.",
    )
    library_2 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
    )
    library_3 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
    )
    library_4 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
    )
    library_5 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
    )
    library_6 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
    )
    library_7 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
    )
    library_8 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
    )
    no_cache = BooleanField(
        required=False,
        initial=False,
        help_text="Force the page to be regenerated, do not use cache.",
    )
    publish = BooleanField(
        required=False,
        initial=False,
        help_text="Warning: overwrites existing published report, not reversible.",
    )

    @property
    def cache_key(self):
        chosen_libraries = [
            self.cleaned_data["library_1"],
            self.cleaned_data["library_2"],
            self.cleaned_data["library_3"],
            self.cleaned_data["library_4"],
            self.cleaned_data["library_5"],
            self.cleaned_data["library_6"],
            self.cleaned_data["library_7"],
            self.cleaned_data["library_8"],
        ]
        lib_string = ",".join(str(x.id) if x else "" for x in chosen_libraries)
        return f"full-report-{lib_string}"

    def _get_library_order(self, top_libraries) -> list[int]:
        library_order = [
            x.id
            for x in [
                self.cleaned_data["library_1"],
                self.cleaned_data["library_2"],
                self.cleaned_data["library_3"],
                self.cleaned_data["library_4"],
                self.cleaned_data["library_5"],
                self.cleaned_data["library_6"],
                self.cleaned_data["library_7"],
                self.cleaned_data["library_8"],
            ]
            if x is not None
        ]
        if not library_order:
            library_order = [x.id for x in top_libraries]
        return library_order

    def _get_top_contributors_overall(self):
        return (
            CommitAuthor.objects.all()
            .annotate(
                commit_count=Count(
                    "commit",
                    filter=Q(
                        commit__library_version__library__in=self.library_queryset
                    ),
                )
            )
            .values("name", "avatar_url", "commit_count", "github_profile_url")
            .order_by("-commit_count")[:10]
        )

    def _get_top_contributors_for_library(self, library_order):
        top_contributors_library = []
        for library_id in library_order:
            top_contributors_library.append(
                CommitAuthor.objects.filter(
                    commit__library_version__library_id=library_id
                )
                .annotate(commit_count=Count("commit"))
                .order_by("-commit_count")[:10]
            )
        return top_contributors_library

    def get_stats(self):
        commit_count = Commit.objects.filter(
            library_version__library__in=self.library_queryset
        ).count()

        top_libraries = get_top_libraries()
        library_order = self._get_library_order(top_libraries)
        libraries = Library.objects.filter(id__in=library_order)
        library_data = [
            {
                "library": x[0],
                "full_count": x[1],
                "top_contributors": x[2],
            }
            for x in zip(
                sorted(list(libraries), key=lambda x: library_order.index(x.id)),
                get_library_full_counts(libraries, library_order),
                self._get_top_contributors_for_library(library_order),
            )
        ]
        top_contributors = self._get_top_contributors_overall()
        mailinglist_total = EmailData.objects.all().aggregate(total=Sum("count"))[
            "total"
        ]
        first_version = Version.objects.order_by("release_date").first()
        return {
            "mailinglist_counts": EmailData.objects.with_total_counts().order_by(
                "-total_count"
            )[:10],
            "mailinglist_total": mailinglist_total,
            "first_version": first_version,
            "commit_count": commit_count,
            "top_contributors": top_contributors,
            "library_data": library_data,
            "top_libraries": top_libraries,
            "library_count": self.library_queryset.count(),
        }

    def cache_html(self, base_uri=None):
        """Render and cache the html for this report."""
        # ensure we have "cleaned_data"
        if not self.is_valid():
            return ""
        try:
            context = self.get_stats()
            if base_uri:
                context["base_uri"] = base_uri
            html = render_to_string(self.html_template_name, context)
        except FileNotFoundError as e:
            html = (
                f"An error occurred generating the report: {e}. To see the image "
                f"which is broken copy the error and run the report again. This "
                f"error isn't shown on subsequent runs."
            )
        self.cache_set(html)
        return html

    def cache_get(self) -> RenderedContent | None:
        return RenderedContent.objects.filter(cache_key=self.cache_key).first()

    def cache_clear(self):
        return RenderedContent.objects.filter(cache_key=self.cache_key).delete()

    def cache_set(self, content_html):
        """Cache the html for this report."""
        return RenderedContent.objects.update_or_create(
            cache_key=self.cache_key,
            defaults={
                "content_html": content_html,
                "content_type": "text/html",
            },
        )


class CreateReportForm(CreateReportFullForm):
    """Form for creating a report for a specific release."""

    html_template_name = "admin/release_report_detail.html"
    # queryset will be set in __init__
    report_configuration = ModelChoiceField(queryset=ReportConfiguration.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # we want to allow master, develop, the latest release, the latest beta, along
        # with any report configuration matching no Version, exclude all others.
        exclusion_versions = []
        if betas := Version.objects.filter(beta=True).order_by("-release_date")[1:]:
            exclusion_versions += betas
        if older_releases := Version.objects.filter(
            active=True, full_release=True
        ).order_by("-release_date")[1:]:
            exclusion_versions += older_releases
        qs = ReportConfiguration.objects.exclude(
            version__in=[v.name for v in exclusion_versions]
        ).order_by("-version")

        self.fields["report_configuration"].queryset = qs
        self.fields["library_1"].help_text = (
            "If none are selected, all libraries will be selected."
        )

    @property
    def cache_key(self):
        chosen_libraries = [
            self.cleaned_data["library_1"],
            self.cleaned_data["library_2"],
            self.cleaned_data["library_3"],
            self.cleaned_data["library_4"],
            self.cleaned_data["library_5"],
            self.cleaned_data["library_6"],
            self.cleaned_data["library_7"],
            self.cleaned_data["library_8"],
        ]
        lib_string = ",".join(str(x.id) if x else "" for x in chosen_libraries)
        report_configuration = self.cleaned_data["report_configuration"]
        return f"release-report-{lib_string}-{report_configuration.version}"

    def get_stats(self):
        report_configuration = self.cleaned_data["report_configuration"]
        committee_members = report_configuration.financial_committee_members.all()
        # NOTE TO FUTURE DEVS: remember to account for the fact that a report
        #  configuration may not match with a real version in frequent cases where
        #  reports are generated before the release version has been created.
        (report_before_release, prior_version, version) = determine_versions(
            report_configuration.version
        )

        # trigger tasks first to run in parallel
        mailing_list_contributors_task = count_mailinglist_contributors.delay(
            prior_version.pk, version.pk
        )
        mailing_list_stats_task = get_mailing_list_stats.delay(
            prior_version.pk, version.pk
        )
        commit_contributors_task = count_commit_contributors_totals.delay(
            version.pk, prior_version.pk
        )
        new_subscribers_stats_task = get_new_subscribers_stats.delay(
            prior_version.release_date, version.release_date or date.today()
        )
        mailinglist_wordcloud_task = generate_mailinglist_cloud.delay(
            prior_version.pk, version.pk
        )
        # if the report is based on a live version, look for stats for that
        # version, otherwise use the stats for the prior (live) version
        search_wordcloud_task = generate_search_cloud.delay(
            prior_version.pk if report_before_release else version.pk
        )
        new_contributors_count_task = get_new_contributors_count.delay(version.pk)
        # end of task triggering

        commit_count, version_commit_count = get_commit_counts(version)
        top_libraries_for_version = get_top_libraries_for_version(version)
        top_libraries_by_name = get_libraries_by_name(version)
        library_order = self._get_library_order(top_libraries_by_name)
        # TODO: we may in future need to find a way to show the removed libraries, for
        #  now it's not needed. In that case the distinction between running this on a
        #  ReportConfiguration with a real 'version' entry vs one that instead uses 'master'
        #  will need to be considered
        libraries = get_libraries(library_order)
        new_libraries = libraries.exclude(
            library_version__version__release_date__lte=prior_version.release_date
        ).prefetch_related("authors")
        top_contributors = get_top_contributors_for_version(version)
        mailinglist_counts = get_mailinglist_counts(version)
        lines_added, lines_removed = lines_changes_count(version)
        opened_issues_count, closed_issues_count = get_issues_counts(
            prior_version, version
        )
        # TODO: connected to above todo, add removed_libraries.count()
        removed_library_count = 0

        library_data = get_library_data(library_order, prior_version.pk, version.pk)
        slack_stats = get_slack_stats(prior_version, version)

        library_index_library_data = get_libraries_for_index(library_data, version)
        batched_library_data = conditional_batched(
            library_data,
            2,
            lambda x: x.get("top_contributors_release").count()
            <= RELEASE_REPORT_AUTHORS_PER_PAGE_THRESHOLD,
        )
        git_graph_data = get_git_graph_data(prior_version, version)
        download = get_download_links(version)
        ### completed task handling ###
        (mailinglist_contributor_release_count, mailinglist_contributor_new_count) = (
            mailing_list_contributors_task.get()
        )
        (mailinglist_post_stats, total_mailinglist_count) = (
            mailing_list_stats_task.get()
        )
        (commit_contributors_release_count, commit_contributors_new_count) = (
            commit_contributors_task.get()
        )
        (
            mailinglist_words,
            mailinglist_wordcloud_base64,
            mailinglist_wordcloud_top_words,
        ) = mailinglist_wordcloud_task.get()
        (search_wordcloud_base64, search_wordcloud_top_words, search_stats) = (
            search_wordcloud_task.get()
        )
        global_contributors_new_count = new_contributors_count_task.get()

        return {
            "committee_members": committee_members,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "version": version,
            "report_configuration": report_configuration,
            "prior_version": prior_version,
            "opened_issues_count": opened_issues_count,
            "closed_issues_count": closed_issues_count,
            "mailinglist_wordcloud_base64": mailinglist_wordcloud_base64,
            "mailinglist_wordcloud_frequencies": mailinglist_wordcloud_top_words,
            "mailinglist_counts": mailinglist_counts,
            "mailinglist_total": total_mailinglist_count or 0,
            "mailinglist_contributor_release_count": mailinglist_contributor_release_count,  # noqa: E501
            "mailinglist_contributor_new_count": mailinglist_contributor_new_count,
            "mailinglist_post_stats": mailinglist_post_stats,
            "mailinglist_new_subscribers_stats": new_subscribers_stats_task.get(),
            "mailinglist_charts_start_year": prior_version.release_date.year,
            "search_wordcloud_base64": search_wordcloud_base64,
            "search_wordcloud_frequencies": search_wordcloud_top_words,
            "search_stats": search_stats,
            "commit_contributors_release_count": commit_contributors_release_count,
            "commit_contributors_new_count": commit_contributors_new_count,
            "global_contributors_new_count": global_contributors_new_count,
            "commit_count": commit_count,
            "version_commit_count": version_commit_count,
            "top_contributors_release_overall": top_contributors,
            "library_data": library_data,
            "new_libraries": new_libraries,
            "batched_library_data": batched_library_data,
            "top_libraries_for_version": top_libraries_for_version,
            "library_count": libraries.count(),
            "library_index_libraries": library_index_library_data,
            "added_library_count": new_libraries.count(),
            "removed_library_count": removed_library_count,
            "downloads": download,
            "contribution_box_graph": git_graph_data,
            "slack_channels": get_slack_channels(),
            "slack": slack_stats,
        }

    def generate_context(
        self, report_configuration: ReportConfiguration, stats_results: dict
    ):
        committee_members = report_configuration.financial_committee_members.all()

        # NOTE TO FUTURE DEVS: remember to account for the fact that a report
        #  configuration may not match with a real version in frequent cases where
        #  reports are generated before the release version has been created.
        (report_before_release, prior_version, version) = determine_versions(
            report_configuration.version
        )

        # Unpack stats_results in the same order as tasks were defined in the workflow
        (
            (mailinglist_contributor_release_count, mailinglist_contributor_new_count),
            (mailinglist_post_stats, total_mailinglist_count),
            (commit_contributors_release_count, commit_contributors_new_count),
            mailinglist_new_subscribers_stats,
            (
                mailinglist_words,
                mailinglist_wordcloud_base64,
                mailinglist_wordcloud_top_words,
            ),
            (search_wordcloud_base64, search_wordcloud_top_words, search_stats),
            global_contributors_new_count,
        ) = stats_results

        # Compute the synchronous stats that don't require async tasks
        commit_count, version_commit_count = get_commit_counts(version)
        top_libraries_for_version = get_top_libraries_for_version(version)
        top_libraries_by_name = get_libraries_by_name(version)
        library_order = self._get_library_order(top_libraries_by_name)
        # TODO: we may in future need to find a way to show the removed libraries, for
        #  now it's not needed. In that case the distinction between running this on a
        #  ReportConfiguration with a real 'version' entry vs one that instead uses 'master'
        #  will need to be considered
        libraries = get_libraries(library_order)
        new_libraries = libraries.exclude(
            library_version__version__release_date__lte=prior_version.release_date
        ).prefetch_related("authors")
        top_contributors = get_top_contributors_for_version(version)
        mailinglist_counts = get_mailinglist_counts(version)
        lines_added, lines_removed = lines_changes_count(version)
        opened_issues_count, closed_issues_count = get_issues_counts(
            prior_version, version
        )
        # TODO: connected to above todo, add removed_libraries.count()
        removed_library_count = 0

        library_data = get_library_data(library_order, prior_version.pk, version.pk)
        slack_stats = get_slack_stats(prior_version, version)

        library_index_library_data = get_libraries_for_index(library_data, version)
        batched_library_data = conditional_batched(
            library_data,
            2,
            lambda x: x.get("top_contributors_release").count()
            <= RELEASE_REPORT_AUTHORS_PER_PAGE_THRESHOLD,
        )
        git_graph_data = get_git_graph_data(prior_version, version)
        download = get_download_links(version)

        return {
            "committee_members": committee_members,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "version": version,
            "report_configuration": report_configuration,
            "prior_version": prior_version,
            "opened_issues_count": opened_issues_count,
            "closed_issues_count": closed_issues_count,
            "mailinglist_wordcloud_base64": mailinglist_wordcloud_base64,
            "mailinglist_wordcloud_frequencies": mailinglist_wordcloud_top_words,
            "mailinglist_counts": mailinglist_counts,
            "mailinglist_total": total_mailinglist_count or 0,
            "mailinglist_contributor_release_count": mailinglist_contributor_release_count,  # noqa: E501
            "mailinglist_contributor_new_count": mailinglist_contributor_new_count,
            "mailinglist_post_stats": mailinglist_post_stats,
            "mailinglist_new_subscribers_stats": mailinglist_new_subscribers_stats,
            "mailinglist_charts_start_year": prior_version.release_date.year,
            "search_wordcloud_base64": search_wordcloud_base64,
            "search_wordcloud_frequencies": search_wordcloud_top_words,
            "search_stats": search_stats,
            "commit_contributors_release_count": commit_contributors_release_count,
            "commit_contributors_new_count": commit_contributors_new_count,
            "global_contributors_new_count": global_contributors_new_count,
            "commit_count": commit_count,
            "version_commit_count": version_commit_count,
            "top_contributors_release_overall": top_contributors,
            "library_data": library_data,
            "new_libraries": new_libraries,
            "batched_library_data": batched_library_data,
            "top_libraries_for_version": top_libraries_for_version,
            "library_count": libraries.count(),
            "library_index_libraries": library_index_library_data,
            "added_library_count": new_libraries.count(),
            "removed_library_count": removed_library_count,
            "downloads": download,
            "contribution_box_graph": git_graph_data,
            "slack_channels": get_slack_channels(),
            "slack": slack_stats,
        }

    def render_with_stats(self, stats_results, base_uri=None):
        """Render HTML with pre-computed stats results"""
        context = self.generate_context(
            self.cleaned_data["report_configuration"], stats_results
        )
        if base_uri:
            context["base_uri"] = base_uri
        html = render_to_string(self.html_template_name, context)
        self.cache_set(html)
        return html


class CommitAuthorEmailForm(Form):
    """
    This model is used to allow developers to claim a commit author
    by email address.
    """

    email = forms.EmailField()

    class Meta:
        fields = ["email"]

    def clean_email(self):
        """Emails should have been created by the commit import process, so we need to
        ensure the email exists."""
        email = self.cleaned_data.get("email")
        commit_author_email = CommitAuthorEmail.objects.filter(
            email__iexact=email
        ).first()
        msg = None

        if not commit_author_email:
            msg = "Email address is not associated with any commits."
        elif commit_author_email.author.user is not None:
            msg = (
                "This email address is already associated with a user. Report an "
                "issue if this is incorrect."
            )
        elif commit_author_email.claim_verified:
            msg = (
                "This email address has already been claimed and verified. Report an"
                " issue if this is incorrect."
            )
        if msg:
            raise forms.ValidationError(msg)

        return email
