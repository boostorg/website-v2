/*
This is a customized version of frontend/wyisyg-editor.js which pares down the
available functions for use on the edit user profile page.
*/

import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";
import { createToolbarButton, openModal, parseMarkdownSafe, setupMermaidEditMode, highlightPreviewCodeBlocks, renderMermaidPreview, debounce, ICONS, } from "./wysiwyg-editor"

const editorInstances = new Map();

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

const buildToolbar = (editor, toolbarEl) => {
  const left = document.createElement("div");
  left.className = "wysiwyg-toolbar__left";
  const right = document.createElement("div");
  right.className = "wysiwyg-toolbar__right";


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

  return { mdBtn, previewBtn };
};

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
      StarterKit.configure(
        {
          codeBlock: false,
        }
      ),
      Underline,
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

  const { mdBtn, previewBtn } = buildToolbar(editor, toolbarEl);
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

  editorInstances.set(textareaId, {
    editor,
    cleanup: () => {
      if (form) form.removeEventListener("submit", syncTextarea, true);
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
}
