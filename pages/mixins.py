from django.db import models
from modelcluster.fields import ParentalKey
from taggit.models import ItemBase
from taggit.models import TagBase
from wagtail.models import Page
from wagtail.snippets.models import register_snippet

from core.mixins import V3Mixin


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
        to="pages.PostPage",
        on_delete=models.CASCADE,
        related_name="tagged_items",
    )


class BasePage(V3Mixin, Page):
    """
    Abstract Base Page for all our new Pages to inherit from
    """

    class Meta(Page.Meta):
        abstract = True
