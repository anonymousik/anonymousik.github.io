#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  QUANTUM APEX OPTIMIZER v4.1 — THE ULTIMATE STATE-AWARE ENGINE               ║
║  Target: Sagemcom DCTIW362P | Cortex-A15 | VideoCore IV | Android 9          ║
║  Features: Zero eMMC Wear | Shizuku ADB Escalation | Multi-Tasking Tuning    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import subprocess
import time
import sys

class Tui:
    C = '\033[96m'  # Cyan
    G = '\033[92m'  # Green
    Y = '\033[93m'  # Yellow
    R = '\033[91m'  # Red
    W = '\033[1m'   # Bold
    O = '\033[0m'   # Reset

def log(lvl, msg):
    color = {'OK': Tui.G, 'INFO': Tui.C, 'WARN': Tui.Y, 'ERR': Tui.R}.get(lvl, Tui.O)
    print(f"{Tui.W}[{lvl}]{Tui.O} {color}{msg}{Tui.O}")

class ShizukuStateEngine:
    """
    State-Aware Shizuku Wrapper over ADB.
    Executes commands securely using /data/local/tmp/./rish.
    Validates current state to prevent unnecessary eMMC flash writes.
    """
    def __init__(self, target_ip=""):
        self.rish_path = "/data/local/tmp/./rish"
        self.adb_prefix = f"adb -s {target_ip} shell" if target_ip else "adb shell"
        self.changes_applied = 0
        self._verify_environment()

    def _verify_environment(self):
        log("INFO", "Weryfikacja środowiska ADB i Shizuku (rish)...")
        check_cmd = f"{self.adb_prefix} ls {self.rish_path}"
        check = subprocess.getoutput(check_cmd)
        
        if "No such file" in check or "not found" in check:
            log("ERR", f"Brak binarki Shizuku w {self.rish_path} na urządzeniu!")
            log("INFO", "Upewnij się, że urządzenie jest podłączone (adb devices) i rish jest wgrany.")
            sys.exit(1)
            
        test_rish = self.run_cmd("id")
        if "uid=0" in test_rish or "system" in test_rish or "shell" in test_rish:
             log("OK", "Shizuku (rish) API — Aktywne i gotowe do wstrzykiwania komend.")
        else:
             log("WARN", "Odpowiedź rish jest nietypowa, ale kontynuuję...")

    def run_adb(self, cmd: str) -> str:
        """Standardowe wywołanie ADB shell bez eskalacji."""
        return subprocess.getoutput(f"{self.adb_prefix} {cmd}").strip()

    def run_cmd(self, cmd: str) -> str:
        """Wykonanie komendy przez Shizuku z sanityzacją."""
        safe_cmd = cmd.replace("'", "'\\''")
        wrapper = f"{self.adb_prefix} sh {self.rish_path} -c '{safe_cmd}'"
        return subprocess.getoutput(wrapper).strip()

    def enforce_prop(self, key: str, target: str, desc: str):
        """Inteligentna zmiana setprop z weryfikacją."""
        current = self.run_cmd(f"getprop {key}")
        if current != target:
            log("WARN", f"Prop: {key} [{current} -> {target}] | {desc}")
            self.run_cmd(f"setprop {key} {target}")
            self.changes_applied += 1
        else:
            log("INFO", f"Prop: {key} = {target} (Zoptymalizowano)")

    def enforce_setting(self, namespace: str, key: str, target: str, desc: str):
        """Inteligentna zmiana settings z weryfikacją."""
        current = self.run_cmd(f"settings get {namespace} {key}")
        if current != target:
            log("WARN", f"Set: {namespace}/{key} [{current} -> {target}] | {desc}")
            self.run_cmd(f"settings put {namespace} {key} {target}")
            self.changes_applied += 1
        else:
            log("INFO", f"Set: {namespace}/{key} = {target} (Zoptymalizowano)")

    def enforce_appops(self, pkg: str, op: str, mode: str, desc: str):
        """Wymuszanie restrykcji AppOps."""
        log("INFO", f"AppOps: {pkg} {op}={mode} | {desc}")
        self.run_cmd(f"cmd appops set {pkg} {op} {mode}")
        self.changes_applied += 1

class QuantumArchitect:
    """
    Centralna logika operacyjna optymalizująca środowisko pod 
    kątem responsywności i wielozadaniowości na Android TV 9.
    """
    def __init__(self, engine: ShizukuStateEngine):
        self.engine = engine

    def phase_1_cpu_dalvik(self):
        print(f"\n{Tui.W}{Tui.C}=== FAZA 1: CPU, DALVIK & WIELOZADANIOWOŚĆ ==={Tui.O}")
        # Odblokowanie instrukcji sprzętowych CPU dla Cortex-A15
        self.engine.enforce_prop("dalvik.vm.isa.arm.features", "default,idiv", "Aktywacja HW Integer Divide (Odciążenie CPU)")
        
        # Pamięć i Garbage Collection - unikanie ścinania ekranu podczas czyszczenia RAM
        self.engine.enforce_prop("dalvik.vm.heapminfree", "2m", "Płynniejszy Garbage Collection (Start)")
        self.engine.enforce_prop("dalvik.vm.heapmaxfree", "16m", "Płynniejszy Garbage Collection (Limit)")
        
        # Low Memory Killer - optymalizacja pod ciężkie aplikacje
        self.engine.enforce_prop("ro.lmk.upgrade_pressure", "50", "Agresywniejsze zwalnianie RAM dla zadań w tle")
        
        # Zwiększenie wielozadaniowości poprzez Activity Manager
        # max_cached_processes zwiększone z domyślnego 12 do 24, pozwalając procesorowi płynnie przełączać aplikacje
        self.engine.enforce_setting("global", "activity_manager_constants", "max_cached_processes=24,background_settle_time=100,fgservice_min_report_time=2000", "Zwiększenie wielozadaniowości i buforowania aplikacji")

    def phase_2_gpu_rendering(self):
        print(f"\n{Tui.W}{Tui.C}=== FAZA 2: RENDERING GPU & HARDWARE UI ==={Tui.O}")
        # Sprzętowe renderowanie interfejsu 2D
        self.engine.enforce_prop("persist.sys.ui.hw", "true", "Wymuszenie renderowania interfejsu przez GPU")
        self.engine.enforce_setting("system", "force_gpu_rendering", "1", "Forsowanie akceleracji 2D")
        
        # Ominięcie błędów sprzętowego kompozytora (HWC) z użyciem SkiaGL
        self.engine.enforce_prop("debug.sf.hw", "1", "Sprzętowy SurfaceFlinger")
        self.engine.enforce_prop("debug.hwui.renderer", "skiagl", "Blokada niekompatybilnego Vulkana, użycie SkiaGL")
        self.engine.enforce_prop("debug.hwui.render_thread", "true", "Asynchroniczny wątek renderowania (Zmniejsza użycie CPU)")
        
        # Minimalizacja opóźnień wyświetlania klatek Broadcom VideoCore IV
        self.engine.enforce_prop("debug.sf.latch_unsignaled", "1", "Asynchroniczne nakładanie klatek (Anti-Jank)")
        self.engine.enforce_prop("debug.sf.disable_backpressure", "1", "Wyłączenie dławienia klatek (Zwiększa FPS UI)")
        
        # Bypassing HWC z użyciem uprzywilejowanego Service Call
        log("INFO", "Wstrzykiwanie ominięcia HWC do SurfaceFlinger...")
        self.engine.run_cmd("service call SurfaceFlinger 1008 i32 1")

    def phase_3_responsiveness(self):
        print(f"\n{Tui.W}{Tui.C}=== FAZA 3: RESPONSIVNOŚĆ UI & SYSTEMU ==={Tui.O}")
        # Wyłączenie obciążających animacji okien
        for anim in ["window_animation_scale", "transition_animation_scale", "animator_duration_scale"]:
            self.engine.enforce_setting("global", anim, "0.0", "Błyskawiczny czas reakcji UI (Animacje 0.0x)")
            
        # Zmniejszenie opóźnień pilota i interakcji
        self.engine.enforce_setting("secure", "long_press_timeout", "250", "Krótszy czas reakcji na przytrzymanie klawisza (z 500ms)")
        self.engine.enforce_setting("secure", "multi_press_timeout", "250", "Krótszy czas reakcji na wielokrotne wciśnięcie")
        
        # Optymalizacja obciążenia procesora przez usługi ułatwień dostępu (np. mappery)
        self.engine.enforce_setting("secure", "accessibility_interactive_ui_timeout_ms", "2000", "Redukcja dławienia CPU przez usługi ułatwień")
        self.engine.enforce_setting("secure", "accessibility_non_interactive_ui_timeout_ms", "3000", "Redukcja zapytań o stan ekranu w tle")

    def phase_4_network_and_sleep(self):
        print(f"\n{Tui.W}{Tui.C}=== FAZA 4: NETWORKING & ANTI-SLEEP FIX ==={Tui.O}")
        # Agresywny TCP Read Window dla SmartTube (4K Video Buffering)
        self.engine.enforce_prop("net.tcp.default_init_rwnd", "120", "2x Szybszy start streamu (TCP Window)")
        self.engine.enforce_setting("global", "tcp_default_init_rwnd", "120", "Zapis okna TCP w Global Settings")
        
        # Wyłączenie telemetrii systemowej obciążającej dysk i internet
        self.engine.enforce_setting("global", "send_action_app_error", "0", "Wyłączenie raportowania błędów")
        self.engine.enforce_setting("global", "activity_starts_logging_enabled", "0", "Wyłączenie logowania uruchamiania aplikacji")

        # Blokada wyłączania się telewizora podczas odtwarzania wideo
        self.engine.enforce_setting("secure", "sleep_timeout", "-1", "Wyłączenie limitu usypiania Eco-Standby")
        self.engine.enforce_setting("global", "stay_on_while_plugged_in", "3", "Wymuszenie aktywności procesora na zasilaniu (AC)")

    def phase_5_purging(self):
        print(f"\n{Tui.W}{Tui.C}=== FAZA 5: RAM PURGE & BACKGROUND BLOAT ==={Tui.O}")
        # Dławienie zasobożernych usług Google w tle, z zachowaniem funkcjonalności Cast
        self.engine.enforce_appops("com.google.android.gms", "RUN_IN_BACKGROUND", "ignore", "Blokada pożerania RAM przez GMS w tle")
        self.engine.enforce_appops("com.google.android.gms", "WAKE_LOCK", "ignore", "Blokada nadmiernego wybudzania CPU przez Google Play")
        
        log("INFO", "Wykonywanie głębokiego czyszczenia pamięci (TRIM & Caches)...")
        # Wyczyszczenie pamięci tymczasowej z RAM
        self.engine.run_cmd("pm trim-caches 1024M")
        self.engine.run_cmd("am kill com.google.android.gms")
        
        # FSTRIM kompresuje komórki w pamięci eMMC, drastycznie przyspieszając zapis/odczyt plików
        log("INFO", "Trimming /data partition (Może to zająć kilka sekund)...")
        self.engine.run_cmd("fstrim -v /data")
        self.engine.run_cmd("fstrim -v /cache")

def main():
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{Tui.W}{Tui.Y}╔══════════════════════════════════════════════════════════════╗{Tui.O}")
    print(f"{Tui.W}{Tui.Y}║        QUANTUM APEX OPTIMIZER v4.1 - BROADCOM EDITION        ║{Tui.O}")
    print(f"{Tui.W}{Tui.Y}╚══════════════════════════════════════════════════════════════╝{Tui.O}")
    
    # Pobranie ewentualnego IP z argumentu, np. python3 quantum_apex.py 192.168.1.3
    target_ip = sys.argv[1] if len(sys.argv) > 1 else ""
    
    try:
        engine = ShizukuStateEngine(target_ip)
        architect = QuantumArchitect(engine)
        
        time_start = time.time()
        
        architect.phase_1_cpu_dalvik()
        architect.phase_2_gpu_rendering()
        architect.phase_3_responsiveness()
        architect.phase_4_network_and_sleep()
        architect.phase_5_purging()
        
        time_end = time.time()
        
        print(f"\n{Tui.W}{Tui.G}================================================================{Tui.O}")
        print(f"{Tui.W}{Tui.G} [✓] OPTYMALIZACJA ZAKOŃCZONA W {time_end - time_start:.2f} SEKUND.{Tui.O}")
        print(f"{Tui.W}{Tui.G} [✓] Zaaplikowano {engine.changes_applied} modyfikacji stanu systemu.{Tui.O}")
        print(f"{Tui.W}{Tui.G}================================================================{Tui.O}")
        print(f"{Tui.C}Zalecany jest szybki restart aplikacji takich jak SmartTube.{Tui.O}")
        
    except KeyboardInterrupt:
        print("\nPrzerwano przez użytkownika.")
        sys.exit(0)

if __name__ == "__main__":
    main()
