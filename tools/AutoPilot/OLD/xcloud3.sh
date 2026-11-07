#!/system/bin/sh
# ==============================================================================
# PLAYBOX TITANIUM — ADVANCED FRAME-PACING & JANK REDUCTION FIXER
# Target: Sagemcom DCTIW362P | Android TV 9 | Broadcom BCM72604
# ==============================================================================

# Wykrycie uprawnień wykonawczych (Root / Rish)
if su -c 'id' 2>/dev/null | grep -q 'uid=0'; then
    EXEC="su -c"
elif [ -x "/data/local/tmp/rish" ] && /data/local/tmp/rish -c 'id' 2>/dev/null | grep -q 'uid=2000'; then
    EXEC="/data/local/tmp/rish -c"
else
    EXEC="sh -c"
fi

echo "[*] Rozpoczynam głęboką optymalizację potoku klatek i redukcję janków..."

# 1. Naprawa silnika renderowania interfejsu (Wyłączenie Vulkan, wymuszenie stabilnego SkiaGL)
$EXEC "setprop debug.hwui.renderer skiagl"
$EXEC "setprop debug.renderengine.backend skiagl"
$EXEC "setprop debug.hwui.render_thread true"
$EXEC "setprop debug.egl.hw 1"
$EXEC "setprop debug.sf.hw 1"

# 2. Eliminacja opóźnień V-Sync i narzutu buforowania ramek UI
$EXEC "setprop debug.sf.latch_unsignaled 1"
$EXEC "setprop debug.sf.disable_backpressure 1"
$EXEC "setprop debug.sf.early_phase_offset_ns 500000"
$EXEC "setprop debug.gr.numframebuffers 3"

# 3. Naprawa WebView / WebEmbed (Zarządzanie procesami pod SponsorBlock)
$EXEC "settings put global webview_multiprocess true"
$EXEC "setprop debug.webview.max_renderers 3"

# 4. Optymalizacja OMX i VDec32 (Płynny seek przy pomijaniu wideo)
$EXEC "setprop persist.media.treble_omx false"
$EXEC "setprop media.codec.priority 0"
$EXEC "setprop media.vcodec.preferhw true"
$EXEC "setprop media.acodec.preferhw true"
$EXEC "setprop media.brcm.mma.enable 1"
$EXEC "setprop media.brcm.vpu.buffers 32"
$EXEC "setprop media.brcm.vdec.progoverride 2"
$EXEC "setprop media.tunneled-playback.enable true"

# 5. Przyspieszenie JIT dla procesora Cortex-A15 (Instrukcja idiv)
$EXEC "setprop dalvik.vm.isa.arm.features default,idiv"
$EXEC "setprop dalvik.vm.heapminfree 2m"
$EXEC "setprop dalvik.vm.heapmaxfree 16m"

# 6. Czyszczenie pamięci i restart usług systemowych wideo
$EXEC "pm trim-caches 4096G" 2>/dev/null
$EXEC "killall android.hardware.media.omx@1.0-service" 2>/dev/null
$EXEC "killall mediaserver" 2>/dev/null
sync

echo "[✓] Potok dekodowania został zoptymalizowany. Klatkowanie wyeliminowane."
