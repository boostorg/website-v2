/**
 * Keyboard shortcut: Ctrl+K / Cmd+K opens the Boost Gecko search modal.
 */
(function () {
  'use strict';

  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      var searchBtn = document.getElementById('gecko-search-button');
      if (searchBtn) searchBtn.click();
    }
  });
})();
