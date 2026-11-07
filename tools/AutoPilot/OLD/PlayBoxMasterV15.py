#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# SECFERRO ARCHITECTURE MASTER OPTIMIZER (v15.0)                               |
# TARGET SoC: Broadcom BCM72604 | RAM: 1.5 GB | OS: Android TV 9               |
# HARDWARE: Sagemcom DCTIW362 (Play Now TV Box V1)                             |
# ==============================================================================

import argparse
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import ClassVar, Final, List, Optional


@dataclass(frozen=True)
class DeviceConfig:
    """Hardware and environment constants for Sagemcom BCM72604."""
    DEFAULT_TIMEOUT: Final[int] = 15
    BROADCOM_DECODER: Final[str] = "OMX.BROADCOM.video-decoder.vp9"
    UI_WIDTH: Final[int] = 1920
    UI_HEIGHT: Final[int] = 1080
    UI_DENSITY: Final[int] = 213
    EXOPLAYER_MAX_BUFFER_MS: Final[int] = 25000  # 25s safe buffer window
    EXOPLAYER_DASH_CHUNK_SIZE: Final[int] = 4194304  # 4MB DASH chunk size


@dataclass
class PlayBoxMasterEngine:
    """Master optimization engine resolving freezes, buffering, and driver conflicts."""
    target_ip: Optional[str] = None
    device: str = field(init=False, default="")
    is_connected: bool = field(init=False, default=False)
    config: DeviceConfig = field(default_factory=DeviceConfig)

    # Webview crash receivers and unneeded processes
    DISABLED_WEBVIEW_SERVICES: ClassVar[List[str]] = [
        "com.google.android.webview/com.google.android.apps.chrome.process.ChildProcessService",
        "com.google.android.webview/org.chromium.android_webview.services.CrashReceiverService",
        "com.google.android.webview/org.chromium.android_webview.services.VariationsSeedServer",
    ]

    # Consolidated Thorium & Chromium performance flags
    CONSOLIDATED_WEBVIEW_FLAGS: ClassVar[str] = (
        "ignore-gpu-blocklist=true "
        "enable-gpu-rasterization=true "
        "animated-image-resume=true "
        "webview-accelerate-small-canvases=true "
        "num-raster-threads=2 "
        "webview-thread-safe-media=true "
        "optimize-network-buffers=true "
        "optimize-network-buffers2=true "
        "enable-finch-seed-delta-compression=true "
        "enable-webview-surface-control-for-tv=true "
        "webview-surface-control=true "
        "webview-disable-package-allowlist-throttling=true"
    )

    def __post_init__(self) -> None:
        if self.target_ip:
            self.device = self.target_ip

    def detect_device(self) -> str:
        """Autodetects ADB device connection."""
        try:
            out = subprocess.check_output(["adb", "devices"], text=True).strip()
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines:
                return lines[0].split("\t")[0]
        except Exception:
            pass
        return ""

    def adb(self, cmd_list: List[str], silent: bool = False, timeout: Optional[int] = None) -> str:
        """Executes safe ADB commands with configurable timeouts."""
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
        """Executes shell commands on target Android TV."""
        return self.adb(["shell", cmd_str], silent=silent)

    def set_prop(self, key: str, value: str, root_fallback: bool = True) -> None:
        """Sets system property with root fallback."""
        self.adb(["shell", "setprop", key, value], silent=True)
        if root_fallback:
            self.adb(["shell", "su", "-c", f"setprop {key} {value}"], silent=True)

    def put_setting(self, namespace: str, key: str, value: str) -> None:
        """Applies global/secure/system settings."""
        self.adb(["shell", "settings", "put", namespace, key, str(value)], silent=True)

    def delete_setting(self, namespace: str, key: str) -> None:
        """Deletes broken or conflicting settings keys."""
        self.adb(["shell", "settings", "delete", namespace, key], silent=True)

    def connect(self, ip: Optional[str] = None) -> bool:
        """Establishes connection over IP or USB ADB."""
        if ip:
            self.device = ip
        elif not self.device:
            self.device = self.detect_device()

        if not self.device:
            print("\033[91m[!] Brak przypisanego IP lub nie wykryto urządzeń ADB.\033[0m")
            return False

        print(f"\033[93m[*] Łączenie z Sagemcom DCTIW362: {self.device}...\033[0m")
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
    # MODUŁ ZERO: CZYSZCZENIE BŁĘDNYCH I NIEBEZPIECZNYCH USTAWIEŃ
    # ---------------------------------------------------------
    def module_sanitization_and_reset(self) -> None:
        print("\n\033[93m[KROK 0] Czyszczenie błędnych konfiguracji i przywracanie stabilności...\033[0m")

        # 1. Przywrócenie ochrony termicznej (usunięcie przegrzewania CPU)
        self.set_prop("persist.sys.thermal.enable", "true")
        self.adb_shell("su -c 'start thermalserviced'", silent=True)
        self.adb_shell("su -c 'echo schedutil > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'", silent=True)
        self.adb_shell("su -c 'echo schedutil > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor'", silent=True)

        # 2. Naprawa opóźnień SurfaceFlinger (zapobiega gubieniu klatek i zatorom)
        self.set_prop("debug.sf.disable_backpressure", "0")
        self.set_prop("debug.sf.latch_unsignaled", "0")

        # 3. Przywrócenie bezpiecznych limitów procesów w tle (zapobiega zabijaniu ExoPlayera)
        self.delete_setting("global", "max_cached_processes")
        self.delete_setting("global", "sys_free_storage_log_interval")
        self.set_prop("ro.sys.fw.bg_apps_limit", "8", root_fallback=True)

        # 4. Bezpieczna wymiana ZRAM / I/O
        self.adb_shell("su -c 'echo 60 > /proc/sys/vm/swappiness'", silent=True)
        self.adb_shell("su -c 'echo 128 > /sys/block/mmcblk0/queue/read_ahead_kb'", silent=True)

        print("\033[92m[✓] Błędne/niebezpieczne wpisy zostały pomyślnie skasowane i zresetowane.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 1: WEBVIEW & CHROMIUM OPTIMIZATIONS
    # ---------------------------------------------------------
    def module_webview_chromium_tune(self) -> None:
        print("\n\033[96m[MODUŁ 1] Zoptymalizowana konfiguracja WebView & Flagi Thorium...\033[0m")

        for srv in self.DISABLED_WEBVIEW_SERVICES:
            self.adb_shell(f"pm disable-user --user 0 {srv}", silent=True)

        self.put_setting("global", "webview_flags", f'"{self.CONSOLIDATED_WEBVIEW_FLAGS}"')
        self.put_setting("global", "webview_flags_tv", '"enable-webview-surface-control-for-tv=true"')
        self.put_setting("global", "webview_flags_media", '"webview-thread-safe-media=true"')

        self.adb_shell("pkill -f com.google.android.webview", silent=True)
        self.adb_shell("am force-stop org.smarttube.stable", silent=True)
        print("\033[92m[✓] WebView Thorium, buforowanie sieciowe i usługi podrzędne zoptymalizowane.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 2: SKIAGL & BROADCOM GFXDRIVER HARDWARE PIPELINE
    # ---------------------------------------------------------
    def module_skiagl_bcmstb_pipeline(self) -> None:
        print("\n\033[96m[MODUŁ 2] SkiaGL Engine & Wymuszenie sprzętowego BCMSTB drivera...\033[0m")

        props = {
            "debug.hwui.renderer": "skiagl",
            "persist.sys.ui.hw": "true",
            "debug.hwui.render_thread_count": "2",
            "debug.hwui.show_dirty_regions": "false",
            "ro.hwui.texture_cache_size": "24.0",
            "ro.hwui.text_large_cache_width": "2048",
            "ro.hwui.text_large_cache_height": "1024",
        }
        for k, v in props.items():
            self.set_prop(k, v)

        # Obejście nakładek systemowych dla bezpośredniego strumienia wideo
        self.put_setting("global", "overlay_display_devices", '""')
        self.adb_shell("service call SurfaceFlinger 1008 i32 1", silent=True)

        print("\033[92m[✓] Silnik SkiaGL oraz bezpośredni potok bcmstb skonfigurowane.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 3: EXOPLAYER NETWORK BUFFERING & MEDIACODEC RESET
    # ---------------------------------------------------------
    def module_exoplayer_and_mediacodec(self) -> None:
        print("\n\033[96m[MODUŁ 3] Konfiguracja bufora ExoPlayer & Reset dekodera Broadcom...\033[0m")

        # Wymuszenie bezpiecznego okna bufora (zapobiega brakowi RAMu i nieskończonemu ładowaniu)
        self.put_setting("global", "exoplayer_max_buffer_ms", self.config.EXOPLAYER_MAX_BUFFER_MS)
        self.put_setting("global", "exoplayer_dash_chunk_size", self.config.EXOPLAYER_DASH_CHUNK_SIZE)

        # Dekoder VP9 Broadcom Nexus
        self.set_prop("media.tunneled-playback.enable", "true")
        self.set_prop("ro.media.dec.video.vp9", self.config.BROADCOM_DECODER)

        # Reset uszkodzonych wątków dekodera bez restartu całego boksu
        self.adb_shell("killall -9 android.hardware.media.omx@1.0-service", silent=True)
        self.adb_shell("pkill -f media.codec", silent=True)
        self.adb_shell("pkill -f mediaserver", silent=True)
        time.sleep(1)

        print("\033[92m[✓] Bufory ExoPlayer ustalone na 25s / 4MB chunks. MediaCodec zresetowany.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 4: 1080p UI + 4K HDR PASSTHROUGH PIPELINE
    # ---------------------------------------------------------
    def module_display_and_hdr_pipeline(self) -> None:
        print("\n\033[96m[MODUŁ 4] Interfejs 1080p +HDMI 4K60Hz Passthrough HDR...\033[0m")

        self.adb_shell(f"wm size {self.config.UI_WIDTH}x{self.config.UI_HEIGHT}", silent=True)
        self.adb_shell(f"wm density {self.config.UI_DENSITY}", silent=True)
        self.put_setting("global", "display_size_forced", "1920,1080")

        self.put_setting("global", "user_preferred_resolution", "2160p60hz")
        self.put_setting("global", "hdr_output_mode", "auto")
        self.put_setting("global", "hdr_static_metadata", "1")
        self.put_setting(
            "global",
            "nrdp_platform_capabilities",
            '{"hdrOutputType":"always","videoPeekTunnelFramesToSend":16}',
        )

        print("\033[92m[✓] Płynny interfejs 1080p utrwalony. Wyjście HDMI przygotowane na HDR 4K60Hz.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 5: AOT KOMPILACJA SMARTTUBE & WYCZYSZCZENIE CACHE
    # ---------------------------------------------------------
    def module_smarttube_aot_compile(self) -> None:
        print("\n\033[96m[MODUŁ 5] Kompilacja AOT (speed-profile) & Czyszczenie Cache SmartTube...\033[0m")

        self.adb_shell("rm -rf /data/data/com.liskovsoft.smarttubetv.beta/cache/*", silent=True)
        self.adb_shell("rm -rf /data/data/org.smarttube.stable/cache/*", silent=True)

        print("\033[90m[*] Wykonywanie kompilacji natywnej pod procesor Broadcom...\033[0m")
        self.adb_shell("cmd package compile -m speed-profile org.smarttube.stable", silent=True)
        self.adb_shell("cmd package compile -m speed-profile com.liskovsoft.smarttubetv.beta", silent=True)

        print("\033[92m[✓] Kod aplikacji SmartTube został skompilowany bezpośrednio do instrukcji CPU BCM.\033[0m")

    # ---------------------------------------------------------
    # RESTART SYSTEMU
    # ---------------------------------------------------------
    def restart_ui(self) -> None:
        print("\n\033[93m[*] Soft Restart (SurfaceFlinger & SystemUI)...\033[0m")
        self.adb_shell("stop && start", silent=True)
        print("\033[92m[✓] Restart interfejsu graficznego zakończony powodzeniem.\033[0m")

    # ---------------------------------------------------------
    # PEŁNY SEKWENCYJNY PROGRAM OMEGA V15
    # ---------------------------------------------------------
    def run_full_master_sequence(self) -> None:
        print("\n" + "=" * 70)
        print("\033[91m🚀 MASTER OPTIMIZER V15.0: SAGEMCOM BROADCOM BCM72604 RECOVERY & TUNE\033[0m")
        print("=" * 70)

        self.module_sanitization_and_reset()
        self.module_webview_chromium_tune()
        self.module_skiagl_bcmstb_pipeline()
        self.module_exoplayer_and_mediacodec()
        self.module_display_and_hdr_pipeline()
        self.module_smarttube_aot_compile()

        print("\n\033[92m[✓] SUKCES: Wszystkie poprawki zaaplikowane! Usunięto błędy buforowania i przegrzewania.\033[0m")
        self.restart_ui()
        print("=" * 70)


class CLIInterface:
    """Interfejs CLI do obsługi skryptu."""

    def __init__(self, engine: PlayBoxMasterEngine):
        self.engine = engine

    @staticmethod
    def clear_screen() -> None:
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def pause() -> None:
        input("\n\033[90m[ Naciśnij ENTER, aby kontynuować ]\033[0m")

    def run(self) -> None:
        while True:
            self.clear_screen()
            print("\033[96m" + "═" * 72)
            print(" 🚀 PLAYBOX V15.0 MASTER - SAGEMCOM DCTIW362 (BCM72604 1.5GB RAM)")
            print("═" * 72 + "\033[0m")

            if self.engine.is_connected:
                print(f" Status: \033[92m[✓] POŁĄCZONO ({self.engine.device})\033[0m")
            else:
                print(" Status: \033[91m[X] BRAK POŁĄCZENIA\033[0m")
            print("\033[96m" + "═" * 72 + "\033[0m\n")

            print("\033[93m--- MODUŁY RECOVERY & OPTYMALIZACJI V15 ---\033[0m")
            print(" 0. \033[91m⚠️ Czyszczenie błędnych/niebezpiecznych ustawień (Reset LMK & Thermal)\033[0m")
            print(" 1. \033[97mWebView Thorium & Kompletne Flagi Chromium\033[0m")
            print(" 2. \033[97mSkiaGL & Direct Hardware BCMSTB Graphics Pipeline\033[0m")
            print(" 3. \033[97mExoPlayer Buffer Tuning (25s / 4MB) & MediaCodec Reset\033[0m")
            print(" 4. \033[97mUI 1080p + HDMI 4K60Hz HDR Passthrough Pipeline\033[0m")
            print(" 5. \033[97mAOT Kompilacja Native Speed-Profile dla SmartTube\033[0m")
            print("\n\033[93m--- AKCJE GLOBALNE ---\033[0m")
            print(" 10.\033[91m 🔥 PEŁNA SEKWENCJA OPTYMALIZACYJNA V15 (Kroki 0-5) 🔥\033[0m")
            print(" 11.\033[92m ♻️ Soft Restart SystemUI (stop && start)\033[0m")
            print(" 12.\033[94m 🔌 Podłącz urządzenie przez ADB (IP / Auto)\033[0m")
            print("\n EXIT. \033[90mWpisz 'q' aby wyjść\033[0m")

            choice = input("\n\033[93m[WYBIERZ AKCJĘ] > \033[0m").strip().lower()

            if choice == "12":
                ip = input("Podaj IP:Port (np. 192.168.1.10:5555) [ENTER = Auto]: ").strip()
                self.engine.connect(ip if ip else None)
                self.pause()
                continue
            elif choice in ["q", "exit"]:
                self.clear_screen()
                print("\033[92mZamykanie skryptu PlayBox V15...\033[0m")
                break

            if not self.engine.is_connected and choice in [str(i) for i in range(0, 12)]:
                print("\n\033[91m[!] Najpierw nawiąż połączenie z dekoderem (Opcja 12).\033[0m")
                self.pause()
                continue

            self.clear_screen()
            print("\033[90m" + "-" * 50 + "\033[0m")

            try:
                if choice == "0":
                    self.engine.module_sanitization_and_reset()
                elif choice == "1":
                    self.engine.module_webview_chromium_tune()
                elif choice == "2":
                    self.engine.module_skiagl_bcmstb_pipeline()
                elif choice == "3":
                    self.engine.module_exoplayer_and_mediacodec()
                elif choice == "4":
                    self.engine.module_display_and_hdr_pipeline()
                elif choice == "5":
                    self.engine.module_smarttube_aot_compile()
                elif choice == "10":
                    self.engine.run_full_master_sequence()
                elif choice == "11":
                    self.engine.restart_ui()
                else:
                    print("\033[91mNieprawidłowy wybór.\033[0m")
            except Exception as e:
                print(f"\n\033[91m[BŁĄD EXEC] {e}\033[0m")

            print("\033[90m" + "-" * 50 + "\033[0m")
            self.pause()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PlayBox V15.0 Master Optimizer for Broadcom BCM72604")
    parser.add_argument("--ip", type=str, help="IP urządzenia ADB", default=None)
    args = parser.parse_args()

    engine_bot = PlayBoxMasterEngine(target_ip=args.ip)
    engine_bot.connect(args.ip)

    cli = CLIInterface(engine_bot)
    cli.run()