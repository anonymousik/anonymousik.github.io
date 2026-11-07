#!/bin/bash

# ==============================================================================
# KONFIGURACJA SEKTORA SIECIOWEGO
# ==============================================================================
DEVICE_IP="192.168.1.3"
REMOTE_DIR="/data/local/tmp"

echo "[*] Inicjalizacja: Bypass DNS (Direct IP Routing)..."

# Test 1: Test łączności surowym TCP/80 do Cloudflare (Bez DNS)
echo "[*] Testowanie dostępności Cloudflare (Anycast)..."
adb shell "$REMOTE_DIR/curl -v --connect-timeout 5 http://162.159.140.220/ 2>&1" | grep "Connected" 

# Test 2: Pomiar prędkości metodą "Direct IP Header Spoofing"
echo "[*] Rozpoczynam pomiar przepustowości (50MB)..."
DL_RESULT=$(adb shell "$REMOTE_DIR/curl -o /dev/null -s -w '%{speed_download}' \
    -H 'Host: speed.cloudflare.com' \
    'http://162.159.140.220/__down?bytes=50000000'")

# Konwersja bajtów na Mbps z użyciem 'bc' lub 'awk'
# Używamy prostszego porównania dostępnego w każdym shellu
if [ -n "$DL_RESULT" ] && [ "$DL_RESULT" != "0" ]; then
    MBPS=$(awk -v d="$DL_RESULT" 'BEGIN { printf "%.2f", (d*8)/1000000 }')
    echo "[+] WYNIK DOWNLOAD: $MBPS Mbps"
else
    echo "[!] BŁĄD: CDN nie odpowiedział lub zerowa prędkość. Sprawdź ruting IP."
fi