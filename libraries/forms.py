from django.db.models import Count, OuterRef
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
    version = ModelChoiceField(
        queryset=Version.objects.active()
        .exclude(name__in=["develop", "master", "head"])
        .order_by("-name")
    )
    library_1 = ModelChoiceField(
        queryset=Library.objects.all().order_by("name"),
        required=False,
        help_text="If none are selected, the top 5 for this release will be auto-selected.",
    )
    library_2 = ModelChoiceField(
        queryset=Library.objects.all().order_by("name"),
        required=False,
    )
    library_3 = ModelChoiceField(
        queryset=Library.objects.all().order_by("name"),
        required=False,
    )
    library_4 = ModelChoiceField(
        queryset=Library.objects.all().order_by("name"),
        required=False,
    )
    library_5 = ModelChoiceField(
        queryset=Library.objects.all().order_by("name"),
        required=False,
    )
    library_6 = ModelChoiceField(
        queryset=Library.objects.all().order_by("name"),
        required=False,
    )
    library_7 = ModelChoiceField(
        queryset=Library.objects.all().order_by("name"),
        required=False,
    )
    library_8 = ModelChoiceField(
        queryset=Library.objects.all().order_by("name"),
        required=False,
    )

    def get_stats(self):
        version = self.cleaned_data["version"]

        top_contributors_release_overall = (
            CommitAuthor.objects.filter(commit__library_version__version=version)
            .annotate(commit_count=Count("commit"))
            .values("name", "avatar_url", "commit_count")
            .order_by("-commit_count")[:10]
        )

        top_libraries_release = (
            Library.objects.filter(
                library_version=LibraryVersion.objects.filter(
                    library=OuterRef("id"), version=version
                )[:1],
            )
            .annotate(commit_count=Count("library_version__commit"))
            .order_by("-commit_count")[:5]
        )

        commit_count = Commit.objects.filter(
            library_version__version__name__lte=version.name
        ).count()
        version_commit_count = Commit.objects.filter(
            library_version__version=version
        ).count()

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
        if library_order:
            libraries = Library.objects.filter(id__in=library_order)
        else:
            library_order = [x.id for x in top_libraries_release]
            libraries = Library.objects.filter(
                id__in=[x.id for x in top_libraries_release]
            )

        library_count = Library.objects.all().count()

        library_full_counts = sorted(list(
            libraries.annotate(commit_count=Count("library_version__commit")).values(
                "commit_count", "id"
            )
        ), key=lambda x: library_order.index(x["id"]))

        library_version_counts = sorted(list(
            libraries.filter(
                library_version=LibraryVersion.objects.filter(
                    library=OuterRef("id"), version=version
                )[:1]
            )
            .annotate(commit_count=Count("library_version__commit"))
            .values("commit_count", "id")
        ), key=lambda x: library_order.index(x["id"]))

        top_contributors_release = []
        for library_id in library_order:
            top_contributors_release.append(
                CommitAuthor.objects.filter(
                    commit__library_version=LibraryVersion.objects.get(
                        version=version, library_id=library_id
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

        libraries = sorted(list(libraries), key=lambda x: library_order.index(x.id))
        library_data = [
            {
                "library": a,
                "full_count": b,
                "version_count": c,
                "top_contributors_release": d,
            }
            for a, b, c, d in zip(
                libraries,
                library_full_counts,
                library_version_counts,
                top_contributors_release,
            )
        ]

        return {
            "version": version,
            "commit_count": commit_count,
            "version_commit_count": version_commit_count,
            "top_contributors_release_overall": top_contributors_release_overall,
            "library_data": library_data,
            "top_libraries_release": top_libraries_release,
            "library_count": library_count,
        }
