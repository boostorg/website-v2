import base64
import io
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import timedelta, date
from functools import cached_property
from itertools import chain, groupby
from operator import attrgetter

import psycopg2
from django.conf import settings
from django.contrib.staticfiles import finders
from django.db.models import OuterRef, Q, F, Case, When, Value, Sum, Count
from matplotlib import pyplot as plt
from wordcloud import WordCloud, STOPWORDS
from algoliasearch.analytics.client import AnalyticsClientSync

from core.models import SiteSettings
from libraries.constants import RELEASE_REPORT_SEARCH_TOP_COUNTRIES_LIMIT
from libraries.models import (
    WordcloudMergeWord,  # TODO: move model to this app
    CommitAuthor,
    LibraryVersion,
    Issue,
    Commit,
    Library,
)
from libraries.utils import batched
from mailing_list.models import EmailData
from reports.constants import WORDCLOUD_FONT
from slack.models import Channel, SlackActivityBucket, SlackUser
from versions.exceptions import BoostImportedDataException
from versions.models import Version

logger = logging.getLogger(__name__)


def generate_mailinglist_words(
    prior_version: Version, version: Version
) -> dict[str, int]:
    """Generates word frequencies from mailing list content between two versions."""
    word_frequencies = {}
    for content in get_mail_content(version, prior_version):
        for key, val in WordCloud().process_text(content).items():
            key = key.strip().lower()
            if len(key) < 2:
                continue
            if key in SiteSettings.load().wordcloud_ignore_set:
                continue
            if key not in word_frequencies:
                word_frequencies[key] = 0
            word_frequencies[key] += val

    return word_frequencies


def generate_algolia_words(
    client: AnalyticsClientSync, version: Version
) -> dict[str, int]:
    args = {
        "index": version.stripped_boost_url_slug,
        "limit": 100,
    }
    try:
        search_results = client.get_top_searches(**args).to_json()
        search_data = json.loads(search_results)
        searches = search_data.get("searches") or []
        return {r["search"]: r["count"] for r in searches if r["count"] > 1}
    except ValueError:
        return {}


def generate_wordcloud(
    word_frequencies: dict[str, int], width: int, height: int
) -> tuple[str | None, list]:
    """Generates a wordcloud png and returns it as a base64 string and word frequencies.

    Returns:
        Tuple of (base64_encoded_png_string, wordcloud_top_words)
    """
    if not word_frequencies:
        return None, []
    font_relative_path = f"font/{WORDCLOUD_FONT}"
    font_full_path = finders.find(font_relative_path)

    if not font_full_path:
        raise FileNotFoundError(f"Could not find font at {font_relative_path}")

    wc = WordCloud(
        mode="RGBA",
        background_color=None,
        width=width,
        height=height,
        stopwords=STOPWORDS,
        font_path=font_full_path,
    )
    word_frequencies = boost_normalize_words(
        word_frequencies,
        {x.from_word: x.to_word for x in WordcloudMergeWord.objects.all()},
    )
    wordcloud_top_words = [
        word
        for word, frequency in sorted(
            word_frequencies.items(),
            key=lambda x: x[1],  # sort by frequency
            reverse=True,
        )
    ][:200]

    wc.generate_from_frequencies(word_frequencies)
    plt.figure(figsize=(14, 7), facecolor=None)
    plt.imshow(
        wc.recolor(color_func=grey_color_func, random_state=3),
        interpolation="bilinear",
    )
    plt.axis("off")
    image_bytes = io.BytesIO()
    plt.savefig(
        image_bytes,
        format="png",
        dpi=100,
        bbox_inches="tight",
        pad_inches=0,
        transparent=True,
    )
    image_bytes.seek(0)
    return base64.b64encode(image_bytes.read()).decode(), wordcloud_top_words


def boost_normalize_words(frequencies, word_map):
    # from word, to word
    for o, n in word_map.items():
        from_count = frequencies.get(o, 0)
        if not from_count:
            continue
        to_count = frequencies.get(n, 0)
        frequencies[n] = from_count + to_count
        del frequencies[o]
    return frequencies


def grey_color_func(*args, **kwargs):
    return "hsl(0, 0%%, %d%%)" % random.randint(10, 80)


def get_mail_content(version: Version, prior_version: Version):
    if not prior_version or not settings.HYPERKITTY_DATABASE_NAME:
        return []
    conn = psycopg2.connect(settings.HYPERKITTY_DATABASE_URL)
    with conn.cursor(name="fetch-mail-content") as cursor:
        cursor.execute(
            """
                SELECT content FROM hyperkitty_email
                WHERE date >= %(start)s AND date < %(end)s;
            """,
            {
                "start": prior_version.release_date,
                "end": version.release_date or date.today(),
            },
        )
        for [content] in cursor:
            yield content


def get_mailinglist_counts(version: Version):
    return (
        EmailData.objects.filter(version=version)
        .with_total_counts()
        .order_by("-total_count")[:10]
    )


def get_algolia_search_stats(client: AnalyticsClientSync, version: Version) -> dict:
    default_args = {"index": version.stripped_boost_url_slug}
    # search data
    search_response = client.get_searches_count(**default_args).to_json()
    search_data = json.loads(search_response)
    try:
        # country data
        country_results = client.get_top_countries(**default_args, limit=100).to_json()
        country_data = json.loads(country_results)
        countries = country_data.get("countries") or []
        country_stats = {r["country"]: r["count"] for r in countries}
    except ValueError:
        country_stats = {}
    return {
        "total_searches": search_data.get("count"),
        "country_stats": country_stats,
        "top_countries": list(country_stats.items())[
            :RELEASE_REPORT_SEARCH_TOP_COUNTRIES_LIMIT
        ],
    }


def determine_versions(report_configuration_name: str) -> tuple[bool, Version, Version]:
    version = Version.objects.filter(name=report_configuration_name).first()
    report_before_release = False if version else True
    prior_version = None
    if report_before_release:
        # if the version is not set then the user has chosen a report configuration
        #  that's not matching a live version, so we use the most recent version
        version = Version.objects.filter(name="master").first()
        prior_version = Version.objects.most_recent()

    if not prior_version:
        prior_version = (
            Version.objects.minor_versions()
            .filter(version_array__lt=version.cleaned_version_parts_int)
            .order_by("-version_array")
            .first()
        )
    return report_before_release, prior_version, version


def get_dependency_data(library_order, version):
    try:
        dependency_diff_values = version.get_dependency_diffs().values()
    except BoostImportedDataException as e:
        logger.warning(f"Could not get dependency diffs for version {version}: {e}")
        dependency_diff_values = {}

    diffs_by_id = {x["library_id"]: x for x in dependency_diff_values}
    diffs = []
    for lib_id in library_order:
        diffs.append(diffs_by_id.get(lib_id, {}))
    return diffs


def global_new_contributors(version):
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


def get_library_queryset_by_version(version: Version, annotate_commit_count=False):
    from libraries.forms import CreateReportFullForm

    qs = CreateReportFullForm.library_queryset.none()
    if version:
        qs = CreateReportFullForm.library_queryset.filter(
            library_version=LibraryVersion.objects.filter(
                library=OuterRef("id"), version=version
            )[:1],
        )
    if annotate_commit_count:
        qs = qs.annotate(commit_count=Count("library_version__commit"))
    return qs


def get_top_libraries_for_version(version):
    library_qs = get_library_queryset_by_version(version, annotate_commit_count=True)
    return library_qs.order_by("-commit_count")


def get_libraries_by_name(version):
    library_qs = get_library_queryset_by_version(version, annotate_commit_count=True)
    return library_qs.order_by("name")


def get_libraries_by_quality(version):
    # returns "great", "good", and "standard" libraries in that order
    library_qs = get_library_queryset_by_version(version)
    return list(
        chain(
            library_qs.filter(graphic__isnull=False),
            library_qs.filter(graphic__isnull=True, is_good=True),
            library_qs.filter(graphic__isnull=True, is_good=False),
        )
    )


def get_library_version_counts(library_order, version):
    library_qs = get_library_queryset_by_version(version, annotate_commit_count=True)
    return sorted(
        list(library_qs.values("commit_count", "id")),
        key=lambda x: library_order.index(x["id"]),
    )


def get_library_full_counts(libraries, library_order):
    return sorted(
        list(
            libraries.annotate(commit_count=Count("library_version__commit")).values(
                "commit_count", "id"
            )
        ),
        key=lambda x: library_order.index(x["id"]),
    )


def get_top_contributors_for_library_version(library_order, version):
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


def count_new_contributors(libraries, library_order, version):
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


def count_issues(libraries, library_order, version, prior_version):
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


def get_library_versions(library_order, version):
    return sorted(
        list(
            LibraryVersion.objects.filter(version=version, library_id__in=library_order)
        ),
        key=lambda x: library_order.index(x.library_id),
    )


def get_top_contributors_for_version(version):
    from libraries.forms import CreateReportFullForm

    return (
        CommitAuthor.objects.filter(commit__library_version__version=version)
        .annotate(
            commit_count=Count(
                "commit",
                filter=Q(
                    commit__library_version__library__in=CreateReportFullForm.library_queryset
                ),
            )
        )
        .order_by("-commit_count")[:10]
    )


def get_git_graph_data(prior_version: Version | None, version: Version):
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


def get_libraries(library_order: list[int]):
    return Library.objects.filter(id__in=library_order).order_by(
        Case(*[When(id=pk, then=Value(pos)) for pos, pk in enumerate(library_order)])
    )


def get_library_data(library_order: list[int], prior_version_id: int, version_id: int):
    prior_version = Version.objects.get(pk=prior_version_id)
    version = Version.objects.get(pk=version_id)
    libraries = get_libraries(library_order)
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
            get_library_full_counts(libraries, library_order),
            get_library_version_counts(library_order, version),
            get_top_contributors_for_library_version(library_order, version),
            count_new_contributors(libraries, library_order, version),
            count_issues(libraries, library_order, version, prior_version),
            get_library_versions(library_order, version),
            get_dependency_data(library_order, version),
        )
    ]
    return [x for x in library_data if x["version_count"]["commit_count"] > 0]


def get_top_libraries():
    from libraries.forms import CreateReportFullForm

    return CreateReportFullForm.library_queryset.annotate(
        commit_count=Count("library_version__commit")
    ).order_by("-commit_count")[:5]


def lines_changes_count(version: Version):
    from libraries.forms import CreateReportFullForm

    lines_added = LibraryVersion.objects.filter(
        version=version,
        library__in=CreateReportFullForm.library_queryset,
    ).aggregate(lines=Sum("insertions"))["lines"]

    lines_removed = LibraryVersion.objects.filter(
        version=version,
        library__in=CreateReportFullForm.library_queryset,
    ).aggregate(lines=Sum("deletions"))["lines"]

    return lines_added, lines_removed


def get_commit_counts(version: Version):
    from libraries.forms import CreateReportFullForm

    commit_count = Commit.objects.filter(
        library_version__version__name__lte=version.name,
        library_version__library__in=CreateReportFullForm.library_queryset,
    ).count()
    version_commit_count = Commit.objects.filter(
        library_version__version=version,
        library_version__library__in=CreateReportFullForm.library_queryset,
    ).count()

    return commit_count, version_commit_count


def get_issues_counts(prior_version: Version, version: Version):
    from libraries.forms import CreateReportFullForm

    opened_issues_count = (
        Issue.objects.filter(library__in=CreateReportFullForm.library_queryset)
        .opened_during_release(version, prior_version)
        .count()
    )
    closed_issues_count = (
        Issue.objects.filter(library__in=CreateReportFullForm.library_queryset)
        .closed_during_release(version, prior_version)
        .count()
    )

    return opened_issues_count, closed_issues_count


def get_download_links(version: Version):
    return {
        k: list(v)
        for k, v in groupby(
            version.downloads.all().order_by("operating_system"),
            key=attrgetter("operating_system"),
        )
    }


def get_mailinglist_msg_counts(version: Version) -> tuple[int, int]:
    total_mailinglist_count = EmailData.objects.filter(version=version).aggregate(
        total=Sum("count")
    )["total"]
    mailinglist_counts = (
        EmailData.objects.filter(version=version)
        .with_total_counts()
        .order_by("-total_count")[:10]
    )

    return total_mailinglist_count, mailinglist_counts


def get_slack_channels():
    return batched(
        Channel.objects.filter(name__istartswith="boost").order_by("name"), 10
    )


def get_libraries_for_index(
    library_data, version: Version, prior_version: Version | None = None
):
    library_index_library_data = []

    # Get libraries that existed in prior version
    prior_version_library_ids = set()
    if prior_version:
        prior_version_library_ids = set(
            LibraryVersion.objects.filter(version=prior_version).values_list(
                "library_id", flat=True
            )
        )

    changed_libraries = {lib["library"] for lib in library_data}

    for library in get_libraries_by_quality(version):
        is_changed = library in changed_libraries
        is_new = library.id not in prior_version_library_ids
        library_index_library_data.append(
            (
                library,
                is_changed or is_new,
            )
        )
    return library_index_library_data


def get_slack_stats_for_channels(
    prior_version, version, channels: list[Channel] | None = None
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
    total = SlackActivityBucket.objects.filter(q).aggregate(total=Sum("count"))["total"]
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
        SlackActivityBucket.objects.filter(q).order_by("user_id").distinct("user_id")
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


def get_slack_stats(prior_version: Version, version: Version):
    """Returns all slack related stats.

    Only returns channels with activity.
    """
    stats = []
    for channel in Channel.objects.filter(name__istartswith="boost"):
        channel_stat = get_slack_stats_for_channels(
            prior_version, version, channels=[channel]
        )
        channel_stat["channel"] = channel
        if channel_stat["user_count"] > 0:
            stats.append(channel_stat)
    stats.sort(key=lambda x: -(x["total"] or 0))  # Convert None to 0
    # we want 2 channels per pdf page, use batched to get groups of 2
    return batched(stats, 2)
