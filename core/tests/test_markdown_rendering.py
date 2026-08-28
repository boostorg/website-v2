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


def test_a_mermaid_fence_renders_as_a_diagram_block():
    """The class is the hook static/js/v3/markdown-diagrams.js renders from."""
    rendered = render_markdown("```mermaid\ngraph TD; A-->B;\n```")

    assert rendered == (
        '<pre class="mermaid-diagram"><code>graph TD; A--&gt;B;</code></pre>'
    )


def test_the_braced_spelling_is_a_diagram_too():
    """The editor's own preview accepts ```{mermaid}, so this has to as well."""
    rendered = render_markdown("```{mermaid}\ngraph TD; A-->B;\n```")

    assert 'class="mermaid-diagram"' in rendered


def test_a_diagram_reaches_the_page_as_text():
    """The source is what mermaid parses, so nothing may interpret it first.

    Highlighting a diagram is also what used to happen to it: `codehilite` hands
    every fence to pygments and drops the language on the way, which is why the
    block arrived indistinguishable from any other code.
    """
    rendered = render_markdown('```mermaid\ngraph TD; A["<b>bold</b>"];\n```')

    assert "&lt;b&gt;bold&lt;/b&gt;" in rendered
    assert "<b>" not in rendered
    assert "codehilite" not in rendered


def test_other_languages_are_still_highlighted():
    rendered = render_markdown("```python\nprint(1)\n```")

    assert "codehilite" in rendered
    assert "mermaid-diagram" not in rendered


def test_a_mermaid_fence_inside_another_fence_is_that_block_s_source():
    rendered = render_markdown("```python\n# ```mermaid\nprint(1)\n```")

    assert "mermaid-diagram" not in rendered
    assert "codehilite" in rendered


def test_an_unclosed_mermaid_fence_keeps_the_rest_of_the_document():
    """No closing fence means no diagram to find the end of; the text stands."""
    rendered = render_markdown("```mermaid\ngraph TD; A-->B;\n\nAfter the fence.")

    assert "mermaid-diagram" not in rendered
    assert "After the fence." in rendered
