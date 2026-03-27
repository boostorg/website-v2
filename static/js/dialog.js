/**
 * Dialog – ESC key support and focus trap for CSS-only dialogs.
 *
 * The dialog uses CSS :target for open/close (no JS required for basic functionality).
 * This script adds progressive enhancement:
 *   - ESC key closes any open dialog
 *   - Focus trap: keeps keyboard focus within the dialog
 */
(function () {
  'use strict';

  function getFocusableElements(container) {
    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'textarea:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(', ');

    return Array.from(container.querySelectorAll(focusableSelectors));
  }

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

  function setInitialFocus(dialog) {
    const focusableElements = getFocusableElements(dialog);
    if (focusableElements.length > 0) {
      focusableElements[0].focus();
    }
  }

  // Dialogs are opened via hash change in the URL. This listens for those specific events.
  window.addEventListener('hashchange', function () {
    const openDialogWrapper = document.querySelector('.dialog-modal:target');
    if (openDialogWrapper) {
      const dialogContainer =
        openDialogWrapper.querySelector('[role="dialog"]');
      if (dialogContainer) {
        setInitialFocus(dialogContainer);
      }
    }
  });

  document.addEventListener('keydown', function (e) {
    const openDialogWrapper = document.querySelector('.dialog-modal:target');

    if (!openDialogWrapper) return;

    const dialogContainer = openDialogWrapper.querySelector('[role="dialog"]');
    if (!dialogContainer) return;

    // ESC key closes the dialog
    if (e.key === 'Escape' || e.key === 'Esc') {
      e.preventDefault();
      window.location.hash = '_';
      return;
    }

    // Tab key traps focus within the dialog
    trapFocus(e, dialogContainer);
  });
})();
