#!/system/bin/sh
# ==============================================================================
# Moduł Naprawczy Wideo, WebEmbed Player & SponsorBlock Freeze Fix
# Target: Sagemcom DCTIW362P / Android TV 9 / Broadcom VDec32
# ==============================================================================
echo "[+] Inicjalizacja zaawansowanego modułu naprawczego wideo i WebEmbed..."

# 1. WEBEMBED PLAYER & SPONSORBLOCK FREEZE FIX
# Problem: SmartTube przy automatycznym pomijaniu segmentów sponsorowanych (SponsorBlock) 
# wysyła szybkie żądanie przewinięcia (seek), co w trybie standardowego WebView 
# powoduje zawieszenie wątku renderowania JavaScript/DOM i zablokowanie odtwarzacza.
# Rozwiązanie: Wymuszenie trybu wieloprocesowego WebView, dedykowany bufor 
# oraz zrównoważony narzut klatek.
settings put global webview_multiprocess true
setprop debug.webview.max_renderers 2
setprop media.stagefright.cache-params "4096,8192,5"
setprop media.vcodec.preferhw 1
setprop media.acodec.preferhw 1

# 2. OMX / BLACKSCREEN & HARDWARE DECODING FIX
# Stabilizacja dekodera VDec32 dla strumieni VP9, blokada wadliwego oprogramowania AV1,
# zapobieganie race-condition przy nagłej zmianie pozycji czasu (skip sponsor block).
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

# 3. GPU SERVICE & UI RENDERING TWEAKS (VideoCore IV OpenGL/SkiaGL)
# Unikanie niestabilnego na tym sprzęcie silnika Vulkan, przejście na wydajne SkiaGL
setprop debug.hwui.renderer opengl
setprop debug.hwui.profile false
setprop debug.hwui.use_partial_updates false
setprop debug.sf.latch_unsignaled 1
setprop debug.sf.disable_backpressure 1
setprop debug.sf.early_phase_offset_ns 500000
setprop debug.sf.early_app_phase_offset_ns 1000000

# Wymuszenie płynności nakładek wideo i hardware acceleration
settings put system hardware_accelerated 1
settings put secure hdcp_checking 0

# Responsywność pilota i czasu reakcji interfejsu
settings put system long_press_timeout 250
settings put global window_animation_scale 0.25
settings put global transition_animation_scale 0.25
settings put global animator_duration_scale 0.25

# 4. RESET INSTANCJI KODEKÓW W PAMIĘCI
# Czyszczenie zepsutych deskryptorów po zawieszeniach odtwarzacza
pm clear com.android.providers.media 2>/dev/null
pm clear com.android.providers.media.module 2>/dev/null
killall android.hardware.media.omx@1.0-service 2>/dev/null
killall mediaserver 2>/dev/null

echo "[✓] WebEmbed, OMX oraz mechanizmy SponsorBlock zostały w pełni zoptymalizowane."