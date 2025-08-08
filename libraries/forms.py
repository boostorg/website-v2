from functools import cached_property
from itertools import groupby, chain
from operator import attrgetter
from dataclasses import dataclass, field
from datetime import date, timedelta


from django.template.loader import render_to_string
from django.db.models import F, Q, Count, OuterRef, Sum, When, Value, Case
from django.forms import Form, ModelChoiceField, ModelForm, BooleanField

from core.models import RenderedContent
from reports.generation import (
    generate_wordcloud,
    get_mailing_list_post_stats,
    get_new_subscribers_stats,
)
from slack.models import Channel, SlackActivityBucket, SlackUser
from versions.models import Version, ReportConfiguration
from .models import (
    Commit,
    CommitAuthor,
    Issue,
    Library,
    LibraryVersion,
)
from libraries.constants import SUB_LIBRARIES
from mailing_list.models import EmailData
from .utils import batched, conditional_batched


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

    def _get_top_libraries(self):
        return self.library_queryset.annotate(
            commit_count=Count("library_version__commit")
        ).order_by("-commit_count")[:5]

    def _get_library_order(self, top_libraries):
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

    def _get_library_full_counts(self, libraries, library_order):
        return sorted(
            list(
                libraries.annotate(
                    commit_count=Count("library_version__commit")
                ).values("commit_count", "id")
            ),
            key=lambda x: library_order.index(x["id"]),
        )

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

        top_libraries = self._get_top_libraries()
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
                self._get_library_full_counts(libraries, library_order),
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

    def cache_html(self):
        """Render and cache the html for this report."""
        # ensure we have "cleaned_data"
        if not self.is_valid():
            return ""
        try:
            html = render_to_string(self.html_template_name, self.get_stats())
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

    report_configuration = ModelChoiceField(
        queryset=ReportConfiguration.objects.order_by("-version")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def _get_top_contributors_for_version(self, version):
        return (
            CommitAuthor.objects.filter(commit__library_version__version=version)
            .annotate(
                commit_count=Count(
                    "commit",
                    filter=Q(
                        commit__library_version__library__in=self.library_queryset
                    ),
                )
            )
            .order_by("-commit_count")[:10]
        )

    def _get_library_queryset_by_version(
        self, version: Version, annotate_commit_count=False
    ):
        qs = self.library_queryset.none()
        if version:
            qs = self.library_queryset.filter(
                library_version=LibraryVersion.objects.filter(
                    library=OuterRef("id"), version=version
                )[:1],
            )
        if annotate_commit_count:
            qs = qs.annotate(commit_count=Count("library_version__commit"))
        return qs

    def _get_top_libraries_for_version(self, version):
        library_qs = self._get_library_queryset_by_version(
            version, annotate_commit_count=True
        )
        return library_qs.order_by("-commit_count")

    def _get_libraries_by_name(self, version):
        library_qs = self._get_library_queryset_by_version(
            version, annotate_commit_count=True
        )
        return library_qs.order_by("name")

    def _get_libraries_by_quality(self, version):
        # returns "great", "good", and "standard" libraries in that order
        library_qs = self._get_library_queryset_by_version(version)
        return list(
            chain(
                library_qs.filter(graphic__isnull=False),
                library_qs.filter(graphic__isnull=True, is_good=True),
                library_qs.filter(graphic__isnull=True, is_good=False),
            )
        )

    def _get_library_version_counts(self, library_order, version):
        library_qs = self._get_library_queryset_by_version(
            version, annotate_commit_count=True
        )
        return sorted(
            list(library_qs.values("commit_count", "id")),
            key=lambda x: library_order.index(x["id"]),
        )

    def _global_new_contributors(self, version):
        version_lt = list(
            Version.objects.minor_versions()
            .filter(version_array__lt=version.cleaned_version_parts_int)
            .order_by("id")
            .values_list("id", flat=True)
        )

        prior_version_author_ids = (
            CommitAuthor.objects.filter(commit__library_version__version__in=version_lt)
            .distinct()
            .values_list("id", flat=True)
        )

        version_author_ids = (
            CommitAuthor.objects.filter(
                commit__library_version__version__in=version_lt + [version.id]
            )
            .distinct()
            .values_list("id", flat=True)
        )

        return set(version_author_ids) - set(prior_version_author_ids)

    def _count_new_contributors(self, libraries, library_order, version):
        version_lt = list(
            Version.objects.minor_versions()
            .filter(version_array__lt=version.cleaned_version_parts_int)
            .values_list("id", flat=True)
        )
        version_lte = version_lt + [version.id]
        lt_subquery = LibraryVersion.objects.filter(
            version__in=version_lt,
            library=OuterRef("id"),
        ).values("id")
        lte_subquery = LibraryVersion.objects.filter(
            version__in=version_lte,
            library=OuterRef("id"),
        ).values("id")
        return sorted(
            list(
                libraries.annotate(
                    authors_before_release_count=Count(
                        "library_version__commit__author",
                        filter=Q(library_version__in=lt_subquery),
                        distinct=True,
                    ),
                    authors_through_release_count=Count(
                        "library_version__commit__author",
                        filter=Q(library_version__in=lte_subquery),
                        distinct=True,
                    ),
                )
                .annotate(
                    count=F("authors_through_release_count")
                    - F("authors_before_release_count")
                )
                .values("id", "count")
            ),
            key=lambda x: library_order.index(x["id"]),
        )

    def _count_issues(self, libraries, library_order, version, prior_version):
        data = {
            x["library_id"]: x
            for x in Issue.objects.count_opened_closed_during_release(
                version, prior_version
            ).filter(library_id__in=[x.id for x in libraries])
        }
        ret = []
        for lib_id in library_order:
            if lib_id in data:
                ret.append(data[lib_id])
            else:
                ret.append({"opened": 0, "closed": 0, "library_id": lib_id})
        return ret

    def _count_commit_contributors_totals(self, version, prior_version):
        """Get a count of contributors for this release, and a count of
        new contributors.

        """
        version_lt = list(
            Version.objects.minor_versions()
            .filter(version_array__lte=prior_version.cleaned_version_parts_int)
            .values_list("id", flat=True)
        )
        version_lte = version_lt + [version.id]
        lt_subquery = LibraryVersion.objects.filter(
            version__in=version_lt,
            library=OuterRef("id"),
        ).values("id")
        lte_subquery = LibraryVersion.objects.filter(
            version__in=version_lte,
            library=OuterRef("id"),
        ).values("id")
        qs = self.library_queryset.aggregate(
            this_release_count=Count(
                "library_version__commit__author",
                filter=Q(library_version__version=version),
                distinct=True,
            ),
            authors_before_release_count=Count(
                "library_version__commit__author",
                filter=Q(library_version__in=lt_subquery),
                distinct=True,
            ),
            authors_through_release_count=Count(
                "library_version__commit__author",
                filter=Q(library_version__in=lte_subquery),
                distinct=True,
            ),
        )
        new_count = (
            qs["authors_through_release_count"] - qs["authors_before_release_count"]
        )
        this_release_count = qs["this_release_count"]
        return this_release_count, new_count

    def _get_top_contributors_for_library_version(self, library_order, version):
        top_contributors_release = []
        for library_id in library_order:
            top_contributors_release.append(
                CommitAuthor.objects.filter(
                    commit__library_version=LibraryVersion.objects.get(
                        version=version, library_id=library_id
                    )
                )
                .annotate(commit_count=Count("commit"))
                .order_by("-commit_count")[:10]
            )
        return top_contributors_release

    def _count_mailinglist_contributors(self, version, prior_version):
        version_lt = list(
            Version.objects.minor_versions()
            .filter(version_array__lte=prior_version.cleaned_version_parts_int)
            .values_list("id", flat=True)
        )
        version_lte = version_lt + [version.id]
        current = (
            EmailData.objects.filter(version__in=version_lte)
            .distinct("author_id")
            .count()
        )
        prior = (
            EmailData.objects.filter(version__in=version_lt)
            .distinct("author_id")
            .count()
        )
        release = EmailData.objects.filter(version=version).count()
        return release, current - prior

    def _get_library_versions(self, library_order, version):
        return sorted(
            list(
                LibraryVersion.objects.filter(
                    version=version, library_id__in=library_order
                )
            ),
            key=lambda x: library_order.index(x.library_id),
        )

    def _get_git_graph_data(self, prior_version: Version | None, version: Version):
        """Fetch commit count data for a release and return an instance of Graph.

        Returns data in a format to easily create a github style green box commit graph.

        """
        if prior_version is None:
            return None

        @dataclass
        class Day:
            date: date
            count: int
            color: str = ""

        @dataclass
        class Week:
            days: list[Day] = field(default_factory=list)

            @cached_property
            def max(self):
                """The max number of commits this week."""
                return max(x.count for x in self.days)

        @dataclass
        class Graph:
            weeks: list[Week] = field(default_factory=list)
            colors: list[str] = field(
                default_factory=lambda: [
                    "#E8F5E9",
                    "#C8E6C9",
                    "#A5D6A7",
                    "#81C784",
                    "#66BB6A",
                    "#4CAF50",
                    "#43A047",
                    "#388E3C",
                    "#2E7D32",
                    "#1B5E20",
                ],
            )

            @cached_property
            def graph_start(self):
                return start.strftime("%B '%y")

            @cached_property
            def graph_end(self):
                return end.strftime("%B '%y")

            @cached_property
            def max(self):
                """The max number of commits in all weeks."""
                return max(x.max for x in self.weeks)

            def append_day(self, day: Day):
                """Append a day into the last week of self.weeks.

                - Automatically create a new week if there are already 7 days in the
                last week.
                """
                if len(self.weeks) == 0 or len(self.weeks[-1].days) == 7:
                    self.weeks.append(Week())
                self.weeks[-1].days.append(day)

            def apply_colors(self):
                """Iterate through each day and apply a color.

                - The color is selected based on the number of commits made on
                that day, relative to the highest number of commits in all days in
                Graph.weeks.days.

                """
                if not (high := self.max):
                    # No commits this release
                    # TODO: we may want a more elegant solution
                    #  than just not graphing this library
                    return
                for week in self.weeks:
                    for day in week.days:
                        decimal = day.count / high
                        if decimal == 1:
                            day.color = self.colors[-1]
                        else:
                            idx = int(decimal * len(self.colors))
                            day.color = self.colors[idx]

        count_query = (
            Commit.objects.filter(library_version__version=version)
            .values("committed_at__date")
            .annotate(count=Count("id"))
        )
        counts_by_date = {x["committed_at__date"]: x["count"] for x in count_query}

        graph = Graph()
        # The start date is the release date of the previous version
        # The end date is one day before the release date of the current version
        start: date = prior_version.release_date
        end: date = (version.release_date or date.today()) - timedelta(days=1)

        # if the release started on a Thursday, we want to add Sun -> Wed to the data
        # with empty counts, even if they aren't part of the release.
        for i in range(start.weekday(), 0, -1):
            day = Day(date=start - timedelta(days=i), count=0)
            graph.append_day(day)

        current_date = start
        while current_date <= end:
            day = Day(date=current_date, count=counts_by_date.get(current_date, 0))
            graph.append_day(day)
            current_date = current_date + timedelta(days=1)
        graph.apply_colors()
        return graph

    def _get_slack_stats(self, prior_version, version):
        """Returns all slack related stats.

        Only returns channels with activity.
        """
        stats = []
        for channel in Channel.objects.filter(name__istartswith="boost"):
            channel_stat = self._get_slack_stats_for_channels(
                prior_version, version, channels=[channel]
            )
            channel_stat["channel"] = channel
            if channel_stat["user_count"] > 0:
                stats.append(channel_stat)
        stats.sort(key=lambda x: -(x["total"] or 0))  # Convert None to 0
        return stats

    def _get_slack_stats_for_channels(
        self, prior_version, version, channels: list[Channel] | None = None
    ):
        """Get slack stats for specific channels, or all channels."""
        start = prior_version.release_date
        end = date.today()
        if version.release_date:
            end = version.release_date - timedelta(days=1)
        # count of all messages in the date range
        q = Q(day__range=[start, end])
        if channels:
            q &= Q(channel__in=channels)
        total = SlackActivityBucket.objects.filter(q).aggregate(total=Sum("count"))[
            "total"
        ]
        # message counts per user in the date range
        q = Q(slackactivitybucket__day__range=[start, end])
        if channels:
            q &= Q(slackactivitybucket__channel__in=channels)
        per_user = (
            SlackUser.objects.annotate(
                total=Sum(
                    "slackactivitybucket__count",
                    filter=q,
                )
            )
            .filter(total__gt=0)
            .order_by("-total")
        )
        q = Q()
        if channels:
            q &= Q(channel__in=channels)
        distinct_users = (
            SlackActivityBucket.objects.filter(q)
            .order_by("user_id")
            .distinct("user_id")
        )
        new_user_count = (
            distinct_users.filter(day__lte=end).count()
            - distinct_users.filter(day__lt=start).count()
        )
        return {
            "users": per_user[:10],
            "user_count": per_user.count(),
            "total": total,
            "new_user_count": new_user_count,
        }

    def _get_dependency_data(self, library_order, version):
        diffs_by_id = {
            x["library_id"]: x for x in version.get_dependency_diffs().values()
        }
        diffs = []
        for lib_id in library_order:
            diffs.append(diffs_by_id.get(lib_id, {}))
        return diffs

    def get_library_data(self, libraries, library_order, prior_version, version):
        library_data = [
            {
                "library": item[0],
                "full_count": item[1],
                "version_count": item[2],
                "top_contributors_release": item[3],
                "new_contributors_count": item[4],
                "issues": item[5],
                "library_version": item[6],
                "deps": item[7],
            }
            for item in zip(
                libraries,
                self._get_library_full_counts(libraries, library_order),
                self._get_library_version_counts(library_order, version),
                self._get_top_contributors_for_library_version(library_order, version),
                self._count_new_contributors(libraries, library_order, version),
                self._count_issues(libraries, library_order, version, prior_version),
                self._get_library_versions(library_order, version),
                self._get_dependency_data(library_order, version),
            )
        ]
        return [x for x in library_data if x["version_count"]["commit_count"] > 0]

    def get_stats(self):
        report_configuration = self.cleaned_data["report_configuration"]
        version = Version.objects.filter(name=report_configuration.version).first()

        prior_version = None
        if not version:
            # if the version is not set then the user has chosen a report configuration
            #  that's not matching a live version, so we use the most recent version
            version = Version.objects.filter(name="master").first()
            prior_version = Version.objects.most_recent()

        downloads = {
            k: list(v)
            for k, v in groupby(
                version.downloads.all().order_by("operating_system"),
                key=attrgetter("operating_system"),
            )
        }

        if not prior_version:
            prior_version = (
                Version.objects.minor_versions()
                .filter(version_array__lt=version.cleaned_version_parts_int)
                .order_by("-version_array")
                .first()
            )

        commit_count = Commit.objects.filter(
            library_version__version__name__lte=version.name,
            library_version__library__in=self.library_queryset,
        ).count()
        version_commit_count = Commit.objects.filter(
            library_version__version=version,
            library_version__library__in=self.library_queryset,
        ).count()

        top_libraries_for_version = self._get_top_libraries_for_version(version)
        top_libraries_by_name = self._get_libraries_by_name(version)
        library_order = self._get_library_order(top_libraries_by_name)
        libraries = Library.objects.filter(id__in=library_order).order_by(
            Case(
                *[When(id=pk, then=Value(pos)) for pos, pk in enumerate(library_order)]
            )
        )

        library_data = self.get_library_data(
            libraries, library_order, prior_version, version
        )
        AUTHORS_PER_PAGE_THRESHOLD = 6
        batched_library_data = conditional_batched(
            library_data,
            2,
            lambda x: x.get("top_contributors_release").count()
            <= AUTHORS_PER_PAGE_THRESHOLD,
        )
        new_libraries = libraries.exclude(
            library_version__version__release_date__lte=prior_version.release_date
        ).prefetch_related("authors")
        # TODO: we may in future need to find a way to show the removed libraries, for
        #  now it's not needed. In that case the distinction between running this on a
        #  ReportConfiguration with a real 'version' entry vs one that instead uses 'master'
        #  will need to be considered
        top_contributors = self._get_top_contributors_for_version(version)
        # total messages sent during this release (version)
        total_mailinglist_count = EmailData.objects.filter(version=version).aggregate(
            total=Sum("count")
        )["total"]
        mailinglist_counts = (
            EmailData.objects.filter(version=version)
            .with_total_counts()
            .order_by("-total_count")[:10]
        )
        (
            mailinglist_contributor_release_count,
            mailinglist_contributor_new_count,
        ) = self._count_mailinglist_contributors(version, prior_version)
        (
            commit_contributors_release_count,
            commit_contributors_new_count,
        ) = self._count_commit_contributors_totals(version, prior_version)

        added_library_count = new_libraries.count()
        # TODO: connected to above todo, add removed_libraries.count()
        removed_library_count = 0

        lines_added = LibraryVersion.objects.filter(
            version=version,
            library__in=self.library_queryset,
        ).aggregate(lines=Sum("insertions"))["lines"]

        lines_removed = LibraryVersion.objects.filter(
            version=version,
            library__in=self.library_queryset,
        ).aggregate(lines=Sum("deletions"))["lines"]
        # we want 2 channels per pdf page, use batched to get groups of 2
        slack_stats = batched(self._get_slack_stats(prior_version, version), 2)
        slack_channels = batched(
            Channel.objects.filter(name__istartswith="boost").order_by("name"), 10
        )
        committee_members = report_configuration.financial_committee_members.all()
        mailinglist_post_stats = get_mailing_list_post_stats(
            prior_version.release_date, version.release_date or date.today()
        )
        new_subscribers_stats = get_new_subscribers_stats(
            prior_version.release_date, version.release_date or date.today()
        )
        library_index_library_data = []
        for library in self._get_libraries_by_quality(version):
            library_index_library_data.append(
                (
                    library,
                    library in [lib["library"] for lib in library_data],
                )
            )
        wordcloud_base64, wordcloud_top_words = generate_wordcloud(
            version, prior_version
        )

        opened_issues_count = (
            Issue.objects.filter(library__in=self.library_queryset)
            .opened_during_release(version, prior_version)
            .count()
        )
        closed_issues_count = (
            Issue.objects.filter(library__in=self.library_queryset)
            .closed_during_release(version, prior_version)
            .count()
        )

        return {
            "committee_members": committee_members,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "wordcloud_base64": wordcloud_base64,
            "wordcloud_frequencies": wordcloud_top_words,
            "version": version,
            "report_configuration": report_configuration,
            "prior_version": prior_version,
            "opened_issues_count": opened_issues_count,
            "closed_issues_count": closed_issues_count,
            "mailinglist_counts": mailinglist_counts,
            "mailinglist_total": total_mailinglist_count or 0,
            "mailinglist_contributor_release_count": mailinglist_contributor_release_count,  # noqa: E501
            "mailinglist_contributor_new_count": mailinglist_contributor_new_count,
            "mailinglist_post_stats": mailinglist_post_stats,
            "mailinglist_new_subscribers_stats": new_subscribers_stats,
            "mailinglist_charts_start_year": prior_version.release_date.year,
            "commit_contributors_release_count": commit_contributors_release_count,
            "commit_contributors_new_count": commit_contributors_new_count,
            "global_contributors_new_count": len(
                self._global_new_contributors(version)
            ),
            "commit_count": commit_count,
            "version_commit_count": version_commit_count,
            "top_contributors_release_overall": top_contributors,
            "library_data": library_data,
            "new_libraries": new_libraries,
            "batched_library_data": batched_library_data,
            "top_libraries_for_version": top_libraries_for_version,
            "library_count": libraries.count(),
            "library_index_libraries": library_index_library_data,
            "added_library_count": added_library_count,
            "removed_library_count": removed_library_count,
            "downloads": downloads,
            "contribution_box_graph": self._get_git_graph_data(prior_version, version),
            "slack_channels": slack_channels,
            "slack": slack_stats,
        }
