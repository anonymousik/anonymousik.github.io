# Changelog
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
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
