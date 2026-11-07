#!/system/bin/sh
# ==============================================================================
# OPTYMALIZATOR SAGEMCOM DCTIW362P (PlayBOX / Play Now TV V3)
# Architektura: BCM72604 | ARMv7l (Cortex-A15) | GPU: VideoCore IV
# OS: Android TV 9 (API 28) | Kernel: 4.9.190-1-6pre
# ==============================================================================
# INSTALACJA I URUCHOMIENIE:
#   adb push sagemcom_optymalizator.sh /data/local/tmp/
#   adb shell chmod +x /data/local/tmp/sagemcom_optymalizator.sh
#
#   # Uruchomienie (najlepiej przez Shizuku/rish dla pełnych uprawnień):
#   adb shell sh -c "/data/local/tmp/rish -c '/data/local/tmp/sagemcom_optymalizator.sh'"
#   # LUB standardowo (część ustawień 'secure' może zostać pominięta):
#   adb shell sh /data/local/tmp/sagemcom_optymalizator.sh
# ==============================================================================

LOG_TAG="DCTIW362P_OPT"
RISH_BIN="/data/local/tmp/rish"

log_info() { echo "\033[96m[INFO]\033[0m $1"; }
log_ok()   { echo "\033[92m[OK]\033[0m   $1"; }
log_warn() { echo "\033[93m[WARN]\033[0m $1"; }

# Sprawdzenie środowiska wykonawczego (Root / Rish / ADB)
if [ "$(id -u)" = "0" ]; then
    EXEC_MODE="ROOT"
elif [ -n "$RISH_APPLICATION_ID" ] || [ "$(id -u)" = "2000" -a -x "$RISH_BIN" ]; then
    EXEC_MODE="RISH"
else
    EXEC_MODE="ADB"
    log_warn "Brak uprawnień Root/Shizuku. Niektóre ustawienia 'secure' mogą zostać zignorowane."
fi

# Wrapper do bezpiecznego ustawiania właściwości (settings/setprop)
set_prop() {
    local key="$1"
    local val="$2"
    local current=$(getprop "$key" 2>/dev/null)
    if [ "$current" != "$val" ]; then
        setprop "$key" "$val"
        log_ok "setprop: $key = $val"
    fi
}

set_setting() {
    local namespace="$1"
    local key="$2"
    local val="$3"
    
    if [ "$EXEC_MODE" = "RISH" ] && [ "$namespace" = "secure" -|| "$namespace" = "global" ]; then
        "$RISH_BIN" -c "settings put $namespace $key $val" >/dev/null 2>&1
        log_ok "settings [$namespace] (rish): $key = $val"
    else
        settings put "$namespace" "$key" "$val" >/dev/null 2>&1
        log_ok "settings [$namespace]: $key = $val"
    fi
}

write_sys() {
    local path="$1"
    local val="$2"
    if [ -w "$path" ]; then
        echo "$val" > "$path" 2>/dev/null
        log_ok "sysfs: $path = $val"
    fi
}

log_info "Rozpoczynam optymalizację dla układu Broadcom BCM72604..."

# ==============================================================================
# 1. WARSTWA GRAFICZNA (GPU VideoCore IV)
# Zablokowanie Vulkan (brak obsługi w VC4), wymuszenie SkiaGL (OpenGL ES 3.1)
# ==============================================================================
set_prop "debug.hwui.renderer" "skiagl"
set_prop "debug.renderengine.backend" "skiaglthreaded"
set_prop "persist.sys.ui.hw" "true"
set_prop "debug.sf.hw" "1"

# BCM VideoCore IV słabo radzi sobie z rozmyciem tła - wyłączamy by odciążyć UI
set_prop "ro.surface_flinger.supports_background_blur" "0"
set_setting "global" "window_animation_scale" "0.4"
set_setting "global" "transition_animation_scale" "0.4"
set_setting "global" "animator_duration_scale" "0.4"

# ==============================================================================
# 2. POTOK WIDEO (MEDIA CODEC) I OCHRONA PROCESORA
# Blokada AV1 (dekodowanie programowe na A15 drastycznie przegrzewa układ)
# Optymalizacja pod sprzętowe VP9 i HEVC
# ==============================================================================
set_prop "debug.stagefright.c2.av1" "0"
set_prop "media.av1.sw.decode.disable" "true"
set_prop "media.codec.av1.disable" "true"

# BCM Nexus / Tunnel mode - synchronizacja audio/wideo sprzętowa dla 4K 60fps
set_prop "media.brcm.tunnel.clock" "hdmi"
set_prop "media.brcm.tunnel.clock.latency" "50"
set_prop "media.brcm.surface.prewarm" "true"
set_prop "media.brcm.hdr.enable" "1"
set_prop "persist.sys.media.avsync" "true"
set_prop "media.stagefright.enable-player" "true"

# ==============================================================================
# 3. OPTYMALIZACJA PAMIĘCI RAM I DALVIK (Dla 2GB RAM / API 28)
# Brak zRAM na tym urządzeniu, optymalizacja odśmiecania (Garbage Collector)
# ==============================================================================
set_prop "dalvik.vm.heapsize" "512m"
set_prop "dalvik.vm.heapgrowthlimit" "192m"
set_prop "dalvik.vm.heapstartsize" "16m"
set_prop "dalvik.vm.heapminfree" "2m"
set_prop "dalvik.vm.heapmaxfree" "16m"
set_prop "dalvik.vm.heaptargetutilization" "0.75"

# Aktywacja sprzętowego dzielenia całkowitego (cecha instrukcji Cortex-A15)
set_prop "dalvik.vm.isa.arm.features" "default,idiv"

# Ustawienia jądra dla pamięci i systemu plików eMMC
write_sys "/proc/sys/vm/swappiness" "0"
write_sys "/proc/sys/vm/vfs_cache_pressure" "30" # Zatrzymuje cache VFS (szybsze wczytywanie UI)
write_sys "/proc/sys/vm/dirty_ratio" "15"
write_sys "/proc/sys/vm/dirty_background_ratio" "5"

# ==============================================================================
# 4. STOS SIECIOWY TCP DLA JĄDRA 4.9.190 (Brak BBR, wymuszamy stabilny CUBIC)
# Rozmiary buforów zoptymalizowane pod 4K (bez przepełniania 2GB RAM)
# ==============================================================================
write_sys "/proc/sys/net/ipv4/tcp_congestion_control" "cubic"
write_sys "/proc/sys/net/ipv4/tcp_fastopen" "3"
write_sys "/proc/sys/net/ipv4/tcp_window_scaling" "1"

# Buforowanie pod stabilne WiFi 5 (max 4MB, zamiast domyślnych niskich wartości)
set_setting "global" "net.tcp.buffersize.wifi" "524288,1048576,4194304,262144,524288,2097152"
set_prop "net.tcp.default_init_rwnd" "60"

# Ograniczenie nieustannego skanowania WiFi/BT w tle (redukuje mikroprzycięcia)
set_setting "global" "wifi_scan_always_enabled" "0"
set_setting "global" "ble_scan_always_enabled" "0"

# ==============================================================================
# 5. DEBLOATING W TLE (Bez niszczenia usługi Chromecast)
# ==============================================================================
set_setting "global" "send_action_app_error" "0"
set_setting "secure" "upload_log_pref" "0"
set_setting "secure" "tv_disable_recommendations" "1"

# Odciążenie szyny AXI i wejścia/wyjścia dysku (I/O)
set_prop "log.tag.stats_log" "OFF"
set_prop "log.tag.statsd" "OFF"

log_info "Zakończono wstrzykiwanie parametrów."
log_ok "Wymagany restart urządzenia w celu pełnej aplikacji parametrów jądra i SF."
log_info "Wpisz 'adb reboot' aby zrestartować boxa."

exit 0