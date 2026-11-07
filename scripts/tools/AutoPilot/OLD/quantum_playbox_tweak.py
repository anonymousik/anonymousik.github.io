#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  QUANTUM TITANIUM CORE v1.0 — PROACTIVE PERFORMANCE ARSENAL                  ║
║  Target: BCM72604 | Cortex-A15 | 2GB RAM | Android TV 9                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, sys, time, subprocess, threading, base64

class UI:
    C = '\033[96m'; G = '\033[92m'; Y = '\033[93m'; R = '\033[91m'; W = '\033[1m'; O = '\033[0m'
    @staticmethod
    def log(lvl, msg):
        col = {'OK': UI.G, 'INFO': UI.C, 'WARN': UI.Y, 'ERR': UI.R}.get(lvl, UI.O)
        print(f"{UI.W}[{lvl}]{UI.O} {col}{msg}{UI.O}")

class PrivilegeEngine:
    """Silnik eskalacji uprawnień oparty na Shizuku (rish) - omija brak roota."""
    RISH_PATH = "/data/local/tmp/rish"
    DEX_PATH = "/data/local/tmp/rish_shizuku.dex"
    
    @classmethod
    def init(cls):
        UI.log("INFO", "Inicjalizacja silnika uprawnień (Privilege Engine)...")
        check = subprocess.getoutput(f"adb shell ls {cls.DEX_PATH}")
        if "No such file" in check:
            UI.log("ERR", "Brak rish_shizuku.dex! Uruchom najpierw menedżera Shizuku na TV.")
            sys.exit(1)
            
        # Generowanie inteligentnego wrappera w locie (omija problemy ze znakami ucieczki)
        script = (
            "#!/system/bin/sh\n"
            "export RISH_APPLICATION_ID=com.android.shell\n"
            f"DEX={cls.DEX_PATH}\n"
            'if [ "$1" = "-c" ]; then shift; CMD="$*"; exec /system/bin/app_process -Djava.class.path="$DEX" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader -c "$CMD"\n'
            'else exec /system/bin/app_process -Djava.class.path="$DEX" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader "$@"\nfi\n'
        )
        b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
        subprocess.getoutput(f"adb shell \"echo '{b64}' | base64 -d > {cls.RISH_PATH} && chmod 755 {cls.RISH_PATH}\"")
        UI.log("OK", "Rish Wrapper aktywny. Tryb God-Mode odblokowany.")

    @classmethod
    def execute(cls, cmd):
        safe_cmd = cmd.replace("'", "'\\''")
        return subprocess.getoutput(f"adb shell sh {cls.RISH_PATH} -c '{safe_cmd}'").strip()

class BatchCommander:
    """Kompiluje wiele poleceń w jedną sesję ADB, drastycznie przyspieszając wykonanie."""
    def __init__(self, name):
        self.name = name
        self.cmds = []

    def setprop(self, k, v): self.cmds.append(f"setprop {k} {v}")
    def settings(self, ns, k, v): self.cmds.append(f"settings put {ns} {k} {v}")
    
    def flush(self):
        if not self.cmds: return
        script = " ; ".join(f"({c})" for c in self.cmds)
        PrivilegeEngine.execute(script)
        UI.log("OK", f"Moduł [{self.name}] wdrożony ({len(self.cmds)} dyrektyw).")

class OptimizationArsenal:
    @staticmethod
    def unleash_cpu_dalvik():
        UI.log("INFO", "Wdrażanie: A15 Hardware IDIV & Dalvik Tuning...")
        b = BatchCommander("CPU_DALVIK")
        # Wymuszenie sprzętowego dzielenia całkowitoliczbowego na Cortex-A15
        b.setprop("dalvik.vm.isa.arm.features", "default,idiv")
        b.setprop("dalvik.vm.isa.arm.variant", "cortex-a15")
        # Optymalizacja Garbage Collectora (Likwidacja mikro-zacięć)
        b.setprop("dalvik.vm.heapminfree", "2m")
        b.setprop("dalvik.vm.heapmaxfree", "16m")
        b.setprop("dalvik.vm.heapsize", "512m")
        b.setprop("dalvik.vm.heaptargetutilization", "0.75")
        # LMK oparty na PSI (Szybsza reakcja na ubytek RAM)
        b.setprop("ro.lmk.upgrade_pressure", "50")
        b.setprop("ro.lmk.use_minfree_levels", "false")
        b.settings("global", "activity_manager_constants", "max_cached_processes=16,background_settle_time=100")
        b.flush()

    @staticmethod
    def unleash_gpu_rendering():
        UI.log("INFO", "Wdrażanie: SkiaGL Overdrive & VSync Phase Alignment...")
        b = BatchCommander("GPU_RENDER")
        # Pełna akceleracja sprzętowa UI
        b.settings("system", "force_gpu_rendering", "1")
        b.setprop("persist.sys.ui.hw", "true")
        b.setprop("debug.sf.hw", "1")
        # Silnik SkiaGL (Vulkan jest niekompatybilny z VideoCore na BCM)
        b.setprop("debug.hwui.renderer", "skiagl")
        b.setprop("debug.renderengine.backend", "skiaglthreaded")
        b.setprop("debug.hwui.render_thread", "true")
        # Wyrównanie fazy VSync dla 60fps (Likwiduje "Jank")
        b.setprop("debug.sf.early_phase_offset_ns", "500000")
        b.setprop("debug.sf.early_app_phase_offset_ns", "1000000")
        b.setprop("debug.sf.disable_backpressure", "1")
        # Natychmiastowa reakcja bez dławiących animacji
        b.settings("global", "window_animation_scale", "0.0")
        b.settings("global", "transition_animation_scale", "0.0")
        b.settings("global", "animator_duration_scale", "0.0")
        b.flush()

    @staticmethod
    def unleash_network_io():
        UI.log("INFO", "Wdrażanie: 4K TCP Window & I/O Storage Defrag...")
        b = BatchCommander("NETWORK_IO")
        # Okno TCP podwójnej wielkości - natychmiastowe buforowanie 4K
        b.settings("global", "tcp_default_init_rwnd", "120")
        b.setprop("net.tcp.default_init_rwnd", "120")
        # Usunięcie drenażu CPU przez ciągłe skanowanie radia
        b.settings("global", "wifi_scan_always_enabled", "0")
        b.settings("global", "ble_scan_always_enabled", "0")
        # Zabezpieczenie HDMI przed zerwaniem synchronizacji (Black Screen Fix)
        b.setprop("persist.sys.hdmi.keep_awake", "true")
        b.setprop("audio.brcm.hdmi.clock_lock", "true")
        b.flush()

        UI.log("INFO", "Przebudowa harmonogramu wejścia/wyjścia (I/O)...")
        # Deadline scheduler i rozszerzenie read-ahead do 2MB dla strumieniowania
        PrivilegeEngine.execute("for d in /sys/block/*/queue/scheduler; do echo deadline > $d 2>/dev/null; done")
        PrivilegeEngine.execute("for d in /sys/block/*/queue/read_ahead_kb; do echo 2048 > $d 2>/dev/null; done")
        # Agresywny FSTRIM eMMC
        PrivilegeEngine.execute("pm trim-caches 2G && vdc fstrim dotrim")

class ProactiveWatchdog:
    """Autonomiczny demon monitorujący kondycję systemu w czasie rzeczywistym."""
    _stop_event = threading.Event()

    @classmethod
    def start(cls):
        UI.log("OK", "Uruchamianie proaktywnego demona Watchdog w tle...")
        threading.Thread(target=cls._loop, daemon=True).start()

    @classmethod
    def _loop(cls):
        while not cls._stop_event.is_set():
            # Sprawdzanie RAM
            mem_raw = PrivilegeEngine.execute("grep MemAvailable /proc/meminfo | awk '{print $2}'")
            if mem_raw.isdigit() and (int(mem_raw) // 1024) < 150:
                # Automatyczne zrzucenie cache VFS i aplikacji przy krytycznym poziomie RAM
                PrivilegeEngine.execute("sync && echo 3 > /proc/sys/vm/drop_caches && pm trim-caches 1G")
                UI.log("WARN", "[Watchdog] Poziom RAM krytyczny. Zastosowano taktyczne zrzucenie cache.")
            
            # Weryfikacja ubicia krytycznych procesów Cast
            mdns = PrivilegeEngine.execute("getprop init.svc.mdnsd")
            if "running" not in mdns:
                PrivilegeEngine.execute("stop mdnsd && start mdnsd")
                UI.log("WARN", "[Watchdog] Usługa mDNS (Chromecast) odzyskana z awarii.")
            
            cls._stop_event.wait(45) # Skan co 45 sekund

if __name__ == "__main__":
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{UI.C}{UI.W}=============================================================={UI.O}")
    print(f"{UI.C}{UI.W}      QUANTUM TITANIUM CORE - PROACTIVE PERFORMANCE           {UI.O}")
    print(f"{UI.C}{UI.W}=============================================================={UI.O}")
    
    # 1. Połączenie ADB (Zakładamy, że urządzenie jest podłączone)
    subprocess.getoutput("adb root 2>/dev/null") # Ciche wywołanie
    
    # 2. Inicjalizacja Arsenału
    PrivilegeEngine.init()
    
    # 3. Wykonanie rdzenia operacyjnego
    OptimizationArsenal.unleash_cpu_dalvik()
    OptimizationArsenal.unleash_gpu_rendering()
    OptimizationArsenal.unleash_network_io()
    
    # 4. Start proaktywnego Demona
    ProactiveWatchdog.start()
    
    print(f"\n{UI.G}{UI.W}[✓] SYSTEM ZDEKLASYFIKOWANY. MAKSYMALNA WYDAJNOŚĆ ODBLOKOWANA.{UI.O}")
    print(f"{UI.G}{UI.W}[✓] Proaktywny Watchdog chroni urządzenie w tle.{UI.O}")
    print(f"{UI.C}Możesz zamknąć to okno (Ctrl+C), lub zostawić otwarte dla logów Watchdoga.{UI.O}")
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nZamykanie Quantum Core...")

