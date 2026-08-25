"""Tests for the site-wide markdown allowlist in `settings.WAGTAILMARKDOWN`.

Everything the V3 WYSIWYG editor writes is rendered through it and sanitised by
nh3, so what the allowlist keeps is part of the editor's contract.
"""

from wagtailmarkdown.utils import render_markdown


def test_underline_survives_sanitisation():
    """The editor serialises its Underline mark as a literal <u>."""
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
    """An inline `width` is the only channel a resize survives on."""
    rendered = render_markdown(
        '<img src="/media/wysiwyg/a.jpg" alt="A" ' 'style="width: 320px">'
    )

    assert 'src="/media/wysiwyg/a.jpg"' in rendered
    assert "width:320px" in rendered.replace(" ", "")


def test_the_width_attribute_is_not_a_channel():
    """Why the width rides in `style`: nh3 allows only src/alt/title on an img.

    Should this ever stop stripping it, the editor could serialise the simpler
    form instead.
    """
    rendered = render_markdown('<img src="/media/wysiwyg/a.jpg" alt="A" width="320">')

    assert "320" not in rendered


def test_an_image_style_cannot_carry_anything_but_size():
    """Sizing is all the inline style is allowed to do.

    Markdown is author-written, so this attribute is reachable by hand — the
    `max-width` keeping an oversized image in its column has to stay unreachable.
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
