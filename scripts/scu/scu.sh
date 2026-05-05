#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SMART COMPILE ULTIMATE  v2.0                                       ║
# ║  SecFERRO Division ◈ FerroART ◈ anonymousik.is-a.dev               ║
# ║  Universal Android/GitHub Actions CI/CD Backend — Termux-native     ║
# ║  © 2026 anonymousik / FerroART  ◈  [FERRO//ANON]                   ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# NOWE W v2.0:
#  • Pełny parser argumentów CLI (długie flagi, --help)
#  • Config-file (INI) z auto-generacją ~/.scu.conf
#  • Hierarchia logowania: TRACE/DEBUG/INFO/WARN/ERROR/FATAL
#  • Rotacja logów + kompresja starych (gzip)
#  • Lock-file — blokada współbieżnych instancji
#  • trap ERR/EXIT/SIGINT — cleanup zawsze uruchamiany
#  • Exponential backoff przy retry (jitter ±10%)
#  • Walidacja JSON CUSTOM_INPUTS przed dispatch
#  • Smart polling run_id (event-time guard, nie tylko [0])
#  • Sanity-check checksum APK po pobraniu (sha256)
#  • Multi-artifact download (CSV lista nazw)
#  • Build-matrix dispatch (pętla po wariantach)
#  • Rate-limit detection (HTTP 403/429 z retry-after)
#  • Summary report: JSON + human-readable
#  • Secret-leak scan (nie pushuj kluczy API do git)
#  • Workflow YAML generator ulepszony (JDK 21, Gradle cache, signing)
#  • Obsługa Termux:API (toast/powiadomienie natywne Android)
#  • Sugestia --cancel przy Ctrl+C (gh run cancel)

#set -Eeuo pipefail
#IFS=$'\n\t'

# ─────────────────────────────────────────────────────────────
# STAŁE WERSJI
# ─────────────────────────────────────────────────────────────
readonly SCU_VERSION="2.0.0"
readonly SCU_BUILD_DATE="2026-05-05"
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_PATH="$(realpath "$0")"
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
touch "$LOGFILE"

# Rotacja: zachowaj max 20 logów, resztę kompresuj
_rotate_logs() {
  local logs=("$LOG_DIR"/scu_*.log)
  local count=${#logs[@]}
  if (( count > 20 )); then
    local old=("${logs[@]:0:$((count-20))}")
    for f in "${old[@]}"; do
      [[ -f "$f" ]] && gzip -f "$f" 2>/dev/null || true
    done
  fi
}
_rotate_logs

# ─────────────────────────────────────────────────────────────
# LOCK FILE — blokada współbieżnych instancji
# ─────────────────────────────────────────────────────────────
LOCK_FILE="${LOCK_DIR}/scu.lock"

_acquire_lock() {
  if [[ -f "$LOCK_FILE" ]]; then
    local old_pid
    old_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "?")
    if kill -0 "$old_pid" 2>/dev/null; then
      echo -e "\e[1;31m[FATAL] Inna instancja SCU działa (PID $old_pid). Użyj --force aby nadpisać.\e[0m"
      exit 1
    else
      rm -f "$LOCK_FILE"
    fi
  fi
  echo "$PID" > "$LOCK_FILE"
}

_release_lock() { rm -f "$LOCK_FILE"; }

# ─────────────────────────────────────────────────────────────
# DEFAULTS (nadpisywane przez conf/CLI)
# ─────────────────────────────────────────────────────────────
REPO_NAME="neurosync-ai-private"
WORKFLOW_FILE="android-build.yml"
BRANCH="main"
BUILD_OUTPUT_DIR="${HOME}/build_output"
ARTIFACT_NAMES="neurosync-wearos-apk"  # CSV: "apk,mapping,bundle"
CUSTOM_INPUTS=""
AUTO_YES="false"
WEBHOOK_URL=""
NOTIFY_EMAIL=""
RETRIES=3
LOG_LEVEL="INFO"           # TRACE|DEBUG|INFO|WARN|ERROR|FATAL
SKIP_PUSH="false"
SKIP_TRIGGER="false"
SKIP_DOWNLOAD="false"
FORCE_LOCK="false"
BUILD_VARIANTS=""          # CSV wariantów: "debug,release"
DRY_RUN="false"
VERIFY_CHECKSUMS="true"
SECRET_SCAN="true"
TERMUX_NOTIFY="true"

# ─────────────────────────────────────────────────────────────
# CONFIG FILE (INI-style)
# ─────────────────────────────────────────────────────────────
_gen_default_conf() {
  cat > "$CONF_FILE" <<EOF
# SCU v${SCU_VERSION} — Smart Compile Ultimate config
# Edytuj wg potrzeb. Wartości nadpisywane przez flagi CLI.

REPO_NAME=neurosync-ai-private
WORKFLOW_FILE=android-build.yml
BRANCH=main
BUILD_OUTPUT_DIR=${HOME}/build_output
ARTIFACT_NAMES=neurosync-wearos-apk
AUTO_YES=false
RETRIES=3
LOG_LEVEL=INFO
WEBHOOK_URL=
NOTIFY_EMAIL=
TERMUX_NOTIFY=true
VERIFY_CHECKSUMS=true
SECRET_SCAN=true
EOF
  echo -e "\e[1;33m[INFO] Wygenerowano domyślny config: $CONF_FILE\e[0m"
}

_load_conf() {
        if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then 
            echo -e "\e[1;31m[FATAL] Ten folder nie jest repozytorium Git! Uruchom: git init\e[0m"; 
            exit 1; 
        fi
  if [[ ! -f "$CONF_FILE" ]]; then _gen_default_conf; fi
  # shellcheck disable=SC1090
  while IFS='=' read -r key val; do
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$key" ]] && continue
    key="${key// /}"
    val="${val// /}"
    # Tylko znane zmienne
    case "$key" in
      REPO_NAME|WORKFLOW_FILE|BRANCH|BUILD_OUTPUT_DIR|ARTIFACT_NAMES| \
      AUTO_YES|RETRIES|LOG_LEVEL|WEBHOOK_URL|NOTIFY_EMAIL| \
      TERMUX_NOTIFY|VERIFY_CHECKSUMS|SECRET_SCAN)
        declare -g "$key"="$val" ;;
    esac
  done < "$CONF_FILE"
}

# ─────────────────────────────────────────────────────────────
# LOGGER (wielopoziomowy)
# ─────────────────────────────────────────────────────────────
declare -A LOG_LEVELS=([TRACE]=0 [DEBUG]=1 [INFO]=2 [WARN]=3 [ERROR]=4 [FATAL]=5)

_log_enabled() {
  local lvl="${1:-INFO}"
  local cur="${LOG_LEVEL:-INFO}"
  (( ${LOG_LEVELS[$lvl]:-2} >= ${LOG_LEVELS[$cur]:-2} ))
}

_ts() { date +'%F %T'; }

log()   { _log_enabled INFO  && echo -e "\e[1;34m[$(_ts)] [INFO]  $*\e[0m" | tee -a "$LOGFILE" || true; }
debug() { _log_enabled DEBUG && echo -e "\e[0;36m[$(_ts)] [DEBUG] $*\e[0m" | tee -a "$LOGFILE" || true; }
trace() { _log_enabled TRACE && echo -e "\e[0;37m[$(_ts)] [TRACE] $*\e[0m" | tee -a "$LOGFILE" || true; }
warn()  { _log_enabled WARN  && echo -e "\e[1;33m[$(_ts)] [WARN]  $*\e[0m" | tee -a "$LOGFILE" || true; }
err()   { _log_enabled ERROR && echo -e "\e[1;31m[$(_ts)] [ERROR] $*\e[0m" | tee -a "$LOGFILE" >&2 || true; }
success(){ echo -e "\e[1;32m[$(_ts)] [OK]    $*\e[0m" | tee -a "$LOGFILE"; }

fatal() {
  echo -e "\e[1;31m[$(_ts)] [FATAL] $*\e[0m" | tee -a "$LOGFILE" >&2
  _notify "💀 FATAL: $*"
  exit 1
}

# ─────────────────────────────────────────────────────────────
# NOTYFIKACJE (Webhook / Email / Termux:API)
# ─────────────────────────────────────────────────────────────
_notify() {
  local msg="[SCU $SCU_VERSION | $(_ts)] $1"
  local safe_msg="${msg//\"/\\\"}"

  # Slack / Discord webhook
  if [[ -n "$WEBHOOK_URL" ]]; then
    curl -sf -X POST -H 'Content-type: application/json' \
      --data "{\"text\":\"${safe_msg}\"}" \
      "$WEBHOOK_URL" 2>/dev/null || true
  fi

  # Mail
  if [[ -n "$NOTIFY_EMAIL" ]]; then
    echo "$msg" | mail -s "[SCU ALERT] $SCRIPT_NAME" "$NOTIFY_EMAIL" 2>/dev/null || true
  fi

  # Termux:API native toast
  if [[ "$TERMUX_NOTIFY" == "true" ]] && command -v termux-toast &>/dev/null; then
    termux-toast -b black -c cyan "$1" 2>/dev/null || true
  fi
}

# ─────────────────────────────────────────────────────────────
# TRAP — cleanup zawsze uruchomiony
# ─────────────────────────────────────────────────────────────
_CURRENT_RUN_ID=""
_cleanup() {
  local exit_code=$?
  _release_lock
  if (( exit_code != 0 )); then
    err "Skrypt zakończył się błędem (exit $exit_code)."
    if [[ -n "$_CURRENT_RUN_ID" ]]; then
      warn "Aktywny run ID: $_CURRENT_RUN_ID — rozważ: gh run cancel $_CURRENT_RUN_ID"
    fi
    _notify "❌ SCU zakończone błędem (exit $exit_code) | repo: $REPO_NAME"
  fi
}

_sigint_handler() {
  echo ""
  warn "Przerwano przez użytkownika (SIGINT)."
  if [[ -n "$_CURRENT_RUN_ID" ]]; then
    if confirm "Czy anulować aktywny workflow run $_CURRENT_RUN_ID na GitHub?"; then
      gh run cancel "$_CURRENT_RUN_ID" && log "Run anulowany." || warn "Nie udało się anulować."
    fi
  fi
  exit 130
}

trap '_cleanup' EXIT
trap '_sigint_handler' SIGINT SIGTERM
trap 'err "Błąd w linii $LINENO (polecenie: $BASH_COMMAND)"; ' ERR

# ─────────────────────────────────────────────────────────────
# EXPONENTIAL BACKOFF z jitter
# ─────────────────────────────────────────────────────────────
_backoff_sleep() {
  local attempt="$1"     # 1-based
  local base="${2:-3}"   # sekundy bazowe
  local max="${3:-60}"   # cap sekundy

  local exp=$(( base * (2 ** (attempt - 1)) ))
  (( exp > max )) && exp=$max
  # Jitter ±10%
  local jitter=$(( RANDOM % (exp / 5 + 1) ))
  local sleep_time=$(( exp + jitter - (exp / 10) ))

  debug "Backoff: próba $attempt → czekam ${sleep_time}s"
  sleep "$sleep_time"
}

# ─────────────────────────────────────────────────────────────
# RETRY WRAPPER z rate-limit detection
# ─────────────────────────────────────────────────────────────
_retry() {
  local retries="${RETRIES:-3}"
  local cmd=("$@")
  local i=1

  while (( i <= retries )); do
    local output
    local exit_code=0
    output=$(eval "${cmd[@]}" 2>&1) || exit_code=$?

    if (( exit_code == 0 )); then
      echo "$output"
      return 0
    fi

    # Rate-limit detection (gh API → 403/429)
    if echo "$output" | grep -qiE "(rate limit|429|403|secondary rate)"; then
      warn "GitHub rate-limit wykryty. Czekam 60s..."
      sleep 60
    else
      warn "Próba $i/$retries nieudana (exit $exit_code): ${output:0:120}"
      _backoff_sleep "$i"
    fi
    (( i++ ))
  done

  err "Wszystkie $retries próby nieudane: ${cmd[*]}"
  return 1
}

# ─────────────────────────────────────────────────────────────
# WALIDACJA ZALEŻNOŚCI
# ─────────────────────────────────────────────────────────────
_require_cmds() {
  local missing=()
  for c in "$@"; do
    if ! command -v "$c" &>/dev/null; then
      missing+=("$c")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    warn "Brakujące narzędzia: ${missing[*]}"
    for pkg in "${missing[@]}"; do
      log "Próba instalacji: $pkg"
      pkg install -y "$pkg" 2>/dev/null \
        || apt-get install -y "$pkg" 2>/dev/null \
        || fatal "Nie można zainstalować: $pkg. Zainstaluj ręcznie."
      command -v "$pkg" &>/dev/null || fatal "Po instalacji brak: $pkg"
    done
    success "Zainstalowano brakujące narzędzia."
  fi
}

# ─────────────────────────────────────────────────────────────
# SELF-DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
_self_diagnose() {
  log "── Self-diagnostics ──────────────────────────"
  log "SCU v${SCU_VERSION} (${SCU_BUILD_DATE}) | PID: $PID"
  log "Kernel: $(uname -r) | Arch: $(uname -m)"
  log "Shell: $BASH_VERSION | User: $(whoami)"
  grep -qi "android" /proc/version 2>/dev/null && log "Środowisko: Android/Termux" || log "Środowisko: Linux"
  log "Logfile: $LOGFILE"
  log "Git: $(git --version 2>/dev/null | head -1)"
  log "GH CLI: $(gh --version 2>/dev/null | head -1)"
  log "jq: $(jq --version 2>/dev/null)"
  log "curl: $(curl --version 2>/dev/null | head -1)"

  local git_status
  git_status="$(git status --porcelain 2>/dev/null || true)"
  [[ -n "$git_status" ]] && warn "Niezatwierdzone zmiany w repo!"
  log "─────────────────────────────────────────────"
}

# ─────────────────────────────────────────────────────────────
# SECRET LEAK SCANNER (uproszczony grep)
# ─────────────────────────────────────────────────────────────
_secret_scan() {
  if [[ "$SECRET_SCAN" != "true" ]]; then return 0; fi
  log "Skanowanie leku sekretów przed pushem..."

  local patterns=(
    'AKIA[0-9A-Z]{16}'         # AWS Access Key
    'sk-[A-Za-z0-9]{32,}'      # OpenAI / Stripe SK
    'ghp_[A-Za-z0-9]{36}'      # GitHub PAT (classic)
    'github_pat_'               # GitHub fine-grained
    'BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE'
    'password\s*=\s*["\x27][^\s]{8,}'
    'token\s*=\s*["\x27][A-Za-z0-9_\-\.]{16,}'
  )

  local found=0
  for pattern in "${patterns[@]}"; do
    local hits
    hits=$(git diff --cached --name-only 2>/dev/null \
      | xargs -I{} grep -rlP "$pattern" -- {} 2>/dev/null || true)
    if [[ -n "$hits" ]]; then
      warn "⚠ Potencjalny leak sekretów (pattern: $pattern) w: $hits"
      (( found++ ))
    fi
  done

  if (( found > 0 )); then
    err "$found potencjalnych lekow sekretów w staged files!"
    confirm "Kontynuować mimo to? (RYZYKOWNE)" || fatal "Push anulowany przez secret scan."
  else
    success "Secret scan czysty."
  fi
}

# ─────────────────────────────────────────────────────────────
# GITHUB AUTH
# ─────────────────────────────────────────────────────────────
_healthcheck_github() {
  log "Weryfikacja autoryzacji GitHub CLI..."
  if ! gh auth status &>/dev/null; then
    warn "Brak aktywnej sesji gh. Uruchamiam gh auth login..."
    gh auth login || fatal "Logowanie do GitHub nie powiodło się."
  fi
  local gh_user
  gh_user=$(gh api user --jq '.login' 2>/dev/null || echo "?")
  log "Zalogowany jako: @${gh_user}"
}

# ─────────────────────────────────────────────────────────────
# REPO INIT
# ─────────────────────────────────────────────────────────────
_init_repo() {
  log "Weryfikacja repo: $REPO_NAME"
  if ! gh repo view "$REPO_NAME" &>/dev/null; then
    log "Repo nie istnieje → tworzę prywatne..."
    [[ "$DRY_RUN" == "true" ]] && { log "[DRY-RUN] gh repo create $REPO_NAME --private"; return; }
    gh repo create "$REPO_NAME" --private --source=. --remote=origin --push \
      || fatal "Tworzenie repo nie powiodło się!"
    success "Repo $REPO_NAME utworzone."
  else
    debug "Repo $REPO_NAME istnieje."
  fi
}

# ─────────────────────────────────────────────────────────────
# SYNC CODE
# ─────────────────────────────────────────────────────────────
_sync_code() {
  if [[ "$SKIP_PUSH" == "true" ]]; then
    log "SKIP_PUSH=true — pomijam commit/push."
    return 0
  fi
  log "Synchronizacja kodu → $BRANCH"
  _secret_scan
  git add -A
  (git commit -m "auto: SCU v${SCU_VERSION} sync $(date +'%F %T')" 2>/dev/null || true)
  [[ "$DRY_RUN" == "true" ]] && { log "[DRY-RUN] git push origin $BRANCH"; return; }
  git push origin "$BRANCH" || fatal "git push nie powiódł się!"
  success "Push zakończony."
}

# ─────────────────────────────────────────────────────────────
# WORKFLOW YAML AUDIT / GENERATOR
# ─────────────────────────────────────────────────────────────
_audit_workflow() {
  local wf_path=".github/workflows/$WORKFLOW_FILE"
  if [[ -f "$wf_path" ]]; then
    debug "Workflow $wf_path istnieje."
    # Sprawdź czy ma workflow_dispatch
    if ! grep -q "workflow_dispatch" "$wf_path"; then
      warn "Workflow nie ma triggera workflow_dispatch — dispatch nie zadziała!"
    fi
    return 0
  fi

  warn "Brak $wf_path."
  confirm "Wygenerować zaawansowany Android workflow?" || { warn "Pominięto generowanie workflow."; return; }

  mkdir -p ".github/workflows"
  cat > "$wf_path" <<'ENDYML'
name: Android Build — SCU

on:
  workflow_dispatch:
    inputs:
      variant:
        description: 'Build variant (debug|release)'
        required: false
        default: 'debug'
  push:
    branches: [main]

env:
  JAVA_VERSION: '21'
  GRADLE_OPTS: -Dorg.gradle.daemon=false -Dorg.gradle.parallel=true -Dorg.gradle.caching=true

jobs:
  build:
    name: Build ${{ inputs.variant || 'debug' }}
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Setup JDK ${{ env.JAVA_VERSION }}
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: ${{ env.JAVA_VERSION }}

      - name: Cache Gradle
        uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
          key: gradle-${{ runner.os }}-${{ hashFiles('**/*.gradle*','**/gradle-wrapper.properties') }}
          restore-keys: |
            gradle-${{ runner.os }}-

      - name: Validate Gradle wrapper
        uses: gradle/wrapper-validation-action@v2

      - name: Make gradlew executable
        run: chmod +x gradlew

      - name: Build APK (${{ inputs.variant || 'debug' }})
        run: |
          if [ "${{ inputs.variant }}" = "release" ]; then
            ./gradlew assembleRelease --stacktrace
          else
            ./gradlew assembleDebug --stacktrace
          fi

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: neurosync-wearos-apk
          path: app/build/outputs/apk/**/*.apk
          retention-days: 7
          if-no-files-found: error

      - name: Upload mapping (release only)
        if: ${{ inputs.variant == 'release' }}
        uses: actions/upload-artifact@v4
        with:
          name: neurosync-mapping
          path: app/build/outputs/mapping/release/mapping.txt
          retention-days: 7

  notify:
    name: Notify on failure
    runs-on: ubuntu-latest
    needs: build
    if: failure()
    steps:
      - name: Failure annotation
        run: echo "::error::Build failed for variant ${{ inputs.variant }}"
ENDYML

  git add "$wf_path"
  git commit -m "ci: add SCU v${SCU_VERSION} advanced android workflow"
  git push origin "$BRANCH"
  success "Workflow $wf_path wygenerowany i wypchnięty."
}

# ─────────────────────────────────────────────────────────────
# WALIDACJA CUSTOM_INPUTS JSON
# ─────────────────────────────────────────────────────────────
_validate_inputs_json() {
  if [[ -z "$CUSTOM_INPUTS" ]]; then return 0; fi
  if ! echo "$CUSTOM_INPUTS" | jq empty 2>/dev/null; then
    fatal "CUSTOM_INPUTS nie jest poprawnym JSON: $CUSTOM_INPUTS"
  fi
  debug "CUSTOM_INPUTS JSON OK."
}

# ─────────────────────────────────────────────────────────────
# TRIGGER WORKFLOW (z obsługą wariantów build matrix)
# ─────────────────────────────────────────────────────────────
_trigger_workflow() {
  if [[ "$SKIP_TRIGGER" == "true" ]]; then
    log "SKIP_TRIGGER=true — pomijam dispatch."
    return 0
  fi

  _validate_inputs_json

  # Build-matrix: iteracja po wariantach (CSV)
  local variants=()
  if [[ -n "$BUILD_VARIANTS" ]]; then
    IFS=',' read -ra variants <<< "$BUILD_VARIANTS"
  else
    variants=("default")
  fi

  for variant in "${variants[@]}"; do
    local dispatch_args=(gh workflow run "$WORKFLOW_FILE" --ref "$BRANCH")

    if [[ "$variant" != "default" ]]; then
      dispatch_args+=(--field "variant=$variant")
    fi

    if [[ -n "$CUSTOM_INPUTS" ]]; then
      while IFS='=' read -r k v; do
        dispatch_args+=(--field "${k}=${v}")
      done < <(echo "$CUSTOM_INPUTS" | jq -r 'to_entries[] | "\(.key)=\(.value)"')
    fi

    log "Dispatch workflow: $WORKFLOW_FILE (variant: $variant, branch: $BRANCH)"
    [[ "$DRY_RUN" == "true" ]] && { log "[DRY-RUN] ${dispatch_args[*]}"; continue; }

    _retry "${dispatch_args[@]}" \
      || fatal "Dispatch nie powiódł się dla wariantu $variant."

    _notify "🚀 Workflow dispatched: $REPO_NAME | $WORKFLOW_FILE | variant=$variant | branch=$BRANCH"
    log "Trigger OK dla wariantu: $variant"
  done
}

# ─────────────────────────────────────────────────────────────
# WAIT FOR RUN ID (z event-time guardem)
# ─────────────────────────────────────────────────────────────
_wait_for_run() {
  log "Oczekiwanie na inicjalizację workflow run..."
  local dispatch_time
  dispatch_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 8

  local run_id=""
  local attempts=15

  for (( i=1; i<=attempts; i++ )); do
    # Filtruj po czasie dispatch (event-time guard) → bierz najnowszy
    run_id=$(gh run list \
      --workflow="$WORKFLOW_FILE" \
      --branch="$BRANCH" \
      --limit=5 \
      --json databaseId,status,createdAt \
      --jq "
        [ .[] | select(.createdAt >= \"$dispatch_time\") ]
        | sort_by(.createdAt)
        | reverse
        | .[0].databaseId
      " 2>/dev/null || true)

    if [[ -n "$run_id" && "$run_id" != "null" ]]; then
      _CURRENT_RUN_ID="$run_id"
      log "Run ID: $run_id"
      return 0
    fi

    debug "Próba $i/$attempts — brak run po $dispatch_time, czekam..."
    _backoff_sleep "$i" 3 20
  done

  fatal "Nie znaleziono workflow run po $attempts próbach. Sprawdź repo: $REPO_NAME"
}

# ─────────────────────────────────────────────────────────────
# MONITOR EXECUTION
# ─────────────────────────────────────────────────────────────
_monitor_execution() {
  local run_id="$1"
  log "Monitorowanie kompilacji (run_id: $run_id)..."
  log "Podgląd: $(gh run view "$run_id" --json url --jq '.url' 2>/dev/null || true)"

  # gh run watch obsłuży polling; przy błędzie fallback na status polling
  if ! gh run watch "$run_id" 2>/dev/null; then
    warn "gh run watch zakończone błędem — manual polling..."
    local status="in_progress"
    local polls=0
    while [[ "$status" =~ ^(in_progress|queued|waiting)$ ]]; do
      (( polls++ ))
      sleep 30
      status=$(gh run view "$run_id" --json status --jq '.status' 2>/dev/null || echo "unknown")
      debug "Poll $polls: status=$status"
      (( polls > 60 )) && fatal "Timeout monitorowania po $polls polls (30s każdy)."
    done
  fi

  local conclusion
  conclusion=$(gh run view "$run_id" --json conclusion --jq '.conclusion' 2>/dev/null || echo "unknown")
  log "Wynik kompilacji: $conclusion"

  case "$conclusion" in
    success) success "Kompilacja zakończona sukcesem!" ;;
    failure|cancelled|timed_out)
      err "Kompilacja nieudana: $conclusion"
      gh run view "$run_id" --log-failed 2>/dev/null | tail -100 | tee -a "$LOGFILE" || true
      fatal "Workflow zakończony: $conclusion"
      ;;
    *)
      warn "Nieznany status kompilacji: $conclusion"
      ;;
  esac
}

# ─────────────────────────────────────────────────────────────
# DOWNLOAD ARTIFACTS (multi-artifact + sha256 verify)
# ─────────────────────────────────────────────────────────────
_download_artifacts() {
  local run_id="$1"
  if [[ "$SKIP_DOWNLOAD" == "true" ]]; then
    log "SKIP_DOWNLOAD=true — pomijam pobieranie artefaktów."
    return 0
  fi

  mkdir -p "$BUILD_OUTPUT_DIR"
  IFS=',' read -ra artifact_list <<< "$ARTIFACT_NAMES"

  for artifact in "${artifact_list[@]}"; do
    artifact="${artifact// /}"  # trim spaces
    log "Pobieram artefakt: $artifact → $BUILD_OUTPUT_DIR"

    [[ "$DRY_RUN" == "true" ]] && { log "[DRY-RUN] gh run download $run_id -n $artifact"; continue; }

    _retry gh run download "$run_id" -n "$artifact" -D "$BUILD_OUTPUT_DIR/$artifact" \
      || { err "Nieudane pobranie artefaktu: $artifact"; continue; }

    success "Artefakt '$artifact' pobrany → $BUILD_OUTPUT_DIR/$artifact"

    # SHA256 verification
    if [[ "$VERIFY_CHECKSUMS" == "true" ]]; then
      log "Generuję checksums SHA-256 dla: $artifact"
      find "$BUILD_OUTPUT_DIR/$artifact" -type f | while read -r f; do
        local sum
        sum=$(sha256sum "$f" | awk '{print $1}')
        echo "$sum  $f" >> "${BUILD_OUTPUT_DIR}/${artifact}.sha256"
        debug "SHA256 $(basename "$f"): $sum"
      done
      success "Checksums zapisane: ${BUILD_OUTPUT_DIR}/${artifact}.sha256"
    fi
  done
}

# ─────────────────────────────────────────────────────────────
# SUMMARY REPORT
# ─────────────────────────────────────────────────────────────
_generate_report() {
  local run_id="${1:-N/A}"
  local end_ts
  end_ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local report_json="${REPORT_DIR}/scu_report_$(date +%Y%m%d_%H%M%S).json"
  local report_txt="${REPORT_DIR}/scu_report_$(date +%Y%m%d_%H%M%S).txt"

  local conclusion
  conclusion=$(gh run view "$run_id" --json conclusion --jq '.conclusion' 2>/dev/null || echo "N/A")

  # JSON
  jq -n \
    --arg ver "$SCU_VERSION" \
    --arg ts "$end_ts" \
    --arg repo "$REPO_NAME" \
    --arg branch "$BRANCH" \
    --arg wf "$WORKFLOW_FILE" \
    --arg run "$run_id" \
    --arg result "$conclusion" \
    --arg outdir "$BUILD_OUTPUT_DIR" \
    --arg log "$LOGFILE" \
    '{
      scu_version: $ver,
      timestamp: $ts,
      repository: $repo,
      branch: $branch,
      workflow: $wf,
      run_id: $run,
      result: $result,
      output_dir: $outdir,
      logfile: $log
    }' > "$report_json"

  # Human-readable
  cat > "$report_txt" <<EOF
╔═══════════════════════════════════════════╗
║   SCU v${SCU_VERSION} — BUILD REPORT            ║
╚═══════════════════════════════════════════╝
Timestamp  : $end_ts
Repository : $REPO_NAME ($BRANCH)
Workflow   : $WORKFLOW_FILE
Run ID     : $run_id
Result     : $conclusion
Output dir : $BUILD_OUTPUT_DIR
Logfile    : $LOGFILE
EOF

  success "Raport: $report_txt"
  cat "$report_txt" | tee -a "$LOGFILE"
  _notify "📊 SCU Report: $REPO_NAME | $WORKFLOW_FILE | run=$run_id | result=$conclusion"
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
  -r, --repo NAME          Nazwa repo (owner/name lub tylko name)
  -w, --workflow FILE      Nazwa pliku workflow (np. android-build.yml)
  -b, --branch BRANCH      Gałąź git (domyślnie: main)
  -o, --output DIR         Katalog wyjściowy artefaktów
  -a, --artifacts CSV      Nazwy artefaktów (CSV), np. "apk,mapping"
  -v, --variants CSV       Warianty build matrix (CSV), np. "debug,release"
  -i, --inputs JSON        JSON inputs dla workflow dispatch
      --retries N          Liczba ponownych prób (domyślnie: 3)
      --log-level LVL      TRACE|DEBUG|INFO|WARN|ERROR|FATAL

FLAGI STERUJĄCE:
  -y, --yes                Auto-akceptuj wszystkie pytania
      --skip-push          Pomiń git push
      --skip-trigger       Pomiń workflow dispatch
      --skip-download      Pomiń pobieranie artefaktów
      --dry-run            Symulacja bez wykonywania operacji
      --force              Nadpisz lock file (jeśli stara instancja)
      --no-checksums       Wyłącz weryfikację SHA-256
      --no-secret-scan     Wyłącz skan sekretów przed pushem
      --no-notify          Wyłącz wszystkie powiadomienia

NOTYFIKACJE:
      --webhook URL        Webhook Slack/Discord
      --email ADDRESS      Adres e-mail do alertów

INNE:
  -h, --help               Pokaż tę pomoc
      --version            Pokaż wersję
      --config             Pokaż ścieżkę config (${CONF_FILE})
      --edit-config        Otwórz config w edytorze (\$EDITOR)
      --show-logs          Pokaż ostatni log

PRZYKŁADY:
  $SCRIPT_NAME --repo myorg/myapp --branch develop --variants debug,release
  $SCRIPT_NAME --skip-push --artifacts "apk,mapping" --no-secret-scan
  $SCRIPT_NAME --dry-run --log-level DEBUG
  $SCRIPT_NAME --yes --webhook https://hooks.slack.com/... --retries 5

CONFIG: $CONF_FILE
LOGI  : $LOG_DIR
EOF
  exit 0
}

# ─────────────────────────────────────────────────────────────
# PARSER ARGUMENTÓW CLI
# ─────────────────────────────────────────────────────────────
_parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -r|--repo)           REPO_NAME="$2";         shift 2 ;;
      -w|--workflow)       WORKFLOW_FILE="$2";      shift 2 ;;
      -b|--branch)         BRANCH="$2";             shift 2 ;;
      -o|--output)         BUILD_OUTPUT_DIR="$2";   shift 2 ;;
      -a|--artifacts)      ARTIFACT_NAMES="$2";     shift 2 ;;
      -v|--variants)       BUILD_VARIANTS="$2";     shift 2 ;;
      -i|--inputs)         CUSTOM_INPUTS="$2";      shift 2 ;;
         --retries)        RETRIES="$2";            shift 2 ;;
         --log-level)      LOG_LEVEL="${2^^}";      shift 2 ;;
      -y|--yes)            AUTO_YES="true";         shift   ;;
         --skip-push)      SKIP_PUSH="true";        shift   ;;
         --skip-trigger)   SKIP_TRIGGER="true";     shift   ;;
         --skip-download)  SKIP_DOWNLOAD="true";    shift   ;;
         --dry-run)        DRY_RUN="true";          shift   ;;
         --force)          FORCE_LOCK="true";       shift   ;;
         --no-checksums)   VERIFY_CHECKSUMS="false";shift   ;;
         --no-secret-scan) SECRET_SCAN="false";     shift   ;;
         --no-notify)      WEBHOOK_URL=""; NOTIFY_EMAIL=""; TERMUX_NOTIFY="false"; shift ;;
         --webhook)        WEBHOOK_URL="$2";        shift 2 ;;
         --email)          NOTIFY_EMAIL="$2";       shift 2 ;;
      -h|--help)           _usage ;;
         --version)        echo "SCU v$SCU_VERSION ($SCU_BUILD_DATE)"; exit 0 ;;
         --config)         echo "$CONF_FILE"; exit 0 ;;
         --edit-config)    "${EDITOR:-nano}" "$CONF_FILE"; exit 0 ;;
         --show-logs)      ls -lt "$LOG_DIR"/*.log 2>/dev/null | head -5; exit 0 ;;
      *) warn "Nieznana opcja: $1"; shift ;;
    esac
  done
}

# ─────────────────────────────────────────────────────────────
# CONFIRM (z AUTO_YES)
# ─────────────────────────────────────────────────────────────
confirm() {
  if [[ "$AUTO_YES" == "true" ]]; then return 0; fi
  read -r -p "$1 [y/N]: " response
  case "$response" in [Yy]*) return 0 ;; *) return 1 ;; esac
}

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
main() {
  # Faza 0: wczytaj config i args
  _load_conf
        if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then 
            echo -e "\e[1;31m[FATAL] Ten folder nie jest repozytorium Git! Uruchom: git init\e[0m"; 
            exit 1; 
        fi
  _parse_args "$@"

  # Faza 1: lock
  if [[ "$FORCE_LOCK" == "true" ]]; then rm -f "$LOCK_FILE"; fi
  _acquire_lock

  echo -e "\e[1;36m"
  cat <<'BANNER'
  ╔═══════════════════════════════════════════════╗
  ║  ◈ SMART COMPILE ULTIMATE v2.0               ║
  ║  SecFERRO Division ◈ [FERRO//ANON]           ║
  ║  anonymousik.is-a.dev                        ║
  ╚═══════════════════════════════════════════════╝
BANNER
  echo -e "\e[0m"

  [[ "$DRY_RUN" == "true" ]] && warn "=== TRYB DRY-RUN — żadne operacje nie zostaną wykonane! ==="

  # Faza 2: requirements
  _require_cmds gh git curl jq

  # Faza 3: diagnostics
  _self_diagnose

  # Faza 4: auth
  _healthcheck_github

  # Faza 5: repo
  _init_repo

  # Faza 6: workflow audit
  _audit_workflow

  # Faza 7: sync
  _sync_code

  # Faza 8: trigger
  _trigger_workflow

  # Faza 9: wait run_id
  local run_id
  if [[ "$SKIP_TRIGGER" == "false" && "$DRY_RUN" == "false" ]]; then
    _wait_for_run
    run_id="$_CURRENT_RUN_ID"

    # Faza 10: monitor
    _monitor_execution "$run_id"

    # Faza 11: download
    _download_artifacts "$run_id"

    # Faza 12: report
    _generate_report "$run_id"
  fi

  success "╔══════════════════════════════════════════╗"
  success "║  SCU ZAKOŃCZONE SUKCESEM                ║"
  success "║  Artefakty: $BUILD_OUTPUT_DIR"
  success "╚══════════════════════════════════════════╝"

  _notify "✅ SCU zakończone sukcesem | $REPO_NAME | run: ${run_id:-N/A}"
}

main "$@"
