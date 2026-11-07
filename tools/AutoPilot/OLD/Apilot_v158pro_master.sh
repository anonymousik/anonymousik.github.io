#!/system/bin/sh
# ==============================================================================
# Tytuł: Titanium Master Orchestrator & Shizuku Smart Wrapper (v17.0)
# Target: Sagemcom DCTIW362P / Android TV 9 / VideoCore IV
# Cel: Automatyzacja demona Shizuku, diagnostyka wideo, ochrona WebEmbed i sieci.
# ==============================================================================

# Zabezpieczenie przed uruchomieniem bezpośrednio jako root (Shizuku operuje jako shell/rish)
if [ "$(id -u)" -eq 0 ]; then
    printf "\033[1;31m[x]\033[0m Uruchamianie tego narzędzia bezpośrednio jako root nie jest zalecane przez Shizuku!\n" >&2
fi

DIR="$(cd "$(dirname "$0")" && pwd)"
C_RED='\033[31m'; C_GREEN='\033[32m'; C_CYAN='\033[36m'; C_YELLOW='\033[33m'; C_RESET='\033[0m'

# Inteligentna detekcja wektora wykonawczego (RISH -> SU -> ADB Fallback)
detect_execution_layer() {
    if [ -x "/data/local/tmp/rish" ] && /data/local/tmp/rish -c 'id' 2>/dev/null | grep -q 'uid=2000'; then
        EXEC="/data/local/tmp/rish -c"
        LAYER="RISH (Shizuku)"
    elif su -c 'id' 2>/dev/null | grep -q 'uid=0'; then
        EXEC="su -c"
        LAYER="ROOT (su)"
    else
        EXEC="sh -c"
        LAYER="ADB Standard (sh)"
    fi
}

detect_execution_layer

# ==============================================================================
# MODUŁ INTELIGENTNEGO ZARZĄDZANIA STANEM SHIZUKU (Smart Shizuku Wrapper)
# ==============================================================================
check_and_start_shizuku() {
    echo -e "${C_CYAN}[i] Sprawdzanie stanu demona Shizuku (shizuku_server)...${C_RESET}"
    SHIZUKU_PID=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
    
    if [ -n "$SHIZUKU_PID" ]; then
        echo -e "${C_GREEN}[✓] Usługa Shizuku jest aktywna (PID: $SHIZUKU_PID).${C_RESET}"
        return 0
    else
        echo -e "${C_YELLOW}[!] Usługa Shizuku jest zatrzymana. Próba automatycznego wzbudzenia...${C_RESET}"
        
        # 1. Próba wywołania głównej Aktywności Shizuku
        MAIN_ACTIVITY=$(cmd package resolve-activity --brief moe.shizuku.privileged.api 2>/dev/null | grep "/" | head -n 1)
        if [ -n "$MAIN_ACTIVITY" ]; then
            am start -n "$MAIN_ACTIVITY" > /dev/null 2>&1
            sleep 2
        fi

        # 2. Skanowanie skryptu rozruchowego start.sh dostarczonego przez aplikację
        START_SCRIPT=""
        for path in "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh" \
                    "/sdcard/Android/data/moe.shizuku.privileged.api/start.sh"; do
            if [ -f "$path" ]; then
                START_SCRIPT="$path"
                break
            fi
        done

        if [ -z "$START_SCRIPT" ]; then
            START_SCRIPT=$(find /sdcard/Android/data -name "start.sh" -path "*moe.shizuku*" 2>/dev/null | head -n 1)
        fi

        if [ -n "$START_SCRIPT" ]; then
            sh "$START_SCRIPT" > /dev/null 2>&1 &
            sleep 3
            NEW_PID=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
            if [ -n "$NEW_PID" ]; then
                echo -e "${C_GREEN}[✓] Wzbudzono Shizuku pomyślnie (Nowy PID: $NEW_PID).${C_RESET}"
                return 0
            fi
        fi

        # 3. Fallback: Iniekcja biblioteki natywnej
        PKG_PATH=$(pm path moe.shizuku.privileged.api 2>/dev/null | cut -d: -f2)
        if [ -n "$PKG_PATH" ]; then
            LIB_PATH="$(dirname "$PKG_PATH")/lib/arm/libshizuku.so"
            if [ -f "$LIB_PATH" ]; then
                chmod +x "$LIB_PATH" 2>/dev/null
                nohup "$LIB_PATH" > /dev/null 2>&1 &
                sleep 2
                if ps -ef | grep -q 'shizuku_server'; then
                    echo -e "${C_GREEN}[✓] Shizuku uruchomione przez iniekcję biblioteki natywnej.${C_RESET}"
                    return 0
                fi
            fi
        fi

        echo -e "${C_RED}[✗] Ostrzeżenie: Nie udało się automatycznie uruchomić Shizuku. Otwórz aplikację Shizuku na TV raz ręcznie.${C_RESET}"
        return 1
    fi
}

# ==============================================================================
# GŁÓWNE MENU INTERAKTYWNE (TUI)
# ==============================================================================
show_menu() {
    clear
    echo -e "${C_CYAN}╔═══════════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_CYAN}║     PLAYBOX TITANIUM v17.0 - MASTER ORCHESTRATOR & FIXER          ║${C_RESET}"
    echo -e "${C_CYAN}╚═══════════════════════════════════════════════════════════════════╝${C_RESET}"
    echo -e " Warstwa wykonawcza: ${C_GREEN}$LAYER${C_RESET}"
    
    SHIZUKU_CHECK=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
    if [ -n "$SHIZUKU_CHECK" ]; then
        echo -e " Stan Shizuku:       ${C_GREEN}URUCHOMIONY (PID: $SHIZUKU_CHECK)${C_RESET}"
    else
        echo -e " Stan Shizuku:       ${C_RED}ZATRZYMANY${C_RESET}"
    fi
    echo -e "${C_CYAN}-------------------------------------------------------------------${C_RESET}"
    echo "  1) 🚀 Wykonaj pełną optymalizację i naprawę systemu (All-In-One)"
    echo "  2) 🎬 Napraw WebEmbed Player & SponsorBlock Freeze Fix"
    echo "  3) 🌐 Tarcza Sieciowa (Naprawa DUP Packets + NextDNS DoT)"
    echo "  4) ⚡ Wymuś sprawdzenie i inteligentny start Shizuku"
    echo "  5) 🧹 Głębokie czyszczenie RAM, Caches i Fstrim"
    echo "  0) Wyjście"
    echo -e "${C_CYAN}───────────────────────────────────────────────────────────────────${C_RESET}"
    printf "Wybierz opcję [0-5]: "
    read opt

    case $opt in
        1)
            check_and_start_shizuku
            $EXEC "sh $DIR/network_shield_fix.sh"
            $EXEC "sh $DIR/core_media_fixer.sh"
            pm trim-caches 2G >/dev/null 2>&1
            ;;
        2)
            check_and_start_shizuku
            $EXEC "sh $DIR/core_media_fixer.sh"
            ;;
        3)
            $EXEC "sh $DIR/network_shield_fix.sh"
            ;;
        4)
            check_and_start_shizuku
            ;;
        5)
            pm trim-caches 2G >/dev/null 2>&1
            sync
            echo -e "${C_GREEN}[✓] Pamięć podręczna wyczyszczona.${C_RESET}"
            ;;
        0)
            exit 0
            ;;
        *)
            echo -e "${C_RED}Nieprawidłowa opcja!${C_RESET}"
            sleep 1
            ;;
    esac
    
    echo -e "\n${C_GREEN}Operacja zakończona. Naciśnij Enter, aby powrócić do menu...${C_RESET}"
    read dummy
    show_menu
}

show_menu