"""Presenter and template behaviour for the homepage testimonial carousel."""

from django.template.loader import render_to_string

from testimonials.models import Testimonial
from testimonials.utils import get_testimonial_cards


def make_testimonial(slug, body=None):
    """Build an unsaved Testimonial; the presenter only reads fields, so no DB."""
    testimonial = Testimonial(
        title=slug.title(), author="Author", author_slug=slug, slug=slug
    )
    testimonial.pull_quote = [("md", f"Quote for {slug}")]
    if body is not None:
        testimonial.body = body
    return testimonial


def render_card(cards):
    return render_to_string(
        "v3/includes/_testimonial_card.html",
        {"heading": "What engineers are saying", "testimonials": cards},
    )


def test_testimonial_without_body_has_no_content():
    (card,) = get_testimonial_cards(qs=[make_testimonial("no-body")])

    assert card["content"] == ""


def test_blank_rich_text_block_counts_as_no_content():
    """An empty rich-text block still renders a wrapper div, but shows nothing."""
    (card,) = get_testimonial_cards(qs=[make_testimonial("blank", [("rich", "")])])

    assert card["content"] == ""


def test_body_holding_only_an_image_counts_as_content():
    (card,) = get_testimonial_cards(
        qs=[make_testimonial("image", [("rich", '<img src="/a.png">')])]
    )

    assert card["content"] != ""


def test_modal_navigation_skips_testimonials_without_a_body():
    """Prev/next must never point at a slug with no modal behind it."""
    cards = get_testimonial_cards(
        qs=[
            make_testimonial("first", [("md", "First body")]),
            make_testimonial("middle"),
            make_testimonial("last", [("md", "Last body")]),
        ]
    )

    first, middle, last = cards
    assert (first["prev_url"], first["next_url"]) == ("#last", "#last")
    assert (last["prev_url"], last["next_url"]) == ("#first", "#first")
    assert (middle["prev_url"], middle["next_url"]) == ("", "")


def test_modals_render_when_the_first_testimonial_has_no_body():
    """A body-less card in the lead slot must not suppress the other modals."""
    cards = get_testimonial_cards(
        qs=[
            make_testimonial("no-body"),
            make_testimonial("has-body", [("md", "Full testimonial text")]),
        ]
    )

    html = render_card(cards)

    assert 'id="has-body"' in html
    assert 'href="#has-body"' in html
    assert 'id="no-body"' not in html


def test_read_more_is_disabled_for_a_testimonial_without_a_body():
    cards = get_testimonial_cards(qs=[make_testimonial("no-body")])

    html = render_card(cards)

    assert 'aria-disabled="true"' in html
    assert "Read more" in html
    assert 'href="#no-body"' not in html


def test_quote_bubble_is_not_a_link_without_a_body():
    cards = get_testimonial_cards(qs=[make_testimonial("no-body")])

    html = render_card(cards)

    assert "testimonial-card__quote-link" not in html


def test_every_testimonial_still_gets_a_card():
    """Missing bodies hide the modal, not the quote."""
    cards = get_testimonial_cards(
        qs=[make_testimonial("no-body"), make_testimonial("has-body", [("md", "Hi")])]
    )

    html = render_card(cards)

    assert len(cards) == 2
    assert "Quote for no-body" in html
    assert "Quote for has-body" in html
