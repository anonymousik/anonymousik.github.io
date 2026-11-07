#!/system/bin/sh

# ==============================================================================
# SCRIPT: PURGE & RESTRICT (M362 Optimized)
# UWAGA: Skrypt wykonuje agresywne czyszczenie. Może zatrzymać usługi 
# działające w tle (np. powiadomienia, synchronizacja).
# ==============================================================================

log_msg() { echo "\033[1;32m[PURGE]\033[0m $1"; }

log_msg "Rozpoczynam restrykcyjne czyszczenie pamięci..."

# 1. Agresywne zwalnianie Cache (FSTRIM + Purge)
log_msg "Etap 1: Czyszczenie pamięci podręcznej i FSTRIM"
sm fstrim
pm trim-caches 9999999999
log_msg "Cache wyczyszczone."

# 2. Force-Stop zbędnych procesów (Non-System Critical)
# Tutaj ubijamy procesy, które nie są krytyczne dla jądra (Zygote) 
# lub interfejsu graficznego (SurfaceFlinger).
log_msg "Etap 2: Ubijanie procesów w tle (oprócz usług systemowych)"

# Lista pakietów do ubicia (możesz dopisać własne aplikacje, których nie używasz w danej chwili)
# NIE UBJAJ: com.android.systemui, com.android.launcher, com.android.settings
KILL_LIST="com.google.android.youtube com.google.android.gms.setup_wizard com.netflix.ninja com.amazon.amazonvideo.livingroom"

for pkg in $KILL_LIST; do
    am force-stop $pkg
    log_msg "Zatrzymano: $pkg"
done

# 3. Wymuszenie Garbage Collection (GC)
# Prosimy system o zwolnienie nieużywanych obiektów w pamięci Heap
log_msg "Etap 3: Wymuszanie Garbage Collection"
cmd activity force-gc

# 4. Restrykcyjne ustawienie LMK (Low Memory Killer)
# Na Androidzie 9 bez roota nie zmienimy wartości w /sys/module/lowmemorykiller/parameters/minfree,
# ale możemy zmniejszyć 'swappiness' (o ile kernel wspiera) lub zresetować limity procesów.
# Poniżej resetujemy limity dla procesów w tle, aby były bardziej agresywnie ubijane.
settings put global background_activity_optimization_enabled 1
log_msg "Aktywowano agresywną optymalizację aktywności w tle."

# 5. Wyłączenie zbędnych usług (Trwałe dla sesji)
# Wyłączamy usługi, które pożerają RAM w tle (Telemetria, Sklepy, itp.)
# UWAGA: To jest bardzo restrykcyjne.
log_msg "Etap 4: Restrykcyjne wyłączanie usług"
# Wyłączenie "Play Auto Install" (częsty pożeracz RAM)
pm disable-user --user 0 com.android.vending > /dev/null 2>&1
# Wyłączenie Google Assistant (jeśli nie używasz - oszczędza dużo RAM)
pm disable-user --user 0 com.google.android.googlequicksearchbox > /dev/null 2>&1

log_msg "=========================================================="
log_msg "Czyszczenie zakończone. System zwolnił zasoby."
log_msg "Zalecane: Uruchom SmartTube od razu po tej operacji."
log_msg "=========================================================="
