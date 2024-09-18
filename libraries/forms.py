from django.db.models import F, Q, Count, OuterRef
from django.forms import Form, ModelChoiceField, ModelForm

from versions.models import Version
from .models import Commit, CommitAuthor, Library, LibraryVersion


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


class CreateReportForm(Form):
    library_queryset = Library.objects.all().order_by("name")
    version = ModelChoiceField(
        queryset=Version.objects.active()
        .exclude(name__in=["develop", "master", "head"])
        .order_by("-name")
    )
    library_1 = ModelChoiceField(
        queryset=library_queryset,
        required=False,
        help_text="If none are selected, the top 5 for this release will be auto-selected.",
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

    def _get_top_contributors_for_version(self):
        return (
            CommitAuthor.objects.filter(
                commit__library_version__version=self.cleaned_data["version"]
            )
            .annotate(commit_count=Count("commit"))
            .values("name", "avatar_url", "commit_count")
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

    def _get_library_order(self, top_libraries_release):
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
            library_order = [x.id for x in top_libraries_release]
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
        lt_subquery = LibraryVersion.objects.filter(
            version__name__lt=version.name, library=OuterRef("id")
        ).values("id")
        lte_subquery = LibraryVersion.objects.filter(
            version__name__lte=version.name, library=OuterRef("id")
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
                ).annotate(
                    count=F("authors_through_release_count")
                    - F("authors_before_release_count")
                ).values("id", "count")
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
                    "commit_count",
                    "commit__library_version__library_id",
                )
                .order_by("-commit_count")[:10]
            )
        return top_contributors_release

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

        return {
            "version": version,
            "commit_count": commit_count,
            "version_commit_count": version_commit_count,
            "top_contributors_release_overall": self._get_top_contributors_for_version(),
            "library_data": library_data,
            "top_libraries_for_version": top_libraries_for_version,
            "library_count": Library.objects.all().count(),
        }
