/*
 * Applies offset to hash link scrolling on documentation pages to prevent navbar overlap.
 */

const NAVBAR_OFFSET = 48;
const LIBRARY_DOC_PATTERN = /\/doc\/libs\//;

function isUserInLibDoc() {
  const currentUrl = window.location.href;
  return LIBRARY_DOC_PATTERN.test(currentUrl);
}

function applyScrollOffset(targetId, offset) {
  const targetElement =
    document.getElementById(targetId) ||
    document.getElementsByName(targetId)[0];
  if (targetElement) {
    const offsetPosition =
      targetElement.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({
      top: offsetPosition,
      behavior: "smooth",
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (!isUserInLibDoc()) return;

  function handleScroll(event) {
    const linkHref = this.getAttribute("href");
    const [baseUrl, targetId] = linkHref.split("#");

    if (targetId && (!baseUrl || window.location.pathname.includes(baseUrl))) {
      event.preventDefault();

      applyScrollOffset(targetId, NAVBAR_OFFSET);
      window.history.pushState(null, null, `#${targetId}`);
    }
  }

  const scollToLinks = document.querySelectorAll('.section a[href*="#"]');
  scollToLinks.forEach((link) => {
    link.addEventListener("click", handleScroll);
  });

  if (window.location.hash) {
    const targetId = window.location.hash.substring(1);
    applyScrollOffset(targetId, NAVBAR_OFFSET);
  }
});

window.addEventListener("load", () => {
  if (window.location.hash) {
    const targetId = window.location.hash.substring(1);
    applyScrollOffset(targetId, NAVBAR_OFFSET);
  }
});
