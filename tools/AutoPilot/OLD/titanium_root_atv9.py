#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  QUANTUM ORCHESTRATOR v2.0 — ROOT & SHIZUKU DEPLOYMENT ENGINE                ║
║  Targets: Sagemcom DCTIW362P | Android 9 Pie | ARMv7 Cortex-A15              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import subprocess
import sys
import time
import urllib.request

class Style:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    HEADER = '\033[95m'

def log(tag, msg, style=Style.RESET):
    print(f"{style}[{tag}]{Style.RESET} {msg}")

class QuantumOrchestrator:
    def __init__(self, target_ip="192.168.1.186"):
        self.target_ip = target_ip
        self.temp_dir = "./.quantum_cache"
        self.shizuku_url = "https://github.com/RikkaApps/Shizuku/releases/latest/download/shizuku-v13.5.4.r1066.1b55023-release.apk"
        self.kingroot_url = "https://archive.org/download/king-root-5-4-0/KingRoot_5-4-0.apk"
        
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def shell(self, cmd):
        full_cmd = f"adb -s {self.target_ip}:5555 {cmd}"
        try:
            res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
            return res.stdout.strip()
        except Exception: return None

    def download_file(self, url, name):
        path = os.path.join(self.temp_dir, name)
        if not os.path.exists(path):
            log("DOWNLOAD", f"Pobieranie {name}...", Style.CYAN)
            urllib.request.urlretrieve(url, path)
            log("DOWNLOAD", "Zakończono.", Style.GREEN)
        return path

    def adb_connect(self):
        log("ADB", f"Próba połączenia z {self.target_ip}...", Style.CYAN)
        subprocess.run(f"adb connect {self.target_ip}", shell=True)
        time.sleep(1)
        state = self.shell("getprop ro.product.model")
        if state:
            log("ADB", f"Połączono z: {state}", Style.GREEN)
            return True
        log("ADB", "Połączenie nieudane.", Style.RED)
        return False

    def try_adb_root(self):
        log("EXPLOIT", "Próba wymuszenia 'adb root'...", Style.YELLOW)
        res = subprocess.getoutput(f"adb -s {self.target_ip}:5555 root")
        if "adbd cannot run as root in production builds" in res:
            log("EXPLOIT", "Build produkcyjny - adb root zablokowany.", Style.RED)
            return False
        log("EXPLOIT", "SUKCES! Daemon adbd działa jako root.", Style.GREEN)
        return True

    def deploy_shizuku(self):
        log("SHIZUKU", "Inicjowanie bezdotykowej instalacji Shizuku...", Style.CYAN)
        apk = self.download_file(self.shizuku_url, "shizuku.apk")
        self.shell(f"install {apk}")
        
        # Ciche uruchomienie demona przez app_process
        pkg_path = self.shell("pm path moe.shizuku.privileged.api").replace("package:", "").strip()
        if pkg_path:
            log("SHIZUKU", "Uruchamianie demona systemowego...", Style.CYAN)
            start_cmd = f"shell export CLASSPATH={pkg_path}; exec app_process /system/bin moe.shizuku.manager.shell.Shell &"
            self.shell(start_cmd)
            log("SHIZUKU", "Demon wysłany do tła. Sprawdź aplikację na TV.", Style.GREEN)

    def deploy_kingroot(self):
        log("ROOT", "Próba bezpiecznego rootowania (KingRoot Hybrid)...", Style.YELLOW)
        apk = self.download_file(self.kingroot_url, "kingroot.apk")
        self.shell(f"install -g {apk}") # -g nadaje wszystkie uprawnienia
        
        log("ROOT", "Uruchamianie procesu rootowania...", Style.CYAN)
        # Uruchomienie głównej aktywności KingRoot
        self.shell("shell am start -n com.kingroot.kinguser/com.kingroot.kinguser.activity.KUMainActivity")
        log("ROOT", "KingRoot uruchomiony. Interakcja wymagana na ekranie TV.", Style.YELLOW)

    def run_scripts(self):
        scripts = [f for f in os.listdir('.') if f.endswith('.sh')]
        if not scripts:
            log("FILES", "Brak skryptów .sh do wdrożenia.", Style.YELLOW)
            return

        for s in scripts:
            log("DEPLOY", f"Wysyłanie {s}...", Style.CYAN)
            subprocess.run(f"adb -s {self.target_ip}:5555 push {s} /data/local/tmp/", shell=True)
            self.shell(f"shell chmod +x /data/local/tmp/{s}")
            log("EXEC", f"Uruchamianie {s}...", Style.GREEN)
            os.system(f"adb -s {self.target_ip}:5555 shell /data/local/tmp/{s}")

    def menu(self):
        while True:
            os.system('clear' if os.name == 'posix' else 'cls')
            print(f"{Style.HEADER}{Style.BOLD}=== QUANTUM ORCHESTRATOR v2.0 ==={Style.RESET}")
            print(f" Cel: {self.target_ip}\n")
            print(f" [{Style.GREEN}1{Style.RESET}] Pełne wdrożenie (Shizuku + Skrypty)")
            print(f" [{Style.GREEN}2{Style.RESET}] Próba ROOT (adb root + KingRoot)")
            print(f" [{Style.GREEN}3{Style.RESET}] Tylko wyślij i uruchom skrypty .sh")
            print(f" [{Style.GREEN}C{Style.RESET}] Zmień IP")
            print(f" [{Style.GREEN}Q{Style.RESET}] Wyjście")
            
            choice = input(f"\n{Style.BOLD}Wybierz protokół: {Style.RESET}").lower()
            
            if choice == 'q': break
            if not self.adb_connect():
                input("Naciśnij Enter, aby spróbować ponownie...")
                continue

            if choice == '1':
                self.deploy_shizuku()
                self.run_scripts()
            elif choice == '2':
                if not self.try_adb_root():
                    self.deploy_kingroot()
            elif choice == '3':
                self.run_scripts()
            elif choice == 'c':
                self.target_ip = input("Podaj nowe IP: ")
            
            input("\nOperacja zakończona. Enter...")

if __name__ == "__main__":
    orchestrator = QuantumOrchestrator()
    orchestrator.menu()
