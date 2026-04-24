
(function () {

  const CAROUSEL_STEP_PX_FALLBACK = 320;
  const SCROLL_RESET_EPSILON = 2;
  const SCROLL_END_EPSILON = 1;
  const DEFAULT_AUTOPLAY_MS = 4000;
  const CAROUSEL_ITEM_SELECTOR = '[data-carousel-item]';

  function setDisabled(btn, disabled) {
    if (!btn) return;
    if (btn.tagName === 'BUTTON') {
      btn.disabled = disabled;
    } else {
      if (disabled) {
        btn.setAttribute('aria-disabled', 'true');
      } else {
        btn.removeAttribute('aria-disabled');
      }
    }
  }

  function isDisabled(btn) {
    if (!btn) return true;
    if (btn.tagName === 'BUTTON') return btn.disabled;
    return btn.getAttribute('aria-disabled') === 'true';
  }

  function updateArrowState(track, prevBtns, nextBtns) {
    if (!track) return;
    const maxScroll = track.scrollWidth - track.clientWidth;
    const noScroll = maxScroll <= 0;
    const atStart = !noScroll && track.scrollLeft <= 0;
    const atEnd = !noScroll && track.scrollLeft >= maxScroll - SCROLL_END_EPSILON;
    prevBtns.forEach(function (b) { setDisabled(b, noScroll || atStart); });
    nextBtns.forEach(function (b) { setDisabled(b, noScroll || atEnd); });
  }

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
    const prevBtns = controls ? controls.querySelectorAll('[data-carousel-prev]') : [];
    const nextBtns = controls ? controls.querySelectorAll('[data-carousel-next]') : [];

    prevBtns.forEach(function (prevBtn) {
      prevBtn.addEventListener('click', function (e) {
        e.preventDefault();
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
    });

    nextBtns.forEach(function (nextBtn) {
      nextBtn.addEventListener('click', function (e) {
        e.preventDefault();
        scrollCarousel(track, 'next', true);
      });
    });

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

  function setupRadioCarousel(root, track) {
    const radios = root.querySelectorAll('input[type="radio"].testimonial-card__state');
    if (radios.length === 0) return;
    const items = track.querySelectorAll(CAROUSEL_ITEM_SELECTOR);

    let scrolling = false;
    let scrollTimeout = null;

    radios.forEach(function (radio, idx) {
      radio.addEventListener('change', function () {
        if (!radio.checked) return;
        const target = items[idx];
        if (!target) return;
        scrolling = true;
        target.scrollIntoView({ inline: 'start', block: 'nearest', behavior: 'smooth' });
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function () { scrolling = false; }, 400);
      });
    });

    track.addEventListener('scroll', function () {
      if (scrolling) return;
      const first = items[0];
      if (!first) return;
      const itemWidth = first.offsetWidth;
      if (itemWidth === 0) return;
      const idx = Math.round(track.scrollLeft / itemWidth);
      const radio = radios[Math.max(0, Math.min(radios.length - 1, idx))];
      if (radio && !radio.checked) radio.checked = true;
    }, { passive: true });
  }

  function initCarousel(root) {
    if (!root || !root.id) return;
    const track = root.querySelector('[data-carousel-track]');
    const controls = document.getElementById(root.id + '-controls');
    if (!track || !controls) return;

    if (root.hasAttribute('data-carousel-radios')) {
      setupRadioCarousel(root, track);
      return;
    }

    if (root.hasAttribute('data-carousel-infinite')) {
      setupInfiniteCarousel(root, track);
      return;
    }

    const prevBtns = controls.querySelectorAll('[data-carousel-prev]');
    const nextBtns = controls.querySelectorAll('[data-carousel-next]');
    prevBtns.forEach(function (prevBtn) {
      prevBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (isDisabled(prevBtn)) return;
        scrollCarousel(track, 'prev', true);
      });
    });
    nextBtns.forEach(function (nextBtn) {
      nextBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (isDisabled(nextBtn)) return;
        scrollCarousel(track, 'next', true);
      });
    });

    const syncArrows = function () {
      updateArrowState(track, prevBtns, nextBtns);
    };
    requestAnimationFrame(syncArrows);
    track.addEventListener('scroll', syncArrows, { passive: true });
    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(syncArrows);
      ro.observe(track);
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
