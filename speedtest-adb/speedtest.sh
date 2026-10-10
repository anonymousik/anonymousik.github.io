#!/usr/bin/env bash
# ==============================================================================
# PROJEKT:     Anonymousik.is-a.dev/scripts/speedtest-adb
# WERSJA:      1.2.0
# PLATFORMA:   Host (Linux/macOS) -> Target (Android TV 9 / Shell Toybox)
# AUTOR:       Anonymousik
# OPIS:        Kompleksowy test sieci (Ping/DL/UL) z interfejsem ANSI Art GUI
# ==============================================================================

#set -eE -o pipefail

# ==============================================================================
# KONFIGURACJA SEKTORA SIECIOWEGO
# ==============================================================================
DEVICE_IP=${1:-"192.168.1.3"}
REMOTE_DIR="/data/local/tmp"
LOCAL_CURL="./curl"

# --- PALETA ANSI ---
C_RST="\e[0m"
C_BOLD="\e[1m"
C_RED="\e[31m"
C_GREEN="\e[32m"
C_YELLOW="\e[33m"
C_CYAN="\e[36m"
C_MAGENTA="\e[35m"

# ==============================================================================
# SEKCJA UI (ANSI ART GUI)
# ==============================================================================
function draw_gui_banner() {
    clear
    echo -e "${C_CYAN}${C_BOLD}"
    cat << "EOF"
 ▄▄▄       ███▄    █  ▒█████   ███▄ ▄███▓▓██   ██▓ ▄████▄   ▒█████   █    ██   ██████ 
▒████▄     ██ ▀█   █ ▒██▒  ██▒▓██▒▀█▀ ██▒ ▒██  ██▒▒██▀ ▀█  ▒██▒  ██▒ ██  ▓██▒▒██    ▒ 
▒██  ▀█▄  ▓██  ▀█ ██▒▒██░  ██▒▓██    ▓██░  ▒██ ██░▒▓█    ▄ ▒██░  ██▒▓██  ▒██░░ ▓██▄   
░██▄▄▄▄██ ▓██▒  ▐▌██▒▒██   ██░▒██    ▒██   ░ ▐██▓░▒▓▓▄ ▄██▒▒██   ██░▓▓█  ░██░  ▒   ██▒
 ▓█   ▓██▒▒██░   ▓██░░ ████▓▒░▒██▒   ░██▒  ░ ██▒▓░▒ ▓███▀ ░░ ████▓▒░▒▒█████▓ ▒██████▒▒
 ▒▒   ▓▒█░░ ▒░   ▒ ▒ ░ ▒░▒░▒░ ░ ▒░   ░  ░   ██▒▒▒ ░ ░▒ ▒  ░░ ▒░▒░▒░ ░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░
EOF
    echo -e "${C_MAGENTA}          is-a.dev/scripts/speedtest-adb | Target: ATV9 (Toybox)${C_RST}"
    echo -e "${C_CYAN}==========================================================================${C_RST}\n"
}

function print_log() { echo -e "${C_BOLD}${C_YELLOW}[*]${C_RST} $1"; }
function print_err() { echo -e "${C_BOLD}${C_RED}[!] BŁĄD:${C_RST} $1"; }
function print_ok()  { echo -e "${C_BOLD}${C_GREEN}[+]${C_RST} $1"; }

# ==============================================================================
# LOGIKA OPERACYJNA
# ==============================================================================
function init_connection() {
    print_log "Inicjalizacja: Bypass DNS (Direct IP Routing) na $DEVICE_IP..."
    adb connect "$DEVICE_IP" > /dev/null 2>&1 || true
    
    # Przesłanie curl (Zabezpieczenie poprawności ścieżek względem oryginalnego skryptu)
    if [ ! -f "$LOCAL_CURL" ]; then
        print_err "Brak binarium $LOCAL_CURL w systemie hosta!"
        exit 1
    fi
    
    print_log "Wysyłam curl na zdalne urządzenie adb do $REMOTE_DIR..."
    adb -s "$DEVICE_IP" push "$LOCAL_CURL" "$REMOTE_DIR/curl" > /dev/null 2>&1
    adb -s "$DEVICE_IP" shell "chmod +x $REMOTE_DIR/curl"
    print_ok "Payload sieciowy zainstalowany pomyślnie."
}

function test_connectivity() {
    print_log "Testowanie dostępności brzegowej Cloudflare (Anycast)..."
    local CONN_CHECK=$(adb -s "$DEVICE_IP" shell "$REMOTE_DIR/curl -v --connect-timeout 5 http://162.159.140.220/ 2>&1" | grep "Connected" || true)
    
    if [ -n "$CONN_CHECK" ]; then
        print_ok "Nawiązano połączenie z klastrem (Status: Connected)."
    else
        print_err "Brak odpowiedzi HTTP od CDN. Sprawdź ruting IP."
        cleanup_and_exit 1
    fi
}

function run_ping_test() {
    print_log "Analiza opóźnień (ICMP Ping)..."
    local PING_RES=$(adb -s "$DEVICE_IP" shell "ping -c 4 -W 2 162.159.140.220 2>/dev/null | tail -1 | awk -F '/' '{print \$4}'")
    if [ -n "$PING_RES" ]; then
        echo -e "    ${C_CYAN}---> ŚREDNI PING:${C_RST} ${C_BOLD}${PING_RES} ms${C_RST}"
    else
        print_err "Ping zablokowany lub pakiet utracony."
    fi
}

function run_download_test() {
    print_log "Rozpoczynam pomiar przepustowości DOWNLOAD (50MB)..."
    local DL_RESULT=$(adb -s "$DEVICE_IP" shell "$REMOTE_DIR/curl -o /dev/null -s -w '%{speed_download}' \
        -H 'Host: speed.cloudflare.com' \
        'http://162.159.140.220/__down?bytes=50000000'")
        
    if [ -n "$DL_RESULT" ] && [ "$DL_RESULT" != "0" ]; then
        local MBPS=$(awk -v d="$DL_RESULT" 'BEGIN { printf "%.2f", (d*8)/1000000 }')
        echo -e "    ${C_GREEN}---> WYNIK DOWNLOAD:${C_RST} ${C_BOLD}${MBPS} Mbps${C_RST}"
    else
        print_err "CDN nie odpowiedział w trakcie pobierania."
    fi
}

function run_upload_test() {
    print_log "Rozpoczynam pomiar przepustowości UPLOAD (Test 20MB)..."
    
    # Generowanie próbki danych (entropia systemowa na ATV9)
    print_log "Buforowanie pakietu testowego w pamięci tymczasowej..."
    adb -s "$DEVICE_IP" shell "dd if=/dev/urandom of=$REMOTE_DIR/test.bin bs=1M count=20 2>/dev/null"
    
    local UL_RESULT=$(adb -s "$DEVICE_IP" shell "$REMOTE_DIR/curl -X POST --data-binary @$REMOTE_DIR/test.bin -o /dev/null -s -w '%{speed_upload}' \
        -H 'Host: speed.cloudflare.com' \
        'http://162.159.140.220/__up'")
        
    # Usunięcie pakietu testowego
    adb -s "$DEVICE_IP" shell "rm -f $REMOTE_DIR/test.bin"
        
    if [ -n "$UL_RESULT" ] && [ "$UL_RESULT" != "0" ]; then
        local MBPS=$(awk -v d="$UL_RESULT" 'BEGIN { printf "%.2f", (d*8)/1000000 }')
        echo -e "    ${C_MAGENTA}---> WYNIK UPLOAD:${C_RST} ${C_BOLD}${MBPS} Mbps${C_RST}"
    else
        print_err "Nie udało się przesłać danych referencyjnych."
    fi
}

function interactive_cleanup() {
    echo ""
    echo -ne "${C_YELLOW}[?] Czy chcesz usunąć środowisko testowe (curl) z telewizora? (t/N): ${C_RST}"
    read -r choice </dev/tty
    if [[ "$choice" =~ ^[TtYy]$ ]]; then
        adb -s "$DEVICE_IP" shell "rm -f $REMOTE_DIR/curl"
        print_ok "Wyczyszczono pozostałości z curl ($REMOTE_DIR/curl)."
    else
        print_log "Pominięto czyszczenie. Skrypt curl pozostał na urządzeniu."
    fi
}

function cleanup_and_exit() {
    local status=${1:-0}
    interactive_cleanup
    print_log "Zakończono działanie systemu Anonymousik ADB-Speedtest."
    exit "$status"
}

# ==============================================================================
# GŁÓWNY WĄTEK WYKONAWCZY (MAIN)
# ==============================================================================
draw_gui_banner
init_connection
test_connectivity
echo ""
run_ping_test
echo ""
run_download_test
echo ""
run_upload_test
cleanup_and_exit 0
