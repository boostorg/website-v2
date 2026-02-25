from typing import NamedTuple
from structlog import get_logger
from wagtail.fields import StreamField

from django.db import models
from django.utils.functional import cached_property
from django.utils.text import slugify


from pages.blocks import POST_BLOCKS
from pages.mixins import BasePage

from news.constants import CONTENT_SUMMARIZATION_THRESHOLD
from news.tasks import summary_dispatcher


logger = get_logger(__name__)


class RoutableHomePage(BasePage):
    """
    Empty home page that contains subroutes for handling special url patters.

    e.g. Making sure that outreach is found at /outreach and posts are found at /posts
    """

    # Defines this as a home page
    parent_page_types = ["wagtailcore.Page"]
    #
    subpage_types = [
        "pages.PostIndexPage",
        "marketing.OutreachHomePage",
    ]
    max_count = 1

    def route(self, request, path_components):
        from marketing.models import OutreachHomePage

        path = request.path
        base = path.split("/")[1]
        if base == "outreach":
            outreach_home_page = self.get_children().type(OutreachHomePage).first()
            return outreach_home_page.route(request, path_components)
        return super().route(request, path_components)


class _PostContentType(NamedTuple):
    """
    Associates content block names with label, icon, and filter name
    """

    block_name: list = []
    icon_name: str = ""
    content_type: str = ""
    filter_name: str = ""


POST_CONTENT_TYPES = (
    _PostContentType(
        block_name=[],
        icon_name="globe",
        content_type="All",
        filter_name="",
    ),
    _PostContentType(
        block_name=["rich_text", "markdown"],
        icon_name="comment",
        content_type="Blog",
        filter_name="blog",
    ),
    _PostContentType(
        block_name=[],
        icon_name="newspaper",
        content_type="News",
        filter_name="news",
    ),
    _PostContentType(
        block_name=["video"],
        icon_name="video",
        content_type="Video",
        filter_name="video",
    ),
    _PostContentType(
        block_name=["url"],
        icon_name="link",
        content_type="Link",
        filter_name="link",
    ),
)
CONTENT_TYPES_BY_FILTER: dict[str, _PostContentType] = {
    x.filter_name: x for x in POST_CONTENT_TYPES if x.filter_name
}
CONTENT_TYPES_BY_BLOCK: dict[str, _PostContentType] = {}
for i in POST_CONTENT_TYPES:
    for bn in i.block_name:
        CONTENT_TYPES_BY_BLOCK[bn] = i


class PostIndexPage(BasePage):
    """
    Parent Index of News items, inheriting by base Page and displaying all content items when visited
    """

    parent_page_types = ["pages.RoutableHomePage"]
    subpage_types = ["pages.PostPage"]
    max_count = 1

    def get_children_by_content_type(
        self, content_type: str | list[str]
    ) -> models.QuerySet["PostPage"]:
        posts = PostPage.objects.child_of(self).live().order_by("-first_published_at")
        if isinstance(content_type, str):
            return posts.filter(content__0__type=content_type)
        elif isinstance(content_type, list):
            return posts.filter(content__0__type__in=content_type)
        else:
            return posts.none()

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)

        content_type = request.GET.get("type", "").lower()
        if content_value := CONTENT_TYPES_BY_FILTER.get(content_type, None):
            posts = self.get_children_by_content_type(content_value.block_name)
        else:
            posts = (
                self.get_children()
                .type(PostPage)
                .live()
                .order_by("-first_published_at")
            )

        ctx["posts"] = posts
        ctx["filters"] = POST_CONTENT_TYPES
        return ctx


class PostPage(BasePage):
    """
    News items, inheriting from base Page and having their content defined by a stream field named content
    """

    parent_page_types = ["pages.PostIndexPage"]
    subpage_types = []
    content = StreamField(POST_BLOCKS, min_num=1, max_num=1)
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    summary = models.TextField(
        blank=True, default="", help_text="AI generated summary. Delete to regenerate."
    )

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        pages = self.__class__.objects.live().order_by("-first_published_at")
        prev_objects = pages.filter(first_published_at__lt=self.first_published_at)
        next_objects = pages.filter(first_published_at__gt=self.first_published_at)
        ctx["prev"] = prev_objects.first()
        ctx["prev_in_category"] = prev_objects.filter(
            content__0__type=self.stream_content_type
        ).first()
        ctx["next"] = next_objects.last()
        ctx["next_in_category"] = next_objects.filter(
            content__0__type=self.stream_content_type
        ).last()
        return ctx

    def get_listing_url(self, request=None, current_site=None):
        if self.stream_content_type == "url":
            return self.content[0]
        return super().get_url(request, current_site)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        result = super().save(*args, **kwargs)

        if not self.summary:
            logger.info(f"Passing {self.pk=} to dispatcher")
            summary_dispatcher.delay(self.pk)

        return result

    @cached_property
    def use_summary(self):
        return bool(len(self.summary)) and (
            not self.content
            or len(str(self.content[0])) > CONTENT_SUMMARIZATION_THRESHOLD
        )

    @cached_property
    def visible_content(self):
        if self.use_summary:
            return self.summary
        return self.content

    @cached_property
    def stream_content_type(self):
        if not len(self.content):
            return ""
        else:
            return self.content[0].block.name

    @cached_property
    def post_content_type(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, _PostContentType()
        ).content_type

    @cached_property
    def icon_name(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, _PostContentType()
        ).icon_name

    @cached_property
    def filter_name(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, _PostContentType()
        ).filter_name

    content_panels = BasePage.content_panels + [
        "content",
        "image",
        "summary",
    ]
