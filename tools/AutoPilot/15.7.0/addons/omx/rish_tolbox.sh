#!/system/bin/sh
# ==============================================================================
# Tytuł: Rish Smart Toolbox (Shizuku Manager)
# Autor: Anonymousik.is-a.dev
# Wersja: 3.1.0(beta)
# Cel: Ekstrakcja, instalacja, diagnostyka i zarządzanie cyklem życia shizuku_server,launcher usługi,
# ==============================================================================

# Zabezpieczenie przed wykonaniem jako root (Shizuku/rish operuje jako shell)
if [ "$(id -u)" -eq 0 ]; then
    printf "\033[1;31m[x]\033[0m Uruchamianie tego skryptu jako root jest zabronione!\n" >&2
    exit 1
fi

# Inicjalizacja zmiennych środowiskowych i konfiguracyjnych
ACTION="menu"
SILENT_MODE=0
RAND_ID="$RANDOM"
TMP_DIR="${TMPDIR:-/data/local/tmp}/rish_toolbox_$RAND_ID"

# Detekcja środowiska roboczego (Termux vs Native ADB Shell)
if [ -n "$PREFIX" ]; then
    TARGET_BIN="$PREFIX/bin"
    PKG="com.termux"
else
    TARGET_BIN="/data/local/tmp"
    PKG="com.android.shell"
fi
RISH_WRAPPER="$TARGET_BIN/rish"
RISH_DEX="$TARGET_BIN/rish_shizuku.dex"

# Parsowanie argumentów CLI
while [ $# -gt 0 ]; do
  case "$1" in
    --install) ACTION="install" ;;
    --uninstall) ACTION="uninstall" ;;
    --start) ACTION="start" ;;
    --stop) ACTION="stop" ;;
    --restart) ACTION="restart" ;;
    --test) ACTION="test" ;;
    --menu) ACTION="menu" ;;
    --silent) SILENT_MODE=1 ;;
    *) echo "Nieznany argument: $1"; exit 1 ;;
  esac
  shift
done

# Ustawienia kolorów zależne od TTY (zapobiega krzakom w logach/potokach)
if [ -t 1 ]; then
  C0='\033[0m'
  CR='\033[1;31m'
  CG='\033[1;32m'
  CY='\033[1;33m'
  CB='\033[1;34m'
  CC='\033[1;36m'
else
  C0=''; CR=''; CG=''; CY=''; CB=''; CC=''
fi

# Funkcje interfejsu i logowania
cancel() { echo -e "${CY}[!]${C0} $1"; exit 0; }
msg()    { [ "$SILENT_MODE" -eq 0 ] && echo -e "${CB}[i]${C0} $1"; }
ok()     { [ "$SILENT_MODE" -eq 0 ] && echo -e "${CG}[+]${C0} $1"; }
warn()   { [ "$SILENT_MODE" -eq 0 ] && echo -e "${CY}[!]${C0} $1"; }
err()    { echo -e "${CR}[x]${C0} $1"; exit 1; }
step()   { [ "$SILENT_MODE" -eq 0 ] && echo -e "${CC}==>${C0} $1"; }

# Sprzątanie po zakończeniu
cleanup() {
    [ -d "$TMP_DIR" ] && rm -rf "$TMP_DIR"
}
on_cancel() {
    echo -e "\n${CY}[!]${C0} Operacja anulowana przez użytkownika."
    exit 1
}
trap on_cancel INT
trap cleanup EXIT

# ------------------------------------------------------------------------------
# MODUŁ: Zależności i Fallback (BusyBox)
# ------------------------------------------------------------------------------
resolve_dependencies() {
    PLAN_A=1
    for t in unzip sed grep cp sh; do
        command -v "$t" >/dev/null 2>&1 || PLAN_A=0
    done

    if [ "$PLAN_A" -eq 1 ]; then
        UNZIP=unzip; SED=sed; GREP=grep; CP=cp
        msg "Natywne narzędzia systemowe (Toybox/mksh) w pełni funkcjonalne."
    else
        warn "Brak natywnych narzędzi. Uruchamianie procedury ratunkowej (BusyBox Fallback)..."
        mkdir -p "$TMP_DIR"
        
        ARCH="$(uname -m)"
        case "$ARCH" in
            aarch64|arm64|armv8*) ARCH=arm64 ;;
            armv*|armhf|arm) ARCH=arm ;;
            x86_64|amd64) ARCH=x86_64 ;;
            i386|i686|x86) ARCH=x86 ;;
            *) err "Nieobsługiwana architektura urządzenia: $ARCH" ;;
        esac

        BB="$TMP_DIR/busybox"
        step "Pobieranie BusyBox ($ARCH)..."
        
        # Próba pobrania curl lub wbudowanym narzędziem Androida
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL "https://raw.githubusercontent.com/merbah3266/rish_installer/main/busybox/$ARCH/busybox" -o "$BB" || err "Błąd pobierania BB"
        else
            err "Brak curl. Instalacja niemożliwa na tym środowisku bez ręcznego wdrożenia BusyBox."
        fi

        chmod +x "$BB"
        UNZIP="$BB unzip"; SED="$BB sed"; GREP="$BB grep"; CP="$BB cp"
        ok "Środowisko ratunkowe BusyBox gotowe."
    fi
}

# ------------------------------------------------------------------------------
# MODUŁ: Instalator & Ekstraktor
# ------------------------------------------------------------------------------
execute_install() {
    step "Rozpoczynam ekstrakcję zasobów (Tryb Offline)..."
    mkdir -p "$TMP_DIR"
    APK_PATH="$TMP_DIR/base.apk"
    
    # 1. Znajdź ścieżkę do APK Shizuku zainstalowanego w systemie
    EXTRACTED=$(cmd package path moe.shizuku.privileged.api --user 0 2>/dev/null | cut -d: -f2)
    
    if [ -z "$EXTRACTED" ]; then
        err "Aplikacja Shizuku nie jest zainstalowana na tym urządzeniu."
    fi

    ok "Zlokalizowano paczkę: $EXTRACTED"
    
    # 2. Kopiuj APK do bezpiecznego miejsca
    $CP "$EXTRACTED" "$APK_PATH" || err "Nie można skopiować APK"
    
    # 3. Wypakuj tylko potrzebne zasoby (DEX i wrapper)
    step "Wypakowywanie zasobów rish z APK..."
    $UNZIP -qq "$APK_PATH" -d "$TMP_DIR" || err "Błąd wypakowywania (unzip)"
    
    [ ! -f "$TMP_DIR/assets/rish" ] && err "Brak skryptu rish w APK!"
    [ ! -f "$TMP_DIR/assets/rish_shizuku.dex" ] && err "Brak pliku dex w APK!"

    # 4. Patchowanie wrappera i instalacja
    TMP_RISH="$TMP_DIR/rish_patched"
    SH_PATH="$(command -v sh)"
    
    echo "#!$SH_PATH" > "$TMP_RISH"
    $GREP -v '^#' "$TMP_DIR/assets/rish" >> "$TMP_RISH"
    $SED -i "s/PKG/$PKG/g" "$TMP_RISH"
    
    step "Instalacja plików w systemie ($TARGET_BIN)..."
    mkdir -p "$TARGET_BIN"
    
    $CP "$TMP_RISH" "$RISH_WRAPPER"
    chmod 755 "$RISH_WRAPPER"
    
    $CP "$TMP_DIR/assets/rish_shizuku.dex" "$RISH_DEX"
    chmod 400 "$RISH_DEX"

    ok "Instalacja rish powiodła się pomyślnie. Ścieżka: $RISH_WRAPPER"
}

# --- MODUŁ: Zdalny Deploy (Uruchamiane z Twojego PC/Termux-hosta) ---
deploy_to_remote() {
    echo -e "\033[1;34m[i]\033[0m Rozpoczynam zdalny deploy na urządzenie ADB..."
    adb push "$0" "$TARGET_DIR/$TOOL_NAME"
    adb shell "chmod +x $TARGET_DIR/$TOOL_NAME"
    echo -e "\033[1;32m[+]\033[0m Narzędzie wysłane. Uruchom: adb shell $TARGET_DIR/$TOOL_NAME"
    exit 0
}

# Jeśli skrypt wywołano z argumentem --deploy, wyślij go
if [ "$1" = "--deploy" ]; then deploy_to_remote; fi

# --- MODUŁ: "Ożywianie" (Wake-up Shizuku) ---
wake_shizuku() {
    echo -e "\033[1;36m[i]\033[0m Automatyczna detekcja aktywności Shizuku..."
    
    # Dynamiczne wyszukanie poprawnej Main Activity
    MAIN_ACTIVITY=$(cmd package resolve-activity --brief moe.shizuku.privileged.api | grep "/" | head -n 1)
    
    if [ -n "$MAIN_ACTIVITY" ]; then
        echo -e "\033[1;32m[+]\033[0m Wykryto aktywność: $MAIN_ACTIVITY. Uruchamianie..."
        am start -n "$MAIN_ACTIVITY" > /dev/null 2>&1
        sleep 3
        echo -e "\033[1;32m[+]\033[0m Aplikacja wywołana w tle."
    else
        echo -e "\033[1;31m[x]\033[0m Nie udało się wykryć głównej aktywności Shizuku."
        echo -e "\033[1;33m[?]\033[0m Czy Shizuku jest na pewno zainstalowane?"
    fi
}

# --- MODUŁ: "Iniekcja Biblioteczna" (Direct Lib Injection) ---
inject_shizuku_library() {
    local PKG=$(pm path moe.shizuku.privileged.api | cut -d: -f2); local DIR=$(dirname "$PKG"); local LIB="$DIR/lib/arm/libshizuku.so"; echo -e "\033[1;36m[i]\033[0m Uruchamianie natywne: $LIB"; chmod +x "$LIB" >/dev/null 2>&1; nohup "$LIB" >/dev/null 2>&1 &
    sleep 2
    if ps | grep -q "libshizuku.so"; then echo -e "\033[1;32m[+] SUKCES: Serwer Shizuku działa.\033[0m"; else echo -e "\033[1;31m[x] Błąd uruchomienia.\033[0m"; fi
}


# ------------------------------------------------------------------------------
# MODUŁ: Zarządzanie cyklem życia shizuku_server
# ------------------------------------------------------------------------------
manage_service() {
    local task=$1
    local shizuku_pid=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')

    if [ "$task" = "stop" ] || [ "$task" = "restart" ]; then
        if [ -n "$shizuku_pid" ]; then
            step "Zatrzymywanie shizuku_server (PID: $shizuku_pid)..."
            kill -9 "$shizuku_pid"
            sleep 1
            ok "Proces zatrzymany."
        else
            msg "Proces shizuku_server nie działa w tle."
        fi
        [ "$task" = "stop" ] && return 0
    fi

    if [ "$task" = "start" ] || [ "$task" = "restart" ]; then
        step "Inicjalizacja usługi shizuku_server..."
        local start_script=""
        
        # Skanowanie standardowych lokalizacji wstrzykujących Shizuku
        for path in "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh" \
                    "/sdcard/Android/data/moe.shizuku.privileged.api/start.sh"; do
            if [ -f "$path" ]; then
                start_script="$path"
                break
            fi
        done

        if [ -z "$start_script" ]; then
            warn "Wyszukiwanie głębokie na partycji sdcard..."
            start_script=$(find /sdcard/Android/data -name "start.sh" -path "*moe.shizuku*" 2>/dev/null | head -n 1)
        fi

        if [ -n "$start_script" ]; then
            sh "$start_script" > /dev/null 2>&1 &
            sleep 2
            local new_pid=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
            if [ -n "$new_pid" ]; then
                ok "SUKCES: Serwer Shizuku wystartował (PID: $new_pid)."
            else
                err "Uruchomiono skrypt rozruchowy, ale proces demonujący zginął. Sprawdź TV."
            fi
        else
	    step " Serwer nie działa. Próba automatycznego startu..."                
	    wake_shizuku
	    inject_shizuku_library
            err "Nie odnaleziono skryptu start.sh. Otwórz aplikację Shizuku na TV przynajmniej raz."
        fi
    fi
}

# ------------------------------------------------------------------------------
# MODUŁ: Weryfikacja wektora wykonawczego (PPID Test)
# ------------------------------------------------------------------------------
verify_ppid() {
    step "Testowanie wektora uprawnień (Binder API)..."
    if [ ! -x "$RISH_WRAPPER" ]; then
        err "Brak zainstalowanego rish. Wykonaj najpierw instalację (--install)."
    fi

    export RISH_APPLICATION_ID="$PKG"
    local result=$(sh -c "$RISH_WRAPPER -c 'cat /proc/\$\$/status | grep PPid'")
    local actual_ppid=$(echo "$result" | awk '{print $2}')
    
    if [ -z "$actual_ppid" ]; then
        err "Komunikacja z procesem rish nie powiodła się. Shizuku prawdopodobnie nie działa."
    fi

    local shizuku_pid=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
    if [ "$actual_ppid" = "$shizuku_pid" ]; then
        ok "TEST ZALICZONY: Wykonanie prawidłowo wstrzyknięte (PPID serwera: $actual_ppid)."
    else
        warn "OSTRZEŻENIE: Komenda wykonana z pominięciem Shizuku (Aktualny PPID: $actual_ppid)."
    fi
}

# ------------------------------------------------------------------------------
# KONTROLER PRZEPŁYWU GŁÓWNEGO (ROUTING)
# ------------------------------------------------------------------------------
case "$ACTION" in
    install)   resolve_dependencies; execute_install ;;
    uninstall) rm -f "$RISH_WRAPPER" "$RISH_DEX"; ok "Rish odinstalowany." ;;
    start)     manage_service "start" ;;
    stop)      manage_service "stop" ;;
    restart)   manage_service "restart" ;;
    test)      verify_ppid ;;
    menu)
        # Tryb interaktywny GUI
        while true; do
            echo ""
            echo -e "${CB}=======================================${C0}"
            echo -e "${CG}   Rish Smart Toolbox v4.0.0 (Anonymousik.is-a.dev)   ${C0}"
            echo -e "${CB}=======================================${C0}"
            
            # Dynamiczny status demona
            DEMON_PID=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
            if [ -n "$DEMON_PID" ]; then
                echo -e " Status usługi: ${CG}URUCHOMIONY (PID: $DEMON_PID)${C0}"
            else
                echo -e " Status usługi: ${CR}ZATRZYMANY${C0}"
            fi
            
            echo -e "${CB}---------------------------------------${C0}"
            echo -e " ${CY}[Moduł Instalacji]${C0}"
            echo "  1) Ekstrakcja i Instalacja Rish (Offline z APK)"
            echo "  2) Odinstaluj Rish (Usuń powiązania)"
            echo -e " ${CY}[Zarządzanie Demona]${C0}"
            echo "  3) Uruchom usługę Shizuku (Start)"
            echo "  4) Zatrzymaj usługę Shizuku (Kill PID)"
            echo "  5) Zrestartuj usługę (Stop -> Start)"
            echo -e " ${CY}[Diagnostyka]${C0}"
            echo "  6) Test weryfikacyjny PPID (Security Check)"
	    echo "  7) Deploy skryptu na urzadzenie adb (--deploy)"
            echo -e "${CB}=======================================${C0}"
            echo "  0) Wyjście"
            echo -e "${CB}=======================================${C0}"
            echo -n " Wybierz operację [0-6]: "
            read -r choice
            
            echo ""
            case $choice in
                1) resolve_dependencies; execute_install ;;
                2) rm -f "$RISH_WRAPPER" "$RISH_DEX"; ok "Odinstalowano." ;;
                3) manage_service "start" ;;
                4) manage_service "stop" ;;
                5) manage_service "restart" ;;
                6) verify_ppid ;;
		7) deploy_to_remote ;;
                0) msg "Zamykanie narzędzia. Cześć Ferro!"; exit 0 ;;
                *) warn "Nieprawidłowa opcja." ;;
            esac
        done
        ;;
esac
