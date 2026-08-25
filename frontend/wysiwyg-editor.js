
import { Editor, Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import StarterKit from "@tiptap/starter-kit";
import CodeBlockLowlight from "@tiptap/extension-code-block-lowlight";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import Table from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import Image from "@tiptap/extension-image";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import { common, createLowlight } from "lowlight";
import { toHtml } from "hast-util-to-html";
import { marked } from "marked";
import DOMPurify from "dompurify";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";

marked.use({
  gfm: true,
  extensions: [{
    name: "fences",
    level: "block",
    tokenizer(src) {
      const match = src.match(/^`{3,}\s*\{(\w+)\}\s*\n([\s\S]*?)^`{3,}\s*$/m);
      if (match) {
        return { type: "code", raw: match[0], text: match[2], lang: match[1] };
      }
    },
  }],
});

export function parseMarkdownSafe(md) {
  return DOMPurify.sanitize(marked.parse(md));
}

/*
Parse markup without letting any of it come alive.

A <template>'s content belongs to an inert document with no browsing context:
setting innerHTML on one runs no script and starts no resource load, which is
the same guarantee DOMPurify itself relies on.
*/
const parseInert = (html) => {
  const template = document.createElement("template");
  template.innerHTML = html;
  return template;
};

/*
Links a <foreignObject> in the sanitised SVG back to its own sanitised label.
Position would be too fragile — a removed element shifts every later index.
*/
const LABEL_ATTRIBUTE = "data-wysiwyg-label";

/*
What a diagram label is allowed to be: the wrapper mermaid emits (a styled div
around a classed span) plus the inline formatting a label can carry. Narrower
than DOMPurify's HTML profile on purpose — a label is a line of formatted text,
so there is no reason for it to be able to introduce links, media or anything
else the profile would wave through.

`style` is the one broad thing left on the list, because mermaid lays every
label out with an inline style and dropping it collapses the label box. It is
not a script vector — `url(javascript:...)` in CSS is inert in every current
browser — and label text is escaped by mermaid's own securityLevel before it
reaches here, so reaching this attribute at all means mermaid's escaping was
already defeated.
*/
const LABEL_PURIFY_CONFIG = {
  ALLOWED_TAGS: ["div", "span", "p", "br", "b", "i", "em", "strong", "code", "sub", "sup"],
  ALLOWED_ATTR: ["class", "style"],
};

/*
Sanitize a mermaid-rendered SVG, labels included. Returns a DocumentFragment.

Two passes, because one cannot do the job. mermaid puts every node and edge
label in an SVG <foreignObject> wrapping HTML, and DOMPurify drops HTML whose
parent is a foreignObject — `annotation-xml` is its only HTML integration point
— so a single SVG-profile pass returns a diagram of unlabelled boxes. Instead
the labels are lifted out and sanitised as HTML (see LABEL_PURIFY_CONFIG), the
SVG skeleton is sanitised on its own, and the cleaned labels go back where they
came from. Both halves still go through DOMPurify: this widens what survives,
not what is trusted.

A fragment rather than a string so that nothing serialises and re-parses the
markup after DOMPurify has passed it — the round trip mutation XSS relies on,
and foreignObject, sitting on the SVG/HTML namespace boundary, is exactly where
parsers disagree. Callers insert the nodes as they are.
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
    // Parsed in an HTML context so the nodes keep the HTML namespace that
    // <foreignObject> exists to host; appending adopts them across documents.
    host.append(...parseInert(label).content.childNodes);
  });

  return cleaned;
}

const lowlight = createLowlight(common);

const CODE_LANGUAGES = [
  { value: "cpp", label: "C++" },
  { value: "python", label: "Python" },
  { value: "mermaid", label: "Mermaid" },
];
const DEFAULT_CODE_LANGUAGE = "cpp";

// Matches core.validators.IMAGE_EXTENSIONS, which the upload endpoint enforces.
const IMAGE_UPLOAD_ACCEPT = "image/jpeg,image/png";


const turndown = new TurndownService({
  headingStyle: "atx",
  codeBlockStyle: "fenced",
  fence: "```",
  bulletListMarker: "-",
  emDelimiter: "*",
  strongDelimiter: "**",
  hr: "---",
});
turndown.use(gfm);

turndown.addRule("underline", {
  filter: ["u"],
  replacement: (content) => `<u>${content}</u>`,
});

turndown.addRule("taskListItem", {
  filter: (node) =>
    node.nodeName === "LI" && node.getAttribute("data-type") === "taskItem",
  replacement: (content, node) => {
    const checked = node.getAttribute("data-checked") === "true";
    const prefix = checked ? "- [x] " : "- [ ] ";
    const text = content.replace(/^\s+/, "").replace(/\s+$/, "");
    return prefix + text + "\n";
  },
});

turndown.addRule("taskList", {
  filter: (node) =>
    node.nodeName === "UL" && node.getAttribute("data-type") === "taskList",
  replacement: (content) => "\n" + content + "\n",
});


export const isSafeUrl = (url) => {
  try {
    const parsed = new URL(url, window.location.href);
    return ["http:", "https:", "mailto:"].includes(parsed.protocol);
  } catch {
    return false;
  }
};

let dialogIdCounter = 0;

/*
Build one field of a dialog body, using the V3 form markup (_field_text.html /
_field_file.html) so the inputs look like every other form on the site. Returns
the wrapper element and the input to read the value from.
*/
const buildDialogField = ({ name, label, type, placeholder, accept, help }, dialogId) => {
  const field = document.createElement("div");
  field.className = type === "file" ? "field field--file" : "field";

  const inputId = `${dialogId}-${name}`;
  const labelEl = document.createElement("label");
  labelEl.className = "field__label";
  labelEl.setAttribute("for", inputId);
  labelEl.textContent = label;
  field.appendChild(labelEl);

  const control = document.createElement("div");
  control.className =
    type === "file" ? "field__control field__control--file" : "field__control";

  const input = document.createElement("input");
  input.id = inputId;
  input.type = type || "text";
  input.className = type === "file" ? "field__input field__input--file" : "field__input";
  if (placeholder) input.placeholder = placeholder;
  if (accept) input.accept = accept;

  if (type === "file") {
    // _field_file.html hides the native input and shows its own label, because
    // browsers render "No file chosen" in a style we can't touch.
    const display = document.createElement("span");
    display.className = "field__file-display";
    display.setAttribute("aria-hidden", "true");
    const placeholderEl = document.createElement("span");
    placeholderEl.className = "field__file-placeholder";
    placeholderEl.textContent = "Choose File";
    display.appendChild(placeholderEl);
    control.appendChild(display);
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      placeholderEl.className = file ? "field__file-name" : "field__file-placeholder";
      placeholderEl.textContent = file ? file.name : "Choose File";
    });
  }

  control.appendChild(input);
  field.appendChild(control);

  if (help) {
    const helpEl = document.createElement("p");
    helpEl.className = "field__help";
    helpEl.id = `${inputId}-help`;
    helpEl.textContent = help;
    input.setAttribute("aria-describedby", helpEl.id);
    field.appendChild(helpEl);
  }

  return { field, input };
};

/*
Open a modal dialog and resolve with whatever `onSubmit` returns, or null if the
user dismisses it.

Rendered with the shared V3 Dialog component's classes (see _dialog.html /
dialog.css) rather than a bespoke look; only the pieces that component has no
template for — the form body, and backdrop/close as <button> instead of <a>,
since there is nowhere to navigate — are styled in wysiwyg-editor.css.

`onSubmit` receives the field values and may be async; throwing an Error keeps
the dialog open and shows the message in it, which is how a rejected image
upload or an unsafe URL is reported.
*/
export const openDialog = ({ title, fields, submitLabel = "Insert", onSubmit }) =>
  new Promise((resolve) => {
    const dialogId = `wysiwyg-dialog-${++dialogIdCounter}`;
    const previouslyFocused = document.activeElement;

    const overlay = document.createElement("div");
    overlay.className = "dialog-modal dialog-modal--open wysiwyg-dialog";

    const backdrop = document.createElement("button");
    backdrop.type = "button";
    backdrop.className = "dialog-modal__backdrop";
    backdrop.tabIndex = -1;
    backdrop.setAttribute("aria-label", "Close dialog");
    overlay.appendChild(backdrop);

    const container = document.createElement("div");
    container.className = "dialog-modal__container";
    container.setAttribute("role", "dialog");
    container.setAttribute("aria-modal", "true");
    container.setAttribute("aria-labelledby", `${dialogId}-title`);

    const header = document.createElement("div");
    header.className = "dialog-modal__header";
    const heading = document.createElement("h2");
    heading.className = "dialog-modal__title";
    heading.id = `${dialogId}-title`;
    heading.textContent = title;
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "dialog-modal__close";
    closeBtn.setAttribute("aria-label", "Close dialog");
    closeBtn.innerHTML = ICONS.close;
    header.appendChild(heading);
    header.appendChild(closeBtn);
    container.appendChild(header);

    const body = document.createElement("div");
    body.className = "wysiwyg-dialog__body";
    const inputs = {};
    fields.forEach((spec) => {
      const { field, input } = buildDialogField(spec, dialogId);
      inputs[spec.name] = input;
      body.appendChild(field);
    });

    const error = document.createElement("p");
    error.className = "field__error";
    error.setAttribute("role", "alert");
    error.setAttribute("aria-live", "polite");
    error.hidden = true;
    body.appendChild(error);
    container.appendChild(body);

    const actions = document.createElement("div");
    actions.className = "dialog-modal__buttons";
    const submitBtn = document.createElement("button");
    submitBtn.type = "button";
    submitBtn.className = "btn btn-primary btn-flex";
    submitBtn.textContent = submitLabel;
    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "btn btn-secondary btn-flex";
    cancelBtn.textContent = "Cancel";
    actions.appendChild(submitBtn);
    actions.appendChild(cancelBtn);
    container.appendChild(actions);

    overlay.appendChild(container);
    document.body.appendChild(overlay);

    const firstInput = Object.values(inputs)[0];
    if (firstInput) requestAnimationFrame(() => firstInput.focus());

    const close = (result) => {
      overlay.remove();
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
      resolve(result);
    };

    const submit = async () => {
      if (submitBtn.disabled) return;
      const values = {};
      for (const [key, input] of Object.entries(inputs)) {
        values[key] = input.type === "file" ? input.files[0] || null : input.value.trim();
      }
      submitBtn.disabled = true;
      error.hidden = true;
      try {
        close(await onSubmit(values));
      } catch (err) {
        submitBtn.disabled = false;
        error.textContent = err?.message || "Something went wrong.";
        error.hidden = false;
      }
    };

    backdrop.addEventListener("click", () => close(null));
    closeBtn.addEventListener("click", () => close(null));
    cancelBtn.addEventListener("click", () => close(null));
    submitBtn.addEventListener("click", submit);
    container.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.target.tagName === "INPUT") submit();
      if (e.key === "Escape") close(null);
    });
  });

/*
POST a file to the editor's upload endpoint and resolve with the stored URL.

The endpoint and the CSRF token come from the wrapper's data attributes (see
_wysiwyg_editor.html) because the editor is built entirely in JS and has no
template of its own to read them from.
*/
export const uploadEditorImage = async (file, wrapper) => {
  const uploadUrl = wrapper?.dataset.wysiwygUploadUrl;
  if (!uploadUrl) throw new Error("Uploading images isn't available here.");

  const body = new FormData();
  body.append("image", file);
  const response = await fetch(uploadUrl, {
    method: "POST",
    headers: { "X-CSRFToken": wrapper.dataset.wysiwygCsrfToken || "" },
    credentials: "same-origin",
    body,
  });

  let data = {};
  try {
    data = await response.json();
  } catch (_) {}
  if (!response.ok || !data.url) {
    throw new Error(data.error || "Could not upload that image.");
  }
  return data.url;
};

let mermaidModule = null;
let mermaidIdCounter = 0;

const getMermaid = async () => {
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
  // suppressErrorRendering: on a parse failure mermaid otherwise draws its
  // "Syntax error in text" graphic into the scratch element it appends to
  // <body> and leaves both behind, so a mistyped diagram in the editor turns up
  // stranded at the foot of the page. With this set it cleans up and rethrows,
  // and the error is reported next to the code block instead.
  mermaidModule.initialize({
    startOnLoad: false,
    theme: "default",
    suppressErrorRendering: true,
  });
  return mermaidModule;
};

export const debounce = (fn, ms) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
};

export const createToolbarButton = (editor, opts) => {
  const { label, onClick, isActive, isDisabled, title } = opts;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "wysiwyg-toolbar__btn";
  btn.setAttribute("aria-label", label);
  if (title) btn.setAttribute("title", title);
  btn.innerHTML = opts.html || label;
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    onClick();
  });
  const updateActive = () => {
    btn.classList.toggle("wysiwyg-toolbar__btn--active", isActive ? isActive() : false);
    // Optional disabled state (e.g. undo/redo greyed out when no history).
    if (isDisabled) {
      const disabled = isDisabled();
      btn.disabled = disabled;
      btn.classList.toggle("wysiwyg-toolbar__btn--disabled", disabled);
    }
  };
  editor.on("selectionUpdate", updateActive);
  editor.on("transaction", updateActive);
  updateActive();
  return btn;
}

const createSeparator = () => {
  const sep = document.createElement("span");
  sep.className = "wysiwyg-toolbar__sep";
  return sep;
};

const createHeadingDropdown = (editor) => {
  const select = document.createElement("select");
  select.className = "wysiwyg-toolbar__lang-select";
  select.setAttribute("aria-label", "Heading level");
  select.setAttribute("title", "Heading level");

  const options = [
    { value: "p", label: "Paragraph" },
    { value: "1", label: "Heading 1" },
    { value: "2", label: "Heading 2" },
    { value: "3", label: "Heading 3" },
  ];
  options.forEach(({ value, label }) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
  });

  select.addEventListener("change", () => {
    const val = select.value;
    if (val === "p") {
      editor.chain().focus().setParagraph().run();
    } else {
      editor.chain().focus().toggleHeading({ level: parseInt(val) }).run();
    }
  });

  const updateSelect = () => {
    if (editor.isActive("heading", { level: 1 })) select.value = "1";
    else if (editor.isActive("heading", { level: 2 })) select.value = "2";
    else if (editor.isActive("heading", { level: 3 })) select.value = "3";
    else select.value = "p";
  };
  editor.on("selectionUpdate", updateSelect);
  editor.on("transaction", updateSelect);
  updateSelect();
  return select;
};

export const ICONS = {
  bulletList:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>',
  orderedList:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/></svg>',
  checkbox:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  link:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
  image:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
  markdown:
    '<svg width="18" height="18" viewBox="0 0 26 18" fill="currentColor" aria-hidden="true"><path d="M2 2h3l3 4 3-4h3v10h-3V6l-3 4-3-4v6H2V2zm17 0h3l3 5h-2v5h-3V7h-2l4-5z" fill-rule="evenodd"/></svg>',
  preview:
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
  // Undo / redo and close are the UI-kit glyphs, shared by every preset so no
  // toolbar falls back to a text arrow. `close` mirrors includes/icon.html's
  // "close" pixel-art icon, which templates get from the icon include.
  undo:
    '<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M8.66667 7.83203C7.25 8.08203 6 8.58203 4.83333 9.4987L2.5 7.08203V12.9154H8.33333L6.08333 10.6654C9.16667 8.4987 13.4167 9.16536 15.6667 12.2487C15.8333 12.4987 16 12.6654 16.0833 12.9154L17.5833 12.1654C15.75 8.9987 12.25 7.2487 8.66667 7.83203Z"/></svg>',
  redo:
    '<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M11.3333 7.83203C12.75 8.08203 14 8.58203 15.1667 9.4987L17.5 7.08203V12.9154H11.6667L13.9167 10.6654C10.8333 8.41536 6.58333 9.16536 4.41667 12.2487C4.25 12.4987 4.08333 12.6654 4 12.9154L2.5 12.1654C4.25 8.9987 7.75 7.2487 11.3333 7.83203Z"/></svg>',
  close:
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M5 5h2v2H5V5zm4 4H7V7h2v2zm2 2H9V9h2v2zm2 0h-2v2H9v2H7v2H5v2h2v-2h2v-2h2v-2h2v2h2v2h2v2h2v-2h-2v-2h-2v-2h-2v-2zm2-2v2h-2V9h2zm2-2v2h-2V7h2zm0 0V5h2v2h-2z"/></svg>',
};

/*
Biography toolbar icons, normalized to `currentColor` so they inherit the
toolbar button colour and active/hover states. Used only by the "bio" toolbar
preset so the icons on other editors (news, examples) are unchanged.
*/
export const BIO_ICONS = {
  bold:
    '<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M12.7096 9.83464C13.1177 9.58617 13.462 9.24582 13.7152 8.84071C13.9684 8.4356 14.1234 7.97694 14.168 7.5013C14.1757 7.07121 14.0986 6.6438 13.9411 6.2435C13.7837 5.84319 13.5489 5.47783 13.2501 5.16829C12.9514 4.85875 12.5947 4.61109 12.2002 4.43945C11.8058 4.26781 11.3814 4.17556 10.9513 4.16797H5.54297V15.8346H11.3763C11.7856 15.8303 12.19 15.7453 12.5665 15.5847C12.943 15.424 13.2841 15.1908 13.5704 14.8983C13.8567 14.6058 14.0826 14.2597 14.2352 13.8799C14.3878 13.5001 14.464 13.0939 14.4596 12.6846V12.5846C14.4599 12.0072 14.2954 11.4417 13.9854 10.9546C13.6754 10.4675 13.2328 10.0789 12.7096 9.83464ZM7.20964 5.83464H10.7096C11.0648 5.82364 11.4148 5.92154 11.7127 6.11518C12.0106 6.30882 12.2422 6.58895 12.3763 6.91797C12.512 7.35779 12.4681 7.83346 12.2542 8.24101C12.0403 8.64857 11.6737 8.95487 11.2346 9.09297C11.0641 9.14294 10.8873 9.1682 10.7096 9.16797H7.20964V5.83464ZM11.043 14.168H7.20964V10.8346H11.043C11.3981 10.8236 11.7481 10.9215 12.046 11.1152C12.3439 11.3088 12.5755 11.5889 12.7096 11.918C12.8454 12.3578 12.8015 12.8335 12.5875 13.241C12.3736 13.6486 12.0071 13.9549 11.568 14.093C11.3975 14.1429 11.2207 14.1682 11.043 14.168Z"/></svg>',
  italic:
    '<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M9.79818 7.5013H11.4648L9.63151 15.8346H7.96484L9.79818 7.5013ZM11.1982 4.16797C11.0334 4.16797 10.8722 4.21684 10.7352 4.30841C10.5982 4.39998 10.4914 4.53013 10.4283 4.6824C10.3652 4.83467 10.3487 5.00223 10.3809 5.16388C10.413 5.32553 10.4924 5.47401 10.6089 5.59056C10.7255 5.7071 10.874 5.78647 11.0356 5.81862C11.1973 5.85078 11.3648 5.83427 11.5171 5.7712C11.6694 5.70813 11.7995 5.60132 11.8911 5.46428C11.9826 5.32724 12.0315 5.16612 12.0315 5.0013C12.0315 4.78029 11.9437 4.56833 11.7874 4.41205C11.6312 4.25577 11.4192 4.16797 11.1982 4.16797Z"/></svg>',
  underline:
    '<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M15.8346 16.668V18.3346H4.16797V16.668H15.8346ZM13.3346 11.0138C13.3072 11.5638 13.1439 12.0984 12.8594 12.5699C12.5749 13.0414 12.178 13.435 11.7042 13.7157C11.2304 13.9963 10.6945 14.1552 10.1443 14.1781C9.59412 14.2011 9.04681 14.0874 8.5513 13.8471C7.98017 13.6001 7.49581 13.1881 7.16028 12.664C6.82474 12.1399 6.65332 11.5276 6.66797 10.9055V4.17214H5.0013V11.0138C5.0295 11.7983 5.24201 12.5652 5.62165 13.2523C6.00129 13.9394 6.53738 14.5274 7.18653 14.9689C7.83568 15.4103 8.57964 15.6927 9.3582 15.7931C10.1368 15.8936 10.928 15.8093 11.668 15.5471C12.6522 15.2191 13.5062 14.5856 14.1057 13.7388C14.7051 12.8921 15.0189 11.8761 15.0013 10.8388V4.17214H13.3346V11.0138Z"/></svg>',
  orderedList:
    '<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M2.08203 13.3346H3.7487V13.7513H2.91536V14.5846H3.7487V15.0013H2.08203V15.8346H4.58203V12.5013H2.08203V13.3346ZM2.91536 7.5013H3.7487V4.16797H2.08203V5.0013H2.91536V7.5013ZM2.08203 9.16797H3.58203L2.08203 10.918V11.668H4.58203V10.8346H3.08203L4.58203 9.08464V8.33464H2.08203V9.16797ZM6.2487 5.0013V6.66797H17.9154V5.0013H6.2487ZM6.2487 15.0013H17.9154V13.3346H6.2487V15.0013ZM6.2487 10.8346H17.9154V9.16797H6.2487V10.8346Z"/></svg>',
  markdown:
    '<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M18.125 3.75H1.875C1.54348 3.75 1.22554 3.8817 0.991117 4.11612C0.756696 4.35054 0.625 4.66848 0.625 5V15C0.625 15.3315 0.756696 15.6495 0.991117 15.8839C1.22554 16.1183 1.54348 16.25 1.875 16.25H18.125C18.4565 16.25 18.7745 16.1183 19.0089 15.8839C19.2433 15.6495 19.375 15.3315 19.375 15V5C19.375 4.66848 19.2433 4.35054 19.0089 4.11612C18.7745 3.8817 18.4565 3.75 18.125 3.75ZM18.125 15H1.875V5H18.125V15ZM10 8.125V11.875C10 12.0408 9.93415 12.1997 9.81694 12.3169C9.69973 12.4342 9.54076 12.5 9.375 12.5C9.20924 12.5 9.05027 12.4342 8.93306 12.3169C8.81585 12.1997 8.75 12.0408 8.75 11.875V9.63359L7.31719 11.0672C7.25914 11.1253 7.19021 11.1714 7.11434 11.2029C7.03846 11.2343 6.95713 11.2505 6.875 11.2505C6.79287 11.2505 6.71154 11.2343 6.63566 11.2029C6.55979 11.1714 6.49086 11.1253 6.43281 11.0672L5 9.63359V11.875C5 12.0408 4.93415 12.1997 4.81694 12.3169C4.69973 12.4342 4.54076 12.5 4.375 12.5C4.20924 12.5 4.05027 12.4342 3.93306 12.3169C3.81585 12.1997 3.75 12.0408 3.75 11.875V8.125C3.7499 8.00132 3.78651 7.88038 3.85517 7.77751C3.92384 7.67464 4.02149 7.59446 4.13576 7.54711C4.25002 7.49977 4.37576 7.48739 4.49707 7.51154C4.61837 7.5357 4.72978 7.59531 4.81719 7.68281L6.875 9.74141L8.93281 7.68281C9.02022 7.59531 9.13163 7.5357 9.25293 7.51154C9.37424 7.48739 9.49998 7.49977 9.61424 7.54711C9.72851 7.59446 9.82616 7.67464 9.89483 7.77751C9.96349 7.88038 10.0001 8.00132 10 8.125ZM16.0672 9.55781C16.1253 9.61586 16.1714 9.68479 16.2029 9.76066C16.2343 9.83654 16.2505 9.91787 16.2505 10C16.2505 10.0821 16.2343 10.1635 16.2029 10.2393C16.1714 10.3152 16.1253 10.3841 16.0672 10.4422L14.1922 12.3172C14.1341 12.3753 14.0652 12.4214 13.9893 12.4529C13.9135 12.4843 13.8321 12.5005 13.75 12.5005C13.6679 12.5005 13.5865 12.4843 13.5107 12.4529C13.4348 12.4214 13.3659 12.3753 13.3078 12.3172L11.4328 10.4422C11.3155 10.3249 11.2497 10.1659 11.2497 10C11.2497 9.83415 11.3155 9.67509 11.4328 9.55781C11.5501 9.44054 11.7091 9.37465 11.875 9.37465C12.0409 9.37465 12.1999 9.44054 12.3172 9.55781L13.125 10.3664V8.125C13.125 7.95924 13.1908 7.80027 13.3081 7.68306C13.4253 7.56585 13.5842 7.5 13.75 7.5C13.9158 7.5 14.0747 7.56585 14.1919 7.68306C14.3092 7.80027 14.375 7.95924 14.375 8.125V10.3664L15.1828 9.55781C15.2409 9.4997 15.3098 9.4536 15.3857 9.42215C15.4615 9.3907 15.5429 9.37451 15.625 9.37451C15.7071 9.37451 15.7885 9.3907 15.8643 9.42215C15.9402 9.4536 16.0091 9.4997 16.0672 9.55781Z"/></svg>',
};


const buildTableGridPicker = (onSelect) => {
  const MAX = 6;
  const popup = document.createElement("div");
  popup.className = "wysiwyg-table-grid";
  popup.style.display = "none";

  const label = document.createElement("div");
  label.className = "wysiwyg-table-grid__label";
  label.textContent = "Insert table";
  popup.appendChild(label);

  const grid = document.createElement("div");
  grid.className = "wysiwyg-table-grid__cells";
  popup.appendChild(grid);

  const cells = [];
  for (let r = 0; r < MAX; r++) {
    for (let c = 0; c < MAX; c++) {
      const cell = document.createElement("span");
      cell.className = "wysiwyg-table-grid__cell";
      cell.dataset.row = r + 1;
      cell.dataset.col = c + 1;
      grid.appendChild(cell);
      cells.push(cell);
    }
  }

  const highlight = (hoverR, hoverC) => {
    cells.forEach((cell) => {
      const r = parseInt(cell.dataset.row);
      const c = parseInt(cell.dataset.col);
      cell.classList.toggle("wysiwyg-table-grid__cell--active", r <= hoverR && c <= hoverC);
    });
    label.textContent = `${hoverR} \u00d7 ${hoverC} table`;
  };

  grid.addEventListener("mouseover", (e) => {
    const cell = e.target.closest(".wysiwyg-table-grid__cell");
    if (cell) highlight(parseInt(cell.dataset.row), parseInt(cell.dataset.col));
  });

  grid.addEventListener("mouseleave", () => {
    cells.forEach((c) => c.classList.remove("wysiwyg-table-grid__cell--active"));
    label.textContent = "Insert table";
  });

  grid.addEventListener("click", (e) => {
    const cell = e.target.closest(".wysiwyg-table-grid__cell");
    if (cell) onSelect(parseInt(cell.dataset.row), parseInt(cell.dataset.col));
  });

  return popup;
};

const setupTableContextBar = (editor, toolbarEl) => {
  const bar = document.createElement("div");
  bar.className = "wysiwyg-table-context";
  bar.style.display = "none";
  toolbarEl.after(bar);

  const actions = [
    { label: "Add row above", icon: "↑ Row", cmd: () => editor.chain().focus().addRowBefore().run() },
    { label: "Add row below", icon: "↓ Row", cmd: () => editor.chain().focus().addRowAfter().run() },
    { label: "Delete row", icon: "✕ Row", cmd: () => editor.chain().focus().deleteRow().run(), danger: true },
    "sep",
    { label: "Add column before", icon: "← Col", cmd: () => editor.chain().focus().addColumnBefore().run() },
    { label: "Add column after", icon: "→ Col", cmd: () => editor.chain().focus().addColumnAfter().run() },
    { label: "Delete column", icon: "✕ Col", cmd: () => editor.chain().focus().deleteColumn().run(), danger: true },
    "sep",
    { label: "Merge cells", icon: "Merge", cmd: () => editor.chain().focus().mergeCells().run() },
    { label: "Split cell", icon: "Split", cmd: () => editor.chain().focus().splitCell().run() },
    "sep",
    { label: "Delete table", icon: "Delete table", cmd: () => editor.chain().focus().deleteTable().run(), danger: true },
  ];

  actions.forEach((a) => {
    if (a === "sep") {
      bar.appendChild(createSeparator());
      return;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "wysiwyg-table-context__btn" + (a.danger ? " wysiwyg-table-context__btn--danger" : "");
    btn.setAttribute("aria-label", a.label);
    btn.setAttribute("title", a.label);
    btn.textContent = a.icon;
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      a.cmd();
    });
    bar.appendChild(btn);
  });

  const update = () => {
    bar.style.display = editor.isActive("table") ? "" : "none";
  };
  editor.on("selectionUpdate", update);
  editor.on("transaction", update);
  update();

  return bar;
};

/*
Toolbar layouts keyed by preset name. Each entry lists the registry keys to
render, in order, into the left and right groups. Pass a preset to buildToolbar
(driven by the `data-wysiwyg-preset` attribute, see initWysiwyg). Unknown preset
names fall back to "full".
*/
const TOOLBAR_PRESETS = {
  full: {
    left: [
      "heading", "bold", "italic", "underline", "strike", "separator",
      "bulletList", "orderedList", "taskList", "separator",
      "link", "image", "blockquote", "horizontalRule", "table", "separator",
      "code", "codeBlock", "langSelect", "separator", "markdown",
    ],
    right: ["preview", "undo", "redo"],
  },
  minimal: {
    left: [
      "bold", "italic", "underline", "separator",
      "bulletList", "orderedList", "separator",
      "link", "markdown",
    ],
    right: ["preview", "undo", "redo"],
  },
  /*
  Biography editor preset: bold, italic, underline, ordered list, link, markdown
  on the left; undo / redo on the right. No separators or bullet list. Preview is
  retained for Markdown-mode preview functionality. The "bio" preset renders
  BIO_ICONS.
  */
  bio: {
    left: ["bold", "italic", "underline", "orderedList", "markdown"],
    right: ["preview", "undo", "redo"],
  },
};

const buildToolbar = (editor, toolbarEl, preset = "full") => {
  // Carries the image-upload endpoint and CSRF token (see _wysiwyg_editor.html).
  const wrapper = toolbarEl.closest('[data-wysiwyg="v3"]');
  const left = document.createElement("div");
  left.className = "wysiwyg-toolbar__left";
  const right = document.createElement("div");
  right.className = "wysiwyg-toolbar__right";

  // mdBtn/previewBtn are wired up by initWysiwyg; handleDocClick is only set
  // when the `table` tool is present and is removed in initWysiwyg's cleanup.
  const ctx = { mdBtn: null, previewBtn: null, handleDocClick: null };

  // The "bio" preset renders the dedicated bio icon set; other presets keep
  // their existing glyphs. `bioIcon` returns the bio SVG for bio, else `fallback`.
  const isBio = preset === "bio";
  const bioIcon = (key, fallback) => (isBio ? BIO_ICONS[key] : fallback);

  const builders = {
    separator: () => createSeparator(),
    heading: () => createHeadingDropdown(editor),
    bold: () => createToolbarButton(editor, {
      label: "Bold", title: "Bold", html: bioIcon("bold", "<strong>B</strong>"),
      onClick: () => editor.chain().focus().toggleBold().run(),
      isActive: () => editor.isActive("bold"),
    }),
    italic: () => createToolbarButton(editor, {
      label: "Italic", title: "Italic", html: bioIcon("italic", "<em>I</em>"),
      onClick: () => editor.chain().focus().toggleItalic().run(),
      isActive: () => editor.isActive("italic"),
    }),
    underline: () => createToolbarButton(editor, {
      label: "Underline", title: "Underline", html: bioIcon("underline", "<u>U</u>"),
      onClick: () => editor.chain().focus().toggleUnderline().run(),
      isActive: () => editor.isActive("underline"),
    }),
    strike: () => createToolbarButton(editor, {
      label: "Strikethrough", title: "Strikethrough", html: "<s>S</s>",
      onClick: () => editor.chain().focus().toggleStrike().run(),
      isActive: () => editor.isActive("strike"),
    }),
    bulletList: () => createToolbarButton(editor, {
      label: "Bullet list", title: "Bullet list", html: ICONS.bulletList,
      onClick: () => editor.chain().focus().toggleBulletList().run(),
      isActive: () => editor.isActive("bulletList"),
    }),
    orderedList: () => createToolbarButton(editor, {
      label: "Ordered list", title: "Ordered list", html: bioIcon("orderedList", ICONS.orderedList),
      onClick: () => editor.chain().focus().toggleOrderedList().run(),
      isActive: () => editor.isActive("orderedList"),
    }),
    taskList: () => createToolbarButton(editor, {
      label: "Checkbox", title: "Checkbox list", html: ICONS.checkbox,
      onClick: () => editor.chain().focus().toggleTaskList().run(),
      isActive: () => editor.isActive("taskList"),
    }),
    link: () => createToolbarButton(editor, {
      label: "Link", title: "Insert link", html: bioIcon("link", ICONS.link),
      onClick: async () => {
        const result = await openDialog({
          title: "Insert Link",
          fields: [
            { name: "url", label: "URL", type: "url", placeholder: "https://example.com" },
          ],
          onSubmit: ({ url }) => {
            if (!url) throw new Error("Enter a URL.");
            if (!isSafeUrl(url)) {
              throw new Error("Only http, https, and mailto URLs are allowed.");
            }
            return { href: url };
          },
        });
        if (result) editor.chain().focus().setLink(result).run();
      },
      isActive: () => editor.isActive("link"),
    }),
    image: () => createToolbarButton(editor, {
      label: "Image", title: "Insert image", html: ICONS.image,
      onClick: async () => {
        const result = await openDialog({
          title: "Insert Image",
          fields: [
            {
              name: "file",
              label: "Upload an image",
              type: "file",
              accept: IMAGE_UPLOAD_ACCEPT,
              help: "JPEG or PNG, up to 5 MB.",
            },
            {
              name: "url",
              label: "Or link to one",
              type: "url",
              placeholder: "https://example.com/image.png",
            },
            { name: "alt", label: "Alt text", type: "text", placeholder: "Image description" },
          ],
          onSubmit: async ({ file, url, alt }) => {
            if (file) return { src: await uploadEditorImage(file, wrapper), alt };
            if (!url) throw new Error("Choose an image to upload, or paste its URL.");
            if (!isSafeUrl(url)) throw new Error("Only http and https image URLs are allowed.");
            return { src: url, alt };
          },
        });
        if (result) editor.chain().focus().setImage(result).run();
      },
      isActive: () => false,
    }),
    blockquote: () => createToolbarButton(editor, {
      label: "Blockquote", title: "Blockquote", html: "&#8220;",
      onClick: () => editor.chain().focus().toggleBlockquote().run(),
      isActive: () => editor.isActive("blockquote"),
    }),
    horizontalRule: () => createToolbarButton(editor, {
      label: "Horizontal rule", title: "Horizontal rule", html: "&#8213;",
      onClick: () => editor.chain().focus().setHorizontalRule().run(),
      isActive: () => false,
    }),
    table: () => {
      const tableWrapper = document.createElement("span");
      tableWrapper.className = "wysiwyg-toolbar__table-wrap";
      const tableBtn = createToolbarButton(editor, {
        label: "Table", title: "Insert table", html: "&#9638;",
        onClick: () => {
          gridPopup.style.display = gridPopup.style.display === "none" ? "" : "none";
        },
        isActive: () => editor.isActive("table"),
      });
      const gridPopup = buildTableGridPicker((rows, cols) => {
        editor.chain().focus().insertTable({ rows, cols, withHeaderRow: true }).run();
        gridPopup.style.display = "none";
      });
      tableWrapper.appendChild(tableBtn);
      tableWrapper.appendChild(gridPopup);

      ctx.handleDocClick = (e) => {
        if (!tableWrapper.contains(e.target)) gridPopup.style.display = "none";
      };
      document.addEventListener("click", ctx.handleDocClick);
      return tableWrapper;
    },
    code: () => createToolbarButton(editor, {
      label: "Inline code", title: "Inline code", html: "&lt;/&gt;",
      onClick: () => editor.chain().focus().toggleCode().run(),
      isActive: () => editor.isActive("code"),
    }),
    codeBlock: () => createToolbarButton(editor, {
      label: "Code block", title: "Code block", html: "&#123;&#123;&#123;",
      onClick: () => editor.chain().focus().toggleCodeBlock({ language: DEFAULT_CODE_LANGUAGE }).run(),
      isActive: () => editor.isActive("codeBlock"),
    }),
    langSelect: () => {
      const langSelect = document.createElement("select");
      langSelect.className = "wysiwyg-toolbar__lang-select";
      langSelect.setAttribute("aria-label", "Code block language");
      langSelect.setAttribute("title", "Code block language");
      CODE_LANGUAGES.forEach(({ value, label }) => {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = label;
        langSelect.appendChild(opt);
      });
      const updateLangSelect = () => {
        const inCodeBlock = editor.isActive("codeBlock");
        langSelect.disabled = !inCodeBlock;
        if (inCodeBlock) {
          const attrs = editor.getAttributes("codeBlock");
          const lang = attrs.language || DEFAULT_CODE_LANGUAGE;
          langSelect.value = CODE_LANGUAGES.some((l) => l.value === lang) ? lang : DEFAULT_CODE_LANGUAGE;
        }
      };
      langSelect.addEventListener("change", () => {
        editor.chain().focus().updateAttributes("codeBlock", { language: langSelect.value }).run();
      });
      editor.on("selectionUpdate", updateLangSelect);
      editor.on("transaction", updateLangSelect);
      updateLangSelect();
      return langSelect;
    },
    markdown: () => {
      const mdBtn = document.createElement("button");
      mdBtn.type = "button";
      mdBtn.className = "wysiwyg-toolbar__btn wysiwyg-toolbar__btn--md";
      mdBtn.setAttribute("aria-label", "Markdown");
      mdBtn.setAttribute("title", "Toggle Markdown mode");
      mdBtn.innerHTML = bioIcon("markdown", ICONS.markdown);
      ctx.mdBtn = mdBtn;
      return mdBtn;
    },
    preview: () => {
      const previewBtn = document.createElement("button");
      previewBtn.type = "button";
      previewBtn.className = "wysiwyg-toolbar__btn wysiwyg-toolbar__btn--preview-toggle";
      previewBtn.setAttribute("aria-label", "Preview");
      previewBtn.setAttribute("title", "Toggle preview");
      previewBtn.innerHTML = ICONS.preview;
      previewBtn.style.display = "none";
      ctx.previewBtn = previewBtn;
      return previewBtn;
    },
    undo: () => createToolbarButton(editor, {
      label: "Undo", title: "Undo", html: ICONS.undo,
      onClick: () => editor.chain().focus().undo().run(),
      isActive: () => false,
      // Grey out when there is no history to undo.
      isDisabled: () => !editor.can().undo(),
    }),
    redo: () => createToolbarButton(editor, {
      label: "Redo", title: "Redo", html: ICONS.redo,
      onClick: () => editor.chain().focus().redo().run(),
      isActive: () => false,
      isDisabled: () => !editor.can().redo(),
    }),
  };

  const layout = TOOLBAR_PRESETS[preset] || TOOLBAR_PRESETS.full;
  layout.left.forEach((name) => {
    const el = builders[name]?.();
    if (el) left.appendChild(el);
  });
  layout.right.forEach((name) => {
    const el = builders[name]?.();
    if (el) right.appendChild(el);
  });

  toolbarEl.appendChild(left);
  toolbarEl.appendChild(right);

  return { mdBtn: ctx.mdBtn, previewBtn: ctx.previewBtn, handleDocClick: ctx.handleDocClick };
};

/*
Render `diagram` into `container` as an SVG, or as an inline error message.

Both outcomes stay inside the container the caller owns. That matters for the
editor, where the alternative — mermaid's own error rendering — escapes to the
end of <body>; see the suppressErrorRendering note in getMermaid.
*/
const renderDiagram = async (container, diagram) => {
  try {
    const mermaid = await getMermaid();
    const { svg } = await mermaid.render(`mermaid-${++mermaidIdCounter}`, diagram);
    container.classList.remove("mermaid-preview--error");
    container.replaceChildren(sanitizeSvg(svg));
  } catch (err) {
    const message = document.createElement("span");
    message.className = "mermaid-error";
    message.textContent = err?.message || "Invalid diagram";
    container.classList.add("mermaid-preview--error");
    container.replaceChildren(message);
  }
};

// Long enough that a diagram is not re-parsed on every keystroke, short enough
// that the preview follows the typing.
const MERMAID_RENDER_DELAY_MS = 400;

/*
Render `diagram` into `container`, unless the editor has moved on by then.

Every edit inside a mermaid code block replaces the whole preview widget (its
decoration is keyed by the diagram source), so a superseded container is
detached before this fires and its render is skipped — which is what keeps
typing a diagram from parsing a half-written one on every keystroke.
*/
const scheduleDiagram = (container, diagram) => {
  setTimeout(() => {
    if (container.isConnected) renderDiagram(container, diagram);
  }, MERMAID_RENDER_DELAY_MS);
};

const mermaidPreviewKey = new PluginKey("mermaidPreview");

/*
One preview per mermaid code block, as a ProseMirror widget decoration keyed by
the diagram source.

Widgets rather than plain DOM appended after the <pre>: ProseMirror owns
everything inside the editable area and reconciles away nodes it doesn't know
about, so an injected preview is wiped on the next transaction. The `key` makes
ProseMirror reuse the existing widget while the source is unchanged, so typing
elsewhere in the document doesn't re-render every diagram.
*/
const mermaidDecorations = (doc) => {
  const decorations = [];
  doc.descendants((node, pos) => {
    if (node.type.name !== "codeBlock" || node.attrs.language !== "mermaid") return;
    const diagram = node.textContent.trim();
    if (!diagram) return;
    decorations.push(
      Decoration.widget(
        pos + node.nodeSize,
        () => {
          const container = document.createElement("div");
          container.className = "mermaid-preview";
          container.contentEditable = "false";
          scheduleDiagram(container, diagram);
          return container;
        },
        { key: `mermaid:${diagram}`, side: 1 },
      ),
    );
  });
  return DecorationSet.create(doc, decorations);
};

export const MermaidPreview = Extension.create({
  name: "mermaidPreview",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: mermaidPreviewKey,
        state: {
          init: (_, { doc }) => mermaidDecorations(doc),
          apply: (tr, previous) =>
            tr.docChanged ? mermaidDecorations(tr.doc) : previous,
        },
        props: {
          decorations(state) {
            return mermaidPreviewKey.getState(state);
          },
        },
      }),
    ];
  },
});

export const highlightPreviewCodeBlocks = (container) => {
  container.querySelectorAll("pre code[class*='language-']").forEach((codeEl) => {
    const match = codeEl.className.match(/language-\{?(\w+)\}?/);
    if (!match) return;
    const lang = match[1];
    if (lang === "mermaid") return;
    const text = codeEl.textContent;
    try {
      const tree = lowlight.highlight(lang, text);
      codeEl.innerHTML = toHtml(tree);
    } catch (_) {}
  });
};

export const renderMermaidPreview = async (container) => {
  const mermaidCodes = container.querySelectorAll("code.language-mermaid");
  for (const codeEl of mermaidCodes) {
    const pre = codeEl.parentElement;
    if (!pre || pre.tagName !== "PRE") continue;
    const diagram = codeEl.textContent.trim();
    if (!diagram) continue;

    const div = document.createElement("div");
    div.className = "mermaid-preview";
    pre.replaceWith(div);
    await renderDiagram(div, diagram);
  }
};

const editorInstances = new Map();

export const initWysiwyg = (textareaId) => {
  const prev = editorInstances.get(textareaId);
  if (prev) {
    prev.editor.destroy();
    prev.cleanup();
    editorInstances.delete(textareaId);
  }

  const textarea = document.getElementById(textareaId);
  if (!textarea) return null;
  const wrapper = textarea.closest('[data-wysiwyg="v3"]');
  if (!wrapper) return null;

  const toolbarEl = wrapper.querySelector(".wysiwyg-editor__toolbar");
  const editorEl = wrapper.querySelector(".wysiwyg-editor__body");
  if (!toolbarEl || !editorEl) return null;

  const preset = wrapper.dataset.wysiwygPreset || "full";
  const maxlength = Number(wrapper.dataset.wysiwygMaxlength) || 0;

  // Live length of the serialized markdown; kept current by dispatchState.
  let markdownLength = 0;
  // Block edits that grow the doc once the markdown is at/over the limit.
  const MarkdownLengthLimit = Extension.create({
    name: "markdownLengthLimit",
    addProseMirrorPlugins() {
      return [
        new Plugin({
          filterTransaction(tr) {
            if (!tr.docChanged) return true;
            const grew = tr.doc.content.size > tr.before.content.size;
            return !(grew && markdownLength >= maxlength);
          },
        }),
      ];
    },
  });

  /* Ensure toolbar is empty and remove any previous table-context bar after re-init (e.g. Fill demo content) to avoid duplicate bars */
  toolbarEl.innerHTML = "";
  wrapper.querySelectorAll(".wysiwyg-table-context").forEach((el) => el.remove());

  const rawContent = textarea.value ? textarea.value.trim() : "";
  const isHtml = rawContent.startsWith("<") && rawContent.includes(">");
  let initialContent = rawContent;
  if (initialContent && !isHtml) {
    try {
      initialContent = parseMarkdownSafe(initialContent);
    } catch (_) {
      initialContent = rawContent;
    }
  }

  const editorRef = { current: null };
  const editor = new Editor({
    element: editorEl,
    extensions: [
      StarterKit.configure({ codeBlock: false }),
      CodeBlockLowlight.configure({
        lowlight,
        defaultLanguage: DEFAULT_CODE_LANGUAGE,
      }),
      Underline,
      Link.configure({ openOnClick: false, HTMLAttributes: { target: "_blank", rel: "noopener" } }),
      Table.configure({ resizable: false }),
      TableRow,
      TableCell,
      TableHeader,
      Image,
      TaskList,
      TaskItem.configure({ nested: true }),
      MermaidPreview,
      ...(maxlength ? [MarkdownLengthLimit] : []),
    ],
    content: initialContent,
    editorProps: {
      attributes: {
        class: "wysiwyg-editor__prose",
      },
      handleKeyDown(view, event) {
        if (event.key === "Tab") {
          const { $from } = view.state.selection;
          if ($from.parent.type.name === "codeBlock") {
            event.preventDefault();
            editorRef.current?.chain().focus().insertContent("\t").run();
            return true;
          }
        }
        return false;
      },
      handlePaste(_view, event) {
        const pastedText = event.clipboardData?.getData("text/plain") || "";
        if (!pastedText.trim() || !editorRef.current) return false;

        // Clamp pasted text to the remaining character budget, mirroring the
        // native <input maxlength> truncation used elsewhere (e.g. Tagline).
        let textToInsert = pastedText;
        if (maxlength) {
          const remaining = maxlength - markdownLength;
          if (remaining <= 0) {
            event.preventDefault();
            return true;
          }
          if (pastedText.length > remaining) {
            textToInsert = pastedText.slice(0, remaining);
          }
        }

        const trimmed = textToInsert.trim();
        const looksLikeMarkdown =
          (!trimmed.startsWith("<") &&
            (/^#|^\*\*|^\- |^\d+\. |^`|^\[|^>|^\||^\- \[ \]|^\- \[x\]/i.test(trimmed) ||
              /\n```|\n#{1,6}\s|\n\*\*|\n\- |\n\d+\. |\n\|---|\n\- \[ \]/.test(textToInsert)));
        if (looksLikeMarkdown) {
          try {
            event.preventDefault();
            const html = parseMarkdownSafe(textToInsert);
            editorRef.current.chain().focus().insertContent(html).run();
            return true;
          } catch (_) {
            return false;
          }
        }
        if (textToInsert !== pastedText) {
          event.preventDefault();
          editorRef.current.chain().focus().insertContent(textToInsert).run();
          return true;
        }
        return false;
      },
    },
  });
  editorRef.current = editor;

  const state = { mode: "wysiwyg", markdownText: "", previewOn: false };

  const { mdBtn, previewBtn, handleDocClick } = buildToolbar(editor, toolbarEl, preset);
  setupTableContextBar(editor, toolbarEl);

  const markdownPane = document.createElement("div");
  markdownPane.className = "wysiwyg-editor__markdown-pane";
  markdownPane.style.display = "none";

  const mdTextarea = document.createElement("textarea");
  mdTextarea.className = "wysiwyg-markdown__textarea";
  mdTextarea.setAttribute("aria-label", "Markdown source");
  mdTextarea.setAttribute("placeholder", "Write markdown here...");

  const mdPreview = document.createElement("div");
  mdPreview.className = "wysiwyg-markdown__preview wysiwyg-editor__prose";

  markdownPane.appendChild(mdTextarea);
  markdownPane.appendChild(mdPreview);
  editorEl.after(markdownPane);

  const previewEl = document.createElement("div");
  previewEl.className = "wysiwyg-editor__preview wysiwyg-editor__prose";
  previewEl.style.display = "none";
  markdownPane.after(previewEl);

  const updateMdPreview = () => {
    mdPreview.innerHTML = parseMarkdownSafe(state.markdownText);
    highlightPreviewCodeBlocks(mdPreview);
    renderMermaidPreview(mdPreview);
  };
  const debouncedMdPreview = debounce(updateMdPreview, 300);

  mdTextarea.addEventListener("input", () => {
    state.markdownText = mdTextarea.value;
    debouncedMdPreview();
  });

  mdBtn.addEventListener("click", (e) => {
    e.preventDefault();
    if (state.mode === "wysiwyg") {
      state.markdownText = turndown.turndown(editor.getHTML());
      state.mode = "markdown";
      state.previewOn = false;
      mdBtn.classList.add("wysiwyg-toolbar__btn--active");
      toolbarEl.classList.add("wysiwyg-editor__toolbar--markdown");
      editorEl.style.display = "none";
      markdownPane.style.display = "";
      previewEl.style.display = "none";
      previewBtn.style.display = "";
      previewBtn.classList.remove("wysiwyg-toolbar__btn--active");
      mdTextarea.value = state.markdownText;
      updateMdPreview();
      mdTextarea.focus();
    } else {
      editor.commands.setContent(parseMarkdownSafe(state.markdownText));
      state.mode = "wysiwyg";
      state.previewOn = false;
      mdBtn.classList.remove("wysiwyg-toolbar__btn--active");
      toolbarEl.classList.remove("wysiwyg-editor__toolbar--markdown");
      editorEl.style.display = "";
      markdownPane.style.display = "none";
      previewEl.style.display = "none";
      previewBtn.style.display = "none";
      previewBtn.classList.remove("wysiwyg-toolbar__btn--active");
    }
  });

  previewBtn.addEventListener("click", (e) => {
    e.preventDefault();
    state.previewOn = !state.previewOn;
    previewBtn.classList.toggle("wysiwyg-toolbar__btn--active", state.previewOn);
    if (state.previewOn) {
      markdownPane.style.display = "none";
      previewEl.style.display = "";
      previewEl.innerHTML = parseMarkdownSafe(state.markdownText);
      highlightPreviewCodeBlocks(previewEl);
      renderMermaidPreview(previewEl);
    } else {
      markdownPane.style.display = "";
      previewEl.style.display = "none";
    }
  });

  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  textarea.style.width = "1px";
  textarea.style.height = "1px";
  textarea.setAttribute("aria-hidden", "true");
  textarea.tabIndex = -1;

  const form = wrapper.closest("form");
  const syncTextarea = () => {
    if (state.mode === "markdown") {
      textarea.value = state.markdownText;
    } else {
      textarea.value = turndown.turndown(editor.getHTML());
    }
  };
  if (form) {
    form.addEventListener("submit", syncTextarea, true);
  }

  // ── Bridge to the host page (e.g. the create-post / profile-edit Alpine form) ──
  // Emit content + plain-text char count on every change so the page can drive
  // a char counter, a Saving/Saved indicator, and localStorage persistence.
  // `programmatic: true` flags updates the user didn't make (initial load /
  // restore) so the page can skip the "Saving" animation and not re-persist.
  const currentValue = () =>
    state.mode === "markdown"
      ? state.markdownText
      : turndown.turndown(editor.getHTML());
  const dispatchState = (programmatic) => {
    // `characters` = visible text; `markdownCharacters` = the stored/validated markdown.
    const value = currentValue();
    markdownLength = value.length;
    editorEl.dispatchEvent(
      new CustomEvent("wysiwyg-update", {
        detail: {
          id: textareaId,
          characters: editor.state.doc.textContent.length,
          markdownCharacters: value.length,
          value,
          programmatic: !!programmatic,
        },
        bubbles: true,
      }),
    );
  };
  editor.on("update", () => dispatchState(false));

  // Let the host push a saved draft back into the editor (restore).
  const onSetContent = (e) => {
    if (!e.detail || e.detail.id !== textareaId) return;
    const md = e.detail.value || "";
    editor.commands.setContent(md ? parseMarkdownSafe(md) : "");
    dispatchState(true);
  };
  window.addEventListener("wysiwyg-set-content", onSetContent);

  // Initial state (deferred a frame so the host's listener is attached).
  dispatchState(true);
  requestAnimationFrame(() => dispatchState(true));

  editorInstances.set(textareaId, {
    editor,
    cleanup: () => {
      if (handleDocClick) document.removeEventListener("click", handleDocClick);
      if (form) form.removeEventListener("submit", syncTextarea, true);
      window.removeEventListener("wysiwyg-set-content", onSetContent);
    },
  });
  return editor;
};

const autoInit = (elId) => {
  if (typeof document === "undefined" || !document.querySelector) return;
  if (elId && elId !== null) {
    const ta = document.querySelector(`textarea[id=${elId}]`);
    if (ta && ta.id) initWysiwyg(ta.id);
  }
  else {
    document.querySelectorAll('[data-wysiwyg="v3"]').forEach((wrapper) => {
      const ta = wrapper.querySelector("textarea[id]");
      if (ta && ta.id) initWysiwyg(ta.id);
    });
  }
};

if (typeof document !== "undefined") {
  window.autoInit = autoInit
  // Handshake for pages whose Alpine components initialize before this module
  // finishes loading (deferred script, cold cache): they wait for this event
  // instead of calling window.autoInit directly.
  window.dispatchEvent(new CustomEvent("wysiwyg-editor-ready"))
}
