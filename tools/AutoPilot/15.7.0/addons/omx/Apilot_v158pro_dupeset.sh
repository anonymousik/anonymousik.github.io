#!/system/bin/sh
# ==============================================================================
# Moduł DB Sanitizer - Usuwanie konfliktów na poziomie warstwy Settings
# ==============================================================================
source /data/local/tmp/.tweaks/rish_env.sh

echo "[*] Rozpoczynam sanityzację bazy Settings (Global & Secure)..."

# Zdefiniowane patologiczne wpisy, które blokują poprawne ładowanie HWUI i OMX
GLOBAL_BAD="max_phantom_processes private_dns1 private_dns2 private_dns private_dns2_specifier \
activity_manager_constants.max_cached_processes sys.sysctl.tcp_def_init_rwnd tcp_default_init_rwnd \
tcp_init_rwnd net.dns1 net.dns2 net.dns3 net.dns4 net.tcp.buffersize.default net.tcp.buffersize.ethernet \
net.tcp.buffersize.wifi hwui.renderer hwui.layer_cache_size sf.renderer sf.early_phase_offset_ns \
media.brcm.mma.enable media.brcm.surface.prewarm media.brcm.tunnel.clock.latency media.brcm.vpu.buffer.size \
media.brcm.vpu.buffer media.brcm.vpu.buffers media.brcm.vpu.bufferz media.codec.priority media.decoder.use-codec-buffer \
media.stagefright.cache-params media.stagefright.enable-aac media.stagefright.enable-http media.stagefright.enable-meta \
media.stagefright.enable-player media.stagefright.enable-rtsp media.stagefright.enable-scan media.stagefright.thumbnail.prefer_hw_codecs \
media.tunneled-playback.enable sys.ui.hw sys.watchdog.timeout sys_watchdog_timeout_ms vdec.progoverride \
video.accelerate.hw dalvik.vm.isa.arm.features persist.sys.hdr.enable persist.sys.sf.color_saturation \
persist.sys.thermal.enable persist.sys.videomode ro.vendor.hdr.enable set-fixed-performance-mode-enabled \
sf_frame_rate_override surface_flinger surface_flinger_enable_layer_caching surface_flinger_layer_caching \
sys_free_storage_alloc_limit sys_uidcpupower ui_hw _boot_Phenotype_flags low_power_mode low_power_mode_sticky"

SECURE_BAD="put .early_gl_phase_offset_ns prop.persist.sys.hdmi.hdr_mode CONFIG_DEBUG_FS GL_ARB_compute_shader \
cpu_frequency cpu_frequency_scaling_enabled dalvik.vm.image-dex2oat-Xms dalvik.vm.isa.arm.features inotify_queue \
isa.features lmk.critical lmk.low lmk.medium lmk.upgrade_pressure media.acodec.preferhw media.brcm.surface.prewarm \
media.brcm.vpu.buffer.size media.brcm.vpu.buffers media.brcm.vpu.bufferz media.vcodec.outportbuf media.vcodec.preferhw \
net.tcp.buffersize.default net.tcp.buffersize.ethernet net.tcp.buffersize.wifi net.tcp.default_init_rwnd persist.media.treble_omx \
persist.sys.hdmi.hdr_mode persist.sys.videomode ro.lmk.upgrade_pressure ro.nx.mma set-fixed-performance-mode-enabled \
sf.early_phase_offset_ns sgc_eda_version sys.sysctl.tcp_def_init_rwnd sys.watchdog.timeout tcp_init_rwnd wifi_network_mtu screensaver_enabled"

for g in $GLOBAL_BAD; do
    $EXEC "settings delete global $g" 2>/dev/null
done

for s in $SECURE_BAD; do
    $EXEC "settings delete secure $s" 2>/dev/null
done

echo "[✓] Śmieci i przestarzałe zmienne zostały usunięte z rejestrów systemowych."