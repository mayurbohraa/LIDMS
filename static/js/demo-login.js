"use strict";

const demoStatus = document.querySelector(".demo-status");
const demoDialog = document.querySelector("#demo-dialog");
const demoOpen = document.querySelector(".demo-open");
if (demoDialog && demoOpen) {
  demoOpen.hidden = false;
  demoOpen.addEventListener("click", () => {
    demoStatus.textContent = "";
    demoDialog.showModal();
    document.body.classList.add("demo-modal-open");
  });
  demoDialog.querySelector(".demo-close").addEventListener("click", () => demoDialog.close());
  demoDialog.addEventListener("close", () => {
    document.body.classList.remove("demo-modal-open");
    demoOpen.focus();
  });
  demoDialog.addEventListener("click", (event) => {
    const bounds = demoDialog.getBoundingClientRect();
    if (event.target === demoDialog && (
      event.clientX < bounds.left || event.clientX > bounds.right ||
      event.clientY < bounds.top || event.clientY > bounds.bottom
    )) demoDialog.close();
  });
}
document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.hidden = false;
  button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.copyTarget);
    const value = target.value ?? target.textContent;
    try {
      await navigator.clipboard.writeText(value);
      demoStatus.textContent = `${button.getAttribute("aria-label").replace(/^Copy /, "")} copied.`;
    } catch {
      // Leave a usable manual-copy path when clipboard permission is unavailable.
      if (target.select) {
        target.focus();
        target.select();
      } else {
        const range = document.createRange();
        range.selectNodeContents(target);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      }
      demoStatus.textContent = "Selected. Copy the highlighted text using your device’s copy command.";
    }
  });
});
