/**
 * Carousel: scrolls a track by one step (e.g. one card) on prev/next button click.
 * Optional autoplay via data-carousel-autoplay (delay in ms).
 *
 * DOM: [data-carousel] root with id; inside: [data-carousel-track] (scrollable), and
 * controls with id "{root.id}-controls" containing [data-carousel-prev] / [data-carousel-next].
 */
(function () {
  'use strict';

  function getStepPx(track) {
    var first = track.querySelector('.post-cards__item');
    if (first) {
      var style = window.getComputedStyle(first);
      var width = first.offsetWidth;
      var marginRight = parseFloat(style.marginRight) || 0;
      return width + marginRight;
    }
    return 320;
  }

  function scrollCarousel(track, direction, smooth) {
    if (!track) return;
    var step = getStepPx(track);
    var maxScroll = track.scrollWidth - track.clientWidth;
    var current = track.scrollLeft;
    var next = direction === 'next'
      ? Math.min(current + step, maxScroll)
      : Math.max(current - step, 0);
    track.scrollTo({ left: next, behavior: smooth ? 'smooth' : 'auto' });
  }

  function initCarousel(root) {
    if (!root || !root.id) return;
    var track = root.querySelector('[data-carousel-track]');
    var controls = document.getElementById(root.id + '-controls');
    if (!track || !controls) return;

    var prevBtn = controls.querySelector('[data-carousel-prev]');
    var nextBtn = controls.querySelector('[data-carousel-next]');
    if (prevBtn) {
      prevBtn.addEventListener('click', function () { scrollCarousel(track, 'prev', true); });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', function () { scrollCarousel(track, 'next', true); });
    }

    var autoplayDelay = root.getAttribute('data-carousel-autoplay');
    if (autoplayDelay) {
      var delayMs = parseInt(autoplayDelay, 10) || 4000;
      var timer = null;

      function startAutoplay() {
        timer = setInterval(function () {
          var maxScroll = track.scrollWidth - track.clientWidth;
          if (track.scrollLeft >= maxScroll - 1) {
            track.scrollTo({ left: 0, behavior: 'smooth' });
          } else {
            scrollCarousel(track, 'next', true);
          }
        }, delayMs);
      }

      function stopAutoplay() {
        if (timer) clearInterval(timer);
        timer = null;
      }

      root.addEventListener('mouseenter', stopAutoplay);
      root.addEventListener('mouseleave', startAutoplay);
      root.addEventListener('focusin', stopAutoplay);
      root.addEventListener('focusout', function (e) {
        if (!root.contains(e.relatedTarget)) startAutoplay();
      });
      startAutoplay();
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
