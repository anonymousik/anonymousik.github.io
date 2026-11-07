#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM — AUTOPILOT HYBRID v22.0 (OMNI ULTIMATE EDITION)           ║
║  Target: Sagemcom DCTIW362P | BCM72604 | Android TV 9 API 28 | Cortex-A15    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ZINTEGROWANE SYSTEMY:                                                       ║
║  1. Optymalizacja GPU i Wyświetlania (SkiaGL vs Natywny GLES, 60fps Lock)   ║
║  2. Silnik Kolorów i EOTF ST2084 (HDR10, BT.2020 passthrough)                ║
║  3. Agresywny Purge RAM & LMK (Zrzucanie VFS, force-gc, fstrim, Freeze)      ║
║  4. SmartTube Config Manager (Eksport, optymalizacja BCM72604, Import, UI)   ║
║  5. Button Remapper Configurator & Smart Script Pusher                       ║
║  6. Skaner crashy logcat, Live Monitor, Benchmark z normami dla A15         ║
║  7. Autonomiczny Watchdog Daemon (Ochrona mDNS, RAM, Cast i procesów)        ║
║  8. Silnik Eskalacji Uprawnień Shizuku/Rish (S1, S2, S3)                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable, NamedTuple

VERSION = "22.0 HYBRID ULTIMATE"
DEFAULT_DEVICE = "192.168.1.3:5555"
CACHE_DIR = Path.home() / ".playbox_cache"
BACKUP_DIR = CACHE_DIR / "backups_v220"
LOG_FILE = CACHE_DIR / "autopilot_hybrid.log"

for d in (CACHE_DIR, BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)

DRY_RUN = False

# ==============================================================================
# SŁOWNIK KOLORÓW I REJESTR LOGOWANIA (Termux Safe)
# ==============================================================================
class L:
    C = {
        "s": "\033[92m", "w": "\033[93m", "e": "\033[91m",
        "c": "\033[96m", "h": "\033[95m", "d": "\033[2m",
        "b": "\033[1m",  "r": "\033[0m"
    }
    _buf: List[str] = []

    @classmethod
    def _out(cls, msg: str, lvl: str) -> None:
        ts = time.strftime("%H:%M:%S")
        c = cls.C.get(lvl, cls.C["c"])
        print(f"{c}[{ts}] {msg}{cls.C['r']}")
        cls._buf.append(f"[{ts}][{lvl}] {msg}")

    @classmethod
    def ok(cls, m: str) -> None:   cls._out(f"✓ {m}", "s")
    @classmethod
    def info(cls, m: str) -> None: cls._out(m, "c")
    @classmethod
    def warn(cls, m: str) -> None: cls._out(f"⚠ {m}", "w")
    @classmethod
    def err(cls, m: str) -> None:  cls._out(f"✗ {m}", "e")
    @classmethod
    def fix(cls, m: str) -> None:  cls._out(f"🔧 {m}", "w")
    @classmethod
    def cast(cls, m: str) -> None: cls._out(f"🛡 {m}", "s")
    @classmethod
    def dim(cls, m: str) -> None:  cls._out(f"  └─ {m}", "d")

    @classmethod
    def row(cls, label: str, value: str, width: int = 24) -> None:
        print(f"  {cls.C['c']}{label:<{width}}{cls.C['r']} {value}")

    @classmethod
    def hdr(cls, m: str) -> None:
        bar = "═" * (len(m) + 8)
        print(f"\n{cls.C['h']}{cls.C['b']}╔{bar}╗\n║    {m.upper()}    ║\n╚{bar}╝{cls.C['r']}\n")

    @classmethod
    def sub(cls, m: str) -> None:
        print(f"\n{cls.C['c']}  ── {m} ──{cls.C['r']}")

    @classmethod
    def save(cls) -> None:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n{'─'*60}\n{time.strftime('%Y-%m-%d %H:%M:%S')} v{VERSION}\n")
                f.write("\n".join(cls._buf) + "\n")
        except OSError:
            pass


# ==============================================================================
# SPECYFIKACJA URZĄDZENIA (Broadcom BCM72604)
# ==============================================================================
class HW:
    SOC_NAME = "BCM72604"
    BOARD = "m362"
    RAM_TOTAL_MB = 1425
    PKG_SMARTTUBE_STABLE = "org.smarttube.stable"
    PKG_SMARTTUBE_BETA = "org.smarttube.beta"
    PKG_PROJECTIVY = "com.spocky.projapp"
    PKG_SHIZUKU = "moe.shizuku.privileged.api"
    PKG_MEDIASHELL = "com.google.android.apps.mediashell"
    DEVICE_BACKUP_BASE = "/storage/emulated/0/data"


# ==============================================================================
# TRANSPORT ADB I SYSTEM UPRAWNIEŃ RISH (S1/S2/S3)
# ==============================================================================
class Transport:
    dev: str = ""

    @classmethod
    def connect(cls, target: str) -> bool:
        cls.dev = target if ":" in target else f"{target}:5555"
        L.info(f"Nawiązywanie połączenia ADB: {cls.dev}")
        if DRY_RUN: return True
        try:
            r = subprocess.run(["adb", "connect", cls.dev], capture_output=True, text=True, timeout=10)
            if "connected" in r.stdout.lower() and "failed" not in r.stdout.lower():
                L.ok("Połączenie ADB ustanowione.")
                return True
            L.err(f"Błąd połączenia: {r.stdout.strip()}")
            return False
        except Exception as e:
            L.err(f"Wyjątek transportu ADB: {e}")
            return False

    @classmethod
    def sh(cls, cmd: str, timeout: int = 25) -> str:
        if DRY_RUN: return "DRY_RUN_OK"
        try:
            return subprocess.check_output(
                ["adb", "-s", cls.dev, "shell", cmd],
                stderr=subprocess.STDOUT, text=True, timeout=timeout
            ).strip()
        except subprocess.CalledProcessError as e:
            return e.output.strip() if e.output else ""
        except Exception:
            return "ERROR"

    @classmethod
    def push(cls, local: str, remote: str) -> bool:
        if DRY_RUN: return True
        try:
            r = subprocess.run(["adb", "-s", cls.dev, "push", local, remote], capture_output=True)
            return r.returncode == 0
        except Exception:
            return False

    @classmethod
    def pull(cls, remote: str, local: str) -> bool:
        if DRY_RUN: return True
        try:
            r = subprocess.run(["adb", "-s", cls.dev, "pull", remote, local], capture_output=True)
            return r.returncode == 0
        except Exception:
            return False


class PrivilegeEngine:
    DEX_PATH = "/data/local/tmp/rish_shizuku.dex"
    BIN_PATH = "/data/local/tmp/rish"
    active_strat = 0  # 0=ADB Std, 1=Shell Bypass, 2=Silent Grant, 3=Direct

    @classmethod
    def init(cls) -> None:
        L.hdr("Inicjalizacja Silnika Uprawnień (Rish Engine)")
        if not cls.ensure_shizuku():
            L.warn("Brak Shizuku. Fallback do uprawnień Standard ADB.")
            return

        out = Transport.sh(f"ls -la {cls.DEX_PATH}")
        if "No such file" in out:
            L.err(f"Brak pliku DEX w lokalizacji systemowej: {cls.DEX_PATH}")
            return

        # S1 Shell Bypass (com.android.shell)
        cls._deploy_wrapper("com.android.shell")
        if "uid=" in cls.run("id"):
            cls.active_strat = 1
            L.ok("Wdrożono S1: Shell-Bypass (Automatyczna pre-autoryzacja Shizuku)")
            return

        # S2 Silent Grant (com.termux)
        grant_cmd = f"app_process -Djava.class.path={cls.DEX_PATH} /system/bin rikka.shizuku.shell.ShizukuShellLoader --request-permission com.termux"
        Transport.sh(grant_cmd)
        time.sleep(1.5)
        cls._deploy_wrapper("com.termux")
        if "uid=" in cls.run("id"):
            cls.active_strat = 2
            L.ok("Wdrożono S2: Silent-Grant")
            return

        # S3 Fallback Direct Execution
        cls.active_strat = 3
        L.warn("Wdrożono S3: Direct Execution (Zmniejszona wydajność, brak stałego wrappera)")

    @classmethod
    def ensure_shizuku(cls) -> bool:
        if "shizuku_server" in Transport.sh("ps -A"):
            return True
        Transport.sh("sh /storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh")
        time.sleep(2)
        return "shizuku_server" in Transport.sh("ps -A")

    @classmethod
    def _deploy_wrapper(cls, app_id: str) -> None:
        script = (
            "#!/system/bin/sh\n"
            f"export RISH_APPLICATION_ID={app_id}\n"
            f"DEX={cls.DEX_PATH}\n"
            'if [ "$1" = "-c" ]; then shift; CMD="$*"; exec /system/bin/app_process -Djava.class.path="$DEX" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader -c "$CMD"\n'
            'else exec /system/bin/app_process -Djava.class.path="$DEX" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader "$@"\nfi\n'
        )
        b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
        Transport.sh(f"echo '{b64}' | base64 -d > {cls.BIN_PATH} && chmod 755 {cls.BIN_PATH}")

    @classmethod
    def run(cls, cmd: str) -> str:
        esc = cmd.replace("'", "'\\''")
        if cls.active_strat in (1, 2):
            return Transport.sh(f"{cls.BIN_PATH} -c '{esc}'")
        elif cls.active_strat == 3:
            return Transport.sh(f"app_process -Djava.class.path={cls.DEX_PATH} /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader -c '{esc}'")
        return Transport.sh(cmd)


class Batch:
    def __init__(self, label: str):
        self.label = label
        self.cmds = []
    def sp(self, k: str, v: str): self.cmds.append(f"setprop {k} {v}")
    def sput(self, ns: str, k: str, v: str): self.cmds.append(f"settings put {ns} {k} {v}")
    def exe(self):
        if not self.cmds: return
        script = "; ".join(f"({c})" for c in self.cmds)
        PrivilegeEngine.run(script)
        L.ok(f"Zastosowano paczkę [{self.label}]: {len(self.cmds)} zmian.")


# ==============================================================================
# SEKCJA 1: SYSTEM OPTIMIZERS (GPU, RAM, NET, AUDIO, DISPLAY)
# ==============================================================================
class SystemOptimizers:
    @staticmethod
    def apply_gpu_display_skiagl():
        """Zoptymalizowany profil oparty na SkiaGL."""
        L.hdr("Optymalizacja GPU — SkiaGL / V3D Explicit Sync")
        b = Batch("GPU_SKIAGL")
        b.sp("debug.hwui.renderer", "skiagl")
        b.sp("debug.renderengine.backend", "skiaglthreaded")
        b.sp("debug.sf.disable_backpressure", "1")
        b.sp("debug.sf.latch_unsignaled", "1")
        b.sp("debug.gr.numframebuffers", "3")
        b.sp("debug.hwui.layer_cache_size", "32768")
        b.sp("debug.hwui.use_buffer_age", "false") # explicit sync active
        b.sp("debug.force_opengl", "1")
        b.exe()
        L.ok("Zastosowano profil SkiaGL (60fps, Triple buffering, niskie opóźnienia).")

    @staticmethod
    def apply_gpu_display_opengl_gles():
        """Lekki profil OpenGL/GLES z skryptu 'skiagl_out.sh'."""
        L.hdr("Optymalizacja GPU — Natywne HWUI GLES / OpenGL (Lekki Profil)")
        b = Batch("GPU_GLES_LIGHT")
        b.sp("debug.hwui.renderer", "opengl")
        b.sp("debug.renderengine.backend", "gles")
        b.sp("debug.hwui.use_buffer_age", "false")
        b.sp("debug.force_opengl", "0")
        b.sp("debug.hwui.layer_cache_size", "49152") # 48MB cache dla TV Launcher
        b.exe()
        L.warn("Przeładowanie menedżera okien (SurfaceFlinger) nastąpi za chwilę...")
        PrivilegeEngine.run("stop && sleep 2 && start")
        L.ok("Zastosowano lekki profil OpenGL GLES. System przeładowany.")

    @staticmethod
    def apply_memory_lmk():
        L.hdr("Zarządzanie Pamięcią RAM & LMKD (PSI-Only)")
        b = Batch("RAM_LMK")
        # Dalvik Heap
        b.sp("dalvik.vm.heapsize", "512m")
        b.sp("dalvik.vm.heapgrowthlimit", "192m")
        b.sp("dalvik.vm.heapstartsize", "16m")
        b.sp("dalvik.vm.heapminfree", "2m")
        b.sp("dalvik.vm.heapmaxfree", "16m")
        b.sp("dalvik.vm.heaptargetutilization", "0.75")
        # PSI LMK Settings
        b.sp("ro.lmk.upgrade_pressure", "50")
        b.sp("ro.lmk.use_minfree_levels", "false")
        b.sp("ro.lmk.kill_heaviest_task", "true")
        b.sp("ro.lmk.filecache_min_kb", "92160")
        b.sp("sys.sysctl.extra_free_kbytes", "32768")
        # System Limits
        b.sput("global", "activity_manager_constants", "max_cached_processes=3,power_check_max_cpu_1=25")
        b.sput("global", "background_process_limit", "3")
        b.exe()
        # VM parameters
        PrivilegeEngine.run("echo 0 > /proc/sys/vm/swappiness")
        PrivilegeEngine.run("echo 30 > /proc/sys/vm/vfs_cache_pressure")
        PrivilegeEngine.run("echo 15 > /proc/sys/vm/dirty_ratio")
        L.ok("Dalvik, LMK i parametry wirtualnej pamięci jądra zoptymalizowane.")

    @staticmethod
    def apply_network_audio():
        L.hdr("Stos Sieciowy (TCP/DoT) & HDMI ARC Sync")
        b = Batch("NET_AUDIO")
        # TCP Buffers
        b.sput("global", "net.tcp.buffersize.wifi", "524288,1048576,4194304,262144,524288,2097152")
        b.sput("global", "tcp_default_init_rwnd", "120")
        b.sp("net.tcp.default_init_rwnd", "120")
        b.sput("global", "wifi_scan_always_enabled", "0")
        b.sput("global", "ble_scan_always_enabled", "0")
        # DNS Cloudflare TLS
        b.sput("global", "private_dns_mode", "hostname")
        b.sput("global", "private_dns_specifier", "one.one.one.one")
        b.sput("global", "captive_portal_mode", "0")
        b.sput("global", "captive_portal_http_url", "http://connectivitycheck.gstatic.com/generate_204")
        # HDMI Audio Sync
        b.sp("audio.offload.disable", "1")
        b.sp("audio.deep_buffer.media", "true")
        b.sp("audio.brcm.hdmi.clock_lock", "true")
        b.sp("persist.sys.hdmi.keep_awake", "true")
        b.exe()
        # FastOpen kernel
        PrivilegeEngine.run("echo 3 > /proc/sys/net/ipv4/tcp_fastopen")
        PrivilegeEngine.run("echo cubic > /proc/sys/net/ipv4/tcp_congestion_control")
        L.ok("Sieć i synchronizacja Audio HDMI zostały poprawnie ustawione.")


# ==============================================================================
# SEKCJA 2: AGGRESIVE PURGE RAM & CACHE (`clear_lmk.sh` & `back_max2.sh`)
# ==============================================================================
class PurgeManager:
    KILL_LIST = [
        "com.google.android.youtube",
        "com.google.android.gms.setup_wizard",
        "com.netflix.ninja",
        "com.amazon.amazonvideo.livingroom"
    ]

    @classmethod
    def aggressive_purge(cls):
        L.hdr("Agresywne Czyszczenie Pamięci (Purge & Restrict)")
        L.info("Etap 1: Czyszczenie pamięci cache i FSTRIM...")
        PrivilegeEngine.run("sm fstrim")
        PrivilegeEngine.run("pm trim-caches 9999999999")
        
        L.info("Etap 2: Zatrzymywanie procesów działających w tle...")
        for pkg in cls.KILL_LIST:
            PrivilegeEngine.run(f"am force-stop {pkg}")
            L.dim(f"Ubiłem: {pkg}")
            
        L.info("Etap 3: Wymuszanie systemowego Garbage Collection (GC)...")
        PrivilegeEngine.run("cmd activity force-gc")
        
        L.info("Etap 4: Aktywacja agresywnej optymalizacji LMK i tła...")
        PrivilegeEngine.run("settings put global background_activity_optimization_enabled 1")
        
        L.info("Etap 5: Blokada GMS / Vending i Asystenta w tle...")
        PrivilegeEngine.run("pm disable-user --user 0 com.android.vending")
        PrivilegeEngine.run("pm disable-user --user 0 com.google.android.googlequicksearchbox")
        
        # Przywrócenie ochrony Cast
        AppManager.protect_cast_services()
        L.ok("Agresywne czyszczenie pamięci zakończone sukcesem!")


# ==============================================================================
# SEKCJA 3: SMARTTUBE CONFIG MANAGER (XML/JSON Parser z UI-Automation)
# ==============================================================================
class SmartTubeConfigManager:
    BCM_PREFS = {
        "video_codec": ("int", "2"),              # VP9 HW
        "av1_enabled": ("boolean", "false"),      # No software AV1 rendering on A15
        "vp9_enabled": ("boolean", "true"),
        "preferred_codec": ("string", "vp9"),
        "use_tunnel_mode": ("boolean", "true"),   # Hardware A/V tunnel mode
        "tunnel_mode_enabled": ("boolean", "true"),
        "tunneled_playback": ("boolean", "true"),
        "video_resolution": ("string", "1080"),   # Target 1080p for performance stability
        "max_video_resolution": ("string", "1080"),
        "hdr_mode": ("boolean", "true"),
        "hdr_enabled": ("boolean", "true"),
        "buffer_type": ("int", "2"),              # Large buffer size
        "min_buffer_duration": ("string", "15000"),
        "max_buffer_duration": ("string", "50000"),
        "hardware_acceleration": ("boolean", "true"),
        "use_hardware_decoder": ("boolean", "true"),
        "background_playback": ("boolean", "false"), # Saves memory/CPU on background exit
    }

    @classmethod
    def get_smarttube_package(cls) -> Optional[str]:
        for pkg in ("org.smarttube.stable", "org.smarttube.beta", "com.liskovsoft.smarttubetv"):
            if pkg in PrivilegeEngine.run("pm list packages"):
                return pkg
        return None

    @classmethod
    def optimize_config(cls):
        L.hdr("Menedżer Konfiguracji SmartTube (v3 Engine)")
        pkg = cls.get_smarttube_package()
        if not pkg:
            L.err("Nie znaleziono zainstalowanej aplikacji SmartTube!")
            return

        L.info(f"Wykryty pakiet: {pkg}")
        backup_dir = f"{HW.DEVICE_BACKUP_BASE}/{pkg}"
        L.info(f"Skanowanie lokalizacji zapisu: {backup_dir}")

        # Wymuś zrzucenie configu poprzez UI automation (z logów)
        L.info("Próba wywołania systemowego okna dialogowego zapisu...")
        PrivilegeEngine.run(f"am start -n {pkg}/com.liskovsoft.smartyoutubetv2.tv.ui.dialogs.AppDialogActivity -f 0x10000000")
        time.sleep(2)
        PrivilegeEngine.run("input keyevent 20") # DPAD_DOWN
        time.sleep(0.5)
        PrivilegeEngine.run("input keyevent 23") # DPAD_CENTER
        time.sleep(1.5)

        # Sprawdzenie obecności plików XML
        L.info("Pobieranie plików konfiguracyjnych do optymalizacji...")
        local_tmp_dir = Path("/tmp/smarttube_patch") if os.path.exists("/tmp") else CACHE_DIR / "st_patch"
        local_tmp_dir.mkdir(parents=True, exist_ok=True)
        
        # Pobieranie struktury plików config
        xml_files = [f for f in Transport.sh(f"ls {backup_dir}").split() if f.endswith(".xml")]
        if not xml_files:
            L.warn("Brak wygenerowanego pliku kopii zapasowej. Uruchom eksport ręcznie w menu SmartTube.")
            return

        for xml_file in xml_files:
            remote_path = f"{backup_dir}/{xml_file}"
            local_path = local_tmp_dir / xml_file
            L.info(f"Pobieranie: {xml_file}")
            if Transport.pull(remote_path, str(local_path)):
                L.ok("Pobrano.")
                cls._patch_xml_file(local_path)
                L.info(f"Wgrywanie zoptymalizowanego pliku: {xml_file}")
                Transport.push(str(local_path), remote_path)
                L.ok("Wgrano z powrotem.")

        # Przeładuj konfigurację
        L.info("Przeładowanie i uruchomienie SmartTube z nową konfiguracją...")
        PrivilegeEngine.run(f"am force-stop {pkg}")
        time.sleep(1)
        PrivilegeEngine.run(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        L.ok("Konfiguracja zoptymalizowana: VP9 + Tunneling + 1080p limit wgrane i aktywne!")

    @classmethod
    def _patch_xml_file(cls, filepath: Path):
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(str(filepath))
            root = tree.getroot()
        except Exception:
            L.err("Błąd parsowania XML. Tworzę nową strukturę konfiguracji.")
            root = ET.Element("map")
            tree = ET.ElementTree(root)

        # Iniekcja optymalnych parametrów
        for key, (typ, val) in cls.BCM_PREFS.items():
            found = False
            for el in root:
                if el.get("name") == key:
                    el.set("value", val) if el.tag != "string" else setattr(el, "text", val)
                    found = True
                    break
            if not found:
                if typ == "string":
                    sub = ET.SubElement(root, "string", {"name": key})
                    sub.text = val
                else:
                    ET.SubElement(root, typ, {"name": key, "value": val})

        tree.write(str(filepath), encoding="utf-8", xml_declaration=True)


# ==============================================================================
# SEKCJA 4: APPS, CAST & DEBLOAT (Chromecast i Projectivy Launcher)
# ==============================================================================
class AppManager:
    @staticmethod
    def protect_cast_services():
        L.hdr("Ochrona Usług Chromecast (mDNS / MediaShell)")
        pkgs = ["com.android.chromecast", "com.google.android.apps.mediashell", "com.castify.tv"]
        for pkg in pkgs:
            PrivilegeEngine.run(f"dumpsys deviceidle whitelist +{pkg}")
            PrivilegeEngine.run(f"am set-standby-bucket {pkg} active")
            PrivilegeEngine.run(f"appops set {pkg} SYSTEM_ALERT_WINDOW allow")
            PrivilegeEngine.run(f"pm enable {pkg}")
            L.info(f"Ochrona mDNS i nakładki włączona dla: {pkg}")

    @staticmethod
    def fix_projectivy_manager():
        L.hdr("Naprawa Menadżera Obrazu (Projectivy Launcher)")
        pkg = "com.spocky.projapp"
        acc_service = "com.spocky.projapp/com.spocky.projapp.services.AccessibilityService"
        
        # Nadanie uprawnień
        PrivilegeEngine.run(f"pm grant {pkg} android.permission.WRITE_SECURE_SETTINGS")
        PrivilegeEngine.run(f"appops set {pkg} SYSTEM_ALERT_WINDOW allow")
        PrivilegeEngine.run(f"appops set {pkg} PROJECT_MEDIA allow")
        PrivilegeEngine.run(f"am set-standby-bucket {pkg} active")
        
        # Aktywacja ułatwień dostępu
        current = PrivilegeEngine.run("settings get secure enabled_accessibility_services").strip()
        if acc_service not in current:
            new_val = f"{current}:{acc_service}".strip(":")
            PrivilegeEngine.run(f"settings put secure enabled_accessibility_services {new_val}")
            PrivilegeEngine.run("settings put secure accessibility_enabled 1")
            L.ok("Usługa Accessibility dla Projectivy została siłowo aktywowana.")
        
        # Przeładowanie
        PrivilegeEngine.run(f"am force-stop {pkg}")
        PrivilegeEngine.run(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        L.ok("Menadżer obrazu (Screen Profiles Engine) został poprawnie zainicjalizowany.")


# ==============================================================================
# SEKCJA 5: DIAGNOSTYKA, LIVE MONITOR I BENCHMARK SYSTEMU
# ==============================================================================
class Performance:
    @staticmethod
    def run_benchmark():
        L.hdr("Benchmark Wydajnościowy CPU & RAM")
        
        # CPU
        t_start = int(Transport.sh("date +%s%3N"))
        Transport.sh("dd if=/dev/urandom bs=1048576 count=4 2>/dev/null | md5sum > /dev/null")
        t_end = int(Transport.sh("date +%s%3N"))
        elapsed = (t_end - t_start) / 4
        L.ok(f"Wydajność procesora Cortex-A15: {elapsed:.0f} ms/MB (Wzorcowa: <150 ms/MB)")
        
        # RAM
        t_start = int(Transport.sh("date +%s%3N"))
        Transport.sh("dd if=/dev/zero of=/dev/null bs=1048576 count=64")
        t_end = int(Transport.sh("date +%s%3N"))
        ms = t_end - t_start
        mb_s = (64 * 1000) / ms if ms > 0 else 0
        L.ok(f"Przepustowość RAM: {mb_s:.0f} MB/s (Wzorcowa: >500 MB/s)")

    @staticmethod
    def live_monitor():
        L.hdr("Live Monitor (Wciśnij Ctrl+C aby wyjść)")
        try:
            while True:
                os.system("clear")
                raw = PrivilegeEngine.run(
                    "grep MemAvailable /proc/meminfo | awk '{print $2}'; "
                    "top -n1 -d1 | grep -E '^[Cc]pu' | head -1; "
                    "cat /sys/class/thermal/thermal_zone0/temp"
                )
                lines = raw.splitlines()
                print(f"{L.C['b']}TITAN SMART CORE - MONITOR CZASU RZECZYWISTEGO{L.C['r']}")
                print("-" * 50)
                if len(lines) >= 1: print(f"Dostępna pamięć RAM : {int(lines[0])//1024} MB")
                if len(lines) >= 2: print(f"Obciążenie procesora: {lines[1].strip()}")
                if len(lines) >= 3: print(f"Temperatura rdzenia : {int(lines[2])/1000:.1f}°C")
                print("-" * 50)
                time.sleep(3)
        except KeyboardInterrupt:
            L.ok("Wyjście z monitora.")


# ==============================================================================
# SEKCJA 6: SMART SCRIPT PUSHER & BUTTON REMAPPER
# ==============================================================================
class OmniTools:
    @staticmethod
    def script_pusher():
        L.hdr("Smart Script Pusher (.sh execute)")
        scripts = [f for f in os.listdir('.') if f.endswith('.sh')]
        if not scripts:
            L.warn("Brak skryptów .sh w bieżącym katalogu hosta.")
            return
        L.info("Wykryte skrypty lokalne:")
        for idx, s in enumerate(scripts, 1):
            print(f"  [{idx}] {s}")
        
        choice = input("\nWybierz numer skryptu do wysłania i wykonania: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(scripts):
            target = scripts[int(choice)-1]
            remote_path = f"/data/local/tmp/{target}"
            L.info(f"Kopiowanie {target} -> {remote_path}")
            if Transport.push(target, remote_path):
                PrivilegeEngine.run(f"chmod 755 {remote_path}")
                L.info("Uruchamianie skryptu...")
                out = PrivilegeEngine.run(f"sh {remote_path}")
                print(f"WYNIK WYKONANIA:\n{out}")
                L.ok("Skrypt wykonany pomyślnie.")
            else:
                L.err("Kopiowanie nieudane.")

    @staticmethod
    def configure_remapper():
        L.hdr("Button Remapper OMNI Access Configurator")
        pkg = input("Podaj nazwę pakietu mapera przycisków (np. flar2.homebutton): ").strip()
        if not pkg: return
        
        L.info(f"Nadawanie uprawnień systemowych dla: {pkg}")
        PrivilegeEngine.run(f"pm grant {pkg} android.permission.WRITE_SECURE_SETTINGS")
        PrivilegeEngine.run(f"pm grant {pkg} android.permission.READ_LOGS")
        PrivilegeEngine.run(f"appops set {pkg} SYSTEM_ALERT_WINDOW allow")
        PrivilegeEngine.run(f"dumpsys deviceidle whitelist +{pkg}")
        
        # Włączenie usługi
        cur = PrivilegeEngine.run("settings get secure enabled_accessibility_services").strip()
        service_path = f"{pkg}/.core.AccessibilityService"
        if service_path not in cur:
            new_services = f"{cur}:{service_path}".strip(":")
            PrivilegeEngine.run(f"settings put secure enabled_accessibility_services {new_services}")
            PrivilegeEngine.run("settings put secure accessibility_enabled 1")
            L.ok("Usługa mapowania przycisków została pomyślnie załadowana do ułatwień dostępu.")


# ==============================================================================
# AUTONOMIDNY WATCHDOG DAEMON (Auto-healing)
# ==============================================================================
class Watchdog:
    _thread: Optional[threading.Thread] = None
    _stop = threading.Event()
    running = False

    @classmethod
    def toggle(cls):
        if cls.running:
            cls._stop.set()
            cls.running = False
            L.warn("Samo-naprawczy Watchdog został wyłączony.")
        else:
            cls._stop.clear()
            cls.running = True
            cls._thread = threading.Thread(target=cls._loop, daemon=True)
            cls._thread.start()
            L.ok("Samo-naprawczy Watchdog został pomyślnie uruchomiony w tle (Skan co 30s).")

    @classmethod
    def _loop(cls):
        while not cls._stop.is_set():
            # Sprawdzenie pamięci RAM
            ram = Transport.sh("grep MemAvailable /proc/meminfo | awk '{print $2}'")
            if ram.isdigit() and int(ram) // 1024 < 120:
                L.warn("Watchdog: Krytycznie mało RAM. Uruchamiam procedurę oczyszczania...")
                PrivilegeEngine.run("pm trim-caches 1G")
                PrivilegeEngine.run("sync && echo 3 > /proc/sys/vm/drop_caches")
            
            # Sprawdzenie mdnsd (Cast Discovery)
            mdns = Transport.sh("getprop init.svc.mdnsd")
            if mdns != "running":
                PrivilegeEngine.run("stop mdnsd && start mdnsd")
                
            cls._stop.wait(30)


# ==============================================================================
# MENU GŁÓWNE INTERFEJSU CUI
# ==============================================================================
class HybridMenu:
    @classmethod
    def show(cls):
        while True:
            os.system("clear")
            strat = ["Standard ADB", "Shell-Bypass (S1)", "Silent-Grant (S2)", "Direct (S3)"][PrivilegeEngine.active_strat]
            wd_status = f"{L.C['s']}ON{L.C['r']}" if Watchdog.running else f"{L.C['e']}OFF{L.C['r']}"
            
            print(f"""
{L.C['h']}{L.C['b']}╔══════════════════════════════════════════════════════════════════════╗
║  AUTOPILOT HYBRID — ALL-IN-ONE HARWDWARE SUITE v{VERSION:<13}        ║
║  Urządzenie: {Transport.dev:<18} Tryb Rish: {strat:<16} WD: {wd_status:<9} ║
╚══════════════════════════════════════════════════════════════════════╝{L.C['r']}
  {L.C['b']}[🚀 TRYB ULTRA ALL-IN-ONE]{L.C['r']}
  {L.C['s']}1.{L.C['r']} Wykonaj PEŁNĄ Optymalizację Urządzenia (Display+RAM+Net+Audio)
  
  {L.C['b']}[🖥  RENDEROWANIE & OBRAZ]{L.C['r']}
  {L.C['s']}2.{L.C['r']} Wymuś Zoptymalizowany Profil SkiaGL (Wysoka wydajność)
  {L.C['s']}3.{L.C['r']} Wymuś Natywny Profil OpenGL GLES (Lekkie renderowanie z restartem SF)
  {L.C['s']}4.{L.C['r']} Wykonaj Display Mode 60fps Lock & DPI Calibration (Dm Fix)

  {L.C['b']}[⚙️ STOSY & SYSTEM]{L.C['r']}
  {L.C['s']}5.{L.C['r']} Optymalizacja Pamięci RAM, LMKD i Dalvik (OEM Matched)
  {L.C['s']}6.{L.C['r']} Optymalizacja Sieciowa, TCP Cubic, Private DoT i Audio
  {L.C['s']}7.{L.C['r']} Optymalizacja i Wgranie Zoptymalizowanych ustawień SmartTube

  {L.C['b']}[🧹 ZARZĄDZANIE & OCZYSZCZANIE]{L.C['r']}
  {L.C['c']}8.{L.C['r']} Agresywny Purge RAM & Blokada Procesów Tła (clear_lmk)
  {L.C['c']}9.{L.C['r']} Aktywuj Ochronę Usług Chromecast (MediaShell Recovery)
  {L.C['c']}10.{L.C['r']} Naprawa Menadżera Obrazu (Projectivy Launcher Screen Profiles)
  
  {L.C['b']}[🛠 NARZĘDZIA & DIAGNOSTYKA]{L.C['r']}
  {L.C['w']}11.{L.C['r']} Button Remapper OMNI Access Configurator
  {L.C['w']}12.{L.C['r']} Smart Script Pusher (Auto-upload i execute)
  {L.C['w']}13.{L.C['r']} Uruchom Benchmark Systemu (CPU / RAM)
  {L.C['w']}14.{L.C['r']} Live Monitor Dashboard (Zużycie & Temperatury)
  {L.C['w']}15.{L.C['r']} Przełącz Samo-naprawczego Watchdoga w tle
  
  {L.C['e']}0.{L.C['r']} Wyjście
""")
            c = input(f"  {L.C['c']}Wybierz akcję > {L.C['r']}").strip()
            
            if c == "1":
                SystemOptimizers.apply_gpu_display_skiagl()
                SystemOptimizers.apply_memory_lmk()
                SystemOptimizers.apply_network_audio()
                AppManager.protect_cast_services()
                AppManager.fix_projectivy_manager()
                L.ok("Optymalizacja ULTRA ukończona.")
            elif c == "2": SystemOptimizers.apply_gpu_display_skiagl()
            elif c == "3": SystemOptimizers.apply_gpu_display_opengl_gles()
            elif c == "4": 
                # Wymuszenie 60fps & density 240
                PrivilegeEngine.run("wm size 1920x1080")
                PrivilegeEngine.run("wm density 240")
                PrivilegeEngine.run("settings put system min_refresh_rate 60.0")
                PrivilegeEngine.run("settings put system display_peak_refresh_rate 60.0")
                L.ok("Display Mode Fix zaaplikowany.")
            elif c == "5": SystemOptimizers.apply_memory_lmk()
            elif c == "6": SystemOptimizers.apply_network_audio()
            elif c == "7": SmartTubeConfigManager.optimize_config()
            elif c == "8": PurgeManager.aggressive_purge()
            elif c == "9": AppManager.protect_cast_services()
            elif c == "10": AppManager.fix_projectivy_manager()
            elif c == "11": OmniTools.configure_remapper()
            elif c == "12": OmniTools.script_pusher()
            elif c == "13": Performance.run_benchmark()
            elif c == "14": Performance.live_monitor()
            elif c == "15": Watchdog.toggle()
            elif c == "0": sys.exit(0)
            
            if c != "14" and c != "0":
                input(f"\n  {L.C['d']}[Wciśnij Enter, aby powrócić do menu]{L.C['r']}")


# ==============================================================================
# SEKCJA ROZRUCHOWA
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autopilot Hybrid Suite")
    parser.add_argument("--device", default="192.168.1.3", help="IP urządzenia Sagemcom")
    parser.add_argument("--auto", action="store_true", help="Uruchom bezgłośną optymalizację Ultra")
    args = parser.parse_args()

    if not Transport.connect(args.device):
        sys.exit(1)

    PrivilegeEngine.init()
    
    if args.auto:
        SystemOptimizers.apply_gpu_display_skiagl()
        SystemOptimizers.apply_memory_lmk()
        SystemOptimizers.apply_network_audio()
        AppManager.protect_cast_services()
        AppManager.fix_projectivy_manager()
        L.ok("Automatyczna optymalizacja Ultra zakończona pomyślnie.")
    else:
        HybridMenu.show()
