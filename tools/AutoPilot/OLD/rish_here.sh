#!/system/bin/sh
# ==============================================================================
# SECFERRO - ADAPTIVE SHIZUKU WRAPPER (AutoPilot v1.0)
# ==============================================================================
# Wektor: Automatyczna lokalizacja DEX, autostart demona, inteligentna diagnoza.
# ==============================================================================

export RISH_APPLICATION_ID="com.android.shell"
PKG_NAME="moe.shizuku.privileged.api"
DEX_TARGET="/data/local/tmp/rish_shizuku.dex"

# --- ZASADY KOMUNIKACYJNE (Intelligent Messages) ---
log_info() { echo "\033[1;34m[INFO]\033[0m $1"; }
log_ok()   { echo "\033[1;32m[ OK ]\033[0m $1"; }
log_warn() { echo "\033[1;33m[WARN]\033[0m $1"; }
log_crit() { echo "\033[1;31m[CRITICAL]\033[0m $1"; }

# --- FAZA DIAGNOSTYCZNA (Pro-Diagnostic Test) ---
diag_system() {
    log_info "Inicjalizacja testu diagnostycznego SecFERRO..."
    
    # 1. Test procesu serwera
    SERVER_PID=$(pidof shizuku_server)
    if [ -n "$SERVER_PID" ]; then
        log_ok "Demon shizuku_server jest aktywny (PID: $SERVER_PID)"
    else
        log_warn "Demon shizuku_server NIE DZIAŁA. Wymagany auto-launch."
    fi

    # 2. Test lokalizacji DEX
    if [ -f "$DEX_TARGET" ]; then
        log_ok "Plik DEX zlokalizowany w: $DEX_TARGET"
    else
        log_warn "Brak pliku DEX w domyślnej lokalizacji."
    fi

    # 3. Test obecności aplikacji
    APP_PATH=$(pm path $PKG_NAME 2>/dev/null | cut -d':' -f2)
    if [ -n "$APP_PATH" ]; then
        log_ok "Aplikacja Shizuku znaleziona w systemie: $APP_PATH"
    else
        log_crit "Aplikacja Shizuku NIE JEST ZAINSTALOWANA."
    fi
}

# --- FAZA LOKALIZACJI I AUTO-NAPRAWY (Adaptive Discovery) ---
ensure_dex() {
    if [ -f "$DEX_TARGET" ]; then
        return 0
    fi
    
    log_warn "Trwa próba odzyskania pliku rish_shizuku.dex..."
    # Możliwe lokalizacje rezerwowe
    FALLBACK_PATHS="/sdcard/rish_shizuku.dex /sdcard/Download/rish_shizuku.dex /data/local/tmp/shizuku/rish_shizuku.dex"
    
    for path in $FALLBACK_PATHS; do
        if [ -f "$path" ]; then
            log_info "Znaleziono DEX w rezerwie: $path. Kopiowanie do $DEX_TARGET..."
            cp "$path" "$DEX_TARGET"
            chmod 755 "$DEX_TARGET"
            return 0
        fi
    done
    
    log_crit "Odzyskiwanie DEX nie powiodło się. Wyeksportuj 'rish' bezpośrednio z aplikacji Shizuku."
    exit 1
}

# --- GENERACJA LAUNCHERA (Auto-Launch) ---
launch_shizuku_server() {
    if [ -n "$(pidof shizuku_server)" ]; then
        return 0
    fi

    log_warn "Inicjalizacja środowiska startowego Shizuku..."
    
    # Próba 1: Standardowa ścieżka Android 11+
    START_SCRIPT="/storage/emulated/0/Android/data/${PKG_NAME}/start.sh"
    
    if [ -f "$START_SCRIPT" ]; then
        log_info "Wykryto skrypt startowy. Eskalacja uprawnień..."
        sh "$START_SCRIPT"
        sleep 2
    else
        log_warn "Brak skryptu startowego w Scope Storage. Próba uruchomienia przez am (Activity Manager)..."
        # Próba zmuszenia samej aplikacji do wygenerowania serwera (wymaga ADB)
        am broadcast -a ${PKG_NAME}.intent.action.AUTH_REQUEST 1>/dev/null 2>&1
        sleep 2
    fi

    if [ -z "$(pidof shizuku_server)" ]; then
        log_crit "Auto-Launch nie powiódł się. Upewnij się, że urządzenie ma odblokowane ADB/Root (SELinux u:r:su:s0)."
        exit 1
    else
        log_ok "Serwer Shizuku uruchomiony pomyślnie."
    fi
}

# --- WEKTOR WYKONAWCZY (Main Execution) ---
if [ "$1" = "--diag" ]; then
    diag_system
    exit 0
fi

# 1. Zapewnij integralność środowiska
launch_shizuku_server
ensure_dex

# 2. Eskalacja komendy
DEX="$DEX_TARGET"
if [ "$1" = "-c" ]; then
    shift
    CMD="$*"
    log_info "Wykonywanie polecenia w rish: $CMD"
    exec /system/bin/app_process -Djava.class.path="$DEX" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader -c "$CMD"
else
    log_info "Otwieranie interaktywnej powłoki rish..."
    exec /system/bin/app_process -Djava.class.path="$DEX" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader "$@"
fi
