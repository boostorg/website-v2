
import { Editor } from "@tiptap/core";
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

function parseMarkdownSafe(md) {
  return DOMPurify.sanitize(marked.parse(md));
}

function sanitizeSvg(svgString) {
  return DOMPurify.sanitize(svgString, { USE_PROFILES: { svg: true, svgFilters: true }, ADD_TAGS: ["use"] });
}

const lowlight = createLowlight(common);

const CODE_LANGUAGES = [
  { value: "cpp", label: "C++" },
  { value: "python", label: "Python" },
  { value: "mermaid", label: "Mermaid" },
];
const DEFAULT_CODE_LANGUAGE = "cpp";


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


const isSafeUrl = (url) => {
  try {
    const parsed = new URL(url, window.location.href);
    return ["http:", "https:", "mailto:"].includes(parsed.protocol);
  } catch {
    return false;
  }
};

const openModal = (title, fields) =>
  new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "wysiwyg-modal__overlay";

    const modal = document.createElement("div");
    modal.className = "wysiwyg-modal";

    const heading = document.createElement("h3");
    heading.className = "wysiwyg-modal__title";
    heading.textContent = title;
    modal.appendChild(heading);

    const inputs = {};
    fields.forEach(({ name, label, type, placeholder }) => {
      const lbl = document.createElement("label");
      lbl.className = "wysiwyg-modal__label";
      lbl.textContent = label;
      modal.appendChild(lbl);

      const input = document.createElement("input");
      input.type = type || "text";
      input.className = "wysiwyg-modal__input";
      if (placeholder) input.placeholder = placeholder;
      modal.appendChild(input);
      inputs[name] = input;
    });

    const actions = document.createElement("div");
    actions.className = "wysiwyg-modal__actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "wysiwyg-modal__btn wysiwyg-modal__btn--cancel";
    cancelBtn.textContent = "Cancel";

    const insertBtn = document.createElement("button");
    insertBtn.type = "button";
    insertBtn.className = "wysiwyg-modal__btn wysiwyg-modal__btn--insert";
    insertBtn.textContent = "Insert";

    actions.appendChild(cancelBtn);
    actions.appendChild(insertBtn);
    modal.appendChild(actions);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const firstInput = Object.values(inputs)[0];
    if (firstInput) requestAnimationFrame(() => firstInput.focus());

    const close = (result) => {
      overlay.remove();
      resolve(result);
    };

    cancelBtn.addEventListener("click", () => close(null));
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close(null);
    });
    insertBtn.addEventListener("click", () => {
      const result = {};
      for (const [k, v] of Object.entries(inputs)) result[k] = v.value;
      close(result);
    });
    modal.addEventListener("keydown", (e) => {
      if (e.key === "Enter") insertBtn.click();
      if (e.key === "Escape") close(null);
    });
  });

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
  mermaidModule.initialize({ startOnLoad: false, theme: "default" });
  return mermaidModule;
};

const debounce = (fn, ms) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
};

const createToolbarButton = (editor, opts) => {
  const { label, onClick, isActive, title } = opts;
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

const ICONS = {
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

const buildToolbar = (editor, toolbarEl) => {
  const left = document.createElement("div");
  left.className = "wysiwyg-toolbar__left";
  const right = document.createElement("div");
  right.className = "wysiwyg-toolbar__right";

  left.appendChild(createHeadingDropdown(editor));

  left.appendChild(
    createToolbarButton(editor, {
      label: "Bold", title: "Bold", html: "<strong>B</strong>",
      onClick: () => editor.chain().focus().toggleBold().run(),
      isActive: () => editor.isActive("bold"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Italic", title: "Italic", html: "<em>I</em>",
      onClick: () => editor.chain().focus().toggleItalic().run(),
      isActive: () => editor.isActive("italic"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Underline", title: "Underline", html: "<u>U</u>",
      onClick: () => editor.chain().focus().toggleUnderline().run(),
      isActive: () => editor.isActive("underline"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Strikethrough", title: "Strikethrough", html: "<s>S</s>",
      onClick: () => editor.chain().focus().toggleStrike().run(),
      isActive: () => editor.isActive("strike"),
    })
  );

  left.appendChild(createSeparator());

  left.appendChild(
    createToolbarButton(editor, {
      label: "Bullet list", title: "Bullet list", html: ICONS.bulletList,
      onClick: () => editor.chain().focus().toggleBulletList().run(),
      isActive: () => editor.isActive("bulletList"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Ordered list", title: "Ordered list", html: ICONS.orderedList,
      onClick: () => editor.chain().focus().toggleOrderedList().run(),
      isActive: () => editor.isActive("orderedList"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Checkbox", title: "Checkbox list", html: ICONS.checkbox,
      onClick: () => editor.chain().focus().toggleTaskList().run(),
      isActive: () => editor.isActive("taskList"),
    })
  );

  left.appendChild(createSeparator());

  left.appendChild(
    createToolbarButton(editor, {
      label: "Link", title: "Insert link", html: ICONS.link,
      onClick: async () => {
        const result = await openModal("Insert Link", [
          { name: "url", label: "URL", type: "url", placeholder: "https://example.com" },
        ]);
        if (!result || !result.url) return;
        if (!isSafeUrl(result.url)) {
          window.alert("Only http, https, and mailto URLs are allowed.");
          return;
        }
        editor.chain().focus().setLink({ href: result.url }).run();
      },
      isActive: () => editor.isActive("link"),
    })
  );

  left.appendChild(
    createToolbarButton(editor, {
      label: "Image", title: "Insert image", html: ICONS.image,
      onClick: async () => {
        const result = await openModal("Insert Image", [
          { name: "url", label: "Image URL", type: "url", placeholder: "https://example.com/image.png" },
          { name: "alt", label: "Alt text", type: "text", placeholder: "Image description" },
        ]);
        if (!result || !result.url) return;
        if (!isSafeUrl(result.url)) {
          window.alert("Only http, https, and mailto URLs are allowed.");
          return;
        }
        editor.chain().focus().setImage({ src: result.url, alt: result.alt || "" }).run();
      },
      isActive: () => false,
    })
  );

  left.appendChild(
    createToolbarButton(editor, {
      label: "Blockquote", title: "Blockquote", html: "&#8220;",
      onClick: () => editor.chain().focus().toggleBlockquote().run(),
      isActive: () => editor.isActive("blockquote"),
    })
  );

  left.appendChild(
    createToolbarButton(editor, {
      label: "Horizontal rule", title: "Horizontal rule", html: "&#8213;",
      onClick: () => editor.chain().focus().setHorizontalRule().run(),
      isActive: () => false,
    })
  );

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
  left.appendChild(tableWrapper);

  const handleDocClick = (e) => {
    if (!tableWrapper.contains(e.target)) gridPopup.style.display = "none";
  };
  document.addEventListener("click", handleDocClick);

  left.appendChild(createSeparator());

  left.appendChild(
    createToolbarButton(editor, {
      label: "Inline code", title: "Inline code", html: "&lt;/&gt;",
      onClick: () => editor.chain().focus().toggleCode().run(),
      isActive: () => editor.isActive("code"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Code block", title: "Code block", html: "&#123;&#123;&#123;",
      onClick: () => editor.chain().focus().toggleCodeBlock({ language: DEFAULT_CODE_LANGUAGE }).run(),
      isActive: () => editor.isActive("codeBlock"),
    })
  );

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
  left.appendChild(langSelect);

  left.appendChild(createSeparator());

  const mdBtn = document.createElement("button");
  mdBtn.type = "button";
  mdBtn.className = "wysiwyg-toolbar__btn wysiwyg-toolbar__btn--md";
  mdBtn.setAttribute("aria-label", "Markdown");
  mdBtn.setAttribute("title", "Toggle Markdown mode");
  mdBtn.innerHTML = ICONS.markdown;
  left.appendChild(mdBtn);

  const previewBtn = document.createElement("button");
  previewBtn.type = "button";
  previewBtn.className = "wysiwyg-toolbar__btn wysiwyg-toolbar__btn--preview-toggle";
  previewBtn.setAttribute("aria-label", "Preview");
  previewBtn.setAttribute("title", "Toggle preview");
  previewBtn.innerHTML = ICONS.preview;
  previewBtn.style.display = "none";

  right.appendChild(previewBtn);
  right.appendChild(
    createToolbarButton(editor, {
      label: "Undo", title: "Undo", html: "&#8630;",
      onClick: () => editor.chain().focus().undo().run(),
      isActive: () => false,
    })
  );
  right.appendChild(
    createToolbarButton(editor, {
      label: "Redo", title: "Redo", html: "&#8631;",
      onClick: () => editor.chain().focus().redo().run(),
      isActive: () => false,
    })
  );

  toolbarEl.appendChild(left);
  toolbarEl.appendChild(right);

  return { mdBtn, previewBtn, handleDocClick };
};

const setupMermaidEditMode = (editor, editorEl) => {
  const renderMermaid = debounce(async () => {
    const pres = editorEl.querySelectorAll("pre");
    const activePreviews = new Set();

    for (const pre of pres) {
      const code = pre.querySelector("code");
      if (!code || !code.classList.contains("language-mermaid")) continue;

      let preview = pre.nextElementSibling;
      if (!preview || !preview.classList.contains("mermaid-preview")) {
        preview = document.createElement("div");
        preview.className = "mermaid-preview";
        pre.after(preview);
      }
      activePreviews.add(preview);

      const diagram = code.textContent.trim();
      if (!diagram) {
        preview.innerHTML = "";
        continue;
      }

      try {
        const mermaid = await getMermaid();
        const id = `mermaid-edit-${++mermaidIdCounter}`;
        const { svg } = await mermaid.render(id, diagram);
        preview.innerHTML = sanitizeSvg(svg);
        preview.classList.remove("mermaid-error");
      } catch (err) {
        const errSpan = document.createElement("span");
        errSpan.className = "mermaid-error";
        errSpan.textContent = err.message || "Invalid diagram";
        preview.innerHTML = "";
        preview.appendChild(errSpan);
        preview.classList.add("mermaid-error");
      }
    }

    editorEl.querySelectorAll(".mermaid-preview").forEach((el) => {
      if (!activePreviews.has(el)) el.remove();
    });
  }, 500);

  editor.on("update", renderMermaid);
  renderMermaid();
};

const highlightPreviewCodeBlocks = (container) => {
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

const renderMermaidPreview = async (container) => {
  const mermaidCodes = container.querySelectorAll("code.language-mermaid");
  if (mermaidCodes.length === 0) return;

  const mermaid = await getMermaid();
  for (const codeEl of mermaidCodes) {
    const pre = codeEl.parentElement;
    if (!pre || pre.tagName !== "PRE") continue;
    const diagram = codeEl.textContent.trim();
    if (!diagram) continue;

    const div = document.createElement("div");
    div.className = "mermaid-preview";
    try {
      const id = `mermaid-preview-${++mermaidIdCounter}`;
      const { svg } = await mermaid.render(id, diagram);
      div.innerHTML = sanitizeSvg(svg);
    } catch (err) {
      const errSpan = document.createElement("span");
      errSpan.className = "mermaid-error";
      errSpan.textContent = err.message || "Invalid diagram";
      div.appendChild(errSpan);
      div.classList.add("mermaid-error");
    }
    pre.replaceWith(div);
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
        const trimmed = pastedText.trim();
        const looksLikeMarkdown =
          (!trimmed.startsWith("<") &&
            (/^#|^\*\*|^\- |^\d+\. |^`|^\[|^>|^\||^\- \[ \]|^\- \[x\]/i.test(trimmed) ||
              /\n```|\n#{1,6}\s|\n\*\*|\n\- |\n\d+\. |\n\|---|\n\- \[ \]/.test(pastedText)));
        if (looksLikeMarkdown) {
          try {
            event.preventDefault();
            const html = parseMarkdownSafe(pastedText);
            editorRef.current.chain().focus().insertContent(html).run();
            return true;
          } catch (_) {
            return false;
          }
        }
        return false;
      },
    },
  });
  editorRef.current = editor;

  const state = { mode: "wysiwyg", markdownText: "", previewOn: false };

  const { mdBtn, previewBtn, handleDocClick } = buildToolbar(editor, toolbarEl);
  setupTableContextBar(editor, toolbarEl);
  setupMermaidEditMode(editor, editorEl);

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
  if (form) {
    form.addEventListener("submit", () => {
      if (state.mode === "markdown") {
        textarea.value = state.markdownText;
      } else {
        textarea.value = turndown.turndown(editor.getHTML());
      }
    });
  }

  editorInstances.set(textareaId, {
    editor,
    cleanup: () => {
      document.removeEventListener("click", handleDocClick);
    },
  });
  return editor;
};

const autoInit = () => {
  if (typeof document === "undefined" || !document.querySelector) return;
  document.querySelectorAll('[data-wysiwyg="v3"]').forEach((wrapper) => {
    const ta = wrapper.querySelector("textarea[id]");
    if (ta && ta.id) initWysiwyg(ta.id);
  });
};

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoInit);
  } else {
    autoInit();
  }
}