/**
 * Install Card — Keyboard navigation & UX enhancements
 * Core interactions (tabs, dropdown, option selection) work without JS via
 * CSS radio inputs and <details>/<summary>. This script adds:
 *   - aria-selected sync on tab labels
 *   - Escape to close dropdown
 *   - Enter/Space to select dropdown items
 *   - Auto-close dropdown after option selection
 *   - aria-selected sync on dropdown items
 * Supports multiple install cards on the same page via querySelectorAll.
 */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-install-card]").forEach(function (card) {
    initInstallCard(card);
  });

  function initInstallCard(card) {
    var tabLabels = card.querySelectorAll('.tab__list [role="tab"]');

    // Sync aria-selected on tab labels when tab radio changes
    card.querySelectorAll("input.install-card__radio").forEach(function (radio) {
      radio.addEventListener("change", function () {
        tabLabels.forEach(function (label) {
          var r = document.getElementById(label.getAttribute("for"));
          label.setAttribute("aria-selected", r && r.checked ? "true" : "false");
        });
      });
    });

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
          updateOptionAria(panel);
          /* Defer focus so it runs after the <label>'s native focus-the-input behavior.
          This ensures focus goes back to the summary, not the radio input (which is visually hidden) */
          setTimeout(function () {
            summary.focus({ focusVisible: true });
          }, 0);
        });

        // Enter/Space to select
        item.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            item.click();
            /* Defer focus so it runs after the <label>'s native focus-the-input behavior.
            This ensures focus goes back to the summary, not the radio input (which is visually hidden) */
            setTimeout(function () {
              summary.focus({ focusVisible: true });
            }, 0);
          }
        });
      });

      // Escape to close dropdown
      details.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && details.hasAttribute("open")) {
          e.preventDefault();
          details.removeAttribute("open");
          summary.focus({ focusVisible: true });
        }
      });

      // Update ARIA on radio change
      panel.querySelectorAll('input[type="radio"]').forEach(function (radio) {
        radio.addEventListener("change", function () {
          updateOptionAria(panel);
        });
      });
    });

    // Sync aria-selected on dropdown items to match the checked option radio.
    function updateOptionAria(panel) {
      var items = panel.querySelectorAll(".dropdown__item");
      items.forEach(function (item) {
        var radioId = item.getAttribute("for");
        var radio = document.getElementById(radioId);
        var isSelected = radio && radio.checked;
        item.setAttribute("aria-selected", isSelected ? "true" : "false");
      });
    }
  }
});
