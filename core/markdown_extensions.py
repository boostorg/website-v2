"""Markdown extensions registered in `settings.WAGTAILMARKDOWN`."""

import re
from html import escape

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

# The hook the client-side renderer looks for. nh3 allows `class` on every tag,
# so it is the one marker that survives sanitisation.
MERMAID_CLASS = "mermaid-diagram"

# ```mermaid, or the {mermaid} spelling the editor's preview also accepts.
_MERMAID_FENCE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})[ ]*\{?mermaid\}?[ ]*$")
_ANY_FENCE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})[ ]*\S*[ ]*$")


def _closes(line, fence):
    match = re.match(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})[ ]*$", line)
    return bool(
        match
        and match.group("fence")[0] == fence[0]
        and len(match.group("fence")) >= len(fence)
    )


class MermaidPreprocessor(Preprocessor):
    """Turn a mermaid fence into a `<pre class="mermaid-diagram">` block.

    Without this the fence reaches `codehilite`, which hands its output to
    pygments and drops the language along the way -- so a diagram arrives at the
    page as an anonymous code block, indistinguishable from C++ or Python, and
    the browser has nothing to render it from. Stashing the block here keeps the
    language and takes the source out of pygments' hands, which has no lexer for
    it anyway.

    The block is emitted as a code block on purpose: with no JavaScript, or
    before mermaid has loaded, the diagram's source is what the reader sees.
    """

    def run(self, lines):
        output = []
        index = 0
        while index < len(lines):
            line = lines[index]
            mermaid = _MERMAID_FENCE.match(line)
            other = None if mermaid else _ANY_FENCE.match(line)

            if not mermaid and not other:
                output.append(line)
                index += 1
                continue

            fence = (mermaid or other).group("fence")
            body = []
            cursor = index + 1
            while cursor < len(lines) and not _closes(lines[cursor], fence):
                body.append(lines[cursor])
                cursor += 1

            # An unclosed fence is the author's text as they typed it; leave the
            # whole run to the markdown parser rather than guess where it ends.
            if cursor >= len(lines):
                output.extend(lines[index:])
                break

            if mermaid:
                diagram = escape("\n".join(body))
                placeholder = self.md.htmlStash.store(
                    f'<pre class="{MERMAID_CLASS}"><code>{diagram}</code></pre>'
                )
                output.extend(["", placeholder, ""])
            else:
                # Another language's fence, kept verbatim for `fenced_code`. It
                # is consumed whole so a mermaid fence nested inside it stays
                # part of that block's source.
                output.extend(lines[index : cursor + 1])

            index = cursor + 1

        return output


class MermaidExtension(Extension):
    def extendMarkdown(self, md):
        # Above `fenced_code` (25), which would otherwise claim the block first.
        md.preprocessors.register(MermaidPreprocessor(md), "mermaid", 26)


def makeExtension(**kwargs):
    return MermaidExtension(**kwargs)
