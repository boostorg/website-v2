/**
 * Code block copy: on click of .code-block__copy, copies the code text to the clipboard,
 * sets data-copied="true" on the button and shows the check icon.
 * After COPY_FEEDBACK_MS it reverts to the initial state.
 */
(function () {
  const COPY_FEEDBACK_MS = 2000;

  function init() {
    document.querySelectorAll(".code-block__copy").forEach(function (btn) {
      if (btn.dataset.codeBlockCopyInit) return;
      btn.dataset.codeBlockCopyInit = "true";
      btn.addEventListener("click", handleCopyClick);
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
      console.warn("code-block: execCommand('copy') failed", e);
    }
    document.body.removeChild(textarea);
    return ok;
  }

  function handleCopyClick(ev) {
    const btn = ev.currentTarget;
    const block = btn.closest(".code-block");
    if (!block) return;
    const codeEl = block.querySelector(".code-block__inner code");
    if (!codeEl) return;
    const text = codeEl.textContent || codeEl.innerText || "";

    function showCopiedFeedback() {
      setCopiedState(btn, "true");
      setTimeout(function () {
        setCopiedState(btn, "false");
      }, COPY_FEEDBACK_MS);
    }

    function showErrorFeedback() {
      setCopiedState(btn, "error");
      setTimeout(function () {
        setCopiedState(btn, "false");
      }, COPY_FEEDBACK_MS);
    }

    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () {
          showCopiedFeedback();
        },
        function () {
          if (fallbackCopy(text)) {
            showCopiedFeedback();
          } else {
            showErrorFeedback();
          }
        }
      );
    } else {
      if (fallbackCopy(text)) {
        showCopiedFeedback();
      } else {
        showErrorFeedback();
      }
    }
  }

  function setCopiedState(btn, state) {
    btn.setAttribute("data-copied", state);
    const labels = {
      true: "Copied",
      false: "Copy code to clipboard",
      error: "Copy failed"
    };
    btn.setAttribute("aria-label", labels[state] || labels.false);
  }

    // Replace C++ highlighting AFTER highlight.js processes blocks
  // Let hljs work initially, then replace C++ blocks with custom highlighter
  function processCppBlocks () {
    const CppHighlight = typeof window !== "undefined" && window.CppHighlight;
    if (!CppHighlight) return
    // Selectors for C++ code blocks that highlight.js has already processed
    const cppSelectors = [
      'code.language-cpp.hljs',
      'code.language-c++.hljs',
      'code[data-lang="cpp"].hljs',
      'code[data-lang="c++"].hljs',
      '.doc pre.highlight code[data-lang="cpp"].hljs',
      '.doc pre.highlight code[data-lang="c++"].hljs',
    ]

    let processedCount = 0

    cppSelectors.forEach(function (selector) {
      try {
        document.querySelectorAll(selector).forEach(function (el) {
          // Skip if already processed
          if (el.classList.contains('cpp-highlight')) return

          // Replace highlight.js's C++ highlighting with our custom highlighter
          // This gives us full control over C++ syntax highlighting
          CppHighlight.highlightElement(el)

          // Mark as processed with our custom highlighter
          el.classList.add('cpp-highlight')
          processedCount++
        })
      } catch (e) {
        console.warn('cpp-highlight error:', selector, e)
      }
    })

  }

  function initHighlight() {
    if (typeof hljs !== "undefined" && hljs.highlightAll) {
      hljs.highlightAll();
    }

       // Then, replace C++ blocks with our custom highlighter
    // Use setTimeout to ensure highlight.js is completely done
    setTimeout(function () {
      processCppBlocks()
    }, 0)
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

    // Also use MutationObserver to catch dynamically added content
  // Process C++ blocks after highlight.js processes new content
  if (typeof window.MutationObserver !== 'undefined') {
    const observer = new window.MutationObserver(function (mutations) {
      let shouldProcess = false
      mutations.forEach(function (mutation) {
        if (mutation.addedNodes.length > 0) {
          shouldProcess = true
        }
      })
      if (shouldProcess) {
        // Wait a bit for highlight.js to process new content
        setTimeout(function () {
          processCppBlocks()
        }, 100)
      }
    })
    observer.observe(document.body || document.documentElement, {
      childList: true,
      subtree: true,
    })
  }
})();
