from django.db.models import F, Q, Count, OuterRef, Sum
from django.forms import Form, ModelChoiceField, ModelForm

from versions.models import Version
from .models import Commit, CommitAuthor, Library, LibraryVersion
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

    def _get_top_emaildata_overall(self):
        return (
            EmailData.objects.annotate(
                name=F("author__name"),
                avatar_url=F("author__avatar_url"),
                github_profile_url=F("author__avatar_url"),
            )
            .values("name", "avatar_url", "github_profile_url")
            .annotate(total_count=Sum("count"))
            .order_by("-total_count")
        )

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
            "mailinglist_counts": self._get_top_emaildata_overall()[:10],
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
        ].help_text = (
            "If none are selected, the top 5 for this release will be auto-selected."
        )

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
            .order_by("-commit_count")[:5]
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

    def _get_top_emaildata_release(self, version):
        return self._get_top_emaildata_overall().filter(version=version)

    def get_stats(self):
        version = self.cleaned_data["version"]

        commit_count = Commit.objects.filter(
            library_version__version__name__lte=version.name
        ).count()
        version_commit_count = Commit.objects.filter(
            library_version__version=version
        ).count()

        top_libraries_for_version = self._get_top_libraries_for_version()
        library_order = self._get_library_order(top_libraries_for_version)
        libraries = Library.objects.filter(id__in=library_order)
        library_data = [
            {
                "library": a,
                "full_count": b,
                "version_count": c,
                "top_contributors_release": d,
                "new_contributors_count": e,
            }
            for a, b, c, d, e in zip(
                sorted(list(libraries), key=lambda x: library_order.index(x.id)),
                self._get_library_full_counts(libraries, library_order),
                self._get_library_version_counts(libraries, library_order),
                self._get_top_contributors_for_library_version(library_order),
                self._count_new_contributors(libraries, library_order),
            )
        ]
        top_contributors = self._get_top_contributors_for_version()
        # total messages sent during this release (version)
        total_mailinglist_count = EmailData.objects.filter(version=version).aggregate(
            total=Sum("count")
        )["total"]
        return {
            "version": version,
            "mailinglist_counts": self._get_top_emaildata_release(version)[:10],
            "mailinglist_total": total_mailinglist_count,
            "commit_count": commit_count,
            "version_commit_count": version_commit_count,
            "top_contributors_release_overall": top_contributors,
            "library_data": library_data,
            "top_libraries_for_version": top_libraries_for_version,
            "library_count": Library.objects.all().count(),
        }
