"use strict";
/**
 * ferro-nav.js
 * Renders the site header, status bar, and drawer navigation used across
 * anonymousik.is-a.dev pages, so a subpage (like this WebTerm tool) reads
 * as part of the same site instead of a bolted-on external app.
 *
 * Link structure below (Home / Projects / Scripts / Stack / Contact /
 * GitHub, plus the "SecFerro Division" group with tmux_setup / Module
 * Reference / Changelog) was pulled from a live fetch of the homepage —
 * it is the REAL nav, not invented. "WebTerm" has been added to the
 * SecFerro Division group since it isn't listed there yet; add the
 * matching entry to the homepage's own nav markup so it shows up
 * everywhere (see the patch note left in this project's CHANGELOG.md).
 */

(function () {
  const ORIGIN = "https://anonymousik.is-a.dev";

  const NAV_LINKS = [
    { label: "Home", href: `${ORIGIN}/` },
    { label: "Projects", href: `${ORIGIN}/#projects` },
    { label: "Scripts", href: `${ORIGIN}/scripts` },
    { label: "Stack", href: `${ORIGIN}/#stack` },
    { label: "Contact", href: `${ORIGIN}/#contact` },
  ];

  const SECFERRO_LINKS = [
    { label: "tmux_setup · v5.0.0", href: `${ORIGIN}/scripts/tmux_setup` },
    { label: "WebTerm", href: `${ORIGIN}/scripts/webterm/`, id: "webterm" },
    { label: "Module Reference", href: `${ORIGIN}/scripts` },
    { label: "Changelog", href: `${ORIGIN}/CHANGELOG` },
  ];

  const EXTERNAL_LINKS = [
    { label: "GitHub ↗", href: "https://github.com/Anonymousik", external: true },
  ];

  function el(tag, props, children) {
    const node = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach((key) => {
        if (key === "class") node.className = props[key];
        else if (key === "html") node.innerHTML = props[key];
        else node.setAttribute(key, props[key]);
      });
    }
    (children || []).forEach((child) => {
      if (child) node.appendChild(child);
    });
    return node;
  }

  function renderLink(item, currentId) {
    const a = el("a", {
      href: item.href,
      class: "ferro-drawer__link" + (item.id && item.id === currentId ? " is-current" : ""),
    });
    a.textContent = item.label;
    if (item.external) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
    return a;
  }

  function buildDrawer(currentId) {
    const panel = el("div", { class: "ferro-drawer__panel" }, [
      el("div", { class: "ferro-drawer__group-title" }, []),
    ]);
    panel.querySelector(".ferro-drawer__group-title").textContent = "Navigation";
    NAV_LINKS.forEach((item) => panel.appendChild(renderLink(item, currentId)));

    const secferroTitle = el("div", { class: "ferro-drawer__group-title" }, []);
    secferroTitle.textContent = "SecFerro Division";
    panel.appendChild(secferroTitle);
    SECFERRO_LINKS.forEach((item) => panel.appendChild(renderLink(item, currentId)));

    const externalTitle = el("div", { class: "ferro-drawer__group-title" }, []);
    externalTitle.textContent = "External";
    panel.appendChild(externalTitle);
    EXTERNAL_LINKS.forEach((item) => panel.appendChild(renderLink(item, currentId)));

    const backdrop = el("div", { class: "ferro-drawer__backdrop" }, []);
    const drawer = el("div", { class: "ferro-drawer" }, [backdrop, panel]);

    function close() { drawer.classList.remove("is-open"); }
    backdrop.addEventListener("click", close);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });

    return { drawer, open: () => drawer.classList.add("is-open"), close };
  }

  const MENU_ICON_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/>' +
    '<line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';

  function buildNav(currentId) {
    const brand = el("a", { href: `${ORIGIN}/`, class: "ferro-nav__brand" }, [
      el("span", { class: "ferro-nav__logo" }, []),
      el("span", { class: "ferro-nav__site" }, []),
    ]);
    brand.querySelector(".ferro-nav__logo").textContent = "ƑERRට";
    brand.querySelector(".ferro-nav__site").textContent = "ANONYMOUSIK";

    const menuBtn = el("button", {
      class: "ferro-nav__menu-btn",
      type: "button",
      "aria-label": "Otwórz nawigację",
      html: MENU_ICON_SVG,
    }, []);

    const { drawer, open } = buildDrawer(currentId);
    menuBtn.addEventListener("click", open);

    const nav = el("nav", { class: "ferro-nav" }, [brand, menuBtn]);
    return { nav, drawer };
  }

  function buildStatusBar() {
    const bar = el("div", { class: "ferro-statusbar" }, []);
    const sessionId = "u0_" + Math.floor(1000 + Math.random() * 8999);

    function render() {
      const now = new Date();
      const time = now.toTimeString().slice(0, 8);
      bar.innerHTML =
        `SESSION: <strong>${sessionId}</strong> &nbsp;|&nbsp; ` +
        `SYS_TIME: <strong>${time}</strong> &nbsp;|&nbsp; ` +
        `ENV: <strong>PRODUCTION</strong>`;
    }
    render();
    setInterval(render, 1000);
    return bar;
  }

  function buildOnlineBadge() {
    return el("div", { class: "ferro-badge-online" }, [
      el("span", { class: "ferro-badge-online__dot" }, []),
      (() => { const s = el("span", {}, []); s.textContent = "SYSTEMS ONLINE"; return s; })(),
    ]);
  }

  function buildFooter() {
    const footer = el("div", { class: "ferro-footer" }, []);
    footer.innerHTML =
      'ƑERRට · SECFERRO DIVISION SERIES · anonymousik.is-a.dev<br>' +
      `© ${new Date().getFullYear()} Anonymousik · MIT License · ` +
      '<a href="https://github.com/Anonymousik" target="_blank" rel="noopener noreferrer">github.com/Anonymousik</a>';
    return footer;
  }

  /**
   * Mounts the shared chrome. Call once per page:
   *   FerroNav.mount({ currentId: "webterm", breadcrumb: "SCRIPTS / WEBTERM" })
   */
  window.FerroNav = {
    mount(opts) {
      const options = opts || {};
      document.body.classList.add("ferro-themed");

      const { nav, drawer } = buildNav(options.currentId);
      document.body.insertBefore(drawer, document.body.firstChild);
      document.body.insertBefore(nav, document.body.firstChild === drawer ? drawer.nextSibling : document.body.firstChild);

      const header = el("div", {}, [buildStatusBar(), buildOnlineBadge()]);
      header.style.textAlign = "center";
      nav.insertAdjacentElement("afterend", header);

      if (options.breadcrumb) {
        const crumb = el("div", { class: "ferro-breadcrumb" }, []);
        crumb.innerHTML = options.breadcrumb;
        header.insertAdjacentElement("afterend", crumb);
      }

      if (options.mountFooter !== false) {
        document.body.appendChild(buildFooter());
      }
    },
  };
})();
