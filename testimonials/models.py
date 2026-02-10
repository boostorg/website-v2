from django.conf import settings
from django.db import models
from django.urls import reverse
from wagtail.admin.panels import FieldPanel
from wagtail.blocks import RichTextBlock
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtailmarkdown.blocks import MarkdownBlock


class TestimonialsIndexPage(Page):
    """Container page for all testimonials."""

    max_count = 1  # Only allow one testimonials index page
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["testimonials.Testimonial"]

    def get_url(self, request=None, current_site=None):
        """Override to return the correct URL for this page."""
        return reverse("testimonials-index")

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        # Get all live testimonials that are children of this page
        context["testimonials"] = (
            Testimonial.objects.live().child_of(self).order_by("-first_published_at")
        )
        return context


class Testimonial(Page):
    author = models.CharField(max_length=255)
    author_slug = models.SlugField(
        help_text="Slug used for author's URL - must be unique", unique=True
    )
    author_url = models.URLField(
        help_text="Optional URL to link the author's name to", blank=True, default=""
    )
    pull_quote = StreamField(
        [
            ("md", MarkdownBlock(label="Markdown")),
        ],
        use_json_field=True,
        blank=True,
        help_text="Optional pull quote to highlight on the homepage",
    )
    body = StreamField(
        [
            (
                "rich",
                RichTextBlock(features=settings.RICH_TEXT_FEATURES, label="Rich text"),
            ),
            ("md", MarkdownBlock(label="Markdown")),
        ],
        use_json_field=True,
        blank=True,
    )

    # Configure Wagtail admin panels
    content_panels = Page.content_panels + [
        FieldPanel("title"),
        FieldPanel("author"),
        FieldPanel("author_slug"),
        FieldPanel("author_url"),
        FieldPanel("pull_quote"),
        FieldPanel("body"),
    ]

    # Define where this page type can be created
    parent_page_types = ["testimonials.TestimonialsIndexPage"]
    subpage_types = []  # Testimonials can't have child pages

    def get_url(self, request=None, current_site=None):
        """Override to return the correct URL for this page."""
        # Use the page's slug (set in Wagtail admin) for the URL
        return reverse("testimonial-detail", kwargs={"author_slug": self.slug})

    class Meta:
        verbose_name = "Testimonial"
        verbose_name_plural = "Testimonials"
