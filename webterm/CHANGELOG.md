# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.3.0] - 2026-07-11

### Added
- `frontend/assets/ferro-theme.css` — shared design tokens + component
  styles (nav, drawer, status bar, badges, terminal chrome, login form)
  matching the anonymousik.is-a.dev visual language. Colors/font are
  **approximated from a screenshot** and isolated in a single `:root`
  block for exact correction — the fetched homepage gave exact copy and
  nav structure, not compiled CSS, so hex values are a best-effort match,
  not a verified one.
- `frontend/assets/ferro-nav.js` — renders the real site nav (Home /
  Projects / Scripts / Stack / Contact / GitHub) plus the "SecFerro
  Division" group (tmux_setup, Module Reference, Changelog), pulled from
  a live fetch of the homepage. **WebTerm has been added to that group**
  here — it was not previously linked from the main site nav anywhere.
- `@view-transition { navigation: auto; }` in ferro-theme.css — smooth
  cross-page transitions on supporting browsers (progressive enhancement,
  silently ignored elsewhere) instead of a hand-rolled SPA router. This is
  what makes moving between WebTerm and the rest of the site feel dynamic
  without adding a client-side routing framework.
- WebTerm boot sequence now echoes the homepage's own identity block
  (`$ whoami` / `$ cat /etc/identity` / SECFERRO status line) before the
  login prompt, for narrative + visual continuity with the homepage's
  terminal panel.

### Changed
- `index.html`, `app.js`: restyled from generic GitHub-dark palette to
  FERRO theme classes; inline JS style objects moved into
  `ferro-theme.css` (presentation out of behavior code).

### Action required on your side (not done here — I don't have this file)
- Add a `WebTerm · v1.3.0` entry to the **homepage's own** "SecFerro
  Division Series" nav list (next to `tmux_setup` / `Module Reference` /
  `Changelog`), pointing at `/scripts/webterm/`, so the link is
  discoverable from the homepage too, not just outbound from WebTerm.
- Verify `--ferro-*` color variables and `--ferro-font-mono` in
  `ferro-theme.css` against your actual site CSS/fonts, or share that
  file/repo path and I'll lock them to exact values.

## [1.2.0] - 2026-07-11

### Fixed
- **server.js**: removed duplicated `server.on("upgrade", ...)` handler and
  reference to undefined `ALLOWED_ORIGINS` (plural) left over from commit
  `9ed43d4` — this was a `SyntaxError` that crashed the process on every boot.
- **index.html**: restored a real SRI story instead of silently dropping
  `integrity` (see Security section below).

### Added
- **server.js**: input validation for `host`/`port`/`username`/`password` in
  the first WS message; per-connection cleanup guaranteed via a single
  `cleanup()` path; `MAX_CONCURRENT_SESSIONS` cap; `uncaughtException` /
  `unhandledRejection` guards so the process fails loudly instead of hanging
  in a broken state.
- **app.js**: reconnect prompt after an unexpected disconnect; guard against
  double-submitting the login form while a connection attempt is in flight;
  inline error messages instead of silent no-ops on invalid input.
- **index.html**: `Content-Security-Policy` meta tag restricting
  `script-src`/`connect-src` to the known CDN and backend origin —
  mitigates credential exfiltration via XSS even if a script gets injected.
- **render.yaml**: `healthCheckPath: /healthz`, `NODE_ENV=production`,
  `DEBUG`, `MAX_CONCURRENT_SESSIONS`, `SSH_CONNECT_TIMEOUT_MS` env vars.
- **package.json**: `engines.node >=18` pin; `lint:syntax` script
  (`node --check server.js`) for a pre-push sanity check.

### Security
- **Origin check hardened**: `ALLOWED_ORIGIN` is now normalized through
  `new URL(...).origin`, so a stray path or trailing slash in the Render
  dashboard env var can no longer silently break WS auth (root cause of the
  earlier 1006 Abnormal Closure).
- **Known limitation, not fixed here (needs a decision from you):** the WS
  endpoint has no authentication of its own — anything that can reach it
  can make the backend attempt an outbound TCP+SSH connection to any
  host:port it names, before credentials are checked. Origin-checking only
  stops browser pages from unauthorized origins; it does not stop a direct
  script/curl client. If this backend will ever be reachable from anywhere
  other than your private tunnel, add real session auth (JWT/shared secret
  checked server-side) or put Cloudflare Access / an IP allowlist in front
  of the Render service.
- **SRI**: previous version deleted `integrity="..."` entirely after a hash
  mismatch, instead of regenerating it. This build documents the exact
  `openssl` command to regenerate correct hashes; a hash was **not**
  fabricated here since this sandbox has no network access to
  `cdn.jsdelivr.net` to compute it correctly. Run the command in
  `index.html`'s comment and add the `integrity` attributes back before
  the next deploy.

### Changed
- **app.js**: reduced duplicate `term.clear()` logic; unified disconnect
  messaging (Polish, consistent wording).
- **config.js**: comments corrected; values unchanged (they were already
  correct: `wsUrl` includes the `-8mj1` Render subdomain suffix).
