/**
 * Boostlook documentation behaviour, vendored for the docs iframe.
 *
 * Source: boostlook/boostlook-v3.rb (the `scripts` heredoc). Upstream injects
 * this at doc build time, but the published library docs were built before it
 * existed, so the site supplies it instead. Keep in sync with that file, the
 * same way static/css/v3/boostlook-v3.css is kept in sync with boostlook-v3.css.
 *
 * Two independent branches, picked by the shape of the navigation tree:
 *
 *   AsciiDoctor docs  — the collapsible TOC upstream bakes in at build time.
 *                       Published library docs predate it, so serve it here.
 *
 *   Antora docs       — normally self-sufficient via _/js/site.js. The bundle
 *                       deployed to S3 predates the nav-toggle work in
 *                       website-v2-docs, so it binds toggles without ever
 *                       creating them. This backfills that one step, ported
 *                       from antora-ui/src/js/01-nav.js. It self-disables the
 *                       moment a current bundle is published (see the guard),
 *                       and should be deleted once that happens.
 *
 * Upstream's theme block is deliberately omitted: it self-disables inside an
 * iframe, and the host page already drives the theme via theme_handling.js.
 */
(function () {
  // Runs on DOM ready, so it works whether this is loaded from <head> or body.
  function isAsciiDoctorToc() {
    var toc = document.querySelector('#toc');
    if (!toc) return false;
    // Antora builds `.nav-list` here and drives it from its own bundle;
    // AsciiDoctor builds `ul.sectlevel*`. Only the latter is ours to enhance.
    if (toc.querySelector('.nav-list')) return false;
    return !!toc.querySelector('ul[class^=sectlevel]');
  }

  function staleAntoraNav() {
    var menu = document.querySelector('.nav-container [data-panel=menu]');
    if (!menu) return null;
    // A current bundle builds these itself; if any exist, stand down entirely.
    if (menu.querySelector('.nav-item-toggle')) return null;
    return menu.querySelector('.nav-list > .nav-list') ? menu : null;
  }

  // Ported from website-v2-docs/antora-ui/src/js/01-nav.js. Antora emits a
  // child nav-list as a *sibling* of its parent <li> when an entry is both an
  // xref and a parent, so the tree has to be re-nested before it can collapse.
  function backfillAntoraToggles(menu) {
    var find = function (from, sel) { return [].slice.call(from.querySelectorAll(sel)); };
    var stateKey = function () {
      var title = document.querySelector('.nav-menu .title');
      return 'nav-open-sections:' + (title ? title.textContent.trim() : 'default');
    };
    var labelOf = function (item) {
      var text = item.querySelector('.nav-text');
      if (text) return text.textContent.trim();
      var link = item.querySelector(':scope > .nav-link');
      return link ? link.textContent.trim() : null;
    };
    var save = function () {
      var open = [];
      find(menu, '.nav-item.is-active').forEach(function (item) {
        var l = labelOf(item);
        if (l) open.push(l);
      });
      try { window.localStorage.setItem(stateKey(), JSON.stringify(open)); } catch (e) {}
    };

    find(menu, '.nav-list > .nav-list').forEach(function (orphanList) {
      var prevLi = orphanList.previousElementSibling;
      if (!prevLi || prevLi.tagName !== 'LI') return;
      prevLi.classList.add('nav-item');
      var toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'nav-item-toggle';
      toggle.setAttribute('aria-label', 'Toggle section');
      toggle.setAttribute('aria-expanded', 'false');
      prevLi.insertBefore(toggle, prevLi.firstChild);
      prevLi.appendChild(orphanList);
    });

    try {
      var saved = JSON.parse(window.localStorage.getItem(stateKey()));
      if (saved) {
        find(menu, '.nav-item').forEach(function (item) {
          var l = labelOf(item);
          if (l && saved.indexOf(l) !== -1) item.classList.add('is-active');
        });
      }
    } catch (e) {}

    find(menu, '.nav-item-toggle').forEach(function (btn) {
      var li = btn.parentElement;
      var childList = li.querySelector(':scope > .nav-list');
      li.style.cursor = 'pointer';
      li.addEventListener('click', function (e) {
        if (e.target.closest('.nav-link') || (childList && childList.contains(e.target))) return;
        var open = li.classList.toggle('is-active');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        save();
      });
    });
  }

  function boot() {
    var antoraMenu = staleAntoraNav();
    if (antoraMenu) return backfillAntoraToggles(antoraMenu);
    if (!isAsciiDoctorToc()) return;

    (function () {
      var html = document.documentElement;
      html.classList.add('toc-visible', 'toc-pinned');
      html.classList.remove('toc-hidden');
    })();

    /*
     * Collapsible TOC — mirrors the Antora nav-tree (01-nav.js): parent items
     * get .nav-item + a .nav-item-toggle caret, branches are collapsed by
     * default (.is-active expands them), the current section's path is
     * expanded, open sections persist, and the section in view is highlighted
     * via .is-active-link. Caret/collapse styling lives in boostlook-v3.css.
     */
    (function () {
      function init() {
        var toc = document.querySelector('#toc');
        if (!toc) return;

        var labelOf = function (li) {
          var a = li.querySelector(':scope > a');
          return a ? a.textContent.trim() : null;
        };
        var setOpen = function (li, open) {
          li.classList.toggle('is-active', open);
          var btn = li.querySelector(':scope > .nav-item-toggle');
          if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        };
        var expandPath = function (li) {
          for (var n = li; n && n !== toc; n = n.parentNode) {
            if (n.classList && n.classList.contains('nav-item')) setOpen(n, true);
          }
        };

        // Decorate every parent item with .nav-item + a caret toggle.
        Array.prototype.forEach.call(toc.querySelectorAll('li'), function (li) {
          if (!li.querySelector(':scope > ul')) return;
          li.classList.add('nav-item');
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'nav-item-toggle';
          btn.setAttribute('aria-label', 'Toggle section');
          btn.setAttribute('aria-expanded', 'false');
          li.insertBefore(btn, li.firstChild);
        });

        var navItems = Array.prototype.slice.call(toc.querySelectorAll('.nav-item'));

        // Persist open sections (like Antora's nav-open-sections).
        var KEY = 'boostlook-toc-open:' + (document.title || 'doc');
        var save = function () {
          try {
            localStorage.setItem(KEY, JSON.stringify(
              navItems.filter(function (li) { return li.classList.contains('is-active'); })
                .map(labelOf).filter(Boolean)
            ));
          } catch (e) {}
        };
        var hadSaved = false;
        try {
          var saved = JSON.parse(localStorage.getItem(KEY));
          if (saved && saved.length) {
            navItems.forEach(function (li) {
              if (saved.indexOf(labelOf(li)) !== -1) setOpen(li, true);
            });
            hadSaved = true;
          }
        } catch (e) {}

        // Click the row (not the link or a nested list) to toggle.
        navItems.forEach(function (li) {
          li.addEventListener('click', function (e) {
            if (e.target.closest('a')) return;
            var sub = li.querySelector(':scope > ul');
            if (sub && sub.contains(e.target)) return;
            setOpen(li, !li.classList.contains('is-active'));
            save();
          });
        });

        // Scroll-spy: highlight the section in view (.is-active-link). The
        // .boostlook wrapper is the scroll container (html has overflow:hidden),
        // and on mobile it's the window — so listen on every plausible scroller
        // and measure with viewport-relative rects.
        var links = Array.prototype.slice.call(toc.querySelectorAll('a[href^="#"]'));
        var byId = {};
        links.forEach(function (a) {
          var id = decodeURIComponent(a.getAttribute('href').slice(1));
          if (id && document.getElementById(id)) byId[id] = a;
        });
        var headings = Object.keys(byId).map(function (id) { return document.getElementById(id); });
        var activeLi = null;
        var spyLock = false, spyTimer; // ignore scroll-spy during click-driven scroll
        var relock = function () {
          spyLock = true;
          clearTimeout(spyTimer);
          spyTimer = setTimeout(function () { spyLock = false; }, 150);
        };
        var setActive = function () {
          if (spyLock) return;
          var line = 130, current = null;
          headings.forEach(function (h) {
            if (h.getBoundingClientRect().top - line <= 0) current = h;
          });
          if (!current && headings.length) current = headings[0];
          links.forEach(function (a) { a.classList.remove('is-active-link'); });
          if (current && byId[current.id]) {
            byId[current.id].classList.add('is-active-link');
            activeLi = byId[current.id].closest('li');
          }
        };
        var ticking = false;
        var onScroll = function () {
          if (spyLock) { relock(); return; } // keep the lock through the click-scroll
          if (!ticking) { ticking = true; requestAnimationFrame(function () { ticking = false; setActive(); }); }
        };
        [document.querySelector('.boostlook'),
         document.querySelector('.article.toc2.toc-left'),
         window].forEach(function (el) {
          if (el) el.addEventListener('scroll', onScroll, { passive: true });
        });
        // A click highlights exactly the clicked link; lock the spy through the
        // scroll that follows so it can't bump the highlight to the next heading.
        links.forEach(function (a) {
          a.addEventListener('click', function () {
            relock();
            links.forEach(function (l) { l.classList.remove('is-active-link'); });
            a.classList.add('is-active-link');
            var li = a.closest('li');
            if (li) { activeLi = li; expandPath(li); }
          });
        });
        setActive();

        // On first load (no saved state) expand the current section's path so
        // the tree isn't fully collapsed; otherwise honor what was open.
        if (!hadSaved) {
          var hashLink = location.hash && toc.querySelector('a[href="' + location.hash + '"]');
          var startLi = (hashLink && hashLink.closest('li')) || activeLi || (navItems[0] || null);
          if (startLi) expandPath(startLi);
        }
      }
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
      else init();
    })();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
