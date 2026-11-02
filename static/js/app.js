"use strict";

const passwordToggle = document.querySelector(".password-toggle");
const passwordInput = document.querySelector("#id_password");
if (passwordToggle && passwordInput) {
  passwordToggle.addEventListener("click", () => {
    const show = passwordInput.type === "password";
    passwordInput.type = show ? "text" : "password";
    passwordToggle.setAttribute("aria-pressed", String(show));
    passwordToggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
    passwordToggle.textContent = show ? "Hide" : "Show";
  });
}

const menuToggle = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#navigation");
if (menuToggle && navigation) {
  menuToggle.addEventListener("click", () => {
    const expanded = menuToggle.getAttribute("aria-expanded") !== "true";
    menuToggle.setAttribute("aria-expanded", String(expanded));
    navigation.classList.toggle("open", expanded);
    if (expanded) navigation.querySelector("a")?.focus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navigation.classList.contains("open")) {
      navigation.classList.remove("open");
      menuToggle.setAttribute("aria-expanded", "false");
      menuToggle.focus();
    }
  });
}

// Restore buttons after browser back/forward navigation and preserve failed form input.
window.addEventListener("pageshow", () => {
  document.querySelectorAll("[data-submitting]").forEach((button) => {
    button.disabled = false;
    button.textContent = button.dataset.originalText;
    delete button.dataset.submitting;
  });
});
document.querySelectorAll('form[method="post"]').forEach((form) => {
  form.addEventListener("submit", () => {
    const button = form.querySelector('button[type="submit"]');
    if (button) {
      button.dataset.originalText = button.textContent;
      button.dataset.submitting = "true";
      button.disabled = true;
      button.textContent = "Please wait…";
    }
  });
});
