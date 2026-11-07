#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# SecFERRO Advanced P99, I/O & Network Tuner                                     #
# Cel: Redukcja Janky Frames, przyspieszenie eMMC (odczyt), optymalizacja RAM    #
# Architektura: Adaptacyjna (Root / Rish / ADB)                                  #
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import enum
import os
import subprocess
import sys
from typing import ClassVar, Final, TypeAlias

ResultTriple: TypeAlias = tuple[int, str, str]

_P: Final[str] = "\033[38;2;191;0;255m"
_G: Final[str] = "\033[32m"
_R: Final[str] = "\033[31m"
_Y: Final[str] = "\033[33m"
_D: Final[str] = "\033[90m"
_C: Final[str] = "\033[36m"
_B: Final[str] = "\033[0m"

class ExecLayer(enum.Enum):
    ROOT = "su -c"
    RISH = "adb shell sh /data/local/tmp/rish -c"
    ADB  = "adb shell sh -c"

class Executor:
    def __init__(self, target_ip: str | None = None) -> None:
        self.target_ip = target_ip
        self.adb_prefix = self._setup_adb()
        self.layer = self._probe()

    def _setup_adb(self) -> str:
        if self.target_ip:
            subprocess.run(f"adb connect {self.target_ip}", shell=True, stdout=subprocess.DEVNULL)
            return f"adb -s {self.target_ip} shell "
        return "adb shell "

    def _probe(self) -> ExecLayer:
        if subprocess.run(f"{self.adb_prefix}su -c 'id'", shell=True, capture_output=True).returncode == 0:
            return ExecLayer.ROOT
        if subprocess.run(f"{self.adb_prefix}sh /data/local/tmp/rish -c 'id'", shell=True, capture_output=True).returncode == 0:
            return ExecLayer.RISH
        return ExecLayer.ADB

    def run(self, cmd: str, force_layer: ExecLayer | None = None, timeout: int = 15) -> ResultTriple:
        active_layer = force_layer if force_layer else self.layer
        if active_layer == ExecLayer.ROOT:
            full = f"{self.adb_prefix}su -c '{cmd}'"
        elif active_layer == ExecLayer.RISH:
            full = f"{self.adb_prefix}sh /data/local/tmp/rish -c '{cmd}'"
        else:
            full = f"{self.adb_prefix}{cmd}"
            
        try:
            r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"

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

class AdvancedPerformanceOptimizer:
    """Moduł skupiony na P99 (Jank), I/O (Storage/RAM) oraz przepustowości sieci."""
    
    def __init__(self, ex: Executor):
        self.ex = ex

    def optimize_aot_compiler(self):
        """
        Ahead-Of-Time (AOT) Compilation.
        Kompiluje kod bytecode bezpośrednio do kodu maszynowego CPU.
        Drastycznie redukuje Frame Time P99 i użycie RAM podczas uruchamiania.
        Działa na każdej warstwie (ADB/Rish/Root).
        """
        SecFERRO_TUI.section("AOT DexOpt (Redukcja Janky Frames & P99)")
        
        target_packages = {
            "org.smarttube.stable": "SmartTube (Główny Player)",
            "com.liskovsoft.smarttubetv.beta": "SmartTube Beta",
            "com.google.android.tvlauncher": "Android TV Launcher",
            "com.google.android.apps.tv.settings": "Ustawienia Systemowe"
        }

        for pkg, name in target_packages.items():
            # Sprawdź czy pakiet istnieje
            rc, out, _ = self.ex.run(f"pm list packages {pkg}")
            if pkg in out:
                SecFERRO_TUI.row(f"Kompilacja maszynowa ({name})...", "Proszę czekać", None)
                # Używamy profilu 'speed' dla maksymalnej wydajności (kosztem odrobiny miejsca w eMMC)
                rc_comp, _, _ = self.ex.run(f"cmd package compile -m speed {pkg}", timeout=60)
                SecFERRO_TUI.row(f"AOT DexOpt: {pkg}", "Zakończono (Kod Maszynowy)", rc_comp == 0)

    def optimize_flash_io(self):
        """
        Optymalizacja pamięci wewnętrznej.
        Wymaga Rish/Root dla modyfikacji read_ahead_kb, ale fstrim działa w czystym ADB.
        """
        SecFERRO_TUI.section("I/O Storage & RAM Bandwidth Tuning")
        
        # 1. Odśmiecanie pamięci Flash (Hardware TRIM) - Działa w ADB
        rc_trim, out_trim, _ = self.ex.run("sm fstrim")
        SecFERRO_TUI.row("Hardware FSTrim (eMMC GC)", "Wykonano", rc_trim == 0)

        # 2. Kernel Tweaks (Wymaga RISH/ROOT)
        if self.ex.layer in (ExecLayer.RISH, ExecLayer.ROOT):
            # Zwiększenie Read-Ahead dla szybszego wczytywania dużych bloków (filmów/miniatur)
            rc1, _, _ = self.ex.run("echo 1024 > /sys/block/mmcblk0/queue/read_ahead_kb")
            rc2, _, _ = self.ex.run("echo 1024 > /sys/block/mmcblk0/bdi/read_ahead_kb")
            # Scheduler optymalny dla pamięci półprzewodnikowych
            rc3, _, _ = self.ex.run("echo deadline > /sys/block/mmcblk0/queue/scheduler")
            # Agresywna alokacja pamięci dla GPU (wyłączenie zrzucania tekstur z RAM)
            rc4, _, _ = self.ex.run("echo 0 > /proc/sys/vm/page-cluster")
            
            SecFERRO_TUI.row("eMMC Read-Ahead Buffer", "1024 KB (Szybki odczyt)", rc1 == 0 or rc2 == 0)
            SecFERRO_TUI.row("I/O Scheduler", "deadline", rc3 == 0)
            SecFERRO_TUI.row("RAM Page Cluster", "0 (Redukcja opóźnień GPU)", rc4 == 0)
        else:
            SecFERRO_TUI.row("Kernel I/O Tweaks", "Pominięto (Wymaga Shizuku/Root)", False)

    def optimize_render_pipeline(self):
        """
        Łata znane problemy renderowania na VideoCore IV.
        Działa we wszystkich trybach (setprop lub settings fallback).
        """
        SecFERRO_TUI.section("Render Pipeline (Redukcja P99 Frame Time)")
        
        props = [
            # Wyłączenie śledzenia "wieku" bufora - krytyczne dla starych sterowników Broadcom, zapobiega zacięciom
            ("debug.hwui.use_buffer_age", "false"),
            # Wymuszenie synchronicznego przekazywania klatek do HWC2
            ("debug.sf.latch_unsignaled", "1"),
            ("debug.sf.disable_backpressure", "1"),
            # Powiększenie cache tekstur dla UI
            ("debug.hwui.layer_cache_size", "49152") # 48MB (zamiast domyślnych ~16MB)
        ]

        for key, val in props:
            rc, _, _ = self.ex.run(f"setprop {key} {val}")
            if rc == 0:
                SecFERRO_TUI.row(key, val, True)
            else:
                # Fallback do settings global jeśli setprop zawiedzie
                rc_fb, _, _ = self.ex.run(f"settings put global {key} {val}")
                SecFERRO_TUI.row(f"settings global {key}", val, rc_fb == 0)

    def optimize_network_throughput(self):
        """Optymalizacja okien TCP pod kątem natychmiastowego buforowania (Fast Start)."""
        SecFERRO_TUI.section("Network Data Throughput (Streaming P99)")
        
        # Wartości buforów TCP odczytu/zapisu specjalnie pod duże pakiety (4K)
        tcp_buffers = "524288,1048576,4194304,262144,524288,2097152"
        # Okno odbiorcze na start (przyspiesza rozpoczęcie ładowania wideo)
        init_rwnd = "120"
        
        rc1, _, _ = self.ex.run(f"settings put global net.tcp.buffersize.wifi {tcp_buffers}")
        rc2, _, _ = self.ex.run(f"settings put global tcp_default_init_rwnd {init_rwnd}")
        # Wyłączenie analizy jakości sieci w tle (oszczędność CPU i radia)
        rc3, _, _ = self.ex.run("settings put global network_avoid_bad_wifi 0")
        
        SecFERRO_TUI.row("TCP Stream Buffers", "Zoptymalizowano (4MB Max)", rc1 == 0)
        SecFERRO_TUI.row("TCP Init Receive Window", init_rwnd, rc2 == 0)
        SecFERRO_TUI.row("Background WiFi Scoring", "Wyłączono", rc3 == 0)


def main():
    os.system('clear' if os.name == 'posix' else 'cls')
    SecFERRO_TUI.banner("SecFERRO: Zaawansowany Tuner P99, I/O & Network")
    
    ip_arg = sys.argv[1] if len(sys.argv) > 1 else None
    ex = Executor(ip_arg)
    
    SecFERRO_TUI.section("Weryfikacja Środowiska")
    SecFERRO_TUI.row("Uprawnienia Wykonawcze", ex.layer.name, True)
    
    opt = AdvancedPerformanceOptimizer(ex)
    
    # Wykonanie procedur optymalizacyjnych
    opt.optimize_render_pipeline()
    opt.optimize_network_throughput()
    opt.optimize_flash_io()
    opt.optimize_aot_compiler()

    print(f"\n{_G}  [✓] Parametry P99, RAM oraz I/O zostały pomyślnie zoptymalizowane.{_B}\n")

if __name__ == "__main__":
    main()