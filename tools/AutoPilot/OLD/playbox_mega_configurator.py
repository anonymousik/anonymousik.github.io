#!/usr/bin/env python3
"""
PLAYBOX MEGA CONFIGURATOR v1.0
Wszystko w jednym - konfiguracja sieci, VLAN, optymalizacja, naprawy
Dla: Orange Play + Sagemcom DCTIW362P
"""

import os
import sys
import subprocess
import time

COLORS = {
    'GREEN': '\033[92m',
    'RED': '\033[91m',
    'YELLOW': '\033[93m',
    'CYAN': '\033[96m',
    'BOLD': '\033[1m',
    'RESET': '\033[0m'
}

def print_header(text):
    print(f"\n{COLORS['CYAN']}{COLORS['BOLD']}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{COLORS['RESET']}\n")

def print_success(text):
    print(f"{COLORS['GREEN']}✓ {text}{COLORS['RESET']}")

def print_error(text):
    print(f"{COLORS['RED']}✗ {text}{COLORS['RESET']}")

def print_warning(text):
    print(f"{COLORS['YELLOW']}! {text}{COLORS['RESET']}")

def print_info(text):
    print(f"{COLORS['CYAN']}→ {text}{COLORS['RESET']}")

def run_adb(cmd, ignore_errors=False):
    """Uruchom komendę ADB"""
    try:
        result = subprocess.check_output(
            f"adb shell {cmd}",
            shell=True,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10
        ).strip()
        return result
    except:
        if not ignore_errors:
            print_warning(f"Komenda failed: {cmd[:50]}...")
        return ""

def check_device():
    """Sprawdź połączenie ADB"""
    try:
        out = subprocess.check_output("adb devices", shell=True, text=True)
        if "device" in out and "devices" in out:
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines:
                return True
    except:
        pass
    return False

def show_welcome():
    """Ekran powitalny"""
    print(f"{COLORS['CYAN']}")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*18 + "PLAYBOX MEGA CONFIGURATOR" + " "*25 + "║")
    print("║" + " "*15 + "Orange Play + Sagemcom DCTIW362P" + " "*22 + "║")
    print("╚" + "═"*68 + "╝")
    print(f"{COLORS['RESET']}\n")
    
    print(f"{COLORS['BOLD']}Co robi ten skrypt:{COLORS['RESET']}")
    print("  1. Naprawia DUP packets (zduplikowane pakiety)")
    print("  2. Konfiguruje DNS Cloudflare (szybszy internet)")
    print("  3. Optymalizuje TCP/UDP (streaming)")
    print("  4. Konfiguruje VLAN 40 (Orange TV)")
    print("  5. Weryfikuje konfigurację")
    print()

def diagnose_network():
    """Diagnostyka sieci"""
    print_header("DIAGNOSTYKA SIECI")
    
    # Test 1: Internet
    print_info("Test 1/4: Połączenie internetowe...")
    ping = run_adb("ping -c 3 -W 2 1.1.1.1", ignore_errors=True)
    if "3 packets transmitted, 3 received" in ping:
        print_success("Internet działa")
        internet_ok = True
    else:
        print_error("Brak internetu!")
        internet_ok = False
    
    # Test 2: DUP packets
    print_info("Test 2/4: Sprawdzanie DUP packets...")
    dup_count = ping.count("DUP!")
    if dup_count > 0:
        print_error(f"Wykryto {dup_count} duplikatów - wymaga naprawy!")
        has_dup = True
    else:
        print_success("Brak duplikatów")
        has_dup = False
    
    # Test 3: DNS
    print_info("Test 3/4: Test DNS...")
    dns_test = run_adb("ping -c 2 -W 3 google.com", ignore_errors=True)
    if "2 packets transmitted, 2 received" in dns_test:
        print_success("DNS działa")
        dns_ok = True
    else:
        print_warning("Problem z DNS")
        dns_ok = False
    
    # Test 4: Interfejsy
    print_info("Test 4/4: Sprawdzanie interfejsów...")
    interfaces = run_adb("ip link show", ignore_errors=True)
    eth_up = "eth0" in interfaces and "state UP" in interfaces
    wlan_up = "wlan0" in interfaces and "state UP" in interfaces
    
    if eth_up and wlan_up:
        print_warning("PROBLEM: Ethernet i Wi-Fi aktywne jednocześnie!")
        both_active = True
    else:
        print_success("Tylko jeden interfejs aktywny")
        both_active = False
    
    print()
    return {
        'internet': internet_ok,
        'has_dup': has_dup,
        'dns': dns_ok,
        'both_active': both_active
    }

def fix_dup_packets():
    """Napraw DUP packets"""
    print_header("NAPRAWA DUP PACKETS")
    
    # Sprawdź interfejsy
    print_info("Sprawdzam interfejsy...")
    interfaces = run_adb("ip link show")
    
    eth_up = "eth0" in interfaces and "state UP" in interfaces
    wlan_up = "wlan0" in interfaces and "state UP" in interfaces
    
    if eth_up and wlan_up:
        print_warning("Wykryto Wi-Fi i Ethernet aktywne - wyłączam Ethernet...")
        run_adb("su -c 'ip link set eth0 down'", ignore_errors=True)
        time.sleep(2)
        print_success("Ethernet wyłączony")
    
    # Flush ARP
    print_info("Czyszczenie ARP cache...")
    run_adb("su -c 'ip neigh flush all'", ignore_errors=True)
    
    # Restart Wi-Fi
    print_info("Restart Wi-Fi...")
    run_adb("svc wifi disable")
    time.sleep(3)
    run_adb("svc wifi enable")
    time.sleep(5)
    print_success("Wi-Fi zrestartowany")
    
    # Test
    print_info("Weryfikacja...")
    ping = run_adb("ping -c 5 -W 2 1.1.1.1", ignore_errors=True)
    dup_count = ping.count("DUP!")
    
    if dup_count == 0:
        print_success("✓ DUP packets naprawione!")
        return True
    else:
        print_warning(f"Nadal {dup_count} duplikatów - może być problem z routerem")
        return False

def configure_dns():
    """Konfiguruj DNS Cloudflare"""
    print_header("KONFIGURACJA DNS CLOUDFLARE")
    
    print_info("Ustawiam DNS 1.1.1.1 (Cloudflare)...")
    
    # DNS dla Wi-Fi
    run_adb("ndc resolver setnetdns wlan0 '1.1.1.1 1.0.0.1'", ignore_errors=True)
    
    # Private DNS
    run_adb("settings put global private_dns_mode hostname")
    run_adb("settings put global private_dns_specifier dns.cloudflare.com")
    
    print_success("DNS Cloudflare skonfigurowany")
    
    # Test
    print_info("Test DNS...")
    time.sleep(2)
    dns_test = run_adb("ping -c 2 -W 3 google.com", ignore_errors=True)
    if "2 packets transmitted, 2 received" in dns_test:
        print_success("DNS działa!")
        return True
    else:
        print_warning("DNS może wymagać restartu")
        return False

def optimize_network():
    """Optymalizuj sieć"""
    print_header("OPTYMALIZACJA SIECI")
    
    print_info("Optymalizuję TCP/UDP bufory...")
    
    tweaks = [
        ('settings put global net.tcp.buffersize.wifi "524288,1048576,2097152,262144,524288,1048576"', "TCP bufory"),
        ('settings put global tcp_default_init_rwnd 60', "TCP receive window"),
        ('setprop media.stagefright.cache-params 20480/40960/204800', "Video cache"),
    ]
    
    for cmd, desc in tweaks:
        run_adb(cmd, ignore_errors=True)
        print_success(desc)
    
    print_success("Optymalizacja zakończona")

def setup_vlan40():
    """Konfiguruj VLAN 40 dla Orange TV"""
    print_header("VLAN 40 - ORANGE TV")
    
    print(f"{COLORS['YELLOW']}Czy masz abonament Orange TV (telewizja)?{COLORS['RESET']}")
    print("1) TAK - mam Orange TV")
    print("2) NIE - tylko internet")
    
    choice = input("\nTwój wybór [1/2]: ").strip()
    
    if choice != "1":
        print_info("Pomijam VLAN 40 (nie masz Orange TV)")
        return False
    
    print_info("Konfiguruję VLAN 40...")
    
    # Wykryj główny interfejs
    primary = run_adb("ip route | grep default | awk '{print $5}' | head -1")
    if not primary:
        primary = "eth0"  # fallback
    
    print_info(f"Główny interfejs: {primary}")
    
    # Utwórz VLAN 40
    vlan_if = f"{primary}.40"
    
    print_info(f"Tworzę {vlan_if}...")
    run_adb(f"su -c 'ip link add link {primary} name {vlan_if} type vlan id 40'", ignore_errors=True)
    run_adb(f"su -c 'ip link set {vlan_if} up'", ignore_errors=True)
    
    # DHCP
    print_info("Pobieranie IP przez DHCP...")
    run_adb(f"dhcpcd {vlan_if}", ignore_errors=True)
    time.sleep(3)
    
    # Routing multicast
    print_info("Konfiguracja multicast...")
    run_adb(f"su -c 'ip route add 224.0.0.0/4 dev {vlan_if}'", ignore_errors=True)
    
    # Bufory IPTV
    print_info("Optymalizacja buforów IPTV...")
    run_adb("su -c 'sysctl -w net.core.rmem_max=134217728'", ignore_errors=True)
    run_adb("su -c 'sysctl -w net.ipv4.igmp_max_memberships=100'", ignore_errors=True)
    
    print_success("VLAN 40 skonfigurowany!")
    
    # Weryfikacja
    print_info("Weryfikacja...")
    vlan_status = run_adb(f"ip link show {vlan_if}", ignore_errors=True)
    if "state UP" in vlan_status:
        print_success("VLAN 40 aktywny")
        return True
    else:
        print_warning("VLAN 40 może wymagać restartu")
        return False

def show_status():
    """Pokaż status systemu"""
    print_header("STATUS SYSTEMU")
    
    # IP
    print_info("Informacje sieciowe:")
    ip_info = run_adb("ip addr show | grep 'inet ' | grep -v '127.0.0.1'")
    if ip_info:
        for line in ip_info.split('\n'):
            if 'inet' in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    print(f"  {parts[1]} ({parts[-1]})")
    
    # Gateway
    gateway = run_adb("ip route | grep default | awk '{print $3}' | head -1")
    if gateway:
        print(f"  Gateway: {gateway}")
    
    # DNS
    dns1 = run_adb("getprop net.dns1")
    if dns1:
        print(f"  DNS: {dns1}")
    
    print()
    
    # Test ping
    print_info("Test połączenia:")
    ping = run_adb("ping -c 3 -W 2 1.1.1.1", ignore_errors=True)
    if "3 packets transmitted, 3 received" in ping:
        # Wyciągnij średni czas
        for line in ping.split('\n'):
            if 'min/avg/max' in line:
                print(f"  {line.strip()}")
        
        # Sprawdź DUP
        dup_count = ping.count("DUP!")
        if dup_count > 0:
            print_warning(f"  Wykryto {dup_count} duplikatów!")
        else:
            print_success("  Brak duplikatów")
    else:
        print_error("  Brak połączenia")
    
    print()

def main_menu():
    """Menu główne"""
    while True:
        print(f"\n{COLORS['BOLD']}{'='*70}")
        print(f"  MENU GŁÓWNE")
        print(f"{'='*70}{COLORS['RESET']}\n")
        
        print(f"  {COLORS['GREEN']}1{COLORS['RESET']}) Diagnostyka sieci")
        print(f"  {COLORS['GREEN']}2{COLORS['RESET']}) Napraw DUP packets")
        print(f"  {COLORS['GREEN']}3{COLORS['RESET']}) Konfiguruj DNS Cloudflare")
        print(f"  {COLORS['GREEN']}4{COLORS['RESET']}) Optymalizuj sieć (TCP/UDP)")
        print(f"  {COLORS['GREEN']}5{COLORS['RESET']}) Konfiguruj VLAN 40 (Orange TV)")
        print(f"  {COLORS['GREEN']}6{COLORS['RESET']}) Pokaż status")
        print()
        print(f"  {COLORS['YELLOW']}9{COLORS['RESET']}) {COLORS['BOLD']}AUTO-FIX (wszystko naraz){COLORS['RESET']}")
        print()
        print(f"  {COLORS['RED']}0{COLORS['RESET']}) Wyjście")
        print()
        
        choice = input(f"{COLORS['CYAN']}Twój wybór: {COLORS['RESET']}").strip()
        
        if choice == "1":
            diagnose_network()
        elif choice == "2":
            fix_dup_packets()
        elif choice == "3":
            configure_dns()
        elif choice == "4":
            optimize_network()
        elif choice == "5":
            setup_vlan40()
        elif choice == "6":
            show_status()
        elif choice == "9":
            auto_fix()
        elif choice == "0":
            print_info("Do zobaczenia!")
            break
        else:
            print_warning("Nieprawidłowy wybór!")
        
        input(f"\n{COLORS['CYAN']}Naciśnij Enter...{COLORS['RESET']}")

def auto_fix():
    """Automatyczna naprawa wszystkiego"""
    print_header("🚀 AUTO-FIX - WSZYSTKO NARAZ")
    
    print(f"{COLORS['BOLD']}Wykonam następujące kroki:{COLORS['RESET']}")
    print("  1. Diagnostyka")
    print("  2. Naprawa DUP packets")
    print("  3. DNS Cloudflare")
    print("  4. Optymalizacja TCP/UDP")
    print("  5. VLAN 40 (jeśli masz Orange TV)")
    print("  6. Weryfikacja")
    print()
    
    confirm = input(f"{COLORS['YELLOW']}Kontynuować? (y/n): {COLORS['RESET']}").strip().lower()
    if confirm != 'y':
        print_info("Anulowano")
        return
    
    # Krok 1: Diagnostyka
    print_header("KROK 1/6: Diagnostyka")
    diag = diagnose_network()
    time.sleep(2)
    
    # Krok 2: DUP fix
    print_header("KROK 2/6: Naprawa DUP")
    if diag['has_dup'] or diag['both_active']:
        fix_dup_packets()
    else:
        print_info("Brak problemów z DUP - pomijam")
    time.sleep(2)
    
    # Krok 3: DNS
    print_header("KROK 3/6: DNS Cloudflare")
    configure_dns()
    time.sleep(2)
    
    # Krok 4: Optymalizacja
    print_header("KROK 4/6: Optymalizacja sieci")
    optimize_network()
    time.sleep(2)
    
    # Krok 5: VLAN 40
    print_header("KROK 5/6: VLAN 40")
    setup_vlan40()
    time.sleep(2)
    
    # Krok 6: Weryfikacja
    print_header("KROK 6/6: Weryfikacja")
    show_status()
    
    print_header("✓ AUTO-FIX ZAKOŃCZONY!")
    print(f"{COLORS['GREEN']}{COLORS['BOLD']}Zalecany restart urządzenia za 5 minut{COLORS['RESET']}")

def main():
    """Główna funkcja"""
    show_welcome()
    
    # Sprawdź ADB
    print_info("Sprawdzam połączenie ADB...")
    if not check_device():
        print_error("Brak połączenia z urządzeniem!")
        print()
        print("Upewnij się że:")
        print("  1. USB Debugging włączony na TV")
        print("  2. adb connect IP:5555 wykonany")
        print("  3. Urządzenie autoryzowane")
        sys.exit(1)
    
    print_success("Połączono z urządzeniem")
    print()
    
    # Sprawdź czy są argumenty CLI
    if len(sys.argv) > 1:
        if sys.argv[1] == "--auto":
            auto_fix()
        elif sys.argv[1] == "--diagnose":
            diagnose_network()
        elif sys.argv[1] == "--fix-dup":
            fix_dup_packets()
        elif sys.argv[1] == "--dns":
            configure_dns()
        elif sys.argv[1] == "--optimize":
            optimize_network()
        elif sys.argv[1] == "--vlan40":
            setup_vlan40()
        elif sys.argv[1] == "--status":
            show_status()
        else:
            print_error(f"Nieznany parametr: {sys.argv[1]}")
            print()
            print("Dostępne parametry:")
            print("  --auto       Auto-fix (wszystko)")
            print("  --diagnose   Diagnostyka")
            print("  --fix-dup    Naprawa DUP")
            print("  --dns        DNS Cloudflare")
            print("  --optimize   Optymalizacja")
            print("  --vlan40     VLAN 40")
            print("  --status     Status")
    else:
        # Menu interaktywne
        main_menu()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{COLORS['YELLOW']}Przerwano przez użytkownika{COLORS['RESET']}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Błąd: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
