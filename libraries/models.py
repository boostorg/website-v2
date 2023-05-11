from urllib.parse import urlparse

from django.db import models
from django.utils.functional import cached_property
from django.utils.text import slugify


class Category(models.Model):
    """
    Library categories such as:
      - Math and Numerics
      - Algorithms
      - etc
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super(Category, self).save(*args, **kwargs)


class Library(models.Model):
    """
    Model to represent component Libraries of Boost

    The Library model is the main model for Boost Libraries. Default values
    come from the .gitmodules file in the main Boost repo, and the libraries.json
    file in the meta/ directory of Boost library repos.

    Most libraries have a single Library object, but some libraries have multiple
    Library objects. For example, the Boost Math library has a Library object
    for multiple sub-libraries. Each of those libraries will be its own Library
    object, and will have the github_url to the main library repo.
    """

    name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="The name of the library as defined in libraries.json.",
    )
    key = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="The key of the library as defined in libraries.json.",
    )
    slug = models.SlugField(
        blank=True, null=True, help_text="The slug of the library, used in the URL."
    )
    description = models.TextField(
        blank=True, null=True, help_text="The description of the library."
    )
    github_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="The URL of the library's GitHub repository.",
    )
    first_release = models.ForeignKey(
        "versions.Version",
        related_name="first_releases",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    versions = models.ManyToManyField(
        "versions.Version", through="libraries.LibraryVersion", related_name="libraries"
    )
    cpp_standard_minimum = models.CharField(max_length=50, blank=True, null=True)

    active_development = models.BooleanField(default=True, db_index=True)
    last_github_update = models.DateTimeField(blank=True, null=True, db_index=True)

    categories = models.ManyToManyField(Category, related_name="libraries")

    authors = models.ManyToManyField("users.User", related_name="authors")

    closed_prs_per_month = models.IntegerField(blank=True, null=True)
    open_issues = models.IntegerField(blank=True, null=True)
    commits_per_release = models.IntegerField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Libraries"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Override the save method to confirm the slug is set (or set it)"""
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    def get_cpp_standard_minimum_display(self):
        """Returns the display name for the C++ standard, or the value if not found.

        Source of values is
        https://docs.cppalliance.org/user-guide/prev/library_metadata.html"""
        display_names = {
            "98": "C++98",
            "03": "C++03",
            "11": "C++11",
            "14": "C++14",
            "17": "C++17",
            "20": "C++20",
        }
        return display_names.get(self.cpp_standard_minimum, self.cpp_standard_minimum)

    def github_properties(self):
        """Returns the owner and repo name for the library"""
        parts = urlparse(self.github_url)
        path = parts.path.split("/")

        owner = path[1]
        repo = path[2]

        return {
            "owner": owner,
            "repo": repo,
        }

    @cached_property
    def github_owner(self):
        """Returns the name of the GitHub owner for the library"""
        return self.github_properties()["owner"]

    @cached_property
    def github_repo(self):
        """Returns the name of the GitHub repository for the library"""
        return self.github_properties()["repo"]

    @cached_property
    def github_issues_url(self):
        """
        Returns the URL to the GitHub issues page for the library

        Does not check if the URL is valid.
        """
        if not self.github_owner or not self.github_repo:
            raise ValueError("Invalid GitHub owner or repository")

        return f"https://github.com/{self.github_owner}/{self.github_repo}/issues"


class LibraryVersion(models.Model):
    version = models.ForeignKey(
        "versions.Version",
        related_name="library_version",
        on_delete=models.SET_NULL,
        null=True,
    )
    library = models.ForeignKey(
        "libraries.Library",
        related_name="library_version",
        on_delete=models.SET_NULL,
        null=True,
    )
    maintainers = models.ManyToManyField("users.User", related_name="maintainers")

    def __str__(self):
        return f"{self.library.name} ({self.version.name})"


class Issue(models.Model):
    """
    Model that tracks Library repository issues in Github
    """

    library = models.ForeignKey(
        Library, related_name="issues", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)
    number = models.IntegerField()
    github_id = models.CharField(max_length=100, db_index=True)
    is_open = models.BooleanField(default=False, db_index=True)
    closed = models.DateTimeField(blank=True, null=True, db_index=True)

    created = models.DateTimeField(db_index=True)
    modified = models.DateTimeField(db_index=True)

    data = models.JSONField(default=dict)

    def __str__(self):
        return f"({self.number}) - {self.title}"


class PullRequest(models.Model):
    """
    Model that tracks Pull Requests in Github for a Library
    """

    library = models.ForeignKey(
        Library, related_name="pull_requests", on_delete=models.CASCADE
    )

    title = models.CharField(max_length=255)
    number = models.IntegerField()
    github_id = models.CharField(max_length=100, db_index=True)
    is_open = models.BooleanField(default=False, db_index=True)
    closed = models.DateTimeField(blank=True, null=True, db_index=True)
    merged = models.DateTimeField(blank=True, null=True, db_index=True)

    created = models.DateTimeField(db_index=True)
    modified = models.DateTimeField(db_index=True)

    data = models.JSONField(default=dict)

    def __str__(self):
        return f"({self.number}) - {self.title}"
