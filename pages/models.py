from typing import NamedTuple
from structlog import get_logger
from wagtail.fields import StreamField

from django.core.paginator import Paginator
from django.db import models
from django.utils.functional import cached_property
from django.utils.text import slugify


from pages.blocks import POST_BLOCKS
from pages.mixins import BasePage

from news.tasks import summary_dispatcher
from news.tasks import set_thumbnail_for_video_page

logger = get_logger(__name__)


class RoutableHomePage(BasePage):
    """
    Empty home page that contains subroutes for handling special url patters.

    e.g. Making sure that outreach is found at /outreach and posts are found at /posts
    """

    # Defines this as a home page
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = [
        "pages.PostIndexPage",
        "marketing.OutreachHomePage",
    ]
    max_count = 1

    def route(self, request, path_components):

        path = request.path.rstrip("/").lstrip("/")
        split_path = path.split("/")
        base, *rest = split_path

        if match_child := self.get_children().filter(slug=base).first():
            matched_route = match_child.specific.route(request, rest)
            return matched_route
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
        block_name=["rich_text", "blog"],
        icon_name="comment",
        content_type="Blogpost",
        filter_name="blogpost",
    ),
    _PostContentType(
        block_name=["news"],
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
    template = "v3/posts_list.html"
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
            entry_list = self.get_children_by_content_type(
                content_value.block_name
            ).specific()
        else:
            entry_list = (
                self.get_children()
                .type(PostPage)
                .live()
                .order_by("-first_published_at")
                .specific()
            )

        pag = Paginator(entry_list, 10)
        ctx["paginator"] = pag
        ctx["is_paginated"] = True
        ctx["entry_list"] = pag.get_page(request.GET.get("page", 1))
        ctx["page_obj"] = ctx["entry_list"]
        ctx["header_text"] = "Latest Posts"
        # TODO: Once all content types are settled, this should be generated using our CONTENT_TYPES
        ctx["filter_terms"] = [
            {
                "label": "All",
                "value": "all",
                "url": self.get_url(),
            },
            {
                "label": "News",
                "value": "news",
                "url": self.get_url() + "?type=news",
            },
            {
                "label": "Blogs",
                "value": "blogpost",
                "url": self.get_url() + "?type=blogpost",
            },
            {
                "label": "Links",
                "value": "link",
                "url": self.get_url() + "?type=link",
            },
            {
                "label": "Videos",
                "value": "video",
                "url": self.get_url() + "?type=video",
            },
            {
                "label": "Discussions",
                "value": "discussions",
                "url": self.get_url(),
            },
            {
                "label": "Achievements",
                "value": "achievements",
                "url": self.get_url(),
            },
            {
                "label": "Issues",
                "value": "issues",
                "url": self.get_url(),
            },
        ]
        ctx["filter_value"] = content_type
        return ctx


class PostPage(BasePage):
    """
    News items, inheriting from base Page and having their content defined by a stream field named content
    """

    parent_page_types = ["pages.PostIndexPage"]
    subpage_types = []
    template = "news/v3/detail.html"

    content = StreamField(POST_BLOCKS, min_num=1, max_num=1)
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    video_thumbnail = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    summary = models.TextField(
        blank=True, default="", help_text="AI generated summary. Delete to regenerate."
    )

    def get_content(self):
        if self.post_content_type in ["News", "Blogpost"]:
            return self.content
        else:
            return None

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        pages = self.__class__.objects.live().order_by("-first_published_at")
        next_objects = pages.filter(first_published_at__gt=self.first_published_at)
        ctx["next_post_items"] = [next_objects.last()]
        ctx["related_posts"] = pages.filter(content__0__type=self.stream_content_type)[
            :3
        ]
        ctx["object"] = self.specific
        ctx["post_author"] = self.author
        return ctx

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        result = super().save(*args, **kwargs)

        if not self.summary and self.live:
            logger.info(f"Passing {self.pk=} to dispatcher")
            summary_dispatcher.delay(self.pk, "PostPage")

        if not self.video_thumbnail and self.post_content_type == "Video" and self.live:
            logger.info(f"Setting thumbnail for {self.pk=}")
            set_thumbnail_for_video_page.delay(self.pk)

        return result

    @cached_property
    def use_summary(self):
        return bool(len(self.summary))

    @property
    def visible_content(self):
        if self.post_content_type == "Video":
            return None
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

    @cached_property
    def author(self):
        return self.owner

    @cached_property
    def get_absolute_url(self):
        return self.url

    @cached_property
    def image_url(self):
        if not self.image:
            return ""
        return self.image.get_rendition("original").url

    @cached_property
    def created_at(self):
        return self.first_published_at

    @cached_property
    def publish_at(self):
        return self.last_published_at

    @cached_property
    def date(self):
        return self.first_published_at

    @cached_property
    def determined_news_type(self):
        return self.post_content_type

    @cached_property
    def tag(self):
        if self.tags.exists():
            return self.tags.first()
        return self.post_content_type

    @cached_property
    def external_url(self):
        if self.post_content_type == "Link":
            return self.content[0]
        elif self.post_content_type == "Video":
            return self.content[0].value.url
        else:
            return None

    content_panels = BasePage.content_panels + [
        "content",
        "image",
        "summary",
        "video_thumbnail",
    ]
