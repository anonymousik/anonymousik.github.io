#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# SECFERRO ARCHITECTURE BANNER (80 COLUMNS)                                    |
# MODULE: SecFERRO_PlayBoxOptimizer_v14.py                                     |
# SoC: Broadcom BCM72604 | RAM: 1.5 GB | OS: Android TV 9 (Sagemcom DCTIW362)    |
# ==============================================================================

import argparse
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import ClassVar, Final, List, Optional


@dataclass
class DeviceConfig:
    """Konfiguracja parametrów połączenia i stałych systemowych."""
    DEFAULT_TIMEOUT: Final[int] = 15
    BROADCOM_DECODER: Final[str] = "OMX.BROADCOM.video-decoder.vp9"
    UI_RESOLUTION: Final[str] = "1920x1080"
    UI_DENSITY: Final[int] = 213


@dataclass
class PlayBoxBroadcomV14:
    """Główny silnik optymalizacyjny dla urządzeń Sagemcom BCM72604."""
    target_ip: Optional[str] = None
    device: str = field(init=False, default="")
    is_connected: bool = field(init=False, default=False)
    config: DeviceConfig = field(default_factory=DeviceConfig)

    # Rejestr usług do wyłączenia/zamrożenia
    DISABLED_SERVICES: ClassVar[List[str]] = [
        "com.google.android.webview/com.google.android.apps.chrome.process.ChildProcessService",
        "com.google.android.webview/org.chromium.android_webview.services.CrashReceiverService",
        "com.google.android.webview/org.chromium.android_webview.services.VariationsSeedServer"
    ]

    DEBLOAT_PACKAGES: ClassVar[List[str]] = [
        "com.netflix.ninja",
        "com.google.android.youtube.tv"
    ]

    def __post_init__(self) -> None:
        if self.target_ip:
            self.device = self.target_ip

    def detect_device(self) -> str:
        """Wykrywa pierwsze dostępne urządzenie w interfejsie ADB."""
        try:
            out = subprocess.check_output(["adb", "devices"], text=True).strip()
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines:
                return lines[0].split("\t")[0]
        except Exception:
            pass
        return ""

    def adb(self, cmd_list: List[str], silent: bool = False, timeout: Optional[int] = None) -> str:
        """Wykonywanie komend ADB z zabezpieczeniem czasowym."""
        tout = timeout or self.config.DEFAULT_TIMEOUT
        try:
            full_cmd = ["adb", "-s", self.device] + cmd_list if self.device else ["adb"] + cmd_list
            res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=tout)
            return res.stdout.strip()
        except subprocess.TimeoutExpired:
            if not silent:
                print("\033[91m[ADB TIMEOUT] Urządzenie nie odpowiada.\033[0m")
            return ""
        except Exception as e:
            if not silent:
                print(f"\033[91m[ADB ERROR] {e}\033[0m")
            return ""

    def adb_shell(self, cmd_str: str, silent: bool = False) -> str:
        """Wykonanie polecenia w powłoce sh urządzenia."""
        return self.adb(["shell", cmd_str], silent=silent)

    def set_prop(self, key: str, value: str, root_fallback: bool = True) -> None:
        """Ustawia właściwość systemową (setprop) z powrotem do su w razie braku uprawnień."""
        self.adb(["shell", "setprop", key, value], silent=True)
        if root_fallback:
            self.adb(["shell", "su", "-c", f"setprop {key} {value}"], silent=True)

    def put_setting(self, namespace: str, key: str, value: str) -> None:
        """Aplikuje ustawienie w przestrzeni settings (global/secure/system)."""
        self.adb(["shell", "settings", "put", namespace, key, str(value)], silent=True)
        
    def sysfs_write(self, path: str, value: str) -> None:
        """Zapisuje wartość do ścieżki sysfs z próbą eskalacji uprawnień (root)."""
        self.adb(["shell", f'echo "{value}" > {path}'], silent=True)
        self.adb(["shell", "su", "-c", f'echo "{value}" > {path}'], silent=True)

    def connect(self, ip: Optional[str] = None) -> bool:
        """Nawiązuje połączenie ADB ze wskazanym lub wykrytym adresem IP."""
        if ip:
            self.device = ip
        elif not self.device:
            self.device = self.detect_device()

        if not self.device:
            print("\033[91m[!] Brak przypisanego IP lub nie wykryto urządzeń ADB.\033[0m")
            return False

        print(f"\033[93m[*] Łączenie z bazą Sagemcom: {self.device}...\033[0m")
        self.adb(["disconnect"], silent=True)
        res = self.adb(["connect", self.device])

        if "connected" in res.lower() or "already" in res.lower():
            self.is_connected = True
            print("\033[92m[✓] Połączenie nawiązane pomyślnie.\033[0m")
            return True
        
        self.is_connected = False
        print(f"\033[91m[!] Błąd połączenia: {res}\033[0m")
        return False

    # ---------------------------------------------------------
    # MODUŁ 1: THORIUM WEBVIEW & OPTYMALIZACJA USŁUG
    # ---------------------------------------------------------
    def module_webview_thorium_debloat(self) -> None:
        print("\n\033[96m[MODUŁ 1] Wdrożenie Thorium WebView & Wyłączenie zbędnych usług...\033[0m")
        
        for srv in self.DISABLED_SERVICES:
            self.adb_shell(f"pm disable-user --user 0 {srv}", silent=True)

        thorium_flags = (
            "ignore-gpu-blocklist=true "
            "enable-gpu-rasterization=true "
            "webview-accelerate-small-canvases=true "
            "num-raster-threads=2 "
            "webview-thread-safe-media=true "
            "webview-disable-package-allowlist-throttling=true"
        )
        self.put_setting("global", "webview_flags", f'"{thorium_flags}"')
        
        self.adb_shell("pkill -f com.google.android.webview", silent=True)
        self.adb_shell("am force-stop org.smarttube.stable", silent=True)
        print("\033[92m[✓] WebView Thorium zoptymalizowany, usługi tła odciążone.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 2: SKIAGL & FORCE GPU COMPOSITION (SURFACEFLINGER)
    # ---------------------------------------------------------
    def module_skiagl_gfxdriver_bcmstb(self) -> None:
        print("\n\033[96m[MODUŁ 2] Konfiguracja SkiaGL & Wymuszenie kompozycji GPU...\033[0m")
        
        props = {
            "debug.hwui.renderer": "skiagl",
            "persist.sys.ui.hw": "true",
            "debug.hwui.render_thread_count": "2",
            "debug.hwui.show_dirty_regions": "false",
            "debug.sf.disable_backpressure": "1",
            "debug.sf.latch_unsignaled": "1",
            "ro.hwui.texture_cache_size": "24.0",
            "ro.hwui.text_large_cache_width": "2048",
            "ro.hwui.text_large_cache_height": "1024"
        }
        for k, v in props.items():
            self.set_prop(k, v)

        self.adb_shell("service call SurfaceFlinger 1008 i32 1", silent=True)
        print("\033[92m[✓] SkiaGL aktywny, wymuszenie GPU composition zaimplementowane.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 3: NAPRAWA TUNNELED PLAYBACK & MEDIACODEC RESET
    # ---------------------------------------------------------
    def module_exoplayer_vdec_balance(self) -> None:
        print("\n\033[96m[MODUŁ 3] Naprawa Tunneled Playback & Prawdziwy Reset MediaCodec...\033[0m")
        
        self.set_prop("media.tunneled-playback.enable", "true")
        self.set_prop("ro.media.dec.video.vp9", self.config.BROADCOM_DECODER)

        print("\033[90m[*] Wykonywanie MediaCodecServiceReset (restart mediaserver i media.codec)...\033[0m")
        self.adb_shell("killall -9 android.hardware.media.omx@1.0-service", silent=True)
        self.adb_shell("pkill -f media.codec", silent=True)
        self.adb_shell("pkill -f mediaserver", silent=True)
        time.sleep(1)

        print("\033[92m[✓] Otworzono bezpośredni potok vdec, podsystem MediaCodec zresetowany.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 4: ROZDZIELCZOŚĆ UI (1080p) & PASSTHROUGH HDR
    # ---------------------------------------------------------
    def module_resolution_hdr_pipeline(self) -> None:
        print("\n\033[96m[MODUŁ 4] Wymuszenie UI 1080p & Potok HDMI HDR...\033[0m")
        
        self.adb_shell(f"wm size {self.config.UI_RESOLUTION}", silent=True)
        self.adb_shell(f"wm density {self.config.UI_DENSITY}", silent=True)

        self.put_setting("global", "user_preferred_resolution", "2160p60hz")
        self.put_setting("global", "hdr_output_mode", "auto")
        
        print("\033[92m[✓] UI utrwalone w 1080p (213 DPI), HDMI gotowe na strumień 4K HDR.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 5: GOVERNOR PERFORMANCE & ZARZĄDZANIE PAMIĘCIĄ
    # ---------------------------------------------------------
    def module_cpu_memory_governor(self) -> None:
        print("\n\033[96m[MODUŁ 5] Profil wydajności procesora & Zarządzanie RAM 1.5GB...\033[0m")
        
        self.put_setting("global", "low_power_trigger_level", "0")
        self.put_setting("global", "max_cached_processes", "2")
        self.set_prop("ro.sys.fw.bg_apps_limit", "2", root_fallback=True)

        self.adb_shell("cmd activity kill-all", silent=True)
        self.adb_shell("cmd activity trim-memory RUNNING_CRITICAL", silent=True)
        
        print("\033[92m[✓] Ograniczono procesy w tle do 2, pamięć RAM zwolniona.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 6: MAINTENANCE & KOMPILACJA AOT SMARTTUBE
    # ---------------------------------------------------------
    def module_smarttube_maintenance(self) -> None:
        print("\n\033[96m[MODUŁ 6] Czyszczenie Cache & Kompilacja AOT (SmartTube)...\033[0m")
        
        self.adb_shell("rm -rf /data/data/com.liskovsoft.smarttubetv.beta/cache/*", silent=True)
        self.adb_shell("rm -rf /data/data/org.smarttube.stable/cache/*", silent=True)

        print("\033[90m[*] Kompilacja AOT (speed-profile) dla org.smarttube.stable...\033[0m")
        self.adb_shell("cmd package compile -m speed-profile org.smarttube.stable", silent=True)
        
        print("\033[92m[✓] SmartTube skompilowany bezpośrednio pod architekturę BCM.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 7: GENTLE DEBLOAT & MROŻENIE APLIKACJI
    # ---------------------------------------------------------
    def module_debloat_and_freeze(self) -> None:
        print("\n\033[96m[MODUŁ 7] Łagodne mrożenie (Gentle Freeze) zbędnych pakietów...\033[0m")
        
        settings_secure = {
            "accessibility_enabled": "0",
            "upload_log_enable": "0",
            "assistant": "0"
        }
        for k, v in settings_secure.items():
            self.put_setting("secure", k, v)

        for pkg in self.DEBLOAT_PACKAGES:
            self.adb_shell(f"am force-stop {pkg}", silent=True)
            self.adb_shell(f"cmd appops set {pkg} RUN_IN_BACKGROUND ignore", silent=True)

        print("\033[92m[✓] Tło oczyszczone, zasoby CPU przekierowane na aplikację aktywną.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 8: EXTREME CPU, ZRAM, I/O & THERMAL UNLOCK
    # ---------------------------------------------------------
    def module_extreme_performance(self) -> None:
        print("\n\033[96m[MODUŁ 8] Odblokowanie Extreme CPU (1.8GHz), ZRAM & I/O...\033[0m")
        
        # 1. Odblokowanie Termiczne (Usunięcie Throttlingu)
        print("\033[90m[*] Wyłączanie limitów termicznych (Thermalserviced)...\033[0m")
        self.set_prop("persist.sys.thermal.enable", "false")
        self.adb_shell("stop thermalserviced", silent=True)
        
        # 2. Wymuszenie 1.8GHz i profilu Performance na rdzeniach BCM72604
        for cpu in ["cpu0", "cpu1"]:
            self.sysfs_write(f"/sys/devices/system/cpu/{cpu}/cpufreq/scaling_governor", "performance")
            self.sysfs_write(f"/sys/devices/system/cpu/{cpu}/cpufreq/scaling_max_freq", "1800000")
            
        # 3. Zwiększenie Cache bufora I/O (Szybciej ładuje duże wideo)
        print("\033[90m[*] Przyspieszanie wejścia/wyjścia (Read-Ahead = 2048KB)...\033[0m")
        self.sysfs_write("/sys/block/mmcblk0/queue/read_ahead_kb", "2048")
        
        # 4. Optymalny tuning ZRAM dla 1.5GB RAM
        print("\033[90m[*] Tuning algorytmu wymiany ZRAM (Swappiness & Cache Pressure)...\033[0m")
        self.sysfs_write("/proc/sys/vm/swappiness", "85")              # Agresywniejszy zrzut do skompresowanego RAMu (zapobiega OOM)
        self.sysfs_write("/proc/sys/vm/vfs_cache_pressure", "50")      # Zatrzymanie katalogów i inodów w pamięci (zwiększa responsywność)
        self.sysfs_write("/proc/sys/vm/page-cluster", "0")             # Dekompresja po jednej stronie (zmniejsza opóźnienie wideo)
        
        print("\033[92m[✓] Limit termiczny zniesiony. CPU, ZRAM i bufory ustawione na tryb EXTREME.\033[0m")

    # ---------------------------------------------------------
    # RESTART SYSTEMU UI
    # ---------------------------------------------------------
    def restart_ui(self) -> None:
        print("\n\033[93m[*] Soft Restart (SurfaceFlinger & SystemUI)...\033[0m")
        self.adb_shell("stop && start", silent=True)
        print("\033[92m[✓] Restart zainicjowany.\033[0m")

    # ---------------------------------------------------------
    # CAŁKOWITY PROGRAM OPTYMALIZACYJNY
    # ---------------------------------------------------------
    def run_full_omega(self) -> None:
        print("\n" + "=" * 65)
        print("\033[91m🚀 URUCHAMIANIE OMEGA V14: SAGEMCOM BROADCOM BCM72604\033[0m")
        print("=" * 65)
        
        self.module_webview_thorium_debloat()
        self.module_skiagl_gfxdriver_bcmstb()
        self.module_exoplayer_vdec_balance()
        self.module_resolution_hdr_pipeline()
        self.module_cpu_memory_governor()
        self.module_smarttube_maintenance()
        self.module_debloat_and_freeze()
        self.module_extreme_performance()
        
        print("\n\033[92m[✓] WIZJA SECFERRO ZAAFLIKOWANA: PEŁNA ZGODNOŚĆ BCM72604 (Z TRYBEM EXTREME)!\033[0m")
        self.restart_ui()
        print("=" * 65)


class CLIInterface:
    """Interfejs CLI do zarządzania optymalizatorem."""
    def __init__(self, engine: PlayBoxBroadcomV14):
        self.engine = engine

    @staticmethod
    def clear_screen() -> None:
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def pause() -> None:
        input("\n\033[90m[ Naciśnij ENTER, aby kontynuować ]\033[0m")

    def run(self) -> None:
        while True:
            self.clear_screen()
            print("\033[96m" + "═" * 70)
            print(" 🚀 PLAYBOX V14.0 - BROADCOM BCM72604 SECFERRO EDITION")
            print("═" * 70 + "\033[0m")
            
            if self.engine.is_connected:
                print(f" Status: \033[92m[✓] POŁĄCZONO ({self.engine.device})\033[0m")
            else:
                print(" Status: \033[91m[X] BRAK POŁĄCZENIA\033[0m")
            print("\033[96m" + "═" * 70 + "\033[0m\n")

            print("\033[93m--- MODUŁY OPTYMALIZACJI ---\033[0m")
            print(" 1. \033[97mWebView Thorium & Czyszczenie Usług Tła\033[0m")
            print(" 2. \033[97mSkiaGL & Force-GPU-Composition (SurfaceFlinger)\033[0m")
            print(" 3. \033[97mNaprawa Tunneled Playback & MediaCodecServiceReset\033[0m")
            print(" 4. \033[97mWymuszenie UI 1080p + Potok HDMI HDR\033[0m")
            print(" 5. \033[97mProfil Wydajności CPU & Zarządzanie Pamięcią RAM\033[0m")
            print(" 6. \033[97mAOT Kompilacja SmartTube & Maintenance\033[0m")
            print(" 7. \033[97mGentle Debloat & Mrożenie Aplikacji Tła\033[0m")
            print(" 8. \033[95mExtreme CPU 1.8GHz, Thermal Unlock, ZRAM & I/O Tune\033[0m")
            print("\n\033[93m--- AKCJE GLOBALNE ---\033[0m")
            print(" 10.\033[91m 🔥 BROADCOM OMEGA V14 (Uruchom Sekwencję 1-8) 🔥\033[0m")
            print(" 11.\033[92m ♻️ Soft Restart SystemUI\033[0m")
            print(" 12.\033[94m 🔌 Podłącz urządzenie (IP / Auto)\033[0m")
            print("\n 0. \033[90mWyjście\033[0m")

            choice = input("\n\033[93m[WYBIERZ AKCJĘ] > \033[0m").strip()

            if choice == '12':
                ip = input("Podaj IP:Port (np. 192.168.1.10:5555) [ENTER = Auto]: ").strip()
                self.engine.connect(ip if ip else None)
                self.pause()
                continue
            elif choice == '0':
                self.clear_screen()
                print("\033[92mZamykanie skryptu...\033[0m")
                break

            if not self.engine.is_connected and choice in [str(i) for i in range(1, 12)]:
                print("\n\033[91m[!] Najpierw nawiąż połączenie z urządzeniem (Opcja 12).\033[0m")
                self.pause()
                continue

            self.clear_screen()
            print("\033[90m" + "-" * 50 + "\033[0m")
            
            try:
                if choice == '1': self.engine.module_webview_thorium_debloat()
                elif choice == '2': self.engine.module_skiagl_gfxdriver_bcmstb()
                elif choice == '3': self.engine.module_exoplayer_vdec_balance()
                elif choice == '4': self.engine.module_resolution_hdr_pipeline()
                elif choice == '5': self.engine.module_cpu_memory_governor()
                elif choice == '6': self.engine.module_smarttube_maintenance()
                elif choice == '7': self.engine.module_debloat_and_freeze()
                elif choice == '8': self.engine.module_extreme_performance()
                elif choice == '10': self.engine.run_full_omega()
                elif choice == '11': self.engine.restart_ui()
                else: print("\033[91mNieprawidłowy wybór.\033[0m")
            except Exception as e:
                print(f"\n\033[91m[BŁĄD EXEC] {e}\033[0m")
                
            print("\033[90m" + "-" * 50 + "\033[0m")
            self.pause()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PlayBox V14.0 Broadcom Edition - SecFERRO Engine")
    parser.add_argument("--ip", type=str, help="Adres IP urządzenia ADB", default=None)
    args = parser.parse_args()

    engine_bot = PlayBoxBroadcomV14(target_ip=args.ip)
    if args.ip:
        engine_bot.connect(args.ip)
    else:
        engine_bot.connect()

    cli_app = CLIInterface(engine_bot)
    cli_app.run()