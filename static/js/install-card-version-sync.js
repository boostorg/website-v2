/**
 * Install Card — In-place version sync
 *
 * Listens for the `boost:version-changed` CustomEvent dispatched by the header
 * version-dropdown JS (see _header_v3.html) and swaps the install card between
 * its "latest" and "older" variants without a page reload.
 *
 * Progressive enhancement: with JS disabled, the dropdown's form submits
 * normally and the server's POST + 302 + GET roundtrip swaps the card.
 *
 * Requires:
 *   - Wrapper element [data-install-card-wrapper][data-active-variant]
 *     around each install card render (see _install_card.html).
 *   - The header JS to dispatch `boost:version-changed` with detail
 *     { slug, label, isLatest }.
 */

function _getOrCreateLiveRegion() {
  var el = document.getElementById("install-card-live");
  if (el) return el;
  el = document.createElement("span");
  el.id = "install-card-live";
  el.setAttribute("aria-live", "polite");
  el.style.cssText =
    "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;";
  document.body.appendChild(el);
  return el;
}

document.addEventListener("boost:version-changed", function (e) {
  var detail = e.detail || {};
  var isLatest = detail.isLatest === true;
  var label = detail.label || "";

  document
    .querySelectorAll("[data-install-card-wrapper]")
    .forEach(function (wrapper) {
      var prev = wrapper.getAttribute("data-active-variant");
      var next = isLatest ? "latest" : "older";

      wrapper.setAttribute("data-active-variant", next);

      if (prev !== next) {
        var visible = isLatest
          ? wrapper.querySelector(".install-card:not(.install-card--older)")
          : wrapper.querySelector(".install-card--older");
        if (visible) {
          visible.classList.remove("install-card--entering");
          void visible.offsetWidth;
          visible.classList.add("install-card--entering");
          visible.addEventListener(
            "animationend",
            function () {
              visible.classList.remove("install-card--entering");
            },
            { once: true }
          );
        }
      }
    });

  var liveRegion = _getOrCreateLiveRegion();
  liveRegion.textContent = isLatest
    ? "Showing install steps for the latest version."
    : "Showing documentation link for Boost " + label + ".";
});
