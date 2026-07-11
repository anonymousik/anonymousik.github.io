<div align="center">

# 🖥️ WebTerm

**A secure, modern, and fluid web-based SSH terminal emulator.**
Version: Node.js( Security )
	License: MIT

<p align="center">
WebTerm is a robust terminal interface built for the web, delivering native-feeling cross-page navigation, stringent backend security, and seamless integration with the <i>anonymousik.is-a.dev</i> visual identity.
Part of the <b>SecFerro Division</b> ecosystem.
</p>
</div>
<details>
<summary><kbd>📖 <b>Table of Contents</b> (Click to expand)</kbd></summary>
 * ✨ Key Features
 * 🛡️ Security Guidelines
 * 🚀 Deployment
 * 📝 Changelog
   * [1.3.0] - 2026-07-11
   * [1.2.0] - 2026-07-11
</details>

## ✨ Key Features
 * **Fluid UX & Identity:** Utilizes @view-transition for seamless navigation and ferro-theme.css for a consistent, narrative-driven visual experience (mirrors the homepage identity block: whoami, cat /etc/identity).
 * **Secure Backend:** Implements strict input validation for SSH parameters, robust MAX_CONCURRENT_SESSIONS capping, and process-wide uncaughtException handling.
 * **Resilient Connections:** Features automated reconnection prompts and login form submission guards to prevent race conditions.
 * **Ecosystem Integration:** Synchronizes navigation via ferro-nav.js across the SecFerro Division group (tmux_setup, Module Reference, Changelog).

## 🛡️ Security Guidelines
> [!WARNING]
> **Vulnerability Disclaimer**
> The current WebSocket endpoint lacks internal session authentication (e.g., JWT). Origin-checking (ALLOWED_ORIGINS) prevents unauthorized browser-based access, but direct API calls (e.g., via curl) may still bypass this.
> **Recommendation:** It is highly recommended to gate the backend service behind **Cloudflare Access** or a strict IP allowlist if exposed to the public internet.
>
 * **Content-Security-Policy (CSP):** WebTerm implements strict CSP meta tags to restrict script execution and connection origins.
 * **Subresource Integrity (SRI):** Standard SRI practices are enforced. If hash mismatches occur, regenerate integrity attributes using the command provided in the index.html comments.

## 🚀 Deployment
WebTerm is configured for seamless deployment on modern PaaS platforms like Render.
 * **Render Ready:** Includes a render.yaml with pre-configured healthCheckPath and environment variables.
 * **Node Engine Pinning:** Ensure you are using the pinned Node.js engine version specified in the configuration to guarantee stability.

## 📝 Changelog
All notable changes to this project will be documented in this section.
*Format based on Keep a Changelog.*

### [1.3.0] - 2026-07-11
#### ✨ Added
 * **Visual Identity:** Introduced ferro-theme.css, consolidating design tokens and component styles to align with the *anonymousik.is-a.dev* visual language.
 * **Navigation Integration:** Added ferro-nav.js to synchronize navigation across the ecosystem.
 * **UX Enhancements:** Implemented @view-transition for fluid, native-feeling cross-page navigation.
 * **Narrative Boot Sequence:** WebTerm now mirrors the homepage identity block (whoami, cat /etc/identity, status line) for improved continuity.

#### 🔧 Changed
 * **Code Refactoring:** Migrated styles from app.js and index.html into CSS variables and classes, ensuring a cleaner separation of presentation and logic.

### [1.2.0] - 2026-07-11
#### ✨ Added
 * **Hardened Backend:** Added strict input validation for SSH parameters, MAX_CONCURRENT_SESSIONS capping, and process-wide uncaughtException handlers.
 * **Improved UX:** Added automated reconnection prompts and login form submission guards to prevent race conditions.
 * **Security:** Implemented the Content-Security-Policy (CSP) meta tag.
 * **Deployment:** Added healthCheckPath and environment configuration via render.yaml.
#### 🔧 Changed
 * **Consolidation:** Unified disconnect messaging and reduced redundant terminal clear calls.
 * **Configuration:** Cleaned up config.js documentation and corrected logic in server.js.

#### 🐛 Fixed
 * **Stability:** Resolved a critical SyntaxError caused by duplicate WebSocket upgrade handlers and orphaned ALLOWED_ORIGINS references.
 * **Security:** Hardened origin checking by normalizing ALLOWED_ORIGIN strings.
 * **Integrity:** Restored standard Subresource Integrity (SRI) practices.
<div align="center">
<sub>Built with standard security practices for the <b>SecFerro Division</b>.</sub>
</div>

```
Anonymousik.is-a.dev
```
