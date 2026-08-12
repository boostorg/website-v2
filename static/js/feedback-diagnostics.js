/**
 * Ring buffer of recent client-side failures, read by the beta feedback widget.
 *
 * Loaded early and undeferred so it is installed before other scripts can fail.
 * Everything it collects is browser-only context the server cannot derive:
 * viewport, platform, the live search query, and the last few console errors
 * and failed requests.
 *
 * Exposes window.boostFeedbackDiagnostics() -> plain object, consumed by
 * templates/v3/includes/_feedback_widget.html at submit time.
 *
 * The whole file is defensive: a feedback tool must never be the thing that
 * breaks a page, so every hook falls through to the original behaviour.
 */
(function () {
  'use strict';

  var LIMIT = 10;
  var ENTRY_MAX = 500;
  // Matches the V3 breakpoints (mobile < 768, tablet 768-1279, desktop >= 1280).
  var TABLET_MIN = 768;
  var DESKTOP_MIN = 1280;

  var consoleErrors = [];
  var failedRequests = [];
  var searchQuery = '';

  function push(buffer, entry) {
    try {
      buffer.push(String(entry).slice(0, ENTRY_MAX));
      if (buffer.length > LIMIT) buffer.shift();
    } catch (e) {
      /* never let logging throw */
    }
  }

  // The feedback POST itself must not appear in its own report.
  function isFeedbackEndpoint(url) {
    return url.indexOf('/feedback/') !== -1;
  }

  function deviceType() {
    var width = window.innerWidth || 0;
    if (width >= DESKTOP_MIN) return 'desktop';
    if (width >= TABLET_MIN) return 'tablet';
    return 'mobile';
  }

  /* ---------- console + uncaught errors ---------- */

  window.addEventListener('error', function (event) {
    var where = event.filename ? ' (' + event.filename + ':' + event.lineno + ')' : '';
    push(consoleErrors, 'error: ' + (event.message || 'unknown') + where);
  });

  window.addEventListener('unhandledrejection', function (event) {
    push(consoleErrors, 'unhandled rejection: ' + (event.reason && event.reason.message ? event.reason.message : event.reason));
  });

  var originalConsoleError = window.console && window.console.error;
  if (originalConsoleError) {
    window.console.error = function () {
      push(consoleErrors, 'console.error: ' + Array.prototype.join.call(arguments, ' '));
      return originalConsoleError.apply(window.console, arguments);
    };
  }

  /* ---------- failed network requests ---------- */

  var originalFetch = window.fetch;
  if (originalFetch) {
    window.fetch = function (input, init) {
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      return originalFetch.apply(this, arguments).then(
        function (response) {
          if (!response.ok && !isFeedbackEndpoint(url)) {
            push(failedRequests, response.status + ' ' + (init && init.method ? init.method : 'GET') + ' ' + url);
          }
          return response;
        },
        function (error) {
          if (!isFeedbackEndpoint(url)) push(failedRequests, 'network error ' + url);
          throw error;
        }
      );
    };
  }

  var originalOpen = window.XMLHttpRequest && window.XMLHttpRequest.prototype.open;
  if (originalOpen) {
    window.XMLHttpRequest.prototype.open = function (method, url) {
      try {
        this.addEventListener('load', function () {
          if (this.status >= 400 && !isFeedbackEndpoint(String(url))) {
            push(failedRequests, this.status + ' ' + method + ' ' + url);
          }
        });
        this.addEventListener('error', function () {
          if (!isFeedbackEndpoint(String(url))) push(failedRequests, 'network error ' + url);
        });
      } catch (e) {
        /* fall through to the original open */
      }
      return originalOpen.apply(this, arguments);
    };
  }

  /* ---------- live search query ---------- */

  // The Gecko search modal mounts asynchronously, so listen at the document.
  document.addEventListener(
    'input',
    function (event) {
      var target = event.target;
      if (target && target.classList && target.classList.contains('search-modal__input')) {
        searchQuery = String(target.value || '').slice(0, 200);
      }
    },
    true
  );

  /* ---------- snapshot ---------- */

  window.boostFeedbackDiagnostics = function () {
    return {
      viewport: (window.innerWidth || 0) + 'x' + (window.innerHeight || 0),
      device: deviceType(),
      platform:
        (navigator.userAgentData && navigator.userAgentData.platform) ||
        navigator.platform ||
        '',
      search_query: searchQuery,
      console_errors: consoleErrors.slice(),
      failed_requests: failedRequests.slice()
    };
  };
})();
