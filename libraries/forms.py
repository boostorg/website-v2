from django.db.models import Count, OuterRef
from django.forms import Form, ModelChoiceField, ModelForm, ModelMultipleChoiceField

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
    libraries = ModelMultipleChoiceField(
        queryset=Library.objects.all().order_by("name")
    )

    def get_stats(self):
        version = self.cleaned_data["version"]
        libraries = self.cleaned_data["libraries"]

        commit_count = Commit.objects.count()
        version_commit_count = Commit.objects.filter(
            library_version__version=version
        ).count()

        library_full_counts = (
            libraries.annotate(commit_count=Count("library_version__commit"))
            .values("commit_count")
            .order_by("name")
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
        library_version_counts = (
            libraries.filter(
                library_version=LibraryVersion.objects.filter(
                    library=OuterRef("id"), version=version
                )[:1]
            )
            .annotate(commit_count=Count("library_version__commit"))
            .values("commit_count")
            .order_by("name")
        )

        top_contributors_release_overall = (
            CommitAuthor.objects.filter(commit__library_version__version=version)
            .annotate(commit_count=Count("commit"))
            .values("name", "avatar_url", "commit_count")
            .order_by("-commit_count")[:10]
        )
        top_contributors_release = []
        for library in libraries:
            top_contributors_release.append(
                CommitAuthor.objects.filter(
                    commit__library_version=LibraryVersion.objects.get(
                        version=version, library=library
                    )
                )
                .annotate(commit_count=Count("commit"))
                .values("name", "avatar_url", "commit_count")
                .order_by("-commit_count")[:10]
            )

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
        }
