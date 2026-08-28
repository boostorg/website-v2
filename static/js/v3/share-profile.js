/**
 * Share profile: on click of .js-copy-profile-url, copies the link's own href
 * (the browser resolves it to an absolute URL) to the clipboard instead of
 * navigating, then shows "Copied" for COPY_FEEDBACK_MS.
 *
 * The element stays a real <a href>, so with JS off or blocked the button
 * still leads to the profile it would otherwise have copied.
 */
(function () {
  const COPY_FEEDBACK_MS = 2000;

  function init() {
    document.querySelectorAll(".js-copy-profile-url").forEach(function (link) {
      if (link.dataset.copyProfileUrlInit) return;
      link.dataset.copyProfileUrlInit = "true";
      link.addEventListener("click", handleCopyClick);
    });
  }

  function fallbackCopy(text) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (e) {
      console.warn("share-profile: execCommand('copy') failed", e);
    }
    document.body.removeChild(textarea);
    return ok;
  }

  /**
   * The button's visible text, which sits as a bare text node between the
   * optional icon spans that _button.html renders.
   */
  function labelNode(link) {
    return Array.prototype.find.call(link.childNodes, function (node) {
      return node.nodeType === Node.TEXT_NODE && node.textContent.trim();
    });
  }

  function setState(link, state) {
    const labels = { copied: "Copied", error: "Copy failed" };
    const node = labelNode(link);
    if (state === "reset") {
      if (node && link.dataset.originalLabel !== undefined) {
        node.textContent = link.dataset.originalLabel;
      }
      link.removeAttribute("data-copied");
      link.setAttribute("aria-label", link.dataset.originalLabel || "Share");
      return;
    }
    if (node && link.dataset.originalLabel === undefined) {
      link.dataset.originalLabel = node.textContent;
    }
    if (node) node.textContent = labels[state];
    link.setAttribute("data-copied", state === "copied" ? "true" : "error");
    link.setAttribute("aria-label", labels[state]);
  }

  function handleCopyClick(ev) {
    const link = ev.currentTarget;
    // Reading .href (not the attribute) yields the absolute URL, which is what
    // someone pasting the link elsewhere needs.
    const url = link.href;
    if (!url) return;
    ev.preventDefault();

    function flash(state) {
      setState(link, state);
      setTimeout(function () {
        setState(link, "reset");
      }, COPY_FEEDBACK_MS);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(
        function () {
          flash("copied");
        },
        function () {
          flash(fallbackCopy(url) ? "copied" : "error");
        }
      );
    } else {
      flash(fallbackCopy(url) ? "copied" : "error");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
