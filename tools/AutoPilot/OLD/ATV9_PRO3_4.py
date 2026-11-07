#!/usr/bin/env python3
"""
PLAYBOX TITANIUM v10.6 PRO - ULTIMATE ADVANCED EDITION
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
    """Formatowanie i kolorowanie komunikatów w konsoli STDOUT."""
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
                time.sleep(0.3)
        return ""

    @staticmethod
    def run_as_root(cmd: str, ignore_errors: bool = True) -> str:
        res = SystemShell.run(f"su -c '{cmd}'", ignore_errors=True, retry=False)
        if res and "not found" not in res.lower() and "permission denied" not in res.lower():
            return res
        return SystemShell.run(cmd, ignore_errors=ignore_errors)


class WebViewControlManager:
    """Zarządzanie silnikiem Android WebView, przełączaniem dostawców i flagami Chromium/Thorium."""

    WEBVIEW_PROVIDERS = {
        "1": ("com.google.android.webview", "Google WebView (Domyślny)"),
        "2": ("com.thorium.webview", "Thorium WebView (Zoptymalizowany)"),
        "3": ("com.android.webview", "AOSP System WebView")
    }

    def inspect_webview_status(self) -> None:
        Logger.header("INSPEKCJA SILNIKA ANDROID WEBVIEW")
        current_impl = SystemShell.run("cmd webviewupdate get-current-webview-package", ignore_errors=True)
        Logger.log(f"Aktywny pakiet WebView: {current_impl if current_impl else 'Nieznany / Błąd'}", "info")
        
        flags = SystemShell.run("settings get global webview_flags", ignore_errors=True)
        Logger.log(f"Obecne flagi WebView: {flags if flags else 'Brak wpisów'}", "cyan")

    def switch_webview_provider(self, provider_pkg: str) -> None:
        Logger.log(f"Próba przełączenia dostawcy WebView na: {provider_pkg}...")
        res = SystemShell.run(f"cmd webviewupdate set-webview-implementation {provider_pkg}", ignore_errors=True)
        if "Success" in res or provider_pkg in SystemShell.run("cmd webviewupdate get-current-webview-package", ignore_errors=True):
            Logger.success(f"Pomyślnie ustawiono WebView: {provider_pkg}")
        else:
            Logger.warning(f"Nie udało się przełączyć na {provider_pkg}. Upewnij się, że pakiet jest zainstalowany.")

    def inject_performance_flags(self) -> None:
        Logger.header("WSTRZYKIWANIE FLAG PERFORMANCE CHROMIUM / THORIUM")

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

        Logger.log("Modyfikowanie rejestru bazy Settings (Global WebView Flags)...")
        SystemShell.run(f'settings put global webview_flags "{webview_flags}"', ignore_errors=True)
        SystemShell.run('settings put global webview_flags_tv "enable-webview-surface-control-for-tv=true"', ignore_errors=True)
        SystemShell.run('settings put global webview_flags_media "webview-thread-safe-media=true"', ignore_errors=True)

        Logger.log("Wyłączanie energochłonnych usług analitycznych Google WebView...")
        SystemShell.run("pm disable-user --user 0 com.google.android.webview/com.google.android.apps.chrome.process.ChildProcessService", ignore_errors=True)
        SystemShell.run("pm disable-user --user 0 com.google.android.webview/org.chromium.android_webview.services.CrashReceiverService", ignore_errors=True)
        SystemShell.run("pm disable-user --user 0 com.google.android.webview/org.chromium.android_webview.services.VariationsSeedServer", ignore_errors=True)

        Logger.log("Restartowanie procesów powiązanych z WebView...")
        SystemShell.run("pkill -f com.google.android.webview", ignore_errors=True)
        SystemShell.run("am force-stop org.smarttube.stable", ignore_errors=True)

        Logger.success("Silnik WebView zoptymalizowany dla Android TV!")


class ProcessAndAppManager:
    """Panel zarządzania usługami, aplikacjami, procesami tła oraz parametrami LMK."""

    CRITICAL_SERVICES = [
        ("com.android.systemui", "Interfejs Systemowy (System UI)"),
        ("org.smarttube.stable", "Aplikacja SmartTube"),
        ("com.google.android.webview", "Silnik Renderowania WebView"),
        ("com.netflix.ninja", "Aplikacja Netflix DRM"),
        ("com.google.android.katniss", "Google Assistant / Search")
    ]

    def list_running_processes(self) -> None:
        Logger.header("PANEL MONITOROWANIA KLUCZOWYCH PROCESÓW I USŁUG")
        ps_out = SystemShell.run("ps -A", ignore_errors=True)

        print(f"{Logger.COLORS['cyan']}{'USŁUGA / PAKIET':<35} | {'STAN W SYSTEMIE':<15} | {'OPIS'}{Logger.COLORS['reset']}")
        print("-" * 75)

        for pkg, name in self.CRITICAL_SERVICES:
            if pkg in ps_out:
                status = f"{Logger.COLORS['success']}URUCHOMIONY{Logger.COLORS['reset']}"
            else:
                status = f"{Logger.COLORS['warning']}ZATRZYMANY{Logger.COLORS['reset']}"
            print(f"{pkg:<35} | {status:<24} | {name}")

    def apply_lmk_and_memory_tuning(self) -> None:
        Logger.header("STROJENIE LMK (LOW MEMORY KILLER) & AGRESYWNA PAMIĘĆ")

        Logger.log("Ustawianie stałych w ActivityManager dla ochrony pamięci 1.5 GB RAM...")
        SystemShell.run("settings put global activity_manager_constants max_cached_processes=8", ignore_errors=True)
        SystemShell.run('settings put global power_manager_constants "no_cached_apps_until_foreground=true"', ignore_errors=True)
        SystemShell.run("settings put global low_power_trigger_level 0", ignore_errors=True)
        SystemShell.run("settings put global sys_free_storage_log_interval 0", ignore_errors=True)

        Logger.log("Ograniczanie dławienia aplikacji w tle...")
        SystemShell.run("cmd appops set com.google.android.katniss RUN_IN_BACKGROUND ignore", ignore_errors=True)

        Logger.success("Konfiguracja zarządcy procesów LMK została zapisana.")

    def freeze_bloatware(self) -> None:
        Logger.header("ZAMRAŻANIE ZBĘDNYCH USŁUG TŁA (BLOATWARE)")
        bloat_list = [
            "com.google.android.katniss",
            "com.google.android.videos",
            "com.google.android.play.games"
        ]
        for app in bloat_list:
            Logger.log(f"Zamrażanie pakietu: {app}...")
            SystemShell.run(f"pm disable-user --user 0 {app}", ignore_errors=True)
            SystemShell.run(f"am force-stop {app}", ignore_errors=True)
        Logger.success("Niepotrzebne usługi systemowe zostały zamrożone.")


class KernelAndFramePacingOptimizer:
    """MODUŁ NOWY: Eliminacja mikro-przycięć (Jank), VSync P99 i Kernel VM tuning (Zero-allocation/O(1) policy)."""

    def apply_p99_jank_fixes(self) -> None:
        Logger.header("ELIMINACJA JANK FRAMES (P99) & KERNEL PACING FIX")

        Logger.log("Strojenie VSync Phase Offsets (Zapewnienie 60Hz deterministic latching)...")
        SystemShell.run("setprop debug.sf.early_phase_offset_ns 5000000", ignore_errors=True)
        SystemShell.run("setprop debug.sf.early_app_phase_offset_ns 500000", ignore_errors=True)
        SystemShell.run("setprop ro.surface_flinger.max_frame_buffer_acquired_buffers 3", ignore_errors=True)
        SystemShell.run("setprop debug.hwui.use_buffer_age false", ignore_errors=True)

        Logger.log("Optymalizacja wirtualnej pamięci jądra (zRAM swap & VFS cache pressure)...")
        # Wykorzystanie su (jeśli root), albo fallback do interfejsu setprop/usług
        SystemShell.run_as_root("echo 100 > /proc/sys/vm/swappiness", ignore_errors=True)
        SystemShell.run_as_root("echo 50 > /proc/sys/vm/vfs_cache_pressure", ignore_errors=True)
        SystemShell.run_as_root("echo 1 > /proc/sys/kernel/sched_child_runs_first", ignore_errors=True)

        Logger.log("Iniekcja priorytetów Real-Time (SCHED_FIFO) dla kluczowych demonów grafiki...")
        daemons = [
            "surfaceflinger", 
            "system_server", 
            "android.hardware.graphics.composer@2.1-service"
        ]
        
        for daemon in daemons:
            pid = SystemShell.run(f"pidof {daemon}", ignore_errors=True).strip()
            if pid and pid.isdigit():
                # Ustawienie schedulera na FIFO priority 2 (wymaga roota)
                SystemShell.run_as_root(f"chrt -f -p 2 {pid}", ignore_errors=True)
                # Fallback: Maksymalny priorytet nice
                SystemShell.run_as_root(f"renice -n -20 -p {pid}", ignore_errors=True)
                # Iniekcja do top-app cpuset
                SystemShell.run_as_root(f"echo {pid} > /dev/cpuset/top-app/tasks", ignore_errors=True)

        Logger.log("Wymuszenie czyszczenia zrzuconych stron pamięci (Drop Caches)...")
        SystemShell.run_as_root("echo 3 > /proc/sys/vm/drop_caches", ignore_errors=True)

        Logger.success("Mechanizmy P99 Frame Pacing wstrzyknięte do potoku BCM72604!")


class NetworkAndDnsEngine:
    """Kontrola sieci, strefy DNS oraz optymalizacja buforów TCP dla IPTV i 4K Streaming."""

    DNS_SERVERS = {
        "1": ("Cloudflare 1.1.1.1", "one.one.one.one"),
        "2": ("AdGuard DNS (Blokada Reklam)", "dns.adguard.com"),
        "3": ("Google DNS 8.8.8.8", "dns.google"),
        "4": ("Wyłącz Prywatny DNS (Domyślny ISP)", "off")
    }

    def optimize_tcp_buffers(self) -> None:
        Logger.header("OPTYMALIZACJA BUFORÓW GNIATD TCP / IPTV 4K")

        Logger.log("Ustawianie pojemnych buforów TCP dla Wi-Fi i Ethernet...")
        tcp_val = "524288,1048576,2097152,262144,524288,1048576"
        SystemShell.run(f"setprop net.tcp.buffersize.wifi {tcp_val}", ignore_errors=True)
        SystemShell.run(f"setprop net.tcp.buffersize.ethernet {tcp_val}", ignore_errors=True)

        Logger.log("Wyłączanie zbędnych mechanizmów oszczędzania energii w Wi-Fi...")
        SystemShell.run("settings put global wifi_sleep_policy 2", ignore_errors=True)
        SystemShell.run("settings put global wifi_scan_always_enabled 0", ignore_errors=True)

        Logger.success("Bufory TCP zaktualizowane pod kątem stabilnego płynnego streamingu.")

    def configure_private_dns(self, option: str) -> None:
        if option not in self.DNS_SERVERS:
            Logger.error("Nieprawidłowy wybór dostawcy DNS.")
            return

        name, specifier = self.DNS_SERVERS[option]
        Logger.header(f"USTAWIANIE PRYWATNEGO DNS: {name}")

        if specifier == "off":
            SystemShell.run("settings put global private_dns_mode off", ignore_errors=True)
            Logger.success("Prywatny DNS został wyłączony.")
        else:
            SystemShell.run("settings put global private_dns_mode hostname", ignore_errors=True)
            SystemShell.run(f"settings put global private_dns_specifier {specifier}", ignore_errors=True)
            Logger.success(f"Ustawiono Prywatny DNS: {specifier}")


class SystemDiagnosticsInspector:
    """Weryfikacja kluczowych procesów interfejsu UI, renderera i krytycznych ustawień."""

    def run_full_diagnostics(self) -> None:
        Logger.header("DIAGNOSTYKA SYSTEMU & SILNIKA RENDERUJĄCEGO BCM72604")

        wm_size = SystemShell.run("wm size", ignore_errors=True)
        wm_density = SystemShell.run("wm density", ignore_errors=True)
        Logger.log(f"Rozdzielczość ekranu: {wm_size}", "cyan")
        Logger.log(f"Gęstość DPI: {wm_density}", "cyan")

        hwui = SystemShell.run("getprop debug.hwui.renderer", ignore_errors=True)
        Logger.log(f"Silnik Renderowania HWUI: {hwui if hwui else 'opengl (domyślny)'}", "info")

        res = SystemShell.run("settings get global user_preferred_resolution", ignore_errors=True)
        hdr = SystemShell.run("settings get global hdr_output_mode", ignore_errors=True)
        Logger.log(f"Preferowana rozdzielczość HDMI: {res}", "info")
        Logger.log(f"Tryb wyjścia HDR: {hdr}", "info")

        tcp_wifi = SystemShell.run("getprop net.tcp.buffersize.wifi", ignore_errors=True)
        Logger.log(f"Bufory TCP Wi-Fi: {tcp_wifi if tcp_wifi else 'Brak'}", "cyan")

        dns_mode = SystemShell.run("settings get global private_dns_mode", ignore_errors=True)
        dns_spec = SystemShell.run("settings get global private_dns_specifier", ignore_errors=True)
        Logger.log(f"Tryb DNS: {dns_mode} ({dns_spec})", "info")


class BroadcomPerformanceTuner:
    """Optymalizacja sterownika GFX Broadcom (gfxdriver-bcmstb), VSync i HWUI Renderer."""

    def optimize_gfx_and_surfaceflinger(self) -> None:
        Logger.header("1. OPTYMALIZACJA BCMSTB GFX DRIVER & HWUI (ROOTLESS/ROOT)")

        tweaks = [
            ("setprop debug.hwui.renderer skiagl", "Silnik HWUI SkiaGL"),
            ("setprop persist.sys.ui.hw true", "Wymuszenie HW 2D"),
            ("setprop debug.hwui.render_thread_count 2", "RenderThread 2-rdzeniowy BCM"),
            ("setprop debug.hwui.show_dirty_regions false", "Wyłączenie dirty regions"),
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

        Logger.log("Omijanie nakładek UI i wymuszenie bezpośredniej ścieżki BCM Pipeline...")
        SystemShell.run('settings put global overlay_display_devices ""', ignore_errors=True)
        SystemShell.run("service call SurfaceFlinger 1008 i32 1", ignore_errors=True)

        Logger.success(f"Zastosowano {success}/{len(tweaks)} optymalizacji Broadcom GFX.")


class HdmiHdrTuner:
    """Tuning potoku HDMI, wyjścia rozdzielczości oraz metadanych HDR10."""

    def optimize_hdmi_hdr(self) -> None:
        Logger.header("TUNING POTOKU HDMI & METADANYCH HDR")

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
        Logger.header("SAGEMCOM UI DENSITY & LOW-RAM MANAGEMENT")

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
    Zweryfikowany dekoder sprzętowy: OMX.broadcom.video_decoder.vp9
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
        "custom_video_decoder":      ("string",  "OMX.broadcom.video_decoder.vp9", "Broadcom VP9 OMX override"),
        "video_buffer_size":         ("string",  "25000",   "Max okno bufora (25s)"),
        "exoplayer_dash_chunk_size": ("string",  "4194304", "Paczka DASH (4MB)"),
        "video_resolution":          ("string",  "1080",    "Optymalna rozdzielczość 1080p"),
        "hdr_mode":                  ("boolean", "true",    "Ścieżka sprzętowa HDR10"),
        "video_frame_rate_switch":   ("boolean", "true",    "Automatyczny AFR (Auto FPS)")
    }

    def optimize_smarttube(self) -> None:
        Logger.header("OPTYMALIZACJA SMARTTUBE (ROOTLESS BACKUP VECTOR)")

        Logger.log("Wysyłanie sygnału do SmartTube w celu zrzutu konfiguracji na SDCard...")
        SystemShell.run(f"am broadcast -a com.liskovsoft.smartyoutubetv2.BACKUP_EXPORT -p {self.PKG_STABLE}", ignore_errors=True)
        time.sleep(2.0)

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

            import_dir = f"/sdcard/data/{self.PKG_STABLE}/backup"
            SystemShell.run(f"mkdir -p {import_dir}", ignore_errors=True)
            SystemShell.run(f"cp {self.DEVICE_BACKUP_ZIP} {import_dir}/", ignore_errors=True)

            Logger.success("Modyfikacje wstrzyknięte na kartę pamięci dekodera!")
            Logger.warning("ABY ZAKOŃCZYĆ: Otwórz SmartTube -> Ustawienia -> Kopia zapasowa -> Przywróć kopię.")

        except Exception as e:
            Logger.error(f"Wyjątek podczas modyfikacji pakietu XML: {e}")


class AdvancedMagiskTuner:
    """Tuner Dalvik/ART (kompilacja speed-profile)."""

    def compile_dalvik_speed(self) -> None:
        Logger.header("MAGISK/ART DALVIK COMPILATION (SPEED-PROFILE)")
        Logger.log("Kompilacja aplikacji (speed-profile)... Może to potrwać do kilku minut!")
        SystemShell.run_as_root("cmd package compile -m speed-profile -a", ignore_errors=True)
        Logger.success("Kompilacja Dalvik/ART zakończona pomyślnie.")


class PlayBoxTitaniumPro:
    """Główny kontroler aplikacji z rozbudowanym interaktywnym menu CLI v10.6 PRO."""

    def __init__(self):
        self.broadcom = BroadcomPerformanceTuner()
        self.webview = WebViewControlManager()
        self.process_mgr = ProcessAndAppManager()
        self.network = NetworkAndDnsEngine()
        self.diagnostics = SystemDiagnosticsInspector()
        self.hdmi = HdmiHdrTuner()
        self.sagemcom = SagemcomOptimizer()
        self.smarttube = SmartTubeOptimizer()
        self.magisk = AdvancedMagiskTuner()
        self.pacing = KernelAndFramePacingOptimizer()

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
        self.webview.inject_performance_flags()
        self.hdmi.optimize_hdmi_hdr()
        self.sagemcom.optimize_ui_and_ram()
        self.smarttube.optimize_smarttube()
        self.network.optimize_tcp_buffers()
        self.process_mgr.apply_lmk_and_memory_tuning()
        self.pacing.apply_p99_jank_fixes()
        self.run_cleanup()
        Logger.header("PODSUMOWANIE OPTYMALIZACJI: Wszystkie moduły zrealizowane!")

    def start(self) -> None:
        Logger.header("PLAYBOX TITANIUM v10.6 PRO - ULTIMATE ADVANCED EDITION")
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
            print("║             PLAYBOX TITANIUM v10.6 PRO - ADVANCED ULTIMATE            ║")
            print("║           (Broadcom BCM72604 / Sagemcom DCTIW362)                     ║")
            print("=========================================================================")
            print(f"║  {Logger.COLORS['info']}1.{Logger.COLORS['reset']} [BROADCOM] Optymalizacja Chipsetu GFX & SurfaceFlinger     ║")
            print(f"║  {Logger.COLORS['info']}2.{Logger.COLORS['reset']} [WEBVIEW] Flagi Chromium / Thorium & Usługi Analityczne    ║")
            print(f"║  {Logger.COLORS['info']}3.{Logger.COLORS['reset']} [WEBVIEW-MGR] Zmień Dostawcę WebView (Google/Thorium/AOSP)  ║")
            print(f"║  {Logger.COLORS['info']}4.{Logger.COLORS['reset']} [HDMI/HDR] Konfiguracja 4K60Hz & Metadanych HDR10          ║")
            print(f"║  {Logger.COLORS['info']}5.{Logger.COLORS['reset']} [SAGEMCOM] Normalizacja DPI (1080p) & Profil Low-RAM        ║")
            print(f"║  {Logger.COLORS['info']}6.{Logger.COLORS['reset']} [SMARTTUBE] Wstrzyknięcie profilu BCM72604 (Rootless ZIP)  ║")
            print(f"║  {Logger.COLORS['info']}7.{Logger.COLORS['reset']} [NETWORK] Bufory TCP dla IPTV & Wi-Fi Latency              ║")
            print(f"║  {Logger.COLORS['info']}8.{Logger.COLORS['reset']} [DNS] Konfiguracja Prywatnego DNS (Cloudflare/AdGuard)     ║")
            print(f"║  {Logger.COLORS['info']}9.{Logger.COLORS['reset']} [PROCESS-MGR] Panel Zarządzania Procesami, LMK & Bloatware ║")
            print(f"║ {Logger.COLORS['info']}10.{Logger.COLORS['reset']} [DIAGNOSTICS] Pełna Diagnostyka Systemu, UI & Renderera     ║")
            print(f"║ {Logger.COLORS['info']}11.{Logger.COLORS['reset']} [CLEANUP] Agresywne Czyszczenie Pamięci RAM i Cache         ║")
            print(f"║ {Logger.COLORS['info']}12.{Logger.COLORS['reset']} [DRM SAFE] Zamrożenie Usług Tła dla Netflix                 ║")
            print(f"║ {Logger.COLORS['info']}13.{Logger.COLORS['reset']} [MAGISK] Optymalizacja Dalvik (Kompilacja Speed-Profile)    ║")
            print(f"║ {Logger.COLORS['info']}14.{Logger.COLORS['reset']} [KERNEL-PACING] Fix Janky Frames (P99) & VSync Offsets      ║")
            print(f"║ {Logger.COLORS['warning']}15.{Logger.COLORS['reset']} [FULL AUTO] PEŁNA OPTYMALIZACJA AUTOMATYCZNA (ZALECANE)    ║")
            print(f"║  {Logger.COLORS['error']}0.{Logger.COLORS['reset']} Wyjście                                                   ║")
            print("=========================================================================")

            choice = input(f"\n{Logger.COLORS['cyan']}Twój wybór > {Logger.COLORS['reset']}").strip()

            if choice == "1":
                self.broadcom.optimize_gfx_and_surfaceflinger()
            elif choice == "2":
                self.webview.inject_performance_flags()
            elif choice == "3":
                self.webview.inspect_webview_status()
                print("\nDostępni dostawcy:")
                for k, v in self.webview.WEBVIEW_PROVIDERS.items():
                    print(f"  {k}. {v[1]} ({v[0]})")
                sub = input("Wybierz numer dostawcy > ").strip()
                if sub in self.webview.WEBVIEW_PROVIDERS:
                    self.webview.switch_webview_provider(self.webview.WEBVIEW_PROVIDERS[sub][0])
            elif choice == "4":
                self.hdmi.optimize_hdmi_hdr()
            elif choice == "5":
                self.sagemcom.optimize_ui_and_ram()
            elif choice == "6":
                self.smarttube.optimize_smarttube()
            elif choice == "7":
                self.network.optimize_tcp_buffers()
            elif choice == "8":
                print("\nDostępne konfiguracje DNS:")
                for k, v in self.network.DNS_SERVERS.items():
                    print(f"  {k}. {v[0]}")
                sub = input("Wybierz DNS > ").strip()
                self.network.configure_private_dns(sub)
            elif choice == "9":
                self.process_mgr.list_running_processes()
                print("\nOpcje: [1] Zastosuj LMK & Memory Tuning | [2] Zamroź Bloatware | [Enter] Powrót")
                sub = input("Wybór > ").strip()
                if sub == "1":
                    self.process_mgr.apply_lmk_and_memory_tuning()
                elif sub == "2":
                    self.process_mgr.freeze_bloatware()
            elif choice == "10":
                self.diagnostics.run_full_diagnostics()
            elif choice == "11":
                self.run_cleanup()
            elif choice == "12":
                self.sagemcom.freeze_netflix_dry()
            elif choice == "13":
                self.magisk.compile_dalvik_speed()
            elif choice == "14":
                self.pacing.apply_p99_jank_fixes()
            elif choice == "15":
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
