#!/system/bin/sh

# ==============================================================================
# SECOPS AUDIO MASTER OPTIMIZER - CONFIG & TUNING
# ==============================================================================

echo "[*] Inicjalizacja modyfikacji bazy settings (Shizuku/rish)..."

# 1. OPTYMALIZACJA ZARZĄDZANIA ENERGIĄ (Zapobieganie usypianiu procesów media)
# Wyłączenie agresywnego oszczędzania energii, które często "przycina" audio przy zmianie sceny
settings put global low_power 0
settings put global low_power_mode_sticky 0

# 2. AUDIOPOLICY TUNING (Redukcja restrykcji systemowych)
# Wyłączenie stanu bezpieczeństwa głośności, który może powodować przerwania (glitches) przy zmianie formatu bitstream
settings put system audio_safe_volume_state 3

# 3. ZWIĘKSZENIE PRIORYTETÓW BUFORA (setprop persist)
# Te parametry wymuszają na systemie zwiększenie buforów dla streamingu (zmniejsza ryzyko underrun przy seek)
setprop persist.audio.offload.buffer.size.kb 1024
setprop persist.audio.fluence.voicecall false
setprop persist.audio.fluence.speaker false
setprop media.stagefright.audio.drop 0

# 4. TUNING DLA SmartTube (Dla konkretnego pakietu)
# Jeśli Twój TV to Android TV, wymuszenie "Performance Mode" dla grafiki/media
setprop debug.performance.tuning 1
setprop video.accelerate.hw 1

echo "[+] Modyfikacje zapisane w bazie settings i system prop."
echo "[*] Wymagany restart usług dźwięku w celu aplikacji zmian..."

