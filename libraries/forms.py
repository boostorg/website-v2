import io
import base64

import psycopg2
from wordcloud import WordCloud, STOPWORDS
from matplotlib import pyplot as plt

from django.db.models import F, Q, Count, OuterRef, Sum
from django.forms import Form, ModelChoiceField, ModelForm
from django.conf import settings

from versions.models import Version
from .models import Commit, CommitAuthor, Issue, Library, LibraryVersion
from mailing_list.models import EmailData


class LibraryForm(ModelForm):
    class Meta:
        model = Library
        fields = ["categories"]


class VersionSelectionForm(Form):
    queryset = Version.objects.active().defer("data")
    queryset = queryset.exclude(name__in=["develop", "master", "head"])

    version = ModelChoiceField(
        queryset=queryset,
        label="Select a version",
        empty_label="Choose a version...",
    )


class CreateReportFullForm(Form):
    """Form for creating a report over all releases."""

    library_queryset = Library.objects.all().order_by("name")
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

    def _get_top_libraries(self):
        return (
            Library.objects.all()
            .annotate(commit_count=Count("library_version__commit"))
            .order_by("-commit_count")[:5]
        )

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
            .annotate(commit_count=Count("commit"))
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
                .values(
                    "name",
                    "avatar_url",
                    "github_profile_url",
                    "commit_count",
                    "commit__library_version__library_id",
                )
                .order_by("-commit_count")[:10]
            )
        return top_contributors_library

    def get_stats(self):
        commit_count = Commit.objects.count()

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
            "library_count": Library.objects.all().count(),
        }


class CreateReportForm(CreateReportFullForm):
    """Form for creating a report for a specific release."""

    version = ModelChoiceField(
        queryset=Version.objects.minor_versions().order_by("-version_array")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "library_1"
        ].help_text = "If none are selected, all libraries will be selected."

    def _get_top_contributors_for_version(self):
        return (
            CommitAuthor.objects.filter(
                commit__library_version__version=self.cleaned_data["version"]
            )
            .annotate(commit_count=Count("commit"))
            .values("name", "avatar_url", "commit_count", "github_profile_url")
            .order_by("-commit_count")[:10]
        )

    def _get_top_libraries_for_version(self):
        return (
            Library.objects.filter(
                library_version=LibraryVersion.objects.filter(
                    library=OuterRef("id"), version=self.cleaned_data["version"]
                )[:1],
            )
            .annotate(commit_count=Count("library_version__commit"))
            .order_by("-commit_count")
        )

    def _get_library_version_counts(self, libraries, library_order):
        return sorted(
            list(
                libraries.filter(
                    library_version=LibraryVersion.objects.filter(
                        library=OuterRef("id"), version=self.cleaned_data["version"]
                    )[:1]
                )
                .annotate(commit_count=Count("library_version__commit"))
                .values("commit_count", "id")
            ),
            key=lambda x: library_order.index(x["id"]),
        )

    def _count_new_contributors(self, libraries, library_order):
        version = self.cleaned_data["version"]
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

    def _count_issues(self, libraries, library_order, version):
        data = {
            x["library_id"]: x
            for x in Issue.objects.count_opened_closed_during_release(version).filter(
                library_id__in=[x.id for x in libraries]
            )
        }
        ret = []
        for lib_id in library_order:
            if lib_id in data:
                ret.append(data[lib_id])
            else:
                ret.append({"opened": 0, "closed": 0, "library_id": lib_id})
        return ret

    def _count_commit_contributors_totals(self, version):
        """Get a count of contributors for this release, and a count of
        new contributors.

        """
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
        qs = Library.objects.aggregate(
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

    def _get_top_contributors_for_library_version(self, library_order):
        top_contributors_release = []
        for library_id in library_order:
            top_contributors_release.append(
                CommitAuthor.objects.filter(
                    commit__library_version=LibraryVersion.objects.get(
                        version=self.cleaned_data["version"], library_id=library_id
                    )
                )
                .annotate(commit_count=Count("commit"))
                .values(
                    "name",
                    "avatar_url",
                    "github_profile_url",
                    "commit_count",
                    "commit__library_version__library_id",
                )
                .order_by("-commit_count")[:10]
            )
        return top_contributors_release

    def _get_mail_content(self, version):
        prior_version = (
            Version.objects.minor_versions()
            .filter(version_array__lt=version.cleaned_version_parts_int)
            .order_by("-release_date")
            .first()
        )
        if not prior_version or not settings.HYPERKITTY_DATABASE_URL:
            return []
        conn = psycopg2.connect(settings.HYPERKITTY_DATABASE_URL)
        with conn.cursor(name="fetch-mail-content") as cursor:
            cursor.execute(
                """
                    SELECT content FROM hyperkitty_email
                    WHERE date >= %(start)s AND date < %(end)s;
                """,
                {"start": prior_version.release_date, "end": version.release_date},
            )
            for [content] in cursor:
                yield content

    def _generate_hyperkitty_word_cloud(self, version):
        """Generates a wordcloud png and returns it as a base64 string."""
        wc = WordCloud(
            width=1400,
            height=700,
            stopwords=STOPWORDS | {"boost", "Boost", "http", "lists", "via", "https"},
            font_path=settings.BASE_DIR / "static" / "font" / "notosans_mono.woff",
        )
        image_bytes = io.BytesIO()
        frequencies = {}
        for content in self._get_mail_content(version):
            for key, val in wc.process_text(content).items():
                if key not in frequencies:
                    frequencies[key] = 0
                frequencies[key] += val
        if not frequencies:
            return
        wc.generate_from_frequencies(frequencies)
        plt.figure(figsize=(14, 7))
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        image_bytes = io.BytesIO()
        plt.savefig(
            image_bytes,
            format="png",
            dpi=100,
            bbox_inches="tight",
            pad_inches=0,
        )
        image_bytes.seek(0)
        return base64.b64encode(image_bytes.read()).decode()

    def _count_mailinglist_contributors(self, version):
        version_lt = list(
            Version.objects.minor_versions()
            .filter(version_array__lt=version.cleaned_version_parts_int)
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

    def get_stats(self):
        version = self.cleaned_data["version"]
        prior_version = (
            Version.objects.minor_versions()
            .filter(version_array__lt=version.cleaned_version_parts_int)
            .order_by("-version_array")
            .first()
        )

        commit_count = Commit.objects.filter(
            library_version__version__name__lte=version.name
        ).count()
        version_commit_count = Commit.objects.filter(
            library_version__version=version
        ).count()

        top_libraries_for_version = self._get_top_libraries_for_version()
        library_order = self._get_library_order(top_libraries_for_version)
        libraries = Library.objects.filter(id__in=library_order)
        library_names = (
            LibraryVersion.objects.filter(version=version)
            .annotate(name=F("library__name"))
            .order_by("name")
            .values_list("name", flat=True)
        )
        library_data = [
            {
                "library": a,
                "full_count": b,
                "version_count": c,
                "top_contributors_release": d,
                "new_contributors_count": e,
                "issues": f,
                "library_version": g,
            }
            for a, b, c, d, e, f, g in zip(
                sorted(list(libraries), key=lambda x: library_order.index(x.id)),
                self._get_library_full_counts(libraries, library_order),
                self._get_library_version_counts(libraries, library_order),
                self._get_top_contributors_for_library_version(library_order),
                self._count_new_contributors(libraries, library_order),
                self._count_issues(libraries, library_order, version),
                self._get_library_versions(library_order, version),
            )
        ]
        top_contributors = self._get_top_contributors_for_version()
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
        ) = self._count_mailinglist_contributors(version)
        (
            commit_contributors_release_count,
            commit_contributors_new_count,
        ) = self._count_commit_contributors_totals(version)
        library_count = LibraryVersion.objects.filter(version=version).count()
        if prior_version:
            library_count_prior = LibraryVersion.objects.filter(
                version=prior_version
            ).count()
        else:
            library_count_prior = 0

        added_library_count = max(0, library_count - library_count_prior)
        removed_library_count = max(0, library_count_prior - library_count)
        lines_added = LibraryVersion.objects.filter(version=version).aggregate(
            lines=Sum("insertions")
        )["lines"]
        lines_removed = LibraryVersion.objects.filter(version=version).aggregate(
            lines=Sum("deletions")
        )["lines"]
        return {
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "wordcloud_base64": self._generate_hyperkitty_word_cloud(version),
            "version": version,
            "opened_issues_count": Issue.objects.opened_during_release(version).count(),
            "closed_issues_count": Issue.objects.closed_during_release(version).count(),
            "mailinglist_counts": mailinglist_counts,
            "mailinglist_total": total_mailinglist_count,
            "mailinglist_contributor_release_count": mailinglist_contributor_release_count,  # noqa: E501
            "mailinglist_contributor_new_count": mailinglist_contributor_new_count,
            "commit_contributors_release_count": commit_contributors_release_count,
            "commit_contributors_new_count": commit_contributors_new_count,
            "commit_count": commit_count,
            "version_commit_count": version_commit_count,
            "top_contributors_release_overall": top_contributors,
            "library_data": library_data,
            "top_libraries_for_version": top_libraries_for_version,
            "library_count": library_count,
            "library_count_prior": library_count_prior,
            "library_names": library_names,
            "added_library_count": added_library_count,
            "removed_library_count": removed_library_count,
        }
