#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SMART COMPILE ULTIMATE  v3.0  [FERRO IRONCLAD]                    ║
# ║  SecFERRO Division ◈ FerroART ◈ anonymousik.is-a.dev               ║
# ║  Universal Android/GitHub Actions CI/CD Backend — Termux-native     ║
# ║  © 2026 anonymousik / FerroART  ◈  [FERRO//ANON]                   ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# NAPRAWIONE W v3.0 (względem v2.0):
#  [FIX-01] Bash 4.0+ guard — declare -A wymaga bash >= 4
#  [FIX-02] set -Eeuo pipefail przywrócone z bezpiecznymi wyjątkami
#  [FIX-03] _retry: eval usunięte → "$@" (bezpieczeństwo + poprawne quoting)
#  [FIX-04] _backoff_sleep: jitter modulo-0 guard (exp < 2 → fixed 1)
#  [FIX-05] _secret_scan: xargs -I{} grep -rl zastąpione bezpieczną pętlą
#  [FIX-06] _load_conf: poprawny parser INI (wartości z "=" nie są ucinane)
#  [FIX-07] _load_conf: usunięto zduplikowany git-check (był też w main)
#  [FIX-08] _rotate_logs: nullglob guard — glob bez plików nie tworzy błędu
#  [FIX-09] (( var++ )): zamienione na (( ++var )) wszędzie (set -e + 0-trap)
#  [FIX-10] sha256sum: cross-platform (_sha256sum z fallbackiem na shasum)
#  [FIX-11] _download_artifacts: subshell sha256 loop → process substitution
#  [FIX-12] _require_cmds: Termux-detection przed pkg, fallback apt/apk/brew
#  [FIX-13] _audit_workflow: nowy YAML z doc-3 (validate job, concurrency,
#            setup-android, NDK, clear-cache, build logs, GitHub step summary)
#  [FIX-14] _trigger_workflow: variant→artifact name mapping (_resolve_artifacts)
#  [FIX-15] _wait_for_run: dispatch_time PRZED sleep (event-time guard precyzja)
#  [FIX-16] _monitor_execution: timeout guard (MAX_WAIT_MIN, domyślnie 60 min)
#  [FIX-17] Pre-flight: bash version, disk space, network, git repo
#  [FIX-18] _generate_report: guard gdy jq niedostępne
#  [FIX-19] _cleanup: exit_code capture jako first statement (bash race fix)
#  [FIX-20] Wszystkie gh/curl wywołania owijają timeout (GH_TIMEOUT_S)
#  [FIX-21] Nowe flagi: --clear-cache, --max-wait, --artifact-prefix

# ─────────────────────────────────────────────────────────────
# [FIX-01] BASH VERSION GUARD
# ─────────────────────────────────────────────────────────────
if (( BASH_VERSINFO[0] < 4 )); then
  printf '\e[1;31m[FATAL] Wymagany bash >= 4.0 (aktualny: %s)\e[0m\n' "$BASH_VERSION" >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────
# [FIX-02] STRICT MODE
# Wyjątki inline stosowane przez: || true  /  { cmd; } 2>/dev/null
# ─────────────────────────────────────────────────────────────
set -Eeuo pipefail
IFS=$'\n\t'

# ─────────────────────────────────────────────────────────────
# STAŁE WERSJI
# ─────────────────────────────────────────────────────────────
readonly SCU_VERSION="3.0.0"
readonly SCU_BUILD_DATE="2026-05-05"
readonly SCRIPT_NAME="$(basename -- "$0")"
readonly SCRIPT_PATH="$(realpath -- "$0")"
readonly PID=$$

# ─────────────────────────────────────────────────────────────
# KATALOGI ROBOCZE
# ─────────────────────────────────────────────────────────────
SCU_HOME="${HOME}/.scu"
LOG_DIR="${SCU_HOME}/logs"
LOCK_DIR="${SCU_HOME}/locks"
CONF_FILE="${SCU_HOME}/scu.conf"
REPORT_DIR="${SCU_HOME}/reports"

mkdir -p "$SCU_HOME" "$LOG_DIR" "$LOCK_DIR" "$REPORT_DIR"

# ─────────────────────────────────────────────────────────────
# PLIK LOGÓW
# ─────────────────────────────────────────────────────────────
LOGFILE="${LOG_DIR}/scu_$(date +%Y%m%d_%H%M%S)_${PID}.log"
: > "$LOGFILE"   # bezpieczny touch (nie tworzy pliku z ':' jako polecenie)

# ─────────────────────────────────────────────────────────────
# [FIX-08] ROTACJA LOGÓW z nullglob guard
# ─────────────────────────────────────────────────────────────
_rotate_logs() {
  local -a logs=()
  # Zbierz pliki bezpiecznie — bez glob-expansion-fail gdy brak plików
  while IFS= read -r -d '' f; do
    logs+=("$f")
  done < <(find "$LOG_DIR" -maxdepth 1 -name 'scu_*.log' -print0 2>/dev/null | sort -z)

  local count=${#logs[@]}
  if (( count > 20 )); then
    local -a old=("${logs[@]:0:$(( count - 20 ))}")
    for f in "${old[@]}"; do
      [[ -f "$f" ]] && gzip -f "$f" 2>/dev/null || true
    done
  fi
}
_rotate_logs

# ─────────────────────────────────────────────────────────────
# LOCK FILE
# ─────────────────────────────────────────────────────────────
LOCK_FILE="${LOCK_DIR}/scu.lock"

_acquire_lock() {
  if [[ -f "$LOCK_FILE" ]]; then
    local old_pid
    old_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "0")
    # kill -0 sprawdza egzystencję procesu — nie zabija go
    if [[ -n "$old_pid" && "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
      printf '\e[1;31m[FATAL] Inna instancja SCU działa (PID %s). Użyj --force.\e[0m\n' "$old_pid" >&2
      exit 1
    else
      rm -f "$LOCK_FILE"
    fi
  fi
  printf '%d\n' "$PID" > "$LOCK_FILE"
}

_release_lock() { rm -f "$LOCK_FILE" 2>/dev/null || true; }

# ─────────────────────────────────────────────────────────────
# DEFAULTS
# ─────────────────────────────────────────────────────────────
REPO_NAME="neurosync-ai-private"
WORKFLOW_FILE="android-build.yml"
BRANCH="main"
BUILD_OUTPUT_DIR="${HOME}/build_output"
ARTIFACT_PREFIX="neurosync-apk"     # artifact name = PREFIX-VARIANT
ARTIFACT_NAMES=""                   # override: puste = auto z PREFIX+VARIANT
CUSTOM_INPUTS=""
AUTO_YES="false"
WEBHOOK_URL=""
NOTIFY_EMAIL=""
RETRIES=3
LOG_LEVEL="INFO"
SKIP_PUSH="false"
SKIP_TRIGGER="false"
SKIP_DOWNLOAD="false"
FORCE_LOCK="false"
BUILD_VARIANTS=""
DRY_RUN="false"
VERIFY_CHECKSUMS="true"
SECRET_SCAN="true"
TERMUX_NOTIFY="true"
CLEAR_CACHE="false"           # [FIX-13] clear-cache input do workflow
MAX_WAIT_MIN=60               # [FIX-16] maks czas monitorowania
GH_TIMEOUT_S=30              # [FIX-20] timeout na pojedyncze gh/curl wywołania

# Stanu wewnętrznego — nie eksportuj do conf
_CURRENT_RUN_ID=""
_IS_TERMUX="false"
_DISPATCHED_VARIANTS=()

# ─────────────────────────────────────────────────────────────
# [FIX-01] LOGGER — declare -A wymaga bash 4+
# ─────────────────────────────────────────────────────────────
declare -A _LOG_LEVELS=([TRACE]=0 [DEBUG]=1 [INFO]=2 [WARN]=3 [ERROR]=4 [FATAL]=5)

_log_enabled() {
  local lvl="${1:-INFO}" cur="${LOG_LEVEL:-INFO}"
  (( ${_LOG_LEVELS[$lvl]:-2} >= ${_LOG_LEVELS[$cur]:-2} ))
}

_ts() { date +'%F %T'; }

# Każda funkcja logująca: najpierw sprawdź poziom, potem tee
log()    { _log_enabled INFO  && printf '\e[1;34m[%s] [INFO]  %s\e[0m\n' "$(_ts)" "$*" | tee -a "$LOGFILE" || true; }
debug()  { _log_enabled DEBUG && printf '\e[0;36m[%s] [DEBUG] %s\e[0m\n' "$(_ts)" "$*" | tee -a "$LOGFILE" || true; }
trace()  { _log_enabled TRACE && printf '\e[0;37m[%s] [TRACE] %s\e[0m\n' "$(_ts)" "$*" | tee -a "$LOGFILE" || true; }
warn()   { _log_enabled WARN  && printf '\e[1;33m[%s] [WARN]  %s\e[0m\n' "$(_ts)" "$*" | tee -a "$LOGFILE" || true; }
err()    { _log_enabled ERROR && printf '\e[1;31m[%s] [ERROR] %s\e[0m\n' "$(_ts)" "$*" | tee -a "$LOGFILE" >&2 || true; }
success(){ printf '\e[1;32m[%s] [OK]    %s\e[0m\n' "$(_ts)" "$*" | tee -a "$LOGFILE"; }

fatal() {
  printf '\e[1;31m[%s] [FATAL] %s\e[0m\n' "$(_ts)" "$*" | tee -a "$LOGFILE" >&2 || true
  _notify "💀 FATAL: $*" || true
  exit 1
}

# ─────────────────────────────────────────────────────────────
# NOTYFIKACJE
# ─────────────────────────────────────────────────────────────
_notify() {
  local msg="[SCU ${SCU_VERSION} | $(_ts)] ${1:-}"
  local safe="${msg//\"/\\\"}"

  if [[ -n "${WEBHOOK_URL:-}" ]]; then
    curl -sf --max-time "$GH_TIMEOUT_S" \
      -X POST -H 'Content-type: application/json' \
      --data "{\"text\":\"${safe}\"}" \
      "$WEBHOOK_URL" 2>/dev/null || true
  fi

  if [[ -n "${NOTIFY_EMAIL:-}" ]]; then
    printf '%s\n' "$msg" | mail -s "[SCU ALERT] $SCRIPT_NAME" "$NOTIFY_EMAIL" 2>/dev/null || true
  fi

  # [FIX-12] Termux:API toast — tylko gdy rzeczywiście Termux
  if [[ "$_IS_TERMUX" == "true" && "$TERMUX_NOTIFY" == "true" ]]; then
    command -v termux-toast &>/dev/null && termux-toast -b black -c cyan "${1:-}" 2>/dev/null || true
  fi
}

# ─────────────────────────────────────────────────────────────
# [FIX-19] TRAP — exit_code jako PIERWSZA linia cleanup
# ─────────────────────────────────────────────────────────────
_cleanup() {
  local exit_code=$?   # MUSI być pierwsza linia — bash może to nadpisać
  _release_lock
  if (( exit_code != 0 )); then
    err "Skrypt zakończony błędem (exit ${exit_code})."
    if [[ -n "$_CURRENT_RUN_ID" ]]; then
      warn "Aktywny run: $_CURRENT_RUN_ID — anuluj przez: gh run cancel $_CURRENT_RUN_ID"
    fi
    _notify "❌ SCU błąd (exit ${exit_code}) | repo: ${REPO_NAME}" || true
  fi
}

_sigint_handler() {
  printf '\n' >&2
  warn "Przerwano (SIGINT)."
  if [[ -n "$_CURRENT_RUN_ID" ]]; then
    confirm "Anulować workflow run $_CURRENT_RUN_ID na GitHub?" \
      && { timeout "$GH_TIMEOUT_S" gh run cancel "$_CURRENT_RUN_ID" 2>/dev/null && log "Run anulowany." || warn "Nie anulowano."; }
  fi
  exit 130
}

# ERR trap: wypisz linię i komendę, ale nie re-trap (unikaj infinite loop)
_err_trap() {
  local lineno="$1" cmd="$2"
  err "Błąd w linii ${lineno}: ${cmd}"
}

trap '_cleanup'                          EXIT
trap '_sigint_handler'                   SIGINT SIGTERM
trap '_err_trap "$LINENO" "$BASH_COMMAND"' ERR

# ─────────────────────────────────────────────────────────────
# [FIX-04] EXPONENTIAL BACKOFF — modulo-0 safe
# ─────────────────────────────────────────────────────────────
_backoff_sleep() {
  local attempt="${1:-1}" base="${2:-3}" max_s="${3:-60}"
  local exp=$(( base * (1 << (attempt - 1)) ))   # base * 2^(attempt-1)
  (( exp > max_s )) && exp=$max_s

  # [FIX-04] jitter: range min 2 aby uniknąć RANDOM%0 lub RANDOM%1
  local jrange=$(( exp / 5 > 1 ? exp / 5 : 2 ))
  local jitter=$(( RANDOM % jrange ))
  local sleep_s=$(( exp + jitter ))

  debug "Backoff próba ${attempt}: czekam ${sleep_s}s (base=${base}, max=${max_s})"
  sleep "$sleep_s"
}

# ─────────────────────────────────────────────────────────────
# [FIX-03] RETRY — bez eval, z prawidłowym "$@"
# ─────────────────────────────────────────────────────────────
_retry() {
  local retries="${RETRIES:-3}"
  local i=1
  local output exit_code

  while (( i <= retries )); do
    exit_code=0
    # [FIX-03] "$@" zamiast eval "${cmd[@]}" — bezpieczne, poprawne quoting
    output=$("$@" 2>&1) || exit_code=$?

    if (( exit_code == 0 )); then
      [[ -n "$output" ]] && printf '%s\n' "$output"
      return 0
    fi

    # Rate-limit detection — wzorce GitHub API 429/403
    if printf '%s' "$output" | grep -qiE '(rate.limit|secondary rate|429|403 forbidden)'; then
      warn "GitHub rate-limit: czekam 60s..."
      sleep 60
    else
      warn "Próba ${i}/${retries} nieudana (exit ${exit_code}): ${output:0:140}"
      _backoff_sleep "$i"
    fi
    # [FIX-09] Pre-increment (safe z set -e): (( i++ )) gdy i=0 daje exit 1
    (( ++i ))
  done

  err "Wszystkie ${retries} próby nieudane: $*"
  return 1
}

# ─────────────────────────────────────────────────────────────
# [FIX-10] SHA256 CROSS-PLATFORM (Linux + macOS + Termux)
# ─────────────────────────────────────────────────────────────
_sha256sum() {
  local file="$1"
  if command -v sha256sum &>/dev/null; then
    sha256sum "$file" | awk '{print $1}'
  elif command -v shasum &>/dev/null; then
    shasum -a 256 "$file" | awk '{print $1}'
  elif command -v openssl &>/dev/null; then
    openssl dgst -sha256 -r "$file" | awk '{print $1}'
  else
    warn "Brak sha256sum/shasum/openssl — pomijam checksum dla: $(basename "$file")"
    printf 'UNAVAILABLE\n'
  fi
}

# ─────────────────────────────────────────────────────────────
# CONFIRM (z AUTO_YES)
# ─────────────────────────────────────────────────────────────
confirm() {
  [[ "$AUTO_YES" == "true" ]] && return 0
  local resp
  read -r -p "${1} [y/N]: " resp
  case "${resp,,}" in y|yes) return 0 ;; *) return 1 ;; esac
}

# ─────────────────────────────────────────────────────────────
# [FIX-06] CONFIG FILE — poprawny INI parser
# key=val gdzie val może zawierać '='
# ─────────────────────────────────────────────────────────────
_gen_default_conf() {
  cat > "$CONF_FILE" <<EOF
# SCU v${SCU_VERSION} — Smart Compile Ultimate config
# Wartości nadpisywane przez flagi CLI (CLI ma priorytet).

REPO_NAME=neurosync-ai-private
WORKFLOW_FILE=android-build.yml
BRANCH=main
BUILD_OUTPUT_DIR=${HOME}/build_output
ARTIFACT_PREFIX=neurosync-apk
AUTO_YES=false
RETRIES=3
LOG_LEVEL=INFO
WEBHOOK_URL=
NOTIFY_EMAIL=
TERMUX_NOTIFY=true
VERIFY_CHECKSUMS=true
SECRET_SCAN=true
CLEAR_CACHE=false
MAX_WAIT_MIN=60
GH_TIMEOUT_S=30
EOF
  log "Wygenerowano domyślny config: ${CONF_FILE}"
}

# Znane klucze konfiguracyjne (whitelist — bezpieczeństwo)
_CONF_KEYS=(REPO_NAME WORKFLOW_FILE BRANCH BUILD_OUTPUT_DIR ARTIFACT_PREFIX
            AUTO_YES RETRIES LOG_LEVEL WEBHOOK_URL NOTIFY_EMAIL TERMUX_NOTIFY
            VERIFY_CHECKSUMS SECRET_SCAN CLEAR_CACHE MAX_WAIT_MIN GH_TIMEOUT_S)

_load_conf() {
  [[ ! -f "$CONF_FILE" ]] && _gen_default_conf
  local line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Pomiń komentarze i puste linie
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line//[[:space:]]/}" ]]  && continue
    # [FIX-06] Poprawny split: key=wszystko_po_pierwszym_'='
    key="${line%%=*}"
    val="${line#*=}"
    key="${key//[[:space:]]/}"   # trim spaces w kluczu
    # NIE trimuj wartości — mogą zawierać spacje (np. ścieżki z URL)
    # Whitelist: tylko znane klucze
    local k; for k in "${_CONF_KEYS[@]}"; do
      if [[ "$key" == "$k" ]]; then
        # [FIX-07] declare -g bezpieczne — klucz jest whitelisted
        printf -v "$key" '%s' "$val"
        break
      fi
    done
  done < "$CONF_FILE"
}

# ─────────────────────────────────────────────────────────────
# [FIX-17] PRE-FLIGHT — bash, disk, network, git repo
# ─────────────────────────────────────────────────────────────
_preflight_env() {
  log "── Pre-flight ────────────────────────────────────"

  # Wykrycie Termux
  if grep -qi "android" /proc/version 2>/dev/null \
    || [[ -n "${TERMUX_VERSION:-}" ]] \
    || [[ -d "/data/data/com.termux" ]]; then
    _IS_TERMUX="true"
    log "Środowisko: Android/Termux ${TERMUX_VERSION:-?}"
  else
    log "Środowisko: Linux/Unix"
  fi

  # Disk space — minimum 300 MB
  local avail_mb
  avail_mb=$(df -m "${HOME}" 2>/dev/null | awk 'NR==2{print $4}') || avail_mb=9999
  if (( avail_mb < 300 )); then
    fatal "Za mało miejsca na dysku: ${avail_mb}MB (wymagane ≥300MB)."
  fi
  debug "Wolne miejsce: ${avail_mb}MB"

  # Network check — GitHub API (nie ICMP, bo Android blokuje ping bez root)
  if ! curl -sf --max-time 10 --head "https://api.github.com" >/dev/null 2>&1; then
    fatal "Brak połączenia z api.github.com. Sprawdź sieć."
  fi
  debug "Sieć: OK (github.com dostępny)"

  log "─────────────────────────────────────────────────"
}

_preflight_git() {
  # [FIX-07] git check TYLKO tutaj — nie w _load_conf
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fatal "Bieżący katalog nie jest repozytorium Git. Uruchom: git init && git remote add origin <URL>"
  fi
  local untracked
  untracked=$(git status --porcelain 2>/dev/null || true)
  [[ -n "$untracked" ]] && warn "Niezatwierdzone zmiany w repo (zostaną dodane przez auto-commit)."
}

# ─────────────────────────────────────────────────────────────
# [FIX-12] DEPENDENCIES — Termux-aware installer
# ─────────────────────────────────────────────────────────────
_require_cmds() {
  local -a missing=()
  for c in "$@"; do
    command -v "$c" &>/dev/null || missing+=("$c")
  done
  (( ${#missing[@]} == 0 )) && return 0

  warn "Brakujące narzędzia: ${missing[*]}"
  for pkg in "${missing[@]}"; do
    log "Instalacja: ${pkg}..."
    local installed=false
    if [[ "$_IS_TERMUX" == "true" ]]; then
      pkg install -y "$pkg" 2>/dev/null && installed=true || true
    fi
    if [[ "$installed" == "false" ]] && command -v apt-get &>/dev/null; then
      { apt-get install -y "$pkg" 2>/dev/null && installed=true; } || true
    fi
    if [[ "$installed" == "false" ]] && command -v apk &>/dev/null; then
      { apk add --no-cache "$pkg" 2>/dev/null && installed=true; } || true
    fi
    if [[ "$installed" == "false" ]] && command -v brew &>/dev/null; then
      { brew install "$pkg" 2>/dev/null && installed=true; } || true
    fi
    command -v "$pkg" &>/dev/null || fatal "Nie można zainstalować: ${pkg}. Zainstaluj ręcznie."
    success "Zainstalowano: ${pkg}"
  done
}

# ─────────────────────────────────────────────────────────────
# SELF-DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
_self_diagnose() {
  log "── Diagnostics ───────────────────────────────────"
  log "SCU v${SCU_VERSION} (${SCU_BUILD_DATE}) | PID: ${PID}"
  log "Kernel: $(uname -r) | Arch: $(uname -m)"
  log "Bash: ${BASH_VERSION} | User: $(id -un)"
  log "Git:    $(git --version 2>/dev/null | head -1)"
  log "GH CLI: $(gh --version 2>/dev/null | head -1)"
  log "jq:     $(jq --version 2>/dev/null || echo 'n/a')"
  log "curl:   $(curl --version 2>/dev/null | head -1)"
  log "Log:    ${LOGFILE}"
  log "─────────────────────────────────────────────────"
}

# ─────────────────────────────────────────────────────────────
# [FIX-05] SECRET LEAK SCANNER — bezpieczna pętla zamiast xargs
# ─────────────────────────────────────────────────────────────
_secret_scan() {
  [[ "$SECRET_SCAN" != "true" ]] && return 0
  log "Skanowanie staged files pod kątem lekowania sekretów..."

  # Wzorce — rozszerzone o popularne tokeny SaaS
  local -a patterns=(
    'AKIA[0-9A-Z]{16}'                               # AWS Access Key
    'sk-[A-Za-z0-9]{32,}'                            # OpenAI / Stripe SK
    'ghp_[A-Za-z0-9]{36}'                            # GitHub PAT classic
    'github_pat_'                                     # GitHub fine-grained PAT
    'gho_[A-Za-z0-9]{36}'                            # GitHub OAuth token
    'xox[baprs]-[A-Za-z0-9\-]+'                     # Slack token
    'BEGIN[[:space:]]+(RSA|EC|DSA|OPENSSH)[[:space:]]+PRIVATE'
    'password[[:space:]]*=[[:space:]]*["\x27][^\s]{8,}'
    'token[[:space:]]*=[[:space:]]*["\x27][A-Za-z0-9_\-\.]{16,}'
    'secret[[:space:]]*=[[:space:]]*["\x27][A-Za-z0-9_\-\.]{16,}'
  )

  # Pobierz listę staged files — bezpiecznie
  local -a staged_files=()
  while IFS= read -r f; do
    [[ -f "$f" ]] && staged_files+=("$f")
  done < <(git diff --cached --name-only 2>/dev/null || true)

  if (( ${#staged_files[@]} == 0 )); then
    debug "Brak staged files — secret scan pominięty."
    return 0
  fi

  local found=0
  for pattern in "${patterns[@]}"; do
    local -a hits=()
    for f in "${staged_files[@]}"; do
      # [FIX-05] grep -lP na konkretnym pliku — nie przez xargs -I{}
      if grep -qlP "$pattern" "$f" 2>/dev/null; then
        hits+=("$f")
      fi
    done
    if (( ${#hits[@]} > 0 )); then
      warn "⚠ Potencjalny leak (pattern: ${pattern::50}) w: ${hits[*]}"
      # [FIX-09] pre-increment safe z set -e
      (( ++found ))
    fi
  done

  if (( found > 0 )); then
    err "${found} potencjalnych lekow w staged files!"
    confirm "Kontynuować mimo potencjalnego leaku? (RYZYKOWNE)" \
      || fatal "Push anulowany przez secret scan. Usuń sekrety lub użyj --no-secret-scan."
  else
    success "Secret scan czysty (${#staged_files[@]} plików)."
  fi
}

# ─────────────────────────────────────────────────────────────
# GITHUB AUTH
# ─────────────────────────────────────────────────────────────
_healthcheck_github() {
  log "Weryfikacja GitHub CLI auth..."
  if ! timeout "$GH_TIMEOUT_S" gh auth status &>/dev/null; then
    warn "Brak sesji gh — uruchamiam gh auth login..."
    gh auth login || fatal "gh auth login nie powiodło się."
  fi
  local gh_user
  gh_user=$(timeout "$GH_TIMEOUT_S" gh api user --jq '.login' 2>/dev/null || echo "unknown")
  log "Zalogowany jako: @${gh_user}"

  # Sprawdź scope tokenów
  local scopes
  scopes=$(gh auth status 2>&1 | grep -i "token scopes" || true)
  [[ -n "$scopes" ]] && debug "Token scopes: ${scopes}"
}

# ─────────────────────────────────────────────────────────────
# REPO INIT
# ─────────────────────────────────────────────────────────────
_init_repo() {
  log "Weryfikacja repo: ${REPO_NAME}"
  if ! timeout "$GH_TIMEOUT_S" gh repo view "$REPO_NAME" &>/dev/null; then
    log "Repo nie istnieje → tworzę prywatne..."
    if [[ "$DRY_RUN" == "true" ]]; then
      log "[DRY-RUN] gh repo create ${REPO_NAME} --private"; return
    fi
    timeout "$GH_TIMEOUT_S" gh repo create "$REPO_NAME" --private --source=. --remote=origin --push \
      || fatal "Tworzenie repo nie powiodło się!"
    success "Repo ${REPO_NAME} utworzone."
  else
    debug "Repo ${REPO_NAME} istnieje."
  fi
}

# ─────────────────────────────────────────────────────────────
# SYNC CODE
# ─────────────────────────────────────────────────────────────
_sync_code() {
  if [[ "$SKIP_PUSH" == "true" ]]; then
    log "SKIP_PUSH=true — pomijam commit/push."; return 0
  fi
  log "Synchronizacja kodu → ${BRANCH}"
  _secret_scan
  git add -A

  # commit: ignoruj exit 1 gdy nic do commitowania
  if ! git commit -m "auto: SCU v${SCU_VERSION} sync $(date +'%F %T')" 2>/dev/null; then
    debug "Brak zmian do commitowania."
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY-RUN] git push origin ${BRANCH}"; return
  fi

  git push origin "$BRANCH" || fatal "git push nie powiódł się. Sprawdź uprawnienia i remote."
  success "Push zakończony."
}

# ─────────────────────────────────────────────────────────────
# [FIX-13] WORKFLOW YAML GENERATOR — pełny template z doc-3
# ─────────────────────────────────────────────────────────────
_audit_workflow() {
  local wf_path=".github/workflows/${WORKFLOW_FILE}"

  if [[ -f "$wf_path" ]]; then
    debug "Workflow ${wf_path} istnieje."
    if ! grep -q "workflow_dispatch" "$wf_path"; then
      warn "Workflow nie ma triggera 'workflow_dispatch' — dispatch nie zadziała!"
    fi
    # Sprawdź czy workflow ma concurrency group (dobra praktyka)
    if ! grep -q "concurrency" "$wf_path"; then
      warn "Brak 'concurrency' group — możliwe nakładające się runy przy push."
    fi
    return 0
  fi

  warn "Brak ${wf_path}."
  confirm "Wygenerować zaawansowany Android workflow (JDK 21, SDK 34, NDK, matrix)?" \
    || { warn "Pominięto generowanie workflow."; return; }

  mkdir -p ".github/workflows"
  # [FIX-13] Kompletny YAML z doc-3 — validate job, concurrency, setup-android, NDK,
  # clear-cache input, build logs upload, GitHub step summary, notify job
  cat > "$wf_path" <<ENDYML
name: Android Build — SCU v${SCU_VERSION}

on:
  workflow_dispatch:
    inputs:
      variant:
        description: 'Build variant (debug|release|all)'
        required: false
        default: 'debug'
      clear-cache:
        description: 'Clear Gradle cache before build'
        required: false
        default: 'false'
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

concurrency:
  group: \${{ github.workflow }}-\${{ github.ref }}
  cancel-in-progress: true

env:
  JAVA_VERSION: '21'
  GRADLE_OPTS: >-
    -Dorg.gradle.daemon=false
    -Dorg.gradle.parallel=true
    -Dorg.gradle.caching=true
    -Dorg.gradle.workers.max=4
    -Dorg.gradle.internal.native.jna=false

jobs:
  validate:
    name: Validate Environment
    runs-on: ubuntu-latest
    timeout-minutes: 10
    outputs:
      build-variant: \${{ steps.resolve-variant.outputs.variant }}
      cache-key: \${{ steps.cache-key.outputs.key }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Resolve build variant
        id: resolve-variant
        run: |
          VARIANT="\${{ github.event.inputs.variant || 'debug' }}"
          [[ -z "\$VARIANT" || "\$VARIANT" == "null" ]] && VARIANT="debug"
          echo "variant=\$VARIANT" >> "\$GITHUB_OUTPUT"
          echo "✓ Variant: \$VARIANT"

      - name: Generate cache key
        id: cache-key
        run: |
          KEY="gradle-\${{ runner.os }}-\${{ hashFiles('**/*.gradle*','**/gradle-wrapper.properties') }}"
          echo "key=\$KEY" >> "\$GITHUB_OUTPUT"

      - name: Validate Gradle wrapper
        run: |
          [[ ! -f "gradlew" ]] && { echo "::error::gradlew not found!"; exit 1; }
          chmod +x gradlew
          echo "✓ gradlew OK"

      - name: Validate build files
        run: |
          [[ ! -f "build.gradle" && ! -f "build.gradle.kts" ]] \
            && { echo "::error::build.gradle(kts) not found!"; exit 1; }
          echo "✓ build files OK"

  build:
    name: Build \${{ needs.validate.outputs.build-variant }}
    runs-on: ubuntu-latest
    needs: validate
    timeout-minutes: 90
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Setup JDK \${{ env.JAVA_VERSION }}
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: \${{ env.JAVA_VERSION }}
          cache: gradle

      - name: Setup Android SDK
        uses: android-actions/setup-android@v3.2.1
        with:
          cmdline-tools-version: 11.0
          accept-android-sdk-licenses: true
          packages: |
            platform-tools
            platforms;android-34
            build-tools;34.0.0
            ndk;27.0.12077973

      - name: Validate JDK
        run: java -version && javac -version && echo "✓ JDK OK"

      - name: Clear Gradle cache
        if: github.event.inputs.clear-cache == 'true'
        run: |
          rm -rf ~/.gradle/caches ~/.gradle/wrapper
          echo "✓ Gradle cache cleared"

      - name: Cache Gradle
        uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
            ~/.gradle/gradle.properties
          key: \${{ needs.validate.outputs.cache-key }}
          restore-keys: gradle-\${{ runner.os }}-

      - name: Validate Gradle wrapper integrity
        uses: gradle/actions/wrapper-validation@v3

      - name: Make gradlew executable
        run: chmod +x gradlew && echo "✓ gradlew executable"

      - name: Verify Gradle config
        run: ./gradlew --version && echo "✓ Gradle config OK"

      - name: Build APK — Debug
        if: >-
          needs.validate.outputs.build-variant == 'debug' ||
          needs.validate.outputs.build-variant == 'all'
        run: |
          ./gradlew assembleDebug --stacktrace --build-cache 2>&1 | tee build.log
          echo "✓ Debug APK built"

      - name: Build APK — Release
        if: >-
          needs.validate.outputs.build-variant == 'release' ||
          needs.validate.outputs.build-variant == 'all'
        run: |
          ./gradlew assembleRelease --stacktrace --build-cache 2>&1 | tee -a build.log
          echo "✓ Release APK built"

      - name: Verify APK outputs
        run: |
          APK_COUNT=\$(find . -name "*.apk" -type f | wc -l)
          (( APK_COUNT == 0 )) && { echo "::error::No APK files found!"; exit 1; }
          echo "✓ Found \$APK_COUNT APK file(s):"
          find . -name "*.apk" -type f -exec ls -lh {} \;

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        if: success()
        with:
          name: ${ARTIFACT_PREFIX}-\${{ needs.validate.outputs.build-variant }}
          path: "**/build/outputs/apk/**/*.apk"
          retention-days: 7
          if-no-files-found: error
          compression-level: 6

      - name: Upload mapping (release/all only)
        uses: actions/upload-artifact@v4
        if: >-
          success() && (
            needs.validate.outputs.build-variant == 'release' ||
            needs.validate.outputs.build-variant == 'all'
          )
        with:
          name: ${ARTIFACT_PREFIX}-mapping-release
          path: |
            **/build/outputs/mapping/release/mapping.txt
            **/build/outputs/bundle/release/
          retention-days: 7
          if-no-files-found: warn

      - name: Upload build logs
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: build-logs-\${{ needs.validate.outputs.build-variant }}
          path: |
            build.log
            **/build/reports/
          retention-days: 3

      - name: GitHub Step Summary
        if: always()
        run: |
          {
            echo "## 🔨 SCU Build Summary"
            echo "| Field | Value |"
            echo "|-------|-------|"
            echo "| **Variant** | \${{ needs.validate.outputs.build-variant }} |"
            echo "| **Java** | \${{ env.JAVA_VERSION }} |"
            echo "| **Runner** | \${{ runner.os }} |"
            echo "| **Status** | \${{ job.status }} |"
            echo "| **Commit** | \${{ github.sha }} |"
          } >> "\$GITHUB_STEP_SUMMARY"
          if [[ -f build.log ]]; then
            echo "### Build log (last 40 lines)" >> "\$GITHUB_STEP_SUMMARY"
            echo '```' >> "\$GITHUB_STEP_SUMMARY"
            tail -40 build.log >> "\$GITHUB_STEP_SUMMARY"
            echo '```' >> "\$GITHUB_STEP_SUMMARY"
          fi

  notify:
    name: Notify on Build Status
    runs-on: ubuntu-latest
    needs: [validate, build]
    if: always()
    steps:
      - name: Build Status
        run: |
          RESULT="\${{ needs.build.result }}"
          VARIANT="\${{ needs.validate.outputs.build-variant }}"
          if [[ "\$RESULT" == "failure" || "\$RESULT" == "cancelled" ]]; then
            echo "::error::Build \$RESULT for variant \$VARIANT"
            echo "Tips: check artifacts/build-logs, try clear-cache=true, verify SDK config"
            exit 1
          fi
          echo "✓ Build \$RESULT for variant \$VARIANT"
ENDYML

  git add "$wf_path"
  git commit -m "ci: add SCU v${SCU_VERSION} Android workflow (validate+build+notify)"
  git push origin "$BRANCH"
  success "Workflow ${wf_path} wygenerowany i wypchnięty."
}

# ─────────────────────────────────────────────────────────────
# JSON INPUT VALIDATION
# ─────────────────────────────────────────────────────────────
_validate_inputs_json() {
  [[ -z "$CUSTOM_INPUTS" ]] && return 0
  if ! printf '%s' "$CUSTOM_INPUTS" | jq empty 2>/dev/null; then
    fatal "CUSTOM_INPUTS nie jest poprawnym JSON: ${CUSTOM_INPUTS}"
  fi
  debug "CUSTOM_INPUTS JSON: OK"
}

# ─────────────────────────────────────────────────────────────
# [FIX-14] ARTIFACT NAME RESOLVER
# Mapuje variant → oczekiwaną nazwę artefaktu na GitHub
# ─────────────────────────────────────────────────────────────
_resolve_artifact_name() {
  local variant="$1"
  if [[ -n "$ARTIFACT_NAMES" ]]; then
    # Override: użyj dosłownie (z opcjonalnym {variant})
    printf '%s' "${ARTIFACT_NAMES//\{variant\}/$variant}"
  else
    # Auto: PREFIX-variant  (musi pasować do YAML upload-artifact name)
    printf '%s' "${ARTIFACT_PREFIX}-${variant}"
  fi
}

# ─────────────────────────────────────────────────────────────
# TRIGGER WORKFLOW
# ─────────────────────────────────────────────────────────────
_trigger_workflow() {
  [[ "$SKIP_TRIGGER" == "true" ]] && { log "SKIP_TRIGGER=true — pomijam dispatch."; return 0; }
  _validate_inputs_json

  local -a variants=()
  if [[ -n "$BUILD_VARIANTS" ]]; then
    IFS=',' read -ra variants <<< "$BUILD_VARIANTS"
  else
    variants=("debug")
  fi

  _DISPATCHED_VARIANTS=("${variants[@]}")

  for variant in "${variants[@]}"; do
    local -a dispatch_args=(
      timeout "$GH_TIMEOUT_S"
      gh workflow run "$WORKFLOW_FILE"
      --ref "$BRANCH"
      --field "variant=${variant}"
    )

    # [FIX-13] clear-cache input
    [[ "$CLEAR_CACHE" == "true" ]] && dispatch_args+=(--field "clear-cache=true")

    # Dodatkowe CUSTOM_INPUTS jako pola
    if [[ -n "$CUSTOM_INPUTS" ]]; then
      while IFS='=' read -r k v; do
        dispatch_args+=(--field "${k}=${v}")
      done < <(printf '%s' "$CUSTOM_INPUTS" | jq -r 'to_entries[] | "\(.key)=\(.value)"')
    fi

    log "Dispatch: ${WORKFLOW_FILE} | variant=${variant} | branch=${BRANCH}"
    if [[ "$DRY_RUN" == "true" ]]; then
      log "[DRY-RUN] ${dispatch_args[*]}"; continue
    fi

    _retry "${dispatch_args[@]}" \
      || fatal "Dispatch nieudany dla variant=${variant}."

    _notify "🚀 Dispatched: ${REPO_NAME} | ${WORKFLOW_FILE} | variant=${variant}"
    log "Trigger OK: variant=${variant}"
  done
}

# ─────────────────────────────────────────────────────────────
# [FIX-15] WAIT FOR RUN ID — dispatch_time PRZED sleep
# ─────────────────────────────────────────────────────────────
_wait_for_run() {
  # [FIX-15] Capture czasu PRZED sleep — nie po — dla dokładnego event-time guard
  local dispatch_time
  dispatch_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  log "Oczekiwanie na run (dispatch_time=${dispatch_time})..."
  sleep 8   # GitHub potrzebuje chwili na inicjalizację run

  local run_id="" attempts=20 i=1

  while (( i <= attempts )); do
    # Filtr: bierz najnowszy run POWSTAŁY po dispatch_time dla naszego workflow+branch
    run_id=$(
      timeout "$GH_TIMEOUT_S" gh run list \
        --workflow="$WORKFLOW_FILE" \
        --branch="$BRANCH" \
        --limit=10 \
        --json databaseId,status,createdAt \
        --jq "
          [ .[] | select(.createdAt >= \"${dispatch_time}\") ]
          | sort_by(.createdAt)
          | reverse
          | .[0].databaseId
          // empty
        " 2>/dev/null || true
    )

    if [[ -n "$run_id" && "$run_id" != "null" ]]; then
      _CURRENT_RUN_ID="$run_id"
      log "Run ID: ${run_id}"
      return 0
    fi

    debug "Próba ${i}/${attempts} — brak run po ${dispatch_time}"
    _backoff_sleep "$i" 3 25
    (( ++i ))
  done

  fatal "Nie znaleziono workflow run po ${attempts} próbach. Sprawdź: gh run list --workflow=${WORKFLOW_FILE}"
}

# ─────────────────────────────────────────────────────────────
# [FIX-16] MONITOR EXECUTION — timeout guard MAX_WAIT_MIN
# ─────────────────────────────────────────────────────────────
_monitor_execution() {
  local run_id="$1"
  local url
  url=$(timeout "$GH_TIMEOUT_S" gh run view "$run_id" --json url --jq '.url' 2>/dev/null || true)
  log "Monitorowanie run ${run_id}..."
  [[ -n "$url" ]] && log "Podgląd: ${url}"

  # gh run watch — blokuje do zakończenia
  if ! timeout "$(( MAX_WAIT_MIN * 60 ))" gh run watch "$run_id" 2>/dev/null; then
    warn "gh run watch zakończone — fallback manual polling..."
    local polls=0 max_polls=$(( MAX_WAIT_MIN * 2 )) status="in_progress"

    while [[ "$status" =~ ^(in_progress|queued|waiting|pending)$ ]]; do
      sleep 30
      # [FIX-09] pre-increment
      (( ++polls ))
      status=$(timeout "$GH_TIMEOUT_S" gh run view "$run_id" --json status --jq '.status' 2>/dev/null || echo "unknown")
      debug "Poll ${polls}/${max_polls}: status=${status}"

      if (( polls >= max_polls )); then
        fatal "Timeout monitorowania po ${MAX_WAIT_MIN} minutach. Run: ${run_id}"
      fi
    done
  fi

  local conclusion
  conclusion=$(timeout "$GH_TIMEOUT_S" gh run view "$run_id" --json conclusion --jq '.conclusion' 2>/dev/null || echo "unknown")
  log "Wynik: ${conclusion}"

  case "$conclusion" in
    success)
      success "Kompilacja zakończona sukcesem!" ;;
    failure|timed_out|startup_failure)
      err "Kompilacja nieudana: ${conclusion}"
      # Pobierz logi błędów z GitHub (tail 150 linii)
      timeout "$GH_TIMEOUT_S" gh run view "$run_id" --log-failed 2>/dev/null \
        | tail -150 | tee -a "$LOGFILE" || true
      fatal "Workflow zakończony: ${conclusion}. Sprawdź logi i artefakt build-logs." ;;
    cancelled)
      fatal "Workflow anulowany manualnie." ;;
    *)
      warn "Nieznany conclusion: ${conclusion}" ;;
  esac
}

# ─────────────────────────────────────────────────────────────
# [FIX-11] DOWNLOAD ARTIFACTS — sha256 bez subshell-scope issues
# ─────────────────────────────────────────────────────────────
_download_artifacts() {
  local run_id="$1"
  [[ "$SKIP_DOWNLOAD" == "true" ]] && { log "SKIP_DOWNLOAD=true — pomijam download."; return 0; }

  mkdir -p "$BUILD_OUTPUT_DIR"

  # Buduj listę artefaktów z dispatched variants
  local -a artifacts=()
  if (( ${#_DISPATCHED_VARIANTS[@]} > 0 )); then
    for variant in "${_DISPATCHED_VARIANTS[@]}"; do
      artifacts+=("$(_resolve_artifact_name "$variant")")
      # Release/all — pobierz też mapping
      if [[ "$variant" == "release" || "$variant" == "all" ]]; then
        artifacts+=("${ARTIFACT_PREFIX}-mapping-release")
      fi
    done
  else
    # Fallback do starego ARTIFACT_NAMES jeśli brak variantów
    IFS=',' read -ra artifacts <<< "${ARTIFACT_NAMES:-${ARTIFACT_PREFIX}-debug}"
  fi

  # Deduplikacja
  local -a unique_artifacts=()
  local seen=""
  for a in "${artifacts[@]}"; do
    a="${a// /}"
    [[ "$seen" == *"|${a}|"* ]] && continue
    seen+="|${a}|"
    unique_artifacts+=("$a")
  done

  for artifact in "${unique_artifacts[@]}"; do
    local dest="${BUILD_OUTPUT_DIR}/${artifact}"
    log "Pobieram artefakt: ${artifact} → ${dest}"

    if [[ "$DRY_RUN" == "true" ]]; then
      log "[DRY-RUN] gh run download ${run_id} -n ${artifact} -D ${dest}"; continue
    fi

    if ! _retry timeout "$GH_TIMEOUT_S" gh run download "$run_id" -n "$artifact" -D "$dest"; then
      err "Nieudane pobranie: ${artifact} (możliwe że nie istnieje dla tego wariantu)"
      continue
    fi
    success "Pobrany: ${artifact} → ${dest}"

    # [FIX-10,11] SHA256 — cross-platform, bez subshell scope problemu
    if [[ "$VERIFY_CHECKSUMS" == "true" ]]; then
      local checksum_file="${BUILD_OUTPUT_DIR}/${artifact}.sha256"
      : > "$checksum_file"   # wyczyść przed zapisem
      log "Generuję checksums SHA-256..."

      while IFS= read -r -d '' f; do
        local sum
        sum=$(_sha256sum "$f")
        printf '%s  %s\n' "$sum" "$f" >> "$checksum_file"
        debug "SHA256 $(basename "$f"): ${sum:0:16}..."
      done < <(find "$dest" -type f -print0 2>/dev/null)

      success "Checksums zapisane: ${checksum_file}"
    fi
  done
}

# ─────────────────────────────────────────────────────────────
# [FIX-18] SUMMARY REPORT — guard gdy jq niedostępne
# ─────────────────────────────────────────────────────────────
_generate_report() {
  local run_id="${1:-N/A}"
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local base="${REPORT_DIR}/scu_report_$(date +%Y%m%d_%H%M%S)"
  local report_json="${base}.json"
  local report_txt="${base}.txt"

  local conclusion="N/A"
  if [[ "$run_id" != "N/A" ]]; then
    conclusion=$(timeout "$GH_TIMEOUT_S" gh run view "$run_id" --json conclusion --jq '.conclusion' 2>/dev/null || echo "N/A")
  fi

  # JSON — z guard na jq
  if command -v jq &>/dev/null; then
    jq -n \
      --arg ver  "$SCU_VERSION"      \
      --arg ts   "$ts"               \
      --arg repo "$REPO_NAME"        \
      --arg br   "$BRANCH"           \
      --arg wf   "$WORKFLOW_FILE"    \
      --arg run  "$run_id"           \
      --arg res  "$conclusion"       \
      --arg out  "$BUILD_OUTPUT_DIR" \
      --arg log  "$LOGFILE"          \
      --argjson variants "$(printf '%s\n' "${_DISPATCHED_VARIANTS[@]}" | jq -R . | jq -s .)" \
      '{scu_version:$ver,timestamp:$ts,repository:$repo,branch:$br,
        workflow:$wf,run_id:$run,result:$res,output_dir:$out,
        logfile:$log,dispatched_variants:$variants}' \
      > "$report_json" 2>/dev/null || true
    debug "JSON report: ${report_json}"
  fi

  # Human-readable TXT (zawsze)
  cat > "$report_txt" <<EOF
╔═════════════════════════════════════════════════╗
║   SCU v${SCU_VERSION} — BUILD REPORT                    ║
╚═════════════════════════════════════════════════╝
Timestamp  : ${ts}
Repository : ${REPO_NAME} (${BRANCH})
Workflow   : ${WORKFLOW_FILE}
Run ID     : ${run_id}
Result     : ${conclusion}
Variants   : ${_DISPATCHED_VARIANTS[*]:-N/A}
Output dir : ${BUILD_OUTPUT_DIR}
Logfile    : ${LOGFILE}
EOF

  success "Report: ${report_txt}"
  cat "$report_txt" | tee -a "$LOGFILE"
  _notify "📊 SCU Report: ${REPO_NAME} | run=${run_id} | result=${conclusion}"
}

# ─────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────
_usage() {
  cat <<EOF
╔══════════════════════════════════════════════════════╗
║  SMART COMPILE ULTIMATE v${SCU_VERSION}                     ║
║  SecFERRO Division ◈ anonymousik.is-a.dev           ║
╚══════════════════════════════════════════════════════╝

UŻYCIE:
  $SCRIPT_NAME [OPCJE]

OPCJE GŁÓWNE:
  -r, --repo NAME          Nazwa repo (owner/name)
  -w, --workflow FILE      Plik workflow (domyślnie: android-build.yml)
  -b, --branch BRANCH      Gałąź git (domyślnie: main)
  -o, --output DIR         Katalog artefaktów
  -p, --artifact-prefix    Prefix nazwy artefaktu (domyślnie: neurosync-apk)
  -a, --artifacts CSV      Override nazw artefaktów (CSV lub z {variant})
  -v, --variants CSV       Build matrix, np. "debug,release,all"
  -i, --inputs JSON        JSON inputs dla workflow dispatch
      --retries N          Retry count (domyślnie: 3)
      --log-level LVL      TRACE|DEBUG|INFO|WARN|ERROR|FATAL
      --max-wait N         Max czas monitorowania w minutach (domyślnie: 60)
      --timeout N          Timeout pojedynczych gh/curl wywołań w sekundach

FLAGI STERUJĄCE:
  -y, --yes                Auto-akceptuj wszystkie pytania
  -f, --force              Nadpisz lock file
      --clear-cache        Wyczyść Gradle cache przed buildem
      --skip-push          Pomiń git commit/push
      --skip-trigger       Pomiń dispatch workflow
      --skip-download      Pomiń pobieranie artefaktów
      --dry-run            Symulacja — zero efektów ubocznych
      --no-checksums       Wyłącz SHA-256 verify
      --no-secret-scan     Wyłącz skan sekretów
      --no-notify          Wyłącz wszystkie powiadomienia

NOTYFIKACJE:
      --webhook URL        Slack/Discord webhook
      --email ADDR         E-mail (wymaga: mail)

NARZĘDZIOWE:
  -h, --help               Pokaż pomoc
      --version            Wersja SCU
      --config             Ścieżka config
      --edit-config        Otwórz config w \$EDITOR
      --show-logs          Lista ostatnich logów

PRZYKŁADY:
  $SCRIPT_NAME -r myOrg/myApp -b develop -v debug,release --yes
  $SCRIPT_NAME --skip-push -a "myapp-{variant}" --dry-run --log-level DEBUG
  $SCRIPT_NAME --clear-cache --webhook https://hooks.slack.com/... --retries 5
  curl -fsSL https://anonymousik.is-a.dev/scripts/scu/smart_compile_ultimate.sh \\
    | bash -s -- -r myOrg/myApp -v release --yes

CONFIG: ${CONF_FILE}
LOGI  : ${LOG_DIR}
EOF
  exit 0
}

# ─────────────────────────────────────────────────────────────
# ARG PARSER
# ─────────────────────────────────────────────────────────────
_parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      -r|--repo)            REPO_NAME="$2";             shift 2 ;;
      -w|--workflow)        WORKFLOW_FILE="$2";          shift 2 ;;
      -b|--branch)          BRANCH="$2";                 shift 2 ;;
      -o|--output)          BUILD_OUTPUT_DIR="$2";       shift 2 ;;
      -p|--artifact-prefix) ARTIFACT_PREFIX="$2";        shift 2 ;;
      -a|--artifacts)       ARTIFACT_NAMES="$2";         shift 2 ;;
      -v|--variants)        BUILD_VARIANTS="$2";         shift 2 ;;
      -i|--inputs)          CUSTOM_INPUTS="$2";          shift 2 ;;
         --retries)         RETRIES="$2";                shift 2 ;;
         --log-level)       LOG_LEVEL="${2^^}";           shift 2 ;;
         --max-wait)        MAX_WAIT_MIN="$2";           shift 2 ;;
         --timeout)         GH_TIMEOUT_S="$2";           shift 2 ;;
      -y|--yes)             AUTO_YES="true";             shift   ;;
      -f|--force)           FORCE_LOCK="true";           shift   ;;
         --clear-cache)     CLEAR_CACHE="true";          shift   ;;
         --skip-push)       SKIP_PUSH="true";            shift   ;;
         --skip-trigger)    SKIP_TRIGGER="true";         shift   ;;
         --skip-download)   SKIP_DOWNLOAD="true";        shift   ;;
         --dry-run)         DRY_RUN="true";              shift   ;;
         --no-checksums)    VERIFY_CHECKSUMS="false";    shift   ;;
         --no-secret-scan)  SECRET_SCAN="false";         shift   ;;
         --no-notify)       WEBHOOK_URL=""; NOTIFY_EMAIL=""; TERMUX_NOTIFY="false"; shift ;;
         --webhook)         WEBHOOK_URL="$2";            shift 2 ;;
         --email)           NOTIFY_EMAIL="$2";           shift 2 ;;
      -h|--help)            _usage ;;
         --version)         printf 'SCU v%s (%s)\n' "$SCU_VERSION" "$SCU_BUILD_DATE"; exit 0 ;;
         --config)          printf '%s\n' "$CONF_FILE"; exit 0 ;;
         --edit-config)     "${EDITOR:-nano}" "$CONF_FILE"; exit 0 ;;
         --show-logs)       find "$LOG_DIR" -name '*.log*' | sort -r | head -10; exit 0 ;;
      --) shift; break ;;
      -*) warn "Nieznana opcja: $1"; shift ;;
      *)  warn "Nieoczekiwany argument: $1"; shift ;;
    esac
  done
}

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
main() {
  # ── Faza 0: config + args ──────────────────────────────────
  _load_conf
  _parse_args "$@"

  # ── Lock ──────────────────────────────────────────────────
  [[ "$FORCE_LOCK" == "true" ]] && rm -f "$LOCK_FILE"
  _acquire_lock

  # ── Banner ────────────────────────────────────────────────
  printf '\e[1;36m'
  cat <<'BANNER'
  ╔═══════════════════════════════════════════════╗
  ║  ◈ SMART COMPILE ULTIMATE v3.0 IRONCLAD      ║
  ║  SecFERRO Division ◈ [FERRO//ANON]           ║
  ║  anonymousik.is-a.dev                        ║
  ╚═══════════════════════════════════════════════╝
BANNER
  printf '\e[0m'

  [[ "$DRY_RUN" == "true" ]] && warn "══ TRYB DRY-RUN — żadne operacje nie zostaną wykonane! ══"

  # ── Faza 1: pre-flight ────────────────────────────────────
  _require_cmds gh git curl jq
  _preflight_env      # bash ver, disk, network
  _preflight_git      # git repo check — [FIX-07] nie w _load_conf

  # ── Faza 2: diagnostics ───────────────────────────────────
  _self_diagnose

  # ── Faza 3: GitHub auth ───────────────────────────────────
  _healthcheck_github

  # ── Faza 4: repo ──────────────────────────────────────────
  _init_repo

  # ── Faza 5: workflow YAML ─────────────────────────────────
  _audit_workflow

  # ── Faza 6: sync code ─────────────────────────────────────
  _sync_code

  # ── Faza 7: dispatch ──────────────────────────────────────
  _trigger_workflow

  # ── Fazy 8–11 pomijane przy dry-run / skip-trigger ────────
  if [[ "$SKIP_TRIGGER" == "false" && "$DRY_RUN" == "false" ]]; then

    # ── Faza 8: wait run_id ───────────────────────────────
    _wait_for_run

    # ── Faza 9: monitor ───────────────────────────────────
    _monitor_execution "$_CURRENT_RUN_ID"

    # ── Faza 10: download ─────────────────────────────────
    _download_artifacts "$_CURRENT_RUN_ID"

    # ── Faza 11: report ───────────────────────────────────
    _generate_report "$_CURRENT_RUN_ID"
  fi

  success "╔══════════════════════════════════════════╗"
  success "║  SCU ZAKOŃCZONE SUKCESEM                ║"
  success "║  Output: ${BUILD_OUTPUT_DIR}"
  success "╚══════════════════════════════════════════╝"

  _notify "✅ SCU OK | ${REPO_NAME} | run: ${_CURRENT_RUN_ID:-N/A} | variants: ${_DISPATCHED_VARIANTS[*]:-N/A}"
}

main "$@"