/**
 * Triggers for the Boost Gecko search modal.
 *
 *   - Ctrl/Cmd+K keyboard shortcut anywhere on the page.
 *   - Form submit on `.search-card form` opens the modal prefilled with the input value.
 *   - Click on `.search-card__tag` opens the modal prefilled with the term label.
 *
 * Gecko opens via window.location.hash = '#search-dialog' (set by
 * #gecko-search-button's own click handler) and renders an MUI Autocomplete
 * whose inner <input> has class .search-modal__input. The modal mounts
 * asynchronously, so to prefill we poll briefly for that input then set its
 * value via the native HTMLInputElement value setter — React tracks its own
 * internal value, so dispatching a bubbling 'input' event after bypassing
 * React's setter is what makes the controlled component pick up the query.
 */
(function () {
  'use strict';

  function setReactInputValue(input, value) {
    var setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value'
    ).set;
    setter.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function openGeckoSearch(query) {
    var btn = document.getElementById('gecko-search-button');
    if (!btn) return;
    btn.click();
    if (!query) return;

    var tries = 20;
    var trySet = function () {
      var input = document.querySelector('.search-modal__input');
      if (input) {
        input.focus();
        setReactInputValue(input, query);
      } else if (--tries > 0) {
        setTimeout(trySet, 50);
      }
    };
    trySet();
  }

  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      openGeckoSearch();
    }
  });

  document.addEventListener('submit', function (e) {
    var form = e.target.closest && e.target.closest('.search-card form');
    if (!form) return;
    e.preventDefault();
    var input = form.querySelector('input[name="q"], input[type="search"]');
    openGeckoSearch(input ? input.value.trim() : '');
  });

  document.addEventListener('click', function (e) {
    var tag = e.target.closest && e.target.closest('.search-card__tag');
    if (!tag) return;
    e.preventDefault();
    openGeckoSearch(tag.textContent.trim());
  });
})();
