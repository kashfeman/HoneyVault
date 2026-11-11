"use strict";

// Loaded only by the administrator layout. No network, cookies or web storage.
const documentDialog = document.querySelector("#document-dialog");
const simulationForm = document.querySelector("#document-simulation");
const simulationResult = document.querySelector("#simulation-result");
if (documentDialog && simulationForm && simulationResult && typeof documentDialog.showModal === "function") {
  let opener = null;
  document.querySelectorAll("[data-open-dialog]").forEach(button => {
    button.hidden = false;
    button.addEventListener("click", () => {
      opener = button;
      simulationForm.reset();
      simulationResult.hidden = true;
      documentDialog.showModal();
    });
  });
  documentDialog.querySelectorAll("[data-close-dialog]").forEach(button => {
    button.addEventListener("click", () => documentDialog.close());
  });
  documentDialog.addEventListener("close", () => {
    simulationForm.reset();
    nameInput.setCustomValidity("");
    if (simulationResult.hidden) opener?.focus();
    else simulationResult.focus();
  });
  const nameInput = simulationForm.elements.namedItem("title");
  nameInput.addEventListener("input", () => {
    nameInput.setCustomValidity(nameInput.value.trim().length < 3 ? "Enter at least 3 non-blank characters." : "");
  });
  simulationForm.addEventListener("submit", event => {
    event.preventDefault();
    nameInput.setCustomValidity(nameInput.value.trim().length < 3 ? "Enter at least 3 non-blank characters." : "");
    if (!simulationForm.reportValidity()) return;
    const fields = simulationForm.elements;
    // Render user text as textContent, never markup. Nothing is saved or generated.
    const status = fields.namedItem("status");
    simulationResult.textContent = `Simulation confirmed: “${nameInput.value.trim()}” · ${fields.namedItem("category").value} · ${fields.namedItem("format").value} · ${fields.namedItem("sensitivity").value}${status ? " · " + status.value : ""}. No document was created or changed. Backend integration is pending.`;
    documentDialog.close();
    simulationResult.hidden = false;
  });
}

const reviewedOnPage = new Set();
document.querySelectorAll("[data-review]").forEach(button => {
  button.hidden = false;
  button.addEventListener("click", () => {
    const id = button.dataset.review;
    if (reviewedOnPage.has(id)) return;
    reviewedOnPage.add(id);
    document.querySelectorAll("[data-alert-row]").forEach(row => {
      if (row.dataset.alertRow === id) {
        row.querySelector("[data-review-status]").textContent = "Reviewed · Temporary";
      }
    });
    button.textContent = "Reviewed · Temporary";
    button.disabled = true;
    const total = document.querySelector("#reviewed-total");
    if (total) total.textContent = String(Number(total.dataset.baseline) + reviewedOnPage.size);
    document.querySelector("#review-feedback").textContent = `${id} marked reviewed on this page only. Snapshot filters are unchanged. Refresh or navigate to reset.`;
  });
});
