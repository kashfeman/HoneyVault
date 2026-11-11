"use strict";

const menu = document.querySelector(".menu-toggle");
const sidebar = document.querySelector("#sidebar");
if (menu && sidebar) {
  menu.hidden = false;
  const closeMenu = () => {
    menu.setAttribute("aria-expanded", "false");
    sidebar.classList.remove("is-open");
  };
  menu.addEventListener("click", () => {
    const open = menu.getAttribute("aria-expanded") !== "true";
    menu.setAttribute("aria-expanded", String(open));
    sidebar.classList.toggle("is-open", open);
    if (open) sidebar.querySelector("nav a")?.focus();
  });
  sidebar.querySelectorAll("nav a").forEach(link => {
    link.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 900px)").matches) {
        closeMenu();
        menu.focus();
      }
    });
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
      closeMenu();
      menu.focus();
    }
  });
  window.matchMedia("(max-width: 900px)").addEventListener("change", () => {
    const focusWasInside = sidebar.contains(document.activeElement);
    closeMenu();
    if (focusWasInside && window.matchMedia("(max-width: 900px)").matches) menu.focus();
  });
}

const password = document.querySelector("#demo-password");
const toggle = document.querySelector("#toggle-password");
if (password && toggle) {
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    const show = password.type === "password";
    password.type = show ? "text" : "password";
    toggle.textContent = show ? "Hide" : "Show";
    toggle.setAttribute("aria-pressed", String(show));
  });
}
document.querySelector("#preview-login")?.addEventListener("submit", event => {
  // The inputs have no names, so they are also excluded without JavaScript.
  event.currentTarget.reset();
});
