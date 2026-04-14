/**
 * Dialog – progressive enhancement for CSS-only dialogs.
 *
 * Supports two dialog types:
 *   - Hash-based (_dialog.html component):
 *     - Opened via URL hash and the :target pseudo-class.
 *     - Supports deep linking — navigating to the hash opens the dialog directly.
 *     - Adds a browser history entry, so the back button closes the dialog.
 *   - Checkbox-based (_library-filter.html component):
 *     - Opened via a hidden <input type="checkbox"> toggle.
 *     - No deep linking or history entry — the dialog can only be opened by user interaction on the page.
 *
 * Enhancements (all require JS):
 *   - Focus trap: Tab/Shift+Tab cycle within the dialog
 *   - ESC key closes the active dialog
 *   - Initial focus moves into the dialog on open
 *   - Enter key support for label[role="button"] elements
 *   - URL cleanup: strips #_ fragment after hash-based dialogs close
 */
(function () {
  'use strict';

  // Tracks the element that opened the dialog so focus can return to it on close.
  var triggerElement = null;

  // Returns visible, focusable elements within a container.
  // Filters out hidden elements (e.g. closed dropdown options with tabindex="0").
  function getFocusableElements(container) {
    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'textarea:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(', ');

    return Array.from(container.querySelectorAll(focusableSelectors)).filter(
      function (el) {
        return el.offsetWidth > 0 || el.offsetHeight > 0;
      }
    );
  }

  // On Tab: wraps focus from last → first element. On Shift+Tab: first → last.
  function trapFocus(e, dialog) {
    if (e.key !== 'Tab') return;

    const focusableElements = getFocusableElements(dialog);
    if (focusableElements.length === 0) return;

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    const activeElement = document.activeElement;

    const currentIndex = focusableElements.indexOf(activeElement);

    const isForbiddenElement =
      currentIndex === -1 || !dialog.contains(activeElement);

    if (e.shiftKey && (activeElement === firstElement || isForbiddenElement)) {
      e.preventDefault();
      lastElement.focus();
    } else if (
      !e.shiftKey &&
      (activeElement === lastElement || isForbiddenElement)
    ) {
      e.preventDefault();
      firstElement.focus();
    }
  }

  // Moves focus to the first focusable element when a dialog opens.
  function setInitialFocus(dialog) {
    const focusableElements = getFocusableElements(dialog);
    if (focusableElements.length > 0) {
      focusableElements[0].focus();
    }
  }

  // Finds the currently open dialog, checking both hash-based and checkbox-based types.
  function getActiveDialog() {
    // Hash-based modals (dialog component)
    var hashModal = document.querySelector('.dialog-modal:target');
    if (hashModal) {
      return hashModal.querySelector('[role="dialog"]') || hashModal;
    }
    // Checkbox-based modals (library filter)
    var toggle = document.querySelector('.library-filter__toggle:checked');
    if (toggle) {
      var sibling = toggle.parentElement.querySelector(
        '.library-filter__modal'
      );
      if (sibling) return sibling;
    }
    return null;
  }

  // Closes whichever dialog is currently open, then returns focus to the trigger.
  function closeActiveModal() {
    // Hash-based: navigate away from the target
    var hashModal = document.querySelector('.dialog-modal:target');
    if (hashModal) {
      var closeLink = hashModal.querySelector('[aria-label*="Close"]');
      if (closeLink && closeLink.href) {
        window.location.href = closeLink.href;
      }
    } else {
      // Checkbox-based: uncheck the toggle
      var toggle = document.querySelector('.library-filter__toggle:checked');
      if (toggle) {
        toggle.checked = false;
      }
    }

    // Return focus to the element that opened the dialog
    if (triggerElement) {
      triggerElement.focus({ focusVisible: true });
      triggerElement = null;
    }
  }

  // Hash-based modals open via URL hash change
  window.addEventListener('hashchange', function () {
    // Clean up #_ from the URL after a hash-based modal closes
    if (window.location.hash === '#_') {
      history.replaceState(
        null,
        '',
        window.location.pathname + window.location.search
      );
      return;
    }

    var dialog = getActiveDialog();
    if (dialog) {
      triggerElement = document.activeElement;
      setInitialFocus(dialog);
    }
  });

  // Checkbox-based modals open via toggle change
  document.addEventListener('change', function (e) {
    if (e.target.matches('.library-filter__toggle') && e.target.checked) {
      var dialog = getActiveDialog();
      if (dialog) {
        triggerElement = e.target.parentElement.querySelector(
          '.library-filter__trigger'
        );
        setInitialFocus(dialog);
      }
    }
  });

  // Enter key activates label[role="button"] elements (labels only natively respond to click)
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.matches('label[role="button"]')) {
      e.preventDefault();
      e.target.click();
    }
  });

  document.addEventListener('keydown', function (e) {
    var dialog = getActiveDialog();
    if (!dialog) return;

    // ESC key closes the dialog
    if (e.key === 'Escape' || e.key === 'Esc') {
      e.preventDefault();
      closeActiveModal();
      return;
    }

    // Tab key traps focus within the dialog
    trapFocus(e, dialog);
  });
})();
