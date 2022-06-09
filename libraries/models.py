from django.db import models


class Category(models.Model):
    """
    Library categories such as:
      - Math and Numerics
      - Algorithms
      - etc
    """

    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Library(models.Model):
    """
    Model to represent component Libraries of Boost
    """

    name = models.CharField(max_length=100, db_index=True)
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

    def __str__(self):
        return self.name
