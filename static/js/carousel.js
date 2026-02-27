
(function () {

  const CAROUSEL_STEP_PX_FALLBACK = 320;

  function getStepPx(track) {
    const first = track.querySelector('.post-cards__item');
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

  function initCarousel(root) {
    if (!root || !root.id) return;
    const track = root.querySelector('[data-carousel-track]');
    const controls = document.getElementById(root.id + '-controls');
    if (!track || !controls) return;

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
      const delayMs = parseInt(autoplayDelay, 10) || 4000;
      let timer = null;

      const startAutoplay = () => {
        timer = setInterval(function () {
          var maxScroll = track.scrollWidth - track.clientWidth;
          if (track.scrollLeft >= maxScroll - 1) {
            track.scrollTo({ left: 0, behavior: 'smooth' });
          } else {
            scrollCarousel(track, 'next', true);
          }
        }, delayMs);
      }

      const stopAutoplay = () => {
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
