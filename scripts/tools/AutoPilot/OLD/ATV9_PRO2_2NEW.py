#!/usr/bin/env python3
"""
PLAYBOX TITANIUM v10.3 PRO - SMARTTUBE MOD (ULTIMATE ROOTLESS SUITE)
Target Device: Sagemcom DCTIW362 / DCTIW362P (Play Now TV Box V1)
SoC: Broadcom BCM72604 | Android TV 9 (Pie) API 28
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


# =========================================================
# KONFIGURACJA ŚRODOWISKA
# =========================================================
CACHE_DIR = Path.home() / ".playbox_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SMARTTUBE_DIR = CACHE_DIR / "smarttube"
SMARTTUBE_DIR.mkdir(parents=True, exist_ok=True)


class Logger:
    """Moduł logowania z obsługą ANSI (Cyberpunk/Hacker style)."""
    COLORS = {
        "header": "\033[95m",
        "info": "\033[94m",
        "success": "\033[92m",
        "warning": "\033[93m",
        "error": "\033[91m",
        "reset": "\033[0m",
        "bold": "\033[1m",
        "cyan": "\033[96m",
        "magenta": "\033[35m"
    }

    @staticmethod
    def log(msg: str, level: str = "info") -> None:
        color = Logger.COLORS.get(level, Logger.COLORS["info"])
        timestamp = time.strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] [{level.upper()}] {msg}{Logger.COLORS['reset']}")

    @staticmethod
    def success(msg: str): Logger.log(msg, "success")
    @staticmethod
    def error(msg: str): Logger.log(msg, "error")
    @staticmethod
    def warning(msg: str): Logger.log(msg, "warning")
    @staticmethod
    def header(title: str):
        print(f"\n{Logger.COLORS['header']}{Logger.COLORS['bold']}{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}{Logger.COLORS['reset']}\n")


class SystemShell:
    """Most ADB: Synchroniczne wykonywanie poleceń i parsowanie wyjścia."""
    device: str = ""
    timeout: int = 12

    @staticmethod
    def autodetect() -> bool:
        try:
            out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
            lines = [line for line in out.splitlines() if "\tdevice" in line]
            if lines:
                SystemShell.device = lines[0].split("\t")[0].strip()
                Logger.success(f"ADB Auto-Connect: {SystemShell.device}")
                return True
        except: pass
        return False

    @staticmethod
    def connect(target: str) -> bool:
        try:
            r = subprocess.run(["adb", "connect", target], capture_output=True, text=True, timeout=10)
            if "connected" in r.stdout.lower() or "already" in r.stdout.lower():
                SystemShell.device = target
                Logger.success(f"Połączono z ADB: {target}")
                return True
        except Exception as e:
            Logger.error(f"Błąd połączenia: {e}")
        return False

    @staticmethod
    def run(cmd: str, ignore_errors: bool = True, silent: bool = False) -> str:
        if not SystemShell.device: return ""
        try:
            full_cmd = ["adb", "-s", SystemShell.device, "shell", cmd]
            res = subprocess.check_output(full_cmd, stderr=subprocess.STDOUT, text=True, timeout=SystemShell.timeout).strip()
            return res
        except subprocess.CalledProcessError as e:
            if not ignore_errors and not silent:
                Logger.error(f"Błąd wykonania: {cmd}\n{e.output}")
            return e.output.strip() if hasattr(e, 'output') else ""
        except Exception as e:
            if not ignore_errors and not silent: Logger.error(f"Wyjątek I/O: {e}")
            return ""

    @staticmethod
    def run_as_root(cmd: str) -> str:
        res = SystemShell.run(f"su -c '{cmd}'", silent=True)
        if "not found" not in res.lower() and "permission denied" not in res.lower():
            return res
        return SystemShell.run(cmd)


# =========================================================
# MODUŁY OPTYMALIZACJI I KONTROLI (V10.3)
# =========================================================

class DiagnosticEngine:
    """Weryfikacja krytycznych procesów UI, Silnika i Systemu."""
    
    def run_full_diagnostics(self) -> None:
        Logger.header("DIAGNOSTYKA SYSTEMU: KRYTYCZNE PROCESY & UI")
        
        # 1. System UI & SurfaceFlinger
        sysui_pid = SystemShell.run("pidof com.android.systemui")
        if sysui_pid: Logger.success(f"[UI] SystemUI działa stabilnie (PID: {sysui_pid})")
        else: Logger.error("[UI] UWAGA: SystemUI nie odpowiada lub jest restartowany!")

        sf_status = SystemShell.run("service check SurfaceFlinger")
        if "found" in sf_status: Logger.success("[GFX] SurfaceFlinger (Kompozytor) aktywny.")
        else: Logger.error("[GFX] SurfaceFlinger zgłasza anomalię!")

        # 2. SmartTube
        st_pid = SystemShell.run("pidof org.smarttube.stable")
        if st_pid: Logger.success(f"[APP] SmartTube jest aktualnie Uruchomiony (PID: {st_pid})")
        else: Logger.warning("[APP] SmartTube jest w stanie spoczynku (Zamknięty/Uśpiony).")

        # 3. Aktywny WebView
        wv_info = SystemShell.run("dumpsys webviewupdate | grep 'Current WebView package'")
        Logger.info(f"[WEBVIEW] Status: {wv_info.strip()}")

        # 4. Status LMK (Low Memory Killer)
        lmk_params = SystemShell.run("settings get global activity_manager_constants")
        if "null" not in lmk_params: Logger.info(f"[LMK] Aktywne flagi pamięci: {lmk_params}")
        else: Logger.warning("[LMK] Brak nadpisanych flag. Używany standardowy profil OOM.")

        # 5. Status DNS
        dns_mode = SystemShell.run("settings get global private_dns_mode")
        dns_spec = SystemShell.run("settings get global private_dns_specifier")
        Logger.info(f"[NET] Tryb DNS: {dns_mode if dns_mode != 'null' else 'Standardowy'}")
        if dns_spec != "null": Logger.info(f"[NET] Serwer DoT (DNS-over-TLS): {dns_spec}")


class NetworkAndDnsController:
    """Zarządzanie strefą DNS, buforami TCP oraz flagami sieciowymi."""
    
    def optimize_tcp_buffers(self) -> None:
        Logger.log("Wstrzykiwanie flag buforowania TCP (Streaming 4K)...")
        SystemShell.run("setprop net.tcp.buffersize.wifi 524288,1048576,2097152,262144,524288,2097152")
        SystemShell.run("setprop net.tcp.buffersize.ethernet 524288,1048576,2097152,262144,524288,2097152")
        Logger.success("Rozmiar buforów TCP zmodyfikowany.")

    def set_custom_dns(self, provider: str) -> None:
        Logger.log(f"Zmieniam strefę DNS na: {provider} (DoT)...")
        if provider == "Cloudflare":
            host = "1dot1dot1dot1.cloudflare-dns.com"
        elif provider == "Google":
            host = "dns.google"
        elif provider == "AdGuard":
            host = "dns.adguard-dns.com"
        elif provider == "Off":
            SystemShell.run("settings put global private_dns_mode off")
            SystemShell.run("settings delete global private_dns_specifier")
            Logger.success("Prywatny DNS wyłączony. Wrócono do ustawień DHCP.")
            return
        else:
            return

        SystemShell.run("settings put global private_dns_mode hostname")
        SystemShell.run(f"settings put global private_dns_specifier {host}")
        Logger.success(f"Ruch sieciowy przekierowany przez: {host}")


class ProcessAndLmkManager:
    """Zarządzanie aplikacjami, usługami tła i Low Memory Killer (LMK)."""
    
    def apply_aggressive_lmk(self) -> None:
        Logger.log("Modyfikacja flag Low Memory Killer (LMK)...")
        # Optymalizacja pod 1.5GB RAM - trzymaj max 6 aplikacji w cache, agresywnie zwalniaj pamięć pustych procesów
        lmk_flags = "max_cached_processes=6,background_settle_time=60000,fgservice_min_report_time=3000"
        SystemShell.run(f'settings put global activity_manager_constants "{lmk_flags}"')
        SystemShell.run("settings put global low_power_trigger_level 0")
        Logger.success("Flagi LMK zaktualizowane. Profil RAM: Agresywny.")

    def freeze_bloatware(self) -> None:
        Logger.log("Zamrażanie usłuig tła oraz systemowego Bloatware...")
        apps_to_freeze = [
            "com.netflix.ninja", 
            "com.amazon.amazonvideo.livingroom",
            "com.google.android.play.games",
            "com.google.android.videos"
        ]
        
        for app in apps_to_freeze:
            # ADB Rootless sposób na zablokowanie działania w tle, bez wyłączania apki (DRM Safe)
            SystemShell.run(f"cmd appops set {app} RUN_IN_BACKGROUND ignore")
            # Dodatkowy disable-user jeśli nie używamy tych apek w ogóle
            # SystemShell.run(f"pm disable-user --user 0 {app}") 
            Logger.info(f"Ograniczono procesy w tle dla: {app}")
            
        Logger.success("Zamrażanie zakończone pomyślnie.")


class WebViewManager:
    """Panel kontrolny dla komponentu renderującego UI Androida."""
    
    def apply_flags(self) -> None:
        Logger.log("Wstrzykiwanie flag kompilatora dla WebView (Accelerated Canvas, Rasterization)...")
        flags = (
            "ignore-gpu-blocklist=true "
            "enable-gpu-rasterization=true "
            "webview-accelerate-small-canvases=true "
            "num-raster-threads=2 "
            "webview-thread-safe-media=true "
            "enable-webview-surface-control-for-tv=true "
            "webview-disable-package-allowlist-throttling=true"
        )
        SystemShell.run(f'settings put global webview_flags "{flags}"')
        Logger.success("Flagi dla WebView zaktualizowane.")

    def change_implementation(self, package_name: str) -> None:
        Logger.log(f"Próba zmiany silnika WebView na: {package_name}...")
        res = SystemShell.run(f"cmd webviewupdate set-webview-implementation {package_name}")
        if "Success" in res:
            Logger.success("Silnik WebView zmieniony pomyślnie!")
        else:
            Logger.error(f"Nie udało się zmienić WebView. Pakiet może nie być zainstalowany. Log: {res}")


class BroadcomTuner:
    """Niskopoziomowy dostęp do sprzętowego kompozytora BCM."""
    
    def optimize(self) -> None:
        Logger.log("Aplikacja optymalizacji Broadcom GFX / SkiaGL...")
        SystemShell.run("setprop debug.hwui.renderer skiagl")
        SystemShell.run("setprop persist.sys.ui.hw true")
        SystemShell.run("setprop debug.hwui.render_thread_count 2")
        SystemShell.run("setprop debug.sf.disable_backpressure 1")
        
        # HDMI HDR
        SystemShell.run("settings put global user_preferred_resolution 2160p60hz")
        SystemShell.run("settings put global hdr_output_mode auto")
        Logger.success("Sterowniki GFX i potok HDMI dostrojone.")


class SmartTubeInjector:
    """Manipulator preferencji SmartTube (Rootless XML Modifier)."""
    
    def inject(self) -> None:
        Logger.log("Uruchamiam mechanizm Intent Backup dla SmartTube...")
        pkg = "org.smarttube.stable"
        SystemShell.run(f"am broadcast -a com.liskovsoft.smartyoutubetv2.BACKUP_EXPORT -p {pkg}")
        time.sleep(2.5)

        device_zip = "/sdcard/SmartTubeBackup.zip"
        local_orig = SMARTTUBE_DIR / "backup_orig.zip"
        local_opt = SMARTTUBE_DIR / "backup_opt.zip"

        subprocess.run(["adb", "-s", SystemShell.device, "pull", device_zip, str(local_orig)], capture_output=True)

        if not local_orig.exists() or local_orig.stat().st_size == 0:
            Logger.error("Błąd: Nie pobrano kopii. Uruchom aplikację SmartTube chociaż raz!")
            return

        bcm_overrides = {
            "video_codec": ("int", "2"),
            "av1_enabled": ("boolean", "false"),
            "use_tunnel_mode": ("boolean", "true"),
            "force_hw_decoding": ("boolean", "true"),
            "custom_video_decoder": ("string", "OMX.BROADCOM.video-decoder.vp9"),
            "video_buffer_size": ("string", "25000"),
            "video_resolution": ("string", "1080"),
            "video_frame_rate_switch": ("boolean", "true")
        }

        try:
            with zipfile.ZipFile(str(local_orig), "r") as zin, zipfile.ZipFile(str(local_opt), "w") as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename.endswith(".xml"):
                        root = ET.fromstring(data.decode("utf-8", errors="replace"))
                        for key, (typ, val) in bcm_overrides.items():
                            found = False
                            for child in root:
                                if child.get("name") == key:
                                    child.set("value", val)
                                    if typ == "string": child.text = val
                                    found = True
                                    break
                            if not found:
                                if typ == "string": ET.SubElement(root, typ, {"name": key}).text = val
                                else: ET.SubElement(root, typ, {"name": key, "value": val})

                        buf = io.BytesIO()
                        ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
                        zout.writestr(item, buf.getvalue())
                    else:
                        zout.writestr(item, data)

            SystemShell.run(f"am force-stop {pkg}")
            subprocess.run(["adb", "-s", SystemShell.device, "push", str(local_opt), device_zip], capture_output=True)
            Logger.success("Profil BCM72604 wstrzyknięty! Otwórz STN -> Ustawienia -> Kopia -> Przywróć.")
        except Exception as e:
            Logger.error(f"Błąd parsera XML: {e}")


# =========================================================
# GLÓWNA KONSOLA APLIKACJI
# =========================================================

class PlayBoxController:
    def __init__(self):
        self.diag = DiagnosticEngine()
        self.net = NetworkAndDnsController()
        self.lmk = ProcessAndLmkManager()
        self.wv = WebViewManager()
        self.bcm = BroadcomTuner()
        self.stn = SmartTubeInjector()

    def run_cleanup(self):
        Logger.log("Agresywne czyszczenie Cache i zwalnianie Heap RAM...")
        SystemShell.run_as_root("am kill-all")
        SystemShell.run("cmd activity trim-memory RUNNING_CRITICAL")
        SystemShell.run("pm trim-caches 4096G")
        Logger.success("Zasoby systemowe zwolnione.")

    def run_full_auto(self):
        Logger.header("INICJALIZACJA PEŁNEGO ŁAŃCUCHA OPTYMALIZACJI")
        self.bcm.optimize()
        self.wv.apply_flags()
        self.lmk.apply_aggressive_lmk()
        self.lmk.freeze_bloatware()
        self.net.optimize_tcp_buffers()
        self.net.set_custom_dns("Cloudflare")
        self.stn.inject()
        self.run_cleanup()
        Logger.header("ZAKOŃCZONO: Dekoder gotowy na tryb PRO.")

    def start(self):
        Logger.header("PLAYBOX TITANIUM v10.3 PRO - SMARTTUBE & SYSTEM MOD")
        if not SystemShell.autodetect():
            ip = input(f"{Logger.COLORS['cyan']}Podaj IP:PORT (np. 192.168.1.10:5555) > {Logger.COLORS['reset']}")
            if not SystemShell.connect(ip): return

        while True:
            print(f"\n{Logger.COLORS['magenta']}{Logger.COLORS['bold']}")
            print("==========================================================================")
            print("║             PLAYBOX TITANIUM v10.3 PRO - MASTER DASHBOARD              ║")
            print("==========================================================================")
            print(f"║ {Logger.COLORS['cyan']}-- DIAGNOSTYKA & STATUS --{Logger.COLORS['magenta']}")
            print(f"║  {Logger.COLORS['info']}1.{Logger.COLORS['reset']} [SKANER] Sprawdź procesy UI, WebView, SmartTube, DNS i LMK")
            print(f"║")
            print(f"║ {Logger.COLORS['cyan']}-- SYSTEM KONTROLI RDZENIA --{Logger.COLORS['magenta']}")
            print(f"║  {Logger.COLORS['info']}2.{Logger.COLORS['reset']} [BROADCOM] Optymalizacja Chipsetu GFX (Hardware Renderer)")
            print(f"║  {Logger.COLORS['info']}3.{Logger.COLORS['reset']} [WEBVIEW] Tuning Flag i zarządzanie silnikiem przeglądarki")
            print(f"║  {Logger.COLORS['info']}4.{Logger.COLORS['reset']} [PAMIĘĆ] Agresywny profil LMK & Zamrażanie bloatware (VOD/BG)")
            print(f"║")
            print(f"║ {Logger.COLORS['cyan']}-- SIECIOWE & APLIKACJE --{Logger.COLORS['magenta']}")
            print(f"║  {Logger.COLORS['info']}5.{Logger.COLORS['reset']} [NETWORK] Zmiana DNS (DoT) i optymalizacja buforów TCP")
            print(f"║  {Logger.COLORS['info']}6.{Logger.COLORS['reset']} [SMARTTUBE] Wstrzyknięcie wektora XML (Sprzętowy VP9 BCM72604)")
            print(f"║")
            print(f"║ {Logger.COLORS['cyan']}-- ZARZĄDZANIE MOCĄ --{Logger.COLORS['magenta']}")
            print(f"║  {Logger.COLORS['info']}7.{Logger.COLORS['reset']} [CLEANUP] Agresywne zwalnianie Heap i Drop Caches")
            print(f"║  {Logger.COLORS['warning']}8.{Logger.COLORS['reset']} [FULL AUTO] Uruchom wszystkie bezpieczne modyfikacje (ZALECANE)")
            print(f"║  {Logger.COLORS['error']}0.{Logger.COLORS['reset']} Wyjście i Zakończenie połączenia ADB")
            print("==========================================================================")

            opt = input(f"\n{Logger.COLORS['cyan']}Wybierz operację > {Logger.COLORS['reset']}").strip()

            if opt == "1": self.diag.run_full_diagnostics()
            elif opt == "2": self.bcm.optimize()
            elif opt == "3":
                print("\n1. Wstrzyknij Flagi WebView (Accelerated)\n2. Zmień implementację na systemowy WebView (com.google.android.webview)")
                sub = input("Wybór > ")
                if sub == "1": self.wv.apply_flags()
                elif sub == "2": self.wv.change_implementation("com.google.android.webview")
            elif opt == "4":
                self.lmk.apply_aggressive_lmk()
                self.lmk.freeze_bloatware()
            elif opt == "5":
                print("\n1. Optymalizuj Bufory TCP\n2. Ustaw DNS Cloudflare (1.1.1.1)\n3. Ustaw DNS AdGuard (Blokada Reklam)\n4. Wyłącz Custom DNS")
                sub = input("Wybór > ")
                if sub == "1": self.net.optimize_tcp_buffers()
                elif sub == "2": self.net.set_custom_dns("Cloudflare")
                elif sub == "3": self.net.set_custom_dns("AdGuard")
                elif sub == "4": self.net.set_custom_dns("Off")
            elif opt == "6": self.stn.inject()
            elif opt == "7": self.run_cleanup()
            elif opt == "8": self.run_full_auto()
            elif opt == "0":
                Logger.success("Rozłączenie... Niech stabilność będzie z Tobą!")
                break
            else: Logger.error("Nieprawidłowy wektor polecenia.")
            
            input(f"\n{Logger.COLORS['info']}[ENTER] Wróć do Master Dashboard...{Logger.COLORS['reset']}")


if __name__ == "__main__":
    app = PlayBoxController()
    app.start()