/**
 * Install Card — Keyboard navigation & UX enhancements
 * Core interactions (tabs, dropdown, option selection) work without JS via
 * CSS radio inputs and <details>/<summary>. This script adds:
 *   - Arrow-key navigation between tabs
 *   - Escape to close dropdown
 *   - Enter/Space to select dropdown items
 *   - Auto-close dropdown after option selection
 *   - ARIA attribute updates on state changes
 */
document.addEventListener("DOMContentLoaded", function () {
  var card = document.querySelector("[data-install-card]");
  if (!card) return;

  var tabLabels = card.querySelectorAll('.tab__list [role="tab"]');

  // --- Arrow-key tab navigation ---
  tabLabels.forEach(function (label) {
    label.addEventListener("keydown", function (e) {
      var tabs = Array.from(tabLabels);
      var idx = tabs.indexOf(label);
      var target = null;

      if (e.key === "ArrowRight") target = tabs[(idx + 1) % tabs.length];
      if (e.key === "ArrowLeft")
        target = tabs[(idx - 1 + tabs.length) % tabs.length];

      if (target) {
        e.preventDefault();
        // Check the associated radio to switch tab
        var radio = document.getElementById(target.getAttribute("for"));
        if (radio) radio.checked = true;
        target.focus();
        updateTabAria();
      }
    });
  });

  // --- Tab ARIA updates on radio change ---
  card.querySelectorAll('input[name="install-tab"]').forEach(function (radio) {
    radio.addEventListener("change", updateTabAria);
  });

  function updateTabAria() {
    tabLabels.forEach(function (label) {
      var radio = document.getElementById(label.getAttribute("for"));
      var isActive = radio && radio.checked;
      label.setAttribute("aria-selected", isActive ? "true" : "false");
      label.setAttribute("tabindex", isActive ? "0" : "-1");
    });
  }

  // Set initial ARIA state
  updateTabAria();

  // --- Dropdown enhancements per panel ---
  card.querySelectorAll(".install-card__panel").forEach(function (panel) {
    var details = panel.querySelector("details.install-card__dropdown");
    if (!details) return;

    var summary = details.querySelector("summary");
    var items = panel.querySelectorAll(".dropdown__item");

    // Auto-close <details> after selecting an option
    items.forEach(function (item) {
      item.addEventListener("click", function () {
        details.removeAttribute("open");
        summary.focus();
        updateOptionAria(panel);
      });

      // Enter/Space to select
      item.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          item.click();
        }
      });
    });

    // Escape to close dropdown
    details.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && details.hasAttribute("open")) {
        e.preventDefault();
        details.removeAttribute("open");
        summary.focus();
      }
    });

    // Update ARIA on radio change
    panel.querySelectorAll('input[type="radio"]').forEach(function (radio) {
      radio.addEventListener("change", function () {
        updateOptionAria(panel);
      });
    });
  });

  function updateOptionAria(panel) {
    var items = panel.querySelectorAll(".dropdown__item");
    items.forEach(function (item) {
      var radioId = item.getAttribute("for");
      var radio = document.getElementById(radioId);
      var isSelected = radio && radio.checked;
      item.setAttribute("aria-selected", isSelected ? "true" : "false");
    });
  }
});
