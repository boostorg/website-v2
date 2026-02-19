from django.db import models
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import ItemBase
from taggit.models import TagBase
from wagtail.snippets.models import register_snippet


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
        to="wagtail.Page", on_delete=models.CASCADE, related_name="tagged_items"
    )


class TaggableMixin:
    tags = ClusterTaggableManager(
        through="pages.TaggedContent",
        blank=True,
    )


class FlaggedMixin:
    pass
