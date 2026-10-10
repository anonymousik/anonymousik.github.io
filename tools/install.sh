#!/data/data/com.termux/files/usr/bin/bash
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  SecFerro v2 — Installer dla Termux/Android                             ║
# ║                                                                          ║
# ║  Co instaluje:                                                           ║
# ║  • Katalog ~/secferro z pełną strukturą                                 ║
# ║  • Skrypty: sfstart sfstop sfmail sflog sftest secferro                 ║
# ║  • Aliasy w ~/.bashrc i ~/.zshrc                                        ║
# ║  • Zależności: qemu-system-x86-64, msmtp, netcat-openbsd, openssh      ║
# ║  • Konfiguracja startowa secferro.conf                                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
set -euo pipefail

INSTALL_DIR="${HOME}/secferro"
SCRIPTS_SRC="$(cd "$(dirname "$0")/scripts" 2>/dev/null && pwd || echo "$PWD/scripts")"
BIN_DIR="/data/data/com.termux/files/usr/bin"

R='\033[0m'; B='\033[1m'
GRN='\033[92m'; RED='\033[91m'; YLW='\033[93m'; CYN='\033[96m'; D='\033[2m'
ok()   { echo -e "${GRN}${B}[✓]${R} $*"; }
err()  { echo -e "${RED}${B}[✗]${R} $*"; }
warn() { echo -e "${YLW}${B}[!]${R} $*"; }
info() { echo -e "${CYN}[i]${R} $*"; }
step() { echo -e "\n${CYN}${B}── $* ──${R}\n"; }

# ─────────────────────────────────────────────────────────────────────────────
banner() {
    echo -e "\n${CYN}${B}"
    echo "  ╔═══════════════════════════════════════════════════╗"
    echo "  ║  SecFerro v2.0  ·  Installer  ·  Termux/Android  ║"
    echo "  ║  RouterOS on QEMU + SMTP Relay + Security Suite   ║"
    echo "  ╚═══════════════════════════════════════════════════╝"
    echo -e "${R}"
}

# ─────────────────────────────────────────────────────────────────────────────
check_platform() {
    step "Weryfikacja platformy"

    if [[ ! -d "/data/data/com.termux" ]]; then
        warn "Nie wykryto środowiska Termux — próbuję kontynuować..."
        BIN_DIR="/usr/local/bin"
    else
        ok "Termux wykryty ✓"
    fi

    local arch; arch=$(uname -m)
    info "Architektura: $arch"
    case "$arch" in
        aarch64|arm64) ok "ARM64 — obsługiwane (QEMU TCG mode)" ;;
        x86_64)        ok "x86_64 — obsługiwane (QEMU z opcjonalnym KVM)" ;;
        armv7l)        warn "ARMv7 (32-bit) — QEMU może być wolniejszy" ;;
        *)             warn "Nieznana architektura: $arch" ;;
    esac

    local free_mb; free_mb=$(df "$HOME" | awk 'NR==2{printf "%d", $4/1024}')
    info "Wolne miejsce: ${free_mb}MB"
    [[ $free_mb -lt 200 ]] && warn "Mało miejsca! QEMU image wymaga min. 64MB + RouterOS CHR ~64MB"

    local ram_mb; ram_mb=$(awk '/MemAvailable/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo "?")
    info "Wolna pamięć RAM: ${ram_mb}MB (RouterOS VM wymaga 256MB)"
}

# ─────────────────────────────────────────────────────────────────────────────
install_deps() {
    step "Instalacja zależności (pkg)"

    local PKGS=(
        "qemu-system-x86-64"   # QEMU emulator dla RouterOS CHR (x86)
        "msmtp"                # SMTP client + msmtpd relay daemon
        "openssh"              # SSH client do RouterOS
        "netcat-openbsd"       # nc — sprawdzanie portów TCP
        "iproute2"             # ip addr, ip route
        "socat"                # Opcjonalny: QEMU monitor socket
        "curl"                 # Download narzędzia
    )

    local OPTIONAL=(
        "nmap"           # Port scanner (sftest opcjonalny)
        "dnsutils"       # nslookup, dig
        "net-tools"      # netstat
    )

    info "Aktualizuję listę pakietów..."
    pkg update -y 2>/dev/null | tail -3 || warn "pkg update nieudane — kontynuuję"

    for pkg in "${PKGS[@]}"; do
        if command -v "${pkg%%-*}" >/dev/null 2>&1 || pkg list-installed 2>/dev/null | grep -q "^$pkg"; then
            ok "$pkg — już zainstalowany"
        else
            info "Instaluję: $pkg..."
            pkg install -y "$pkg" 2>/dev/null \
                && ok "$pkg zainstalowany ✓" \
                || warn "$pkg — błąd instalacji (kontynuuję)"
        fi
    done

    echo
    info "Pakiety opcjonalne:"
    for pkg in "${OPTIONAL[@]}"; do
        pkg install -y "$pkg" 2>/dev/null \
            && ok "$pkg zainstalowany" \
            || info "$pkg — niedostępny (OK, niewymagany)"
    done
}

# ─────────────────────────────────────────────────────────────────────────────
create_dirs() {
    step "Tworzenie struktury katalogów"

    local DIRS=(
        "$INSTALL_DIR/conf"
        "$INSTALL_DIR/logs"
        "$INSTALL_DIR/run"
        "$INSTALL_DIR/vm"
        "$INSTALL_DIR/backups"
        "$INSTALL_DIR/reports"
    )

    for d in "${DIRS[@]}"; do
        mkdir -p "$d"
        ok "  $d"
    done
    chmod 700 "$INSTALL_DIR"
}

# ─────────────────────────────────────────────────────────────────────────────
install_scripts() {
    step "Instalacja skryptów SecFerro"

    local SCRIPTS=(sfstart sfstop sfmail sflog sftest secferro)

    for script in "${SCRIPTS[@]}"; do
        local src="${SCRIPTS_SRC}/${script}"
        local dst="${BIN_DIR}/${script}"

        if [[ ! -f "$src" ]]; then
            warn "Brak pliku źródłowego: $src — pomijam"
            continue
        fi

        cp "$src" "$dst"
        chmod 755 "$dst"
        ok "  $script → $dst"
    done

    # Dodaj shortcut 'sfwait' (czekaj na boot RouterOS)
    cat > "${BIN_DIR}/sfwait" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# sfwait — czekaj aż RouterOS SSH będzie dostępny
SF_HOME="${SF_HOME:-$HOME/secferro}"
[[ -f "${SF_HOME}/conf/secferro.conf" ]] && source "${SF_HOME}/conf/secferro.conf"
: "${PORT_SSH:=2222}"
echo "Czekam na RouterOS SSH (127.0.0.1:$PORT_SSH)..."
timeout=120; elapsed=0
while ! nc -z 127.0.0.1 "$PORT_SSH" 2>/dev/null; do
    printf "\r  ⏳ %ds/%ds" "$elapsed" "$timeout"
    sleep 3; elapsed=$((elapsed+3))
    [[ $elapsed -ge $timeout ]] && { echo; echo "[!] Timeout — RouterOS nie odpowiada"; exit 1; }
done
echo; echo "[✓] RouterOS gotowy po ${elapsed}s!"
EOF
    chmod 755 "${BIN_DIR}/sfwait"
    ok "  sfwait → ${BIN_DIR}/sfwait"

    # sfupdate — aktualizuj SecFerro scripts z bieżącego katalogu
    cat > "${BIN_DIR}/sfupdate" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
# sfupdate — zaktualizuj skrypty SecFerro
SCRIPT_DIR="\$(cd "\$(dirname "\$0")/.." && pwd)"
SRC="\${SCRIPT_DIR}/scripts"
BIN="$BIN_DIR"
echo "Aktualizuję SecFerro scripts z: \$SRC"
for s in sfstart sfstop sfmail sflog sftest secferro; do
    [[ -f "\${SRC}/\${s}" ]] && cp "\${SRC}/\${s}" "\${BIN}/\${s}" && chmod 755 "\${BIN}/\${s}" && echo "  ✓ \$s" || echo "  - \$s (brak)"
done
echo "Gotowe!"
EOF
    chmod 755 "${BIN_DIR}/sfupdate"
    ok "  sfupdate → ${BIN_DIR}/sfupdate"
}

# ─────────────────────────────────────────────────────────────────────────────
create_default_config() {
    step "Tworzenie domyślnej konfiguracji"

    local conf="${INSTALL_DIR}/conf/secferro.conf"

    if [[ -f "$conf" ]]; then
        info "Konfiguracja już istnieje: $conf"
        info "Pomijam — nie nadpiszę istniejących ustawień"
        return
    fi

    cat > "$conf" <<EOF
# SecFerro v2 — konfiguracja domyślna
# Wygenerowano: $(date)
# Edytuj w: secferro → Konfiguracja

# ── VM ─────────────────────────────────────────────────────────────────────
VM_RAM="256"
VM_DISK="${INSTALL_DIR}/vm/routeros.img"
VM_ARCH="x86_64"

# ── Sieć QEMU (user/slirp) ─────────────────────────────────────────────────
NET_SUBNET="192.168.168.0/24"
NET_HOST_GW="192.168.168.1"   # IP hosta widoczne z VM
NET_VM_IP="192.168.168.3"     # IP RouterOS (DHCP)
NET_SUBNET_CIDR="24"

# ── Port forwards (Host → VM) ───────────────────────────────────────────────
PORT_SSH="2222"      # SSH RouterOS
PORT_SMTP_IN="2525"  # SMTP do VM (debugging)
PORT_WINBOX="8291"   # Winbox GUI
PORT_API="8728"      # RouterOS API

# ── SMTP relay (VM → Host → Internet via guestfwd) ─────────────────────────
PORT_SMTP_RELAY="2526"   # msmtpd relay listener

# ── RouterOS ────────────────────────────────────────────────────────────────
ROS_USER="admin"
ROS_PASS=""

# ── Email ───────────────────────────────────────────────────────────────────
MAIL_FROM="router@secferro.lan"
MAIL_RELAY_HOST="smtp.gmail.com"
MAIL_RELAY_PORT="587"
MAIL_RELAY_USER=""      # ustaw przez: sfmail configure
MAIL_RELAY_PASS=""
MAIL_ALERT_TO=""

# ── DNS ─────────────────────────────────────────────────────────────────────
DNS_DOMAIN="secferro.lan"
EOF
    chmod 600 "$conf"
    ok "Konfiguracja domyślna: $conf"
}

# ─────────────────────────────────────────────────────────────────────────────
setup_shell_aliases() {
    step "Konfiguracja aliasów powłoki"

    local ALIAS_BLOCK='
# ─── SecFerro v2 ─────────────────────────────────────────────────────────────
export SF_HOME="$HOME/secferro"
alias sfstart="sfstart"
alias sfstop="sfstop"
alias sfwait="sfwait"
alias sftest="sftest"
alias sflog="sflog"
alias sfmail="sfmail"
alias sfupdate="sfupdate"
# ─────────────────────────────────────────────────────────────────────────────
'
    local ALIAS_MARKER="# ─── SecFerro v2"

    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [[ -f "$rc" ]]; then
            if grep -q "$ALIAS_MARKER" "$rc" 2>/dev/null; then
                info "  $rc — aliasy SecFerro już obecne"
            else
                echo "$ALIAS_BLOCK" >> "$rc"
                ok "  $rc — dodano aliasy"
            fi
        else
            info "  $rc — nie istnieje (pomijam)"
        fi
    done

    # Utwórz .bashrc jeśli brak
    if [[ ! -f "$HOME/.bashrc" ]]; then
        echo "$ALIAS_BLOCK" > "$HOME/.bashrc"
        ok "  ~/.bashrc — utworzono z aliasami"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
check_routeros_image() {
    step "Sprawdzanie obrazu RouterOS VM"

    local img="${INSTALL_DIR}/vm/routeros.img"

    if [[ -f "$img" ]]; then
        local size; size=$(du -sh "$img" | cut -f1)
        ok "Obraz RouterOS istnieje: $img ($size)"
    else
        warn "Brak obrazu RouterOS: $img"
        echo
        echo -e "  ${B}Jak uzyskać obraz RouterOS CHR:${R}"
        echo
        echo "  1. Pobierz RouterOS CHR (Cloud Hosted Router) x86:"
        echo -e "     ${CYN}https://mikrotik.com/download#chr${R}"
        echo "     Wybierz: CHR x86 → RAW disk image (.img.zip)"
        echo
        echo "  2. Wypakuj i przenieś:"
        echo -e "     ${D}unzip chr-6.49.13.img.zip${R}"
        echo -e "     ${D}mv chr-6.49.13.img ${img}${R}"
        echo
        echo "  3. Lub użyj QEMU żeby skompresować rozmiar:"
        echo -e "     ${D}qemu-img convert -f raw chr.img -O qcow2 ${img}${R}"
        echo
        echo -e "  ${YLW}VM nie uruchomi się bez obrazu!${R}"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
run_post_checks() {
    step "Weryfikacja instalacji"

    local ALL_OK=1

    # Sprawdź każdy skrypt
    for cmd in sfstart sfstop sfmail sflog sftest secferro sfwait; do
        if command -v "$cmd" >/dev/null 2>&1; then
            ok "  $cmd — dostępny"
        else
            err "  $cmd — NIEDOSTĘPNY (sprawdź $BIN_DIR)"
            ALL_OK=0
        fi
    done

    # Sprawdź QEMU
    echo
    if command -v qemu-system-x86_64 >/dev/null 2>&1; then
        local qver; qver=$(qemu-system-x86_64 --version 2>/dev/null | head -1)
        ok "QEMU: $qver"
    else
        err "qemu-system-x86_64 — NIEDOSTĘPNY!"
        echo -e "  ${D}Zainstaluj: pkg install qemu-system-x86-64${R}"
        ALL_OK=0
    fi

    # msmtp
    if command -v msmtp >/dev/null 2>&1; then
        local mver; mver=$(msmtp --version 2>/dev/null | head -1)
        ok "msmtp: $mver"
    else
        err "msmtp — NIEDOSTĘPNY!"
        ALL_OK=0
    fi

    # msmtpd
    command -v msmtpd >/dev/null 2>&1 && ok "msmtpd relay daemon — dostępny ✓" \
        || warn "msmtpd — niedostępny (wchodzi w pakiet msmtp)"

    # SSH
    command -v ssh >/dev/null 2>&1 && ok "ssh client — dostępny ✓" \
        || err "ssh — NIEDOSTĘPNY!"

    [[ $ALL_OK -eq 1 ]] && return 0 || return 1
}

# ─────────────────────────────────────────────────────────────────────────────
print_next_steps() {
    echo -e "\n${CYN}${B}"
    echo "  ╔═══════════════════════════════════════════════════════════╗"
    echo "  ║  INSTALACJA ZAKOŃCZONA — Następne kroki                   ║"
    echo "  ╚═══════════════════════════════════════════════════════════╝"
    echo -e "${R}"
    echo
    echo -e "  ${B}1. Pobierz obraz RouterOS CHR (jeśli jeszcze nie masz):${R}"
    echo -e "     ${D}https://mikrotik.com/download#chr  →  CHR x86 RAW image${R}"
    echo -e "     ${D}mv chr-*.img ~/secferro/vm/routeros.img${R}"
    echo
    echo -e "  ${B}2. Uruchom VM:${R}"
    echo -e "     ${CYN}sfstart${R}"
    echo
    echo -e "  ${B}3. Poczekaj na boot RouterOS (~30-60s):${R}"
    echo -e "     ${CYN}sfwait${R}"
    echo
    echo -e "  ${B}4. Połącz się z RouterOS:${R}"
    echo -e "     ${CYN}ssh -p 2222 admin@127.0.0.1${R}"
    echo
    echo -e "  ${B}5. Skonfiguruj email relay (opcjonalnie):${R}"
    echo -e "     ${CYN}sfmail configure${R}"
    echo
    echo -e "  ${B}6. Uruchom relay SMTP:${R}"
    echo -e "     ${CYN}sfmail start${R}"
    echo
    echo -e "  ${B}7. Dashboard i menu:${R}"
    echo -e "     ${CYN}secferro${R}"
    echo
    echo -e "  ${B}8. Test bezpieczeństwa:${R}"
    echo -e "     ${CYN}sftest${R}"
    echo
    echo -e "  ${D}Dokumentacja: ~/secferro/docs/  |  Konfiguracja: ~/secferro/conf/secferro.conf${R}"
    echo -e "  ${D}Przeładuj shell: source ~/.bashrc${R}"
    echo
}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

banner
check_platform

# Potwierdzenie instalacji
echo -e "  ${B}Katalog instalacji: ${CYN}${INSTALL_DIR}${R}"
echo -e "  ${B}Katalog binariów:   ${CYN}${BIN_DIR}${R}"
echo
read -rp "  $(echo -e "${CYN}${B}Zainstalować SecFerro v2? [T/n] > ${R}")" ans
[[ "${ans,,}" == "n" ]] && { echo "Anulowano."; exit 0; }

# Wybór: pełna instalacja vs tylko skrypty
echo
echo -e "  ${B}Tryb instalacji:${R}"
echo -e "  1. Pełna (pkg install + katalogi + skrypty + aliasy)"
echo -e "  2. Tylko skrypty (zaktualizuj skrypty, zachowaj konfigurację)"
echo
read -rp "  $(echo -e "${CYN}Tryb [1/2] > ${R}")" mode_ans

case "${mode_ans:-1}" in
    2)
        create_dirs
        install_scripts
        run_post_checks
        ;;
    *)
        install_deps
        create_dirs
        install_scripts
        create_default_config
        setup_shell_aliases
        check_routeros_image
        run_post_checks
        ;;
esac

print_next_steps
