"""Filter state for the posts feed.

Kept out of ``pages.models`` so the content-type table, the querystring parsing
and the header wording can be read (and tested) without loading the page tree.
"""

from dataclasses import dataclass
from dataclasses import replace
from typing import NamedTuple

from django.contrib.auth import get_user_model

from libraries.models import Library

SEARCH_TERM_MAX_LENGTH = 200


class _PostContentType(NamedTuple):
    """
    Associates content block names with label, icon, and filter name
    """

    block_name: list = []
    icon_name: str = ""
    content_type: str = ""
    filter_name: str = ""
    # Pill labels are plural, feed header labels are singular, and neither
    # always matches content_type ("Blogpost" would read "Blogpost Posts").
    label: str = ""
    header_label: str = ""


POST_CONTENT_TYPES = (
    _PostContentType(
        block_name=[],
        icon_name="globe",
        content_type="All",
        filter_name="",
        label="All",
    ),
    _PostContentType(
        block_name=["rich_text", "blog"],
        icon_name="comment",
        content_type="Blogpost",
        filter_name="blogpost",
        label="Blogs",
        header_label="Blog",
    ),
    _PostContentType(
        block_name=["news"],
        icon_name="newspaper",
        content_type="News",
        filter_name="news",
        label="News",
        header_label="News",
    ),
    _PostContentType(
        block_name=["video"],
        icon_name="video",
        content_type="Video",
        filter_name="video",
        label="Videos",
        header_label="Video",
    ),
    _PostContentType(
        block_name=["url"],
        icon_name="link",
        content_type="Link",
        filter_name="link",
        label="Links",
        header_label="Link",
    ),
)
# Stand-in for a block with no content type entry, e.g. a poll.
UNKNOWN_CONTENT_TYPE = _PostContentType()

CONTENT_TYPES_BY_FILTER: dict[str, _PostContentType] = {
    x.filter_name: x for x in POST_CONTENT_TYPES if x.filter_name
}
CONTENT_TYPES_BY_BLOCK: dict[str, _PostContentType] = {}
for i in POST_CONTENT_TYPES:
    for bn in i.block_name:
        CONTENT_TYPES_BY_BLOCK[bn] = i

# These post types are in the design but have no implementation behind them.
# They are rendered disabled rather than left to silently behave like "All".
UNAVAILABLE_FILTER_TERMS = [
    {"label": "Discussions", "value": "discussions", "disabled": True},
    {"label": "Achievements", "value": "achievements", "disabled": True},
    {"label": "Issues", "value": "issues", "disabled": True},
]

FEED_FILTER_TERMS = [
    {
        "label": content_type.label or content_type.content_type,
        "value": content_type.filter_name,
    }
    for content_type in POST_CONTENT_TYPES
] + UNAVAILABLE_FILTER_TERMS


@dataclass(frozen=True)
class PostFeedFilters:
    """Validated feed filter state, parsed from the querystring.

    Every value is resolved to a real object here so that nothing raw from the
    querystring can reach the feed header.
    """

    q: str = ""
    post_type: _PostContentType | None = None
    library: Library | None = None
    author: object | None = None

    # Values a field resets to in without(); anything unlisted resets to None.
    _RESET_VALUES = {"q": ""}

    @classmethod
    def from_request(cls, request):
        params = request.GET
        return cls(
            q=params.get("q", "").strip()[:SEARCH_TERM_MAX_LENGTH],
            post_type=CONTENT_TYPES_BY_FILTER.get(
                params.get("type", "").strip().lower()
            ),
            library=cls._resolve_library(params.get("library", "").strip()),
            author=cls._resolve_author(params.get("author", "").strip()),
        )

    @staticmethod
    def _resolve_library(slug):
        if not slug:
            return None
        return Library.objects.filter(slug=slug).first()

    @staticmethod
    def _resolve_author(value):
        if not value.isdigit():
            return None
        return get_user_model().objects.filter(pk=value).first()

    @property
    def is_active(self):
        return bool(self.q or self.post_type or self.library or self.author)

    @property
    def type_value(self):
        return self.post_type.filter_name if self.post_type else ""

    @property
    def library_value(self):
        return self.library.slug if self.library else ""

    @property
    def author_value(self):
        return self.author.pk if self.author else ""

    @property
    def header_text(self):
        if self.q:
            return f'Results for "{self.q}"'
        if self.author:
            return f"Posts by {self.author.display_name or self.author}"
        if self.post_type:
            return f"{self.post_type.header_label} Posts"
        if self.library:
            return f"{self.library.display_name} Posts"
        return "Latest Posts"

    @property
    def empty_message(self):
        if self.is_active:
            return "No posts match your search or filters."
        return "There are no posts yet."

    def without(self, *names):
        """Copy with the named filters cleared, e.g. without("q", "post_type")."""
        return replace(self, **{name: self._RESET_VALUES.get(name) for name in names})
