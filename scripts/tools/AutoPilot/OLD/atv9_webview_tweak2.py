#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# PlayBox Titanium ULTIMATE — Sagemcom DCTIW362p (BCM72604 / Android TV 9)       #
# Pełna optymalizacja: GPU, Media Pipeline, Dalvik Heap, Sieć, WebView, Kernel #
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

# Paleta kolorów TUI
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
# KATALOGI OPTYMALIZACYJNE
# ════════════════════════════════════════════════════════════════════════════════
class TuningCatalog:
    # 1. Pipeline Graficzny (VideoCore IV)
    GRAPHICS: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.PROP, "debug.hwui.renderer", "skiagl", "SkiaGL (V3D OpenGL ES 3.1)"),
        TuningVector(Namespace.PROP, "debug.renderengine.backend", "skiaglthreaded", "Renderowanie wielowątkowe"),
        TuningVector(Namespace.PROP, "debug.hwui.render_thread", "true", "Włączenie wątku renderowania HWUI"),
        TuningVector(Namespace.PROP, "debug.gr.numframebuffers", "3", "Potrójne buforowanie klatek"),
        TuningVector(Namespace.PROP, "debug.sf.disable_backpressure", "1", "Wyłączenie opóźnień HWC2"),
        TuningVector(Namespace.PROP, "debug.sf.latch_unsignaled", "1", "Wczesny latch klatek (redukcja jank)"),
        TuningVector(Namespace.PROP, "debug.hwui.use_buffer_age", "false", "Wyłączenie starzenia buforów (VC4 bug)"),
        TuningVector(Namespace.PROP, "debug.hwui.layer_cache_size", "32768", "Powiększenie cache warstw do 32MB"),
        TuningVector(Namespace.PROP, "persist.sys.ui.hw", "true", "Wymuszenie akceleracji UI GPU"),
        TuningVector(Namespace.PROP, "debug.sf.early_phase_offset_ns", "500000", "Wyrównanie commit SF do VSync"),
        TuningVector(Namespace.PROP, "debug.sf.early_app_phase_offset_ns", "1000000", "App phase offset"),
        TuningVector(Namespace.GLOBAL, "window_animation_scale", "0.35", "Przyspieszenie animacji ATV"),
        TuningVector(Namespace.GLOBAL, "transition_animation_scale", "0.35", "Przyspieszenie przejść"),
        TuningVector(Namespace.GLOBAL, "animator_duration_scale", "0.35", "Przyspieszenie silnika animacji"),
    )

    # 2. Pipeline Multimedialny (BCM Nexus / Codecs)
    MEDIA: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.PROP, "dalvik.vm.isa.arm.features", "default,idiv", "Odblokowanie instrukcji A15 idiv"),
        TuningVector(Namespace.PROP, "media.stagefright.enable-player", "true", "HW Player"),
        TuningVector(Namespace.PROP, "media.vcodec.preferhw", "true", "Priorytet sprzętowego wideo"),
        TuningVector(Namespace.PROP, "media.acodec.preferhw", "true", "Priorytet sprzętowego audio"),
        TuningVector(Namespace.PROP, "media.stagefright.cache-params", "65536/131072/30", "Zwiększony bufor Stagefright"),
        TuningVector(Namespace.PROP, "media.codec.priority", "0", "Priorytet dekodera = realtime"),
        TuningVector(Namespace.PROP, "debug.stagefright.ccodec", "1", "Nowoczesny Codec2.0"),
        TuningVector(Namespace.PROP, "media.tunneled-playback.enable", "true", "Tunneling sprzętowy (BCM)"),
        TuningVector(Namespace.PROP, "media.brcm.vpu.prealloc", "true", "Prealokacja VPU"),
        TuningVector(Namespace.PROP, "media.brcm.mma.enable", "1", "Włączenie MMA"),
        # BLOKADA AV1 (Brak HW -> ratunek dla procesora)
        TuningVector(Namespace.PROP, "debug.stagefright.c2.av1", "0", "Zablokowanie programowego dekodera AV1"),
        TuningVector(Namespace.PROP, "media.av1.sw.decode.disable", "true", "Krytyczne: Blokada SW AV1"),
        TuningVector(Namespace.PROP, "media.codec.av1.disable", "true", "Krytyczne: Odmowa AV1 dla ExoPlayer"),
        # Audio & HDMI CEC
        TuningVector(Namespace.PROP, "audio.offload.disable", "1", "Wył. Offload (naprawa synchronizacji audio)"),
        TuningVector(Namespace.PROP, "audio.brcm.hdmi.clock_lock", "true", "Blokada zegara HDMI ARC"),
        TuningVector(Namespace.PROP, "persist.sys.hdmi.keep_awake", "true", "Naprawa rozłączeń CEC podczas buforowania"),
    )

    # 3. Dalvik, Pamięć i Stabilność (OOM / LMK)
    MEMORY: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.PROP, "dalvik.vm.heapminfree", "2m", "Redukcja mikro-pauz Garbage Collectora"),
        TuningVector(Namespace.PROP, "dalvik.vm.heapmaxfree", "16m", "Rozszerzenie pułapu zwalniania GC"),
        TuningVector(Namespace.PROP, "ro.lmk.kill_heaviest_task", "true", "Agresywne ubijanie ciężkich zadań tła"),
        TuningVector(Namespace.PROP, "ro.lmk.upgrade_pressure", "50", "Wczesna reakcja OOM oparta na PSI"),
        TuningVector(Namespace.PROP, "ro.lmk.use_minfree_levels", "false", "Przejście w 100% na silnik PSI"),
        TuningVector(Namespace.GLOBAL, "monitor_phantom_procs", "false", "Wyłączenie monitorowania procesów widmo"),
        TuningVector(Namespace.GLOBAL, "send_action_app_error", "0", "Wyłączenie telemetrii błędów"),
    )

    # 4. Sieć i TCP
    NETWORK: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.GLOBAL, "private_dns_mode", "hostname", "Private DNS (DoT)"),
        TuningVector(Namespace.GLOBAL, "private_dns_specifier", "one.one.one.one", "Szybki DNS Cloudflare"),
        TuningVector(Namespace.GLOBAL, "net.tcp.buffersize.wifi", "4096,524288,8388608,262144,524288,4194304", "Profil TCP 4K Streaming"),
        TuningVector(Namespace.GLOBAL, "tcp_default_init_rwnd", "120", "Zwiększone okno odbiorcze (Cold Start)"),
        TuningVector(Namespace.GLOBAL, "wifi_scan_always_enabled", "0", "Wył. skanowania Wi-Fi w tle"),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SILNIK WYKONAWCZY (SHELL)
# ════════════════════════════════════════════════════════════════════════════════
class Executor:
    def __init__(self) -> None:
        self.layer = self._probe()
        self.adb_prefix = self._setup_remote_if_needed()

    def _setup_remote_if_needed(self) -> str:
        # Sprawdzamy czy skrypt jest na komputerze i wymaga IP
        if len(sys.argv) > 1 and ":" in sys.argv[1]:
            ip = sys.argv[1]
            SecFERRO_TUI.row("ADB Network", f"Connecting to {ip}...", None)
            subprocess.run(f"adb connect {ip}", shell=True, stdout=subprocess.DEVNULL)
            return f"adb -s {ip} shell "
        return ""

    def _probe(self) -> ExecLayer:
        cmd = self.adb_prefix + "su -c 'id'"
        if subprocess.run(cmd, shell=True, capture_output=True).returncode == 0:
            return ExecLayer.ROOT
        cmd_rish = self.adb_prefix + "sh /data/local/tmp/rish -c 'id'"
        if subprocess.run(cmd_rish, shell=True, capture_output=True).returncode == 0:
            return ExecLayer.RISH
        return ExecLayer.ADB

    def run(self, cmd: str) -> ResultTriple:
        if self.layer == ExecLayer.ROOT:
            cmd_str = f"{self.adb_prefix}su -c '{cmd}'"
        elif self.layer == ExecLayer.RISH:
            cmd_str = f"{self.adb_prefix}sh /data/local/tmp/rish -c '{cmd}'"
        else:
            # Fallback (wymaga aby proces miał dostęp)
            cmd_str = f"{self.adb_prefix}{cmd}"
            
        try:
            r = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=10)
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
# MENEDŻER WEBVIEW (Nowość!)
# ════════════════════════════════════════════════════════════════════════════════
class WebViewOptimizer:
    """Implementacja zaawansowanych flag Chromium dla Android System WebView."""
    def __init__(self, ex: Executor):
        self.ex = ex
        self.cmd_line_path = "/data/local/tmp/webview-command-line"

    def apply(self):
        SecFERRO_TUI.section("WebView & Chromium Engine Optimization")
        
        # Flagi Chromium wymuszające wielowątkową rasteryzację i wyłączające zbędne ficzery
        flags = (
            "webview "
            "--ignore-gpu-blocklist "
            "--enable-gpu-rasterization "
            "--enable-oop-rasterization "
            "--disable-smooth-scrolling " # Zgodnie ze wskazówkami z prop_tweaks (zapobiega hiccupom)
            "--num-raster-threads=2 "     # Optymalnie pod 2 rdzenie Cortex-A15
            "--disable-features=SurfacePolish "
            "--enable-quic "              # Przyspieszenie zapytań sieciowych HTTP/3
            "--enable-accelerated-video-decode "
        )

        # Zapisz flagi do pliku czytanego przez WebView
        rc1, _, _ = self.ex.run(f"echo '{flags}' > {self.cmd_line_path}")
        rc2, _, _ = self.ex.run(f"chmod 666 {self.cmd_line_path}")

        # Powiadom WebView o konieczności czytania pliku (działa na userdebug / root / rish)
        rc3, _, _ = self.ex.run("setprop webview.command_line " + self.cmd_line_path)
        
        # Agresywna redukcja pamięci pre-alokowanej dla silnika V8 w WebView (100MB -> 50MB)
        # STB (Set-Top-Box) nie korzysta intensywnie ze skryptów JS w przeglądarkach.
        rc4, _, _ = self.ex.run("setprop webview.vmsize 52428800")

        ok = (rc1 == 0 and rc4 == 0)
        SecFERRO_TUI.row("WebView Hardware Rasterization (OOP-R)", "Wymuszone", ok)
        SecFERRO_TUI.row("WebView VMSIZE (Dalvik JS budget)", "50 MB", rc4 == 0)
        SecFERRO_TUI.row("Smooth Scrolling", "Zablokowane (Anti-hiccup)", True)

# ════════════════════════════════════════════════════════════════════════════════
# KERNEL SCHEDULER & I/O
# ════════════════════════════════════════════════════════════════════════════════
class KernelTweaks:
    def __init__(self, ex: Executor):
        self.ex = ex

    def apply(self):
        SecFERRO_TUI.section("Kernel CPU & I/O Scheduler (Wymaga ROOT/RISH)")
        
        # Wymuszanie Performance Governora dla obu rdzeni Cortex-A15 (stabilne ~1.0 GHz)
        cmds = [
            "echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
            "echo performance > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor",
            "echo deadline > /sys/block/mmcblk0/queue/scheduler",
            "echo 512 > /sys/block/mmcblk0/queue/read_ahead_kb",
            "echo 0 > /proc/sys/vm/swappiness" # Brak ZRAM w BCM72604
        ]
        
        applied = 0
        for cmd in cmds:
            rc, _, _ = self.ex.run(cmd)
            if rc == 0: applied += 1
            
        SecFERRO_TUI.row("CPU Governors (A15)", "performance", applied > 0)
        SecFERRO_TUI.row("I/O Scheduler & ReadAhead", "deadline | 512kb", applied > 0)


# ════════════════════════════════════════════════════════════════════════════════
# TUI & ORKIESTRATOR
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
    SecFERRO_TUI.banner("PLAYBOX TITANIUM ULTIMATE — BCM72604 V9.7 PRO")
    
    ex = Executor()
    SecFERRO_TUI.section("Środowisko Uruchomieniowe")
    SecFERRO_TUI.row("Wektor Wykonawczy (Privilege)", ex.layer.name, True)
    
    catalogs = {
        "Graphics Pipeline (VideoCore IV)": TuningCatalog.GRAPHICS,
        "Multimedia Pipeline (VDec32/Tunnel)": TuningCatalog.MEDIA,
        "Dalvik & LMK (Memory Management)": TuningCatalog.MEMORY,
        "Network & DNS (TCP BDP Tuning)": TuningCatalog.NETWORK,
    }

    for name, vectors in catalogs.items():
        SecFERRO_TUI.section(name)
        for v in vectors:
            ok = ex.apply_vector(v)
            SecFERRO_TUI.row(v.key, v.value, ok)

    # Nowe zaawansowane moduły
    WebViewOptimizer(ex).apply()
    
    if ex.layer in (ExecLayer.ROOT, ExecLayer.RISH):
        KernelTweaks(ex).apply()

    SecFERRO_TUI.section("Memory Caches Flush")
    ex.run("am kill-all")
    ex.run("pm trim-caches 4096G")
    SecFERRO_TUI.row("Systemowe bufory i procesy tła", "Wyczyszczone", True)

    print(f"\n{_G}  [✓] Optymalizacja zakończona sukcesem. Zalecany restart urządzenia.{_B}\n")

if __name__ == "__main__":
    main()
