from django.db import models
from django.utils.functional import cached_property
from django.utils.text import slugify

from .managers import VersionManager, VersionFileManager


class Version(models.Model):
    name = models.CharField(
        max_length=256, null=False, blank=False, help_text="Version name"
    )
    slug = models.SlugField(blank=True, null=True)
    release_date = models.DateField(auto_now=False, auto_now_add=False)
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
    data = models.JSONField(default=dict)

    objects = VersionManager()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.get_slug()
        return super(Version, self).save(*args, **kwargs)

    def get_slug(self):
        if self.slug:
            return self.slug
        name = self.name.replace(".", " ")
        return slugify(name)[:50]

    @cached_property
    def display_name(self):
        return self.name.replace("boost-", "")

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
    def documentation_url(self):
        """Return the URL path to documentation for this version of Boost.
        This maps to the appropriate directory in the S3 bucket. See the
        static content config file for the mapping from the site_path to the
        S3 path."""
        site_path = "/doc/libs/"
        slug = self.slug.replace("-", "_").replace(".", "_")
        return f"{site_path}{slug}/index.html"


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
    checksum = models.CharField(max_length=64, unique=True, default=None)
    url = models.URLField()
    display_name = models.CharField(max_length=256, blank=True, null=True)

    objects = VersionFileManager()
