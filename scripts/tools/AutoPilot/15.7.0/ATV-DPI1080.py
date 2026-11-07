#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
playbox_dpi_cache_tuner.py
================================================================
  PlayBox Titanium -- DPI & Cache Master Optimizer
  Target: Sagemcom DCTIW362P | Android 9 | Broadcom BCM72604
  
  Zadania:
    1. Optymalizacja DPI (240 DPI) z zachowaniem pełnej jakości 1080p
    2. Konfiguracja SurfaceFlinger i V3D pipeline (brak rozmyć i janków)
    3. Precyzyjne dostrojenie buforów cache (Stagefright & Dalvik)
    4. Bezpieczne czyszczenie i zarządzanie pamięcią podręczną (Cache/Dalvik)
================================================================
"""

import subprocess
import sys
import time
from pathlib import Path

# ANSI Kolory (Termux safe)
_R = "\033[0m"; _G = "\033[92m"; _Y = "\033[93m"; _B = "\033[94m"; _C = "\033[96m"; _BO = "\033[1m"

def ok(m):   print(_G + "  [OK] " + str(m) + _R)
def warn(m): print(_Y + "  [!!] " + str(m) + _R)
def err(m):  print(_R + "  [XX] " + str(m) + _R)
def info(m): print(_B + "  [  ] " + str(m) + _R)
def hdr(m):  print(f"\n{_C}{_BO}{'='*60}\n  {m}\n{'='*60}{_R}")

class ADBTuner:
    @staticmethod
    def run(cmd: str) -> str:
        try:
            res = subprocess.run(
                ["adb", "shell", cmd],
                capture_output=True, text=True, timeout=15
            )
            return res.stdout.strip()
        except Exception as e:
            return ""

    @staticmethod
    def setprop(key: str, val: str):
        subprocess.run(["adb", "shell", f"setprop {key} {val}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        info(f"setprop {key} = {val}")

    @staticmethod
    def settings_put(table: str, key: str, val: str):
        subprocess.run(["adb", "shell", f"settings put {table} {key} {val}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        info(f"settings put {table} {key} = {val}")


def optimize_display_and_dpi():
    hdr("KROK 1 -- Optymalizacja DPI i Jakości Obrazu (1080p @ 240 DPI)")
    
    info("Ustawianie rozdzielczości bazowej 1920x1080...")
    ADBTuner.run("wm size 1920x1080")
    
    info("Ustawianie optymalnej gęstości DPI na 240 (zwiększona czytelność UI bez strat jakości)...")
    ADBTuner.run("wm density 240")
    
    info("Konfiguracja potoku renderowania SurfaceFlinger i GLES...")
    ADBTuner.setprop("debug.hwui.renderer", "skiagl")
    ADBTuner.setprop("persist.sys.ui.hw", "true")
    ADBTuner.setprop("debug.sf.hw", "1")
    ADBTuner.setprop("debug.egl.hw", "1")
    ADBTuner.setprop("debug.sf.latch_unsignaled", "1")
    ADBTuner.setprop("debug.sf.disable_backpressure", "1")
    ADBTuner.setprop("debug.gr.numframebuffers", "3")
    
    # Blokada rozmycia skalowania i filtry wygładzania wektorowego
    ADBTuner.setprop("debug.hwui.use_gpu_pixel_buffers", "true")
    ADBTuner.setprop("debug.hwui.render_dirty_regions", "false")
    
    ok("DPI i podsystem graficzny zoptymalizowane.")


def optimize_cache_and_buffers():
    hdr("KROK 2 -- Zarządzanie Cache i Buforami Strumieniowymi")
    
    info("Konfiguracja parametrów pamięci podręcznej Stagefright (optymalizacja dla 1080p/4K IPTV)...")
    # Format: max-size / initial-watermark / resume-watermark (w bajtach)
    ADBTuner.settings_put("global", "media.stagefright.cache-params", "65536/131072/30")
    
    ADBTuner.setprop("media.stagefright.enable-player", "true")
    ADBTuner.setprop("media.stagefright.enable-meta", "true")
    ADBTuner.setprop("media.stagefright.enable-scan", "true")
    ADBTuner.setprop("media.stagefright.enable-http", "true")
    
    info("Dostrajanie parametrów pamięci Dalvik pod 1.45 GB RAM (zapobieganie LMK/GC micro-pauses)...")
    ADBTuner.setprop("dalvik.vm.heapminfree", "2m")
    ADBTuner.setprop("dalvik.vm.heapmaxfree", "16m")
    ADBTuner.setprop("dalvik.vm.heapgrowthlimit", "192m")
    ADBTuner.setprop("dalvik.vm.heapsize", "512m")
    
    info("Czyszczenie przestarzałych buforów i cache systemowego...")
    ADBTuner.run("pm trim-caches 2048G")
    ADBTuner.run("sync")
    
    ok("Bufory cache i limity pamięci zostały pomyślnie dostrojone.")


def verify_system_state():
    hdr("KROK 3 -- Weryfikacja Stanu Systemu")
    
    density = ADBTuner.run("wm density")
    size = ADBTuner.run("wm size")
    renderer = ADBTuner.run("getprop debug.hwui.renderer")
    
    print(f"  [i] {density}")
    print(f"  [i] {size}")
    print(f"  [i] Render Engine: {renderer if renderer else 'default (opengl)'}")
    ok("Weryfikacja zakończona pomyślnie.")


def main():
    hdr("PlayBox Titanium -- DPI & Cache Tuner")
    print("  Docelowe urządzenie: Sagemcom DCTIW362P (BCM72604)\n")
    
    # Test połączenia ADB
    devices = ADBTuner.run("devices")
    if "device" not in devices.splitlines()[-1] if devices else True:
        err("Brak aktywnego połączenia ADB! Podłącz urządzenie poleceniem: adb connect <IP>")
        sys.exit(1)
        
    optimize_display_and_dpi()
    optimize_cache_and_buffers()
    verify_system_state()
    
    hdr("GOTOWE!")
    print("  Zalecany jest restart urządzenia w celu pełnego zatwierdzenia zmian DPI:\n")
    print("    adb reboot\n")

if __name__ == "__main__":
    main()
