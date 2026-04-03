from django.db import models
from django.http import HttpResponseForbidden
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import ItemBase
from taggit.models import TagBase
from wagtail.models import Page
from wagtail.snippets.models import register_snippet
import waffle


@register_snippet
class ContentTag(TagBase):
    # Disable Free tagging, to prevent adding extraneous tags
    free_tagging = False

    class Meta:
        verbose_name = "content tag"
        verbose_name_plural = "content tags"


class TaggedContent(ItemBase):
    tag = models.ForeignKey(
        ContentTag,
        related_name="tagged_content",
        on_delete=models.CASCADE,
    )
    content_object = ParentalKey(
        to="wagtailcore.Page",
        on_delete=models.CASCADE,
        related_name="tagged_items",
    )


class TaggableMixin(Page):
    tags = ClusterTaggableManager(
        through="pages.TaggedContent",
        blank=True,
    )

    content_panels = Page.content_panels + ["tags"]

    class Meta:
        abstract = True


class FlaggedMixin(Page):
    def serve(self, request, *args, **kwargs):
        if not waffle.flag_is_active(request, "v3"):
            return HttpResponseForbidden("You do not have access to this page.")
        return super().serve(request, *args, **kwargs)

    class Meta:
        abstract = True


class BasePage(FlaggedMixin, TaggableMixin, Page):
    """
    Abstract Base Page for all our new Pages to inherit from
    """

    class Meta(Page.Meta):
        abstract = True
