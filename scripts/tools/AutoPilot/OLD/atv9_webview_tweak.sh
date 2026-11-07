#!/system/bin/sh
# ==============================================================================
# PlayBox Titanium Ultimate — Native POSIX Fallback
# Jeśli Python nie jest dostępny, ten skrypt aplikuje krytyczne fundamenty.
# Uruchamiać z uprawnieniami ROOT (su).
# ==============================================================================

LOG_TAG="Titanium_Ultimate"
log() { echo "\033[36m[*]\033[0m $1"; logger -t "$LOG_TAG" "$1" 2>/dev/null; }
err() { echo "\033[31m[x]\033[0m $1"; exit 1; }

[ "$(id -u)" != "2000" ] && err "Wymagane uprawnienia roota (shell!)	"

log "Inicjalizacja PlayBox Titanium Native (API 28 | BCM72604)..."

# 1. GRAPHICS (SkiaGL + Triple Buffering)
setprop debug.hwui.renderer skiagl
setprop debug.renderengine.backend skiaglthreaded
setprop debug.hwui.render_thread true
setprop debug.gr.numframebuffers 3
setprop debug.sf.disable_backpressure 1
setprop persist.sys.ui.hw true

# 2. MEDIA (AV1 Block -> VP9 Enforce)
setprop debug.stagefright.c2.av1 0
setprop media.av1.sw.decode.disable true
setprop media.codec.av1.disable true
setprop media.stagefright.enable-player true
setprop media.vcodec.preferhw true
setprop media.tunneled-playback.enable true
setprop audio.offload.disable 1
setprop persist.sys.hdmi.keep_awake true

# 3. DALVIK & MEMORY
setprop dalvik.vm.heapminfree 2m
setprop dalvik.vm.heapmaxfree 16m
setprop ro.lmk.kill_heaviest_task true
setprop ro.lmk.upgrade_pressure 50

# 4. WEBVIEW (Wymuszenie akceleracji i wył. smooth scrollingu)
log "Aplikowanie flag WebView..."
FLAGS="--ignore-gpu-blocklist --enable-gpu-rasterization --enable-oop-rasterization --disable-smooth-scrolling --num-raster-threads=2 --disable-features=SurfacePolish"
echo "webview $FLAGS" > /data/local/tmp/webview-command-line
chmod 666 /data/local/tmp/webview-command-line
setprop webview.command_line /data/local/tmp/webview-command-line
setprop webview.vmsize 52428800

# 5. KERNEL & I/O
log "Optymalizacja Kernel Schedulera (Cortex-A15)..."
echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null
echo performance > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor 2>/dev/null
echo deadline > /sys/block/mmcblk0/queue/scheduler 2>/dev/null
echo 512 > /sys/block/mmcblk0/queue/read_ahead_kb 2>/dev/null
echo 0 > /proc/sys/vm/swappiness 2>/dev/null

# 6. GLOBAL SETTINGS
settings put global window_animation_scale 0.35
settings put global transition_animation_scale 0.35
settings put global animator_duration_scale 0.35
settings put global private_dns_mode hostname
settings put global private_dns_specifier one.one.one.one

sync
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null
log "Gotowe! Urządzenie działa na sterydach."
