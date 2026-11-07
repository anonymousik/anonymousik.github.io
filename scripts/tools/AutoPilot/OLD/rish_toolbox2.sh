#!/system/bin/sh
# ==============================================================================
# Tytuł: Rish Smart Toolbox v3.0.0 (Ultimate Edition)
# Autor: Ferro (#AIAssisted)
# Cel: Pełna automatyzacja Shizuku, zdalny deployment, "ożywianie" aplikacji
# ==============================================================================

# Definicje ścieżek
TOOL_NAME="rish_toolbox.sh"
TARGET_DIR="/data/local/tmp"

# --- MODUŁ: Zdalny Deploy (Uruchamiane z Twojego PC/Termux-hosta) ---
deploy_to_remote() {
    echo -e "\033[1;34m[i]\033[0m Rozpoczynam zdalny deploy na urządzenie ADB..."
    adb push "$0" "$TARGET_DIR/$TOOL_NAME"
    adb shell "chmod +x $TARGET_DIR/$TOOL_NAME"
    echo -e "\033[1;32m[+]\033[0m Narzędzie wysłane. Uruchom: adb shell $TARGET_DIR/$TOOL_NAME"
    exit 0
}

# Jeśli skrypt wywołano z argumentem --deploy, wyślij go
if [ "$1" = "--deploy" ]; then deploy_to_remote; fi

# --- MODUŁ: "Ożywianie" (Wake-up Shizuku) ---
wake_shizuku() {
    echo -e "\033[1;36m[i]\033[0m Próba automatycznego wybudzenia aplikacji Shizuku..."
    # Uruchomienie głównej aktywności w tle
    am start -n moe.shizuku.privileged.api/.MainActivity > /dev/null 2>&1
    sleep 3
    echo -e "\033[1;32m[+]\033[0m Aplikacja wywołana. Jeśli na TV pojawiło się okno, zaakceptuj dostęp."
}

# --- MODUŁ: Zarządzanie Serwerem ---
manage_service() {
    SHIZUKU_PID=$(ps -ef | grep 'shizuku_server' | grep -v 'grep' | awk '{print $2}')
    
    if [ -z "$SHIZUKU_PID" ]; then
        echo -e "\033[1;33m[!]\033[0m Serwer nie działa. Próba automatycznego startu..."
        wake_shizuku
        
        # Skanowanie ścieżek startowych
        START_SCRIPT=$(find /sdcard/Android/data -name "start.sh" -path "*moe.shizuku*" 2>/dev/null | head -n 1)
        
        if [ -n "$START_SCRIPT" ]; then
            sh "$START_SCRIPT" > /dev/null 2>&1 &
            sleep 3
            echo -e "\033[1;32m[+]\033[0m Usługa wystartowała."
        else
            echo -e "\033[1;31m[x]\033[0m Nie odnaleziono start.sh. Sprawdź, czy aplikacja na TV jest zainstalowana."
        fi
    else
        echo -e "\033[1;32m[+]\033[0m Serwer już działa (PID: $SHIZUKU_PID)."
    fi
}

# MENU GŁÓWNE
echo -e "\033[1;34m=== Rish Toolbox v3.0.0 ===\033[0m"
echo "1) Wymuś start (Wake-up & Inject)"
echo "2) Weryfikacja wektora (PPID)"
echo "3) Deploy (Pushuj na zdalne urządzenie: --deploy)"
echo "0) Wyjście"
read -p "Wybierz [0-3]: " choice

case $choice in
    1) manage_service ;;
    2) # Logika weryfikacji PPID (z poprzedniej wersji)
       export RISH_APPLICATION_ID="com.android.shell"
       RESULT=$(sh -c "/data/local/tmp/rish -c 'cat /proc/\$\$/status | grep PPid'")
       echo "PPID: $RESULT" ;;
    3) deploy_to_remote ;;
    *) exit 0 ;;
esac