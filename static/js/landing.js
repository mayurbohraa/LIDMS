"use strict";

const campusHeader = document.querySelector("[data-campus-header]");
const campusMenu = document.querySelector("[data-campus-menu]");
const campusNavigation = document.querySelector("#campus-navigation");

if (campusHeader && campusMenu && campusNavigation) {
  campusHeader.classList.add("is-enhanced");
  const setMenu = (open) => {
    campusMenu.setAttribute("aria-expanded", String(open));
    campusMenu.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    campusHeader.classList.toggle("menu-open", open);
  };
  campusMenu.addEventListener("click", () => setMenu(campusMenu.getAttribute("aria-expanded") !== "true"));
  campusNavigation.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => setMenu(false)));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && campusMenu.getAttribute("aria-expanded") === "true") {
      setMenu(false);
      campusMenu.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!campusHeader.contains(event.target)) setMenu(false);
  });
  window.matchMedia("(min-width: 761px)").addEventListener("change", () => setMenu(false));
  const updateHeader = () => campusHeader.classList.toggle("is-scrolled", window.scrollY > 12);
  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });
}

function campusTabs(tabsSelector, panelsSelector, key, verticalQuery) {
  const tabs = Array.from(document.querySelectorAll(tabsSelector));
  const panels = Array.from(document.querySelectorAll(panelsSelector));
  if (!tabs.length || !panels.length) return null;
  const select = (value, focus = false) => {
    const tab = tabs.find((element) => element.dataset[key] === value);
    if (!tab) return;
    tabs.forEach((peer) => {
      peer.setAttribute("aria-selected", String(peer === tab));
      peer.tabIndex = peer === tab ? 0 : -1;
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset[key + "Panel"] !== value;
    });
    if (focus) tab.focus();
  };
  const orientation = verticalQuery ? window.matchMedia(verticalQuery) : null;
  const updateOrientation = () => tabs[0].parentElement.setAttribute("aria-orientation", orientation?.matches ? "vertical" : "horizontal");
  updateOrientation();
  orientation?.addEventListener("change", updateOrientation);
  select(tabs[0].dataset[key]);
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => select(tab.dataset[key]));
    tab.addEventListener("keydown", (event) => {
      const vertical = Boolean(orientation?.matches);
      let next;
      if (event.key === (vertical ? "ArrowDown" : "ArrowRight")) next = (index + 1) % tabs.length;
      if (event.key === (vertical ? "ArrowUp" : "ArrowLeft")) next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        select(tabs[next].dataset[key], true);
      }
    });
  });
  return select;
}

campusTabs("[data-role-tabs] [role=tab]", "[data-role-panel]", "role");

if ("IntersectionObserver" in window) {
  const navigationLinks = Array.from(document.querySelectorAll("#campus-navigation a[href^='#']"));
  const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      navigationLinks.forEach((link) => {
        if (link.hash === "#" + entry.target.id) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    });
  }, { rootMargin: "-12% 0px -65% 0px", threshold: 0 });
  document.querySelectorAll("#home, #about, #services, #roles, #faq").forEach((section) => sectionObserver.observe(section));

  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.08 });
    document.querySelectorAll("[data-reveal]").forEach((element) => revealObserver.observe(element));
    document.body.classList.add("campus-motion");
  }
}

// These previews are screenshots of the actual demo workspaces, not generated UI.
const dashboardPreview = document.querySelector("#dashboard-preview-image");
const dashboardPreviewLink = document.querySelector("[data-preview-open]");
const dashboardDialog = document.querySelector("[data-dashboard-dialog]");
const dashboardControls = document.querySelector("[data-preview-controls]");
if (dashboardPreview && dashboardPreviewLink) {
  const buttons = dashboardControls ? Array.from(dashboardControls.querySelectorAll("[data-dashboard]")) : [];
  if (dashboardControls) dashboardControls.hidden = false;
  let label = "Administrator";
  buttons.forEach((button) => {
    const preload = new Image();
    preload.src = button.dataset.image;
    button.addEventListener("click", () => {
      label = button.dataset.label;
      buttons.forEach((peer) => peer.setAttribute("aria-pressed", String(peer === button)));
      dashboardPreview.src = button.dataset.image;
      dashboardPreview.alt = `Actual LIDMS ${label} dashboard with local demonstration data`;
      dashboardPreviewLink.href = button.dataset.image;
      dashboardPreviewLink.setAttribute("aria-label", `Enlarge ${label} dashboard preview`);
    });
  });
  if (dashboardDialog && typeof dashboardDialog.showModal === "function") {
    const fullImage = dashboardDialog.querySelector("[data-dialog-image]");
    const imageArea = dashboardDialog.querySelector(".dashboard-lightbox-image-area");
    const zoom = dashboardDialog.querySelector("[data-zoom-dashboard]");
    dashboardPreviewLink.addEventListener("click", (event) => {
      event.preventDefault();
      fullImage.src = dashboardPreview.src;
      fullImage.alt = `Full ${label} dashboard preview`;
      dashboardDialog.querySelector("#dashboard-dialog-title").textContent = `${label} dashboard`;
      dashboardDialog.showModal();
      document.body.classList.add("preview-is-open");
    });
    zoom.addEventListener("click", () => {
      const expanded = imageArea.classList.toggle("is-zoomed");
      zoom.setAttribute("aria-pressed", String(expanded));
      zoom.textContent = expanded ? "Zoom out" : "Zoom in";
    });
    dashboardDialog.querySelector("[data-close-dashboard]").addEventListener("click", () => dashboardDialog.close());
    dashboardDialog.addEventListener("click", (event) => {
      const box = dashboardDialog.getBoundingClientRect();
      if (event.target === dashboardDialog && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) dashboardDialog.close();
    });
    dashboardDialog.addEventListener("close", () => {
      document.body.classList.remove("preview-is-open");
      imageArea.classList.remove("is-zoomed");
      imageArea.scrollTo(0, 0);
      zoom.setAttribute("aria-pressed", "false");
      zoom.textContent = "Zoom in";
    });
  }
}
