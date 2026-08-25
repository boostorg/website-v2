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
