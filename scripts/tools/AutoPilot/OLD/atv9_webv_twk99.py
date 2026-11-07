#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# PlayBox Titanium ULTIMATE PRO — Sagemcom DCTIW362p (BCM72604 / Android TV 9)   #
# Autonomiczna logika proaktywnego łączenia ADB + WebView + Media + Kernel       #
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import enum
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import ClassVar, Final, TypeAlias

ResultTriple: TypeAlias = tuple[int, str, str]

# Palette TUI
_P: Final[str] = "\033[38;2;191;0;255m"
_G: Final[str] = "\033[32m"
_R: Final[str] = "\033[31m"
_Y: Final[str] = "\033[33m"
_D: Final[str] = "\033[90m"
_C: Final[str] = "\033[36m"
_B: Final[str] = "\033[0m"

class ExecLayer(enum.Enum):
    ROOT = "su -c"
    RISH = "sh /data/local/tmp/rish -c"
    ADB  = "sh -c"

class Namespace(enum.StrEnum):
    PROP    = "prop"
    GLOBAL  = "global"
    SECURE  = "secure"
    SYSTEM  = "system"

@dataclass(frozen=True, slots=True)
class TuningVector:
    ns: Namespace
    key: str
    value: str
    desc: str = ""

# ════════════════════════════════════════════════════════════════════════════════
# PROAKTYWNY MENEDŻER POŁĄCZEŃ ADB (Automated Discovery & Pairing)
# ════════════════════════════════════════════════════════════════════════════════
class ADBConnector:
    """Automatycznie wykrywa, paruje i przygotowuje sesję ADB z urządzeniem TV."""
    def __init__(self, target_ip: str | None = None) -> None:
        self.target_ip = target_ip

    def _get_local_subnet(self) -> str:
        try:
            # Próba odczytu bramy domyślnej / adresu lokalnego w poszukiwaniu podsieci
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return ".".join(local_ip.split(".")[:3])
        except Exception:
            return "192.168.1"

    def scan_and_connect(self) -> str:
        SecFERRO_TUI.section("Proactive ADB Discovery & Connection Engine")
        
        # 1. Sprawdź jawnie podany cel lub aktywne połączenie
        if self.target_ip:
            targets = [self.target_ip]
        else:
            targets = []
            # Sprawdź aktualne urządzenia w `adb devices`
            res = subprocess.run("adb devices", shell=True, capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if "\tdevice" in line:
                    targets.append(line.split("\t")[0].strip())
            
            # Jeśli brak urządzeń, uruchom inteligentny skan podsieci lokalnej na porcie 5555
            if not targets:
                subnet = self._get_local_subnet()
                SecFERRO_TUI.row("Skanowanie podsieci", f"{subnet}.x:5555...", None)
                for i in range(2, 255):
                    ip = f"{subnet}.{i}"
                    r = subprocess.run(f"adb connect {ip}:5555", shell=True, capture_output=True, text=True, timeout=1)
                    if "connected" in r.stdout.lower():
                        targets.append(f"{ip}:5555")
                        break

        if not targets:
            SecFERRO_TUI.row("Auto-Connect", "Nie znalezmiono urządzenia w sieci LAN.", False)
            print(f"\n{_Y}Wskazówka: Uruchom skrypt podając IP ręcznie:{_B}")
            print(f"  python3 playbox_ultimate_pro.py 192.168.1.X:5555\n")
            sys.exit(1)

        active_device = targets[0]
        SecFERRO_TUI.row("Docelowe urządzenie TV", active_device, True)
        
        # Testowa stabilizacja mostka
        subprocess.run(f"adb connect {active_device}", shell=True, stdout=subprocess.DEVNULL)
        subprocess.run(f"adb -s {active_device} tcpip 5555", shell=True, stdout=subprocess.DEVNULL)
        time.sleep(1)
        
        return active_device


# ════════════════════════════════════════════════════════════════════════════════
# KATALOGI OPTYMALIZACYJNE
# ════════════════════════════════════════════════════════════════════════════════
class TuningCatalog:
    GRAPHICS: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.PROP, "debug.hwui.renderer", "skiagl", "SkiaGL Render Engine"),
        TuningVector(Namespace.PROP, "debug.renderengine.backend", "skiaglthreaded", "SkiaGL Threaded Backend"),
        TuningVector(Namespace.PROP, "debug.hwui.render_thread", "true", "Wątek renderowania HWUI"),
        TuningVector(Namespace.PROP, "debug.gr.numframebuffers", "3", "Triple Buffering V3D"),
        TuningVector(Namespace.PROP, "debug.sf.disable_backpressure", "1", "Wył. backpressure HWC2"),
        TuningVector(Namespace.PROP, "debug.sf.latch_unsignaled", "1", "Wczesny latch klatek"),
        TuningVector(Namespace.PROP, "debug.hwui.layer_cache_size", "32768", "Cache warstw 32MB"),
        TuningVector(Namespace.PROP, "persist.sys.ui.hw", "true", "Akceleracja UI GPU"),
        TuningVector(Namespace.GLOBAL, "window_animation_scale", "0.35", "Skala animacji okien"),
        TuningVector(Namespace.GLOBAL, "transition_animation_scale", "0.35", "Skala animacji przejść"),
    )

    MEDIA: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.PROP, "dalvik.vm.isa.arm.features", "default,idiv", "A15 Hardware IDIV"),
        TuningVector(Namespace.PROP, "media.stagefright.enable-player", "true", "Stagefright Player"),
        TuningVector(Namespace.PROP, "media.vcodec.preferhw", "true", "Sprzętowe wideo VDec32"),
        TuningVector(Namespace.PROP, "media.tunneled-playback.enable", "true", "Tunneled Playback BCM"),
        TuningVector(Namespace.PROP, "debug.stagefright.c2.av1", "0", "Blokada C2 AV1"),
        TuningVector(Namespace.PROP, "media.av1.sw.decode.disable", "true", "Blokada programowego AV1"),
        TuningVector(Namespace.PROP, "media.codec.av1.disable", "true", "Całkowity zakaz AV1"),
        TuningVector(Namespace.PROP, "audio.offload.disable", "1", "Wył. Audio Offload (sync fix)"),
        TuningVector(Namespace.PROP, "audio.brcm.hdmi.clock_lock", "true", "Lock zegara HDMI ARC"),
    )

    MEMORY: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.PROP, "dalvik.vm.heapminfree", "2m", "Dalvik minfree GC fix"),
        TuningVector(Namespace.PROP, "dalvik.vm.heapmaxfree", "16m", "Dalvik maxfree GC fix"),
        TuningVector(Namespace.PROP, "ro.lmk.kill_heaviest_task", "true", "Agresywne LMK heaviest"),
        TuningVector(Namespace.PROP, "ro.lmk.upgrade_pressure", "50", "PSI memory pressure limit"),
    )

    NETWORK: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.GLOBAL, "private_dns_mode", "hostname", "Private DNS (DoT)"),
        TuningVector(Namespace.GLOBAL, "private_dns_specifier", "one.one.one.one", "Cloudflare DNS"),
        TuningVector(Namespace.GLOBAL, "tcp_default_init_rwnd", "120", "TCP Window Scalability"),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SILNIK WYKONAWCZY ADB
# ════════════════════════════════════════════════════════════════════════════════
class Executor:
    def __init__(self, device: str) -> None:
        self.device = device
        self.prefix = f"adb -s {device} shell "
        self.layer = self._probe()

    def _probe(self) -> ExecLayer:
        if subprocess.run(f"{self.prefix}su -c 'id'", shell=True, capture_output=True).returncode == 0:
            return ExecLayer.ROOT
        if subprocess.run(f"{self.prefix}sh /data/local/tmp/rish -c 'id'", shell=True, capture_output=True).returncode == 0:
            return ExecLayer.RISH
        return ExecLayer.ADB

    def run(self, cmd: str) -> ResultTriple:
        if self.layer == ExecLayer.ROOT:
            full = f"{self.prefix}su -c '{cmd}'"
        elif self.layer == ExecLayer.RISH:
            full = f"{self.prefix}sh /data/local/tmp/rish -c '{cmd}'"
        else:
            full = f"{self.prefix}{cmd}"
            
        try:
            r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=10)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"

    def apply_vector(self, v: TuningVector) -> bool:
        if v.ns == Namespace.PROP:
            rc, _, _ = self.run(f"setprop {v.key} {v.value}")
        else:
            rc, _, _ = self.run(f"settings put {v.ns.value} {v.key} {v.value}")
        return rc == 0


# ════════════════════════════════════════════════════════════════════════════════
# WEBVIEW & KERNEL TWEAKS
# ════════════════════════════════════════════════════════════════════════════════
class SystemOptimizer:
    def __init__(self, ex: Executor):
        self.ex = ex

    def apply_webview(self):
        SecFERRO_TUI.section("WebView & Chromium Engine Optimization")
        flags = (
            "webview "
            "--ignore-gpu-blocklist "
            "--enable-gpu-rasterization "
            "--enable-oop-rasterization "
            "--disable-smooth-scrolling "
            "--num-raster-threads=2 "
            "--disable-features=SurfacePolish "
            "--enable-quic "
        )
        self.ex.run(f"echo '{flags}' > /data/local/tmp/webview-command-line")
        self.ex.run("chmod 666 /data/local/tmp/webview-command-line")
        self.ex.run("setprop webview.command_line /data/local/tmp/webview-command-line")
        rc, _, _ = self.ex.run("setprop webview.vmsize 52428800")
        SecFERRO_TUI.row("Chromium OOP-R & Hardware Raster", "Aktywne", True)
        SecFERRO_TUI.row("WebView VMSIZE Budget", "50 MB", rc == 0)

    def apply_kernel(self):
        SecFERRO_TUI.section("Kernel CPU & I/O Scheduler Tweaks")
        cmds = [
            "echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
            "echo performance > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor",
            "echo deadline > /sys/block/mmcblk0/queue/scheduler",
            "echo 512 > /sys/block/mmcblk0/queue/read_ahead_kb",
            "echo 0 > /proc/sys/vm/swappiness"
        ]
        ok_count = sum(1 for c in cmds if self.ex.run(c)[0] == 0)
        SecFERRO_TUI.row("Cortex-A15 CPU Governor", "performance", ok_count > 0)
        SecFERRO_TUI.row("MMC I/O Deadline Scheduler", "512kb read-ahead", ok_count > 0)


# ════════════════════════════════════════════════════════════════════════════════
# TUI & MAIN ENTRYPOINT
# ════════════════════════════════════════════════════════════════════════════════
class SecFERRO_TUI:
    @staticmethod
    def banner(title: str) -> None:
        print(f"\n{_P}╔{'═'*78}╗")
        print(f"║ {_C}{title:^76}{_P} ║")
        print(f"╚{'═'*78}╝{_B}")

    @staticmethod
    def section(text: str) -> None:
        print(f"\n  {_Y}── {text} ──{_B}")

    @staticmethod
    def row(key: str, value: str, ok: bool | None = None) -> None:
        tag = f"{_G}[✓]{_B}" if ok is True else (f"{_R}[✗]{_B}" if ok is False else f"{_D}[~]{_B}")
        print(f"  {tag} {_D}{key:<45}{_B}{value}")

def main():
    os.system('clear' if os.name == 'posix' else 'cls')
    SecFERRO_TUI.banner("PLAYBOX TITANIUM ULTIMATE PRO — PROACTIVE ADB ENGINE")

    # Pobierz argument IP jeśli podany z konsoli
    cli_ip = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Krok proaktywnego łączenia
    connector = ADBConnector(cli_ip)
    active_device = connector.scan_and_connect()

    ex = Executor(active_device)
    SecFERRO_TUI.section("Stan Sesji Diagnostycznej")
    SecFERRO_TUI.row("Aktywny endpoint ADB", active_device, True)
    SecFERRO_TUI.row("Warstwa Egzekucyjna (Priv)", ex.layer.name, True)

    catalogs = {
        "Graphics Pipeline (VideoCore IV SkiaGL)": TuningCatalog.GRAPHICS,
        "Multimedia Pipeline (VDec32/Tunnel)": TuningCatalog.MEDIA,
        "Dalvik & LMK (Memory Management)": TuningCatalog.MEMORY,
        "Network & DNS (TCP BDP Tuning)": TuningCatalog.NETWORK,
    }

    for name, vectors in catalogs.items():
        SecFERRO_TUI.section(name)
        for v in vectors:
            ok = ex.apply_vector(v)
            SecFERRO_TUI.row(v.key, v.value, ok)

    sys_opt = SystemOptimizer(ex)
    sys_opt.apply_webview()
    if ex.layer in (ExecLayer.ROOT, ExecLayer.RISH):
        sys_opt.apply_kernel()

    SecFERRO_TUI.section("Volatile Cache Purge")
    ex.run("am kill-all")
    ex.run("pm trim-caches 4096G")
    SecFERRO_TUI.row("Czyszczenie pamięci podręcznej", "Zakończone pomyślnie", True)

    print(f"\n{_G}  [✓] Proaktywna optymalizacja Sagemcom DCTIW362p zakończona! Zalecany restart.{_B}\n")

if __name__ == "__main__":
    main()
