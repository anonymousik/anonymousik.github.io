<div align="center">
# 🖥️ WebTerm
**A secure, modern, and fluid web-based SSH terminal emulator.**
Version

Node.js

Security

License: MIT
WebTerm is a robust terminal interface built for the web, delivering native-feeling cross-page navigation, stringent backend security, and seamless integration with the *anonymousik.is-a.dev* visual identity. Part of the **SecFerro Division** ecosystem.
Features • Security • Changelog
</div>
## 📑 Table of Contents
 * Key Features
 * Security Guidelines
 * Deployment
 * Changelog
   * 1.3.0 (2026-07-11)
   * 1.2.0 (2026-07-11)
## ✨ Key Features
 * **Fluid UX & Identity:** Utilizes @view-transition for seamless navigation and ferro-theme.css for a consistent, narrative-driven visual experience (mirrors the homepage identity block: whoami, cat /etc/identity).
 * **Secure Backend:** Strict input validation for SSH parameters, robust MAX_CONCURRENT_SESSIONS capping, and process-wide uncaughtException handling.
 * **Resilient Connections:** Automated reconnection prompts and login form submission guards to prevent race conditions.
 * **Ecosystem Integration:** Synchronized navigation via ferro-nav.js across the SecFerro Division group (tmux_setup, Module Reference, Changelog).
## 🛡️ Security Guidelines
> [!WARNING]
> **Vulnerability Disclaimer:** > The current WebSocket endpoint lacks internal session authentication (e.g., JWT). Origin-checking (ALLOWED_ORIGINS) prevents unauthorized browser-based access, but direct API calls (e.g., via curl) may still bypass this.
> **Recommendation:** It is highly recommended to gate the backend service behind **Cloudflare Access** or a strict IP allowlist if exposed to the public internet.
> 
 * **Content-Security-Policy (CSP):** WebTerm implements strict CSP meta tags to restrict script execution and connection origins.
 * **Subresource Integrity (SRI):** Standard SRI practices are enforced. If hash mismatches occur, regenerate integrity attributes using the command provided in index.html comments.
## 🚀 Deployment
WebTerm is configured for seamless deployment on platforms like Render.
 * **Render Ready:** Includes a render.yaml with pre-configured healthCheckPath and environment configurations.
 * **Node Engine:** Ensure you are using the pinned Node.js engine version specified in the configuration.
## 📝 Changelog
All notable changes to this project will be documented in this section. The format is based on Keep a Changelog.
### [1.3.0] - 2026-07-11
#### ✨ Added
 * **Visual Identity:** Introduced ferro-theme.css, consolidating design tokens and component styles to align with the *anonymousik.is-a.dev* visual language.
 * **Navigation Integration:** Added ferro-nav.js to synchronize navigation across the ecosystem, including the "SecFerro Division" group (tmux_setup, Module Reference, Changelog, and now WebTerm).
 * **UX Enhancements:** Implemented @view-transition for fluid, native-feeling cross-page navigation.
 * **Narrative Boot Sequence:** WebTerm now mirrors the homepage identity block (whoami, cat /etc/identity, status line) for improved continuity.
#### 🔧 Changed
 * **Code Refactoring:** Migrated styles from app.js and index.html into CSS variables and classes, ensuring a cleaner separation of presentation and logic.
### [1.2.0] - 2026-07-11
#### ✨ Added
 * **Hardened Backend:** Added strict input validation for SSH parameters, MAX_CONCURRENT_SESSIONS capping, and process-wide uncaughtException handlers.
 * **Improved UX:** Added automated reconnection prompts and login form submission guards to prevent race conditions.
 * **Security:** Implemented Content-Security-Policy (CSP) meta tag to restrict script execution and connection origins.
 * **Deployment:** Added healthCheckPath and environment configuration via render.yaml, along with Node.js engine pinning.
#### 🔧 Changed
 * **Consolidation:** Unified disconnect messaging and reduced redundant terminal clear calls.
 * **Configuration:** Cleaned up config.js documentation and corrected logic in server.js.
#### 🐛 Fixed
 * **Stability:** Resolved critical SyntaxError caused by duplicate WebSocket upgrade handlers and orphaned ALLOWED_ORIGINS references.
 * **Security:** Hardened origin checking by normalizing ALLOWED_ORIGIN strings, preventing WebSocket connection failures due to trailing slashes.
 * **Integrity:** Restored standard Subresource Integrity (SRI) practices.
#### 🛡️ Security Notes
 * **Vulnerability Disclaimer:** The current WebSocket endpoint lacks internal session authentication (e.g., JWT). Origin-checking prevents unauthorized browser-based access, but direct API calls (e.g., via curl) may still bypass this. It is recommended to gate the backend service behind Cloudflare Access or an IP allowlist if exposed to the public internet.
 * **SRI Implementation:** If hash mismatches occur, regenerate integrity attributes using the command provided in index.html comments.
<div align="center">


<i>Built with standard security practices for the SecFerro Division.</i>
</div>
