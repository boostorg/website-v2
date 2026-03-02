
(function () {

  const CAROUSEL_STEP_PX_FALLBACK = 320;
  const SCROLL_RESET_EPSILON = 2;
  const DEFAULT_AUTOPLAY_MS = 4000;
  const CAROUSEL_ITEM_SELECTOR = '[data-carousel-item]';

  function getStepPx(track) {
    const first = track.querySelector(CAROUSEL_ITEM_SELECTOR);
    if (first) {
      const itemStyle = window.getComputedStyle(first);
      const width = first.offsetWidth;
      const marginRight = parseFloat(itemStyle.marginRight) || 0;
      const trackStyle = window.getComputedStyle(track);
      const gap = parseFloat(trackStyle.gap) || 0;
      return width + marginRight + gap;
    }
    return CAROUSEL_STEP_PX_FALLBACK;
  }

  function scrollCarousel(track, direction, smooth) {
    if (!track) return;
    const step = getStepPx(track);
    const maxScroll = track.scrollWidth - track.clientWidth;
    const current = track.scrollLeft;
    const next = direction === 'next'
      ? Math.min(current + step, maxScroll)
      : Math.max(current - step, 0);
    track.scrollTo({ left: next, behavior: smooth ? 'smooth' : 'auto' });
  }

  function setupAutoplay(root, onTick, delayMs) {
    const ms = delayMs || DEFAULT_AUTOPLAY_MS;
    let timer = null;
    const start = function () {
      timer = setInterval(onTick, ms);
    };
    const stop = function () {
      if (timer) clearInterval(timer);
      timer = null;
    };
    root.addEventListener('mouseenter', stop);
    root.addEventListener('mouseleave', start);
    root.addEventListener('focusin', stop);
    root.addEventListener('focusout', function (e) {
      if (!root.contains(e.relatedTarget)) start();
    });
    start();
  }

  function setupInfiniteCarousel(root, track) {
    const items = track.querySelectorAll(CAROUSEL_ITEM_SELECTOR);
    if (items.length === 0) return;

    let setCount = 1;
    const appendCloneSet = () => {
      const list = track.querySelectorAll(CAROUSEL_ITEM_SELECTOR);
      const n = list.length / setCount;
      for (let i = 0; i < n; i++) {
        track.appendChild(list[i].cloneNode(true));
      }
      setCount++;
    };

    appendCloneSet();
    while (track.scrollWidth / setCount < track.clientWidth) {
      appendCloneSet();
    }

    const setWidth = track.scrollWidth / setCount;
    const step = getStepPx(track);
    let scrollResetInProgress = false;

    track.addEventListener('scroll', function () {
      if (scrollResetInProgress) return;
      const left = track.scrollLeft;
      if (left >= setWidth - SCROLL_RESET_EPSILON) {
        scrollResetInProgress = true;
        track.scrollLeft = left - setWidth;
        requestAnimationFrame(function () {
          scrollResetInProgress = false;
        });
      }
    });

    const controls = document.getElementById(root.id + '-controls');
    const prevBtn = controls && controls.querySelector('[data-carousel-prev]');
    const nextBtn = controls && controls.querySelector('[data-carousel-next]');

    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        if (track.scrollLeft < step) {
          scrollResetInProgress = true;
          track.scrollLeft = setWidth;
          requestAnimationFrame(function () {
            scrollResetInProgress = false;
            scrollCarousel(track, 'prev', true);
          });
        } else {
          scrollCarousel(track, 'prev', true);
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        scrollCarousel(track, 'next', true);
      });
    }

    const autoplayDelay = root.getAttribute('data-carousel-autoplay');
    if (autoplayDelay) {
      setupAutoplay(root, () => {
        if (track.scrollLeft >= setWidth - SCROLL_RESET_EPSILON) {
          scrollResetInProgress = true;
          track.scrollLeft = track.scrollLeft - setWidth;
          requestAnimationFrame(function () {
            scrollResetInProgress = false;
          });
        }
        scrollCarousel(track, 'next', true);
      }, parseInt(autoplayDelay, 10));
    }
  }

  function initCarousel(root) {
    if (!root || !root.id) return;
    const track = root.querySelector('[data-carousel-track]');
    const controls = document.getElementById(root.id + '-controls');
    if (!track || !controls) return;

    if (root.hasAttribute('data-carousel-infinite')) {
      setupInfiniteCarousel(root, track);
      return;
    }

    const prevBtn = controls.querySelector('[data-carousel-prev]');
    const nextBtn = controls.querySelector('[data-carousel-next]');
    if (prevBtn) {
      prevBtn.addEventListener('click', function () { scrollCarousel(track, 'prev', true); });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', function () { scrollCarousel(track, 'next', true); });
    }

    const autoplayDelay = root.getAttribute('data-carousel-autoplay');
    if (autoplayDelay) {
      setupAutoplay(root,  () => {
        const maxScroll = track.scrollWidth - track.clientWidth;
        if (track.scrollLeft >= maxScroll - 1) {
          track.scrollTo({ left: 0, behavior: 'smooth' });
        } else {
          scrollCarousel(track, 'next', true);
        }
      }, parseInt(autoplayDelay, 10));
    }
  }

  function init() {
    document.querySelectorAll('[data-carousel]').forEach(initCarousel);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
