from typing import NamedTuple

from wagtail.contrib.routable_page.models import RoutablePageMixin
from wagtail.fields import StreamField

from django.db.models import QuerySet

from pages.blocks import POST_BLOCKS
from pages.mixins import BasePage


class RoutableHomePage(BasePage, RoutablePageMixin):
    """
    Empty home page that contains subroutes for handling special url patters.

    e.g. Making sure that outreach is found at /outreach and posts are found at /posts
    """

    # Defines this as a home page
    parent_page_types = ["wagtailcore.Page"]
    #
    subpage_types = ["pages.PostIndexPage"]
    max_count = 1


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
    ) -> QuerySet["PostPage"]:
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

    @property
    def stream_content_type(self):
        if not len(self.content):
            return ""
        else:
            return self.content[0].block.name

    @property
    def post_content_type(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, _PostContentType()
        ).content_type

    @property
    def icon_name(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, _PostContentType()
        ).icon_name

    @property
    def filter_name(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, _PostContentType()
        ).filter_name

    content_panels = BasePage.content_panels + [
        "content",
    ]
