#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║  SCU v2.0 — INSTALLER                                   ║
# ║  SecFERRO Division ◈ anonymousik.is-a.dev              ║
# ║                                                          ║
# ║  curl -fsSL https://anonymousik.is-a.dev/scu/install.sh | bash
# ║  wget -qO-  https://anonymousik.is-a.dev/scu/install.sh | bash
# ╚══════════════════════════════════════════════════════════╝

set -Eeuo pipefail

# ─────────────────────────────────────────────
# STAŁE
# ─────────────────────────────────────────────
readonly SCU_VERSION="2.0.0"
readonly BASE_URL="https://anonymousik.is-a.dev/scu"
readonly SCRIPT_URL="${BASE_URL}/smart_compile_ultimate.sh"
readonly CHECKSUM_URL="${BASE_URL}/checksums.txt"
readonly INSTALL_DIR="${HOME}/bin"
readonly INSTALL_PATH="${INSTALL_DIR}/scu.sh"

# ─────────────────────────────────────────────
# KOLORY
# ─────────────────────────────────────────────
C_CYAN='\e[1;36m'; C_GREEN='\e[1;32m'
C_YELLOW='\e[1;33m'; C_RED='\e[1;31m'; C_RESET='\e[0m'

log()     { echo -e "${C_CYAN}[INFO]${C_RESET}    $*"; }
success() { echo -e "${C_GREEN}[OK]${C_RESET}      $*"; }
warn()    { echo -e "${C_YELLOW}[WARN]${C_RESET}    $*"; }
err()     { echo -e "${C_RED}[ERROR]${C_RESET}   $*" >&2; }
fatal()   { err "$*"; exit 1; }

# ─────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────
echo -e "${C_CYAN}"
cat <<'BANNER'
  ╔══════════════════════════════════════════════════╗
  ║  SMART COMPILE ULTIMATE v2.0 — INSTALLER        ║
  ║  SecFERRO Division ◈ [FERRO//ANON]              ║
  ║  anonymousik.is-a.dev                           ║
  ╚══════════════════════════════════════════════════╝
BANNER
echo -e "${C_RESET}"

# ─────────────────────────────────────────────
# WYKRYCIE ŚRODOWISKA
# ─────────────────────────────────────────────
_detect_env() {
  if grep -qi "android" /proc/version 2>/dev/null; then
    ENV_TYPE="termux"
    PKG_MGR="pkg"
    log "Wykryto środowisko: Android/Termux"
  elif command -v apt-get &>/dev/null; then
    ENV_TYPE="debian"
    PKG_MGR="apt-get"
    log "Wykryto środowisko: Debian/Ubuntu"
  elif command -v apk &>/dev/null; then
    ENV_TYPE="alpine"
    PKG_MGR="apk add"
    log "Wykryto środowisko: Alpine Linux"
  else
    ENV_TYPE="generic"
    PKG_MGR=""
    warn "Nieznane środowisko — automatyczna instalacja zależności wyłączona."
  fi
}

# ─────────────────────────────────────────────
# INSTALACJA ZALEŻNOŚCI
# ─────────────────────────────────────────────
_install_deps() {
  local required=(git curl jq)
  local missing=()

  for cmd in "${required[@]}"; do
    command -v "$cmd" &>/dev/null || missing+=("$cmd")
  done

  if (( ${#missing[@]} == 0 )); then
    success "Wszystkie zależności bazowe obecne."
    return
  fi

  log "Brakujące pakiety: ${missing[*]}"

  if [[ -z "$PKG_MGR" ]]; then
    fatal "Brak menedżera pakietów. Zainstaluj ręcznie: ${missing[*]}"
  fi

  case "$ENV_TYPE" in
    termux)
      pkg update -y &>/dev/null
      pkg install -y "${missing[@]}"
      ;;
    debian)
      sudo apt-get update -qq
      sudo apt-get install -y "${missing[@]}"
      ;;
    alpine)
      apk add --no-cache "${missing[@]}"
      ;;
  esac

  success "Zależności zainstalowane."

  # gh CLI — osobna instalacja jeśli brak
  if ! command -v gh &>/dev/null; then
    _install_gh_cli
  fi
}

_install_gh_cli() {
  log "Instalacja GitHub CLI (gh)..."
  case "$ENV_TYPE" in
    termux)
      pkg install -y gh && success "gh zainstalowane (Termux)." && return
      ;;
    debian)
      # Oficjalny skrypt GitHub
      curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
      echo "deb [arch=$(dpkg --print-architecture) \
        signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
        https://cli.github.com/packages stable main" \
        | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
      sudo apt-get update -qq && sudo apt-get install -y gh
      success "gh zainstalowane (apt)."
      return
      ;;
    alpine)
      apk add --no-cache github-cli 2>/dev/null && success "gh zainstalowane (apk)." && return
      ;;
  esac
  warn "Nie udało się automatycznie zainstalować gh CLI."
  warn "Instrukcja ręczna: https://github.com/cli/cli#installation"
}

# ─────────────────────────────────────────────
# POBRANIE SCU
# ─────────────────────────────────────────────
_download_scu() {
  log "Pobieram SCU v${SCU_VERSION}..."
  mkdir -p "$INSTALL_DIR"

  # Preferuj curl, fallback wget
  if command -v curl &>/dev/null; then
    curl -fsSL "$SCRIPT_URL" -o "$INSTALL_PATH" \
      || fatal "Nie udało się pobrać SCU przez curl."
  elif command -v wget &>/dev/null; then
    wget -q "$SCRIPT_URL" -O "$INSTALL_PATH" \
      || fatal "Nie udało się pobrać SCU przez wget."
  else
    fatal "Brak curl ani wget — nie można pobrać SCU."
  fi

  chmod +x "$INSTALL_PATH"
  success "SCU pobrane → $INSTALL_PATH"
}

# ─────────────────────────────────────────────
# WERYFIKACJA CHECKSUM
# ─────────────────────────────────────────────
_verify_checksum() {
  log "Weryfikacja SHA-256..."

  local remote_sum
  remote_sum=$(
    if command -v curl &>/dev/null; then
      curl -fsSL "$CHECKSUM_URL"
    else
      wget -qO- "$CHECKSUM_URL"
    fi | grep "smart_compile_ultimate.sh" | awk '{print $1}'
  )

  if [[ -z "$remote_sum" ]]; then
    warn "Nie można pobrać checksums.txt — pomijam weryfikację."
    return 0
  fi

  local local_sum
  local_sum=$(sha256sum "$INSTALL_PATH" | awk '{print $1}')

  if [[ "$remote_sum" == "$local_sum" ]]; then
    success "SHA-256 zweryfikowany: ${local_sum:0:16}..."
  else
    err "CHECKSUM MISMATCH!"
    err "  Oczekiwany: $remote_sum"
    err "  Pobrany:    $local_sum"
    rm -f "$INSTALL_PATH"
    fatal "Instalacja przerwana — plik może być uszkodzony lub podmieniony."
  fi
}

# ─────────────────────────────────────────────
# KONFIGURACJA PATH
# ─────────────────────────────────────────────
_setup_path() {
  # Sprawdź czy ~/bin jest już w PATH
  if echo "$PATH" | grep -q "${HOME}/bin"; then
    debug_info "~/bin już w PATH."
    return 0
  fi

  local shell_rc=""
  case "${SHELL:-bash}" in
    */zsh)  shell_rc="${HOME}/.zshrc"  ;;
    */bash) shell_rc="${HOME}/.bashrc" ;;
    *)      shell_rc="${HOME}/.profile" ;;
  esac

  if [[ -n "$shell_rc" ]]; then
    echo '' >> "$shell_rc"
    echo '# SCU — Smart Compile Ultimate' >> "$shell_rc"
    echo 'export PATH="$HOME/bin:$PATH"' >> "$shell_rc"
    warn "Dodano ~/bin do PATH w $shell_rc"
    warn "Uruchom: source $shell_rc  (lub otwórz nową sesję)"
  fi
}

debug_info() { :; }  # placeholder

# ─────────────────────────────────────────────
# WERYFIKACJA INSTALACJI
# ─────────────────────────────────────────────
_verify_install() {
  if [[ -x "$INSTALL_PATH" ]]; then
    local ver
    ver=$(bash "$INSTALL_PATH" --version 2>/dev/null || echo "?")
    success "Instalacja zakończona: $ver"
  else
    fatal "Plik $INSTALL_PATH nie istnieje lub nie jest wykonywalny."
  fi
}

# ─────────────────────────────────────────────
# PODSUMOWANIE
# ─────────────────────────────────────────────
_print_summary() {
  echo ""
  echo -e "${C_GREEN}╔══════════════════════════════════════════════════╗${C_RESET}"
  echo -e "${C_GREEN}║  SCU v${SCU_VERSION} zainstalowane pomyślnie!          ║${C_RESET}"
  echo -e "${C_GREEN}╚══════════════════════════════════════════════════╝${C_RESET}"
  echo ""
  echo -e "  Plik:     ${C_CYAN}${INSTALL_PATH}${C_RESET}"
  echo -e "  Config:   ${C_CYAN}~/.scu/scu.conf${C_RESET}  (generowany przy 1. uruchomieniu)"
  echo -e "  Logi:     ${C_CYAN}~/.scu/logs/${C_RESET}"
  echo ""
  echo -e "  ${C_YELLOW}Następne kroki:${C_RESET}"
  echo -e "    1. gh auth login"
  echo -e "    2. scu.sh --edit-config"
  echo -e "    3. scu.sh --dry-run --log-level DEBUG"
  echo -e "    4. scu.sh --repo twojOrg/twojApp --yes"
  echo ""
  echo -e "  Dokumentacja: ${C_CYAN}https://anonymousik.is-a.dev/scu/docs${C_RESET}"
  echo ""
  echo -e "  ${C_CYAN}[FERRO//ANON] ◈ SecFERRO Division${C_RESET}"
  echo ""
}

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
main() {
  _detect_env
  _install_deps
  _download_scu
  _verify_checksum
  _setup_path
  _verify_install
  _print_summary
}

main "$@"
