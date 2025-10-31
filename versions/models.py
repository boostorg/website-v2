import re
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.text import slugify

from .converters import to_url
from .exceptions import BoostImportedDataException
from .managers import VersionManager, VersionFileManager
from .utils.model_validators import validate_version_name_format

User = get_user_model()


class Version(models.Model):
    name = models.CharField(
        max_length=256, null=False, blank=False, help_text="Version name"
    )
    slug = models.SlugField(blank=True, null=True)
    release_date = models.DateField(auto_now=False, auto_now_add=False, null=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(
        default=True,
        help_text="Control whether or not this version is available on the website",
    )
    github_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="The URL of the Boost version's GitHub repository.",
    )
    beta = models.BooleanField(
        default=False, help_text="Whether this is a beta release"
    )
    full_release = models.BooleanField(
        default=True,
        help_text="Whether this is a full release and not a "
        "beta release or a development version",
    )
    data = models.JSONField(default=dict)
    fully_imported = models.BooleanField(
        default=False,
        help_text="Whether this version has been fully imported and is ready for use.",
    )
    objects = VersionManager()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.get_slug()
        return super(Version, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("release-detail", args=[to_url(str(self.slug))])

    def get_slug(self):
        if self.slug:
            return self.slug
        name = self.name.replace(".", " ").replace("boost_", "")
        return slugify(name)[:50]

    def get_dependency_diffs(self, library=None):
        """Computes added, removed and unchanged dependencies.

        - Computed for all LibraryVersion models, between this Version and the
          previous Version.
        - Only boost-x.x.0 versions are considered, as given by
          Version.objects.minor_versions()

        If library is given, the query is constrained to only one library.

        """
        from libraries.models import LibraryVersion

        current_library_versions = (
            LibraryVersion.objects.filter(version=self)
            .select_related("library")
            .prefetch_related("dependencies")
        )
        previous_library_versions = (
            LibraryVersion.objects.filter(
                version__in=self.__class__.objects.minor_versions()
                .filter(version_array__lt=self.cleaned_version_parts_int)
                .order_by("-version_array")[:1],
            )
            .select_related("library")
            .prefetch_related("dependencies")
        )
        if library:
            current_library_versions = current_library_versions.filter(library=library)
            previous_library_versions = previous_library_versions.filter(
                library=library
            )
        diffs = {}
        dependencies_count = 0
        if previous_library_versions and current_library_versions:
            prev = {x.library.name: x for x in previous_library_versions}
            current = {x.library.name: x for x in current_library_versions}
            for key, current_lv in current.items():
                prev_lv = prev.get(key)
                if not prev_lv:
                    continue
                prev_dep_objects = prev_lv.dependencies.all()
                current_dep_objects = current_lv.dependencies.all()
                old_dependencies = {x.name for x in prev_dep_objects}
                current_dependencies = {x.name for x in current_dep_objects}
                dependencies_count += len(current_dependencies)
                diffs[key] = {
                    "library_id": current_lv.library_id,
                    "added": list(current_dependencies - old_dependencies),
                    "removed": list(old_dependencies - current_dependencies),
                    "previous_dependencies": sorted(
                        prev_dep_objects, key=lambda x: x.name.lower()
                    ),
                    "current_dependencies": sorted(
                        current_dep_objects, key=lambda x: x.name.lower()
                    ),
                    "both": sorted(
                        list(set(prev_dep_objects) | set(current_dep_objects)),
                        key=lambda x: x.name.lower(),
                    ),
                }
        if dependencies_count == 0:
            msg = "No dependencies found for libraries in this version."
            raise BoostImportedDataException(msg)
        return diffs

    @cached_property
    def display_name(self):
        return self.name.replace("boost-", "")

    @cached_property
    def non_beta_slug(self):
        """Return the slug without any beta suffix.

        Example:
        - "boost-1-75-0-beta1" --> "boost-1-75-0"
        - "develop" --> "develop"
        """
        return self.slug.split("-beta")[0]

    @cached_property
    def boost_url_slug(self):
        """Return the slug for the version that is used in the Boost URL to get to
        the existing Boost docs. The GitHub slug and the Boost slug don't match, so
        this method converts the GitHub slug to the Boost slug.

        Example:
        - "boost-1.75.0" --> "boost_1_75_0"
        - "develop" --> "develop"
        """
        return self.slug.replace("-", "_").replace(".", "_")

    @cached_property
    def stripped_boost_url_slug(self):
        """Return the only the numbers and underscores for this version

        Example:
        - "boost-1.75.0" --> "1_75_0"
        - "develop" --> "develop"
        """
        return self.slug.replace("-", "_").replace(".", "_").replace("boost_", "")

    @cached_property
    def boost_release_notes_url(self):
        """Return the URL path to the release notes for this version of Boost on
        the existing Boost.org website.
        """
        slug = self.boost_url_slug.replace("boost", "version")
        return f"https://www.boost.org/users/history/{slug}.html"

    @cached_property
    def documentation_url(self):
        """Return the URL path to documentation for this version of Boost.
        This maps to the appropriate directory in the S3 bucket. See the
        static content config file for the mapping from the site_path to the
        S3 path."""
        site_path = "/doc/libs/"
        slug = self.slug.replace("-", "_").replace(".", "_").replace("boost_", "")
        return f"{site_path}{slug}"

    @cached_property
    def cleaned_version_parts(self):
        """Returns only the release data from the name. Also omits "boost", "beta"
        information from the name."""
        if not self.name:
            return

        cleaned = re.sub(r"^[^0-9]*", "", self.name).split("beta")[0]
        return [part for part in cleaned.split(".") if part]

    @cached_property
    def cleaned_version_parts_int(self):
        """Returns the release data as a list of integers."""
        if not self.cleaned_version_parts:
            return []
        return [int(x) if x.isdigit() else 0 for x in self.cleaned_version_parts]

    @cached_property
    def release_notes_cache_key(self):
        """Returns the cache key used to access the release notes in the
        RenderedContent model."""
        version = "-".join(self.cleaned_version_parts)
        return f"release_notes_boost-{version}"


class VersionFile(models.Model):
    Unix = "Unix"
    Windows = "Windows"
    OPERATING_SYSTEM_CHOICES = (
        (Unix, "Unix"),
        (Windows, "Windows"),
    )

    version = models.ForeignKey(
        Version, related_name="downloads", on_delete=models.CASCADE
    )
    operating_system = models.CharField(
        choices=OPERATING_SYSTEM_CHOICES, max_length=15, default=Unix
    )
    checksum = models.CharField(max_length=64, default=None)
    url = models.URLField()
    display_name = models.CharField(max_length=256, blank=True, null=True)

    objects = VersionFileManager()

    class Meta:
        unique_together = [["version", "checksum"]]


# TODO: should this go in a new `reviews` app?
class Review(models.Model):
    submission = models.CharField()
    # TODO: drop raw fields once users have been linked
    submitter_raw = models.CharField()
    review_manager_raw = models.CharField(blank=True, default="Needed!")
    submitters = models.ManyToManyField(
        "libraries.CommitAuthor", related_name="submitted_reviews"
    )
    review_manager = models.ForeignKey(
        "libraries.CommitAuthor",
        related_name="managed_reviews",
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )
    review_dates = models.CharField()
    github_link = models.URLField(blank=True, default="")
    documentation_link = models.URLField(blank=True, default="")

    def __str__(self) -> str:
        return self.submission

    def __repr__(self) -> str:
        return f"<Review: {self} ({self.pk})>"


class ReviewResult(models.Model):
    review = models.ForeignKey(Review, related_name="results", on_delete=models.CASCADE)
    short_description = models.CharField()
    is_most_recent = models.BooleanField(default=True)
    announcement_link = models.URLField(blank=True, default="")

    class Meta:
        verbose_name_plural = "review results"

    def __str__(self) -> str:
        return self.short_description

    def __repr__(self) -> str:
        return f"<ReviewResult: {self} ({self.pk})>"

    def save(self, *args, **kwargs):
        """Ensure only one status is most recent per review."""
        if self.is_most_recent:
            sibling_results = ReviewResult.objects.filter(review=self.review).exclude(
                pk=self.pk
            )
            sibling_results.update(is_most_recent=False)
        super().save(*args, **kwargs)


class ReportConfiguration(models.Model):
    """
    Configuration for release reports. Used so these can be set in advance of a version
     being generated and then used by that version's release report.
    """

    version = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        help_text="The version name for this report configuration. e.g. boost-1.75.0",
        unique=True,
        validators=[validate_version_name_format],
    )
    release_report_cover_image = models.ImageField(
        null=True,
        blank=True,
        upload_to="release_report_cover/",
    )
    sponsor_message = models.TextField(
        default="",
        blank=True,
        help_text='Message to show in release reports on the "Fiscal Sponsorship Committee" page.',  # noqa: E501
    )
    financial_committee_members = models.ManyToManyField(
        User,
        blank=True,
        help_text="Financial Committee members who are responsible for this release.",
    )

    @cached_property
    def display_name(self):
        return self.version.replace("boost-", "")

    def get_slug(self):
        # this output should always match the Version slug format
        name = self.version.replace(".", " ").replace("boost_", "")
        return slugify(name)[:50]

    def __str__(self):
        return self.version


def docs_path_to_boost_name(content_path):
    """
    Convert a documentation content path to the Boost version name.
    e.g. "1_79_0/doc/html/accumulators.html" to "boost-1.79.0"
    """
    if content_path.startswith("develop") or content_path.startswith("master"):
        result = content_path.split("/")[0]
    else:
        result = re.sub(r"^([_0-9]+)(/\S+)", r"boost-\1", content_path)
    return result.replace("_", ".")
