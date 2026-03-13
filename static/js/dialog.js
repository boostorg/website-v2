/**
 * Dialog – ESC key support for CSS-only dialogs.
 *
 * The dialog uses CSS :target for open/close (no JS required for basic functionality).
 * This script adds progressive enhancement: ESC key closes any open dialog.
 */
(function () {
  'use strict';

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' || e.key === 'Esc') {
      // Check if any dialog is currently open (has :target)
      var openDialog = document.querySelector('.dialog-modal:target');
      if (openDialog) {
        e.preventDefault();
        // Close by navigating to #_ (same as clicking close button)
        window.location.hash = '_';
      }
    }
  });
})();
