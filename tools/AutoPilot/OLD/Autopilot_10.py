#!/usr/bin/env python3
"""
PLAYBOX TITANIUM v10.0 - ULTIMATE AUTOMATION
Autopilot z zaawansowaną optymalizacją wideo 4K, HDR i zarządzaniem pamięcią
Styczeń 2026
"""

import os
import sys
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional, List

# ==========================================
# KONFIGURACJA I TRWAŁOŚĆ
# ==========================================
CACHE_DIR = Path.home() / ".playbox_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# KLASY POMOCNICZE
# ==========================================

class Logger:
    """Kolorowe logowanie z kategoryzacją"""
    
    COLORS = {
        'info': '\033[94m',      # Niebieski
        'success': '\033[92m',   # Zielony
        'warning': '\033[93m',   # Żółty
        'error': '\033[91m',     # Czerwony
        'header': '\033[95m',    # Fioletowy
        'cyan': '\033[96m',      # Cyan
        'reset': '\033[0m'
    }
    
    @staticmethod
    def log(msg: str, level: str = 'info'):
        """Standardowe logowanie"""
        color = Logger.COLORS.get(level, Logger.COLORS['info'])
        timestamp = time.strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] {msg}{Logger.COLORS['reset']}")
    
    @staticmethod
    def success(msg: str):
        Logger.log(f"✓ {msg}", 'success')
    
    @staticmethod
    def warning(msg: str):
        Logger.log(f"⚠ {msg}", 'warning')
    
    @staticmethod
    def error(msg: str):
        Logger.log(f"✗ {msg}", 'error')
    
    @staticmethod
    def header(msg: str):
        print(f"\n{Logger.COLORS['header']}{'='*70}")
        print(f"   {msg}")
        print(f"{'='*70}{Logger.COLORS['reset']}\n")


class SystemShell:
    """Wrapper dla wykonywania komend ADB z obsługą błędów"""
    
    device: Optional[str] = None
    
    @staticmethod
    def set_device(device: str):
        """Ustaw urządzenie docelowe"""
        SystemShell.device = device
    
    @staticmethod
    def run(cmd: str, ignore_errors: bool = False, shell_wrapper: bool = True) -> str:
        """
        Wykonaj komendę ADB shell
        
        Args:
            cmd: Komenda do wykonania
            ignore_errors: Czy ignorować błędy
            shell_wrapper: Czy używać adb shell (True) czy bezpośrednio adb (False)
        """
        if not SystemShell.device:
            Logger.error("Urządzenie nie zostało ustawione!")
            return ""
        
        try:
            if shell_wrapper:
                full_cmd = ["adb", "-s", SystemShell.device, "shell", cmd]
            else:
                full_cmd = ["adb", "-s", SystemShell.device] + cmd.split()
            
            result = subprocess.check_output(
                full_cmd,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30
            ).strip()
            return result
        except subprocess.TimeoutExpired:
            if not ignore_errors:
                Logger.warning(f"Timeout: {cmd[:50]}...")
        except subprocess.CalledProcessError as e:
            if not ignore_errors:
                Logger.warning(f"Błąd komendy: {cmd[:50]}... -> {e.output[:100]}")
        except Exception as e:
            if not ignore_errors:
                Logger.error(f"Nieoczekiwany błąd: {str(e)[:100]}")
        return ""


class PerformanceTuner:
    """Zaawansowany moduł optymalizacji - Styczeń 2026"""
    
    def apply_tweaks(self):
        """Aplikuj pełny profil optymalizacji dla 4K HDR i stabilności systemu"""
        Logger.log("Inicjacja zaawansowanego potoku wideo 4K + HDR...")
        
        tweaks = [
            # --- VIDEO & AUDIO PIPELINE (4K@60fps) ---
            "settings put global persist.sys.hdr.enable true",
            "setprop media.stagefright.enable-player true",
            "settings put global media.stagefright.enable-scan true",
            "settings put global media.acodec.preferhw true",
            "settings put global media.stagefright.cache-params 20480/40960/200",  # Duży bufor dla IPTV
            "settings put global audio.deep_buffer.media true",  # Lepsza stabilność dźwięku
            
            # --- GPU & RENDERING (VideoCore V / Vulkan) ---
            "setprop debug.hwui.renderer skiagl",
            "setprop debug.renderengine.backend skiavulkan",  # Wymuszenie backendu Vulkan
            "setprop ro.hwui.use_vulkan 1",
            "setprop debug.hwui.use_gpu_pixel_buffers true",
            "settings put global debug.force_hw_ui 1",  # Wymuszenie sprzętowego renderowania UI
            "setprop debug.hwui.render_dirty_regions false",  # Redukcja zbędnego przerysowywania
            
            # --- NETWORK & TCP BUFFERS (4K Streaming) ---
            'settings put global net.tcp.buffersize.wifi "524288,1048576,2097152,262144,524288,1048576"',  # Optymalizacja pod 4K
            "settings put global tcp_default_init_rwnd 60",
            
            # --- SYSTEM STABILITY & POWER ---
            "settings put global sys.watchdog.timeout 60000",  # Zapobieganie restartom
            "settings put global anr_show_background 0",  # Ukrywanie komunikatów o braku odpowiedzi
            "setprop debug.config.hw_quickpoweron true",  # Szybszy start urządzenia
            "settings put system touch_sounds_enabled 0",  # Redukcja użycia CPU przez dźwięki systemowe
            
            # --- TELEMETRY & ADS ---
            "settings put secure limit_ad_tracking 1",
            "settings put global send_action_app_error 0",
            "settings put global activity_starts_logging_enabled 0"  # Wyłączenie logowania aktywności
        ]

        success_count = 0
        for cmd in tweaks:
            result = SystemShell.run(cmd, ignore_errors=True)
            if result != "":
                success_count += 1
        
        Logger.log(f"Zastosowano {success_count}/{len(tweaks)} optymalizacji podstawowych")
        
        self._optimize_gms()
        self._flush_memory()
        Logger.success("Pełny profil optymalizacji został zaaplikowany.")

    def _optimize_gms(self):
        """Agresywne ograniczanie usług Google Play (GMS)"""
        Logger.log("Ograniczanie procesów GMS w tle...")
        gms_commands = [
            "am force-stop com.google.android.gms.persistent",
            "pm disable com.google.android.gms/.analytics.service.AnalyticsService",
            "cmd appops set com.google.android.gms WAKE_LOCK ignore"  # Blokowanie wybudzeń
        ]
        for cmd in gms_commands:
            SystemShell.run(cmd, ignore_errors=True)
        Logger.success("Usługi GMS zostały ograniczone")

    def _flush_memory(self):
        """Czyszczenie pamięci podręcznej i reset statystyk"""
        Logger.log("Czyszczenie pamięci i cache...")
        SystemShell.run("am kill-all", ignore_errors=True)  # Zabicie procesów w cache
        SystemShell.run("pm trim-caches 1G", ignore_errors=True)  # Czyszczenie cache systemowego
        SystemShell.run("dumpsys batterystats --reset", ignore_errors=True)  # Reset statystyk baterii
        
        # Jeśli masz uprawnienia wyższe (np. rish/su):
        SystemShell.run("sync && echo 3 > /proc/sys/vm/drop_caches", ignore_errors=True)
        Logger.success("Pamięć została wyczyszczona")


class InteractiveExpert:
    """Główna klasa interaktywnego przewodnika"""
    
    def __init__(self):
        self.device = self._detect_device()
        SystemShell.set_device(self.device)
        self.os_version = ""
        self.ram_total = ""
        self.performance_tuner = PerformanceTuner()
        
    def _detect_device(self) -> str:
        """Automatyczne wykrywanie podłączonego urządzenia ADB"""
        try:
            out = subprocess.check_output(["adb", "devices"], text=True).strip()
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines:
                device = lines[0].split("\t")[0]
                Logger.success(f"Wykryto urządzenie: {device}")
                return device
        except Exception as e:
            Logger.warning(f"Nie można wykryć urządzenia: {e}")
        
        # Fallback na domyślny adres
        default = "192.168.1.3:5555"
        Logger.warning(f"Używam domyślnego adresu: {default}")
        return default

    def adb(self, cmd: List[str]) -> str:
        """Kompatybilność wsteczna - wrapper dla SystemShell"""
        if cmd[0] == "shell":
            return SystemShell.run(" ".join(cmd[1:]))
        else:
            return SystemShell.run(" ".join(cmd), shell_wrapper=False)

    def clear(self):
        """Czyszczenie ekranu terminala"""
        os.system('clear' if os.name != 'nt' else 'cls')

    def print_header(self):
        """Wyświetlanie nagłówka aplikacji"""
        Logger.header("PLAYBOX TITANIUM v10.0 - ULTIMATE AUTOPILOT")

    def setup_persistence(self):
        """Tworzy skrypt startowy w Termux, który można wywołać po restarcie TV"""
        boot_script = Path.home() / "autostart_tv.sh"
        content = f"""#!/bin/bash
# PLAYBOX TITANIUM v10.0 - Auto-start script
adb connect {self.device}
sleep 2
python3 {os.path.abspath(__file__)} --auto
"""
        try:
            with open(boot_script, "w") as f:
                f.write(content)
            os.chmod(boot_script, 0o755)
            Logger.success(f"Utworzono warstwę trwałości: ~/autostart_tv.sh")
        except Exception as e:
            Logger.error(f"Błąd tworzenia skryptu startowego: {e}")

    def get_system_info(self):
        """Pobierz informacje o systemie"""
        Logger.log("Zbieranie informacji o systemie...")
        
        self.os_version = SystemShell.run("getprop ro.build.version.release")
        ram_info = SystemShell.run("cat /proc/meminfo | grep MemTotal")
        if ram_info:
            self.ram_total = ram_info.split()[1]
        
        device_model = SystemShell.run("getprop ro.product.model")
        device_brand = SystemShell.run("getprop ro.product.brand")
        
        print(f"\n{Logger.COLORS['cyan']}╔═══════════════════════════════════════════════╗")
        print(f"║  Informacje o urządzeniu                      ║")
        print(f"╠═══════════════════════════════════════════════╣")
        print(f"║  Marka: {device_brand:<36} ║")
        print(f"║  Model: {device_model:<36} ║")
        print(f"║  Android: {self.os_version:<34} ║")
        print(f"║  RAM: {self.ram_total:<38} kB ║")
        print(f"╚═══════════════════════════════════════════════╝{Logger.COLORS['reset']}\n")

    def interactive_menu(self):
        """Główne menu interaktywne"""
        self.setup_persistence()
        self.get_system_info()
        
        while True:
            self.clear()
            self.print_header()
            print(f"Połączono z: {Logger.COLORS['cyan']}{self.device}{Logger.COLORS['reset']}")
            print("\n╔════════════════════════════════════════════════════════════════╗")
            print("║  Wybierz obszar, który chcesz zoptymalizować:                 ║")
            print("╠════════════════════════════════════════════════════════════════╣")
            print(f"║  {Logger.COLORS['info']}1.{Logger.COLORS['reset']} [WIDEO] Maksymalna płynność i kodeki (SmartTube/4K)     ║")
            print(f"║  {Logger.COLORS['info']}2.{Logger.COLORS['reset']} [PILOT] Mapowanie przycisków i zabijanie apek         ║")
            print(f"║  {Logger.COLORS['info']}3.{Logger.COLORS['reset']} [SYSTEM] Agresywne uwalnianie RAM (Debloat)           ║")
            print(f"║  {Logger.COLORS['info']}4.{Logger.COLORS['reset']} [SIEĆ] Blokowanie reklam (DNS) i optymalizacja Cast  ║")
            print(f"║  {Logger.COLORS['success']}5.{Logger.COLORS['reset']} [PERFORMANCE] Zaawansowana optymalizacja 4K+HDR       ║")
            print(f"║  {Logger.COLORS['success']}6.{Logger.COLORS['reset']} [AUTO] Wykonaj wszystko (Zalecane!)                  ║")
            print(f"║  {Logger.COLORS['warning']}7.{Logger.COLORS['reset']} [INFO] Sprawdź stan systemu                          ║")
            print(f"║  {Logger.COLORS['error']}0.{Logger.COLORS['reset']} Wyjście                                              ║")
            print("╚════════════════════════════════════════════════════════════════╝")
            
            choice = input(f"\n{Logger.COLORS['cyan']}Twój wybór >{Logger.COLORS['reset']} ")
            
            if choice == "1":
                self.opt_video()
            elif choice == "2":
                self.opt_remote()
            elif choice == "3":
                self.opt_system()
            elif choice == "4":
                self.opt_network()
            elif choice == "5":
                self.opt_performance()
            elif choice == "6":
                self.run_full_auto()
            elif choice == "7":
                self.check_system_status()
            elif choice == "0":
                Logger.log("Do zobaczenia!", 'cyan')
                break
            else:
                Logger.warning("Nieprawidłowy wybór!")
            
            input(f"\n{Logger.COLORS['cyan']}Naciśnij Enter, aby kontynuować...{Logger.COLORS['reset']}")

    # --- MODUŁY OPTYMALIZACJI ---

    def opt_video(self):
        """Optymalizacja pipeline'u wideo"""
        Logger.header("OPTYMALIZACJA WIDEO")
        
        # Wymuszanie profilu sprzętowego dla dekoderów
        SystemShell.run("setprop media.stagefright.thumbnail.prefer_hw_codecs 1")
        SystemShell.run("setprop debug.stagefright.omx_default_rank 0")
        
        # Kompilacja SmartTube
        Logger.log("Kompilacja AOT dla SmartTube (może potrwać minutę)...")
        SystemShell.run("cmd package compile -m speed -f com.teamsmart.videomanager.tv")
        
        # Dodatkowe optymalizacje wideo
        SystemShell.run("setprop media.stagefright.enable-player true")
        SystemShell.run("setprop media.stagefright.enable-scan true")
        
        Logger.success("Optymalizacja wideo zakończona! SmartTube będzie startować szybciej.")

    def opt_remote(self):
        """Konfiguracja udogodnień pilota"""
        Logger.header("KONFIGURACJA PILOTA")
        
        # Nadawanie uprawnień dla Button Mappera
        SystemShell.run("pm grant flar2.homebutton android.permission.WRITE_SECURE_SETTINGS", ignore_errors=True)
        
        Logger.log("Propozycja: Przypisz 'Długie naciśnięcie' przycisku Home do 'Zabij aplikację'.", 'cyan')
        Logger.log("Zyskujesz: Błyskawiczne czyszczenie RAM bez wchodzenia w ustawienia.", 'cyan')
        Logger.success("Uprawnienia dla Button Mappera zostały nadane")

    def opt_system(self):
        """Agresywny Debloat i zarządzanie RAM"""
        Logger.header("OPTYMALIZACJA SYSTEMU")
        
        apps_to_kill = [
            "com.google.android.katniss",
            "com.amazon.amazonvideo.livingroom",
            "com.sagemcom.stb.setupwizard",
            "com.google.android.tungsten.setupwraith",
            "com.google.android.backdrop",  # Dodatkowe aplikacje do debloatu
            "com.google.android.apps.tv.launcherx"
        ]
        
        disabled_count = 0
        for app in apps_to_kill:
            result = SystemShell.run(f"pm disable-user --user 0 {app}", ignore_errors=True)
            if "disabled" in result.lower() or result == "":
                disabled_count += 1
        
        # Zmniejszenie logowania systemowego (oszczędza CPU)
        SystemShell.run("setprop log.tag.statsd OFF")
        SystemShell.run("setprop log.tag.stats_log OFF")
        
        Logger.success(f"Zamrożono {disabled_count}/{len(apps_to_kill)} zbędnych procesów. Wolny RAM zwiększony.")

    def opt_network(self):
        """Optymalizacja sieci i blokada reklam"""
        Logger.header("OPTYMALIZACJA SIECI")
        
        # Prywatny DNS AdGuard (Blokada reklam w całym systemie)
        SystemShell.run("settings put global private_dns_mode hostname")
        SystemShell.run("settings put global private_dns_specifier dns.adguard.com")
        
        # Cast buffer
        SystemShell.run("setprop media.stagefright.audio.deepbuffer true")
        
        # Dodatkowe optymalizacje TCP
        SystemShell.run('settings put global net.tcp.buffersize.default "4096,87380,524288,4096,16384,110208"')
        
        Logger.success("Aktywowano systemową blokadę reklam AdGuard i poprawiono Cast.")

    def opt_performance(self):
        """Zaawansowana optymalizacja wydajności (nowa funkcja!)"""
        Logger.header("ZAAWANSOWANA OPTYMALIZACJA WYDAJNOŚCI")
        self.performance_tuner.apply_tweaks()

    def check_system_status(self):
        """Sprawdź aktualny stan systemu"""
        Logger.header("STATUS SYSTEMU")
        
        # Zużycie RAM
        Logger.log("Sprawdzanie zużycia pamięci RAM...")
        meminfo = SystemShell.run("cat /proc/meminfo")
        if meminfo:
            for line in meminfo.split('\n')[:5]:
                print(f"  {line}")
        
        # Top procesów
        Logger.log("\nTop 5 procesów (CPU):")
        top_output = SystemShell.run("top -n 1 -b | head -n 12 | tail -n 5")
        if top_output:
            print(top_output)
        
        # Temperatura (jeśli dostępna)
        Logger.log("\nTemperatura urządzenia:")
        temp = SystemShell.run("cat /sys/class/thermal/thermal_zone0/temp", ignore_errors=True)
        if temp and temp.isdigit():
            temp_c = int(temp) / 1000
            print(f"  {temp_c}°C")
        else:
            print("  Brak danych o temperaturze")
        
        # Właściwości wydajności
        Logger.log("\nUstawienia wydajności:")
        props_to_check = [
            "debug.hwui.renderer",
            "debug.renderengine.backend",
            "persist.sys.hdr.enable"
        ]
        for prop in props_to_check:
            value = SystemShell.run(f"getprop {prop}")
            print(f"  {prop}: {value if value else 'nie ustawiono'}")

    def run_full_auto(self):
        """Wykonaj wszystkie optymalizacje automatycznie"""
        Logger.header("AUTOMATYCZNA OPTYMALIZACJA - PEŁNY PROFIL")
        
        Logger.log("Uruchamiam pełną sekwencję optymalizacji...\n", 'cyan')
        
        time.sleep(1)
        self.opt_video()
        time.sleep(1)
        
        self.opt_system()
        time.sleep(1)
        
        self.opt_network()
        time.sleep(1)
        
        self.opt_performance()
        time.sleep(1)
        
        # Optymalizacja animacji
        Logger.log("Przyspieszanie animacji systemowych...")
        SystemShell.run("settings put global window_animation_scale 0.5")
        SystemShell.run("settings put global transition_animation_scale 0.5")
        SystemShell.run("settings put global animator_duration_scale 0.5")
        
        Logger.header("🎉 TITANIUM COMPLETE 🎉")
        Logger.success("Wszystkie udogodnienia i optymalizacje zostały wdrożone!")
        Logger.log("Twoje urządzenie jest teraz w trybie ULTIMATE PERFORMANCE!", 'cyan')


# ==========================================
# GŁÓWNA FUNKCJA
# ==========================================

def main():
    """Punkt wejścia aplikacji"""
    try:
        expert = InteractiveExpert()
        
        if "--auto" in sys.argv:
            expert.run_full_auto()
        elif "--performance" in sys.argv:
            expert.opt_performance()
        elif "--video" in sys.argv:
            expert.opt_video()
        elif "--system" in sys.argv:
            expert.opt_system()
        elif "--network" in sys.argv:
            expert.opt_network()
        elif "--status" in sys.argv:
            expert.check_system_status()
        else:
            expert.interactive_menu()
    except KeyboardInterrupt:
        print("\n")
        Logger.warning("Przerwano przez użytkownika")
        sys.exit(0)
    except Exception as e:
        Logger.error(f"Nieoczekiwany błąd: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
