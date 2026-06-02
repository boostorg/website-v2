"""Reusable presenters for Testimonial pages (homepage carousel, demo page, etc.)."""

import html

from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from wagtail.rich_text import expand_db_html

from testimonials.models import Testimonial


def _pull_quote_text(testimonial):
    """Plain-text pull quote for the carousel bubble (StreamField renders to HTML)."""
    return html.unescape(strip_tags(str(testimonial.pull_quote))).strip()


def _avatar_url(testimonial):
    return (
        testimonial.author_avatar.get_rendition("fill-96x96").url
        if testimonial.author_avatar
        else ""
    )


def _author_role_html(testimonial):
    """Render the role RichTextField, expanding Wagtail link formats; safe for direct template output."""
    role = testimonial.author_role or ""
    return mark_safe(expand_db_html(role)) if role else ""


def _to_card(testimonial, *, prev_slug, next_slug):
    return {
        "quote": _pull_quote_text(testimonial),
        "content": str(testimonial.body),
        "title": testimonial.title,
        "subtitle": f"By {testimonial.author}",
        "slug": testimonial.slug,
        "prev_url": f"#{prev_slug}",
        "next_url": f"#{next_slug}",
        "author": {
            "name": testimonial.author,
            "profile_url": testimonial.author_url,
            "role": _author_role_html(testimonial),
            "avatar_url": _avatar_url(testimonial),
        },
    }


def get_testimonial_cards(qs=None, limit=None):
    """Carousel-card dicts for the V3 _testimonial_card.html include and its modals.

    Defaults to live testimonials that have a pull quote, newest first; pass a
    custom `qs` to scope/order differently. The page slug targets the bundled
    Content Modal, with prev/next wrapping cyclically.
    """
    if qs is None:
        qs = (
            Testimonial.objects.live()
            .filter(pull_quote__gt="")
            .order_by("-first_published_at")
        )
    testimonials = list(qs[:limit] if limit else qs)
    count = len(testimonials)
    return [
        _to_card(
            testimonial,
            prev_slug=testimonials[(i - 1) % count].slug,
            next_slug=testimonials[(i + 1) % count].slug,
        )
        for i, testimonial in enumerate(testimonials)
    ]
