/**
 * Code block copy: al hacer clic en .code-block__copy, copia el texto del código
 * al portapapeles, pone data-copied="true" en el botón y muestra el icono check.
 * Tras COPY_FEEDBACK_MS vuelve al estado inicial.
 */
(function () {
  var COPY_FEEDBACK_MS = 2000;

  function init() {
    document.querySelectorAll(".code-block__copy").forEach(function (btn) {
      if (btn.dataset.codeBlockCopyInit) return;
      btn.dataset.codeBlockCopyInit = "true";
      btn.addEventListener("click", handleCopyClick);
    });
  }

  function handleCopyClick(ev) {
    var btn = ev.currentTarget;
    var block = btn.closest(".code-block");
    if (!block) return;
    var codeEl = block.querySelector(".code-block__inner code");
    if (!codeEl) return;
    var text = codeEl.textContent || codeEl.innerText || "";

    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () {
          setCopiedState(btn, true);
          setTimeout(function () {
            setCopiedState(btn, false);
          }, COPY_FEEDBACK_MS);
        },
        function () {
          setCopiedState(btn, true);
          setTimeout(function () {
            setCopiedState(btn, false);
          }, COPY_FEEDBACK_MS);
        }
      );
    } else {
      setCopiedState(btn, true);
      setTimeout(function () {
        setCopiedState(btn, false);
      }, COPY_FEEDBACK_MS);
    }
  }

  function setCopiedState(btn, copied) {
    btn.setAttribute("data-copied", copied ? "true" : "false");
    btn.setAttribute("aria-label", copied ? "Copied" : "Copy code to clipboard");
  }

  function initHighlight() {
    if (typeof hljs !== "undefined" && hljs.highlightAll) {
      hljs.highlightAll();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init();
      initHighlight();
    });
  } else {
    init();
    initHighlight();
  }
})();
