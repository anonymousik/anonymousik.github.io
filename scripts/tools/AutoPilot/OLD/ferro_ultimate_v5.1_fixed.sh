#!/bin/bash

#set -euo pipefail
#IFS=$'\n\t'

# ═══════════════════════════════════════════════════════════════════════════
# ⌐FER۝PLAYB༽ටX⫸ ULTIMATE OPTIMIZATION ENGINE v5.1
# ═══════════════════════════════════════════════════════════════════════════

readonly SCRIPT_VERSION="5.1.0-STABLE"
readonly SCRIPT_NAME="⌐FER۝PLAYB༽ටX⫸"
readonly DEVICE_IP="192.168.1.3"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly NC='\033[0m'

# Paths
readonly HOME_DIR="$HOME/qtcs"
readonly LOG_DIR="${HOME_DIR}/ferro_logs"
readonly REPORT_DIR="${HOME_DIR}/ferro_reports"
readonly TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
readonly LOG_FILE="${LOG_DIR}/ferro_${TIMESTAMP}.log"

# Globals
declare -A DEVICE_CAPS
declare -A OPTIMIZATION_PLAN
HAS_ROOT=false

# ═══════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

setup_dirs() {
    mkdir -p "$LOG_DIR" "$REPORT_DIR"
}

log() {
    local level=$1
    shift
    local msg="$*"
    echo "[$(date '+%H:%M:%S')] [$level] $msg" >> "$LOG_FILE"
    
    case $level in
        ERROR)   echo -e "${RED}✘${NC} $msg" >&2 ;;
        WARN)    echo -e "${YELLOW}⚠${NC} $msg" ;;
        SUCCESS) echo -e "${GREEN}✓${NC} $msg" ;;
        INFO)    echo -e "${CYAN}ℹ${NC} $msg" ;;
    esac
}

banner() {
    clear
    echo -e "${CYAN}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║      ⌐FER۝PLAYB༽ටX⫸  ULTIMATE OPTIMIZATION v5.1       ║
║                                                              ║
║   Android TV 9 Specialist | SecFERRO Division               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}\n"
}

adb_safe() {
    local cmd="$*"
    local result
    
    if result=$(adb shell "$cmd" 2>&1); then
        echo "$result"
        return 0
    else
        log WARN "ADB command failed: $cmd"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# CONNECTION
# ═══════════════════════════════════════════════════════════════════════════

connect_device() {
    log INFO "Connecting to Play Box ($DEVICE_IP)..."
    
    adb disconnect >/dev/null 2>&1
    
    if adb connect $DEVICE_IP 2>&1 | grep -q "connected"; then
        sleep 2
        log SUCCESS "Connected"
    else
        log ERROR "Failed to connect"
        return 1
    fi
    
    # Check root
    if adb_safe "su -c 'id'" 2>&1 | grep -q "uid=0"; then
        HAS_ROOT=true
        log SUCCESS "Root access available"
    else
        HAS_ROOT=false
        log WARN "No root - limited features"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC
# ═══════════════════════════════════════════════════════════════════════════

diagnose() {
    log INFO "Starting diagnostic scan..."
    echo ""
    
    # Device info
    echo -e "${CYAN}[1/8]${NC} Device Identity..."
    DEVICE_CAPS[model]=$(adb_safe "getprop ro.product.model" | tr -d '\r' 2>/dev/null || echo "unknown")
    DEVICE_CAPS[android]=$(adb_safe "getprop ro.build.version.release" | tr -d '\r' 2>/dev/null || echo "unknown")
    DEVICE_CAPS[sdk]=$(adb_safe "getprop ro.build.version.sdk" | tr -d '\r' 2>/dev/null || echo "unknown")
    log INFO "Device: ${DEVICE_CAPS[model]} (Android ${DEVICE_CAPS[android]})"
    
    # CPU
    echo -e "${CYAN}[2/8]${NC} CPU Analysis..."
    local cpu_info=$(adb_safe "cat /proc/cpuinfo" 2>/dev/null || echo "")
    DEVICE_CAPS[cpu_cores]=$(echo "$cpu_info" | grep -c "processor" || echo "2")
    DEVICE_CAPS[cpu_hw]=$(echo "$cpu_info" | grep "Hardware" | cut -d':' -f2 | xargs || echo "unknown")
    log INFO "CPU: ${DEVICE_CAPS[cpu_hw]} (${DEVICE_CAPS[cpu_cores]} cores)"
    
    # GPU
    echo -e "${CYAN}[3/8]${NC} GPU Detection..."
    local gpu_info=$(adb_safe "dumpsys SurfaceFlinger 2>/dev/null | grep GLES" || echo "")
    if echo "$gpu_info" | grep -qi "videocore.*v3d"; then
        DEVICE_CAPS[gpu_type]="videocore_v"
        DEVICE_CAPS[use_vulkan]=true
        log INFO "GPU: VideoCore V (Vulkan capable)"
    else
        DEVICE_CAPS[gpu_type]="generic"
        DEVICE_CAPS[use_vulkan]=false
        log INFO "GPU: Generic (OpenGL ES)"
    fi
    
    # Memory
    echo -e "${CYAN}[4/8]${NC} Memory Analysis..."
    local meminfo=$(adb_safe "cat /proc/meminfo" 2>/dev/null || echo "")
    DEVICE_CAPS[ram_total]=$(echo "$meminfo" | grep "MemTotal" | awk '{print int($2/1024)}' || echo "1425")
    DEVICE_CAPS[ram_free]=$(echo "$meminfo" | grep "MemFree" | awk '{print int($2/1024)}' || echo "154")
    DEVICE_CAPS[ram_avail]=$(echo "$meminfo" | grep "MemAvailable" | awk '{print int($2/1024)}' || echo "509")
    
    local ram_used=$((${DEVICE_CAPS[ram_total]} - ${DEVICE_CAPS[ram_avail]}))
    local ram_pct=$((ram_used * 100 / ${DEVICE_CAPS[ram_total]}))
    
    if [ $ram_pct -gt 85 ]; then
        DEVICE_CAPS[mem_status]="critical"
        log WARN "Memory: CRITICAL (${ram_pct}% used)"
    elif [ $ram_pct -gt 70 ]; then
        DEVICE_CAPS[mem_status]="high"
        log WARN "Memory: HIGH (${ram_pct}% used)"
    else
        DEVICE_CAPS[mem_status]="normal"
        log INFO "Memory: Normal (${ram_pct}% used)"
    fi
    
    # ZRAM
    echo -e "${CYAN}[5/8]${NC} ZRAM Detection..."
    if adb_safe "test -b /dev/block/zram0" 2>/dev/null; then
        DEVICE_CAPS[has_zram]=true
        log INFO "ZRAM: Available"
    else
        DEVICE_CAPS[has_zram]=false
        log INFO "ZRAM: Not available"
    fi
    
    # Services
    echo -e "${CYAN}[6/8]${NC} Service Check..."
    local chromecast_running=false
    if adb_safe "pidof com.google.android.apps.mediashell" >/dev/null 2>&1; then
        chromecast_running=true
        log SUCCESS "Chromecast: Running"
    else
        chromecast_running=false
        log WARN "Chromecast: Not running"
    fi
    DEVICE_CAPS[chromecast_ok]=$chromecast_running
    
    # Bloatware
    echo -e "${CYAN}[7/8]${NC} Bloatware Scan..."
    local bloat_count=0
    local bloat_packages=(
        "com.spocky.projengmenu"
        "com.sagemcom.sysupdate"
        "com.sagemcom.appupdate"
        "com.sagemcom.stb.setupwizard"
    )
    
    for pkg in "${bloat_packages[@]}"; do
        if adb_safe "pm list packages" 2>/dev/null | grep -q "^package:$pkg$"; then
            bloat_count=$((bloat_count + 1))
        fi
    done
    DEVICE_CAPS[bloatware]=$bloat_count
    log INFO "Bloatware: $bloat_count packages found"
    
    # Performance
    echo -e "${CYAN}[8/8]${NC} Performance Check..."
    local gfx=$(adb_safe "dumpsys gfxinfo com.teamsmart.videomanager.tv 2>/dev/null" || echo "")
    if [ -n "$gfx" ]; then
        local frames=$(echo "$gfx" | grep "Total frames rendered:" | tail -1 | awk '{print $4}' || echo "0")
        local janky=$(echo "$gfx" | grep "Janky frames:" | tail -1 | awk '{print $3}' || echo "0")
        if [ "$frames" -gt 0 ] 2>/dev/null; then
            local janky_pct=$((janky * 100 / frames))
            DEVICE_CAPS[janky_pct]=$janky_pct
            if [ $janky_pct -gt 50 ]; then
                log WARN "GPU Performance: POOR (${janky_pct}% janky frames)"
            else
                log INFO "GPU Performance: OK (${janky_pct}% janky frames)"
            fi
        fi
    fi
    
    echo ""
    log SUCCESS "Diagnostic complete"
}

# ═══════════════════════════════════════════════════════════════════════════
# OPTIMIZATION PLAN
# ═══════════════════════════════════════════════════════════════════════════

plan() {
    log INFO "Generating optimization plan..."
    echo ""
    
    # GPU
    if [ "${DEVICE_CAPS[use_vulkan]}" = "true" ]; then
        OPTIMIZATION_PLAN[gpu_renderer]="skiavulkan"
        OPTIMIZATION_PLAN[gpu_cache]=48
        log INFO "Plan: Vulkan backend"
    else
        OPTIMIZATION_PLAN[gpu_renderer]="skiagl"
        OPTIMIZATION_PLAN[gpu_cache]=32
        log INFO "Plan: OpenGL backend"
    fi
    
    # Memory
    if [ "${DEVICE_CAPS[mem_status]}" = "critical" ]; then
        OPTIMIZATION_PLAN[aggressive]=true
        OPTIMIZATION_PLAN[zram_mb]=512
        OPTIMIZATION_PLAN[remove_bloat]=true
        log WARN "Plan: Aggressive memory optimization"
    elif [ "${DEVICE_CAPS[mem_status]}" = "high" ]; then
        OPTIMIZATION_PLAN[aggressive]=false
        OPTIMIZATION_PLAN[zram_mb]=384
        OPTIMIZATION_PLAN[remove_bloat]=true
        log INFO "Plan: Moderate memory optimization"
    else
        OPTIMIZATION_PLAN[aggressive]=false
        OPTIMIZATION_PLAN[zram_mb]=256
        OPTIMIZATION_PLAN[remove_bloat]=false
        log INFO "Plan: Standard optimization"
    fi
    
    # Services
    OPTIMIZATION_PLAN[fix_chromecast]=$( [ "${DEVICE_CAPS[chromecast_ok]}" = "false" ] && echo "true" || echo "false" )
    
    echo ""
    log SUCCESS "Optimization plan ready"
}

# ═══════════════════════════════════════════════════════════════════════════
# OPTIMIZATION MODULES
# ═══════════════════════════════════════════════════════════════════════════

optimize_gpu() {
    log INFO "Optimizing GPU..."
    
    # Hardware acceleration
    adb_safe "setprop debug.hwui.use_hardware_acceleration true" >/dev/null
    adb_safe "setprop debug.composition.type gpu" >/dev/null
    adb_safe "setprop debug.egl.hw 1" >/dev/null
    adb_safe "setprop debug.sf.hw 1" >/dev/null
    
    # Renderer
    local renderer="${OPTIMIZATION_PLAN[gpu_renderer]}"
    adb_safe "setprop debug.hwui.renderer $renderer" >/dev/null
    
    if [ "$renderer" = "skiavulkan" ]; then
        adb_safe "setprop debug.renderengine.backend skiavulkan" >/dev/null
        adb_safe "setprop ro.hwui.use_vulkan 1" >/dev/null
    else
        adb_safe "setprop debug.renderengine.backend skiaglthreaded" >/dev/null
    fi
    
    # Cache
    local cache="${OPTIMIZATION_PLAN[gpu_cache]}"
    adb_safe "setprop debug.hwui.texture_cache_size $cache" >/dev/null
    adb_safe "setprop debug.hwui.layer_cache_size $((cache * 2 / 3))" >/dev/null
    adb_safe "setprop debug.hwui.path_cache_size $((cache / 6))" >/dev/null
    
    # Optimizations
    adb_safe "setprop debug.hwui.render_dirty_regions false" >/dev/null
    adb_safe "setprop debug.hwui.use_buffer_age false" >/dev/null
    
    log SUCCESS "GPU optimized ($renderer, ${cache}MB cache)"
}

optimize_surfaceflinger() {
    log INFO "Optimizing SurfaceFlinger..."
    
    # Virtual display support (for cast/mirroring)
    adb_safe "setprop debug.sf.disable_hwc_vds 0" >/dev/null
    adb_safe "setprop debug.sf.enable_hwc_vds 1" >/dev/null
    adb_safe "setprop debug.sf.latch_unsignaled 1" >/dev/null
    adb_safe "setprop debug.sf.max_virtual_display_dimension 1920" >/dev/null
    
    log SUCCESS "SurfaceFlinger optimized (mirroring enabled)"
}

optimize_chromecast() {
    log INFO "Optimizing Chromecast..."
    
    local pkg="com.google.android.apps.mediashell"
    
    # Check if installed
    if ! adb_safe "pm list packages" | grep -q "^package:$pkg$"; then
        log WARN "Chromecast not installed"
        return 1
    fi
    
    # Grant permissions
    local perms=(
        "android.permission.INTERNET"
        "android.permission.ACCESS_NETWORK_STATE"
        "android.permission.ACCESS_WIFI_STATE"
        "android.permission.WAKE_LOCK"
    )
    
    for perm in "${perms[@]}"; do
        adb_safe "pm grant $pkg $perm" >/dev/null 2>&1
    done
    
    # Disable battery optimization
    adb_safe "dumpsys deviceidle whitelist +$pkg" >/dev/null 2>&1
    
    # Fix if not running
    if [ "${OPTIMIZATION_PLAN[fix_chromecast]}" = "true" ]; then
        log INFO "Restarting Chromecast service..."
        adb_safe "am force-stop $pkg" >/dev/null 2>&1
        sleep 2
        adb_safe "am start -n $pkg/.MainActivity" >/dev/null 2>&1
        sleep 2
    fi
    
    log SUCCESS "Chromecast optimized"
}

optimize_mdns() {
    log INFO "Optimizing mDNS (cast discovery)..."
    
    # Enable mDNS
    adb_safe "setprop persist.service.mdns.enable true" >/dev/null
    
    # Start if not running
    if ! adb_safe "getprop init.svc.mdnsd" | grep -q "running"; then
        adb_safe "start mdnsd" >/dev/null 2>&1
        sleep 1
    fi
    
    # Multicast on WiFi
    adb_safe "ip link set wlan0 multicast on" >/dev/null 2>&1
    
    log SUCCESS "mDNS optimized (discovery enabled)"
}

optimize_memory() {
    log INFO "Optimizing memory..."
    
    # Dalvik/ART heap
    adb_safe "setprop dalvik.vm.heapstartsize 8m" >/dev/null
    adb_safe "setprop dalvik.vm.heapgrowthlimit 192m" >/dev/null
    adb_safe "setprop dalvik.vm.heapsize 384m" >/dev/null
    adb_safe "setprop dalvik.vm.heaptargetutilization 0.75" >/dev/null
    
    # ZRAM (if root and available)
    if [ "$HAS_ROOT" = "true" ] && [ "${DEVICE_CAPS[has_zram]}" = "true" ]; then
        local zram_mb="${OPTIMIZATION_PLAN[zram_mb]}"
        local zram_bytes=$((zram_mb * 1024 * 1024))
        
        log INFO "Configuring ZRAM (${zram_mb}MB)..."
        adb_safe "su -c 'swapoff /dev/block/zram0'" >/dev/null 2>&1
        adb_safe "su -c 'echo 1 > /sys/block/zram0/reset'" >/dev/null 2>&1
        adb_safe "su -c 'echo $zram_bytes > /sys/block/zram0/disksize'" >/dev/null 2>&1
        adb_safe "su -c 'mkswap /dev/block/zram0'" >/dev/null 2>&1
        adb_safe "su -c 'swapon /dev/block/zram0'" >/dev/null 2>&1
        
        log SUCCESS "ZRAM enabled (${zram_mb}MB)"
    fi
    
    # LMK (if root)
    if [ "$HAS_ROOT" = "true" ]; then
        log INFO "Tuning LMK..."
        adb_safe "su -c 'echo \"18432,23040,27648,32256,36864,46080\" > /sys/module/lowmemorykiller/parameters/minfree'" >/dev/null 2>&1
        log SUCCESS "LMK tuned"
    fi
    
    # VM tuning (if root)
    if [ "$HAS_ROOT" = "true" ]; then
        if [ "${OPTIMIZATION_PLAN[aggressive]}" = "true" ]; then
            adb_safe "su -c 'echo 100 > /proc/sys/vm/swappiness'" >/dev/null 2>&1
        else
            adb_safe "su -c 'echo 60 > /proc/sys/vm/swappiness'" >/dev/null 2>&1
        fi
        adb_safe "su -c 'echo 50 > /proc/sys/vm/vfs_cache_pressure'" >/dev/null 2>&1
    fi
    
    log SUCCESS "Memory optimized"
}

optimize_video() {
    log INFO "Optimizing video..."
    
    # Media stagefright
    adb_safe "setprop media.stagefright.enable-player true" >/dev/null
    adb_safe "setprop media.stagefright.enable-http true" >/dev/null
    adb_safe "setprop media.stagefright.enable-aac true" >/dev/null
    
    # Buffers
    adb_safe "setprop media.stagefright.cache-params 20971520" >/dev/null
    
    log SUCCESS "Video optimized"
}

optimize_network() {
    log INFO "Optimizing network..."
    
    # DNS
    adb_safe "setprop net.dns1 1.1.1.1" >/dev/null
    adb_safe "setprop net.dns2 1.0.0.1" >/dev/null
    
    # WiFi
    adb_safe "settings put global wifi_sleep_policy 2" >/dev/null 2>&1
    
    log SUCCESS "Network optimized (Cloudflare DNS)"
}

optimize_ui() {
    log INFO "Optimizing UI responsiveness..."
    
    # Animation speeds
    adb_safe "settings put global window_animation_scale 0.5" >/dev/null 2>&1
    adb_safe "settings put global transition_animation_scale 0.5" >/dev/null 2>&1
    adb_safe "settings put global animator_duration_scale 0.5" >/dev/null 2>&1
    
    # Force GPU for 2D
    adb_safe "setprop debug.hwui.render_thread true" >/dev/null
    
    log SUCCESS "UI optimized"
}

remove_bloatware() {
    if [ "${OPTIMIZATION_PLAN[remove_bloat]}" != "true" ]; then
        return 0
    fi
    
    log INFO "Removing bloatware..."
    
    local bloat=(
        "com.spocky.projengmenu"
        "com.sagemcom.sysupdate"
        "com.sagemcom.appupdate"
        "com.sagemcom.stb.setupwizard"
    )
    
    local removed=0
    for pkg in "${bloat[@]}"; do
        if adb_safe "pm list packages" | grep -q "^package:$pkg$"; then
            if adb_safe "pm uninstall --user 0 $pkg" 2>&1 | grep -q "Success"; then
                removed=$((removed + 1))
            else
                adb_safe "pm disable-user --user 0 $pkg" >/dev/null 2>&1 && removed=$((removed + 1))
            fi
        fi
    done
    
    log SUCCESS "Bloatware removed ($removed packages)"
}

# ═══════════════════════════════════════════════════════════════════════════
# VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

verify() {
    log INFO "Verifying optimizations..."
    echo ""
    
    sleep 3
    
    # GPU renderer
    local renderer=$(adb_safe "getprop debug.hwui.renderer" | tr -d '\r')
    if [ "$renderer" = "${OPTIMIZATION_PLAN[gpu_renderer]}" ]; then
        log SUCCESS "GPU renderer: $renderer ✓"
    else
        log WARN "GPU renderer: $renderer (expected: ${OPTIMIZATION_PLAN[gpu_renderer]})"
    fi
    
    # Chromecast
    if adb_safe "pidof com.google.android.apps.mediashell" >/dev/null 2>&1; then
        log SUCCESS "Chromecast: Running ✓"
    else
        log WARN "Chromecast: Not running"
    fi
    
    # mDNS
    if adb_safe "getprop init.svc.mdnsd" | grep -q "running"; then
        log SUCCESS "mDNS: Running ✓"
    else
        log WARN "mDNS: Not running"
    fi
    
    # Memory
    local new_avail=$(adb_safe "cat /proc/meminfo" | grep "MemAvailable" | awk '{print int($2/1024)}')
    local improvement=$((new_avail - ${DEVICE_CAPS[ram_avail]}))
    if [ $improvement -gt 0 ]; then
        log SUCCESS "Memory freed: +${improvement}MB ✓"
    else
        log INFO "Memory: ${new_avail}MB available"
    fi
    
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════

report() {
    local file="${REPORT_DIR}/optimization_${TIMESTAMP}.txt"
    
    cat > "$file" << EOF
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║      ⌐FER۝PLAYB༽ටX⫸  OPTIMIZATION REPORT              ║
║                                                              ║
║   Completed: $(date)                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

DEVICE INFORMATION:
  Model: ${DEVICE_CAPS[model]}
  Android: ${DEVICE_CAPS[android]} (SDK ${DEVICE_CAPS[sdk]})
  CPU: ${DEVICE_CAPS[cpu_hw]} (${DEVICE_CAPS[cpu_cores]} cores)
  GPU: ${DEVICE_CAPS[gpu_type]}
  RAM: ${DEVICE_CAPS[ram_total]}MB total, ${DEVICE_CAPS[ram_avail]}MB available

OPTIMIZATIONS APPLIED:
  ✓ GPU: ${OPTIMIZATION_PLAN[gpu_renderer]} (${OPTIMIZATION_PLAN[gpu_cache]}MB cache)
  ✓ SurfaceFlinger: Optimized for cast/mirroring
  ✓ Chromecast: Service optimized
  ✓ mDNS: Discovery enabled
  ✓ Memory: Dalvik/ART tuned$( [ "$HAS_ROOT" = "true" ] && [ "${DEVICE_CAPS[has_zram]}" = "true" ] && echo ", ZRAM ${OPTIMIZATION_PLAN[zram_mb]}MB" || echo "" )
  ✓ Video: Media pipeline optimized
  ✓ Network: Cloudflare DNS
  ✓ UI: Responsiveness boosted$( [ "${OPTIMIZATION_PLAN[remove_bloat]}" = "true" ] && echo "
  ✓ Bloatware: Removed ${DEVICE_CAPS[bloatware]} packages" || echo "" )

RECOMMENDATIONS:
  • Reboot device for all changes to take effect
  • Test Chromecast functionality after reboot
  • Monitor performance over next 24 hours

Report saved: $file
EOF
    
    log SUCCESS "Report generated: $file"
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

main() {
    setup_dirs
    banner
    
    log INFO "Starting $SCRIPT_NAME v$SCRIPT_VERSION"
    echo ""
    
    # Connect
    if ! connect_device; then
        exit 1
    fi
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  PHASE 1: DIAGNOSTIC${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    diagnose
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  PHASE 2: PLANNING${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    plan
    
    echo ""
    read -p "Proceed with optimization? [Y/n]: " -r
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log INFO "Cancelled by user"
        exit 0
    fi
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  PHASE 3: OPTIMIZATION${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    optimize_gpu
    optimize_surfaceflinger
    optimize_chromecast
    optimize_mdns
    optimize_memory
    optimize_video
    optimize_network
    optimize_ui
    remove_bloatware
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  PHASE 4: VERIFICATION${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    verify
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  PHASE 5: REPORTING${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    report
    
    echo ""
    echo -e "${GREEN}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║               ✓  OPTIMIZATION COMPLETE  ✓                   ║
║                                                              ║
║   Your Play Box has been optimized!                         ║
║                                                              ║
║   🔄 Recommended: Reboot device now                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    
    log SUCCESS "Optimization completed"
    log INFO "Logs: $LOG_FILE"
    echo ""
    
    read -p "Reboot device now? [y/N]: " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log INFO "Rebooting..."
        adb reboot
    else
        log INFO "Please reboot manually"
    fi
    
    echo ""
}

main "$@"
