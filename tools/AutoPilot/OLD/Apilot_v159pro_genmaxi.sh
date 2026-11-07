#!/system/bin/sh
INSTALL_DIR="/data/local/tmp/AutoPilot_PRO_Master"
mkdir -p "$INSTALL_DIR"

echo "[*] Generowanie: titanium_master.sh"
cat << 'EOF' > "$INSTALL_DIR/titanium_master.sh"
#!/system/bin/sh
if [ "$(id -u)" -eq 0 ]; then
    printf "\033[1;31m[x]\033[0m Uruchamianie tego narzędzia bezpośrednio jako root nie jest zalecane przez Shizuku!\n" >&2
fi
DIR="$(cd "$(dirname "$0")" && pwd)"
C_RED='\033[31m'; C_GREEN='\033[32m'; C_CYAN='\033[36m'; C_YELLOW='\033[33m'; C_RESET='\033[0m'
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
check_and_start_shizuku() {
    SHIZUKU_PID=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
    if [ -n "$SHIZUKU_PID" ]; then
        return 0
    else
        MAIN_ACTIVITY=$(cmd package resolve-activity --brief moe.shizuku.privileged.api 2>/dev/null | grep "/" | head -n 1)
        [ -n "$MAIN_ACTIVITY" ] && am start -n "$MAIN_ACTIVITY" > /dev/null 2>&1 && sleep 2
        START_SCRIPT=""
        for path in "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh" "/sdcard/Android/data/moe.shizuku.privileged.api/start.sh"; do
            [ -f "$path" ] && START_SCRIPT="$path" && break
        done
        [ -z "$START_SCRIPT" ] && START_SCRIPT=$(find /sdcard/Android/data -name "start.sh" -path "*moe.shizuku*" 2>/dev/null | head -n 1)
        [ -n "$START_SCRIPT" ] && sh "$START_SCRIPT" > /dev/null 2>&1 & sleep 3
        return 0
    }
}
show_menu() {
    clear
    echo -e "${C_CYAN}╔═══════════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_CYAN}║     PLAYBOX TITANIUM v17.0 - MASTER ORCHESTRATOR & FIXER          ║${C_RESET}"
    echo -e "${C_CYAN}╚═══════════════════════════════════════════════════════════════════╝${C_RESET}"
    echo -e " Warstwa wykonawcza: ${C_GREEN}$LAYER${C_RESET}"
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
        1) check_and_start_shizuku; $EXEC "sh $DIR/network_shield_fix.sh"; $EXEC "sh $DIR/core_media_fixer.sh"; pm trim-caches 2G >/dev/null 2>&1 ;;
        2) check_and_start_shizuku; $EXEC "sh $DIR/core_media_fixer.sh" ;;
        3) $EXEC "sh $DIR/network_shield_fix.sh" ;;
        4) check_and_start_shizuku ;;
        5) pm trim-caches 2G >/dev/null 2>&1; sync; echo -e "${C_GREEN}[✓] Pamięć podręczna wyczyszczona.${C_RESET}" ;;
        0) exit 0 ;;
        *) echo -e "${C_RED}Nieprawidłowa opcja!${C_RESET}"; sleep 1 ;;
    esac
    echo -e "\n${C_GREEN}Operacja zakończona. Naciśnij Enter...${C_RESET}"
    read dummy
    show_menu
}
show_menu
EOF

echo "[*] Generowanie: core_media_fixer.sh"
cat << 'EOF' > "$INSTALL_DIR/core_media_fixer.sh"
#!/system/bin/sh
settings put global webview_multiprocess true
setprop debug.webview.max_renderers 2
setprop media.stagefright.cache-params "4096,8192,5"
setprop media.vcodec.preferhw 1
setprop media.acodec.preferhw 1
setprop debug.stagefright.c2.av1 0
setprop debug.stagefright.omx_default_rank 0
setprop media.codec.priority 0
setprop media.stagefright.enable-player true
setprop media.stagefright.enable-http true
setprop media.stagefright.enable-meta true
setprop media.brcm.surface.prewarm true
setprop media.brcm.vpu.prealloc true
setprop media.brcm.decoder.preinit true
setprop media.brcm.tunnel.clock.latency 50
setprop media.tunneled-playback.enable true
setprop debug.hwui.renderer opengl
setprop debug.hwui.profile false
setprop debug.hwui.use_partial_updates false
setprop debug.sf.latch_unsignaled 1
setprop debug.sf.disable_backpressure 1
setprop debug.sf.early_phase_offset_ns 500000
setprop debug.sf.early_app_phase_offset_ns 1000000
settings put system hardware_accelerated 1
settings put secure hdcp_checking 0
settings put system long_press_timeout 250
settings put global window_animation_scale 0.25
settings put global transition_animation_scale 0.25
settings put global animator_duration_scale 0.25
pm clear com.android.providers.media 2>/dev/null
pm clear com.android.providers.media.module 2>/dev/null
killall android.hardware.media.omx@1.0-service 2>/dev/null
killall mediaserver 2>/dev/null
echo "[✓] WebEmbed, OMX oraz mechanizmy SponsorBlock zostały w pełni zoptymalizowane."
EOF

echo "[*] Generowanie: network_shield_fix.sh"
cat << 'EOF' > "$INSTALL_DIR/network_shield_fix.sh"
#!/system/bin/sh
WIFI_UP=$(ip link show | grep -c "wlan.*state UP")
ETH_UP=$(ip link show | grep -c "eth.*state UP")
if [ "$WIFI_UP" -gt 0 ] && [ "$ETH_UP" -gt 0 ]; then
    ETH_IFACE=$(ip link show | grep "eth.*state UP" | awk '{print $2}' | tr -d ':')
    for iface in $ETH_IFACE; do
        ip link set $iface down
    done
fi
ip neigh flush all 2>/dev/null
settings put global wifi_network_mtu 1492
settings put global network_mtu 1492
setprop net.tcp.default_init_rwnd 120
settings put global tcp_default_init_rwnd 120
setprop net.tcp.buffersize.wifi "524288,1048576,2097152,262144,524288,1048576"
setprop net.tcp.buffersize.ethernet "524288,1048576,2097152,262144,524288,1048576"
settings put global network_avoid_bad_wifi 1
settings put global captive_portal_mode 0
settings put global private_dns_mode hostname
settings put global private_dns_specifier "atv-ultralow.dns.nextdns.io"
setprop net.dns1 45.90.28.0
setprop net.dns2 45.90.30.0
svc wifi disable 2>/dev/null
sleep 2
svc wifi enable 2>/dev/null
echo "[✓] Tarcza sieciowa wdrożona pomyślnie."
EOF

chmod -R +x "$INSTALL_DIR"
echo "[*] Sukces! Środowisko Titanium Master zostało zainstalowane w: $INSTALL_DIR"
sh "$INSTALL_DIR/titanium_master.sh"

