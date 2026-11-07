#!/system/bin/sh

# ============================================================================
# AUTOFIX ATV-NET PRO v2.0 - Ultimate Network Repair Tool
# ============================================================================
# Przeznaczenie: Android TV 9+ (API 28+)
# Autor: Titanium Development Team
# Data: Luty 2026
# 
# FUNKCJE:
# - Automatyczna diagnostyka sieci (ping, DNS, NTP, connectivity)
# - Wybór z 8 serwerów DNS (Cloudflare, Google, Quad9, AdGuard, itd.)
# - Auto-fix problemów sieciowych
# - Restart interfejsów Wi-Fi/Ethernet
# - Synchronizacja czasu NTP
# - Captive Portal fix
# - Kolorowe raporty
#
# SZYBKIE UŻYCIE (jedna komenda):
# curl -sL https://gist.githubusercontent.com/.../AUTOFIX_ATV-NET-PRO.sh | sh -c "cat > /tmp/net.sh && adb push /tmp/net.sh /data/local/tmp/ && adb shell 'chmod +x /data/local/tmp/net.sh && sh /data/local/tmp/net.sh'"
# ============================================================================

# --- KONFIGURACJA ---
VERSION="2.0"
SCRIPT_NAME="AUTOFIX ATV-NET PRO"
LOG_FILE="/data/local/tmp/network_fix.log"

# Kolory (dla Android shell - uproszczone)
C_RED="\033[31m"
C_GREEN="\033[32m"
C_YELLOW="\033[33m"
C_BLUE="\033[34m"
C_CYAN="\033[36m"
C_RESET="\033[0m"
C_BOLD="\033[1m"

# --- FUNKCJE POMOCNICZE ---

print_header() {
    echo ""
    echo "${C_BOLD}${C_CYAN}╔════════════════════════════════════════════════════════════╗${C_RESET}"
    echo "${C_BOLD}${C_CYAN}║  $1${C_RESET}"
    echo "${C_BOLD}${C_CYAN}╚════════════════════════════════════════════════════════════╝${C_RESET}"
    echo ""
}

print_success() {
    echo "${C_GREEN}[✓] $1${C_RESET}"
}

print_error() {
    echo "${C_RED}[✗] $1${C_RESET}"
}

print_warning() {
    echo "${C_YELLOW}[!] $1${C_RESET}"
}

print_info() {
    echo "${C_BLUE}[i] $1${C_RESET}"
}

log_action() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# --- DIAGNOSTYKA SIECI ---

check_connectivity() {
    print_header "DIAGNOSTYKA POŁĄCZENIA INTERNETOWEGO"
    
    # Test 1: Ping Google DNS
    print_info "Test 1/4: Ping Google DNS (8.8.8.8)..."
    if ping -c 3 -W 2 8.8.8.8 > /dev/null 2>&1; then
        print_success "Internet działa (IP routing OK)"
        INTERNET_OK=1
    else
        print_error "Brak połączenia IP (problem z routingiem lub Wi-Fi)"
        INTERNET_OK=0
    fi
    
    # Test 2: Ping Cloudflare DNS
    print_info "Test 2/4: Ping Cloudflare DNS (1.1.1.1)..."
    if ping -c 3 -W 2 1.1.1.1 > /dev/null 2>&1; then
        print_success "Alternatywny DNS dostępny"
        ALT_DNS_OK=1
    else
        print_error "Cloudflare DNS niedostępny"
        ALT_DNS_OK=0
    fi
    
    # Test 3: DNS Resolution
    print_info "Test 3/4: Resolucja DNS (google.com)..."
    if ping -c 2 -W 3 google.com > /dev/null 2>&1; then
        print_success "DNS działa poprawnie"
        DNS_OK=1
    else
        print_error "Błąd DNS (problem z resolucją nazw)"
        DNS_OK=0
    fi
    
    # Test 4: Captive Portal Check
    print_info "Test 4/4: Sprawdzanie Captive Portal..."
    CP_MODE=$(settings get global captive_portal_mode)
    if [ "$CP_MODE" = "0" ] || [ "$CP_MODE" = "1" ]; then
        print_success "Captive Portal skonfigurowany"
        CP_OK=1
    else
        print_warning "Captive Portal wymaga konfiguracji"
        CP_OK=0
    fi
    
    # Podsumowanie
    echo ""
    echo "${C_BOLD}PODSUMOWANIE DIAGNOSTYKI:${C_RESET}"
    echo "  Internet (IP): $([ $INTERNET_OK -eq 1 ] && echo '✓ OK' || echo '✗ BŁĄD')"
    echo "  Alt DNS:       $([ $ALT_DNS_OK -eq 1 ] && echo '✓ OK' || echo '✗ BŁĄD')"
    echo "  DNS Resolve:   $([ $DNS_OK -eq 1 ] && echo '✓ OK' || echo '✗ BŁĄD')"
    echo "  Captive Portal: $([ $CP_OK -eq 1 ] && echo '✓ OK' || echo '! UWAGA')"
    
    # Oblicz wynik (% sukcesu)
    TOTAL_TESTS=4
    PASSED_TESTS=$((INTERNET_OK + ALT_DNS_OK + DNS_OK + CP_OK))
    SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    
    echo ""
    if [ $SUCCESS_RATE -ge 75 ]; then
        print_success "Sieć działa w ${SUCCESS_RATE}% (${PASSED_TESTS}/${TOTAL_TESTS} testów OK)"
    elif [ $SUCCESS_RATE -ge 50 ]; then
        print_warning "Sieć częściowo działa w ${SUCCESS_RATE}% (${PASSED_TESTS}/${TOTAL_TESTS} testów OK)"
    else
        print_error "Sieć ma poważne problemy ${SUCCESS_RATE}% (${PASSED_TESTS}/${TOTAL_TESTS} testów OK)"
    fi
    
    log_action "Diagnostyka: Internet=$INTERNET_OK, DNS=$DNS_OK, Score=${SUCCESS_RATE}%"
}

# --- SERWERY DNS ---

show_dns_menu() {
    print_header "WYBIERZ SERWER DNS"
    
    echo "${C_BOLD}POLECANE DLA POLSKI:${C_RESET}"
    echo "  ${C_GREEN}1${C_RESET}) Cloudflare         - 1.1.1.1 / 1.0.0.1       ${C_CYAN}[NAJSZYBSZY]${C_RESET}"
    echo "  ${C_GREEN}2${C_RESET}) Google DNS         - 8.8.8.8 / 8.8.4.4       ${C_CYAN}[STABILNY]${C_RESET}"
    echo "  ${C_GREEN}3${C_RESET}) Quad9 Security     - 9.9.9.9 / 149.112.112.112 ${C_CYAN}[BEZPIECZNY]${C_RESET}"
    
    echo ""
    echo "${C_BOLD}BLOKADA REKLAM:${C_RESET}"
    echo "  ${C_YELLOW}4${C_RESET}) AdGuard DNS        - 94.140.14.14 / 94.140.15.15"
    echo "  ${C_YELLOW}5${C_RESET}) AdGuard Family     - 94.140.14.15 / 94.140.15.16 ${C_CYAN}[+ Kontrola rodzicielska]${C_RESET}"
    
    echo ""
    echo "${C_BOLD}PRYWATNOŚĆ:${C_RESET}"
    echo "  ${C_BLUE}6${C_RESET}) NextDNS             - 45.90.28.0 / 45.90.30.0"
    echo "  ${C_BLUE}7${C_RESET}) OpenDNS             - 208.67.222.222 / 208.67.220.220"
    
    echo ""
    echo "${C_BOLD}INNE:${C_RESET}"
    echo "  ${C_CYAN}8${C_RESET}) DNS.WATCH (Niemcy) - 84.200.69.80 / 84.200.70.40"
    echo "  ${C_YELLOW}9${C_RESET}) AUTO (wybór najszybszego)"
    echo "  ${C_RED}0${C_RESET}) Przywróć domyślne DNS"
    
    echo ""
    printf "Twój wybór [1-9, 0]: "
}

set_dns() {
    DNS_CHOICE=$1
    
    case $DNS_CHOICE in
        1)
            DNS_NAME="Cloudflare"
            DNS_PRIMARY="1.1.1.1"
            DNS_SECONDARY="1.0.0.1"
            DNS_PRIVATE="dns.cloudflare.com"
            ;;
        2)
            DNS_NAME="Google DNS"
            DNS_PRIMARY="8.8.8.8"
            DNS_SECONDARY="8.8.4.4"
            DNS_PRIVATE="dns.google"
            ;;
        3)
            DNS_NAME="Quad9 Security"
            DNS_PRIMARY="9.9.9.9"
            DNS_SECONDARY="149.112.112.112"
            DNS_PRIVATE="dns.quad9.net"
            ;;
        4)
            DNS_NAME="AdGuard DNS"
            DNS_PRIMARY="94.140.14.14"
            DNS_SECONDARY="94.140.15.15"
            DNS_PRIVATE="dns.adguard.com"
            ;;
        5)
            DNS_NAME="AdGuard Family"
            DNS_PRIMARY="94.140.14.15"
            DNS_SECONDARY="94.140.15.16"
            DNS_PRIVATE="dns-family.adguard.com"
            ;;
        6)
            DNS_NAME="NextDNS"
            DNS_PRIMARY="45.90.28.0"
            DNS_SECONDARY="45.90.30.0"
            DNS_PRIVATE="dns.nextdns.io"
            ;;
        7)
            DNS_NAME="OpenDNS"
            DNS_PRIMARY="208.67.222.222"
            DNS_SECONDARY="208.67.220.220"
            DNS_PRIVATE="dns.opendns.com"
            ;;
        8)
            DNS_NAME="DNS.WATCH"
            DNS_PRIMARY="84.200.69.80"
            DNS_SECONDARY="84.200.70.40"
            DNS_PRIVATE=""
            ;;
        9)
            print_info "Testowanie prędkości DNS..."
            auto_select_dns
            return
            ;;
        0)
            print_info "Przywracanie domyślnych DNS..."
            ndc resolver clearnetdns wlan0 > /dev/null 2>&1
            ndc resolver clearnetdns eth0 > /dev/null 2>&1
            settings delete global private_dns_mode
            settings delete global private_dns_specifier
            print_success "Przywrócono domyślne DNS"
            log_action "DNS: Przywrócono domyślne"
            return
            ;;
        *)
            print_error "Nieprawidłowy wybór!"
            return 1
            ;;
    esac
    
    print_header "KONFIGURACJA DNS: ${DNS_NAME}"
    
    # Ustawienie DNS dla Wi-Fi
    print_info "Konfiguracja DNS dla Wi-Fi..."
    ndc resolver setnetdns wlan0 "$DNS_PRIMARY $DNS_SECONDARY" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "Wi-Fi DNS: ${DNS_PRIMARY}, ${DNS_SECONDARY}"
    else
        print_warning "Nie można ustawić DNS dla Wi-Fi (możliwe, że nieaktywne)"
    fi
    
    # Ustawienie DNS dla Ethernet
    print_info "Konfiguracja DNS dla Ethernet..."
    ndc resolver setnetdns eth0 "$DNS_PRIMARY $DNS_SECONDARY" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "Ethernet DNS: ${DNS_PRIMARY}, ${DNS_SECONDARY}"
    else
        print_warning "Nie można ustawić DNS dla Ethernet (możliwe, że nieaktywne)"
    fi
    
    # Private DNS (Android 9+)
    if [ -n "$DNS_PRIVATE" ]; then
        print_info "Konfiguracja Private DNS (DNS-over-TLS)..."
        settings put global private_dns_mode hostname
        settings put global private_dns_specifier "$DNS_PRIVATE"
        print_success "Private DNS: ${DNS_PRIVATE}"
    fi
    
    # Czyszczenie cache DNS
    print_info "Czyszczenie cache DNS..."
    ndc resolver flushnet wlan0 > /dev/null 2>&1
    ndc resolver flushnet eth0 > /dev/null 2>&1
    
    # Test DNS
    echo ""
    print_info "Testowanie DNS (google.com)..."
    sleep 1
    if ping -c 2 -W 3 google.com > /dev/null 2>&1; then
        print_success "DNS działa poprawnie!"
    else
        print_error "DNS nie działa - sprawdź połączenie"
    fi
    
    log_action "DNS: Ustawiono ${DNS_NAME} (${DNS_PRIMARY})"
}

auto_select_dns() {
    print_header "AUTOMATYCZNY WYBÓR NAJSZYBSZEGO DNS"
    
    # Lista DNS do testowania
    DNS_SERVERS="1.1.1.1 8.8.8.8 9.9.9.9 94.140.14.14"
    FASTEST_DNS=""
    FASTEST_TIME=9999
    
    for DNS in $DNS_SERVERS; do
        print_info "Testowanie ${DNS}..."
        
        # Pomiar czasu ping (3 pakiety)
        START_TIME=$(date +%s%N)
        ping -c 3 -W 2 "$DNS" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            END_TIME=$(date +%s%N)
            ELAPSED=$((($END_TIME - $START_TIME) / 1000000)) # ms
            
            echo "  → Czas odpowiedzi: ${ELAPSED}ms"
            
            if [ $ELAPSED -lt $FASTEST_TIME ]; then
                FASTEST_TIME=$ELAPSED
                FASTEST_DNS=$DNS
            fi
        else
            echo "  → Niedostępny"
        fi
    done
    
    if [ -n "$FASTEST_DNS" ]; then
        echo ""
        print_success "Najszybszy DNS: ${FASTEST_DNS} (${FASTEST_TIME}ms)"
        
        # Mapowanie na wybór
        case $FASTEST_DNS in
            "1.1.1.1") set_dns 1 ;;
            "8.8.8.8") set_dns 2 ;;
            "9.9.9.9") set_dns 3 ;;
            "94.140.14.14") set_dns 4 ;;
        esac
    else
        print_error "Nie można znaleźć działającego DNS!"
    fi
}

# --- SYNCHRONIZACJA CZASU ---

sync_time() {
    print_header "SYNCHRONIZACJA CZASU NTP"
    
    print_info "Włączanie automatycznej synchronizacji czasu..."
    settings put global auto_time 1
    settings put global auto_time_zone 1
    
    print_info "Konfiguracja serwera NTP (time.google.com)..."
    settings put global ntp_server time.google.com
    
    # Force sync (wymaga root, ale spróbujemy)
    print_info "Wymuszanie synchronizacji..."
    am broadcast -a android.intent.action.TIME_SET > /dev/null 2>&1
    
    # Pokaż aktualny czas
    CURRENT_TIME=$(date '+%Y-%m-%d %H:%M:%S')
    print_success "Aktualny czas: ${CURRENT_TIME}"
    
    log_action "NTP: Synchronizacja czasu z time.google.com"
}

# --- CAPTIVE PORTAL ---

fix_captive_portal() {
    print_header "NAPRAWA CAPTIVE PORTAL"
    
    print_info "Włączanie detekcji Captive Portal..."
    settings put global captive_portal_detection_enabled 1
    
    print_info "Tryb Captive Portal: Auto"
    settings put global captive_portal_mode 0
    
    # URLs dla Captive Portal (Google)
    print_info "Konfiguracja URL weryfikacji..."
    settings put global captive_portal_http_url http://connectivitycheck.gstatic.com/generate_204
    settings put global captive_portal_https_url https://www.google.com/generate_204
    
    print_success "Captive Portal skonfigurowany"
    
    log_action "Captive Portal: Skonfigurowano"
}

# --- RESTART INTERFEJSÓW ---

restart_network() {
    print_header "RESTART INTERFEJSÓW SIECIOWYCH"
    
    # Wi-Fi
    print_info "Restartowanie Wi-Fi..."
    svc wifi disable
    sleep 2
    svc wifi enable
    sleep 3
    print_success "Wi-Fi zrestartowane"
    
    # Sprawdzenie statusu Wi-Fi
    WIFI_STATUS=$(dumpsys wifi | grep "mWifiEnabled" | head -1)
    if echo "$WIFI_STATUS" | grep -q "true"; then
        print_success "Wi-Fi aktywne"
    else
        print_warning "Wi-Fi nieaktywne - włącz ręcznie"
    fi
    
    log_action "Network: Restart Wi-Fi"
}

# --- CZYSZCZENIE CACHE ---

clear_network_cache() {
    print_header "CZYSZCZENIE CACHE SIECIOWEGO"
    
    print_info "Czyszczenie cache DNS..."
    ndc resolver flushdefaultif > /dev/null 2>&1
    ndc resolver flushif wlan0 > /dev/null 2>&1
    ndc resolver flushif eth0 > /dev/null 2>&1
    
    print_info "Czyszczenie cache Connectivity Service..."
    am force-stop com.android.server.connectivity > /dev/null 2>&1
    
    print_success "Cache wyczyszczony"
    
    log_action "Cache: Wyczyszczono DNS i Connectivity"
}

# --- AUTO FIX ---

auto_fix() {
    print_header "AUTOMATYCZNA NAPRAWA SIECI"
    
    print_info "Uruchamiam pełną procedurę naprawczą..."
    echo ""
    
    # Krok 1: Synchronizacja czasu
    sync_time
    sleep 1
    
    # Krok 2: DNS (Cloudflare - najszybszy)
    set_dns 1
    sleep 1
    
    # Krok 3: Captive Portal
    fix_captive_portal
    sleep 1
    
    # Krok 4: Cache
    clear_network_cache
    sleep 1
    
    # Krok 5: Restart sieci
    restart_network
    sleep 2
    
    # Krok 6: Weryfikacja
    check_connectivity
    
    print_success "Auto-fix zakończony!"
    log_action "Auto-fix: Zakończono"
}

# --- MENU GŁÓWNE ---

show_main_menu() {
    clear
    print_header "${SCRIPT_NAME} v${VERSION}"
    
    echo "${C_BOLD}OPCJE:${C_RESET}"
    echo ""
    echo "  ${C_GREEN}1${C_RESET}) ${C_BOLD}Diagnostyka sieci${C_RESET} (sprawdź połączenie)"
    echo "  ${C_GREEN}2${C_RESET}) ${C_BOLD}Zmień DNS${C_RESET} (wybierz z 8 serwerów)"
    echo "  ${C_GREEN}3${C_RESET}) ${C_BOLD}Synchronizacja czasu${C_RESET} (NTP)"
    echo "  ${C_GREEN}4${C_RESET}) ${C_BOLD}Naprawa Captive Portal${C_RESET}"
    echo "  ${C_GREEN}5${C_RESET}) ${C_BOLD}Restart sieci${C_RESET} (Wi-Fi/Ethernet)"
    echo "  ${C_GREEN}6${C_RESET}) ${C_BOLD}Czyszczenie cache${C_RESET}"
    echo ""
    echo "  ${C_CYAN}9${C_RESET}) ${C_BOLD}AUTO-FIX${C_RESET} ${C_YELLOW}[ZALECANE - Napraw wszystko]${C_RESET}"
    echo ""
    echo "  ${C_RED}0${C_RESET}) Wyjście"
    echo ""
    printf "Twój wybór: "
}

# --- MAIN ---

main() {
    # Sprawdź czy skrypt jest uruchamiany jako root/system
    CURRENT_USER=$(whoami)
    if [ "$CURRENT_USER" != "root" ] && [ "$CURRENT_USER" != "shell" ]; then
        print_warning "Uruchamianie jako: ${CURRENT_USER}"
        print_warning "Niektóre funkcje mogą wymagać uprawnień root"
    fi
    
    # Utwórz log
    log_action "=== Start: ${SCRIPT_NAME} v${VERSION} ==="
    
    # Jeśli podano argument --auto, uruchom auto-fix
    if [ "$1" = "--auto" ] || [ "$1" = "-a" ]; then
        auto_fix
        exit 0
    fi
    
    # Jeśli podano argument --dns, uruchom menu DNS
    if [ "$1" = "--dns" ] || [ "$1" = "-d" ]; then
        show_dns_menu
        read DNS_CHOICE
        set_dns "$DNS_CHOICE"
        exit 0
    fi
    
    # Jeśli podano argument --check, uruchom diagnostykę
    if [ "$1" = "--check" ] || [ "$1" = "-c" ]; then
        check_connectivity
        exit 0
    fi
    
    # Menu interaktywne
    while true; do
        show_main_menu
        read CHOICE
        
        case $CHOICE in
            1)
                check_connectivity
                ;;
            2)
                show_dns_menu
                read DNS_CHOICE
                set_dns "$DNS_CHOICE"
                ;;
            3)
                sync_time
                ;;
            4)
                fix_captive_portal
                ;;
            5)
                restart_network
                ;;
            6)
                clear_network_cache
                ;;
            9)
                auto_fix
                ;;
            0)
                print_info "Do zobaczenia!"
                log_action "=== Koniec ==="
                exit 0
                ;;
            *)
                print_error "Nieprawidłowy wybór!"
                ;;
        esac
        
        echo ""
        printf "${C_CYAN}Naciśnij Enter aby kontynuować...${C_RESET}"
        read
    done
}

# Uruchom main
main "$@"
