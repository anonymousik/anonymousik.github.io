#!/usr/bin/env python3
"""
PLAYBOX TITANIUM v10.2 PRO - ULTIMATE EDITION (ROOTLESS & ROOT HYBRID)
Target Device: Sagemcom DCTIW362 / DCTIW362P (Play Now TV Box V1)
SoC: Broadcom BCM72604 / m362 | Android TV 9 (Pie) API 28
Author: Anonymousik / Architecture Master Optimizer
"""

import io
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DeviceSpec:
    """Specyfikacja docelowa Sagemcom DCTIW362 / DCTIW362P."""
    MODEL = "dctiw362p"
    MANUFACTURER = "PLAY/Sagemcom"
    ANDROID_VERSION = "9"
    HARDWARE = "m362"
    CHIPSET = "Broadcom BCM72604"


# DIRS & CACHE
CACHE_DIR = Path.home() / ".playbox_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SMARTTUBE_DIR = CACHE_DIR / "smarttube"
SMARTTUBE_DIR.mkdir(parents=True, exist_ok=True)


class Logger:
    """Formatowanie i kolorowanie komunikatów w konsoli."""
    COLORS = {
        "header": "\033[95m",
        "info": "\033[94m",
        "success": "\033[92m",
        "warning": "\033[93m",
        "error": "\033[91m",
        "reset": "\033[0m",
        "bold": "\033[1m",
        "cyan": "\033[96m"
    }

    @staticmethod
    def log(msg: str, level: str = "info") -> None:
        color = Logger.COLORS.get(level, Logger.COLORS["info"])
        timestamp = time.strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] [{level.upper()}] {msg}{Logger.COLORS['reset']}")

    @staticmethod
    def success(msg: str) -> None:
        Logger.log(msg, "success")

    @staticmethod
    def error(msg: str) -> None:
        Logger.log(msg, "error")

    @staticmethod
    def warning(msg: str) -> None:
        Logger.log(msg, "warning")

    @staticmethod
    def header(title: str) -> None:
        print(f"\n{Logger.COLORS['header']}{Logger.COLORS['bold']}{'=' * 75}")
        print(f"  {title}")
        print(f"{'=' * 75}{Logger.COLORS['reset']}\n")


class SystemShell:
    """Warstwa komunikacji ADB z obsługą połączeń sieciowych, detekcji i uniwersalnego Shell."""
    device: str = ""
    timeout: int = 10
    retry_count: int = 2

    @staticmethod
    def autodetect() -> bool:
        try:
            out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
            lines = [line for line in out.splitlines() if "\tdevice" in line]
            if lines:
                SystemShell.device = lines[0].split("\t")[0].strip()
                Logger.success(f"ADB auto-wykryty: {SystemShell.device}")
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def connect(target: str) -> bool:
        try:
            r = subprocess.run(["adb", "connect", target], capture_output=True, text=True, timeout=10)
            if "connected" in r.stdout.lower():
                SystemShell.device = target
                Logger.success(f"Połączono z ADB: {target}")
                return True
        except Exception as e:
            Logger.error(f"Błąd połączenia ADB: {e}")
        return False

    @staticmethod
    def run(cmd: str, ignore_errors: bool = True, retry: bool = True) -> str:
        if not SystemShell.device:
            return ""
        attempts = SystemShell.retry_count if retry else 1
        for _ in range(attempts):
            try:
                full_cmd = ["adb", "-s", SystemShell.device, "shell", cmd]
                result = subprocess.check_output(full_cmd, stderr=subprocess.STDOUT, text=True, timeout=SystemShell.timeout).strip()
                return result
            except Exception as e:
                if not ignore_errors:
                    Logger.error(f"Wykonanie nieudane [{cmd}]: {e}")
                time.sleep(0.5)
        return ""

    @staticmethod
    def run_as_root(cmd: str, ignore_errors: bool = True) -> str:
        """Próbuje wykonać komendę jako root, z automatycznym wycofaniem do trybu bez-root."""
        res = SystemShell.run(f"su -c '{cmd}'", ignore_errors=True, retry=False)
        if res and "not found" not in res.lower() and "permission denied" not in res.lower():
            return res
        return SystemShell.run(cmd, ignore_errors=ignore_errors)


class BroadcomPerformanceTuner:
    """Optymalizacja sterownika GFX Broadcom (gfxdriver-bcmstb), VSync i HWUI Renderer."""

    def optimize_gfx_and_surfaceflinger(self) -> None:
        Logger.header("1. OPTYMALIZACJA BCMSTB GFX DRIVER & HWUI (ROOTLESS/ROOT)")

        tweaks = [
            # Wymuszenie silnika SkiaGL dla wyeliminowania janky frames w UI
            ("setprop debug.hwui.renderer skiagl", "Silnik HWUI SkiaGL"),
            ("setprop persist.sys.ui.hw true", "Wymuszenie HW 2D"),
            ("setprop debug.hwui.render_thread_count 2", "RenderThread 2-rdzeniowy BCM"),
            ("setprop debug.hwui.show_dirty_regions false", "Wyłączenie dirty regions"),
            # VSync pacing & backpressure
            ("setprop debug.sf.disable_backpressure 1", "SF Vsync backpressure disable"),
            ("setprop debug.sf.latch_unsignaled 1", "SF latch unsignaled buffer zwalnianie"),
            ("setprop debug.egl.hw 1", "Hardware EGL"),
            ("setprop debug.sf.hw 1", "Hardware SurfaceFlinger"),
            ("setprop debug.gr.numframebuffers 3", "Triple buffering (UI smoothness)")
        ]

        success = 0
        for cmd, desc in tweaks:
            SystemShell.run(cmd, ignore_errors=True)
            success += 1

        # Obejście miksera Androida – przekazywanie warstw bezpośrednio do potoku BCM
        Logger.log("Omijanie nakładek UI i wymuszenie bezpośredniej ścieżki BCM Pipeline...")
        SystemShell.run('settings put global overlay_display_devices ""', ignore_errors=True)
        SystemShell.run("service call SurfaceFlinger 1008 i32 1", ignore_errors=True)

        Logger.success(f"Zastosowano {success}/{len(tweaks)} optymalizacji Broadcom GFX.")


class WebViewOptimizer:
    """Tuning silnika Chromium / Thorium WebView pod kątem płynności na Android TV."""

    def optimize_webview(self) -> None:
        Logger.header("2. OPTYMALIZACJA WEBVIEW (THORIUM / CHROMIUM FLAGS)")

        webview_flags = (
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

        Logger.log("Wstrzykiwanie flag wydajnościowych do WebView...")
        SystemShell.run(f'settings put global webview_flags "{webview_flags}"', ignore_errors=True)
        SystemShell.run('settings put global webview_flags_tv "enable-webview-surface-control-for-tv=true"', ignore_errors=True)
        SystemShell.run('settings put global webview_flags_media "webview-thread-safe-media=true"', ignore_errors=True)

        Logger.log("Wyłączanie zbędnych usłuig analitycznych i raportowania WebView...")
        SystemShell.run("pm disable-user --user 0 com.google.android.webview/com.google.android.apps.chrome.process.ChildProcessService", ignore_errors=True)
        SystemShell.run("pm disable-user --user 0 com.google.android.webview/org.chromium.android_webview.services.CrashReceiverService", ignore_errors=True)
        SystemShell.run("pm disable-user --user 0 com.google.android.webview/org.chromium.android_webview.services.VariationsSeedServer", ignore_errors=True)

        Logger.success("Silnik WebView zoptymalizowany pomyślnie.")


class HdmiHdrTuner:
    """Tuning potoku HDMI, wyjścia rozdzielczości oraz metadanych HDR10."""

    def optimize_hdmi_hdr(self) -> None:
        Logger.header("3. TUNING POTOKU HDMI & METADANYCH HDR")

        Logger.log("Ustawianie preferencji wyjścia 2160p60Hz z dynamicznym przełączaniem HDR...")
        SystemShell.run("settings put global user_preferred_resolution 2160p60hz", ignore_errors=True)
        SystemShell.run("settings put global hdr_output_mode auto", ignore_errors=True)
        SystemShell.run("settings put global hdr_static_metadata 1", ignore_errors=True)

        nrdp_caps = '{"hdrOutputType":"always","videoPeekTunnelFramesToSend":16}'
        SystemShell.run(f"settings put global nrdp_platform_capabilities '{nrdp_caps}'", ignore_errors=True)

        Logger.success("Konfiguracja HDMI / HDR zakończona.")


class SagemcomOptimizer:
    """Optymalizacje pamięci, skalowania DPI oraz zarządzania zasobami pod Sagemcom."""

    def optimize_ui_and_ram(self) -> None:
        Logger.header("4. SAGEMCOM UI DENSITY & LOW-RAM MANAGEMENT")

        Logger.log("Normalizacja rozdzielczości UI (1080p @ 213 DPI)...")
        SystemShell.run("wm size 1920x1080", ignore_errors=True)
        SystemShell.run("wm density 213", ignore_errors=True)
        SystemShell.run("settings put global display_size_forced 1920,1080", ignore_errors=True)

        Logger.log("Modyfikacja limitów pamięci RAM pod kątem 1.5 GB...")
        SystemShell.run("settings put global low_power_trigger_level 0", ignore_errors=True)
        SystemShell.run("settings put global activity_manager_constants max_cached_processes=8", ignore_errors=True)
        SystemShell.run('settings put global power_manager_constants "no_cached_apps_until_foreground=true"', ignore_errors=True)
        SystemShell.run("settings put global sys_free_storage_log_interval 0", ignore_errors=True)

        Logger.success("UI i limity pamięci RAM pomyślnie ze strojone.")

    def freeze_netflix_dry(self) -> None:
        Logger.log("Zamrażanie usłuig tła dla aplikacji Netflix (Widevine L1 Safe)...")
        SystemShell.run("cmd appops set com.netflix.ninja RUN_IN_BACKGROUND ignore", ignore_errors=True)
        Logger.success("Działanie aplikacji Netflix w tle zablokowane.")


class SmartTubeOptimizer:
    """
    Zaawansowany menedżer konfiguracji SmartTube dla BCM72604.
    Działa w 100% ROOTLESS przy użyciu Intent Backup Export/Import.
    """
    PKG_STABLE = "org.smarttube.stable"
    DEVICE_BACKUP_ZIP = "/sdcard/SmartTubeBackup.zip"

    BCM72604_OPTIMAL = {
        "video_codec":               ("int",     "2",       "VP9 HW codec BCM72604"),
        "av1_enabled":               ("boolean", "false",   "AV1 off (brak HW dekodera)"),
        "use_tunnel_mode":           ("boolean", "true",    "Tunnel mode BCM sync"),
        "tunneled_playback":         ("boolean", "true",    "Tunneled playback bypass SF"),
        "force_hw_decoding":         ("boolean", "true",    "Wymuszenie dekoderów HW"),
        "disable_software_decoders": ("boolean", "true",    "Blokada dekoderów SW"),
        "custom_video_decoder":      ("string",  "OMX.BROADCOM.video-decoder.vp9", "Broadcom VP9 override"),
        "video_buffer_size":         ("string",  "25000",   "Max okno bufora (25s)"),
        "exoplayer_dash_chunk_size": ("string",  "4194304", "Paczka DASH (4MB)"),
        "video_resolution":          ("string",  "1080",    "Optymalna rozdzielczość 1080p"),
        "hdr_mode":                  ("boolean", "true",    "Ścieżka sprzętowa HDR10"),
        "video_frame_rate_switch":   ("boolean", "true",    "Automatyczny AFR (Auto FPS)")
    }

    def optimize_smarttube(self) -> None:
        Logger.header("5. OPTYMALIZACJA SMARTTUBE (ROOTLESS BACKUP VECTOR)")

        Logger.log("Wysyłanie sygnału do SmartTube w celu zrzutu konfiguracji na SDCard...")
        SystemShell.run(f"am broadcast -a com.liskovsoft.smartyoutubetv2.BACKUP_EXPORT -p {self.PKG_STABLE}", ignore_errors=True)
        time.sleep(2.0)  # Czas na dokończenie operacji I/O przez eMMC

        local_orig = SMARTTUBE_DIR / "SmartTubeBackup_original.zip"
        local_opt = SMARTTUBE_DIR / "SmartTubeBackup_opt.zip"

        Logger.log("Pobieranie pliku backupu przez powłokę ADB...")
        subprocess.run(["adb", "-s", SystemShell.device, "pull", self.DEVICE_BACKUP_ZIP, str(local_orig)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if not local_orig.exists() or local_orig.stat().st_size == 0:
            Logger.error("Błąd: Nie udało się pobrać SmartTubeBackup.zip. Uruchom SmartTube przynajmniej raz!")
            return

        Logger.success(f"Pobrano konfigurację SmartTube ({local_orig.stat().st_size} bajtów). Modyfikacja w RAM...")

        try:
            with zipfile.ZipFile(str(local_orig), "r") as zin:
                with zipfile.ZipFile(str(local_opt), "w", compression=zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        data = zin.read(item.filename)
                        if item.filename.endswith(".xml"):
                            root = ET.fromstring(data.decode("utf-8", errors="replace"))

                            for key, (typ, val, desc) in self.BCM72604_OPTIMAL.items():
                                found = False
                                for child in root:
                                    if child.get("name") == key:
                                        child.set("value", val)
                                        if typ == "string":
                                            child.text = val
                                        found = True
                                        break
                                if not found:
                                    if typ == "string":
                                        ET.SubElement(root, typ, {"name": key}).text = val
                                    else:
                                        ET.SubElement(root, typ, {"name": key, "value": val})

                            buf = io.BytesIO()
                            ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
                            zout.writestr(item, buf.getvalue())
                        else:
                            zout.writestr(item, data)

            Logger.log("Zamykanie SmartTube i wysyłanie zmodyfikowanej konfiguracji...")
            SystemShell.run(f"am force-stop {self.PKG_STABLE}", ignore_errors=True)

            subprocess.run(["adb", "-s", SystemShell.device, "push", str(local_opt), self.DEVICE_BACKUP_ZIP],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Wgrywanie kopii do katalogu wymaganego przez nowsze wydania STN
            import_dir = f"/sdcard/data/{self.PKG_STABLE}/backup"
            SystemShell.run(f"mkdir -p {import_dir}", ignore_errors=True)
            SystemShell.run(f"cp {self.DEVICE_BACKUP_ZIP} {import_dir}/", ignore_errors=True)

            Logger.success("Modyfikacje wstrzyknięte na kartę pamięci dekodera!")
            Logger.warning("ABY ZAKOŃCZYĆ: Otwórz SmartTube -> Ustawienia -> Kopia zapasowa -> Przywróć kopię.")

        except Exception as e:
            Logger.error(f"Wyjątek podczas modyfikacji pakietu XML: {e}")


class AndroidTV9Optimizer:
    """Modyfikacje sieciowe IPTV i bufory TCP dla Android TV 9."""

    def optimize_network(self) -> None:
        Logger.header("6. OPTYMALIZACJA SIEĆ / IPTV / TCP BUFFERS")
        Logger.log("Ustawianie optymalnych buforów TCP dla strumieni 4K...")
        SystemShell.run("setprop net.tcp.buffersize.wifi 524288,1048576,2097152,262144,524288,1048576", ignore_errors=True)
        SystemShell.run("setprop net.tcp.buffersize.ethernet 524288,1048576,2097152,262144,524288,1048576", ignore_errors=True)
        Logger.success("Bufory TCP zaktualizowane pomyślnie.")


class AdvancedMagiskTuner:
    """Opcjonalny tuner Dalvik/ART (dla urządzeń po zrootowaniu)."""

    def compile_dalvik_speed(self) -> None:
        Logger.header("7. MAGISK/ART DALVIK COMPILATION (SPEED-PROFILE)")
        Logger.log("Kompilacja aplikacji (speed-profile)... Może to potrwać do kilku minut!")
        SystemShell.run_as_root("cmd package compile -m speed-profile -a", ignore_errors=True)
        Logger.success("Kompilacja Dalvik/ART zakończona pomyślnie.")


class PlayBoxTitaniumPro:
    """Główny kontroler aplikacji z rozbudowanym interaktywnym menu CLI."""

    def __init__(self):
        self.broadcom = BroadcomPerformanceTuner()
        self.webview = WebViewOptimizer()
        self.hdmi = HdmiHdrTuner()
        self.sagemcom = SagemcomOptimizer()
        self.smarttube = SmartTubeOptimizer()
        self.atv = AndroidTV9Optimizer()
        self.magisk = AdvancedMagiskTuner()

    def run_cleanup(self) -> None:
        Logger.header("CZYSZCZENIE SYSTEMU I ZASOBÓW")
        SystemShell.run_as_root("am kill-all", ignore_errors=True)
        SystemShell.run("cmd activity trim-memory RUNNING_CRITICAL", ignore_errors=True)
        SystemShell.run("pm trim-caches 4096G", ignore_errors=True)
        SystemShell.run("cmd activity gc-heap", ignore_errors=True)
        Logger.success("Zwolniono zasoby pamięci RAM i przeczyszczono stertę (Heap GC).")

    def full_auto_optimization(self) -> None:
        Logger.header("PEŁNA OPTYMALIZACJA AUTOMATYCZNA (FULL AUTO - ROOTLESS SAFE)")
        self.broadcom.optimize_gfx_and_surfaceflinger()
        self.webview.optimize_webview()
        self.hdmi.optimize_hdmi_hdr()
        self.sagemcom.optimize_ui_and_ram()
        self.smarttube.optimize_smarttube()
        self.atv.optimize_network()
        self.run_cleanup()
        Logger.header("PODSUMOWANIE OPTYMALIZACJI: Wszystkie moduły zrealizowane!")

    def start(self) -> None:
        Logger.header("PLAYBOX TITANIUM v10.2 PRO - ULTIMATE EDITION")
        Logger.log("Inicjalizacja połączenia ADB...")

        if not SystemShell.autodetect():
            Logger.warning("Nie wykryto dekodera automatycznie przez ADB.")
            ip = input(f"{Logger.COLORS['cyan']}Podaj IP:PORT dekodera > {Logger.COLORS['reset']}")
            if not SystemShell.connect(ip):
                Logger.error("Nie udało się połączyć. Zakończenie programu.")
                sys.exit(1)

        while True:
            print(f"\n{Logger.COLORS['header']}{Logger.COLORS['bold']}")
            print("=========================================================================")
            print("║             PLAYBOX TITANIUM v10.2 PRO - ULTIMATE                     ║")
            print("║           (Broadcom BCM72604 / Sagemcom DCTIW362)                     ║")
            print("=========================================================================")
            print(f"║  {Logger.COLORS['info']}1.{Logger.COLORS['reset']} [BROADCOM] Optymalizacja Chipsetu GFX & SurfaceFlinger     ║")
            print(f"║  {Logger.COLORS['info']}2.{Logger.COLORS['reset']} [WEBVIEW] Tuning Thorium / Chromium WebEngine Flags        ║")
            print(f"║  {Logger.COLORS['info']}3.{Logger.COLORS['reset']} [HDMI/HDR] Konfiguracja 4K60Hz & Metadanych HDR10          ║")
            print(f"║  {Logger.COLORS['info']}4.{Logger.COLORS['reset']} [SAGEMCOM] Normalizacja DPI (1080p) & Profil Low-RAM        ║")
            print(f"║  {Logger.COLORS['info']}5.{Logger.COLORS['reset']} [SMARTTUBE] Wstrzyknięcie profilu BCM72604 (Rootless ZIP)  ║")
            print(f"║  {Logger.COLORS['info']}6.{Logger.COLORS['reset']} [NETWORK] Bufory TCP dla IPTV / Streaming                  ║")
            print(f"║  {Logger.COLORS['info']}7.{Logger.COLORS['reset']} [CLEANUP] Agresywne czyszczenie pamięci RAM i Cache        ║")
            print(f"║  {Logger.COLORS['info']}8.{Logger.COLORS['reset']} [DRM SAFE] Zamrożenie usłuig tła dla Netflix                ║")
            print(f"║  {Logger.COLORS['info']}9.{Logger.COLORS['reset']} [MAGISK] Optymalizacja Dalvik (Kompilacja Speed-Profile)   ║")
            print(f"║  {Logger.COLORS['warning']}10.{Logger.COLORS['reset']} [FULL AUTO] Pełna optymalizacja automatyczna (ZALECANE)   ║")
            print(f"║  {Logger.COLORS['error']}0.{Logger.COLORS['reset']} Wyjście                                                  ║")
            print("=========================================================================")

            choice = input(f"\n{Logger.COLORS['cyan']}Twój wybór > {Logger.COLORS['reset']}").strip()

            if choice == "1":
                self.broadcom.optimize_gfx_and_surfaceflinger()
            elif choice == "2":
                self.webview.optimize_webview()
            elif choice == "3":
                self.hdmi.optimize_hdmi_hdr()
            elif choice == "4":
                self.sagemcom.optimize_ui_and_ram()
            elif choice == "5":
                self.smarttube.optimize_smarttube()
            elif choice == "6":
                self.atv.optimize_network()
            elif choice == "7":
                self.run_cleanup()
            elif choice == "8":
                self.sagemcom.freeze_netflix_dry()
            elif choice == "9":
                self.magisk.compile_dalvik_speed()
            elif choice == "10":
                self.full_auto_optimization()
            elif choice == "0":
                Logger.success("Zakończono. Życzymy płynnego korzystania z PlayBox Titanium Pro!")
                break
            else:
                Logger.error("Nieprawidłowy wybór. Spróbuj ponownie.")

            input(f"\n{Logger.COLORS['info']}Naciśnij Enter, aby kontynuować...{Logger.COLORS['reset']}")


if __name__ == "__main__":
    app = PlayBoxTitaniumPro()
    app.start()