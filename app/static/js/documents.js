"use strict";

// Switch the presentation of the already rendered fixtures. No storage or network.
const viewControls = document.querySelector(".view-controls");
const cardView = document.querySelector("#document-cards");
const tableView = document.querySelector("#document-table");
if (viewControls && cardView && tableView) {
  viewControls.hidden = false;
  viewControls.addEventListener("click", event => {
    const button = event.target.closest("button[data-view]");
    if (!button) return;
    const cards = button.dataset.view === "cards";
    cardView.hidden = !cards;
    tableView.hidden = cards;
    viewControls.querySelectorAll("button").forEach(control => {
      control.setAttribute("aria-pressed", String(control === button));
    });
  });
}
