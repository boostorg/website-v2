"""Flag-aware URL helpers for posts.

Posts live in two places during the V3 migration:

* the legacy ``news.Entry`` models, served by ``news.views`` under
  ``/news/entry/``;
* the Wagtail ``pages.PostPage`` tree, served under ``/news/``.

Which of the two a link must point at depends entirely on the ``v3`` waffle
flag, so every post URL in the codebase is built through these helpers rather
than through a bare ``reverse()`` or ``{% slugurl %}``. Turning the flag off
puts every reference back on the legacy Entry routes, which is what makes the
flag a usable rollback switch.

This module lives in ``pages`` rather than ``news`` on purpose: when the legacy
Entry models are retired, the ``v3_posts_active`` branches and the ``reverse()``
fallbacks are deleted in place and what remains still belongs here.
"""

from django.urls import reverse
from waffle import flag_is_active

_INDEX_PAGE_CACHE_ATTR = "_v3_post_index_page"


def v3_posts_active(request) -> bool:
    """True when posts should be sourced from and linked to Wagtail."""
    return request is not None and flag_is_active(request, "v3")


def get_post_index_page(request=None):
    """The live Wagtail post index page, or None if it has not been created.

    Cached on the request because the header context processor needs it on
    every single page render.
    """
    if request is not None and hasattr(request, _INDEX_PAGE_CACHE_ATTR):
        return getattr(request, _INDEX_PAGE_CACHE_ATTR)

    from pages.models import PostIndexPage

    page = PostIndexPage.objects.live().first()
    if request is not None:
        setattr(request, _INDEX_PAGE_CACHE_ATTR, page)
    return page


def post_index_url(request, post_type: str = "") -> str:
    """URL of the post list, optionally filtered to a single post type.

    Falls back to the legacy list whenever the flag is off or the Wagtail
    index page does not exist yet, so a link is never rendered as "None".
    """
    if v3_posts_active(request):
        index = get_post_index_page(request)
        if index is not None:
            url = index.get_url(request=request)
            if url:
                if post_type and post_type != "all":
                    return f"{url}?type={post_type}"
                return url
    return reverse("news")


def get_post_page(slug: str):
    """The live Wagtail post with this slug, or None."""
    from pages.models import PostPage

    return PostPage.objects.live().filter(slug=slug).first()


def post_detail_url(request, slug: str) -> str:
    """URL of a single post.

    Under V3 this resolves to the Wagtail page. An entry that has no Wagtail
    counterpart yet (the conversion command has not been run, or the post is
    not live) keeps its legacy URL rather than 404ing.
    """
    if v3_posts_active(request):
        page = get_post_page(slug)
        if page is not None:
            url = page.get_url(request=request)
            if url:
                return url
    return reverse("news-detail", args=[slug])
