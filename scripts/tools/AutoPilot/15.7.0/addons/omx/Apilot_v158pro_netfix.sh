#!/system/bin/sh
# ==============================================================================
# Moduł Sieciowy: Eliminacja DUP Packets, Konfiguracja DoT, MTU i Buforów TCP
# ==============================================================================
echo "[+] Inicjalizacja tarczy sieciowej i procedury usuwania DUP Packets..."

# 1. NAPRAWA DUP PACKETS (Konflikt Wi-Fi + Ethernet jednocześnie)
WIFI_UP=$(ip link show | grep -c "wlan.*state UP")
ETH_UP=$(ip link show | grep -c "eth.*state UP")

if [ "$WIFI_UP" -gt 0 ] && [ "$ETH_UP" -gt 0 ]; then
    echo "  [!] Wykryto jednoczesną aktywność Wi-Fi oraz Ethernet. Wyłączam eth0, aby uniknąć pętli..."
    ETH_IFACE=$(ip link show | grep "eth.*state UP" | awk '{print $2}' | tr -d ':')
    for iface in $ETH_IFACE; do
        ip link set $iface down
    done
fi
ip neigh flush all 2>/dev/null

# 2. MTU ORAZ BUFOROWANIE TCP (Streamowanie IPTV 4K bez zacięć)
settings put global wifi_network_mtu 1492
settings put global network_mtu 1492
setprop net.tcp.default_init_rwnd 120
settings put global tcp_default_init_rwnd 120
setprop net.tcp.buffersize.wifi "524288,1048576,2097152,262144,524288,1048576"
setprop net.tcp.buffersize.ethernet "524288,1048576,2097152,262144,524288,1048576"

# 3. FIX DNS (Szybki NextDNS DoT, brak błędu "Brak internetu")
settings put global network_avoid_bad_wifi 1
settings put global captive_portal_mode 0
settings put global private_dns_mode hostname
settings put global private_dns_specifier "atv-ultralow.dns.nextdns.io"
setprop net.dns1 45.90.28.0
setprop net.dns2 45.90.30.0

# 4. RESET SUBSYSTEMU SIECIOWEGO
svc wifi disable 2>/dev/null
sleep 2
svc wifi enable 2>/dev/null

echo "[✓] Tarcza sieciowa wdrożona pomyślnie."