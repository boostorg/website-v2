(function () {
  function isMarkdown(text) {
    return /`[^`]+`|(^|\n)```|(^|\n)#{1,6}\s|(^|\n)[*-]\s/.test(text);
  }

  function convertAndInsertMarkdown(evt, editorEl) {
    try {
      if (typeof window.DOMPurify === "undefined") {
        return false;
      }
      const md = evt.clipboardData.getData("text/markdown") || evt.clipboardData.getData("text/plain");
      if (!md || !isMarkdown(md)) return false;

      const rawHtml = window.marked.parse(md, { mangle: false, headerIds: false });
      const html = window.DOMPurify.sanitize(rawHtml);

      evt.preventDefault();

      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) return false;

      document.execCommand("insertHTML", false, html);
      return true;
    } catch (_) {
      return false;
    }
  }

  function attach() {
    document.querySelectorAll("[data-draftail-input]").forEach((wrapper) => {
      const editorEl = wrapper.querySelector("[contenteditable='true']");
      if (!editorEl || editorEl.__md_paste_bound) return;
      editorEl.__md_paste_bound = true;

      editorEl.addEventListener("paste", (evt) => {
        const hasMarkdownMime = evt.clipboardData && Array.from(evt.clipboardData.types || []).includes("text/markdown");
        if (hasMarkdownMime || isMarkdown(evt.clipboardData.getData("text/plain") || "")) {
          convertAndInsertMarkdown(evt, editorEl);
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", attach);
  document.addEventListener("wagtail:document-loaded", attach);
})();
