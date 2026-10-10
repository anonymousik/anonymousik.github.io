# CHANGELOG

> **SECFERRO DIVISION SERIES** — Termux Ultimate Setup  
> Maintained by [Anonymousik](https://github.com/Anonymousik) · [Anonymousik.is-a.dev](https://anonymousik.is-a.dev)  
> Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

> Features scheduled for upcoming releases.

### Planned
- `--update` flag: in-place script self-update via curl
- Module `Blockchain` — Foundry, Hardhat, Cast, ethers.js, web3.py
- Module `Cloud-Native` — AWS CLI, Azure CLI, GCP SDK, eksctl
- Module `Pentest-Pro` — Burp Suite CE bootstrap, OWASP ZAP, wfuzz
- Interactive TUI installer using `whiptail` / `dialog`
- Resume-on-failure: checkpoint system via `~/.secferro.state`
- Multi-architecture support: arm64, x86_64 auto-detection

---

## [5.0.0] — 2026-03-08 · codename: `IRONCLAD`

### ⚡ Breaking Changes
- Removed `set -euo pipefail` — replaced with per-command error handling (`sf_run` / `sf_try`) to prevent false aborts in restricted Android/Termux environments
- Replaced `ping` connectivity check with `curl` (ICMP blocked without root on Android API 24+)
- Menu numbering extended: options `1–7` replaced by `1–12` + `all`
- `$INSTALL_*` variable prefix renamed to `$M_*` (shorter, consistent namespace)

### ✨ Added — New Modules
- **Module `Data`** (07/12) — numpy, pandas, scikit-learn, Jupyter, polars, DuckDB, HuggingFace Transformers
- **Module `DevOps`** (08/12) — kubectl, Helm, k9s, Ansible, Terraform, GitHub CLI (`gh`), jq, yq, glances, autossh
- **Module `Media`** (09/12) — FFmpeg, exiftool, yt-dlp, aria2, Sherlock (username OSINT), Holehe (email OSINT)
- **Module `DB`** (10/12) — SQLite, MariaDB, Redis, SQLAlchemy, Alembic, Peewee, pgcli, mycli
- **Module `IoT`** (11/12) — esptool, pyserial, PlatformIO, paho-mqtt, aiocoap (MQTT + CoAP protocols)
- **Module `Game`** (12/12) — Lua 5.4, Ruby, Perl, pygame, pyglet

### ✨ Added — Core Infrastructure
- `preflight()` — intelligent pre-flight system with 9 automated checks
- `sf_loading()` / `sf_loading_done()` — animated spinner for long-running operations (git clone, rootfs download, etc.)
- `sf_fix()` — purple-accented auto-fix messages for self-healing operations
- `sf_step()` — full-width bordered ASCII section headers (`╔══╗` style)
- `sf_phase()` — sub-section separators with `[SECFERRO DIVISION]` branding
- Auto-removal of stale dpkg lock files (`lock-frontend`, `lock`, `apt/lists/lock`)
- Auto-switch to Cloudflare CDN mirror when primary repo unreachable
- Auto-invocation of `termux-setup-storage` when `~/storage` missing
- Auto-fix of `$HOME` permissions when directory not writable
- `~/tools` and `~/bin` directory scaffolding on first run
- `save_config()` now writes full module manifest + error count to `~/.secferro.conf`
- `--verbose` flag: full per-command stdout passthrough via `tee`

### ✨ Added — Shell Environment
- Zsh plugins: `zsh-history-substring-search` added alongside existing autosuggestions + syntax-highlighting
- Additional aliases: `scan`, `scan-fast`, `scan-full`, `tor-status`, `tor-ip`, `prox`, `anon`, `strip-meta`, `ffinfo`, `yml-check`, `gsync`, `jnb`, `jlab`, `pio`, `esp`
- `$PATH` auto-extended: `~/.npm-global/bin`, `~/go/bin`, `~/.cargo/bin`, `~/bin`, `~/.local/bin`

### ✨ Added — Cyber Module
- Holehe email OSINT tool (`pip install holehe`)
- Shodan + Censys API clients
- hashcat, john (password auditing)
- `masscan`, `tshark` (optional, soft-fail)

### ✨ Added — Tor Module
- Hardened `torrc`: ExcludeExitNodes `{RU},{CN},{BY},{KP},{IR}` with `StrictNodes 1`
- `DNSPort 5353` + `AutomapHostsOnResolve 1` for DNS-over-Tor
- Backup of existing `torrc` before overwrite

### 🔧 Changed
- `run_cmd()` → replaced by `sf_run()` (live tee output) + `sf_try()` (silent soft-fail)
- `pkg_install()` / `pkg_try()` / `pip_install()` / `npm_global()` — unified wrappers with consistent logging
- `pip install` now always uses `--break-system-packages` flag (required Termux 0.118+)
- Interactive menu accepts multi-selection (`1,3,5`) and `all` keyword
- `print_summary()` now shows context-aware next-steps per installed module
- `do_uninstall()` now requires typing `tak` (not just `t`) for confirmation

### 🐛 Fixed
- **Critical**: Script no longer silently hangs on `ping` (ICMP requires CAP_NET_RAW, blocked on Android without root)
- **Critical**: `set -euo pipefail` caused premature exit on `getprop` (returns non-zero outside Android shell context)
- **Critical**: `${PIPESTATUS[0]}` correctly captured after `tee` pipeline
- dpkg lock left from interrupted previous installs now auto-cleared
- Oh-My-Zsh installer: `RUNZSH=no CHSH=no` flags prevent interactive shell switch mid-script

### 🗑 Removed
- Spinner background-process approach (unreliable on low-memory devices) → replaced by `sf_loading()`
- `progress_bar()` using `seq` (spawned subshells per-character) → consolidated into `sf_progress()`

---

## [4.0.0] — 2025 · codename: `—`

### Added
- `--dry-run` flag: full simulation without package installation
- `--no-ui` flag: skip Zsh/Oh-My-Zsh configuration (headless deployments)
- `--verbose` / `--uninstall` / `--version` flags
- Module `Tor` — Tor daemon + ProxyChains-ng (dynamic chain mode)
- Module `Docker` — proot-distro + Ubuntu 22.04 LTS rootfs
- Powerlevel10k theme + zsh-autosuggestions + zsh-syntax-highlighting
- SSH key generation (ed25519) at end of install
- `~/.secferro.conf` install manifest
- `~/.secferro_install.log` timestamped operation log
- Animated progress bar (`progress_bar()`)
- `run_cmd()` wrapper with PIPESTATUS-aware error handling
- `check_environment()` with storage space verification
- Backup of existing `.zshrc` before overwrite

### Changed
- Modules restructured as discrete functions: `install_web()`, `install_android()`, etc.
- Interactive menu: multi-select support (`1,3,5`)
- MOTD injected as shell function (not raw echo) for reliable rendering

### Fixed
- Oh-My-Zsh install: `--unattended` flag prevents interactive prompt blocking script

---

## [3.0.0] — 2024

### Added
- `--dev <modules>` flag for unattended/automated mode
- Argument parser with `IFS=','` multi-module support
- Modular install functions per stack
- ANSI art banner (`print_banner()`)
- Modules: WebDev, Android, CyberSec, Fullstack

### Changed
- Monolithic script refactored into function-based architecture
- Oh-My-Zsh install moved to dedicated `setup_ui()` function

---

## [2.x] — 2024 (legacy)

### Summary
- Basic Termux environment setup
- Single-choice menu
- pkg installs without error handling

---

## [1.x] — 2023 (legacy)

### Summary  
- Initial monolithic script
- Hardcoded package list
- No modularity, no error handling, no logging

---

[Unreleased]: https://github.com/Anonymousik/scripts/compare/v5.0.0...HEAD
[5.0.0]: https://github.com/Anonymousik/scripts/releases/tag/v5.0.0
[4.0.0]: https://github.com/Anonymousik/scripts/releases/tag/v4.0.0
[3.0.0]: https://github.com/Anonymousik/scripts/releases/tag/v3.0.0
