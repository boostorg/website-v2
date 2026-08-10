"""Reusable presenters for Testimonial pages (homepage carousel, demo page, etc.)."""

import html
import re

from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from wagtail.rich_text import expand_db_html

from testimonials.models import Testimonial

# Tags that carry visible content on their own, so a body holding only these
# is not blank even though stripping tags leaves no text behind.
_MEDIA_TAG_RE = re.compile(
    r"<(img|iframe|video|audio|embed|object|svg)\b", re.IGNORECASE
)


def _pull_quote_text(testimonial):
    """Plain-text pull quote for the carousel bubble (StreamField renders to HTML)."""
    return html.unescape(strip_tags(str(testimonial.pull_quote))).strip()


def _body_html(testimonial):
    """Rendered body HTML, normalized to "" when it holds nothing visible.

    An unset StreamField already stringifies to "", but a rich-text block left
    blank renders an empty wrapper div. Both mean "no modal to open", so the
    templates get a single falsy value to branch on.
    """
    body = str(testimonial.body)
    if strip_tags(body).strip() or _MEDIA_TAG_RE.search(body):
        return body
    return ""


def _avatar_url(testimonial):
    return (
        testimonial.author_avatar.get_rendition("fill-96x96").url
        if testimonial.author_avatar
        else ""
    )


def _author_role_html(testimonial):
    """Render the role RichTextField, expanding Wagtail link formats; safe for direct template output.

    Links open in a new tab to match the rest of the testimonial author profile.
    """
    role = testimonial.author_role or ""
    if not role:
        return ""
    expanded = expand_db_html(role).replace(
        "<a ", '<a target="_blank" rel="noopener noreferrer" '
    )
    return mark_safe(expanded)


def _to_card(testimonial, *, content, prev_slug, next_slug):
    return {
        "quote": _pull_quote_text(testimonial),
        "content": content,
        "title": testimonial.title,
        "subtitle": f"By {testimonial.author}",
        "slug": testimonial.slug,
        "prev_url": f"#{prev_slug}" if prev_slug else "",
        "next_url": f"#{next_slug}" if next_slug else "",
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

    A testimonial may have a pull quote but no body. Those still get a card, so
    the quote stays on the page, but no modal — and the prev/next cycle skips
    them so paging never lands on a slug with nothing rendered behind it.
    """
    if qs is None:
        qs = (
            Testimonial.objects.live()
            .filter(pull_quote__gt="")
            .order_by("-first_published_at")
        )
    testimonials = list(qs[:limit] if limit is not None else qs)
    contents = [_body_html(testimonial) for testimonial in testimonials]

    modal_slugs = [
        testimonial.slug
        for testimonial, content in zip(testimonials, contents)
        if content
    ]
    neighbors = {
        slug: (
            modal_slugs[(i - 1) % len(modal_slugs)],
            modal_slugs[(i + 1) % len(modal_slugs)],
        )
        for i, slug in enumerate(modal_slugs)
    }

    cards = []
    for testimonial, content in zip(testimonials, contents):
        prev_slug, next_slug = neighbors.get(testimonial.slug, ("", ""))
        cards.append(
            _to_card(
                testimonial,
                content=content,
                prev_slug=prev_slug,
                next_slug=next_slug,
            )
        )
    return cards
