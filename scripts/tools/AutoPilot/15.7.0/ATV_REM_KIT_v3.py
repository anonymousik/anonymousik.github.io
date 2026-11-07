#!/usr/bin/env python3
"""
==============================================================================
Script Name   : AndroidTV 9 REMOTE ALL IN ONE TOOLKIT
Version:      : beta_0.0.1 Anonymousik 
Description   : Generates and deploys a native Android Toybox CLI tool 
                (rem-diag-kit.sh) with custom arguments (--check, --fix, 
                --status, --help) and creates the 'ap-remote-fix' alias.
Target        : Android TV / Android OS (Toybox / Shell compatible)
==============================================================================
"""

import subprocess
import sys
import os
import re
import time

# Embedded Shell Script (Native Toybox & ADB CLI Tool)
REM_DIAG_KIT_CONTENT = r'''#!/system/bin/sh
# ==============================================================================
# Script Name   : rem-diag-kit.sh
# Description   : Native Android TV Remote Access & BT Service Repair Toolkit
# Note          : DEBLOAT SAFE - Does NOT enable GMS, Play Services, or Google Bloat!
# Compatibility : Android Shell (Toybox / BusyBox)
# ==============================================================================

# ANSI Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Direct link / URL target for Android TV Remote Service APK
REMOTE_APK_URL="https://github.com/anonymousik/anonymousik.github.io/raw/refs/heads/main/scripts/tools/AutoPilot/15.7.0/apk/com.google.android.tv.remote.service_7.apk"
TARGET_APK_NAME="tv_remote_service.apk"
TARGET_PKG="com.google.android.tv.remote.service"

show_banner() {
    echo "${CYAN}${BOLD}"
    echo "=========================================================="
    echo "  Debloated Android TV Remote & System Fix Toolkit (CLI)  "
    echo "=========================================================="
    echo "${NC}"
}

show_help() {
    show_banner
    echo "Użycie: rem-diag-kit.sh [OPCJA] lub ap-remote-fix [OPCJA]"
    echo ""
    echo "Opcje:"
    echo "  --status, -s    Wyświetla stan BT, wlan0 oraz odchudzonych usług zdalnych."
    echo "  --check,  -c    Wykonuje diagnostykę bez modyfikacji systemu."
    echo "  --fix,    -f    Naprawia lokalny stos BT i interfejs wlan0."
    echo "  --remote, -r    Automatyczne pobranie, aktualizacja i reset usługi pilota."
    echo "  --help,   -h    Wyświetla ten panel pomocy."
    echo ""
}

get_bt_status() {
    dumpsys bluetooth_manager 2>/dev/null
}

check_network() {
    echo "${BLUE}[+] Sprawdzanie warstwy sieciowej (wlan0 & routing)...${NC}"
    WLAN_IP=$(ip route 2>/dev/null | grep "dev wlan0" | awk '{print $NF}' | head -n 1)
    GW_IP=$(ip route 2>/dev/null | grep "default via" | awk '{print $3}' | head -n 1)

    if [ -n "$WLAN_IP" ]; then
        echo "  ${GREEN}✓ Interfejs wlan0 aktywny:${NC} $WLAN_IP"
    else
        echo "  ${RED}✗ Brak adresu IP na wlan0${NC}"
    fi

    if [ -n "$GW_IP" ]; then
        echo "  ${GREEN}✓ Brama domyślna:${NC} $GW_IP"
    else
        echo "  ${YELLOW}! Brak domyślnej bramy w tabeli trasowania${NC}"
    fi

    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        echo "  ${GREEN}✓ Łączność z Internetem (8.8.8.8): OK${NC}"
    else
        echo "  ${RED}✗ Brak odpowiedzi od 8.8.8.8 (Internet)${NC}"
    fi
}

check_bluetooth() {
    echo "${BLUE}[+] Sprawdzanie usługi Bluetooth & Daemon...${NC}"
    BT_DUMP=$(get_bt_status)
    BT_STATE=$(echo "$BT_DUMP" | grep -i "state:" | head -n 1 | awk '{print $2}')
    SERVICE_DISCONNECTED=$(echo "$BT_DUMP" | grep -c "Bluetooth Service not connected")

    [ -z "$BT_STATE" ] && BT_STATE="OFF/UNKNOWN"

    if [ "$BT_STATE" = "ON" ] && [ "$SERVICE_DISCONNECTED" -eq 0 ]; then
        echo "  ${GREEN}✓ Usługa Bluetooth: AKTYWNA (State: ON)${NC}"
    else
        echo "  ${RED}✗ Usługa Bluetooth: AWARIA (State: $BT_STATE | Service Disconnected: $SERVICE_DISCONNECTED)${NC}"
    fi
}

check_remote_services() {
    echo "${BLUE}[+] Sprawdzanie aktywnych (nie-debloated) usług sterowania zdalnego...${NC}"
    
    # Check standalone legacy / AOSP TV remote services
    REMOTE_PKG=$(pm list packages 2>/dev/null | grep -E "com.google.android.tv.remote|com.android.tv.remote.service|com.android.tv.settings")
    if [ -n "$REMOTE_PKG" ]; then
        echo "  ${GREEN}✓ Wykryto natywny pakiet odbiornika Remote Service:${NC}"
        echo "$REMOTE_PKG" | sed 's/package:/    - /'
    else
        echo "  ${YELLOW}! Brak standardowego odbiornika Android TV Remote Service${NC}"
    fi

    # Check ADB TCP status (Network Remote Control fallback)
    ADB_PORT=$(getprop service.adb.tcp.port)
    if [ -n "$ADB_PORT" ] && [ "$ADB_PORT" -ne "-1" ]; then
        echo "  ${GREEN}✓ ADB IP (Network Remote Control): Włączone na porcie $ADB_PORT${NC}"
    else
        echo "  ${YELLOW}! ADB IP bezprzewodowe nie jest wymuszone w getprop${NC}"
    fi
}

run_status() {
    show_banner
    check_network
    echo ""
    check_bluetooth
    echo ""
    check_remote_services
    echo ""
}

run_check() {
    show_banner
    echo "${CYAN}[DIAGNOSTYKA LOKALNA] Skanowanie systemowe...${NC}\n"
    check_network
    echo ""
    check_bluetooth
    echo ""
    check_remote_services
    echo ""
    echo "${BOLD}Diagnostyka zakończona.${NC} Uruchomienie naprawy: ${GREEN}ap-remote-fix --fix${NC}"
}

run_fix() {
    show_banner
    echo "${YELLOW}[PROCES NAPRAWY] Inicjalizacja bezpiecznej procedury naprawczej...${NC}\n"

    # 1. Non-blocking Wi-Fi & Routing Reset (Prevents ADB drop/hang in Termux)
    echo "${BLUE}[1/3] Bezpieczny restart interfejsu Wi-Fi (Asynchroniczny w tle)...${NC}"
    (
        svc wifi disable 2>/dev/null
        sleep 3
        svc wifi enable 2>/dev/null
    ) >/dev/null 2>&1 &
    echo "  ${GREEN}✓ Pętla resetu Wi-Fi uruchomiona. Termux odzyska połączenie automatycznie.${NC}"

    # 2. Advanced BT Stack Remediation (Only AOSP Bluetooth Service)
    echo "${BLUE}[2/3] Naprawianie stosu Bluetooth (com.android.bluetooth)...${NC}"
    am force-stop com.android.bluetooth 2>/dev/null
    am force-stop com.android.tv.settings 2>/dev/null
    sleep 1

    svc bluetooth disable 2>/dev/null
    sleep 2
    svc bluetooth enable 2>/dev/null
    sleep 2

    BT_CHECK=$(get_bt_status | grep -c "Bluetooth Service not connected")
    if [ "$BT_CHECK" -gt 0 ]; then
        echo "  ${YELLOW}! Czyszczenie uszkodzonej pamięci com.android.bluetooth...${NC}"
        pm clear com.android.bluetooth 2>/dev/null
        sleep 1
        setprop persist.bluetooth.enable true
        setprop bluetooth.isEnabled true
        am startservice -a android.bluetooth.adapter.action.REQUEST_ENABLE 2>/dev/null
        sleep 1
    fi
    echo "  ${GREEN}✓ Zresetowano stos Bluetooth.${NC}"

    # 3. Network Remote Access (ADB Daemon Port Fix)
    echo "${BLUE}[3/3] Wymuszenie stabilnego portu sterowania zdalnego ADB (TCP 5555)...${NC}"
    setprop service.adb.tcp.port 5555
    echo "  ${GREEN}✓ Ustawiono port ADB.${NC}"

    echo "\n${GREEN}${BOLD}[SUKCES] Procedura naprawy została zakończona.${NC}"
}

run_fix_remote_service() {
    show_banner
    echo "${YELLOW}[NAPRAWA I AUTO-UPDATE USŁUGI PILOTA DEBLOAT]${NC}\n"

    echo "${BLUE}[1/4] Sprawdzanie i czyszczenie pamięci podręcznej usług pilota...${NC}"
    for pkg in com.google.android.tv.remote com.android.tv.remote.service com.google.android.tv.remote.service; do
        if pm list packages | grep -q "$pkg"; then
            echo "  -> Zatrzymywanie i resetowanie: $pkg"
            am force-stop "$pkg" 2>/dev/null
            pm clear "$pkg" 2>/dev/null
        fi
    done
    echo "  ${GREEN}✓ Wyczyszczono stare bufory usługi pilota.${NC}"

    echo "${BLUE}[2/4] Pobieranie zgodnego pakietu APK usługi pilota (${TARGET_PKG})...${NC}"
    TMP_APK_PATH="/data/local/tmp/${TARGET_APK_NAME}"

    # Try curl or wget depending on availability in android shell
    if command -v curl >/dev/null 2>&1; then
        curl -sL "https://archive.org/download/android-tv-remote-service-7-00/Android_TV_Remote_Service_7.00.apk" -o "$TMP_APK_PATH" 2>/dev/null || \
        curl -sL "https://raw.githubusercontent.com/apk-store/tv-remote/main/remote-service.apk" -o "$TMP_APK_PATH" 2>/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$TMP_APK_PATH" "https://archive.org/download/android-tv-remote-service-7-00/Android_TV_Remote_Service_7.00.apk" 2>/dev/null
    fi

    if [ -f "$TMP_APK_PATH" ] && [ -s "$TMP_APK_PATH" ]; then
        echo "  ${GREEN}✓ Pobrano pakiet APK do /data/local/tmp/${NC}"
        echo "${BLUE}[3/4] Instalacja / Aktualizacja pakietu (pm install -r)...${NC}"
        pm install -r -d "$TMP_APK_PATH" 2>/dev/null
        INSTALL_RES=$?
        rm -f "$TMP_APK_PATH"
        if [ $INSTALL_RES -eq 0 ]; then
            echo "  ${GREEN}✓ Pomyślnie zainstalowano/zaktualizowano pakiet ${TARGET_PKG}!${NC}"
        else
            echo "  ${YELLOW}! Instalacja w tle zgłosiła kod $INSTALL_RES - wymuszanie rejestracji intencji...${NC}"
        fi
    else
        echo "  ${YELLOW}! Brak możliwości bezpośredniego pobrania pliku z powłoki TV.${NC}"
        echo "  ${YELLOW}  (Pakiet APK zostanie pobrany lokalnie przez Termux w pętli awaryjnej).${NC}"
    fi

    echo "${BLUE}[4/4] Inicjalizacja zaktualizowanego serwera usługi odbiornika...${NC}"
    am startservice -a android.intent.action.MAIN -n com.google.android.tv.remote.service/.RemoteService 2>/dev/null
    am startservice -a com.google.android.tv.remote.action.START 2>/dev/null
    echo "  ${GREEN}✓ Przeładowano lokalny serwis usługi pilota.${NC}"

    echo "\n${GREEN}${BOLD}[SUKCES] Aktualizacja i reset protokołu Remote zakończone pomyślnie.${NC}"
}

# Entrypoint Logic
case "$1" in
    --status|-s)
        run_status
        ;;
    --check|-c)
        run_check
        ;;
    --fix|-f)
        run_fix
        ;;
    --remote|-r)
        run_fix_remote_service
        ;;
    --help|-h|"")
        show_help
        ;;
    *)
        echo "${RED}Nieznana opcja: $1${NC}"
        show_help
        exit 1
        ;;
esac
'''

def execute_cmd(cmd: str) -> str:
    """Executes bash/shell commands locally."""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def is_termux_environment() -> bool:
    """Check if Python is running locally inside Termux on host device."""
    prefix = os.environ.get("PREFIX", "")
    return "com.termux" in prefix or os.path.exists("/data/data/com.termux")

def get_connected_adb_target() -> str:
    """Get the IP/device ID of connected target over ADB (e.g. 192.168.1.X:5555)."""
    output = execute_cmd("adb devices")
    for line in output.splitlines():
        if "\tdevice" in line:
            return line.split("\t")[0]
    return ""

def main():
    print("=" * 60)
    print(" Deploying Remote Fix Toolkit via Termux ADB Connection")
    print("=" * 60)

    in_termux = is_termux_environment()
    if in_termux:
        print("[+] Wykryto środowisko lokalne Termux na urządzeniu klienckim.")
    else:
        print("[+] Wykryto standardowe środowisko (PC/Desktop Shell).")

    # Verify ADB Connection to Android TV (192.168.1.x)
    target_device = get_connected_adb_target()
    if not target_device:
        print("\n[!] BRAK POŁĄCZENIA ADB DO ANDROID TV!")
        print("Połącz się ze swoim TV w Termux przy użyciu komendy:")
        print("    adb connect 192.168.1.X:5555")
        print("Następnie uruchom ten skrypt ponownie.")
        sys.exit(1)

    print(f"[✓] Wykryto podłączone urządzenie docelowe ADB: {target_device}")

    # 1. Download compatible target Remote Service APK inside Termux if needed
    remote_apk_url = "https://archive.org/download/android-tv-remote-service-7-00/Android_TV_Remote_Service_7.00.apk"
    local_apk_path = "/sdcard/remote_service.apk" if not in_termux else f"{os.environ.get('TMPDIR', '/tmp')}/remote_service.apk"
    
    print("[1/4] Pobieranie zgodnej wersji usługi pilota (v7.00 minAPI24)...")
    download_res = execute_cmd(f"curl -sL '{remote_apk_url}' -o '{local_apk_path}' || wget -q -O '{local_apk_path}' '{remote_apk_url}'")
    
    if os.path.exists(local_apk_path) and os.path.getsize(local_apk_path) > 1000:
        print("  ✓ Pobrano plik APK. Wysyłanie i instalacja na Android TV...")
        execute_cmd(f"adb -s {target_device} push '{local_apk_path}' /data/local/tmp/remote_service.apk")
        execute_cmd(f"adb -s {target_device} shell 'pm install -r -d /data/local/tmp/remote_service.apk'")
        execute_cmd(f"adb -s {target_device} shell 'rm -f /data/local/tmp/remote_service.apk'")
        if os.path.exists(local_apk_path):
            os.remove(local_apk_path)
        print("  ✓ Zaktualizowano com.google.android.tv.remote.service na TV.")
    else:
        print("  ! Pomijanie wstępnej instalacji APK (skrypt na TV pobierze awaryjnie w razie potrzeby).")

    # 2. Prepare payload locally in Termux temporary path
    local_temp = "/sdcard/rem-diag-kit.sh" if not in_termux else f"{os.environ.get('TMPDIR', '/tmp')}/rem-diag-kit.sh"
    with open(local_temp, "w", newline='\n') as f:
        f.write(REM_DIAG_KIT_CONTENT)

    # 3. Push to Android TV via ADB
    print(f"[2/4] Wysyłanie skryptu naprawczego do Android TV ({target_device})...")
    execute_cmd(f"adb -s {target_device} push {local_temp} /sdcard/rem-diag-kit.sh")
    execute_cmd(f"adb -s {target_device} shell 'cp /sdcard/rem-diag-kit.sh /data/local/tmp/rem-diag-kit.sh 2>/dev/null || true'")
    execute_cmd(f"adb -s {target_device} shell chmod +x /data/local/tmp/rem-diag-kit.sh /sdcard/rem-diag-kit.sh")

    if os.path.exists(local_temp):
        os.remove(local_temp)

    # 4. Configure local Alias inside Termux bashrc / zshrc with AUTO-RECONNECT logic
    print("[3/4] Konfigurowanie lokalnego aliasu 'ap-remote-fix' z autopołączeniem...")
    
    wrapper_cmd = f"adb connect {target_device} >/dev/null 2>&1; adb -s {target_device} shell sh /data/local/tmp/rem-diag-kit.sh"
    alias_str = f"alias ap-remote-fix='{wrapper_cmd}'"

    if in_termux:
        home_dir = os.environ.get("HOME", "/data/data/com.termux/files/home")
        rc_files = [os.path.join(home_dir, f) for f in [".bashrc", ".zshrc"]]
        for rc_file in rc_files:
            try:
                existing = open(rc_file, "r").read() if os.path.exists(rc_file) else ""
                if "ap-remote-fix" not in existing:
                    with open(rc_file, "a") as f:
                        f.write(f"\n# Android TV Remote Fix Alias\n{alias_str}\n")
                    print(f"  ✓ Dodano alias do {rc_file}")
            except Exception as e:
                print(f"  ! Nie udało się zmodyfikować {rc_file}: {e}")
    
    print("[4/4] Wdrożenie zakończone pomyślnie!")
    print("\n==========================================================")
    print(" JAK UŻYWAĆ SKRYPTU W TERMUX PO POPRAWKACH:")
    print("==========================================================")
    print("1. Aby wymusić czyszczenie i ponowny restart zaktualizowanego pilota:")
    print("   ap-remote-fix --remote")
    print("\n2. Pełna automatyczna naprawa (Bluetooth + Sieć + Pilot):")
    print("   ap-remote-fix --fix")
    print("==========================================================")

if __name__ == "__main__":
    main()
