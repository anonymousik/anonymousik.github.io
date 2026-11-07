#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM — ATV9 Deep Optimizer v1.2 ULTIMATE EDITION               ║
║  Target  : Android TV 9 (API 28) · BCM72604 / Amlogic S905X · Cortex-A15  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Moduły:                                                                     ║
║    ATV9DisplayOptimizer  — Color Engine, EOTF ST2084, HDMI BT.2020 override ║
║    ATV9GPUOptimizer      — Skia backend, VSync phase offsets, SF tweaks     ║
║    ATV9ARTOptimizer      — AOT speed compile, heap, GC, dex2oat             ║
║    ATV9LMKOptimizer      — LMKD PSI, max_cached_processes, OOM adj          ║
║    ATV9PowerOptimizer    — Fixed-performance, CPU governor, thermal          ║
║    ATV9NetworkOptimizer  — WiFi stability, TCP bufors, Stagefright           ║
║    ATV9InputOptimizer    — VSync offsets, input latency, tap thresholds      ║
║    ATV9Debloater         — pm disable-user, telemetry, GMS partial           ║
║    ATV9BackgroundDaemon  — Autonomiczny skrypt no-drop w tle (anti-disconnect)║
║    ATV9PersistEngine     — zapis tweaków do skryptów przeżywających reboot   ║
║    ATV9HealthCheck       — diagnostyka po optymalizacji                      ║
║    ATV9MasterOptimizer   — pełna orkiestracja wszystkich modułów             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import re
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Titanium Faza 1 imports ───────────────────────────────────────────────────
from titanium_phase1 import (
    ADB, ADBGuard, ADBResult, BatchCommander, BACKUP_DIR,
    C, DRY_RUN, HW, L, OptimLevel, RepairSector, SessionJournal,
)

# ══════════════════════════════════════════════════════════════════════════════
# STAŁE ATV9
# ══════════════════════════════════════════════════════════════════════════════

PERSIST_SCRIPT_REMOTE = "/data/local/tmp/titanium_persist.sh"
PERSIST_INITD_REMOTE  = "/system/etc/init.d/99titanium"
PERSIST_MAGISK_REMOTE = "/data/adb/service.d/titanium_persist.sh"

PERSIST_HEADER = """#!/system/bin/sh
# PlayBox Titanium v15.8 — Persist Script
# Wygenerowany: {ts}
# Przeżywa reboot: init.d / Magisk service.d
# ─────────────────────────────────────────
TITANIUM_LOG=/data/local/tmp/titanium_persist.log
echo "[$(date)] Titanium persist start" >> $TITANIUM_LOG
"""

class GPUBackend(str, Enum):
    SKIAGL         = "skiagl"          
    SKIAGLTHREADED = "skiaglthreaded"  
    SKIAVK         = "skiavk"          
    OPENGL         = "opengl"          

CRITICAL_SYSTEM_PKGS: set[str] = {
    "com.android.systemui",
    "com.android.settings",
    "com.android.providers.settings",
    "com.android.providers.media",
    "com.android.shell",
    "android",
}

# ══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DeviceProfile:
    soc:           str   = ""
    gpu_model:     str   = ""
    has_vulkan:    bool  = False
    has_mali:      bool  = False
    has_vc4:       bool  = False
    ram_mb:        int   = 0
    cpu_cores:     int   = 2
    cpu_max_mhz:   int   = 0
    android_api:   int   = 28
    is_amlogic:    bool  = False
    is_bcm:        bool  = False
    has_init_d:    bool  = False    
    has_magisk:    bool  = False    
    has_su:        bool  = False    

    @property
    def optimal_gpu_backend(self) -> GPUBackend:
        if self.has_vulkan and self.has_mali: return GPUBackend.SKIAVK
        if self.has_vc4 or self.is_bcm:       return GPUBackend.OPENGL # Zmiana wymuszona przez logi: opengl jest tu najlepszy
        return GPUBackend.SKIAGL

    @property
    def recommended_heap_growth(self) -> str:
        if self.ram_mb >= 3000: return "384m"
        if self.ram_mb >= 1800: return "192m" # Zmiana dla Playbox
        return "128m"

    @property
    def recommended_heap_size(self) -> str:
        if self.ram_mb >= 3000: return "768m"
        if self.ram_mb >= 1800: return "512m"
        return "256m"

    @property
    def recommended_max_cached(self) -> int:
        if self.ram_mb >= 3000: return 64
        if self.ram_mb >= 1800: return 16 # Podbite do 16
        return 12

    @property
    def persist_method(self) -> str:
        if self.has_magisk:  return "magisk"
        if self.has_init_d:  return "initd"
        if self.has_su:      return "su_script"
        return "props_only"   


@dataclass
class OptimResult:
    module:      str
    success:     bool
    applied:     int   = 0
    failed:      int   = 0
    elapsed_s:   float = 0.0
    persist_ok:  bool  = False
    notes:       List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        s = f"{C.OK if self.success else C.WARN}[{self.module:<22}]{C.RST}"
        s += f"  {self.applied}/{self.applied+self.failed} OK"
        s += f"  ({self.elapsed_s:.1f}s)"
        if self.persist_ok: s += f"  {C.OK if hasattr(C,'OK') else ''}[persist✓]{C.RST}"
        return s


# ══════════════════════════════════════════════════════════════════════════════
# PERSIST ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class ATV9PersistEngine:
    def __init__(self, guard: ADBGuard, journal: SessionJournal, profile: DeviceProfile) -> None:
        self._guard   = guard
        self._journal = journal
        self._profile = profile
        self._cmds:   List[str] = []

    def queue(self, cmd: str, description: str = "") -> None:
        self._cmds.append(cmd)
        if description: self._cmds.insert(-1, f"# {description}")

    def commit(self) -> bool:
        if not self._cmds: return True
        method = self._profile.persist_method
        L.info(f"PersistEngine: commit {len(self._cmds)} komend → [{method}]")

        script = PERSIST_HEADER.format(ts=datetime.now().isoformat())
        script += "\n".join(self._cmds) + "\n"
        script += '\necho "[$(date)] Titanium persist done" >> $TITANIUM_LOG\n'

        return {
            "magisk":     self._write_magisk,
            "initd":      self._write_initd,
            "su_script":  self._write_su_script,
            "props_only": self._write_local_prop,
        }.get(method, self._write_local_prop)(script)

    def _write_magisk(self, script: str) -> bool:
        return self._push_and_chmod(script, PERSIST_MAGISK_REMOTE, "755")

    def _write_initd(self, script: str) -> bool:
        self._guard.sh("mount -o remount,rw /system 2>/dev/null || true")
        ok = self._push_and_chmod(script, PERSIST_INITD_REMOTE, "755")
        self._guard.sh("mount -o remount,ro /system 2>/dev/null || true")
        return ok

    def _write_su_script(self, script: str) -> bool:
        ok = self._push_and_chmod(script, PERSIST_SCRIPT_REMOTE, "755")
        if ok: L.info("Persist: Wymaga Termux:Boot ~/.termux/boot/")
        return ok

    def _write_local_prop(self, script: str) -> bool:
        props = []
        for line in self._cmds:
            m = re.match(r"setprop\s+(\S+)\s+(.+)", line.strip())
            if m: props.append(f"{m.group(1)}={m.group(2)}")

        if not props: return False
        content = "\n".join(props) + "\n"
        existing = self._guard.sh("cat /data/local.prop 2>/dev/null").output
        new_content = existing + "\n# Titanium ATV9\n" + content
        tmp = "/sdcard/titanium_local_prop.tmp"
        ADB.push(str(self._create_local_tmp(new_content)), tmp)
        self._guard.sh(f"cp {tmp} /data/local.prop && rm {tmp}")
        L.ok("local.prop zaktualizowany (właściwości persist.* przeżyją reboot)")
        return True

    def _push_and_chmod(self, content: str, remote: str, mode: str) -> bool:
        import base64
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        cmd = f"echo '{b64}' | base64 -d > {remote} && chmod {mode} {remote}"
        r = self._guard.sh(cmd, timeout=15)
        return True if (r.ok or DRY_RUN) else False

    def _create_local_tmp(self, content: str) -> Path:
        import tempfile
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".prop", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        return Path(f.name)


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY OPTIMIZER — Color Engine, EOTF, HDMI Output Quality (NOWY MODUŁ)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9DisplayOptimizer:
    """
    Zaawansowany silnik zarządzania obrazem. Wymusza poprawne przekazywanie
    metadanych HDR (ST2084/BT.2020) przez złącze HDMI do telewizora, naprawiając
    braki w fabrycznym oprogramowaniu BCM72604/Playbox.
    Wspiera natywne UI sRGB i osobne wideo HDR10 (Hardware Composer Layer).
    """

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, profile: DeviceProfile) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9DisplayOptimizer — HDMI · Color Engine · EOTF ST2084")
        applied = failed = 0

        # ── 1. Wymuszenie HDMI Output Mode (Fix dla oceny 0/25 HDMI) ─────
        hdmi_props: List[Tuple[str,str,str]] = [
            ("persist.sys.hdmi.hdr_mode", "auto", "HDMI HDR Mode: auto (przełączanie sygnału)"),
            ("persist.sys.hdmi.color_space", "bt2020", "HDMI Color Space: Wymuszenie BT.2020"),
            ("persist.sys.hdmi.eotf", "smpte2084", "HDMI EOTF: ST2084 (Krzywa PQ dla HDR10)"),
            ("persist.sys.hdmi.hdr_metadata", "1", "HDMI Metadata: Transmisja MaxCLL/MaxFALL"),
            ("persist.sys.display.hdr", "true", "Display HDR: Włączony globalnie"),
            ("ro.vendor.hdr.enable", "true", "Vendor HDR enable (Broadcom)"),
        ]

        for prop, val, desc in hdmi_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else:
                failed += 1

        # ── 2. Poprawa zarządzania kolorem (EOTF Pipeline Fix) ───────────
        color_props: List[Tuple[str,str,str]] = [
            ("ro.surface_flinger.use_color_management", "true", "SF: Color Management (poprawne SDR)"),
            ("ro.surface_flinger.has_wide_color_display", "true", "SF: Wyświetlacz WCG (Wide Color Gamut)"),
            ("ro.surface_flinger.has_HDR_display", "true", "SF: Zgłoszenie wyświetlacza HDR"),
            ("persist.sys.sf.color_saturation", "1.0", "SF: Normalizacja saturacji UI"),
        ]

        for prop, val, desc in color_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else:
                failed += 1

        # ── 3. Ustawienia Settings API dla Display ───────────────────────
        settings_cmds: List[Tuple[str,str,str,str]] = [
            ("system", "display_color_mode", "0", "System Color Mode: 0 (Natywne sRGB dla UI)"),
            ("secure", "ui_night_mode", "1", "Wymuszenie ciemnego motywu UI (redukuje banding)"),
            ("global", "sys_uidcpupower", "1", "Global UID CPU Power (stabilność klatek)"),
        ]
        
        for ns, key, val, desc in settings_cmds:
            r = guard.sh(f"settings put {ns} {key} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} {val}", desc)
            else:
                failed += 1

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9DisplayOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# GPU OPTIMIZER — Skia, VSync, SurfaceFlinger (FULL ORIGINAL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9GPUOptimizer:
    VSYNC_PHASE_SF_60HZ   = 2_000_000    
    VSYNC_PHASE_APP_60HZ  = 4_000_000    
    VSYNC_PHASE_SF_50HZ   = 4_000_000    
    VSYNC_PHASE_EARLY     = 1_000_000    

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, profile: DeviceProfile, level: OptimLevel) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9GPUOptimizer — Skia · VSync · SurfaceFlinger")
        applied = failed = 0

        backend = profile.optimal_gpu_backend
        L.info(f"GPU: {profile.gpu_model}  Backend: {backend.value}")

        # ── Blok 1: Skia renderer props + Playbox fixes ───────────────────
        renderer_props: List[Tuple[str,str,str]] = [
            ("debug.hwui.renderer", backend.value, f"Skia renderer: {backend.value}"),
            ("debug.renderengine.backend", backend.value + "threaded" if "gl" in backend.value else backend.value, "RenderEngine backend"),
            ("debug.hwui.disable_vulkan", "0" if profile.has_vulkan else "1", f"Vulkan: {'enabled' if profile.has_vulkan else 'disabled'}"),
            ("debug.hwui.use_buffer_age", "true", "Buffer age: reuse stale regions → mniej overdraw"),
            ("debug.force_opengl", "1", "Force GPU composition (disable SW fallback)"),
            ("debug.force_msaa", "0", "Wyłączenie MSAA (oszczędność GPU)"),
            ("debug.hwui.use_hint_manager", "1", "HWUI: Optymalizacja wątków CPU dla GPU"),
        ]

        for prop, val, desc in renderer_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
                journal.record(RepairSector.GPU_PIPELINE, "ATV9GPUOptimizer", desc, f"setprop {prop} {val}", f"setprop {prop} ''")
            else:
                failed += 1; L.warn(f"setprop {prop}: FAIL")

        # Fallbacks dla persist.sys.ui.hw
        guard.sh("setprop debug.sys.ui.hw true")
        persist.queue("setprop debug.sys.ui.hw true", "Fallback UI HW accel")
        
        r = guard.sh("setprop persist.sys.ui.hw true")
        if r.ok:
            applied += 1; persist.queue("setprop persist.sys.ui.hw true", "UI HW acceleration: forced")

        # ── Blok 2: VSync Phase Offsets (Pełna oryginalna logika) ─────────
        sf_hz = 50 if profile.is_bcm else 60
        sf_off  = cls.VSYNC_PHASE_SF_50HZ  if sf_hz == 50 else cls.VSYNC_PHASE_SF_60HZ
        app_off = cls.VSYNC_PHASE_APP_60HZ

        vsync_props: List[Tuple[str,str,str]] = [
            ("debug.sf.early_phase_offset_ns", str(sf_off), f"SF VSync phase offset: {sf_off//1_000_000}ms @ {sf_hz}Hz"),
            ("debug.sf.early_app_phase_offset_ns", str(app_off), f"App VSync phase offset: {app_off//1_000_000}ms"),
            ("debug.sf.high_fps_early_phase_offset_ns", str(cls.VSYNC_PHASE_EARLY), f"High-FPS early phase: {cls.VSYNC_PHASE_EARLY//1_000_000}ms"),
            ("debug.sf.high_fps_early_gl_phase_offset_ns", str(cls.VSYNC_PHASE_EARLY), "High-FPS GL early phase offset"),
        ]

        for prop, val, desc in vsync_props:
            if guard.sh(f"setprop {prop} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else: failed += 1

        # ── Blok 3: SurfaceFlinger settings ───────────────────────────────
        sf_settings: List[Tuple[str,str,str,str]] = [
            ("global", "surface_flinger_enable_layer_caching", "true", "SF: layer cache → mniej full redraws"),
            ("global", "sf_frame_rate_override", "0", "SF: disable frame rate override"),
        ]
        for ns, key, val, desc in sf_settings:
            if guard.sh(f"settings put {ns} {key} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} {val}", desc)
            else: failed += 1

        # ── Blok 4: SurfaceFlinger setprop tweaki ─────────────────────────
        sf_props: List[Tuple[str,str,str]] = [
            ("debug.sf.latch_unsignaled", "1", "SF latch_unsignaled: pobierz bufory bez fence wait (-1 klatka)"),
            ("debug.sf.disable_backpressure", "1", "SF: brak back-pressure → płynniejszy pipeline"),
            ("debug.sf.enable_gl_backpressure", "0", "SF GL back-pressure: wyłączona"),
            ("debug.sf.reuse_refresh_rate_configs", "1", "SF: reuse refresh rate config"),
            ("debug.sf.enable.hwc.vds", "1", "SF: Virtual Displays przez HWC (HDR support)"),
        ]
        for prop, val, desc in sf_props:
            if guard.sh(f"setprop {prop} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else: failed += 1

        # ── AGGRESSIVE: Wyłącz HW overlays (wymusza GPU compositing) ─────
        if level in (OptimLevel.AGGRESSIVE, OptimLevel.TURBO):
            r = guard.sh("service call SurfaceFlinger 1008 i32 1 2>/dev/null || true")
            L.ok("SF: wymuś GPU compositing (disable HW overlays)")
            persist.queue("service call SurfaceFlinger 1008 i32 1 2>/dev/null || true", "SF: GPU-forced composition")
            applied += 1

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9GPUOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# ART OPTIMIZER — AOT, heap, dex2oat, GC (FULL ORIGINAL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9ARTOptimizer:
    PRIORITY_PACKAGES: List[str] = [
        "org..smarttube.stable", "com.castify.tv", "com.spocky.projengmenu",
        "com.android.systemui", "com.google.android.tvlaunche",
    ]

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, profile: DeviceProfile, level: OptimLevel) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9ARTOptimizer — AOT · Heap · GC · dex2oat")
        applied = failed = 0

        # Wymuszenie agresywnego trim-caches na początku (Rozwiązanie braku miejsca na Playbox)
        guard.sh("pm trim-caches 999G 2>/dev/null")
        guard.sh("rm -rf /data/local/tmp/* 2>/dev/null")
        guard.sh("pm clear com.android.providers.downloads 2>/dev/null")
        L.ok("Wyczyszczono potężne cache systemowe i resztki plików (Fix No space left on device)")
        applied += 1

        # ── Heap tuning ────────────────────────
        heap_props: List[Tuple[str,str,str]] = [
            ("dalvik.vm.heapstartsize", "16m", "Heap start: 16MB"),
            ("dalvik.vm.heapminfree", "2m", "Heap min free: 2MB"),
            ("dalvik.vm.heapmaxfree", "16m", "Heap max free: 16MB"),
            ("dalvik.vm.heapgrowthlimit", profile.recommended_heap_growth, f"Heap growth limit: {profile.recommended_heap_growth}"),
            ("dalvik.vm.heapsize", profile.recommended_heap_size, f"Heap max: {profile.recommended_heap_size}"),
            ("dalvik.vm.heaptargetutilization", "0.5", "Heap utilization: 0.5 (krótkie cykle GC)"),
            ("dalvik.vm.dex2oat-threads", str(min(profile.cpu_cores, 4)), f"dex2oat threads: {min(profile.cpu_cores,4)}"),
            ("dalvik.vm.dex2oat-Xmx", "512m", "dex2oat max heap: 512MB"),
            ("dalvik.vm.image-dex2oat-filter", "speed", "System image: AOT speed filter"),
            ("dalvik.vm.dex2oat-filter", "speed", "App dex2oat: speed filter"),
            ("dalvik.vm.isa.arm.features", "default,idiv", "ARM ISA: hardware SDIV/UDIV"),
        ]

        for prop, val, desc in heap_props:
            if guard.sh(f"setprop {prop} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
                journal.record(RepairSector.DALVIK_RUNTIME, "ATV9ARTOptimizer", desc, f"setprop {prop} {val}")
            else: failed += 1

        # ── AOT Speed Compile ──────────────────────
        L.section("AOT: kompilacja priorytetowych pakietów")
        for pkg in cls.PRIORITY_PACKAGES:
            chk = guard.sh(f"pm list packages {pkg} 2>/dev/null").output
            if f"package:{pkg}" not in chk: continue
            L.info(f"AOT speed compile: {pkg}...")
            r = guard.sh(f"cmd package compile -m speed -f {pkg} 2>/dev/null", timeout=120)
            if r.ok or DRY_RUN:
                applied += 1; L.ok(f"AOT: {pkg} skompilowany")
            else: failed += 1

        if level == OptimLevel.TURBO:
            L.info("TURBO: AOT speed compile ALL packages...")
            r = guard.sh("cmd package compile -m speed -f -a 2>/dev/null", timeout=600)
            if r.ok or DRY_RUN:
                applied += 1; L.ok("AOT: pełna kompilacja wszystkich pakietów")
            else: failed += 1

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9ARTOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# LMK OPTIMIZER — OOM, cached processes (FULL ORIGINAL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9LMKOptimizer:
    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, profile: DeviceProfile, level: OptimLevel) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9LMKOptimizer — LMKD PSI · OOM · Cached Processes")
        applied = failed = 0

        max_cached = profile.recommended_max_cached

        # ── Activity Manager constants ────────────────────────────────────
        am_constants = (
            f"max_cached_processes={max_cached},"
            f"background_settle_time=100,"
            f"fgservice_min_shown_time=1000,"
            f"fgservice_min_report_time=2000,"
            f"fgservice_screen_on_before_time=0,"
            f"min_crash_interval=200,"
            f"process_start_async=true"
        )
        r = guard.sh(f"settings put global activity_manager_constants '{am_constants}'")
        if r.ok or DRY_RUN:
            applied += 1
            L.ok(f"AM: max_cached={max_cached} + async start + crash interval")
            persist.queue(f"settings put global activity_manager_constants '{am_constants}'", "Activity Manager constants")

        # Rozwiązanie Playbox (Phantom Processes)
        guard.sh(f"settings put global activity_manager_max_phantom_processes {max_cached}")
        guard.sh(f"settings put global background_process_limit {max_cached}")
        guard.sh("settings put global settings_enable_monitor_phantom_procs disable")
        guard.sh("setprop config.max_starting_bg 8")
        guard.sh("setprop debug.max_starting_bg 8")

        # ── LMKD properties ───────────────────────────────────────────────
        lmk_props: List[Tuple[str,str,str]] = [
            ("ro.lmk.filecache_min_kb", str(90 * 1024), "LMK: filecache min 90MB"),
            ("ro.lmk.use_minfree_levels", "false", "LMK: PSI-based (sysfs minfree ignorowane)"),
            ("ro.lmk.low", "1024", "LMK: low pressure threshold"),
            ("ro.lmk.medium", "512", "LMK: medium pressure threshold"),
            ("ro.lmk.critical", "0", "LMK: critical threshold"),
            ("ro.lmk.critical_upgrade", "true", "LMK: enable critical upgrade"),
            ("ro.lmk.upgrade_pressure", "80", "LMK: upgrade pressure 80%"),
            ("ro.lmk.downgrade_pressure", "60", "LMK: downgrade pressure 60%"),
            ("ro.lmk.kill_heaviest_task", "true", "LMK: zabij najcięższy proces"),
            ("ro.lmk.kill_timeout_ms", "100", "LMK: timeout zabijania 100ms"),
        ]
        for prop, val, desc in lmk_props:
            if guard.sh(f"setprop {prop} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else: failed += 1

        # ── PSI thresholds (wymaga root/rish) ─────────────────────────────
        psi_cmds: List[Tuple[str,str]] = [
            ("echo '70 200' > /proc/pressure/memory 2>/dev/null || true", "PSI memory: stall threshold 70ms/200ms"),
            ("echo '200 1000' > /proc/pressure/cpu 2>/dev/null || true", "PSI CPU: stall threshold 200ms/1s"),
        ]
        for cmd, desc in psi_cmds:
            if guard.sh(cmd).ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(cmd, desc)

        # ── OOM ADJ ochrona dekodera video ───────────────────────────────
        if level in (OptimLevel.AGGRESSIVE, OptimLevel.TURBO):
            st_pid = guard.sh("pidof is.xyz.smarttube 2>/dev/null | awk '{print $1}'").output.strip()
            if st_pid.isdigit():
                guard.sh(f"echo -800 > /proc/{st_pid}/oom_score_adj 2>/dev/null || true")
                L.ok(f"OOM adj: SmartTube PID {st_pid} → -800 (chroniony)")
                applied += 1
                persist.queue(
                    "pid=$(pidof is.xyz.smarttube 2>/dev/null | awk '{print $1}'); "
                    "[ -n \"$pid\" ] && echo -800 > /proc/$pid/oom_score_adj 2>/dev/null || true",
                    "OOM ADJ: SmartTube protected"
                )

        if profile.is_bcm or (profile.cpu_max_mhz > 0 and profile.cpu_max_mhz <= 1500):
            if guard.sh("settings put global zram_enabled 0").ok or DRY_RUN:
                applied += 1; L.ok("ZRAM: wyłączony (BCM CPU zbyt wolny)")
                persist.queue("settings put global zram_enabled 0", "ZRAM disabled")

        if profile.ram_mb >= 1800:
            if guard.sh("setprop ro.config.low_ram false").ok or DRY_RUN:
                applied += 1; L.ok("low_ram=false: pełne możliwości Android UI odblokowane")
                persist.queue("setprop ro.config.low_ram false", "low_ram=false")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9LMKOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# POWER OPTIMIZER — CPU, Thermal (FULL ORIGINAL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9PowerOptimizer:
    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, profile: DeviceProfile, level: OptimLevel) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9PowerOptimizer — Fixed Perf · CPU Gov · Thermal")
        applied = failed = 0

        r = guard.sh("cmd power set-fixed-performance-mode-enabled true 2>/dev/null || true")
        if r.ok or DRY_RUN:
            applied += 1; L.ok("Fixed Performance Mode: AKTYWNY (blokada CPU/GPU)")
            persist.queue("cmd power set-fixed-performance-mode-enabled true 2>/dev/null || true", "Fixed Performance Mode")

        guard.sh("settings put global sem_enhanced_cpu_responsiveness 1")
        persist.queue("settings put global sem_enhanced_cpu_responsiveness 1")
        
        guard.sh("settings put global hardware_acceleration_optimization_enabled 1")
        guard.sh("settings put global high_priority_render_thread 1")
        persist.queue("settings put global hardware_acceleration_optimization_enabled 1")
        persist.queue("settings put global high_priority_render_thread 1")

        guard.sh("cmd deviceidle disable 2>/dev/null || true")
        persist.queue("cmd deviceidle disable 2>/dev/null || true", "Disable Doze mode")

        # ── CPU Governor tuning (Oryginalna pętla po rdzeniach) ─────────────
        blk_dev = guard.sh("ls /sys/devices/system/cpu/cpu0/cpufreq/ 2>/dev/null | head -1").output
        if blk_dev:
            cpu_count = profile.cpu_cores
            gov_cmds: List[Tuple[str,str]] = []

            if level == OptimLevel.TURBO:
                for i in range(cpu_count):
                    gov_cmds.append((f"echo performance > /sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor 2>/dev/null || true", f"CPU{i}: governor=performance"))
            else:
                for i in range(cpu_count):
                    gov_cmds.append((f"echo schedutil > /sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor 2>/dev/null || true", f"CPU{i}: governor=schedutil"))
                    gov_cmds.append((f"echo 500 > /sys/devices/system/cpu/cpu{i}/cpufreq/schedutil/rate_limit_us 2>/dev/null || true", f"CPU{i}: schedutil rate_limit=500µs"))

            if profile.cpu_max_mhz > 0:
                max_khz = profile.cpu_max_mhz * 1000
                for i in range(cpu_count):
                    gov_cmds.append((f"echo {max_khz} > /sys/devices/system/cpu/cpu{i}/cpufreq/scaling_max_freq 2>/dev/null || true", f"CPU{i}: max_freq={profile.cpu_max_mhz}MHz"))

            for cmd, desc in gov_cmds:
                if guard.sh(cmd).ok or DRY_RUN:
                    applied += 1; L.ok(desc)
                    persist.queue(cmd, desc)
                else: failed += 1

        guard.sh("setprop persist.sys.powermode 1")
        persist.queue("setprop persist.sys.powermode 1", "PowerMode: HIGH")
        
        guard.sh("settings put system multicore_packet_scheduler 1")
        persist.queue("settings put system multicore_packet_scheduler 1")
        applied += 1

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9PowerOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# NETWORK OPTIMIZER — WiFi, Stagefright, TCP (FULL ORIGINAL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9NetworkOptimizer:
    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, profile: DeviceProfile) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9NetworkOptimizer — WiFi · TCP · Stagefright")
        applied = failed = 0

        # ── WiFi settings ─────────────────────────────────────────────────
        wifi_settings: List[Tuple[str,str,str,str]] = [
            ("global", "wifi_scan_always_enabled", "0", "WiFi: scan_always disabled"),
            ("global", "wifi_power_save", "0", "WiFi: power save OFF"),
            ("global", "wifi_sleep_policy", "2", "WiFi: never sleep"),
            ("global", "wifi_aggressive_handover_enabled", "0", "WiFi: aggressive handover OFF"),
            ("global", "wifi_enhanced_auto_join", "0", "WiFi: enhanced auto-join OFF"),
            ("global", "wifi_country_code", "", "WiFi: country code reset"),
        ]
        for ns, key, val, desc in wifi_settings:
            if guard.sh(f"settings put {ns} {key} '{val}'").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} '{val}'", desc)
                journal.record(RepairSector.NETWORK_TCP, "ATV9NetworkOptimizer", desc, f"settings put {ns} {key} {val}")
            else: failed += 1

        # ── TCP kernel params (Aktualizacja z 4K Playbox Settings) ────────
        tcp_params: List[Tuple[str,str,str]] = [
            ("net.tcp.buffersize.default", "4096,87380,704512,4096,16384,110208", "TCP Buf Default Playbox"),
            ("net.tcp.buffersize.wifi", "524288,1048576,2097152,262144,524288,1048576", "TCP Buf WiFi Playbox"),
        ]
        for prop, val, desc in tcp_params:
            if guard.sh(f"setprop {prop} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else: failed += 1

        tcp_kernel: List[Tuple[str,str,str]] = [
            ("net/ipv4/tcp_congestion_control", "cubic", "TCP: CUBIC congestion control"),
            ("net/ipv4/tcp_fastopen", "3", "TCP Fast Open: client+server"),
            ("net/ipv4/tcp_sack", "1", "TCP SACK: aktywny"),
            ("net/ipv4/tcp_ecn", "1", "TCP ECN: aktywny"),
            ("net/ipv4/tcp_slow_start_after_idle", "0", "TCP: brak slow-start po idle"),
            ("net/ipv4/tcp_notsent_lowat", "131072", "TCP notsent_lowat: 128KB"),
            ("net/core/rmem_max", "4194304", "Socket Rx max: 4MB"),
            ("net/core/wmem_max", "4194304", "Socket Tx max: 4MB"),
            ("net/core/netdev_max_backlog", "5000", "Net backlog: 5000 pakietów"),
        ]
        for path, val, desc in tcp_kernel:
            cmd = f"echo '{val}' > /proc/sys/{path} 2>/dev/null || true"
            if guard.sh(cmd).ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(cmd, desc)

        # ── DNS Cloudflare + DoT ──────────────────────────────────────────
        dns_cmds: List[Tuple[str,str]] = [
            ("ndc resolver setnetdns 100 '' 1.1.1.1 1.0.0.1 2>/dev/null || true", "DNS: Cloudflare 1.1.1.1"),
            ("setprop net.dns1 1.1.1.1", "DNS1: Cloudflare"),
            ("setprop net.dns2 1.0.0.1", "DNS2: Cloudflare fallback"),
            ("settings put global private_dns_mode hostname", "DoT: tryb hostname"),
            ("settings put global private_dns_specifier one.one.one.one", "DoT: one.one.one.one"),
            ("settings put global dns_resolver_max_samples 1", "Optymalizacja DNS resolvera Playbox"),
        ]
        for cmd, desc in dns_cmds:
            if guard.sh(cmd).ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(cmd, desc)

        # ── Stagefright buffers ─────────────────────────────
        sf_props: List[Tuple[str,str,str]] = [
            ("media.stagefright.thumbnail.timeout", "10000", "Stagefright: thumbnail timeout 10s"),
            ("media.stagefright.prefer-container-mime-type", "1", "Stagefright: prefer container MIME type"),
            ("debug.stagefright.ccodec", "4", "Stagefright: Codec2 priority 4"),
        ]
        for prop, val, desc in sf_props:
            if guard.sh(f"setprop {prop} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)

        guard.sh("settings put global captive_portal_https_url https://connectivitycheck.gstatic.com/generate_204")
        persist.queue("settings put global captive_portal_https_url https://connectivitycheck.gstatic.com/generate_204")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9NetworkOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# INPUT OPTIMIZER — Latencja wejścia, VSync, timeouty (FULL ORIGINAL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9InputOptimizer:
    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, level: OptimLevel) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9InputOptimizer — Input Latency · Timeouty · Animacje")
        applied = failed = 0

        anim_scale = "0.0" if level == OptimLevel.TURBO else "0.2"

        input_settings: List[Tuple[str,str,str,str]] = [
            ("secure", "long_press_timeout", "300", "Long press timeout: 300ms"),
            ("secure", "multi_press_timeout", "250", "Multi press timeout: 250ms"),
            ("secure", "tap_duration_threshold", "0.0", "Tap duration: 0.0"),
            ("secure", "touch_blocking_period", "0.0", "Touch blocking: 0.0"),
            ("secure", "cursor_speed", "0", "Cursor speed: 0"),
            ("global", "sysui_latency_reboot_count", "0", "SysUI latency counter: reset"),
            ("global", "window_animation_scale", anim_scale, f"Animacje okien: {anim_scale}x"),
            ("global", "transition_animation_scale", "0.25", f"Animacje przejść: 0.25x"),
            ("global", "animator_duration_scale", anim_scale, f"Animator: {anim_scale}x"),
        ]
        for ns, key, val, desc in input_settings:
            if guard.sh(f"settings put {ns} {key} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} {val}", desc)
                journal.record(RepairSector.HWUI_RENDERER, "ATV9InputOptimizer", desc, f"settings put {ns} {key} {val}")
            else: failed += 1

        inp_pid = guard.sh("pidof inputflinger 2>/dev/null | awk '{print $1}'").output.strip()
        if inp_pid.isdigit():
            guard.sh(f"echo -1 > /proc/{inp_pid}/oom_adj 2>/dev/null || true")
            L.ok(f"InputFlinger PID {inp_pid}: oom_adj=-1 (nietykalny)")
            applied += 1
            persist.queue(
                "pid=$(pidof inputflinger 2>/dev/null | awk '{print $1}'); "
                "[ -n \"$pid\" ] && echo -1 > /proc/$pid/oom_adj 2>/dev/null || true",
                "InputFlinger: oom_adj=-1"
            )

        if level == OptimLevel.TURBO:
            if guard.sh("settings put system sound_effects_enabled 0").ok or DRY_RUN:
                applied += 1; L.ok("Dźwięki UI: wyłączone")
                persist.queue("settings put system sound_effects_enabled 0")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9InputOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# DEBLOATER — pm disable-user, telemetria (FULL ORIGINAL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9Debloater:
    PACKAGES: List[Tuple[str, OptimLevel, str, str]] = [
        ("com.google.android.feedback",          OptimLevel.SAFE, "Google Feedback", "telemetria"),
        ("com.google.android.partnersetup",      OptimLevel.SAFE, "Partner Setup", "telemetria"),
        ("com.android.statementservice",         OptimLevel.SAFE, "Statement Service", "telemetria"),
        ("com.android.traceur",                  OptimLevel.SAFE, "System Trace", "telemetria"),
        ("com.google.android.onetimeinitializer",OptimLevel.SAFE, "One Time Initializer", "telemetria"),
        ("com.google.android.tvrecommendations", OptimLevel.STANDARD, "TV Recommendations", "launcher"),
        ("com.google.android.tungsten.setupwraith", OptimLevel.STANDARD, "Setup Wizard", "setup"),
        ("com.google.android.backdrop",          OptimLevel.STANDARD, "Backdrop", "ambient"),
        ("com.google.android.tvlauncheranimations", OptimLevel.STANDARD, "Launcher Animations", "launcher"),
        ("com.google.android.katniss",           OptimLevel.AGGRESSIVE, "Google Assistant ATV", "assistant"),
        ("com.google.android.speech",            OptimLevel.AGGRESSIVE, "Google Speech", "assistant"),
        ("com.google.mainline.phone.providers.sms", OptimLevel.AGGRESSIVE, "SMS Provider", "gms"),
        ("com.google.android.syncadapters.contacts", OptimLevel.AGGRESSIVE, "Contacts Sync", "gms"),
        ("com.android.providers.contacts",       OptimLevel.AGGRESSIVE, "Contacts Provider", "system"),
        ("fusion.android.tv.demo",               OptimLevel.TURBO, "OEM Demo", "oem"),
        ("com.tcl.ocean.instructions",           OptimLevel.TURBO, "TCL instrukcje", "oem"),
        ("com.android.providers.usagestats",     OptimLevel.TURBO, "Usage Stats Provider", "telemetria"),
    ]

    TELEMETRY_SETTINGS: List[Tuple[str,str,str,str]] = [
        ("system",  "send_security_reports",         "0", "Security reports: off"),
        ("secure",  "send_action_app_error",         "0", "App error reports: off"),
        ("global",  "activity_starts_logging_enabled","0", "Activity starts log: off"),
        ("global",  "send_action_app_error",         "0", "Global app error: off"),
        ("global",  "usage_stats_report_interval",   "0", "Usage stats report: off"),
        ("global",  "auto_time_zone",                "0", "Auto timezone: off"),
        ("secure",  "limit_ad_tracking",             "1", "Ad tracking: limited"),
        ("global",  "android_id_migration_enabled",  "0", "Android ID migration: off"),
        ("global",  "damage_app_usage_log_enabled",  "0", "Damage app usage log: off"),
        ("global",  "dropbox_max_files",             "0", "Dropbox max files: 0"),
        ("secure",  "voice_interaction_service",   '""', "Voice interaction: off"),
        ("secure",  "assist_structure_enabled",      "0", "Assist structure: off"),
        ("secure",  "assist_screenshot_enabled",     "0", "Assist screenshot: off"),
    ]

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, level: OptimLevel = OptimLevel.STANDARD) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9Debloater — pm disable-user · Telemetria")
        applied = failed = 0
        disabled: List[str] = []

        level_order = [OptimLevel.SAFE, OptimLevel.STANDARD, OptimLevel.AGGRESSIVE, OptimLevel.TURBO]
        level_idx   = level_order.index(level)

        L.section("Dezaktywacja pakietów ATV9")
        for pkg, min_lvl, desc, cat in cls.PACKAGES:
            if level_order.index(min_lvl) > level_idx: continue
            if pkg in CRITICAL_SYSTEM_PKGS: continue
            chk = guard.sh(f"pm list packages {pkg} 2>/dev/null").output
            if f"package:{pkg}" not in chk: continue

            r = guard.sh(f"pm disable-user --user 0 {pkg} 2>/dev/null || pm disable {pkg} 2>/dev/null || true")
            if r.ok or DRY_RUN:
                applied += 1; disabled.append(pkg)
                L.ok(f"[{cat}] Wyłączono: {pkg}  ({desc})")
                journal.record(RepairSector.PRIVACY_GUARD, "ATV9Debloater", f"disable {pkg}", f"pm disable-user {pkg}", f"pm enable {pkg}")
            else: failed += 1

        L.section("Blokada telemetrii i analityki")
        for ns, key, val, desc in cls.TELEMETRY_SETTINGS:
            if guard.sh(f"settings put {ns} {key} {val}").ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} {val}", desc)
            else: failed += 1

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9Debloater", applied > 0, applied, failed, elapsed, notes=[f"Wyłączone pakiety: {', '.join(disabled[:5])}..."])


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND DAEMON — Skrypt no-drop w tle (anti-disconnect) (NOWY MODUŁ)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9BackgroundDaemon:
    """
    Instaluje i uruchamia autonomicznego demona na urządzeniu docelowym.
    Działa całkowicie w tle bez udziału hosta (uniezależnia od przerw w ADB).
    Realizuje cykliczne tweaki (zwalnianie RAM, wymuszanie profilu wydajności).
    Rozwiązuje problem przerywanego połączenia ADB.
    """
    DAEMON_PATH = "/data/local/tmp/titanium_daemon.sh"

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal, persist: ATV9PersistEngine) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9BackgroundDaemon — Autonomiczny demon w tle")
        applied = failed = 0

        script_content = """#!/system/bin/sh
# PlayBox Titanium - Background Daemon (No-Drop ADB Independent)
while true; do
    echo 1 > /proc/sys/vm/drop_caches 2>/dev/null
    cmd power set-fixed-performance-mode-enabled true 2>/dev/null
    sync
    pm trim-caches 16G 2>/dev/null
    logcat -G 1M 2>/dev/null
    sleep 900
done
"""
        import base64
        b64 = base64.b64encode(script_content.encode("utf-8")).decode("ascii")
        cmd = (
            f"echo '{b64}' | base64 -d > {cls.DAEMON_PATH} && "
            f"chmod 755 {cls.DAEMON_PATH} && "
            f"nohup {cls.DAEMON_PATH} >/dev/null 2>&1 &"
        )
        
        guard.sh("kill -9 $(pgrep -f titanium_daemon) 2>/dev/null || true")
        r = guard.sh(cmd)
        if r.ok or DRY_RUN:
            applied += 1
            L.ok("Daemon w tle: zainstalowany i aktywny (nohup)")
            persist.queue(
                f"kill -9 $(pgrep -f titanium_daemon) 2>/dev/null || true\n"
                f"nohup {cls.DAEMON_PATH} >/dev/null 2>&1 &",
                "Start autonomicznego demona Titanium"
            )
            journal.record(RepairSector.DALVIK_RUNTIME, "ATV9BackgroundDaemon", "Daemon instalacja", cmd)
        else:
            failed += 1; L.warn("Daemon w tle: błąd uruchamiania")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9BackgroundDaemon", applied > 0, applied, failed, elapsed, notes=["Działa autonomicznie"])



# ══════════════════════════════════════════════════════════════════════════════
# CAST & PERMISSIONS OPTIMIZER — Chromecast, Projectivy, Foreground Priority
# ══════════════════════════════════════════════════════════════════════════════

class ATV9CastAndPermsOptimizer:
    """
    Moduł rozwiązujący problemy z Castowaniem (przeglądarka -> Android TV),
    nadający krytyczne uprawnienia dla Projectivy Launcher (modyfikacja kolorów)
    oraz wyłączający mechanizmy oszczędzania baterii usypiające procesy w tle.
    """
    
    # Lista aplikacji, które muszą być bezwzględnie odporne na ubijanie
    CAST_PACKAGES = [
        "com.android.chromecast",
        "com.google.android.apps.mediashell", # Prawdziwy odbiornik cast w ATV
        "com.castify.tv"
    ]
    
    PROJECTIVY_PKG = "com.spocky.projengmenu"

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, level: OptimLevel) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9CastAndPermsOptimizer — Cast Fix · Permissions · Standby")
        applied = failed = 0

        # ── 1. Globalne wyłączenie zarządzania energią (TV = Stałe Zasilanie) ──
        energy_settings = [
            ("global", "app_standby_enabled", "0", "Wyłączenie App Standby (Utrzymuje apki w RAM)"),
            ("global", "adaptive_battery_management_enabled", "0", "Wyłączenie Adaptive Battery"),
            ("global", "low_power", "0", "Wymuszenie trybu wysokiej wydajności CPU"),
        ]
        
        for ns, key, val, desc in energy_settings:
            r = guard.sh(f"settings put {ns} {key} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} {val}", desc)
            else:
                failed += 1

        # ── 2. Optymalizacja procesów RAM/CPU dla zadań pierwszoplanowych ──
        sys_props = [
            ("sys.sysctl.extra_free_kbytes", "24300", "Zabezpieczenie przed fragmentacją RAM"),
            ("persist.sys.purgeable_assets", "1", "Agresywne zwalnianie zasobów ukrytych"),
        ]
        for prop, val, desc in sys_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)

        # ── 3. Zabezpieczenie apek do Castowania (DIAL / mDNS V2) ──
        for pkg in cls.CAST_PACKAGES:
            # Sprawdź czy pakiet istnieje
            if pkg not in guard.sh("pm list packages").output:
                continue
                
            # Dodanie do białej listy Doze Mode (wymagane dla nasłuchiwania w tle)
            cmd_whitelist = f"dumpsys deviceidle whitelist +{pkg} 2>/dev/null"
            if guard.sh(cmd_whitelist).ok or DRY_RUN:
                applied += 1
                persist.queue(cmd_whitelist)
            
            # Wymuszenie koszyka "active" (najwyższy priorytet I/O i CPU)
            cmd_bucket = f"am set-standby-bucket {pkg} active 2>/dev/null"
            guard.sh(cmd_bucket)
            persist.queue(cmd_bucket)

            # Uprawnienia do rysowania okna na wierzchu (żeby odtwarzacz wystartował)
            cmd_overlay = f"appops set {pkg} SYSTEM_ALERT_WINDOW allow 2>/dev/null"
            if guard.sh(cmd_overlay).ok:
                applied += 1
                L.ok(f"Cast Fix nałożony dla: {pkg}")

        # ── 4. Projectivy Launcher - Pełne Uprawnienia ──
        if cls.PROJECTIVY_PKG in guard.sh("pm list packages").output:
            proj_cmds = [
                (f"pm grant {cls.PROJECTIVY_PKG} android.permission.WRITE_SECURE_SETTINGS 2>/dev/null", 
                 "Projectivy: WRITE_SECURE_SETTINGS (Wymagane do profili kolorów HDR/SDR)"),
                (f"appops set {cls.PROJECTIVY_PKG} SYSTEM_ALERT_WINDOW allow 2>/dev/null", 
                 "Projectivy: Rysowanie po ekranie"),
                (f"appops set {cls.PROJECTIVY_PKG} GET_USAGE_STATS allow 2>/dev/null", 
                 "Projectivy: Dostęp do statystyk użycia"),
                (f"dumpsys deviceidle whitelist +{cls.PROJECTIVY_PKG} 2>/dev/null", 
                 "Projectivy: Wykluczenie z usypiania"),
            ]
            
            for cmd, desc in proj_cmds:
                r = guard.sh(cmd)
                if r.ok or DRY_RUN:
                    applied += 1; L.ok(desc)
                    persist.queue(cmd, desc)
                else:
                    failed += 1
                    L.warn(f"Projectivy Perm: {cmd}")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9CastAndPermsOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# IO STORAGE OPTIMIZER — I/O Scheduler, read_ahead, eMMC tuning (PATCH v1.2)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9IOStorageOptimizer:
    """
    Optymalizacja pamięci masowej eMMC/NAND.
    Zmienia zarządcę I/O na 'deadline' (lub 'noop'), co eliminuje opóźnienia
    w odczycie blokowym. Zwiększa read_ahead_kb do 2048KB (optymalne dla 4K video).
    Wyłącza iostats, aby odciążyć CPU.
    """
    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, level: OptimLevel) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9IOStorageOptimizer — I/O Scheduler · eMMC Tuning")
        applied = failed = 0

        # Wyszukiwanie urządzeń blokowych
        blk_devs_raw = guard.sh("ls /sys/block/ | grep -v loop | grep -v ram").output.strip()
        blk_devs = [d for d in blk_devs_raw.split() if d]

        if not blk_devs:
            L.warn("IO: Nie znaleziono fizycznych urządzeń blokowych.")
            return OptimResult("ATV9IOStorageOptimizer", False, 0, 1, time.monotonic() - t0)

        for dev in blk_devs:
            cmds = [
                # Scheduler: deadline sprawdza się najlepiej dla eMMC w Androidzie
                (f"echo deadline > /sys/block/{dev}/queue/scheduler 2>/dev/null || echo noop > /sys/block/{dev}/queue/scheduler", 
                 f"IO [{dev}]: scheduler → deadline/noop"),
                
                # Zwiększenie bufora odczytu z wyprzedzeniem (redukuje czasy ładowania aplikacji)
                (f"echo 2048 > /sys/block/{dev}/queue/read_ahead_kb 2>/dev/null", 
                 f"IO [{dev}]: read_ahead_kb → 2048"),
                
                # Wyłączenie statystyk I/O (zmniejsza obciążenie procesora)
                (f"echo 0 > /sys/block/{dev}/queue/iostats 2>/dev/null", 
                 f"IO [{dev}]: iostats → 0 (OFF)"),
                
                # Parametry dla deadline schedulera (jeśli aktywny)
                (f"echo 1 > /sys/block/{dev}/queue/iosched/fifo_batch 2>/dev/null", None),
                (f"echo 250 > /sys/block/{dev}/queue/iosched/read_expire 2>/dev/null", None),
                (f"echo 2500 > /sys/block/{dev}/queue/iosched/write_expire 2>/dev/null", None),
            ]

            for cmd, desc in cmds:
                r = guard.sh(cmd)
                if r.ok or DRY_RUN:
                    applied += 1
                    if desc:
                        L.ok(desc)
                        persist.queue(cmd, desc)
                else:
                    if desc:
                        failed += 1
                        L.warn(f"IO błąd dla {dev}: {cmd}")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9IOStorageOptimizer", applied > 0, applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# PROJECTIVY IMAGE MANAGER FIXER — Naprawa błędu "Nie załadowano menadżera obrazu"
# ══════════════════════════════════════════════════════════════════════════════

class ATV9ProjectivyFixer:
    """
    Naprawia błąd 'Nie załadowano menadżera obrazu' w Projectivy Launcher.
    Wymusza nadanie uprawnień systemowych, aktywuje Accessibility Service
    oraz ustawia flagi Secure Settings wymagane do filtrów kolorów.
    """
    PKG = "com.spocky.projengmenu"
    ACCESSIBILITY_SERVICE = "com.spocky.projengmenu/com.spocky.projengmenu.services.AccessibilityService"

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine, level: OptimLevel) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9ProjectivyFixer — Fixing Image Manager")
        applied = failed = 0

        # Sprawdzenie czy Projectivy jest zainstalowany
        if cls.PKG not in guard.sh("pm list packages").output:
            L.warn("Projectivy Launcher nie jest zainstalowany. Pomijam.")
            return OptimResult("ATV9ProjectivyFixer", False, 0, 0, 0)

        # 1. Nadanie uprawnień krytycznych (Shell/Root level)
        perms = [
            f"pm grant {cls.PKG} android.permission.WRITE_SECURE_SETTINGS",
            f"pm grant {cls.PKG} android.permission.SET_DEBUG_APP",
            f"appops set {cls.PKG} SYSTEM_ALERT_WINDOW allow",
            f"appops set {cls.PKG} PROJECT_MEDIA allow" # Wymagane na niektórych ATV9 do filtrów
        ]
        
        for cmd in perms:
            if guard.sh(cmd).ok or DRY_RUN:
                applied += 1
                persist.queue(cmd)

        # 2. Siłowa aktywacja Usługi Ułatwień Dostępu (Klucz do Image Managera)
        # Pobieramy aktualne usługi, żeby ich nie nadpisać
        current_services = guard.sh("settings get secure enabled_accessibility_services").output.strip()
        if cls.ACCESSIBILITY_SERVICE not in current_services:
            new_services = f"{current_services}:{cls.ACCESSIBILITY_SERVICE}".strip(":")
            cmd_acc = f"settings put secure enabled_accessibility_services {new_services}"
            cmd_acc_on = "settings put secure accessibility_enabled 1"
            
            if guard.sh(cmd_acc).ok or DRY_RUN:
                guard.sh(cmd_acc_on)
                applied += 1
                L.ok("Usługa Accessibility dla Projectivy aktywowana (Silnik Obrazu).")
                persist.queue(cmd_acc)
                persist.queue(cmd_acc_on)

        # 3. Dodatkowe flagi dla procesora obrazu ( Sagecom / BCM72604 Specific )
        # Ustawiamy Projectivy jako 'active' w systemie zarządzania energią
        guard.sh(f"am set-standby-bucket {cls.PKG} active")
        
        # Wymuszamy zatrzymanie i restart launchera, aby przeładował uprawnienia
        L.info("Restartowanie Projectivy w celu przeładowania filtrów...")
        guard.sh(f"am force-stop {cls.PKG}")
        guard.sh(f"monkey -p {cls.PKG} -c android.intent.category.LAUNCHER 1")

        elapsed = time.monotonic() - t0
        L.success("Błąd 'Nie załadowano menadżera obrazu' powinien zostać rozwiązany.")
        return OptimResult("ATV9ProjectivyFixer", applied > 0, applied, failed, elapsed)

# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK (FULL ORIGINAL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9HealthCheck:
    @classmethod
    def run(cls, guard: ADBGuard, profile: DeviceProfile) -> Dict[str,Any]:
        L.hdr("ATV9HealthCheck — Weryfikacja po optymalizacji")
        checks: Dict[str,Any] = {}

        checks["gpu_renderer"] = guard.sh("getprop debug.hwui.renderer").output.strip()
        L.table_row("GPU Renderer", checks["gpu_renderer"], ok=(checks["gpu_renderer"] != ""))

        checks["vulkan"] = guard.sh("getprop debug.hwui.disable_vulkan").output.strip()

        checks["sf_latch"] = guard.sh("getprop debug.sf.latch_unsignaled").output.strip()
        L.table_row("SF latch_unsignaled", checks["sf_latch"], ok=(checks["sf_latch"] == "1"))

        checks["heap_growth"] = guard.sh("getprop dalvik.vm.heapgrowthlimit").output.strip()
        L.table_row("Heap growth limit", checks["heap_growth"], ok=(checks["heap_growth"] != ""))

        mem_raw = guard.sh("cat /proc/meminfo | grep MemAvailable").output
        m = re.search(r"(\d+)", mem_raw)
        avail_mb = int(m.group(1)) // 1024 if m else 0
        checks["avail_mb"] = avail_mb
        L.table_row("RAM dostępne", f"{avail_mb}MB", ok=(avail_mb > 200))

        checks["wifi_scan"] = guard.sh("settings get global wifi_scan_always_enabled").output.strip()
        L.table_row("WiFi scan always", checks["wifi_scan"], ok=(checks["wifi_scan"] == "0"))

        checks["anim_scale"] = guard.sh("settings get global window_animation_scale").output.strip()
        L.table_row("Animacje UI", f"{checks['anim_scale']}×", ok=(float(checks["anim_scale"] or "1") <= 0.5))

        checks["lmk_fc"] = guard.sh("getprop ro.lmk.filecache_min_kb").output.strip()
        L.table_row("LMK filecache_min", f"{checks['lmk_fc']} KB", ok=(checks["lmk_fc"] != ""))

        checks["persist_magisk"] = "found" if guard.sh(f"ls {PERSIST_MAGISK_REMOTE} 2>/dev/null").output.strip() else "not found"
        checks["persist_initd"]  = "found" if guard.sh(f"ls {PERSIST_INITD_REMOTE} 2>/dev/null").output.strip() else "not found"
        L.table_row("Persist Magisk", checks["persist_magisk"], ok=(checks["persist_magisk"]=="found"))
        L.table_row("Persist init.d", checks["persist_initd"], ok=(checks["persist_initd"]=="found"))

        ok_count = sum(1 for v in checks.values() if v not in ("","0","not found"))
        total    = len(checks)
        score    = int(ok_count / total * 100)
        checks["score"] = score
        color = C.OK if hasattr(C,'OK') and score >= 80 else ''
        L.section(f"Health Score: {color}{score}/100{C.RST}")
        return checks


# ══════════════════════════════════════════════════════════════════════════════
# PROBE (FULL ORIGINAL VERSION + FIX SILENT ERROR)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9Probe:
    @classmethod
    def run(cls, guard: ADBGuard) -> DeviceProfile:
        L.section("Probe: wykrywanie profilu sprzętowego")
        p = DeviceProfile()

        # UWAGA NA POPRAWKĘ BŁĘDU Z TypeError (Usunięto parametr silent=True)
        def gp(prop: str) -> str:
            return guard.sh(f"getprop {prop}").output.strip()

        p.soc         = gp("ro.board.platform")
        p.gpu_model   = gp("ro.hardware.egl") or gp("ro.hardware.vulkan") or "unknown"
        p.android_api = int(gp("ro.build.version.sdk") or "28")
        cpu_abi       = gp("ro.product.cpu.abi")
        p.cpu_cores   = cls._count_cores(guard)
        p.cpu_max_mhz = cls._detect_cpu_max(guard)
        p.ram_mb      = cls._detect_ram(guard)

        soc_l = p.soc.lower()
        p.is_bcm     = any(x in soc_l for x in ("bcm", "72604", "broadcom"))
        p.is_amlogic = any(x in soc_l for x in ("amlogic","meson","s905","s912"))

        vk_raw = guard.sh("vulkaninfo 2>/dev/null | head -5 || getprop ro.hardware.vulkan").output
        p.has_vulkan = "vulkan" in vk_raw.lower() and "1." in vk_raw
        p.has_vc4    = p.is_bcm   
        p.has_mali   = "mali" in p.gpu_model.lower()

        p.has_magisk = bool(guard.sh("ls /data/adb/magisk 2>/dev/null").output)
        p.has_su     = bool(guard.sh("which su 2>/dev/null").output)
        p.has_init_d = bool(guard.sh("ls /system/etc/init.d/ 2>/dev/null").output)

        L.table_row("SoC",         p.soc)
        L.table_row("GPU",         p.gpu_model)
        L.table_row("RAM",         f"{p.ram_mb}MB")
        L.table_row("CPU",         f"{p.cpu_cores} cores @ {p.cpu_max_mhz}MHz")
        L.table_row("Vulkan",      str(p.has_vulkan))
        L.table_row("VC4",         str(p.has_vc4))
        L.table_row("Magisk",      str(p.has_magisk))
        L.table_row("init.d",      str(p.has_init_d))
        L.table_row("Persist method", p.persist_method)
        L.table_row("GPU backend", p.optimal_gpu_backend.value)
        return p

    @classmethod
    def _count_cores(cls, guard: ADBGuard) -> int:
        raw = guard.sh("nproc 2>/dev/null || ls /sys/devices/system/cpu/ 2>/dev/null | grep -c 'cpu[0-9]'").output.strip()
        return int(raw) if raw.isdigit() else 2

    @classmethod
    def _detect_cpu_max(cls, guard: ADBGuard) -> int:
        raw = guard.sh("cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq 2>/dev/null").output.strip()
        return int(raw) // 1000 if raw.isdigit() else 0

    @classmethod
    def _detect_ram(cls, guard: ADBGuard) -> int:
        raw = guard.sh("grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}'").output.strip()
        return int(raw) // 1024 if raw.isdigit() else 2048


# ══════════════════════════════════════════════════════════════════════════════
# MASTER OPTIMIZER (FULL VERSION)
# ══════════════════════════════════════════════════════════════════════════════

class ATV9MasterOptimizer:
    def __init__(self, guard: ADBGuard, journal: SessionJournal, level: OptimLevel = OptimLevel.STANDARD) -> None:
        self._guard   = guard
        self._journal = journal
        self._level   = level
        self._profile: Optional[DeviceProfile] = None
        self._persist: Optional[ATV9PersistEngine] = None
        self._results: List[OptimResult] = []

    def run_full(self) -> List[OptimResult]:
        L.hdr(f"ATV9 Master Optimizer — [{self._level.value.upper()}]")
        t_total = time.monotonic()

        self._profile = ATV9Probe.run(self._guard)
        self._persist = ATV9PersistEngine(self._guard, self._journal, self._profile)

        modules: List[Tuple[str, Any]] = [
            ("Display",  lambda: ATV9DisplayOptimizer.apply(self._guard, self._journal, self._persist, self._profile)),
            ("GPU",      lambda: ATV9GPUOptimizer.apply(self._guard, self._journal, self._persist, self._profile, self._level)),
            ("ART",      lambda: ATV9ARTOptimizer.apply(self._guard, self._journal, self._persist, self._profile, self._level)),
            ("Power",    lambda: ATV9PowerOptimizer.apply(self._guard, self._journal, self._persist, self._profile, self._level)),
            ("Network",  lambda: ATV9NetworkOptimizer.apply(self._guard, self._journal, self._persist, self._profile)),
            ("LMK",      lambda: ATV9LMKOptimizer.apply(self._guard, self._journal, self._persist, self._profile, self._level)),
            ("Input",    lambda: ATV9InputOptimizer.apply(self._guard, self._journal, self._persist, self._level)),
            ("Debloat",  lambda: ATV9Debloater.apply(self._guard, self._journal, self._persist, self._level)),
            ("CastPerms", lambda: ATV9CastAndPermsOptimizer.apply(self._guard, self._journal, self._persist, self._level)),
            ("ProjFix",   lambda: ATV9ProjectivyFixer.apply(self._guard, self._journal, self._persist, self._level)),
            ("Daemon",   lambda: ATV9BackgroundDaemon.apply(self._guard, self._journal, self._persist)),
            ("IO_Store", lambda: ATV9IOStorageOptimizer.apply(self._guard, self._journal, self._persist, self._level)),
        ]

        for name, fn in modules:
            try:
                self._results.append(fn())
            except Exception as exc:
                L.err(f"Moduł {name}: {exc}")
                self._results.append(OptimResult(f"ATV9{name}", False, 0, 1, 0.0, notes=[str(exc)]))

        L.section("PersistEngine: commit → skrypty startowe")
        persist_ok = self._persist.commit()
        for r in self._results: r.persist_ok = persist_ok
        
        if persist_ok: L.ok(f"Persist: {self._profile.persist_method} → tweaki przeżyją reboot")
        else: L.warn("Persist: tylko settings (setprop zresetowane po rebootcie)")

        checks = ATV9HealthCheck.run(self._guard, self._profile)
        self._print_final_report(t_total, checks)
        return self._results

    def run_module(self, module: str) -> OptimResult:
        if self._profile is None: self._profile = ATV9Probe.run(self._guard)
        if self._persist is None: self._persist = ATV9PersistEngine(self._guard, self._journal, self._profile)

        dispatch: Dict[str, Any] = {
            "display": lambda: ATV9DisplayOptimizer.apply(self._guard, self._journal, self._persist, self._profile),
            "gpu":     lambda: ATV9GPUOptimizer.apply(self._guard, self._journal, self._persist, self._profile, self._level),
            "art":     lambda: ATV9ARTOptimizer.apply(self._guard, self._journal, self._persist, self._profile, self._level),
            "power":   lambda: ATV9PowerOptimizer.apply(self._guard, self._journal, self._persist, self._profile, self._level),
            "network": lambda: ATV9NetworkOptimizer.apply(self._guard, self._journal, self._persist, self._profile),
            "lmk":     lambda: ATV9LMKOptimizer.apply(self._guard, self._journal, self._persist, self._profile, self._level),
            "input":   lambda: ATV9InputOptimizer.apply(self._guard, self._journal, self._persist, self._level),
            "debloat": lambda: ATV9Debloater.apply(self._guard, self._journal, self._persist, self._level),
            "cast":    lambda: ATV9CastAndPermsOptimizer.apply(self._guard, self._journal, self._persist, self._level),
            "projfix": lambda: ATV9ProjectivyFixer.apply(self._guard, self._journal, self._persist, self._level),
            "daemon":  lambda: ATV9BackgroundDaemon.apply(self._guard, self._journal, self._persist),
            "io":      lambda: ATV9IOStorageOptimizer.apply(self._guard, self._journal, self._persist, self._level),
        }
        
        fn = dispatch.get(module.lower())
        if fn:
            r = fn()
            self._persist.commit()
            return r
        L.err(f"Nieznany moduł: {module}. Dostępne: {list(dispatch)}")
        return OptimResult(module, False)

    def _print_final_report(self, t_total: float, checks: Dict[str,Any]) -> None:
        elapsed = time.monotonic() - t_total
        ok_n = sum(1 for r in self._results if r.success)
        applied = sum(r.applied for r in self._results)
        failed  = sum(r.failed  for r in self._results)

        L.hdr("ATV9 Master Optimizer — Raport Finalny")
        L.table_row("Moduły OK", f"{ok_n}/{len(self._results)}")
        L.table_row("Tweaki zastosowane", str(applied))
        L.table_row("Tweaki nieudane", str(failed), ok=(failed == 0))
        L.table_row("Czas optymalizacji", f"{elapsed:.1f}s")
        L.table_row("Persist method", self._profile.persist_method if self._profile else "?", ok=(self._profile.persist_method != "props_only" if self._profile else False))
        L.table_row("Health Score", f"{checks.get('score',0)}/100", ok=(checks.get('score',0) >= 75))

        L.section("Wyniki modułów")
        for r in self._results: print(f"  {r.summary}")

        if self._profile and self._profile.persist_method == "props_only":
            L.warn("Brak roota — tylko settings przeżyją reboot.\nZainstaluj Termux:Boot dla skryptu.")

# ══════════════════════════════════════════════════════════════════════════════
# INTEGRACJA Z TITANIUM BRAIN (Faza 5)
# ══════════════════════════════════════════════════════════════════════════════

def register_atv9_ops(brain: Any) -> None:
    def _make_optimizer(b: Any) -> ATV9MasterOptimizer:
        return ATV9MasterOptimizer(b._guard, b._journal, OptimLevel(b._level) if isinstance(b._level, str) else b._level)

    ops = [
        ("atv9_full",    lambda b, **_: _make_optimizer(b).run_full(), "Pełna optymalizacja (Full)"),
        ("atv9_display", lambda b, **_: _make_optimizer(b).run_module("display"), "Color Engine, HDR10 HDMI"),
        ("atv9_gpu",     lambda b, **_: _make_optimizer(b).run_module("gpu"), "Skia backend + VSync"),
        ("atv9_art",     lambda b, **_: _make_optimizer(b).run_module("art"), "AOT compile + heap + GC"),
        ("atv9_power",   lambda b, **_: _make_optimizer(b).run_module("power"), "Fixed Performance + CPU"),
        ("atv9_network", lambda b, **_: _make_optimizer(b).run_module("network"), "WiFi stability + TCP"),
        ("atv9_lmk",     lambda b, **_: _make_optimizer(b).run_module("lmk"), "LMKD PSI + OOM adj"),
        ("atv9_input",   lambda b, **_: _make_optimizer(b).run_module("input"), "Input latency + animacje"),
        ("atv9_debloat", lambda b, **_: _make_optimizer(b).run_module("debloat"), "Dezaktywacja pakietów"),
        ("atv9_cast",    lambda b, **_: _make_optimizer(b).run_module("cast"), "Casting Fix, Projectivy Perms, Standby OFF"),
        ("atv9_daemon",  lambda b, **_: _make_optimizer(b).run_module("daemon"), "Demon w tle"),
        ("atv9_io",      lambda b, **_: _make_optimizer(b).run_module("io"), "Optymalizacja I/O Storage i eMMC"),
        ("atv9_persist", lambda b, **_: (ATV9PersistEngine(b._guard, b._journal, ATV9Probe.run(b._guard)).commit()), "Zapisz tweaki startowe"),
        ("atv9_probe",   lambda b, **_: ATV9Probe.run(b._guard), "Wykryj profil sprzętowy"),
        ("atv9_health",  lambda b, **_: ATV9HealthCheck.run(b._guard, ATV9Probe.run(b._guard)), "Health check po optymalizacji"),
    ]
    for key, fn, desc in ops: brain._DISPATCH[key] = (fn, desc)
    L.ok(f"ATV9: zarejestrowano {len(ops)} operacji w TitaniumBrain")

# ══════════════════════════════════════════════════════════════════════════════
# CLI STANDALONE + RECONNECT FIX
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse
    p = argparse.ArgumentParser(prog="titanium_atv9_optimizer", description="ATV9 Deep Optimizer — ULTIMATE EDITION")
    p.add_argument("--device", default="192.168.1.3")
    p.add_argument("--level", default="standard", choices=["safe","standard","aggressive","turbo"])
    p.add_argument("--module", default=None, choices=["display", "gpu","art","power","network","lmk","input","debloat","daemon","cast","projfix","persist","probe"])
    p.add_argument("--health", action="store_true", help="Tylko health check")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    from titanium_phase1 import titanium_init, ADBStatus, LOG_DIR
    titanium_init(dry_run=args.dry_run)
    
    L.info("Nawiązywanie połączenia ADB...")
    status = ADB.connect(args.device)
    retries = 3
    
    # Anti-disconnect logic
    while status != ADBStatus.CONNECTED and retries > 0 and not args.dry_run:
        L.warn(f"ADB nieudane ({status.value}). Próba ponownego połączenia... (pozostało prób: {retries})")
        time.sleep(2)
        status = ADB.connect(args.device)
        retries -= 1

    if status != ADBStatus.CONNECTED and not args.dry_run:
        L.err(f"Krytyczny błąd ADB: {status.value}. Brak stabilnego połączenia.")
        raise SystemExit(1)

    guard = ADBGuard(args.device)
    guard.__enter__()
    journal = SessionJournal(LOG_DIR)
    opt = ATV9MasterOptimizer(guard, journal, OptimLevel(args.level))

    try:
        if args.health:
            profile = ATV9Probe.run(guard)
            ATV9HealthCheck.run(guard, profile)
        elif args.module:
            if args.module == "probe": ATV9Probe.run(guard)
            elif args.module == "persist":
                profile = ATV9Probe.run(guard)
                persist = ATV9PersistEngine(guard, journal, profile)
                persist.commit()
            else: opt.run_module(args.module)
        else: opt.run_full()
    except KeyboardInterrupt:
        L.warn("Przerwano ręcznie.")
    finally:
        journal.summary()
        try: guard.__exit__(None, None, None)
        except Exception: pass

if __name__ == "__main__":
    main()
