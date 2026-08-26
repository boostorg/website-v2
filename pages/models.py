from structlog import get_logger
from wagtail.admin.panels import FieldPanel
from wagtail.models import PageManager
from wagtail.url_routing import RouteResult
from wagtail.fields import RichTextField, StreamField
from wagtail.search import index

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import ExpressionWrapper, FloatField, F, Func, Value
from django.db.models.functions import Coalesce, Greatest, Now, Power
from django.db import models
from django.urls import reverse_lazy
from django.utils.functional import cached_property
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.utils.timezone import localtime, now

from modelcluster.contrib.taggit import ClusterTaggableManager

from waffle import flag_is_active


from libraries.utils import library_filter_options
from pages.blocks import POST_BLOCKS
from pages.feed import (
    CONTENT_TYPES_BY_BLOCK,
    FEED_FILTER_TERMS,
    UNKNOWN_CONTENT_TYPE,
    PostFeedFilters,
)
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


class PostIndexPage(BasePage):
    """
    Parent Index of News items, inheriting by base Page and displaying all content items when visited
    """

    parent_page_types = ["pages.RoutableHomePage"]
    subpage_types = ["pages.PostPage"]
    template = "v3/posts_list.html"
    max_count = 1

    PAGE_SIZE = 10
    RELATED_POSTS_LIMIT = 3

    def route(self, request, path_components):
        """Act as an umbrella handler for both Wagtail posts and legacy entries.

        `path_components` is the remainder of the path below this page, so for
        `/news/some-post/` it is `["some-post"]`. With the flag off an entry
        that has no `PostPage` counterpart would 404 here, so we route it to
        this page and let `serve()` hand it to the legacy detail view.
        """
        from news.models import Entry

        if (
            len(path_components) == 1
            and not flag_is_active(request, "v3")
            and not self.get_children().filter(slug=path_components[0]).exists()
        ):
            if entry := Entry.objects.filter(slug=path_components[0]).first():
                return RouteResult(self, kwargs={"pk": entry.pk})
        return super().route(request, path_components)

    def serve(self, request, *args, **kwargs):
        if not flag_is_active(request, "v3"):
            # Rather than return a 404 on non v3 views, we allow Legacy
            # and wagtail to live at the same endpoint by serving the Legacy view
            from news.views import EntryListView

            if pk := kwargs.get("pk"):
                from news.views import EntryDetailView

                return EntryDetailView.as_view()(request, pk=pk)

            return EntryListView.as_view()(request)

        return super().serve(request, *args, **kwargs)

    def _filtered_queryset(self, filters) -> models.QuerySet["PostPage"]:
        posts = (
            PostPage.objects.child_of(self)
            .live()
            .select_related("owner")
            # tags per card, and the author's routing keys for the profile link.
            .prefetch_related("tags", "owner__profile_routing_keys")
        )
        if filters.post_type:
            posts = posts.filter(content__0__type__in=filters.post_type.block_name)
        if filters.library:
            # tagged_items rather than tags: the reverse relation resolves
            # against the concrete PostPage table under either tag arrangement.
            posts = posts.filter(tagged_items__tag__slug=filters.library.slug)
        if filters.author:
            posts = posts.filter(owner=filters.author)
        return posts.order_by("-first_published_at")

    def _results(self, filters):
        """Filtered posts, searched when a term was submitted.

        The search backend rejects StreamField and tag lookups, so the filters
        are applied first and handed back in through a pk subquery. Anything
        the result rows need (select_related, prefetch_related) has to be set
        up before .search(), which returns SearchResults rather than a queryset.
        """
        posts = self._filtered_queryset(filters)
        if not filters.q:
            return posts
        return (
            PostPage.objects.filter(pk__in=posts.order_by().values("pk"))
            .select_related("owner")
            .prefetch_related("tags", "owner__profile_routing_keys")
            .search(filters.q)
        )

    def _related_posts(self, filters):
        """Fallback shown with the empty state: same library, search dropped.

        Only a library filter produces related posts. Without one the widest
        fallback would be the whole feed, which reads as "no results, here is
        everything" rather than as a suggestion.
        """
        if not filters.library:
            return []
        for fallback in (filters.without("q"), filters.without("q", "post_type")):
            related = list(
                self._filtered_queryset(fallback)[: self.RELATED_POSTS_LIMIT]
            )
            if related:
                return related
        return []

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        ctx.update(self.feed_context(request))
        return ctx

    def feed_context(self, request):
        """Template context for the posts feed.

        Public because the feed is also served from the legacy news URL, where
        the v3 flag decides between it and the v2 Entry list. The posts it
        lists are this page's children either way, so the context is built
        here rather than duplicated against the same tree.
        """
        ctx = {}
        filters = PostFeedFilters.from_request(request)
        pag = Paginator(self._results(filters), self.PAGE_SIZE)
        page_obj = pag.get_page(request.GET.get("page", 1))

        ctx["paginator"] = pag
        ctx["is_paginated"] = True
        ctx["entry_list"] = page_obj
        ctx["page_obj"] = page_obj
        ctx["header_text"] = filters.header_text
        ctx["filter_terms"] = FEED_FILTER_TERMS
        ctx["filter_value"] = filters.type_value
        ctx["library_options"] = library_filter_options()
        ctx["library_value"] = filters.library_value
        ctx["search_value"] = filters.q
        ctx["author_value"] = filters.author_value
        ctx["empty_message"] = filters.empty_message
        if not page_obj.object_list and filters.is_active:
            ctx["related_posts"] = self._related_posts(filters)
        return ctx


class ExtractEpoch(Func):
    function = "EXTRACT"
    template = "%(function)s(EPOCH FROM %(expressions)s)"
    output_field = FloatField()


class PostPageManager(PageManager):
    def ranked(self):
        gravity = float(getattr(settings, "POSTS_RANKING_GRAVITY", 2.0))
        # `first_published_at` is nullable; without the Coalesce its NULL score
        # would sort ahead of every real post under Postgres' DESC NULLS FIRST.
        published_at = Coalesce("first_published_at", "last_published_at", Now())
        age_in_hours = ExpressionWrapper(
            Greatest(ExtractEpoch(Now() - published_at), Value(0.0)) / Value(3600.0),
            output_field=FloatField(),
        )
        score = ExpressionWrapper(
            F("page_views") / Power(age_in_hours + Value(2.0), Value(gravity)),
            output_field=FloatField(),
        )
        return (
            self.get_queryset().annotate(ranking_score=score).order_by("-ranking_score")
        )


class PostPage(BasePage):
    """
    News items, inheriting from base Page and having their content defined by a stream field named content
    """

    objects = PostPageManager()

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
    tags = ClusterTaggableManager(through="pages.TaggedContent", blank=True)
    page_views = models.PositiveIntegerField(default=0)

    def serve(self, request, *args, **kwargs):
        if not flag_is_active(request, "v3"):
            # Rather than return a 404 on non v3 views, we allow Legacy
            # and wagtail to live at the same endpoint by serving the Legacy view
            from news.views import EntryDetailView

            return EntryDetailView.as_view()(request, slug=self.slug)

        return super().serve(request, *args, **kwargs)

    def get_content(self):
        if self.post_content_type in ["News", "Blogpost"]:
            return self.content
        else:
            return None

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        pages: models.QuerySet = PostPage.objects.live().order_by("-first_published_at")
        if self.first_published_at:
            next_objects = pages.filter(first_published_at__gt=self.first_published_at)
        else:
            next_objects = pages
        if next_objects.exists():
            ctx["next_post_items"] = [next_objects.last()]
        ctx["related_posts"] = (
            pages.filter(tags__in=self.tags.all()).exclude(pk=self.pk).distinct()[:3]
        ) or pages.filter(content__0__type=self.stream_content_type).exclude(
            pk=self.pk
        )[
            :3
        ]
        ctx["object"] = self.specific
        ctx["post_author"] = self.author
        ctx["user_can_edit"] = self.user_can_edit(request.user)
        ctx["user_can_delete"] = self.user_can_delete(request.user)
        ctx["user_can_approve"] = False

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

    def get_preview_context(self, request, mode_name):
        ctx = super().get_preview_context(request, mode_name)
        ctx["is_preview"] = True
        return ctx

    def edit_url(self):
        return reverse_lazy("v3-news-edit", kwargs={"slug": self.slug})

    def delete_url(self):
        return reverse_lazy("v3-news-delete", kwargs={"slug": self.slug})
    def to_v3_post_card_dict(self, author_role=None):
        """Dict shape consumed by `v3/includes/_post_card.html` items."""
        from news.models import POST_CARD_TAG_LABELS

        category = ""

        if self.tag:
            tag_key = str(self.tag).lower()
            category = POST_CARD_TAG_LABELS.get(tag_key, self.tag.capitalize())

        return {
            "title": self.title,
            "url": self.get_absolute_url(),
            "date": self.date or self.publish_at,
            "category": category,
            "tag": "",
            "author": (
                self.author.to_v3_profile_dict(role=author_role)
                if self.author
                else None
            ),
        }

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

    @property
    def needs_approval(self):
        return self.workflow_in_progress

    @cached_property
    def search_body(self):
        """Plain-text body used for search indexing.

        Indexing `content` directly stores the raw block output, which for
        markdown and rich text is HTML - a search for "p" would then match
        every post through its `<p>` tags.

        Failures are swallowed on purpose: the indexing task records an error
        without re-raising, so a raising indexer would quietly make the post
        unfindable instead of failing loudly.
        """
        try:
            field = self._meta.get_field("content")
            return strip_tags(" ".join(field.get_searchable_content(self.content)))
        except Exception:
            logger.exception("search_body_failed", page_id=self.pk)
            return ""

    @cached_property
    def stream_content_type(self):
        if not len(self.content):
            return ""
        else:
            return self.content[0].block.name

    @cached_property
    def post_content_type(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, UNKNOWN_CONTENT_TYPE
        ).content_type

    @cached_property
    def icon_name(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, UNKNOWN_CONTENT_TYPE
        ).icon_name

    @cached_property
    def filter_name(self):
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, UNKNOWN_CONTENT_TYPE
        ).filter_name

    @cached_property
    def author(self):
        return self.owner

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
    def type_label(self):
        """How the post's type is worded on a card, e.g. "Blog".

        Deliberately not `post_content_type`. That is the internal name of the
        type, and for one of them the two differ: a reader is shown "Blog"
        where the code says "Blogpost".
        """
        return CONTENT_TYPES_BY_BLOCK.get(
            self.stream_content_type, UNKNOWN_CONTENT_TYPE
        ).header_label

    @cached_property
    def tag(self):
        if self.tags.exists():
            return self.tags.first()
        return None

    @cached_property
    def external_url(self):
        if self.post_content_type == "Link":
            return self.content[0].value
        elif self.post_content_type == "Video":
            return self.content[0].value.url
        else:
            return None

    def _in_edit_window(self):
        first_revision = self.revisions.order_by("created_at").first()
        if not first_revision:
            return False

        right_now = localtime(now())
        td = abs(right_now - first_revision.created_at)
        if td.days > 0 or abs(right_now - first_revision.created_at).seconds > (
            6 * 60 * 60
        ):
            return False
        return True

    def user_can_edit(self, user):
        return self.owner == user and self._in_edit_window()

    def user_can_delete(self, user):
        return self.owner == user and self._in_edit_window()

    content_panels = BasePage.content_panels + [
        "tags",
        "content",
        "image",
        "summary",
        "video_thumbnail",
        FieldPanel("page_views", read_only=True),
    ]

    # `title` is already indexed by Page.search_fields, so it is not repeated
    # here. Note that filters have to be applied *before* .search(): the search
    # backend rejects StreamField and tag lookups, and the SearchResults it
    # returns is not a queryset. See PostIndexPage._results for how the feed
    # works around that.
    search_fields = BasePage.search_fields + [
        index.SearchField("search_body"),
        index.SearchField("summary"),
        index.SearchField("post_content_type"),
        index.RelatedFields(
            "tags",
            [
                index.SearchField("name"),
                index.SearchField("slug"),
            ],
        ),
        index.RelatedFields(
            "owner",
            [
                index.SearchField("display_name"),
            ],
        ),
    ]


class LegalPage(BasePage):
    """Simple policy/legal page: title + rich text body.

    "Last Updated" in the template uses the built-in `last_published_at`,
    so republishing in Wagtail auto-updates the visible date.
    """

    template = "v3/legal_page.html"

    parent_page_types = ["pages.RoutableHomePage"]
    subpage_types = []

    body = RichTextField(features=settings.RICH_TEXT_FEATURES, blank=True)

    content_panels = BasePage.content_panels + ["body"]
