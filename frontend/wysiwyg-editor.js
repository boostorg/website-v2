/**
 * TipTap WYSIWYG editor for v3 blog post content.
 *
 * Code blocks: Rendered by CodeBlockLowlight + lowlight (syntax highlighting).
 * New blocks from the toolbar get defaultLanguage (C++); language can be changed via the dropdown.
 *
 * Markdown: Initial content and pasted text are parsed with marked when they look like markdown.
 * Marked turns fenced code (```cpp, ```python, etc.) into <pre><code class="language-xxx">...</code></pre>,
 * which TipTap parses as codeBlock nodes with the language attribute, so pasted/initial markdown
 * produces proper code blocks with syntax highlighting.
 */
import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Code from "@tiptap/extension-code";
import CodeBlockLowlight from "@tiptap/extension-code-block-lowlight";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import { common, createLowlight } from "lowlight";
import { marked } from "marked";

const lowlight = createLowlight(common);

const CODE_LANGUAGES = [
  { value: "cpp", label: "C++" },
  { value: "python", label: "Python" },
];
const DEFAULT_CODE_LANGUAGE = "cpp";

function createToolbarButton(editor, opts) {
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
  function updateActive() {
    btn.classList.toggle("wysiwyg-toolbar__btn--active", isActive ? isActive() : false);
  }
  editor.on("selectionUpdate", updateActive);
  editor.on("transaction", updateActive);
  updateActive();
  return btn;
}

function buildToolbar(editor, toolbarEl) {
  const left = document.createElement("div");
  left.className = "wysiwyg-toolbar__left";
  const right = document.createElement("div");
  right.className = "wysiwyg-toolbar__right";

  left.appendChild(
    createToolbarButton(editor, {
      label: "Bold",
      title: "Bold",
      html: "<strong>B</strong>",
      onClick: () => editor.chain().focus().toggleBold().run(),
      isActive: () => editor.isActive("bold"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Italic",
      title: "Italic",
      html: "<em>I</em>",
      onClick: () => editor.chain().focus().toggleItalic().run(),
      isActive: () => editor.isActive("italic"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Underline",
      title: "Underline",
      html: "<u>U</u>",
      onClick: () => editor.chain().focus().toggleUnderline().run(),
      isActive: () => editor.isActive("underline"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Bullet list",
      title: "Bullet list",
      html: "&#8226;&#8226;&#8226;",
      onClick: () => editor.chain().focus().toggleBulletList().run(),
      isActive: () => editor.isActive("bulletList"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Link",
      title: "Link",
      html: "&#128279;",
      onClick: () => {
        const url = window.prompt("URL:");
        if (url) editor.chain().focus().setLink({ href: url }).run();
      },
      isActive: () => editor.isActive("link"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Inline code",
      title: "Inline code",
      html: "&lt;/&gt;",
      onClick: () => editor.chain().focus().toggleCode().run(),
      isActive: () => editor.isActive("code"),
    })
  );
  left.appendChild(
    createToolbarButton(editor, {
      label: "Code block",
      title: "Code block",
      html: "&#123;&#123;&#123;",
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
  function updateLangSelect() {
    const inCodeBlock = editor.isActive("codeBlock");
    langSelect.disabled = !inCodeBlock;
    if (inCodeBlock) {
      const attrs = editor.getAttributes("codeBlock");
      const lang = attrs.language || DEFAULT_CODE_LANGUAGE;
      langSelect.value = CODE_LANGUAGES.some((l) => l.value === lang) ? lang : DEFAULT_CODE_LANGUAGE;
    }
  }
  langSelect.addEventListener("change", () => {
    editor.chain().focus().updateAttributes("codeBlock", { language: langSelect.value }).run();
  });
  editor.on("selectionUpdate", updateLangSelect);
  editor.on("transaction", updateLangSelect);
  updateLangSelect();
  left.appendChild(langSelect);

  right.appendChild(
    createToolbarButton(editor, {
      label: "Undo",
      title: "Undo",
      html: "&#8630;",
      onClick: () => editor.chain().focus().undo().run(),
      isActive: () => false,
    })
  );
  right.appendChild(
    createToolbarButton(editor, {
      label: "Redo",
      title: "Redo",
      html: "&#8631;",
      onClick: () => editor.chain().focus().redo().run(),
      isActive: () => false,
    })
  );

  toolbarEl.appendChild(left);
  toolbarEl.appendChild(right);
}

/**
 * Initialize WYSIWYG editor for a textarea.
 * @param {string} textareaId - id of the content textarea (e.g. "id_content")
 */
export function initWysiwyg(textareaId) {
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
      initialContent = marked.parse(initialContent);
    } catch (_) {
      initialContent = rawContent;
    }
  }

  const editorRef = { current: null };
  const editor = new Editor({
    element: editorEl,
    extensions: [
      StarterKit.configure({ codeBlock: false }),
      Code,
      CodeBlockLowlight.configure({
        lowlight,
        defaultLanguage: DEFAULT_CODE_LANGUAGE,
      }),
      Underline,
      Link.configure({ openOnClick: false, HTMLAttributes: { target: "_blank", rel: "noopener" } }),
    ],
    content: initialContent,
    editorProps: {
      attributes: {
        class: "wysiwyg-editor__prose",
      },
      handleKeyDown(view, event) {
        if (event.key === "Tab") {
          event.preventDefault();
          editorRef.current?.chain().focus().insertContent("\t").run();
          return true;
        }
        return false;
      },
      handlePaste(_view, event) {
        const pastedText = event.clipboardData?.getData("text/plain") || "";
        if (!pastedText.trim() || !editorRef.current) return false;
        const trimmed = pastedText.trim();
        const looksLikeMarkdown =
          (!trimmed.startsWith("<") &&
            (/^#|^\*\*|^\- |^\d+\. |^`|^\[|^>|^\|/.test(trimmed) ||
              /\n```|\n#{1,6}\s|\n\*\*|\n\- |\n\d+\. /.test(pastedText)));
        if (looksLikeMarkdown) {
          try {
            const html = marked.parse(pastedText);
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

  buildToolbar(editor, toolbarEl);

  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  textarea.style.width = "1px";
  textarea.style.height = "1px";
  textarea.setAttribute("aria-hidden", "true");
  textarea.tabIndex = -1;

  const form = wrapper.closest("form");
  if (form) {
    form.addEventListener("submit", () => {
      textarea.value = editor.getHTML();
    });
  }

  return editor;
}

function autoInit() {
  if (typeof document === "undefined" || !document.querySelector) return;
  document.querySelectorAll('[data-wysiwyg="v3"]').forEach((wrapper) => {
    const ta = wrapper.querySelector("textarea[id]");
    if (ta && ta.id) initWysiwyg(ta.id);
  });
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoInit);
  } else {
    autoInit();
  }
}
