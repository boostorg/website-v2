/**
 * Code block copy: al hacer clic en .code-block__copy, copia el texto del código
 * al portapapeles, pone data-copied="true" en el botón y muestra el icono check.
 * Tras COPY_FEEDBACK_MS vuelve al estado inicial.
 */
(function () {
  var COPY_FEEDBACK_MS = 2000;
  var CppHighlight = typeof window !== 'undefined' && window.CppHighlight

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

    // Replace C++ highlighting AFTER highlight.js processes blocks
  // Let hljs work initially, then replace C++ blocks with custom highlighter
  function processCppBlocks () {
    if (!CppHighlight) return
    // Selectors for C++ code blocks that highlight.js has already processed
    var cppSelectors = [
      'code.language-cpp.hljs',
      'code.language-c++.hljs',
      'code[data-lang="cpp"].hljs',
      'code[data-lang="c++"].hljs',
      '.doc pre.highlight code[data-lang="cpp"].hljs',
      '.doc pre.highlight code[data-lang="c++"].hljs',
    ]

    var processedCount = 0

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

    if (processedCount > 0) {
      console.log('cpp-highlight: Replaced ' + processedCount + ' C++ code blocks')
    }
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
    var observer = new window.MutationObserver(function (mutations) {
      var shouldProcess = false
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
