import logging
import os
import re
import uuid
from datetime import timedelta
from typing import Self
from urllib.parse import urlencode, urlparse

from django.core.cache import caches
from django.db import models, transaction
from django.db.models import Q, Sum
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.db.models.functions import Upper

from config import settings
from core.custom_model_fields import NullableFileField
from core.markdown import process_md
from core.models import RenderedContent
from core.asciidoc import convert_adoc_to_html
from core.validators import image_validator, max_file_size_validator
from libraries.bots import is_bot_name
from libraries.managers import (
    CommitAuthorManager,
    HumanCommitAuthorManager,
    IssueManager,
)
from mailing_list.models import EmailData
from versions.models import ReportConfiguration
from .constants import (
    COMMIT_EMAIL_CLAIM_MAX_AGE,
    LATEST_RELEASE_URL_PATH_STR,
    LIBRARY_GITHUB_URL_OVERRIDES,
)

from .utils import (
    generate_random_string,
    write_content_to_tempfile,
    generate_release_report_filename,
)

logger = logging.getLogger(__name__)


class Category(models.Model):
    """
    Library categories such as:
      - Math and Numerics
      - Algorithms
      - etc
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True, null=True)
    short_description = models.TextField(
        blank=True,
        default="",
        help_text="Short marketing copy shown on the Learn page category carousel.",
    )

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super(Category, self).save(*args, **kwargs)

    def get_filter_url(self, version_slug=LATEST_RELEASE_URL_PATH_STR):
        """URL to the libraries list filtered by this category.

        e.g. /libraries/1.90.0/list/?category=asynchronous — the query-param
        form the list/grid category filter reads. Single source of truth for
        category-tag links; returns "#" when the category has no slug.
        """
        if not self.slug:
            return "#"
        base = reverse(
            "libraries-list",
            kwargs={"version_slug": version_slug, "library_view_str": "list"},
        )
        return f"{base}?{urlencode({'category': self.slug})}"


class CommitAuthor(models.Model):
    name = models.CharField(max_length=100)
    avatar_url = models.URLField(null=True, max_length=100)
    github_profile_url = models.URLField(null=True, max_length=100)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    is_bot = models.BooleanField(
        default=False,
        help_text="Exclude from contributor lists. Auto-set on import for "
        "known bot names; editable here for anything detected later.",
    )

    objects = CommitAuthorManager()
    humans = HumanCommitAuthorManager()

    def save(self, *args, **kwargs):
        # On create, seed is_bot from the name so any creation path (import,
        # shell, admin) gets the same detection as the main commit importer.
        # Skipped on update to preserve admin overrides.
        if self._state.adding and not self.is_bot and is_bot_name(self.name):
            self.is_bot = True
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        if (
            self.user
            and self.user.is_commit_author_name_overridden
            and self.user.display_name
        ):
            return self.user.display_name
        return self.name

    def __str__(self):
        return self.name

    def to_v3_profile_dict(self, role=None):
        """Dict shape consumed by `v3/includes/_user_profile.html`.

        Mirrors `User.to_v3_profile_dict` so the same template can render
        either a registered user or a git-only contributor.

        A contributor who has claimed a Boost account links to that profile;
        one who has not falls back to their GitHub page, which is all this site
        knows about them. A deactivated account falls back the same way, since
        its profile 404s.

        Badges are awarded to the account, not to the git identity, so a
        contributor with no linked account has none to show - it is the same
        empty case as a member who has earned nothing (issue #2708).
        """
        user_profile_url = self.user.profile_url if self.user else None
        return {
            "name": self.display_name,
            "profile_url": user_profile_url or self.github_profile_url,
            "role": role,
            "avatar_url": self.avatar_url or "",
            "tenure_stamp": self.user.tenure_stamp if self.user else None,
            "boost_day_stamp": self.user.boost_day_stamp if self.user else None,
            "badge": self.user.badge if self.user else None,
            "badge_label": self.user.badge_label if self.user else "",
            "bio": None,
        }

    @transaction.atomic
    def merge_author(self, other: Self):
        """Update references to `other` to point to `self`.

        Deletes `other` after updating references.
        """
        if self.pk == other.pk:
            return
        other.commitauthoremail_set.update(author=self)
        other.commit_set.update(author=self)
        self.merge_author_email_data(other)
        if not self.avatar_url:
            self.avatar_url = other.avatar_url
        if not self.github_profile_url:
            self.github_profile_url = other.github_profile_url
        self.save(update_fields=["avatar_url", "github_profile_url", "user_id"])
        other.delete()

    @transaction.atomic
    def merge_author_email_data(self, other: Self):
        """Merge EmailData for the 2 authors.

        - Update or create EmailData with author=self with the total counts for
        both `self` and `other` authors for each version.
        - Delete all EmailData objects for the `other` author.

        """
        count_totals = (
            EmailData.objects.filter(author__in=[self, other])
            .values("version_id")
            .annotate(total_count=Sum("count"))
        )

        for item in count_totals:
            EmailData.objects.update_or_create(
                author=self,
                version_id=item["version_id"],
                defaults={"count": item["total_count"]},
            )
        EmailData.objects.filter(author=other).delete()


class CommitAuthorEmail(models.Model):
    author = models.ForeignKey(CommitAuthor, on_delete=models.CASCADE)
    email = models.CharField(unique=True)
    claim_hash = models.UUIDField(null=True, blank=True)
    claim_hash_expiration = models.DateTimeField(default=timezone.now)
    claim_verified = models.BooleanField(default=False)
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commit_email_claims",
        help_text="Who asked to claim this email. Public attribution "
        "(author.user) is only bound at verification.",
    )

    @classmethod
    def claimed_by_user(cls, user):
        """Emails the user actually claimed: verified ones, or pending ones
        with an open, unexpired ask, verified first. Expired asks are not
        cleared anywhere - they are simply never shown, their token is dead,
        and the next ask (by anyone) overwrites the claim fields. A bound
        author's other imported emails are not the user's business.
        """
        return (
            cls.objects.filter(claimed_by=user)
            .filter(
                Q(claim_verified=True)
                | Q(
                    claim_hash__isnull=False,
                    claim_hash_expiration__gt=timezone.now(),
                )
            )
            .order_by("-claim_verified", "email")
        )

    def is_verification_email_expired(self):
        return timezone.now() > self.claim_hash_expiration

    def trigger_verification_email(self, request):
        self.author.user = request.user
        self.author.save(update_fields=["user"])
        # the one delta from the pre-v3 flow: record the claimant so claims
        # made while the v3 flag is off still show in the v3 card once it
        # flips on
        self.claimed_by = request.user
        self.claim_hash = uuid.uuid4()
        self.claim_hash_expiration = timezone.now() + timedelta(days=1)
        self.save()

        url = request.build_absolute_uri(
            reverse(
                "commit-author-email-verify",
                kwargs={"token": self.claim_hash},
            )
        )
        # here to avoid circular import
        from .tasks import send_commit_author_email_verify_mail

        send_commit_author_email_verify_mail.delay(self.email, url)

        return CommitAuthorEmail.objects.filter(author__user=self.author.user)

    def ask_to_claim(self, request):
        """Ask to claim this email for request.user - the v3 flow. The legacy
        flow is trigger_verification_email above, preserved untouched.

        Side-effect-free beyond this row: records the claimant and a fresh
        token and emails the address. author.user - the field driving public
        attribution - is only bound once the inbox owner confirms
        (see verify_claim).

        Returns None without side effects if the row is no longer claimable
        by request.user - the form validated an unlocked row, so a concurrent
        request may have verified it or opened a competing claim since.
        """
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            claimed_by_other = (
                locked.claimed_by_id is not None
                and locked.claimed_by_id != request.user.pk
                and locked.claim_hash is not None
                and locked.claim_hash_expiration > timezone.now()
            )
            if locked.claim_verified or claimed_by_other:
                return None

            self.claimed_by = request.user
            self.claim_hash = uuid.uuid4()
            self.claim_hash_expiration = timezone.now() + timedelta(
                seconds=COMMIT_EMAIL_CLAIM_MAX_AGE
            )
            # self predates the lock; a full-row save would clobber
            # concurrent writes to unrelated fields with the stale snapshot
            self.save(
                update_fields=["claimed_by", "claim_hash", "claim_hash_expiration"]
            )

        url = request.build_absolute_uri(
            reverse(
                "commit-author-email-verify",
                kwargs={"token": self.claim_hash},
            )
        )
        # here to avoid circular import
        from .tasks import send_commit_author_email_verify_mail

        # may be blank - the email falls back to an anonymous variant rather
        # than leaking the claimant's account email
        send_commit_author_email_verify_mail.delay(
            self.email,
            url,
            request.user.display_name,
            v3=True,
        )

        return CommitAuthorEmail.objects.filter(claimed_by=request.user)

    def accept_proven_claim(self, user):
        """Complete a claim with no verification email, for an address `user`
        has already proven control of elsewhere (see
        libraries.utils.address_already_proven_by).

        Sending a token to an address the account has already confirmed asks
        the user to prove the same thing twice, so this binds the claim
        outright. The guards mirror ask_to_claim: a row someone else has
        verified, or holds an open ask on, is still refused - proving your own
        inbox does not settle a dispute over someone else's.

        Returns the same queryset as ask_to_claim on success, or None when the
        row is no longer claimable by `user`.
        """
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            claimed_by_other = (
                locked.claimed_by_id is not None
                and locked.claimed_by_id != user.pk
                and locked.claim_hash is not None
                and locked.claim_hash_expiration > timezone.now()
            )
            if locked.claim_verified or claimed_by_other:
                return None

            # claim_hash stays null: there is no token to redeem, and
            # verify_claim below is what marks the row verified
            self.claimed_by = user
            self.save(update_fields=["claimed_by"])

        self.verify_claim()
        return CommitAuthorEmail.objects.filter(claimed_by=user)

    def verify_claim(self):
        """Complete a claim: mark this row verified and bind public
        attribution (author.user) to the claimant.

        A verified claim outranks the email/github matching heuristics that
        also set author.user (see tasks.update_commit_author_user), but it
        never steals an author on which a different user holds another
        verified claim - in that conflict the row is verified without
        rebinding and the conflict is logged for admins.

        Returns True when attribution was bound to the claimant, False
        when a conflicting verified sibling claim left author.user alone.
        """
        with transaction.atomic():
            # locking the author serializes sibling verifications, so two
            # can't both pass the conflict check before either commits
            author = CommitAuthor.objects.select_for_update().get(pk=self.author_id)
            self.claim_verified = True
            self.claim_hash_expiration = timezone.now()
            self.save(update_fields=["claim_verified", "claim_hash_expiration"])

            conflicting_claim = (
                author.commitauthoremail_set.exclude(pk=self.pk)
                .filter(claim_verified=True, claimed_by__isnull=False)
                .exclude(claimed_by=self.claimed_by)
                .exists()
            )
            if conflicting_claim:
                logger.warning(
                    "Verified commit email claim %s (user %s) conflicts with a "
                    "verified sibling claim on author %s; author.user left as %s",
                    self.pk,
                    self.claimed_by_id,
                    self.author_id,
                    author.user_id,
                )
                return False
            author.user = self.claimed_by
            author.save(update_fields=["user"])
            return True

    def withdraw_claim(self):
        """Undo a pending claim without touching the imported email record.

        The commit importer owns CommitAuthorEmail rows, so withdrawing an
        unverified claim must never delete one; it only clears the claim
        fields on this row. Unbinding author.user remains solely as a
        fallback for legacy rows claimed before the claimed_by field
        existed, which bound the author at ask time.
        """
        with transaction.atomic():
            claimant = self.claimed_by
            self.claimed_by = None
            self.claim_hash = None
            self.claim_hash_expiration = timezone.now()
            self.save(
                update_fields=["claimed_by", "claim_hash", "claim_hash_expiration"]
            )

            if claimant is None:
                return
            # same author lock as verify_claim, so the sibling check below
            # can't race a sibling verification into a stale unbind
            author = CommitAuthor.objects.select_for_update().get(pk=self.author_id)
            if author.user != claimant:
                return
            # only the claimant's own active claims justify keeping the
            # binding: expired tokens are never cleared (so they must not
            # count forever), and other users' asks never bound this author
            # to this claimant
            author_still_bound = (
                author.commitauthoremail_set.exclude(pk=self.pk)
                .filter(
                    Q(claim_verified=True, claimed_by=claimant)
                    | Q(
                        claim_verified=False,
                        claimed_by=claimant,
                        claim_hash__isnull=False,
                        claim_hash_expiration__gt=timezone.now(),
                    )
                )
                .exists()
            )
            if not author_still_bound:
                author.user = None
                author.save(update_fields=["user"])

    def __str__(self):
        return f"{self.author.name}: {self.email}"


class Commit(models.Model):
    author = models.ForeignKey(CommitAuthor, on_delete=models.CASCADE)
    library_version = models.ForeignKey("LibraryVersion", on_delete=models.CASCADE)
    sha = models.CharField(max_length=40)
    message = models.TextField(default="")
    committed_at = models.DateTimeField(db_index=True)
    is_merge = models.BooleanField(default=False)
    # A count rather than a flag, so weighting a commit by how much it documented
    # stays possible without another import. Zero for merges, which change no
    # files of their own.
    docs_files_changed = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sha", "library_version"],
                name="%(app_label)s_%(class)s_sha_library_version_unique",
            )
        ]

    def __str__(self):
        return self.sha


class Tier(models.IntegerChoices):
    FLAGSHIP = 10, "Flagship"
    CORE = 20, "Core"
    DEPRECATED = 30, "Deprecated"
    LEGACY = 40, "Legacy"


# Tiers eligible to be featured on the V3 homepage (spotlight + highlight carousel).
FEATURED_LIBRARY_TIERS = [Tier.FLAGSHIP, Tier.CORE]


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
    )  # holds the most recent version's description
    graphic = NullableFileField(
        upload_to="library_graphics",
        blank=True,
        null=True,
        default=None,
        validators=[image_validator, max_file_size_validator],
        verbose_name="Library Graphic",
    )
    is_good = models.BooleanField(
        default=False,
        verbose_name="Good Library",
        help_text="Is this library considered 'good' by the Boost community?",
    )
    github_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="The URL of the library's GitHub repository.",
    )
    slack_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text=(
            "URL of the dedicated Slack channel for this library. "
            "Falls back to the general Boost Slack when blank."
        ),
    )
    versions = models.ManyToManyField(
        "versions.Version", through="libraries.LibraryVersion", related_name="libraries"
    )
    cpp_standard_minimum = models.CharField(
        max_length=50, blank=True, null=True
    )  # deprecated for LibraryVersion.cpp_standard_minimum
    categories = models.ManyToManyField(Category, related_name="libraries")

    authors = models.ManyToManyField("users.User", related_name="authors")
    featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Should this library be featured on the home page?",
    )
    data = models.JSONField(
        default=dict, help_text="Contains the libraries.json for this library"
    )
    tier = models.IntegerField(
        choices=Tier,
        blank=True,
        null=True,
        help_text="The tier classification for this library",
    )

    class Meta:
        verbose_name_plural = "Libraries"
        constraints = [
            models.UniqueConstraint(Upper("slug"), name="slug_unique_case_insensitive")
        ]

    @cached_property
    def display_name(self):
        """Returns the display name for the library."""
        return "Boost." + self.display_name_short

    @cached_property
    def display_name_short(self):
        """Returns the short display name for the library."""

        # Custom method to capitalize words, taking care of special cases
        def custom_capitalize(word):
            # Only capitalize if the word is not already in CamelCase
            if not re.match(r"[A-Z][a-z]+[A-Z][A-Za-z]*", word):
                return "".join(part.capitalize() for part in re.split(r"(/)", word))
            return word

        # Split the name into segments to handle parts inside parentheses separately
        segments = re.split(r"(\([^\)]+\))", self.name)
        processed_segments = []

        for segment in segments:
            # Check if the segment is within parentheses
            if segment.startswith("(") and segment.endswith(")"):
                # Process the content within parentheses without the surrounding ()
                inner_content = segment[1:-1]
                processed_segments.append(f"({custom_capitalize(inner_content)})")
            else:
                # Split on whitespace, hyphens, underscores for regular segments
                words = re.split(r"[\s\-_]+", segment)
                capitalized_words = [custom_capitalize(word) for word in words]
                processed_segments.append("".join(capitalized_words))

        return "".join(processed_segments)

    @cached_property
    def group(self):
        if self.graphic:
            return "great"
        elif self.is_good:
            return "good"
        else:
            return "standard"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Override the save method to confirm the slug is set (or set it)

        We need the slug to be unique, but we want to intelligently make that happen,
        because there are libraries (like Container Hash) that are more easily managed
        as two records due to changes in the data between versions.
        """
        # Generate slug based on name
        if not self.slug:
            # Base the slug name off of the key from the gitmodules file.
            slug = slugify(self.key)

            # If there is a library with that slug, try a slug based on the key from the
            # gitmodules file
            if Library.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = slugify(self.key)

            # If that slug already exists, append a random string to the slug
            if Library.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                random_str = generate_random_string()
                slug = f"{slug}-{random_str}"

            self.slug = slug
        return super().save(*args, **kwargs)

    def get_description(self, client, tag="develop"):
        """Get description from the appropriate file on GitHub.

        For more recent versions, that will be `/doc/library-details.adoc`.
        For older versions, or libraries that have not adopted the adoc file,
        that will be `/README.md`.
        """
        content = None
        # File paths/names where description data might be stored.
        files = ["doc/library-detail.adoc", "README.md"]

        # Try to get the content from the cache first
        static_content_cache = caches["static_content"]
        cache_key = f"library_description_{self.github_repo}_{tag}"
        cached_result = static_content_cache.get(cache_key)
        if cached_result:
            return cached_result

        # Now try to get the content from the database
        try:
            content_obj = RenderedContent.objects.get(cache_key=cache_key)
            # TODO: if master or develop, fire a task to update the content
            return content_obj.content_html
        except RenderedContent.DoesNotExist:
            pass

        # It's not in a cache -- now try to get the content of each file in turn
        for file_path in files:
            content = client.get_file_content(
                repo_slug=self.github_repo, tag=tag, file_path=file_path
            )
            if content:
                # There is content, so process it
                if file_path.endswith(".adoc"):
                    body_content = convert_adoc_to_html(content.decode("utf-8"))
                else:
                    temp_file = write_content_to_tempfile(content)
                    _, body_content = process_md(temp_file.name)
                static_content_cache.set(cache_key, body_content)
                RenderedContent.objects.update_or_create(
                    cache_key=cache_key,
                    content_html=body_content,
                    content_type="text/html",
                )
                return body_content

        # If no content was found for any of the files
        return None

    def github_properties(self):
        """Returns the owner and repo name for the library"""
        if not self.github_url:
            return {}

        parts = urlparse(self.github_url)
        path = parts.path.split("/")

        owner = path[1]
        repo = path[2]

        return {
            "owner": owner,
            "repo": repo,
        }

    @cached_property
    def first_boost_version(self):
        """Returns the first Boost version that included this library"""
        first = (
            self.library_version.select_related("version")
            .order_by("version__release_date", "version__name")
            .first()
        )
        return first.version if first else None

    @cached_property
    def github_owner(self):
        """Returns the name of the GitHub owner for the library"""
        return self.github_properties().get("owner")

    @cached_property
    def github_repo(self):
        """Returns the name of the GitHub repository for the library"""
        return self.github_properties().get("repo")

    @cached_property
    def github_issues_url(self):
        """
        Returns the URL to the GitHub issues page for the library

        Does not check if the URL is valid.
        """
        if not self.github_owner or not self.github_repo:
            raise ValueError("Invalid GitHub owner or repository")

        return LIBRARY_GITHUB_URL_OVERRIDES.get(
            self.slug,
            f"https://github.com/{self.github_owner}/{self.github_repo}/issues",
        )

    @cached_property
    def category_tags(self):
        return [
            {
                "label": x.name,
                "slug": x.slug,
                "variant": "neutral",
            }
            for x in self.categories.all()
        ]


class LibraryVersion(models.Model):
    # Source: https://docs.cppalliance.org/contributor-guide/requirements/library-metadata.html
    CPP_STANDARD_DISPLAY_NAMES = {
        "98": "C++98",
        "03": "C++03",
        "11": "C++11",
        "14": "C++14",
        "17": "C++17",
        "20": "C++20",
        "23": "C++23",
    }

    version = models.ForeignKey(
        "versions.Version",
        related_name="library_version",
        on_delete=models.CASCADE,
    )
    library = models.ForeignKey(
        "libraries.Library",
        related_name="library_version",
        on_delete=models.CASCADE,
    )
    maintainers = models.ManyToManyField("users.User", related_name="maintainers")
    authors = models.ManyToManyField(
        "users.User", related_name="author_libraryversions"
    )
    missing_docs = models.BooleanField(
        default=False,
        help_text="If true, then there are not docs for this version of this library.",
    )
    documentation_url = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="The path to the docs for this library version.",
    )
    description = models.TextField(
        blank=True, null=True, help_text="The description of the library."
    )
    data = models.JSONField(
        default=dict, help_text="Contains the libraries.json for this library-version"
    )
    website_adoc_source = models.TextField(
        null=True,
        blank=True,
        help_text=(
            "Raw meta/website.adoc for this version (the source of truth). "
            "Editing this and saving re-derives website_adoc."
        ),
    )
    website_adoc = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Parsed content of the library's optional meta/website.adoc "
            "(About, Playground, Designed for, Links, Install, Benchmarks, "
            "Freeform), derived from website_adoc_source. Null when the repo "
            "has no website.adoc for this version."
        ),
    )
    # stats from git stored between x.x.0 versions
    insertions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    files_changed = models.IntegerField(default=0)
    cpp_standard_minimum = models.CharField(max_length=50, blank=True, null=True)
    cpp_standard_maximum = models.CharField(max_length=50, blank=True, null=True)
    cpp20_module_support = models.BooleanField(default=False)
    dependencies = models.ManyToManyField(
        "libraries.Library",
        symmetrical=False,
        related_name="dependents",
        blank=True,
    )

    def __str__(self):
        return f"{self.library.name} ({self.version.name})"

    @cached_property
    def library_repo_url_for_version(self):
        """Returns the URL to the GitHub repository for the library at this specicfic
        version.
        """
        if not self.library or not self.version or not self.library.github_url:
            raise ValueError("Invalid data for library version")

        return f"{self.library.github_url}/tree/{self.version.name}"

    @cached_property
    def library_detail_url_for_version(self):
        return reverse(
            "library-detail",
            kwargs={
                "version_slug": self.version.slug,
                "library_slug": self.library.slug,
            },
        )

    @cached_property
    def author_details(self):
        author = self.authors.first()
        return {
            "name": author.display_name if author else "Unknown",
            "role": "Author",
            "profile_url": author.profile_url if author else None,
            "avatar_url": author.get_avatar_url() if author else "",
            # `badge_url` used to sit here, pointing at a fixed first-place PNG.
            # Nothing read it: `_user_profile.html` takes `badge` and
            # `badge_label`, so the card showed the tenure star and no badge.
            "badge": author.badge if author else None,
            "badge_label": author.badge_label if author else "",
            **(author.profile_stamps if author else {}),
        }

    def get_cpp_standard_minimum_display(self):
        """Returns the display name for the minimum C++ standard, or the value if not found."""
        return self.CPP_STANDARD_DISPLAY_NAMES.get(
            self.cpp_standard_minimum, self.cpp_standard_minimum
        )

    def get_cpp_standard_maximum_display(self):
        """Returns the display name for the maximum C++ standard, or the value if not found."""
        return self.CPP_STANDARD_DISPLAY_NAMES.get(
            self.cpp_standard_maximum, self.cpp_standard_maximum
        )


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

    objects = IssueManager()

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


class WordcloudMergeWord(models.Model):
    from_word = models.CharField(max_length=255)
    to_word = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.from_word}->{self.to_word}"


class ReleaseReport(models.Model):
    upload_dir = "release-reports/"
    file = models.FileField(upload_to=upload_dir, blank=True, null=True)
    report_configuration = models.ForeignKey(
        ReportConfiguration, on_delete=models.CASCADE
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    locked = models.BooleanField(
        default=False,
        help_text="Can't be overwritten during release report publish. Blocks task-based publishing.",
    )

    def __str__(self):
        return f"{self.file.name.replace(self.upload_dir, "")}"

    def rename_file_to(self, filename: str, allow_overwrite: bool = False):
        """Rename the file to use the version slug from report_configuration."""
        from django.core.files.storage import default_storage

        current_name = self.file.name
        final_filename = f"{self._meta.get_field("file").upload_to}{filename}"
        if current_name == final_filename:
            return

        if default_storage.exists(final_filename):
            if not allow_overwrite:
                raise ValueError(f"{final_filename} already exists")
            default_storage.delete(final_filename)

        with default_storage.open(current_name, "rb") as source:
            default_storage.save(final_filename, source)
        # delete the old file and update the reference
        default_storage.delete(current_name)
        self.file.name = final_filename

    def get_media_file(self):
        return os.sep.join(
            [
                settings.MEDIA_URL.rstrip("/"),
                self.file.name,
            ]
        )

    @staticmethod
    def latest_published_locked(
        report_configuration: ReportConfiguration,
        release_report_exclusion=None,
    ) -> bool:
        release_reports_qs = ReleaseReport.objects.filter(
            report_configuration__version=report_configuration.version,
            published=True,
        )
        if release_report_exclusion:
            release_reports_qs = release_reports_qs.exclude(
                pk=release_report_exclusion.id
            )
        if release_reports_qs:
            return release_reports_qs.first().locked
        return False

    def unpublish_previous_reports(self):
        for r in ReleaseReport.objects.filter(
            report_configuration__version=self.report_configuration.version,
            published=True,
        ).exclude(pk=self.id):
            r.published = False
            r.save()

    def save(self, allow_published_overwrite=False, *args, **kwargs):
        """
        Args:
            allow_published_overwrite (bool): If True, allows overwriting of published
                reports (locked checks still apply)
            *args: Additional positional arguments passed to the superclass save method
            **kwargs: Additional keyword arguments passed to the superclass save method

        Raises:
            ValueError: Raised if there is an existing locked release report for the configuration, preventing publication
                        of another one without resolving the conflict.
        """
        is_being_published = self.published and not self.published_at
        if not is_being_published:
            super().save(*args, **kwargs)
        if is_being_published and self.file:
            if ReleaseReport.latest_published_locked(self.report_configuration, self):
                msg = (
                    f"A release report already exists with locked status for "
                    f"{self.report_configuration.display_name}. Delete or unlock the "
                    f"most recent report."
                )
                raise ValueError(msg)
            self.unpublish_previous_reports()
            new_filename = generate_release_report_filename(
                self.report_configuration.get_slug(), self.published
            )
            self.rename_file_to(new_filename, allow_published_overwrite)
            self.published_at = timezone.now()
            super().save()


# Signal handler to delete files when ReleaseReport is deleted
@receiver(pre_delete, sender=ReleaseReport)
def delete_release_report_files(sender, instance, **kwargs):
    """Delete file from storage when ReleaseReport is deleted."""
    if instance.file:
        instance.file.delete(save=False)
