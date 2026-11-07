#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import time
import argparse
import datetime

# ==============================================================================
# AEGIS SENTINEL - Sagemcom DCTIW362p (Broadcom BCM72xx / Android TV 9)
# Auto-Diagnostyka i Pętla Utrzymania Wydajności
# ==============================================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

GOLDEN_STATE = {
    "props": {
        # Zablokowanie zbugowanego tunelowania na urządzeniach Broadcom
        "media.tunneled-playback.enable": "false",
        # Wymuszenie priorytetu sprzętowego dla miniatur i wideo
        "media.stagefright.thumbnail.prefer_hw_codecs": "1",
        "debug.stagefright.ccodec": "4",
        # Wyłączenie głębokiego bufora psującego synchronizację Cast/Audio
        "media.stagefright.audio.deepbuffer": "false"
    },
    "settings_global": {
        # Wyłączenie wadliwego trybu surround (Rozwiązuje błąd Audio-22/38)
        "encoded_surround_output": "0",
        # Drastyczne ograniczenie procesów w tle (Lekarstwo na wycieki RAM Sagemcom)
        "background_process_limit": "2",
        # Zablokowanie wybudzania/działania aplikacji gdy urządzenie śpi
        "stay_on_while_plugged_in": "0",
        # Skrócenie czasów animacji dla responsywności (0.0 to natychmiastowe przejście)
        "window_animation_scale": "0.0",
        "transition_animation_scale": "0.0",
        "animator_duration_scale": "0.0"
    },
    "bloatware": [
        "com.google.android.katniss",
        "com.sagemcom.stb.setupwizard",
        "com.google.android.speech.pumpkin",
        "com.amazon.amazonvideo.livingroom"
    ]
}

class AdbManager:
    def __init__(self, target_device=None):
        self.device = target_device
        
    def execute(self, command, timeout=10):
        """Wykonywanie komend ADB z zabezpieczeniem czasowym (timeout) i obsługą błędów"""
        base_cmd = ["adb"]
        if self.device:
            base_cmd.extend(["-s", self.device])
        base_cmd.extend(["shell"] + command.split())
        
        try:
            result = subprocess.run(base_cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "ERROR_TIMEOUT"
        except Exception as e:
            return f"ERROR_{str(e)}"

    def connect(self):
        """Łączenie z urządzeniem, jeśli zostało podane po IP"""
        if self.device and ":" in self.device:
            print(f"{Colors.YELLOW}[*] Nawiązywanie połączenia z {self.device}...{Colors.RESET}")
            subprocess.run(["adb", "connect", self.device], capture_output=True)
        
        # Test połączenia
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        if self.device and self.device not in res.stdout:
            print(f"{Colors.RED}[!] Urządzenie {self.device} jest niedostępne.{Colors.RESET}")
            return False
        elif "device\n" not in res.stdout and "device\t" not in res.stdout:
            print(f"{Colors.RED}[!] Brak podłączonych urządzeń ADB.{Colors.RESET}")
            return False
        
        print(f"{Colors.GREEN}[✓] Połączenie ADB ustabilizowane.{Colors.RESET}")
        return True

class DiagnosticEngine:
    def __init__(self, adb):
        self.adb = adb

    def run_health_check(self, auto_heal=False):
        """Weryfikuje każdy kluczowy parametr z ustalonym GOLDEN_STATE"""
        print(f"\n{Colors.CYAN}=== ROZPOCZYNANIE SAMODIAGNOSTYKI SYSTEMU ==={Colors.RESET}")
        anomalies_found = 0
        
        # 1. Sprawdzanie Properties (build.prop / getprop)
        print(f"{Colors.BOLD}\n[ Weryfikacja silnika multimediów (Properties) ]{Colors.RESET}")
        for prop, expected in GOLDEN_STATE["props"].items():
            current = self.adb.execute(f"getprop {prop}")
            if current != expected:
                print(f"{Colors.RED}[BŁĄD] {prop} = {current} (Oczekiwano: {expected}){Colors.RESET}")
                anomalies_found += 1
                if auto_heal:
                    self.adb.execute(f"setprop {prop} {expected}")
                    print(f"{Colors.GREEN}       -> Naprawiono w locie!{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}[OK] {prop} = {expected}{Colors.RESET}")

        # 2. Sprawdzanie Ustawień Globalnych (Settings)
        print(f"{Colors.BOLD}\n[ Weryfikacja ustawień UI i RAM (Global Settings) ]{Colors.RESET}")
        for setting, expected in GOLDEN_STATE["settings_global"].items():
            current = self.adb.execute(f"settings get global {setting}")
            if current != expected:
                print(f"{Colors.RED}[BŁĄD] {setting} = {current} (Oczekiwano: {expected}){Colors.RESET}")
                anomalies_found += 1
                if auto_heal:
                    self.adb.execute(f"settings put global {setting} {expected}")
                    print(f"{Colors.GREEN}       -> Zoptymalizowano!{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}[OK] {setting} = {expected}{Colors.RESET}")

        # 3. Sprawdzanie Bloatware
        print(f"{Colors.BOLD}\n[ Weryfikacja zamrożonych procesów w tle ]{Colors.RESET}")
        disabled_packages = self.adb.execute("pm list packages -d")
        for app in GOLDEN_STATE["bloatware"]:
            if app not in disabled_packages:
                # Oznacza, że aplikacja nadal jest aktywna
                print(f"{Colors.RED}[ZAGROŻENIE] Zidentyfikowano działający bloatware: {app}{Colors.RESET}")
                anomalies_found += 1
                if auto_heal:
                    self.adb.execute(f"pm disable-user --user 0 {app}")
                    print(f"{Colors.GREEN}       -> Aplikacja zamrożona na poziomie systemu!{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}[OK] {app} - zablokowana.{Colors.RESET}")

        return anomalies_found

class AegisDaemon:
    def __init__(self, adb, diag):
        self.adb = adb
        self.diag = diag
        self.running = False
        self.ram_threshold_mb = 120 # Minimalna wolna pamięć przed agresywnym zrzutem

    def get_free_ram(self):
        """Pobiera ilość dostępnej pamięci RAM bezpośrednio z kernela dla szybkości"""
        meminfo = self.adb.execute("cat /proc/meminfo")
        if "ERROR" in meminfo: return -1
        
        try:
            for line in meminfo.splitlines():
                if line.startswith("MemAvailable:"):
                    # Wartość jest w kB (np. MemAvailable:   152432 kB)
                    parts = line.split()
                    kb = int(parts[1])
                    return kb // 1024
        except Exception:
            pass
        return -1

    def start_loop(self, interval_seconds=15):
        self.running = True
        print(f"\n{Colors.HEADER}===================================================={Colors.RESET}")
        print(f"{Colors.HEADER}🛡️  AEGIS DAEMON URUCHOMIONY W TRYBIE PODTRZYMANIA 🛡️{Colors.RESET}")
        print(f"{Colors.HEADER}===================================================={Colors.RESET}")
        print(f"{Colors.YELLOW}[*] Pętla kontrolna: {interval_seconds}s | Próg RAM: {self.ram_threshold_mb}MB{Colors.RESET}")
        print("[*] Zostaw ten proces włączony. Naciśnij Ctrl+C aby przerwać.\n")

        check_cycle = 0

        while self.running:
            try:
                now = datetime.datetime.now().strftime("%H:%M:%S")
                free_ram = self.get_free_ram()
                
                # Zabezpieczenie przed przerwaniem połączenia ADB
                if free_ram == -1:
                    print(f"[{now}] {Colors.RED}Błąd komunikacji ADB. Próba wznowienia...{Colors.RESET}")
                    self.adb.connect()
                    time.sleep(5)
                    continue

                status_msg = f"[{now}] Stan pamięci RAM: "
                
                # REAKCJA NA BRAK PAMIĘCI (OOM GUARD)
                if free_ram < self.ram_threshold_mb:
                    print(status_msg + f"{Colors.RED}{free_ram} MB (KRYTYCZNY){Colors.RESET}")
                    print(f"[{now}] {Colors.YELLOW}>> Inicjowanie zrzutu śmieci (Trim Caches)...{Colors.RESET}")
                    
                    # Agresywnie uwalniamy RAM z cachowanych procesów
                    self.adb.execute("pm trim-caches 999999M")
                    # Czyszczenie przestrzeni wymiany aplikacji (Dalvik)
                    self.adb.execute("am kill-all") 
                    
                    new_ram = self.get_free_ram()
                    print(f"[{now}] {Colors.GREEN}>> Zwolniono pamięć! Obecnie: {new_ram} MB{Colors.RESET}")
                else:
                    print(status_msg + f"{Colors.GREEN}{free_ram} MB (Stabilny){Colors.RESET}")

                # Co 20 cykli (~5 minut) wykonaj pełną samodiagnostykę i autonaprawę w tle
                if check_cycle >= 20:
                    print(f"[{now}] {Colors.CYAN}>> Wykonywanie rutynowej diagnostyki systemu w tle...{Colors.RESET}")
                    anomalies = self.diag.run_health_check(auto_heal=True)
                    if anomalies > 0:
                        print(f"[{now}] {Colors.YELLOW}>> Aegis naprawił {anomalies} usterki/przywrócone wartości.{Colors.RESET}")
                    else:
                        print(f"[{now}] {Colors.GREEN}>> Środowisko czyste. Nie wykryto anomalii.{Colors.RESET}")
                    check_cycle = 0

                check_cycle += 1
                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}[*] Przerywanie pracy demona utrzymaniowego. System nie jest już chroniony na żywo.{Colors.RESET}")
                self.running = False
            except Exception as e:
                print(f"[{now}] {Colors.RED}Nieoczekiwany błąd demona: {e}{Colors.RESET}")
                time.sleep(5)

def main():
    parser = argparse.ArgumentParser(description="Aegis Sentinel - Android TV Performance Guard")
    parser.add_argument("--device", help="IP urządzenia (np. 192.168.1.5:5555) lub zostaw puste dla USB", default=None)
    parser.add_argument("--daemon", action="store_true", help="Uruchom niekończącą się pętlę monitorującą (Aegis)")
    parser.add_argument("--heal", action="store_true", help="Automatycznie napraw znalezione usterki podczas testu")
    args = parser.parse_args()

    # Ekran powitalny
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Colors.BLUE}{Colors.BOLD}")
    print("      ___  ___________ _________    ")
    print("     / _ \\/ __/ ___/ //_/ __/ _ |   ")
    print("    / __ / _// (_ / ,< /\\ \\/ __ |   ")
    print("   /_/ |_/___/\\___/_/|_|___/_/ |_|  ")
    print(f"   Aegis Sentinel - Broadcom ATV9 Fixer{Colors.RESET}\n")

    adb = AdbManager(args.device)
    if not adb.connect():
        sys.exit(1)

    diag = DiagnosticEngine(adb)

    if args.daemon:
        # Tryb ciągły
        anomalies = diag.run_health_check(auto_heal=True)
        if anomalies > 0:
             print(f"\n{Colors.GREEN}[✓] System został wstępnie naprawiony. Uruchamianie ochrony...{Colors.RESET}")
        daemon = AegisDaemon(adb, diag)
        daemon.start_loop(interval_seconds=15)
    else:
        # Tryb jednorazowy
        anomalies = diag.run_health_check(auto_heal=args.heal)
        
        print(f"\n{Colors.BOLD}--- WYNIKI DIAGNOSTYKI ---{Colors.RESET}")
        if anomalies == 0:
            print(f"{Colors.GREEN}[✓] Urządzenie Sagemcom jest w idealnym stanie optymalizacyjnym.{Colors.RESET}")
        else:
            if args.heal:
                print(f"{Colors.GREEN}[✓] Znaleziono i automatycznie naprawiono {anomalies} problemów.{Colors.RESET}")
            else:
                print(f"{Colors.RED}[!] Znaleziono {anomalies} odchyleń od normy.{Colors.RESET}")
                print(f"{Colors.YELLOW}Uruchom skrypt z flagą --heal, aby je automatycznie naprawić.{Colors.RESET}")
        
        if not args.daemon:
            print(f"\n{Colors.CYAN}Wskazówka: Aby zapobiec powrotom problemów (np. po restarcie lub wybudzeniu),{Colors.RESET}")
            print(f"{Colors.CYAN}uruchom narzędzie z flagą: python {sys.argv[0]} --daemon{Colors.RESET}")

if __name__ == "__main__":
    main()