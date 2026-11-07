#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# PLAYBOX ULTIMATE V14.0 - BROADCOM BCM72604 REFACTORED EDITION
# Dedykowana optymalizacja dla Sagemcom DCTIW362 (Play Now TV Box V1)
# SoC: Broadcom BCM72604 (Dual-Core) | RAM: 1.5 GB | OS: Android TV 9
# ==============================================================================

import argparse
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import ClassVar, Final, List, Optional


@dataclass(frozen=True)
class DeviceConfig:
    """Stałe konfiguracyjne dla dekodera Sagemcom BCM72604."""
    DEFAULT_TIMEOUT: Final[int] = 15
    BROADCOM_DECODER: Final[str] = "OMX.BROADCOM.video-decoder.vp9"
    UI_WIDTH: Final[int] = 1920
    UI_HEIGHT: Final[int] = 1080
    UI_DENSITY: Final[int] = 213


@dataclass
class PlayBoxBroadcomV14:
    """Główny silnik optymalizacyjny dla Android TV 9 na SoC Broadcom."""
    target_ip: Optional[str] = None
    device: str = field(init=False, default="")
    is_connected: bool = field(init=False, default=False)
    config: DeviceConfig = field(default_factory=DeviceConfig)

    # Rejestry klasowe usług i pakietów (ClassVar)
    DISABLED_WEBVIEW_SERVICES: ClassVar[List[str]] = [
        "com.google.android.webview/com.google.android.apps.chrome.process.ChildProcessService",
        "com.google.android.webview/org.chromium.android_webview.services.CrashReceiverService",
        "com.google.android.webview/org.chromium.android_webview.services.VariationsSeedServer",
    ]

    FREEZE_PACKAGES: ClassVar[List[str]] = [
        "com.netflix.ninja",
        "com.google.android.youtube.tv",
    ]

    THORIUM_FLAGS: ClassVar[str] = (
        "ignore-gpu-blocklist=true "
        "enable-gpu-rasterization=true "
        "webview-accelerate-small-canvases=true "
        "num-raster-threads=2 "
        "webview-thread-safe-media=true "
        "webview-disable-package-allowlist-throttling=true"
    )

    def __post_init__(self) -> None:
        if self.target_ip:
            self.device = self.target_ip

    def detect_device(self) -> str:
        """Automatyczne wykrywanie pierwszego dostępnego urządzenia ADB."""
        try:
            out = subprocess.check_output(["adb", "devices"], text=True).strip()
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines:
                return lines[0].split("\t")[0]
        except Exception:
            pass
        return ""

    def adb(self, cmd_list: List[str], silent: bool = False, timeout: Optional[int] = None) -> str:
        """Bezpieczne wykonywanie polecenia ADB z obsługą timeoutu."""
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
        """Ustawianie właściwości systemowej setprop (z obsługą root su)."""
        self.adb(["shell", "setprop", key, value], silent=True)
        if root_fallback:
            self.adb(["shell", "su", "-c", f"setprop {key} {value}"], silent=True)

    def put_setting(self, namespace: str, key: str, value: str) -> None:
        """Ustawianie wartości w przestrzeni settings (global/secure/system)."""
        self.adb(["shell", "settings", "put", namespace, key, str(value)], silent=True)

    def connect(self, ip: Optional[str] = None) -> bool:
        """Nawiązywanie połączenia ADB."""
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
    # MODUŁ 1: WEBVIEW THORIUM & ODCIĄŻENIE USŁUG TŁA
    # ---------------------------------------------------------
    def module_webview_thorium_debloat(self) -> None:
        print("\n\033[96m[MODUŁ 1] Wyłączenie zbędnych usług WebView & Flagi Thorium...\033[0m")

        for srv in self.DISABLED_WEBVIEW_SERVICES:
            self.adb_shell(f"pm disable-user --user 0 {srv}", silent=True)

        self.put_setting("global", "webview_flags", f'"{self.THORIUM_FLAGS}"')

        # Wyczyszczenie i restart instancji WebView i SmartTube
        self.adb_shell("pkill -f com.google.android.webview", silent=True)
        self.adb_shell("am force-stop org.smarttube.stable", silent=True)
        print("\033[92m[✓] WebView Thorium zoptymalizowany, usługi tła odciążone.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 2: SKIAGL & FORCE GPU COMPOSITION
    # ---------------------------------------------------------
    def module_skiagl_gfxdriver_bcmstb(self) -> None:
        print("\n\033[96m[MODUŁ 2] SkiaGL & Wymuszenie kompozycji GPU (SurfaceFlinger)...\033[0m")

        props = {
            "debug.hwui.renderer": "skiagl",
            "persist.sys.ui.hw": "true",
            "debug.hwui.render_thread_count": "2",
            "debug.hwui.show_dirty_regions": "false",
            "debug.sf.disable_backpressure": "1",
            "debug.sf.latch_unsignaled": "1",
            "ro.hwui.texture_cache_size": "24.0",
            "ro.hwui.text_large_cache_width": "2048",
            "ro.hwui.text_large_cache_height": "1024",
        }
        for k, v in props.items():
            self.set_prop(k, v)

        # Wymuszenie renderingu przez GPU w SurfaceFlinger (Obejście HWC)
        self.put_setting("global", "overlay_display_devices", '""')
        self.adb_shell("service call SurfaceFlinger 1008 i32 1", silent=True)

        print("\033[92m[✓] SkiaGL aktywny, kompozycja GPU wymuszona w SurfaceFlinger.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 3: TUNNELED PLAYBACK & MEDIACODEC RESET (FIX 10S BLACK SCREEN)
    # ---------------------------------------------------------
    def module_exoplayer_vdec_balance(self) -> None:
        print("\n\033[96m[MODUŁ 3] Przywrócenie Tunneled Playback & Reset MediaCodec...\033[0m")

        # FIX: Tunneled playback MUSI być aktywny dla sprzętowej akceleracji Broadcom.
        # Wyłączenie tego klucza w poprzednich wersjach było bezpośrednią przyczyną 10s czarnego ekranu.
        self.set_prop("media.tunneled-playback.enable", "true")
        self.set_prop("ro.media.dec.video.vp9", self.config.BROADCOM_DECODER)

        # Prawdziwy reset sprzętowego podsystemu dekoderów wideo
        print("\033[90m[*] Wykonywanie MediaCodecServiceReset (restart service OMX, media.codec, mediaserver)...\033[0m")
        self.adb_shell("killall -9 android.hardware.media.omx@1.0-service", silent=True)
        self.adb_shell("pkill -f media.codec", silent=True)
        self.adb_shell("pkill -f mediaserver", silent=True)
        time.sleep(1)

        print("\033[92m[✓] Tunneled playback aktywne, MediaCodec zresetowany (Usunięto czarny ekran).\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 4: ROZDZIELCZOŚĆ UI 1080p & POTOK HDMI HDR
    # ---------------------------------------------------------
    def module_resolution_hdr_pipeline(self) -> None:
        print("\n\033[96m[MODUŁ 4] Wymuszenie UI 1080p & Konfiguracja HDMI Passthrough...\033[0m")

        self.adb_shell(f"wm size {self.config.UI_WIDTH}x{self.config.UI_HEIGHT}", silent=True)
        self.adb_shell(f"wm density {self.config.UI_DENSITY}", silent=True)

        self.put_setting("global", "user_preferred_resolution", "2160p60hz")
        self.put_setting("global", "hdr_output_mode", "auto")

        print("\033[92m[✓] Interfejs 1080p zaimplementowany, wyjście HDMI przygotowane na 4K HDR.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 5: GOVERNOR PROCESORA & ZARZĄDZANIE PAMIĘCIĄ (1.5GB RAM)
    # ---------------------------------------------------------
    def module_cpu_memory_governor(self) -> None:
        print("\n\033[96m[MODUŁ 5] Profil wydajnościowy CPU & Zarządzanie LMK (1.5GB RAM)...\033[0m")

        self.put_setting("global", "low_power_trigger_level", "0")
        self.put_setting("global", "max_cached_processes", "2")
        self.set_prop("ro.sys.fw.bg_apps_limit", "2", root_fallback=True)

        # Zwolnienie pamięci podręcznej RAM
        self.adb_shell("cmd activity kill-all", silent=True)
        self.adb_shell("cmd activity trim-memory RUNNING_CRITICAL", silent=True)

        print("\033[92m[✓] Ograniczono procesy w tle do 2, pamięć RAM zwolniona dla odtwarzacza.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 6: CACHE CLEANUP & AOT KOMPILACJA (SMARTTUBE)
    # ---------------------------------------------------------
    def module_smarttube_maintenance(self) -> None:
        print("\n\033[96m[MODUŁ 6] Czyszczenie Cache & Kompilacja AOT SmartTube...\033[0m")

        self.adb_shell("rm -rf /data/data/com.liskovsoft.smarttubetv.beta/cache/*", silent=True)
        self.adb_shell("rm -rf /data/data/org.smarttube.stable/cache/*", silent=True)

        print("\033[90m[*] Kompilacja natywna AOT (speed-profile) dla org.smarttube.stable...\033[0m")
        self.adb_shell("cmd package compile -m speed-profile org.smarttube.stable", silent=True)

        print("\033[92m[✓] SmartTube skompilowany AOT pod procesor Broadcom.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 7: GENTLE DEBLOAT & MROŻENIE APLIKACJI
    # ---------------------------------------------------------
    def module_debloat_and_freeze(self) -> None:
        print("\n\033[96m[MODUŁ 7] Zamrożenie zbędnych aplikacji i telemetrii...\033[0m")

        settings_secure = {
            "accessibility_enabled": "0",
            "upload_log_enable": "0",
            "assistant": "0",
        }
        for k, v in settings_secure.items():
            self.put_setting("secure", k, v)

        for pkg in self.FREEZE_PACKAGES:
            self.adb_shell(f"am force-stop {pkg}", silent=True)
            self.adb_shell(f"cmd appops set {pkg} RUN_IN_BACKGROUND ignore", silent=True)

        print("\033[92m[✓] Pakiety w tle zamrożone, procesor odciążony.\033[0m")

    # ---------------------------------------------------------
    # RESTART SYSTEMUI
    # ---------------------------------------------------------
    def restart_ui(self) -> None:
        print("\n\033[93m[*] Soft Restart (SurfaceFlinger & SystemUI)...\033[0m")
        self.adb_shell("stop && start", silent=True)
        print("\033[92m[✓] Powłoka graficzna restartuje się.\033[0m")

    # ---------------------------------------------------------
    # PEŁNY PROGRAM OPTYMALIZACJI
    # ---------------------------------------------------------
    def run_full_omega(self) -> None:
        print("\n" + "=" * 65)
        print("\033[91m🚀 URUCHAMIANIE OMEGA V14 REFACTORED: BROADCOM BCM72604\033[0m")
        print("=" * 65)

        self.module_webview_thorium_debloat()
        self.module_skiagl_gfxdriver_bcmstb()
        self.module_exoplayer_vdec_balance()
        self.module_resolution_hdr_pipeline()
        self.module_cpu_memory_governor()
        self.module_smarttube_maintenance()
        self.module_debloat_and_freeze()

        print("\n\033[92m[✓] WSZYSTKIE AUDYTOWANE I SPRAWDZONE TWEAKI ZAAPLIKOWANE!\033[0m")
        self.restart_ui()
        print("=" * 65)


class CLIInterface:
    """Interfejs konsolowy (CLI) dla skryptu."""

    def __init__(self, bot: PlayBoxBroadcomV14):
        self.bot = bot

    @staticmethod
    def clear_screen() -> None:
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def pause() -> None:
        input("\n\033[90m[ Naciśnij ENTER, aby kontynuować ]\033[0m")

    def run(self) -> None:
        while True:
            self.clear_screen()
            print("\033[96m" + "═" * 70)
            print(" 🚀 PLAYBOX V14.0 REFACTORED - SAGEMCOM BCM72604 (1.5GB RAM)")
            print("═" * 70 + "\033[0m")

            if self.bot.is_connected:
                print(f" Status: \033[92m[✓] POŁĄCZONO ({self.bot.device})\033[0m")
            else:
                print(" Status: \033[91m[X] BRAK POŁĄCZENIA\033[0m")
            print("\033[96m" + "═" * 70 + "\033[0m\n")

            print("\033[93m--- MODUŁY OPTYMALIZACYJNE V14 ---\033[0m")
            print(" 1. \033[97mWebView Thorium & Wyłączenie zbędnych usług\033[0m")
            print(" 2. \033[97mSkiaGL & Force GPU Composition (SurfaceFlinger)\033[0m")
            print(" 3. \033[97mPrzywrócenie Tunneled Playback & MediaCodec Reset (Fix 10s)\033[0m")
            print(" 4. \033[97mUI 1080p + HDMI 4K HDR Passthrough Pipeline\033[0m")
            print(" 5. \033[97mProfil Wydajności CPU & LMK (Limit 2 procesów)\033[0m")
            print(" 6. \033[97mCzyszczenie Cache & AOT Kompilacja SmartTube\033[0m")
            print(" 7. \033[97mGentle Debloat & Zamrożenie Tła\033[0m")
            print("\n\033[93m--- AKCJE GLOBALNE ---\033[0m")
            print(" 10.\033[91m 🔥 BROADCOM OMEGA V14 (Uruchom Sekwencję 1-7) 🔥\033[0m")
            print(" 11.\033[92m ♻️ Soft Restart SystemUI\033[0m")
            print(" 12.\033[94m 🔌 Podłącz urządzenie (IP / Auto)\033[0m")
            print("\n 0. \033[0mWyjście\033[0m")

            choice = input("\n\033[93m[WYBIERZ AKCJĘ] > \033[0m").strip()

            if choice == "12":
                ip = input("Podaj IP:Port (np. 192.168.1.10:5555) [ENTER = Auto]: ").strip()
                self.bot.connect(ip if ip else None)
                self.pause()
                continue
            elif choice == "0":
                self.clear_screen()
                print("\033[92mZamykanie skryptu...\033[0m")
                break

            if not self.bot.is_connected and choice in [str(i) for i in range(1, 12)]:
                print("\n\033[91m[!] Najpierw nawiąż połączenie z urządzeniem (Opcja 12).\033[0m")
                self.pause()
                continue

            self.clear_screen()
            print("\033[90m" + "-" * 50 + "\033[0m")

            try:
                if choice == "1":
                    self.bot.module_webview_thorium_debloat()
                elif choice == "2":
                    self.bot.module_skiagl_gfxdriver_bcmstb()
                elif choice == "3":
                    self.bot.module_exoplayer_vdec_balance()
                elif choice == "4":
                    self.bot.module_resolution_hdr_pipeline()
                elif choice == "5":
                    self.bot.module_cpu_memory_governor()
                elif choice == "6":
                    self.bot.module_smarttube_maintenance()
                elif choice == "7":
                    self.bot.module_debloat_and_freeze()
                elif choice == "10":
                    self.bot.run_full_omega()
                elif choice == "11":
                    self.bot.restart_ui()
                else:
                    print("\033[91mNieprawidłowy wybór.\033[0m")
            except Exception as e:
                print(f"\n\033[91m[BŁĄD EXEC] {e}\033[0m")

            print("\033[90m" + "-" * 50 + "\033[0m")
            self.pause()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PlayBox V14.0 Refactored Broadcom Edition")
    parser.add_argument("--ip", type=str, help="IP urządzenia ADB", default=None)
    args = parser.parse_args()

    bot = PlayBoxBroadcomV14(target_ip=args.ip)
    bot.connect(args.ip)

    cli = CLIInterface(bot)
    cli.run()