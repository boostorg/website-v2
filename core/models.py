import re

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from django.db.models.functions import Lower
from wagtail.admin.forms.models import WagtailAdminModelForm
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting

from libraries.path_matcher.utils import determine_latest_url
from versions.models import Version
from .managers import PopularSearchTermManager, RenderedContentManager


class LatestPathMatchIndicator(models.IntegerChoices):
    UNDETERMINED = 0, _("Undetermined")
    DIRECT_MATCH = 1, _("Direct match exists")
    CUSTOM_MATCH = 2, _("Determined by matcher")


class RenderedContent(TimeStampedModel):
    """Stores a copy of rendered content. Generally, this content is retrieved
    from the S3 buckets and, if necessary, converted to HTML.

    This model is intended to be used as a cache. If the content is not found,
    it will be retrieved from S3 and stored in this model. If the content is
    found, it will be returned from this model.

    TimeStampedModel adds `created` and `modified` fields:
    https://django-extensions.readthedocs.io/en/latest/model_extensions.html
    """

    cache_key = models.CharField(
        max_length=255,
        unique=True,
        help_text=_("The cache key for the content."),
        db_index=True,
    )
    content_type = models.CharField(
        max_length=255,
        help_text=_("The content type/MIME type."),
        null=True,
        blank=True,
    )
    content_original = models.TextField(
        help_text=_("The original content."), null=True, blank=True
    )
    content_html = models.TextField(
        help_text=_("The rendered HTML content."), null=True, blank=True
    )
    last_updated_at = models.DateTimeField(
        help_text=_("The last time the content was updated in S3."),
        null=True,
        blank=True,
    )

    latest_path_matched_indicator = models.IntegerField(
        choices=LatestPathMatchIndicator,
        default=LatestPathMatchIndicator.UNDETERMINED,
        null=False,
        blank=False,
        help_text=_("Indicates how the latest path should be determined."),
    )
    latest_docs_path = models.CharField(blank=True, default="")
    latest_path_match_class = models.CharField(max_length=128, blank=True, default="")

    objects = RenderedContentManager()

    class Meta:
        verbose_name = _("rendered content")
        verbose_name_plural = _("rendered contents")

    def __str__(self):
        return self.cache_key

    @property
    def latest_path(self) -> str | None:
        indicator = self.latest_path_matched_indicator
        if indicator == LatestPathMatchIndicator.DIRECT_MATCH:
            return re.sub(
                r"static_content_[\d_]+/(?P<content_path>[^/]\S+)",
                "doc/libs/latest/\g<content_path>",
                self.cache_key,
            )
        elif indicator == LatestPathMatchIndicator.CUSTOM_MATCH:
            return self.latest_docs_path
        elif indicator == LatestPathMatchIndicator.UNDETERMINED:
            return determine_latest_url(
                self.cache_key.replace("static_content_", ""),
                Version.objects.most_recent(),
            )

    def save(self, *args, **kwargs):
        if isinstance(self.content_original, bytes):
            self.content_original = self.content_original.decode("utf-8")
        if isinstance(self.content_html, bytes):
            self.content_html = self.content_html.decode("utf-8")
        if isinstance(self.content_type, bytes):
            self.content_type = self.content_type.decode("utf-8")

        super().save(*args, **kwargs)


class SiteSettings(models.Model):
    wordcloud_ignore = models.TextField(
        default="",
        help_text="A comma-separated list of words to ignore in the release report wordcloud.",  # noqa E501
    )
    rendered_content_replacement_start = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="Set via RenderedContent admin action.",
    )
    pinned_community_libraries = models.ManyToManyField(
        "libraries.Library",
        blank=True,
        related_name="pinned_on_community_page",
        help_text=(
            "Pinned libraries always shown on the community page. "
            "Remaining slots are filled randomly from other libraries."
        ),
    )

    class Meta:
        constraints = [
            # check constraint to only allow id=1 to exist
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_single_instance",
                condition=models.Q(id=1),
            ),
        ]
        verbose_name_plural = "Site Settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def wordcloud_ignore_set(self):
        return set(x.strip().lower() for x in self.wordcloud_ignore.split(","))


class HomepageSettingsForm(WagtailAdminModelForm):
    """Scopes the library choosers to flagship and core libraries present in
    the latest stable release, A→Z."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from libraries.models import FEATURED_LIBRARY_TIERS, Library

        qs = Library.objects.filter(tier__in=FEATURED_LIBRARY_TIERS)
        latest = Version.objects.most_recent()
        if latest:
            qs = qs.filter(library_version__version=latest)
        qs = qs.order_by(Lower("name"))
        self.fields["featured_library"].queryset = qs
        self.fields["highlighted_libraries"].queryset = qs


@register_setting
class HomepageSettings(BaseGenericSetting):
    """Editor-managed homepage configuration, set in the Wagtail admin."""

    base_form_class = HomepageSettingsForm

    featured_library = models.ForeignKey(
        "libraries.Library",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=(
            "Library featured in the V3 homepage. Only flagship and core "
            "libraries present in the latest stable release are listed "
            "(beta-only libraries are excluded). If not set, a random "
            "flagship or core library will be featured."
        ),
    )

    highlighted_libraries = models.ManyToManyField(
        "libraries.Library",
        blank=True,
        related_name="+",
        help_text=(
            "Libraries shown in the homepage 'Explore battle tested "
            "libraries' carousel. Only flagship and core libraries present in "
            "the latest stable release are listed. If empty, a random "
            "selection of flagship or core libraries is used."
        ),
    )

    panels = [
        FieldPanel("featured_library"),
        FieldPanel("highlighted_libraries"),
    ]

    class Meta:
        verbose_name = "Homepage Settings"


class PopularSearchTerm(models.Model):
    """Top popular Algolia search terms, refreshed weekly by Celery.

    Each weekly refresh runs an LLM quality check to drop typos/garbage
    before any row is written. Tick `is_pinned` on an admin-created row to
    pin it above Algolia-fetched terms; the weekly refresh leaves
    `is_pinned` alone.
    """

    label = models.CharField(max_length=64)
    # `rank` is a compound sort key whose meaning depends on row state:
    #   - fresh rows (this week's refresh): rank 1..N in popularity order
    #   - stale rows: re-packed into a contiguous band right below the fresh
    #     block each run (ordered by prior rank), so they sort below fresh
    #     without their rank growing unbounded over time
    #   - pinned rows: curator-set rank for explicit ordering above all others
    # Always interpret `rank` together with `is_pinned`. Full rationale in
    # docs/popular_search_terms.md.
    rank = models.PositiveSmallIntegerField()
    search_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(
        default=False,
        help_text=(
            "Pin this term above Algolia-derived rows on the homepage. "
            "Use rank to order among multiple pins."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    objects = PopularSearchTermManager()

    class Meta:
        ordering = ["-is_pinned", "rank", "label"]
        constraints = [
            models.UniqueConstraint(
                Lower("label"),
                name="core_popularsearchterm_label_ci_unique",
                violation_error_message=(
                    "A popular search term with this label already exists "
                    "(matching is case-insensitive)."
                ),
            )
        ]

    def save(self, *args, **kwargs):
        self.label = self.label.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        pin = "[PIN] " if self.is_pinned else ""
        return f"{pin}{self.rank}. {self.label} ({self.search_count})"


class PopularSearchTermExclusion(models.Model):
    """Search terms that should never appear on the homepage (case-insensitive)."""

    term = models.CharField(max_length=64)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        # Exclusions are matched case-insensitively; enforce that at the DB layer.
        constraints = [
            models.UniqueConstraint(
                Lower("term"),
                name="core_popularsearchtermexclusion_term_ci_unique",
                violation_error_message=(
                    "This term is already in the exclusion list "
                    "(matching is case-insensitive)."
                ),
            )
        ]

    def save(self, *args, **kwargs):
        self.term = self.term.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.term
