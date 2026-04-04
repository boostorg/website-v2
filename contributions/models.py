from django.db import models
from django_extensions.db.models import TimeStampedModel


class ContributionType(models.TextChoices):
    PR_CREATE = "pr-create", "PR Created"
    PR_COMMENT = "pr-comment", "PR Commented"
    PR_REVIEW = "pr-review", "PR Reviewed"
    PR_APPROVE = "pr-approve", "PR Approved"
    PR_MERGE = "pr-merge", "PR Merged"
    PR_CLOSE = "pr-close", "PR Closed"
    ISSUE_CREATE = "issue-create", "Issue Created"
    ISSUE_REOPENED = "issue-reopened", "Issue Reopened"
    ISSUE_COMMENT = "issue-comment", "Issue Commented"
    ISSUE_CLOSE = "issue-close", "Issue Closed"


class Email(TimeStampedModel):
    """Contributor email addresses."""

    email = models.EmailField(max_length=255, unique=True, db_index=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.email

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.pk}): {self}>"


class Identity(TimeStampedModel):
    """Identity grouping multiple profiles belonging to the same contributor."""

    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    needs_review = models.BooleanField(
        default=False,
        help_text="Flag for AI-generated identities needing manual review",
    )

    class Meta:
        ordering = ["-created"]
        verbose_name_plural = "Identities"

    def __str__(self):
        return self.name or f"Identity {self.id}"

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.pk}): {self}>"


class Profile(TimeStampedModel):
    """Abstract base model for user profiles."""

    identity = models.ForeignKey(
        "Identity",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="%(class)s_profiles",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-created"]

    def __str__(self):
        return self.name or f"{self.__class__.__name__} {self.pk}"

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.pk}): {self}>"


class Contribution(TimeStampedModel):
    """Abstract base model for all contribution types.

    Provides common fields and behavior for contribution tracking:
    - date: When the contribution occurred
    - info: Unique identifier (commit hash, PR number, paper ID, etc.)
    - comment: Message, comment, or title
    - Automatic timestamps (created, modified) via TimeStampedModel

    Each subclass maintains its own profile and specific fields (like repo for Git/GitHub).
    """

    contributed_at = models.DateTimeField(
        null=True, blank=True, db_index=True, help_text="Date/time of the contribution"
    )
    info = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique identifier (commit hash, PR number, paper ID, etc.)",
    )
    comment = models.TextField(
        null=True, blank=True, help_text="Commit message, comment, or title"
    )

    class Meta:
        abstract = True
        ordering = ["-contributed_at"]

    def __str__(self):
        return f"{self.__class__.__name__} {self.pk}"

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.pk}): {self}>"


class GithubProfile(Profile):
    """GitHub user profile."""

    github_user_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="GitHub user ID",
    )

    class Meta:
        ordering = ["-created"]


class GitProfile(Profile):
    """Git user profile (for general Git commits)."""

    email = models.ForeignKey(
        "Email",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="git_profiles",
    )

    class Meta:
        ordering = ["-created"]


class Wg21Profile(Profile):
    """WG21 user profile."""

    class Meta:
        ordering = ["-created"]


class GitContribution(Contribution):
    """Git commits"""

    profile = models.ForeignKey(
        "GitProfile",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="git_contributions",
    )
    repo = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Repository name or path",
    )
    library = models.ForeignKey(
        "libraries.Library",
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-contributed_at"]
        unique_together = [("profile", "repo", "library", "info")]

    def __str__(self):
        return f"{self.profile} - {self.repo} ({self.info[:7]})"


class GithubContribution(Contribution):
    """GitHub contribution events. e.g. issues, PRs, etc."""

    profile = models.ForeignKey(
        "GithubProfile",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="github_contributions",
    )
    type = models.CharField(
        max_length=50,
        choices=ContributionType,
        null=True,
        blank=True,
        db_index=True,
        help_text="Type of GitHub contribution",
    )
    repo = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Repository name",
    )

    class Meta:
        ordering = ["-contributed_at"]
        unique_together = [("profile", "contributed_at", "info")]

    def __str__(self):
        return f"{self.profile} - {self.type} on {self.repo}"


class Wg21Contribution(Contribution):
    """WG21 paper contributions."""

    profile = models.ForeignKey(
        "Wg21Profile",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="wg21_contributions",
    )

    class Meta:
        ordering = ["-contributed_at"]

    def __str__(self):
        return f"{self.profile} - {self.info or 'Paper'}"

    @property
    def year(self):
        """Helper property to extract year from date."""
        return self.contributed_at.year if self.contributed_at else None

    @property
    def paper_id(self):
        """Alias for backward compatibility."""
        return self.info

    @property
    def title(self):
        """Alias for backward compatibility."""
        return self.comment


class GitRepoETag(TimeStampedModel):
    """Store ETags for GitHub repository commit fetching.

    Used to implement conditional requests that don't count against rate limits
    when no changes have occurred.
    """

    repo = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="GitHub repository name (e.g., 'beast', 'asio')",
    )
    etag = models.CharField(
        max_length=255, help_text="ETag value from GitHub API response"
    )

    class Meta:
        ordering = ["-modified"]

    def __str__(self):
        return f"{self.repo} - {self.etag}"
