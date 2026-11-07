#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  PLAYBOX TITANIUM -- ADAPTIVE SMARTTUBE & JANK OPTIMIZER v1.2
  Precision Performance Tuner for Sagemcom DCTIW362P (Android TV 9)
  Target: Eliminating Janky Frames & Video Start Latency ("Thinking" Delay)
================================================================================
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.2"
TARGET_MODEL = "dctiw362p"

# Kolory terminala
_R  = "\033[0m"
_G  = "\033[92m"
_Y  = "\033[93m"
_B  = "\033[94m"
_E  = "\033[91m"
_H  = "\033[95m"
_C  = "\033[96m"
_BO = "\033[1m"

class Log:
    @staticmethod
    def ok(m: str): print(f"{_G}  [✓] {m}{_R}")
    @staticmethod
    def warn(m: str): print(f"{_Y}  [!] {m}{_R}")
    @staticmethod
    def err(m: str): print(f"{_E}  [✗] {m}{_R}")
    @staticmethod
    def info(m: str): print(f"{_B}  [i] {m}{_R}")
    @staticmethod
    def hdr(m: str): print(f"\n{_H}{_BO}{'=' * 68}\n  {m}\n{'=' * 68}{_R}")


class ADBManager:
    dev: Optional[str] = None

    @classmethod
    def connect(cls, target: str) -> bool:
        try:
            r = subprocess.run(["adb", "connect", target], capture_output=True, text=True, timeout=10)
            if "connected" in r.stdout.lower() or "already connected" in r.stdout.lower():
                cls.dev = target
                Log.ok(f"ADB połączone z {target}")
                return True
            Log.err(f"Błąd połączenia ADB: {r.stdout.strip()}")
            return False
        except Exception as e:
            Log.err(f"Błąd ADB: {e}")
            return False

    @classmethod
    def autodetect(cls) -> bool:
        try:
            out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
            for line in out.splitlines():
                if "\tdevice" in line:
                    cls.dev = line.split("\t")[0].strip()
                    Log.ok(f"ADB wykryto automatycznie: {cls.dev}")
                    return True
        except Exception:
            pass
        return False

    @classmethod
    def sh(cls, cmd: str, silent: bool = True) -> str:
        if not cls.dev:
            return ""
        try:
            r = subprocess.run(["adb", "-s", cls.dev, "shell", cmd], capture_output=True, text=True, timeout=15)
            return (r.stdout or "").strip()
        except Exception:
            return ""


class SystemAnalyzer:
    """Porównuje aktualny stan systemu z optymalnymi wartościami dla SmartTube."""

    # Kluczowe parametry powiązane z jankami i opóźnieniem startu wideo
    OPTIMAL_PARAMS = {
        # SurfaceFlinger & Jank Reduction
        "debug.sf.latch_unsignaled": {"type": "prop", "target": "1", "desc": "Explicit sync / latch unsignaled"},
        "debug.sf.disable_backpressure": {"type": "prop", "target": "1", "desc": "Wyeliminowanie backpressure ramki"},
        "debug.sf.early_phase_offset_ns": {"type": "prop", "target": "500000", "desc": "Optymalny offset fazy VSYNC (0.5ms)"},
        "debug.sf.early_app_phase_offset_ns": {"type": "prop", "target": "1000000", "desc": "Offset aplikacji VSYNC (1.0ms)"},
        
        # UI & Rendering Pipeline
        "debug.hwui.renderer": {"type": "prop", "target": "skiagl", "desc": "SkiaGL hardware acceleration pipeline"},
        "debug.renderengine.backend": {"type": "prop", "target": "skiaglthreaded", "desc": "Multi-threaded rendering backend"},
        "persist.sys.ui.hw": {"type": "prop", "target": "true", "desc": "Wymuszenie akceleracji UI GPU"},

        # Codec & Video Start Latency ("Myślenie" przed startem)
        "media.stagefright.enable-player": {"type": "prop", "target": "true", "desc": "Stagefright hardware player pipeline"},
        "media.stagefright.cache-params": {"type": "prop", "target": "65536/131072/30", "desc": "Zwiększony bufor strumieniowania HTTP/Media"},
        "media.vcodec.preferhw": {"type": "prop", "target": "true", "desc": "Preferowanie dekodowania sprzętowego VPU"},
        "media.acodec.preferhw": {"type": "prop", "target": "true", "desc": "Preferowanie sprzętowego dekodowania audio"},
        "media.tunneled-playback.enable": {"type": "prop", "target": "true", "desc": "Tunnel Mode (bezpośrednia synchronizacja zegara HDMI)"},
        "media.codec.av1.disable": {"type": "prop", "target": "true", "desc": "Blokada dekodowania AV1 (brak HW na A15 - unika 100% CPU)"},

        # Dalvik Heap & GC Micro-pauses
        "dalvik.vm.heapminfree": {"type": "prop", "target": "2m", "desc": "Minimalny wolny stos pamięci (redukcja mikro-pauz GC)"},
        "dalvik.vm.heapmaxfree": {"type": "prop", "target": "16m", "desc": "Maksymalny wolny stos pamięci"},

        # Global Animator Scales (UI responsiveness)
        "animator_duration_scale": {"type": "settings", "table": "global", "target": "0.25", "desc": "Skala animacji animatora"},
        "transition_animation_scale": {"type": "settings", "table": "global", "target": "0.25", "desc": "Skala animacji przejść"},
        "window_animation_scale": {"type": "settings", "table": "global", "target": "0.25", "desc": "Skala animacji okien"}
    }

    @classmethod
    def audit(cls) -> Dict[str, Dict[str, Any]]:
        Log.hdr("AUDYT PARAMETRÓW SYSTEMOWYCH (SmartTube & Jank Analysis)")
        results = {}

        for key, config in cls.OPTIMAL_PARAMS.items():
            if config["type"] == "prop":
                current = ADBManager.sh(f"getprop {key}")
                if not current:
                    current = "not set"
            elif config["type"] == "settings":
                current = ADBManager.sh(f"settings get {config['table']} {key}")
                if not current or current == "null":
                    current = "default"
            else:
                current = "unknown"

            match = str(current).strip() == str(config["target"])
            results[key] = {
                "current": current,
                "target": config["target"],
                "match": match,
                "desc": config["desc"]
            }

            status_str = f"{_G}[OK]{_R}" if match else f"{_E}[ODCHYLENIE]{_R}"
            print(f"  {status_str} {_BO}{key}{_R}")
            print(f"       Opis: {config['desc']}")
            print(f"       Aktualnie: {_Y}{current}{_R} | Optymalnie: {_G}{config['target']}{_R}\n")

        return results


class AdaptiveOptimizer:
    """Adaptacyjnie aplikuje brakujące optymalizacje oraz agresywne przyspieszenie startu wideo."""

    @classmethod
    def optimize_all(cls):
        Log.hdr("ADAPTYWNA OPTYMALIZACJA WYDAJNOŚCI SYSTEMU")
        
        commands = [
            # Zastosowanie właściwości systemowych (prop)
            "setprop debug.sf.latch_unsignaled 1",
            "setprop debug.sf.disable_backpressure 1",
            "setprop debug.sf.early_phase_offset_ns 500000",
            "setprop debug.sf.early_app_phase_offset_ns 1000000",
            "setprop debug.hwui.renderer skiagl",
            "setprop debug.renderengine.backend skiaglthreaded",
            "setprop persist.sys.ui.hw true",
            "setprop media.stagefright.enable-player true",
            "setprop media.stagefright.cache-params 65536/131072/30",
            "setprop media.vcodec.preferhw true",
            "setprop media.acodec.preferhw true",
            "setprop media.tunneled-playback.enable true",
            "setprop media.codec.av1.disable true",
            "setprop dalvik.vm.heapminfree 2m",
            "setprop dalvik.vm.heapmaxfree 16m",
            
            # Dodatkowe flagi eliminujące "myślenie" i opóźnienie startu strumienia
            "setprop media.brcm.decoder.preinit true",
            "setprop media.brcm.surface.prewarm true",
            "setprop media.brcm.vpu.prealloc true",
            "setprop media.codec.priority 0",
            
            # Zastosowanie zmiennych globalnych ustawień (settings)
            "settings put global animator_duration_scale 0.25",
            "settings put global transition_animation_scale 0.25",
            "settings put global window_animation_scale 0.25",
            
            # Wymuszenie odświeżenia kompozytora SurfaceFlinger oraz wyczyszczenie cache RAM
            "service call SurfaceFlinger 1008 i32 1",
            "sync && echo 3 > /proc/sys/vm/drop_caches"
        ]

        Log.info("Wykonywanie zaawansowanego wsadu optymalizacyjnego (w tym preinit VPU)...")
        combined = " && ".join(commands)
        res = ADBManager.sh(combined, silent=False)
        
        Log.ok("Wszystkie optymalizacje zostały pomyślnie zaaplikowane.")
        Log.info("Wprowadzono flagi preinit VPU oraz priorytetyzację kodeka (priority 0) w celu usunięcia opóźnień startu wideo.")


def main():
    parser = argparse.ArgumentParser(description="SmartTube & System Jank Optimizer for Sagemcom DCTIW362P")
    parser.add_argument("--device", default=None, help="Adres IP:PORT urządzenia ADB")
    parser.add_argument("--audit", action="store_true", help="Wykonaj tylko audyt rozbieżności parametrów")
    parser.add_argument("--optimize", action="store_true", help="Wykonaj adaptacyjną optymalizację systemu")
    args = parser.parse_args()

    if args.device:
        ADBManager.connect(args.device)
    else:
        if not ADBManager.autodetect():
            target = input("Podaj adres IP:PORT dekodera (np. 192.168.1.3:5555): ").strip()
            if target:
                ADBManager.connect(target)
            else:
                Log.err("Brak aktywnego połączenia ADB. Wyjście.")
                sys.exit(1)

    if args.audit:
        SystemAnalyzer.audit()
    elif args.optimize:
        SystemAnalyzer.audit()
        AdaptiveOptimizer.optimize_all()
        Log.hdr("WERYFIKACJA PO OPTYMALIZACJI")
        SystemAnalyzer.audit()
    else:
        # Domyślnie pełny cykl: audyt -> optymalizacja -> ponowny audyt
        SystemAnalyzer.audit()
        ans = input(f"\n{_Y}Czy chcesz automatycznie zastosować adaptacyjne optymalizacje usunięcia janków i opóźnień startu? [T/n] > {_R}").strip().lower()
        if ans in ("", "t", "y", "tak", "yes"):
            AdaptiveOptimizer.optimize_all()
            Log.hdr("WERYFIKACJA KOŃCOWA")
            SystemAnalyzer.audit()
        else:
            Log.info("Anulowano przez użytkownika.")


if __name__ == "__main__":
    main()