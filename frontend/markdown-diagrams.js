import { renderDiagram } from "./mermaid-diagram.js";

/*
Draws the mermaid diagrams in rendered markdown — a post's body, a profile's bio.

The server renders a ```mermaid fence as `<pre class="mermaid-diagram">` holding
the diagram's source (see core/markdown_extensions.py), which is what a reader
without JavaScript is left with. Here that source becomes the drawing.
*/

const SOURCE_SELECTOR = "pre.mermaid-diagram";

export const renderMarkdownDiagrams = async (root = document) => {
  for (const source of root.querySelectorAll(SOURCE_SELECTOR)) {
    const diagram = source.textContent.trim();
    if (!diagram) continue;

    const figure = document.createElement("figure");
    figure.className = "mermaid-diagram";
    source.replaceWith(figure);
    // Serially: mermaid holds one config and one measuring container, so
    // concurrent renders interleave into each other's diagram.
    await renderDiagram(figure, diagram, "mermaid-diagram");
  }
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => renderMarkdownDiagrams(), {
    once: true,
  });
} else {
  renderMarkdownDiagrams();
}
