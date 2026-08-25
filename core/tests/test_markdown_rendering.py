"""Tests for the site-wide markdown allowlist in `settings.WAGTAILMARKDOWN`.

Everything the V3 WYSIWYG editor writes — post bodies, profile biographies — is
Markdown rendered through wagtail-markdown's `markdown` filter and sanitised by
nh3. The editor serialises marks nh3's default allowlist doesn't all cover, so
the allowlist is part of the editor's contract, not just a settings detail.
"""

from wagtailmarkdown.utils import render_markdown


def test_underline_survives_sanitisation():
    """The editor's Underline mark round-trips as a literal <u> tag (#2303)."""
    assert render_markdown("<u>underlined</u>") == "<p><u>underlined</u></p>"


def test_the_other_inline_marks_still_render():
    rendered = render_markdown("**bold** *italic* ~~struck~~ `code`")

    assert "<strong>bold</strong>" in rendered
    assert "<em>italic</em>" in rendered
    assert "<del>struck</del>" in rendered
    assert "<code>code</code>" in rendered


def test_scripts_and_event_handlers_are_still_stripped():
    """Allowing <u> must not widen anything else."""
    rendered = render_markdown('<u onclick="steal()">x</u><script>alert(1)</script>')

    assert "onclick" not in rendered
    assert "<script>" not in rendered
    assert "<u>x</u>" in rendered


def test_image_width_survives_sanitisation():
    """A resized image keeps its size.

    The editor stores a resize as an inline `width`, which is the only channel
    that survives: nh3 allows `src`, `alt` and `title` on an image and drops
    every other attribute, but its CSS property allowlist includes `width`.
    """
    rendered = render_markdown(
        '<img src="/media/wysiwyg/a.jpg" alt="A" ' 'style="width: 320px">'
    )

    assert 'src="/media/wysiwyg/a.jpg"' in rendered
    assert "width:320px" in rendered.replace(" ", "")


def test_the_width_attribute_is_not_a_channel():
    """Why the width rides in `style` and not where an <img> would expect it.

    If this ever starts passing with the attribute intact, the editor could
    serialise the simpler form instead.
    """
    rendered = render_markdown('<img src="/media/wysiwyg/a.jpg" alt="A" width="320">')

    assert "320" not in rendered


def test_an_image_style_cannot_carry_anything_but_size():
    """Sizing is all the inline style is allowed to do.

    Markdown is author-written, so the style attribute is reachable by hand and
    not only through the editor. nh3 filters it down to its own property
    allowlist, which is what keeps a width from turning into a way out of the
    page — including the `max-width` the site's stylesheet uses to keep an
    oversized image inside its column.
    """
    rendered = render_markdown(
        '<img src="/a.jpg" style="position: fixed; inset: 0; z-index: 9999; '
        'max-width: 100vw; background: red; width: 320px">'
    )
    compact = rendered.replace(" ", "")

    assert "width:320px" in compact
    assert "position" not in compact
    assert "inset" not in compact
    assert "z-index" not in compact
    assert "max-width" not in compact
    assert "background" not in compact
