from urllib.parse import urlparse

from django.db import models
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
    """

    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    github_url = models.URLField(max_length=500, blank=True, null=True)
    first_release = models.ForeignKey(
        "versions.Version",
        related_name="first_releases",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    cpp_standard_minimum = models.CharField(max_length=50, blank=True, null=True)

    active_development = models.BooleanField(default=True, db_index=True)
    last_github_update = models.DateTimeField(blank=True, null=True, db_index=True)

    categories = models.ManyToManyField(Category, related_name="libraries")

    authors = models.ManyToManyField("users.User", related_name="authors")
    maintainers = models.ManyToManyField("users.User", related_name="maintainers")

    closed_prs_per_month = models.IntegerField(blank=True, null=True)
    open_issues = models.IntegerField(blank=True, null=True)
    commits_per_release = models.IntegerField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Libraries"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    def github_properties(self):
        parts = urlparse(self.github_url)
        path = parts.path.split("/")

        owner = path[1]
        repo = path[2]

        return {
            "owner": owner,
            "repo": repo,
        }

    @property
    def github_owner(self):
        return self.github_properties()["owner"]

    @property
    def github_repo(self):
        return self.github_properties()["repo"]


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
