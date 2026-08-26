import DOMPurify from "dompurify";

/*
Loading, rendering and sanitising a mermaid diagram. Shared by the editor, which
draws a preview under the block being written, and by markdown-diagrams.js,
which draws the diagrams in already-published content.
*/

/*
A <template>'s content belongs to an inert document: setting innerHTML on one
runs no script and starts no resource load.
*/
const parseInert = (html) => {
  const template = document.createElement("template");
  template.innerHTML = html;
  return template;
};

/* Links a <foreignObject> back to its own label; sanitising shifts positions. */
const LABEL_ATTRIBUTE = "data-wysiwyg-label";

/*
Narrower than DOMPurify's HTML profile on purpose: mermaid does not escape what
a diagram's source puts in a label, so `A["<img src=x>"]` arrives as a real
element. A label is a line of formatted text and nothing more.
*/
const LABEL_PURIFY_CONFIG = {
  ALLOWED_TAGS: ["div", "span", "p", "br", "b", "i", "em", "strong", "code", "sub", "sup"],
  ALLOWED_ATTR: ["class", "style"],
};

/*
`style` cannot simply be dropped: mermaid sizes each label with one and the
values differ per label. But a diagram's source reaches it by the same route as
the <img> above, and `position: fixed` is how a box escapes its box, so only the
properties mermaid lays labels out with are kept.
*/
const LABEL_STYLE_PROPERTIES = new Set([
  "display",
  "white-space",
  "line-height",
  "max-width",
  "width",
  "text-align",
]);

const pruneLabelStyles = (root) => {
  root.querySelectorAll("[style]").forEach((element) => {
    const kept = [];
    // Via the CSSOM, so the browser parses the declarations rather than a regex.
    for (const property of element.style) {
      if (LABEL_STYLE_PROPERTIES.has(property)) {
        kept.push(`${property}: ${element.style.getPropertyValue(property)}`);
      }
    }
    if (kept.length) element.setAttribute("style", kept.join("; "));
    else element.removeAttribute("style");
  });
};

/*
Sanitize a mermaid-rendered SVG, labels included. Returns a DocumentFragment.

Two passes, because DOMPurify drops HTML whose parent is a <foreignObject>, and
that is where mermaid puts every label — one SVG-profile pass returns a diagram
of unlabelled boxes. So labels are lifted out and sanitised as HTML, the
skeleton is sanitised on its own, and the two are reassembled. Both halves still
go through DOMPurify: this widens what survives, not what is trusted.

A fragment rather than a string so nothing re-parses the markup after DOMPurify
has passed it — the round trip mutation XSS relies on.
*/
export function sanitizeSvg(svgString) {
  const source = parseInert(svgString);

  const labels = [];
  source.content.querySelectorAll("foreignObject").forEach((host) => {
    host.setAttribute(LABEL_ATTRIBUTE, String(labels.length));
    labels.push(DOMPurify.sanitize(host.innerHTML, LABEL_PURIFY_CONFIG));
    host.replaceChildren();
  });

  const cleaned = DOMPurify.sanitize(source.innerHTML, {
    USE_PROFILES: { svg: true, svgFilters: true },
    ADD_TAGS: ["use", "foreignObject"],
    RETURN_DOM_FRAGMENT: true,
  });

  cleaned.querySelectorAll(`foreignObject[${LABEL_ATTRIBUTE}]`).forEach((host) => {
    const label = labels[Number(host.getAttribute(LABEL_ATTRIBUTE))] ?? "";
    host.removeAttribute(LABEL_ATTRIBUTE);
    // In an HTML context, so the nodes keep the namespace foreignObject hosts.
    const nodes = parseInert(label).content;
    pruneLabelStyles(nodes);
    host.append(...nodes.childNodes);
  });

  return cleaned;
}

let mermaidModule = null;
let mermaidIdCounter = 0;

export const getMermaid = async () => {
  if (mermaidModule) return mermaidModule;
  if (window.mermaid) {
    mermaidModule = window.mermaid;
  } else {
    await new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js";
      script.integrity = "sha256-pDvBr9RG+cTMZqxd1F0C6NZeJvxTROwO94f4jW3bb54=";
      script.crossOrigin = "anonymous";
      script.onload = resolve;
      script.onerror = () => reject(new Error("Failed to load mermaid"));
      document.head.appendChild(script);
    });
    mermaidModule = window.mermaid;
  }
  // Without suppressErrorRendering, a parse failure leaves mermaid's "Syntax
  // error" graphic stranded on <body>, at the foot of the page.
  //
  // A diagram's text colour comes from the theme, not from the page, so the
  // light theme on a dark page is dark text on a dark background. Read once,
  // because mermaid keeps one config: a theme switch after this shows in the
  // diagrams on the next load.
  mermaidModule.initialize({
    startOnLoad: false,
    theme: document.documentElement.classList.contains("dark") ? "dark" : "default",
    suppressErrorRendering: true,
  });
  return mermaidModule;
};

/*
Render `diagram` into `container` as an SVG, or as an inline error message.
Both outcomes stay in the container; mermaid's own error rendering does not (see
the suppressErrorRendering note in getMermaid).

`baseClass` names the container's own class, so the error state lands on the
modifier of whichever component is hosting the diagram.
*/
export const renderDiagram = async (
  container,
  diagram,
  baseClass = "mermaid-preview",
) => {
  try {
    const mermaid = await getMermaid();
    const { svg } = await mermaid.render(`mermaid-${++mermaidIdCounter}`, diagram);
    container.classList.remove(`${baseClass}--error`);
    container.replaceChildren(sanitizeSvg(svg));
  } catch (err) {
    const message = document.createElement("span");
    message.className = "mermaid-error";
    message.textContent = err?.message || "Invalid diagram";
    container.classList.add(`${baseClass}--error`);
    container.replaceChildren(message);
  }
};
