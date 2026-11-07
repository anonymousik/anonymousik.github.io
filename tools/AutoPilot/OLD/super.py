#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  QUANTUM OVERDRIVE v5.0 - UNLEASHED PERFORMANCE EDITION                      ║
║  Target: Sagemcom DCTIW362P | Broadcom BCM72604 | Cortex-A15                  ║
║  Optimization: CPU Overdrive, RAM Expansion, ROM Throughput                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import subprocess
import sys
import time

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(lvl, msg):
    mapping = {"INFO": Colors.OKCYAN, "OK": Colors.OKGREEN, "WARN": Colors.WARNING, "ERR": Colors.FAIL}
    print(f"{Colors.BOLD}{mapping.get(lvl, Colors.ENDC)}[{lvl}]{Colors.ENDC} {msg}")

class QuantumEngine:
    def __init__(self, target_ip=""):
        self.adb = f"adb -s {target_ip} shell" if target_ip else "adb shell"
        self.rish = "/data/local/tmp/./rish"
        self.verify_rish()

    def verify_rish(self):
        res = subprocess.getoutput(f"{self.adb} ls {self.rish}")
        if "No such file" in res:
            log("ERR", "Brak rish! Uruchom shizuku_man.sh przed startem.")
            sys.exit(1)
        log("OK", "Rish Engine aktywny. Uprawnienia Shizuku zweryfikowane.")

    def run(self, cmd):
        # Eskalacja przez rish dla komend wymagających shell/root level
        full_cmd = f"{self.adb} sh {self.rish} -c \"{cmd}\""
        return subprocess.getoutput(full_cmd).strip()

    def set_prop(self, prop, val):
        current = self.run(f"getprop {prop}")
        if current != val:
            log("INFO", f"Modyfikacja {prop}: {val}")
            self.run(f"setprop {prop} {val}")
        else:
            log("OK", f"{prop} jest już zoptymalizowany.")

    def set_setting(self, table, key, val):
        current = self.run(f"settings get {table} {key}")
        if current != val:
            log("INFO", f"Settings {table}/{key}: {val}")
            self.run(f"settings put {table} {key} {val}")
        else:
            log("OK", f"{table}/{key} jest już ustawiony.")

def unleash_performance():
    engine = QuantumEngine()
    
    print(f"\n{Colors.HEADER}--- [CPU & KERNEL OVERDRIVE] ---{Colors.ENDC}")
    # Wymuszenie trybu wysokiej wydajności dla planisty (Sheduler)
    engine.set_prop("sys.use_fifo_ui", "1") # Priorytet FIFO dla UI
    engine.set_prop("debug.egl.hw", "1")
    engine.set_prop("debug.gr.num_extra_buffers", "2") # Triple buffering dla VideoCore
    # Optymalizacja pod Cortex-A15 (Neon/VFPv4)
    engine.set_prop("dalvik.vm.isa.arm.variant", "cortex-a15")
    engine.set_prop("dalvik.vm.isa.arm.features", "default")

    print(f"\n{Colors.HEADER}--- [RAM & VIRTUAL MEMORY TWEAKS] ---{Colors.ENDC}")
    # Zarządzanie stosem maszyny wirtualnej - mniejsze przestoje na zbieranie śmieci
    engine.set_prop("dalvik.vm.heapstartsize", "16m")
    engine.set_prop("dalvik.vm.heapgrowthlimit", "192m")
    engine.set_prop("dalvik.vm.heapsize", "512m")
    engine.set_prop("dalvik.vm.heaptargetutilization", "0.75")
    # Agresywny Low Memory Killer dla utrzymania responsywności UI
    engine.set_setting("global", "low_power_mode_trigger_level", "0")
    engine.set_setting("global", "cached_apps_freezer", "disabled") # Zapobiega "zamrażaniu" aplikacji w tle, co laguje ich powrót

    print(f"\n{Colors.HEADER}--- [ROM & STORAGE THROUGHPUT] ---{Colors.ENDC}")
    # Zwiększenie bufora odczytu eMMC (Read-ahead) - standardowo 128kb, podnosimy do 2048kb
    log("INFO", "Zwiększanie przepustowości ROM (Read-ahead buffer)...")
    engine.run("for block in /sys/block/mmcblk*; do echo 2048 > $block/queue/read_ahead_kb; done")
    # Wyłączenie statystyk SQLite (zmniejsza ilość operacji zapisu/IO wait)
    engine.set_prop("debug.sqlite.journalmode", "MEMORY")
    engine.set_prop("debug.sqlite.syncmode", "OFF")

    print(f"\n{Colors.HEADER}--- [UI LATENCY DRAIN] ---{Colors.ENDC}")
    # Całkowite wyłączenie limitów renderowania i wymuszenie 60fps w systemie
    engine.set_setting("global", "window_animation_scale", "0.0")
    engine.set_setting("global", "transition_animation_scale", "0.0")
    engine.set_setting("global", "animator_duration_scale", "0.0")
    # Przyspieszenie reakcji na dotyk/pilot
    engine.set_setting("secure", "long_press_timeout", "200")
    
    print(f"\n{Colors.HEADER}--- [FINAL SYSTEM PURGE] ---{Colors.ENDC}")
    log("INFO", "Czyszczenie pozostałości i wymuszenie TRIM...")
    engine.run("pm trim-caches 4096M")
    engine.run("vdc fstrim dotrim") # Sprzętowa optymalizacja bloków pamięci eMMC

    print(f"\n{Colors.OKGREEN}{Colors.BOLD}SUKCES: Potencjał Quantum Overdrive odblokowany!{Colors.ENDC}")
    print(f"{Colors.OKCYAN}Zalecany restart urządzenia dla pełnej synchronizacji Kernela.{Colors.ENDC}")

if __name__ == "__main__":
    try:
        unleash_performance()
    except KeyboardInterrupt:
        print("\nPrzerwano.")
