#!/system/bin/sh
# ==============================================================================
# PLAYBOX TITANIUM v23.0 ELITE - XCLOUD EDITION (SMART AUTO-DEPLOYER)
# Target: Sagemcom DCTIW362P | Android TV 9 | Broadcom m362
# ==============================================================================

TWEAKS_DIR="/data/local/tmp/.tweaks"
mkdir -p "$TWEAKS_DIR"

echo "[*] Generowanie: rish_env.sh (Wektor Uprawnień)..."
cat << 'EOF' > "$TWEAKS_DIR/rish_env.sh"
#!/system/bin/sh
RISH_BIN="/data/local/tmp/rish"

init_context() {
    if su -c 'id' 2>/dev/null | grep -q 'uid=0'; then
        export EXEC="su -c"; export PRIV_LEVEL="ROOT"; export LAYER="Pełny dostęp ROOT (su)"
    elif [ -x "$RISH_BIN" ] && "$RISH_BIN" -c 'id' 2>/dev/null | grep -q 'uid=2000'; then
        export EXEC="$RISH_BIN -c"; export PRIV_LEVEL="RISH"; export LAYER="Shizuku API (rish)"
    else
        export EXEC="sh -c"; export PRIV_LEVEL="ADB"; export LAYER="Ograniczony ADB Shell"
    fi
}

safe_settings_put() {
    local ns="$1"; local key="$2"; local val="$3"
    $EXEC "settings put $ns $key '$val'" >/dev/null 2>&1
}

safe_settings_del() {
    local ns="$1"; local key="$2"
    $EXEC "settings delete $ns $key" >/dev/null 2>&1
}

safe_setprop() {
    local key="$1"; local val="$2"
    local current=$($EXEC "getprop $key" 2>/dev/null)
    if [ "$current" != "$val" ]; then
        $EXEC "setprop $key $val" >/dev/null 2>&1
    fi
}
init_context
EOF

echo "[*] Generowanie: db_sanitizer.sh (Sanityzacja Bazy Danych)..."
cat << 'EOF' > "$TWEAKS_DIR/db_sanitizer.sh"
#!/system/bin/sh
. /data/local/tmp/.tweaks/rish_env.sh
echo "[*] Skanowanie i czyszczenie baz Settings..."

GLOBAL_BAD="max_phantom_processes private_dns1 private_dns2 private_dns private_dns2_specifier activity_manager_constants.max_cached_processes sys.sysctl.tcp_def_init_rwnd tcp_default_init_rwnd tcp_init_rwnd net.dns1 net.dns2 net.dns3 net.dns4 net.tcp.buffersize.default net.tcp.buffersize.ethernet net.tcp.buffersize.wifi hwui.renderer hwui.layer_cache_size sf.renderer sf.early_phase_offset_ns media.brcm.mma.enable media.brcm.surface.prewarm media.brcm.tunnel.clock.latency media.brcm.vpu.buffer.size media.brcm.vpu.buffer media.brcm.vpu.buffers media.brcm.vpu.bufferz media.codec.priority media.decoder.use-codec-buffer media.stagefright.cache-params media.stagefright.enable-aac media.stagefright.enable-http media.stagefright.enable-meta media.stagefright.enable-player media.stagefright.enable-rtsp media.stagefright.enable-scan media.stagefright.thumbnail.prefer_hw_codecs media.tunneled-playback.enable sys.ui.hw sys.watchdog.timeout sys_watchdog_timeout_ms vdec.progoverride video.accelerate.hw dalvik.vm.isa.arm.features persist.sys.hdr.enable persist.sys.sf.color_saturation persist.sys.thermal.enable persist.sys.videomode ro.vendor.hdr.enable set-fixed-performance-mode-enabled sf_frame_rate_override surface_flinger surface_flinger_enable_layer_caching surface_flinger_layer_caching sys_free_storage_alloc_limit sys_uidcpupower ui_hw _boot_Phenotype_flags low_power_mode low_power_mode_sticky"

SECURE_BAD="put .early_gl_phase_offset_ns prop.persist.sys.hdmi.hdr_mode CONFIG_DEBUG_FS GL_ARB_compute_shader cpu_frequency cpu_frequency_scaling_enabled dalvik.vm.image-dex2oat-Xms dalvik.vm.isa.arm.features inotify_queue isa.features lmk.critical lmk.low lmk.medium lmk.upgrade_pressure media.acodec.preferhw media.brcm.surface.prewarm media.brcm.vpu.buffer.size media.brcm.vpu.buffers media.brcm.vpu.bufferz media.vcodec.outportbuf media.vcodec.preferhw net.tcp.buffersize.default net.tcp.buffersize.ethernet net.tcp.buffersize.wifi net.tcp.default_init_rwnd persist.media.treble_omx persist.sys.hdmi.hdr_mode persist.sys.videomode ro.lmk.upgrade_pressure ro.nx.mma set-fixed-performance-mode-enabled sf.early_phase_offset_ns sgc_eda_version sys.sysctl.tcp_def_init_rwnd sys.watchdog.timeout tcp_init_rwnd wifi_network_mtu screensaver_enabled"

for g in $GLOBAL_BAD; do safe_settings_del "global" "$g"; done
for s in $SECURE_BAD; do safe_settings_del "secure" "$s"; done
echo "[✓] Usunięto wadliwe wpisy z baz konfiguracji."
EOF

echo "[*] Generowanie: adaptive_tuner.sh (Profil Media & SmartTube)..."
cat << 'EOF' > "$TWEAKS_DIR/adaptive_tuner.sh"
#!/system/bin/sh
. /data/local/tmp/.tweaks/rish_env.sh
echo "[*] Wdrażanie optymalizacji Media i WebEmbed..."

WIFI_UP=$(ip link show 2>/dev/null | grep -c "wlan.*state UP")
ETH_UP=$(ip link show 2>/dev/null | grep -c "eth.*state UP")
if [ "$WIFI_UP" -gt 0 ] && [ "$ETH_UP" -gt 0 ]; then
    ETH_IFACES=$(ip link show | grep "eth.*state UP" | awk '{print $2}' | tr -d ':')
    for iface in $ETH_IFACES; do $EXEC "ip link set $iface down"; done
    $EXEC "ip neigh flush all"
fi

safe_settings_put "global" "wifi_network_mtu" "1492"
safe_settings_put "global" "private_dns_mode" "hostname"
safe_settings_put "global" "private_dns_specifier" "atv-ultralow.dns.nextdns.io"
safe_settings_put "global" "network_avoid_bad_wifi" "1"

safe_setprop "net.tcp.default_init_rwnd" "120"
safe_setprop "net.tcp.buffersize.wifi" "524288,1048576,2097152,262144,524288,1048576"

# Optymalizacja WebEmbed (SponsorBlock Fix)
safe_settings_put "global" "webview_multiprocess" "true"
safe_setprop "debug.webview.max_renderers" "3"
safe_setprop "persist.media.treble_omx" "false"
safe_setprop "media.codec.priority" "0"
safe_setprop "debug.stagefright.omx_default_rank" "0"
safe_setprop "media.brcm.mma.enable" "1"
safe_setprop "media.brcm.vpu.buffers" "32"
safe_setprop "media.brcm.vdec.progoverride" "2"

# GPU Rendering SkiaGL
safe_setprop "debug.hwui.renderer" "skiagl"
safe_setprop "debug.sf.latch_unsignaled" "1"
safe_setprop "debug.sf.disable_backpressure" "1"
safe_setprop "debug.sf.early_phase_offset_ns" "500000"
safe_setprop "debug.gr.numframebuffers" "3"

# UI & LMK Standard
safe_settings_put "global" "window_animation_scale" "0.25"
safe_settings_put "global" "transition_animation_scale" "0.25"
safe_settings_put "global" "animator_duration_scale" "0.25"
safe_settings_put "global" "background_process_limit" "3"
safe_setprop "ro.lmk.upgrade_pressure" "50"
safe_setprop "dalvik.vm.heapminfree" "2m"

$EXEC "killall android.hardware.media.omx@1.0-service" 2>/dev/null
echo "[✓] Profil multimedialny zaaplikowany."
EOF

echo "[*] Generowanie: xcloud_tuner.sh (Profil Ekstremalny XCLOUD)..."
cat << 'EOF' > "$TWEAKS_DIR/xcloud_tuner.sh"
#!/system/bin/sh
. /data/local/tmp/.tweaks/rish_env.sh
echo "[*] AKTYWACJA TRYBU XCLOUD GAMING (Maximum Low-Latency)..."

# 1. Całkowite ubicie skanowania w tle (Eliminacja Jittera Wi-Fi / Bluetooth)
safe_settings_put "global" "wifi_scan_always_enabled" "0"
safe_settings_put "global" "ble_scan_always_enabled" "0"
safe_settings_put "global" "captive_portal_mode" "0"

# 2. Odciążenie procesora - tryb Single-Tasking
safe_settings_put "global" "background_process_limit" "1"

# 3. Zrzucenie animacji do ZERA (Błyskawiczna reakcja interfejsu)
safe_settings_put "global" "window_animation_scale" "0.0"
safe_settings_put "global" "transition_animation_scale" "0.0"
safe_settings_put "global" "animator_duration_scale" "0.0"

# 4. Zero-Latency Display Pipeline (Wypychanie ramek bez opóźnień SurfaceFlingera)
safe_setprop "debug.sf.early_phase_offset_ns" "0"
safe_setprop "debug.sf.early_app_phase_offset_ns" "0"
safe_setprop "debug.sf.latch_unsignaled" "1"
safe_setprop "debug.sf.disable_backpressure" "1"

# 5. Agresywne strojenie TCP dla strumieniowania chmurowego
safe_setprop "net.tcp.default_init_rwnd" "120"
safe_setprop "net.ipv4.tcp_fastopen" "3" 2>/dev/null

# Oczyszczenie RAM na start gry
$EXEC "pm trim-caches 4096G" 2>/dev/null
sync
echo "[✓] Tryb XCLOUD GAMING AKTYWNY. Sprzęt skupiony wyłącznie na dekodowaniu strumienia!"
EOF

echo "[*] Generowanie: watchdog_daemon.sh (Demon Sieciowy)..."
cat << 'EOF' > "$TWEAKS_DIR/watchdog_daemon.sh"
#!/system/bin/sh
. /data/local/tmp/.tweaks/rish_env.sh
while [ "$($EXEC getprop sys.boot_completed)" != "1" ]; do sleep 5; done
while true; do
    if ! ps -ef | grep -q '[s]hizuku_server'; then
        START_SCRIPT=$(find /sdcard/Android/data/moe.shizuku.privileged.api -name "start.sh" 2>/dev/null | head -n 1)
        [ -n "$START_SCRIPT" ] && [ -f "$START_SCRIPT" ] && sh "$START_SCRIPT" >/dev/null 2>&1 &
    fi
    WIFI_UP=$(ip link show 2>/dev/null | grep -c "wlan.*state UP")
    ETH_UP=$(ip link show 2>/dev/null | grep -c "eth.*state UP")
    if [ "$WIFI_UP" -gt 0 ] && [ "$ETH_UP" -gt 0 ]; then
        ETH_IFACES=$(ip link show | grep "eth.*state UP" | awk '{print $2}' | tr -d ':')
        for iface in $ETH_IFACES; do $EXEC "ip link set $iface down"; done
        $EXEC "ip neigh flush all"
    fi
    sleep 120
done
EOF

echo "[*] Generowanie: titanium_master.sh (Główny Orchestrator TUI)..."
cat << 'EOF' > "$TWEAKS_DIR/titanium_master.sh"
#!/system/bin/sh
DIR="/data/local/tmp/.tweaks"
. "$DIR/rish_env.sh"

C_RED='\033[31m'; C_GREEN='\033[32m'; C_CYAN='\033[36m'; C_YELLOW='\033[33m'; C_RESET='\033[0m'

show_menu() {
    clear
    echo -e "${C_CYAN}╔═══════════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_CYAN}║     PLAYBOX TITANIUM v23.0 ELITE - XCLOUD GAMING EDITION          ║${C_RESET}"
    echo -e "${C_CYAN}╚═══════════════════════════════════════════════════════════════════╝${C_RESET}"
    echo -e " Warstwa wykonawcza: ${C_GREEN}$LAYER${C_RESET}"
    
    SHIZUKU_CHECK=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
    if [ -n "$SHIZUKU_CHECK" ]; then
        echo -e " Shizuku Server:     ${C_GREEN}AKTYWNY (PID: $SHIZUKU_CHECK)${C_RESET}"
    else
        echo -e " Shizuku Server:     ${C_RED}ZATRZYMANY${C_RESET}"
    fi

    echo -e "${C_CYAN}-------------------------------------------------------------------${C_RESET}"
    echo "  1) 🚀 STANDARD OPTIMIZE (SmartTube, WebEmbed Fix, Sieć, UI)"
    echo -e "  2) ${C_GREEN}🎮 XCLOUD GAMING MODE (Max Performance, Zero Latency, No-Scan)${C_RESET}"
    echo "  3) 🌐 Tarcza Sieciowa (Reset Wi-Fi bez utraty ADB + Fix DUP)"
    echo "  4) 🧹 Czyszczenie Bazy Settings & RAM Trim"
    echo "  5) 🐕 Aktywuj Demona Watchdog w tle"
    echo "  0) Wyjście"
    echo -e "${C_CYAN}───────────────────────────────────────────────────────────────────${C_RESET}"
    printf "Wybierz opcję [0-5]: "
    read opt

    case $opt in
        1)
            sh "$DIR/db_sanitizer.sh"
            sh "$DIR/adaptive_tuner.sh"
            $EXEC "pm trim-caches 2G" >/dev/null 2>&1
            echo -e "${C_GREEN}[✓] System zoptymalizowany pod kątem multimediów.${C_RESET}"
            ;;
        2)
            sh "$DIR/xcloud_tuner.sh"
            echo -e "${C_GREEN}[✓] XCLOUD MODE AKTYWNY. Miłego grania!${C_RESET}"
            ;;
        3)
            # Tarcza sieciowa i restart bez przerywania skryptu
            WIFI_UP=$(ip link show 2>/dev/null | grep -c "wlan.*state UP")
            ETH_UP=$(ip link show 2>/dev/null | grep -c "eth.*state UP")
            if [ "$WIFI_UP" -gt 0 ] && [ "$ETH_UP" -gt 0 ]; then
                ETH_IFACES=$(ip link show | grep "eth.*state UP" | awk '{print $2}' | tr -d ':')
                for iface in $ETH_IFACES; do $EXEC "ip link set $iface down"; done
                $EXEC "ip neigh flush all"
            fi
            echo -e "${C_GREEN}[✓] Pętle DUP wyeliminowane.${C_RESET}"
            ;;
        4)
            sh "$DIR/db_sanitizer.sh"
            $EXEC "pm trim-caches 2G" >/dev/null 2>&1
            sync
            echo -e "${C_GREEN}[✓] Śmieci usunięte z bazy i pamięci RAM.${C_RESET}"
            ;;
        5)
            if ! ps -ef | grep -q '[w]atchdog_daemon.sh'; then
                nohup sh "$DIR/watchdog_daemon.sh" >/dev/null 2>&1 &
                echo -e "${C_GREEN}[+] Demon Watchdog został uruchomiony w tle.${C_RESET}"
            else
                echo -e "${C_YELLOW}[i] Demon Watchdog już działa.${C_RESET}"
            fi
            ;;
        0)
            exit 0
            ;;
        *)
            echo -e "${C_RED}Błędny wybór!${C_RESET}"
            sleep 1
            ;;
    esac

    echo -e "\n${C_GREEN}Naciśnij Enter, aby powrócić do menu...${C_RESET}"
    read dummy
    show_menu
}

show_menu
EOF

chmod -R +x "$TWEAKS_DIR"
echo "[*] Instalacja zakończona sukcesem! Uruchamiam PlayBox Titanium..."
sh "$TWEAKS_DIR/titanium_master.sh"
