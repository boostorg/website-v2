/**
 * Install Card — In-place version sync
 *
 * Listens for the `boost:version-changed` CustomEvent dispatched by the header
 * version-dropdown JS (see _header_v3.html) and swaps the install card between
 * its "latest" and "older" variants without a page reload. When switching to
 * the older variant, updates the "See Documentation" link to point at the
 * selected version's docs.
 *
 * Progressive enhancement: with JS disabled, the dropdown's form submits
 * normally and the server's POST + 302 + GET roundtrip swaps the card.
 *
 * Requires:
 *   - Wrapper element [data-install-card-wrapper][data-active-variant]
 *     around each install card render (see _install_card.html).
 *   - data-doc-link-wrapper marker around the older-variant CTA link.
 *   - The header JS to dispatch `boost:version-changed` with detail
 *     { slug, label, isLatest, docUrl }.
 */
document.addEventListener("boost:version-changed", function (e) {
  var detail = e.detail || {};
  var isLatest = detail.isLatest === true;
  var docUrl = detail.docUrl || "";

  document
    .querySelectorAll("[data-install-card-wrapper]")
    .forEach(function (wrapper) {
      wrapper.setAttribute(
        "data-active-variant",
        isLatest ? "latest" : "older"
      );
      if (!isLatest && docUrl) {
        var linkWrapper = wrapper.querySelector(
          "[data-install-card-doc-link-wrapper]"
        );
        var link = linkWrapper && linkWrapper.querySelector("a");
        if (link) link.setAttribute("href", docUrl);
      }
    });
});
