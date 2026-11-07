#!/system/bin/sh

# ==============================================================================
# Skrypt: Zmiana stosu renderowania na Sagemcom DCTIW362_PLAY
# Cel: Porzucenie ciężkiego SkiaGL na rzecz lżejszego, natywnego HWUI (OpenGL)
# ==============================================================================

LOG_TAG="GPU_TWEAK"

log_info() {
    echo "\033[1;36m[GPU_TWEAK]\033[0m $1"
    log -t $LOG_TAG "$1"
}

echo "=========================================================="
echo " Wymuszanie profilu HWUI OpenGL dla architektury V3D      "
echo "=========================================================="

# 1. Zmiana głównego silnika rysowania interfejsu (HWUI)
# Domyślnie było 'skiagl'. Zmieniamy na natywny silnik 'opengl'.
setprop debug.hwui.renderer opengl
log_info "Silnik HWUI ustawiony na: opengl"

# 2. Zmiana backendu kompozycji (RenderEngine)
# SurfaceFlinger na Android 9 pozwala na wybór. Zmieniamy 'skiaglthreaded' na 'gles'.
setprop debug.renderengine.backend gles
log_info "Backend RenderEngine ustawiony na: gles"

# 3. Rozwiązanie konfliktu buforów
# Wyłączamy 'use_buffer_age' w HWUI, ponieważ sterownik V3D (ro.v3d.disable_buffer_age=true)
# i tak tego nie obsługuje, a próby użycia generują błędy (EGL_EXT_buffer_age).
setprop debug.hwui.use_buffer_age false
log_info "Zarządzanie starymi buforami (Buffer Age) wyłączone."

# 4. Wyłączenie przestarzałej flagi
# 'force_opengl' często konfliktuje z dynamicznym przypisywaniem EGL. Lepsza jest naturalna
# negocjacja kontekstu dla HWUI.
setprop debug.force_opengl 0
log_info "Wymuszanie archaicznego profilu OpenGL wyłączone."

# 5. Zwiększenie ilości zachowywanych warstw dla Leanback Launcher (TV)
# Skoro używamy HWUI, zwiększenie cache dla warstw przyspieszy przewijanie kafelków.
setprop debug.hwui.layer_cache_size 49152  # (Z 32768 na 48MB)
log_info "Zwiększono rozmiar pamięci podręcznej dla warstw."

# --- APLIKOWANIE ZMIAN ---
# Zmiany w 'debug.hwui.*' wymagają zrestartowania serwisu odpowiedzialnego za kompozycję ekranu.
echo "=========================================================="
log_info "Aplikowanie zmian. Nastąpi chwilowe zgaszenie ekranu..."
echo "=========================================================="

# Zatrzymanie i ponowne uruchomienie menedżera okien (SurfaceFlinger) i menedżera aktywności (Zygote).
# To bezpieczna komenda (tzw. "soft reboot"), system wstanie po kilku sekundach z nowymi propami.
stop
sleep 2
start

log_info "System przeładowany. Użyj komendy: getprop | grep debug.hwui.renderer aby sprawdzić."

