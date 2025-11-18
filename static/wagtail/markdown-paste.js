(function () {
  // Runs on the page editor; attaches a paste handler to Draftail editors.
  function isMarkdown(text) {
    // Very light heuristic: backticks or fenced code or headings/bullets
    return /`[^`]+`|(^|\n)```|(^|\n)#{1,6}\s|(^|\n)[*-]\s/.test(text);
  }

  function convertAndInsertMarkdown(evt, editorEl) {
    try {
      const md = evt.clipboardData.getData("text/markdown") || evt.clipboardData.getData("text/plain");
      if (!md || !isMarkdown(md)) return false;

      // Convert markdown -> HTML
      const html = window.marked.parse(md, { mangle: false, headerIds: false });

      // Stop the default paste; inject HTML instead
      evt.preventDefault();

      // Use the browser to paste HTML so Draftail can apply its from_html rules.
      // Create a temp contenteditable to execCommand('insertHTML')
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) return false;

      // Some Draftail builds support 'insertHTML' directly via execCommand:
      document.execCommand("insertHTML", false, html);
      return true;
    } catch (_) {
      return false;
    }
  }

  function attach() {
    // Draftail editor root elements have [data-draftail-input]
    document.querySelectorAll("[data-draftail-input]").forEach((wrapper) => {
      const editorEl = wrapper.querySelector("[contenteditable='true']");
      if (!editorEl || editorEl.__md_paste_bound) return;
      editorEl.__md_paste_bound = true;

      editorEl.addEventListener("paste", (evt) => {
        // Prefer text/markdown if provided by the clipboard
        const hasMarkdownMime = evt.clipboardData && Array.from(evt.clipboardData.types || []).includes("text/markdown");
        if (hasMarkdownMime || isMarkdown(evt.clipboardData.getData("text/plain") || "")) {
          convertAndInsertMarkdown(evt, editorEl);
        }
      });
    });
  }

  // Attach when the editor loads and also after Wagtail re-initializes editors
  document.addEventListener("DOMContentLoaded", attach);
  document.addEventListener("wagtail:document-loaded", attach);
})();
