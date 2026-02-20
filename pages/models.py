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


class PostIndexPage(BasePage):
    """
    Parent Index of News items, inheriting by base Page and displaying all content items when visited
    """

    parent_page_types = ["pages.RoutableHomePage"]
    subpage_types = ["pages.PostPage"]
    max_count = 1

    def get_children_by_content_type(self, content_type: str) -> QuerySet["PostPage"]:
        posts = PostPage.objects.child_of(self).live().order_by("-first_published_at")
        print(posts.first().content[0].block)
        return posts.filter(content__0__name=content_type)

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)

        posts = (
            self.get_children().type(PostPage).live().order_by("-first_published_at")
        )
        if content_type := request.GET.get("content-type", "").lower():
            match content_type:
                case "blog":
                    posts = self.get_children_by_content_type("rich_text")

        ctx["posts"] = posts
        return ctx


class PostPage(BasePage):
    """
    News items, inheriting from base Page and having their content defined by a stream field named content
    """

    parent_page_types = ["pages.PostIndexPage"]
    subpage_types = []
    content = StreamField(POST_BLOCKS, min_num=1, max_num=1)

    @property
    def content_type(self):
        if not len(self.content):
            return ""
        else:
            return self.content[0].block.name

    @property
    def post_content_type(self):
        match self.content_type:
            case "rich_text":
                return "Blog"
            case "markdown":
                return "Blog"
            case "url":
                return "Link"
            case "video":
                return "Video"
            case "poll":
                return "Poll"

    @property
    def icon_name(self):
        match self.content_type:
            case "rich_text":
                return "comment"
            case "markdown":
                return "comment"
            case "url":
                return "link"
            case "video":
                return "video"
            case "poll":
                return "poll"

    content_panels = BasePage.content_panels + [
        "content",
    ]
