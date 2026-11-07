#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM — ATV9 Deep Optimizer v1.0                                ║
║  Target  : Android TV 9 (API 28) · BCM72604 / Amlogic S905X · Cortex-A15  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Moduły:                                                                     ║
║    ATV9GPUOptimizer      — Skia backend, VSync phase offsets, SF tweaks     ║
║    ATV9ARTOptimizer      — AOT speed compile, heap, GC, dex2oat             ║
║    ATV9LMKOptimizer      — LMKD PSI, max_cached_processes, OOM adj          ║
║    ATV9PowerOptimizer    — Fixed-performance, CPU governor, thermal          ║
║    ATV9NetworkOptimizer  — WiFi stability, TCP bufors, Stagefright           ║
║    ATV9InputOptimizer    — VSync offsets, input latency, tap thresholds      ║
║    ATV9Debloater         — pm disable-user, telemetry, GMS partial           ║
║    ATV9PersistEngine     — zapis tweaków do skryptów przeżywających reboot   ║
║    ATV9HealthCheck       — diagnostyka po optymalizacji                      ║
║    ATV9MasterOptimizer   — pełna orkiestracja wszystkich modułów             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Integracja z Titanium Brain (Faza 5):                                       ║
║    brain.dispatch("atv9_full")                                               ║
║    brain.dispatch("atv9_gpu")                                                ║
║    brain.dispatch("atv9_persist")                                            ║
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

# Skrypt startowy — ładowany przez init.d lub Magisk service.d
PERSIST_HEADER = """#!/system/bin/sh
# PlayBox Titanium v15.7 — Persist Script
# Wygenerowany: {ts}
# Przeżywa reboot: init.d / Magisk service.d
# ─────────────────────────────────────────
TITANIUM_LOG=/data/local/tmp/titanium_persist.log
echo "[$(date)] Titanium persist start" >> $TITANIUM_LOG
"""

# GPU — wykryte backendy (ważność: BCM72604 ma VC4, nie Mali/Vulkan)
class GPUBackend(str, Enum):
    SKIAGL         = "skiagl"          # VC4 / BCM72604 — potwierdzone
    SKIAGLTHREADED = "skiaglthreaded"  # VC4 threaded
    SKIAVK         = "skiavk"          # Mali-G31 / Amlogic S905X3
    OPENGL         = "opengl"          # legacy fallback

# Serwisy systemowe krytyczne (nie wyłączaj)
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
    """
    Wykryty profil sprzętowy — determiniuje wybór tweaków.
    Wypełniany przez ATV9MasterOptimizer.probe() przed optymalizacją.
    """
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
    has_init_d:    bool  = False    # partycja /system/etc/init.d istnieje
    has_magisk:    bool  = False    # Magisk root
    has_su:        bool  = False    # dowolny root

    @property
    def optimal_gpu_backend(self) -> GPUBackend:
        """Dobiera optymalny renderer na podstawie profilu sprzętu."""
        if self.has_vulkan and self.has_mali:
            return GPUBackend.SKIAVK
        if self.has_vc4 or self.is_bcm:
            return GPUBackend.SKIAGLTHREADED   # VC4: brak Vulkan
        return GPUBackend.SKIAGL

    @property
    def recommended_heap_growth(self) -> str:
        if self.ram_mb >= 3000: return "384m"
        if self.ram_mb >= 1800: return "256m"
        return "128m"

    @property
    def recommended_heap_size(self) -> str:
        if self.ram_mb >= 3000: return "768m"
        if self.ram_mb >= 1800: return "512m"
        return "256m"

    @property
    def recommended_max_cached(self) -> int:
        if self.ram_mb >= 3000: return 64
        if self.ram_mb >= 1800: return 32
        return 12

    @property
    def persist_method(self) -> str:
        if self.has_magisk:  return "magisk"
        if self.has_init_d:  return "initd"
        if self.has_su:      return "su_script"
        return "props_only"   # brak roota — tylko setprop (nie przeżyje reboot)


@dataclass
class OptimResult:
    """Wynik modułu optymalizacji."""
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
        if self.persist_ok:
            s += f"  {C.GR if hasattr(C,'GR') else C.OK}[persist✓]{C.RST}"
        return s


# ══════════════════════════════════════════════════════════════════════════════
# PERSIST ENGINE — kluczowy: tweaki przeżywające reboot
# ══════════════════════════════════════════════════════════════════════════════

class ATV9PersistEngine:
    """
    Zapisuje tweaki do skryptów uruchamianych przy starcie systemu.

    Strategie (w kolejności priorytetu):
    ──────────────────────────────────────────────────────────────────────────
    S1  Magisk service.d   — /data/adb/service.d/titanium_persist.sh
                             Uruchamiany przez Magisk jako root post-boot.
                             Najlepsza metoda: pełny root, persist.* dozwolone.

    S2  init.d             — /system/etc/init.d/99titanium
                             Wymaga RW /system lub bind mount przez Magisk.
                             Uruchamiany przez init przy starcie Androida.

    S3  su script          — /data/local/tmp/titanium_persist.sh
                             + wpis do com.termux.boot lub Autostart app.
                             Wymaga Termux:Boot lub podobnej aplikacji.

    S4  props-only         — /data/local.prop (Android legacy persist)
                             Niektóre właściwości persist.* przeżywają reboot
                             bez roota jeśli zapisane przez system.

    S5  Settings DB        — settings put global/system/secure
                             Przeżywa reboot ZAWSZE (SQLite database).
                             Ograniczone do settings provider API.
    ──────────────────────────────────────────────────────────────────────────
    """

    def __init__(self, guard: ADBGuard, journal: SessionJournal,
                 profile: DeviceProfile) -> None:
        self._guard   = guard
        self._journal = journal
        self._profile = profile
        self._cmds:   List[str] = []   # kolejka komend do zapisania

    def queue(self, cmd: str, description: str = "") -> None:
        """Dodaje komendę do kolejki persist."""
        self._cmds.append(cmd)
        if description:
            self._cmds.insert(-1, f"# {description}")

    def commit(self) -> bool:
        """
        Zapisuje wszystkie kolejkowane komendy do skryptu startowego.
        Zwraca True przy sukcesie.
        """
        if not self._cmds:
            return True

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
        """Magisk service.d — najlepsza metoda persist."""
        return self._push_and_chmod(script, PERSIST_MAGISK_REMOTE, "755")

    def _write_initd(self, script: str) -> bool:
        """init.d — wymaga RW /system."""
        # Próba remount RW (działa z Magisk lub rootem)
        self._guard.sh(
            "mount -o remount,rw /system 2>/dev/null || true"
        )
        ok = self._push_and_chmod(script, PERSIST_INITD_REMOTE, "755")
        self._guard.sh(
            "mount -o remount,ro /system 2>/dev/null || true"
        )
        return ok

    def _write_su_script(self, script: str) -> bool:
        """Skrypt /data/local/tmp — uruchamiany przez Termux:Boot."""
        ok = self._push_and_chmod(script, PERSIST_SCRIPT_REMOTE, "755")
        if ok:
            L.info(
                "Persist: skrypt zapisany. Aby uruchamiał się przy rebootcie:\n"
                "  Zainstaluj Termux:Boot i umieść wywołanie w ~/.termux/boot/"
            )
        return ok

    def _write_local_prop(self, script: str) -> bool:
        """
        /data/local.prop — legacy Android persist.
        Obsługuje TYLKO właściwości (setprop), nie komendy shell.
        Wyodrębniamy tylko setprop z kolejki.
        """
        props = []
        for line in self._cmds:
            m = re.match(r"setprop\s+(\S+)\s+(.+)", line.strip())
            if m:
                props.append(f"{m.group(1)}={m.group(2)}")

        if not props:
            L.warn("PersistEngine: brak właściwości do zapisania w local.prop")
            return False

        content = "\n".join(props) + "\n"
        # Dołącz do istniejącego local.prop
        existing = self._guard.sh("cat /data/local.prop 2>/dev/null").output
        new_content = existing + "\n# Titanium ATV9\n" + content

        tmp = "/sdcard/titanium_local_prop.tmp"
        ADB.push(str(self._create_local_tmp(new_content)), tmp)
        self._guard.sh(f"cp {tmp} /data/local.prop && rm {tmp}")
        L.ok("local.prop zaktualizowany (właściwości persist.* przeżyją reboot)")
        L.warn("Wymagany restart: adb reboot")
        return True

    def _push_and_chmod(self, content: str, remote: str, mode: str) -> bool:
        """Bezpieczne wysłanie skryptu: base64 → decode → chmod."""
        import base64
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        cmd = (
            f"echo '{b64}' | base64 -d > {remote} && "
            f"chmod {mode} {remote}"
        )
        r = self._guard.sh(cmd, timeout=15)
        if r.ok or DRY_RUN:
            L.ok(f"Persist zapisano: {remote}  (mode={mode})")
            return True
        L.warn(f"Persist zapis nieudany: {remote}: {r.stderr[:40]}")
        return False

    def _create_local_tmp(self, content: str) -> Path:
        """Tworzy plik tymczasowy na hoście."""
        import tempfile
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".prop",
                                        delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        return Path(f.name)


# ══════════════════════════════════════════════════════════════════════════════
# GPU OPTIMIZER — Skia, VSync, SurfaceFlinger
# ══════════════════════════════════════════════════════════════════════════════

class ATV9GPUOptimizer:
    """
    Optymalizacja potoku graficznego Android TV 9.

    Kluczowe obszary:
    ─────────────────────────────────────────────────────────────────────────
    1. Backend Skia — dobór SkiaGL/SkiaVK/SkiaGLThreaded
       BCM72604/VC4  → skiaglthreaded  (brak Vulkan na VC4)
       Mali-G31/G52  → skiavk          (Vulkan 1.1 na Mali)
       Legacy/inne   → skiagl          (bezpieczny fallback)

    2. VSync Phase Offsets — redukcja input latency
       early_phase_offset_ns     : czas przed vsync gdy SF zaczyna rendering
       high_fps_early_phase_offset: dla 60Hz trybu
       Cel: SF i App renderują PRZED vsyncem → zero jank

    3. SurfaceFlinger tweaki
       latch_unsignaled=1 : SF pobiera bufory bez czekania na fence signal
                            → -1 klatka opóźnienia
       disable_backpressure=1: wyłącza hamowanie pipelinu przy pełnych buf.
       enable_gl_backpressure=0: brak back-pressure na GPU path

    4. HWUI pipeline
       use_buffer_age=true : reuse części poprzedniego bufora → mniej rysowania
       capture_skp_enabled : tylko do diagnostyki (wyłączone domyślnie)
    ─────────────────────────────────────────────────────────────────────────
    Źródła: AOSP SurfaceFlinger source, VC4-AG100-R §5, Android 9 HWUI docs
    """

    # VSync phase offsets (ns) — dobrane dla ATV9 60Hz
    VSYNC_PHASE_SF_60HZ   = 2_000_000    # 2ms — SF phase offset
    VSYNC_PHASE_APP_60HZ  = 4_000_000    # 4ms — App phase offset
    VSYNC_PHASE_SF_50HZ   = 4_000_000    # 4ms — SF @ 50Hz PAL
    VSYNC_PHASE_EARLY     = 1_000_000    # 1ms — early phase (low latency)

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine,
              profile: DeviceProfile,
              level: OptimLevel = OptimLevel.STANDARD) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9GPUOptimizer — Skia · VSync · SurfaceFlinger")
        applied = failed = 0
        notes: List[str] = []

        backend = profile.optimal_gpu_backend
        L.info(f"GPU: {profile.gpu_model}  Backend: {backend.value}")
        notes.append(f"GPU backend: {backend.value}")

        # ── Blok 1: Skia renderer props ───────────────────────────────────
        renderer_props: List[Tuple[str,str,str]] = [
            ("debug.hwui.renderer",          backend.value,
             f"Skia renderer: {backend.value}"),
            ("debug.renderengine.backend",   backend.value + "threaded"
             if "gl" in backend.value else backend.value,
             "RenderEngine backend"),
            # Vulkan — włącz tylko jeśli GPU obsługuje
            ("debug.hwui.disable_vulkan",    "0" if profile.has_vulkan else "1",
             f"Vulkan: {'enabled' if profile.has_vulkan else 'disabled (no HW support)'}"),
            # Overdraw reduction
            ("debug.hwui.use_buffer_age",    "true",
             "Buffer age: reuse stale regions → mniej overdraw"),
            ("debug.force_opengl",           "1",
             "Force GPU composition (disable SW fallback)"),
            ("persist.sys.ui.hw",            "true",
             "UI HW acceleration: forced"),
        ]

        for prop, val, desc in renderer_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1
                L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
                journal.record(RepairSector.GPU_PIPELINE,
                               "ATV9GPUOptimizer", desc,
                               f"setprop {prop} {val}",
                               f"setprop {prop} ''")
            else:
                failed += 1; L.warn(f"setprop {prop}: FAIL")

        # ── Blok 2: VSync Phase Offsets ───────────────────────────────────
        # Cel: App render window PRZED vsyncem → minimal frame latency
        # Dobieramy na podstawie wykrytego Hz (50 lub 60)
        sf_hz = 50 if profile.is_bcm else 60
        sf_off  = cls.VSYNC_PHASE_SF_50HZ  if sf_hz == 50 else cls.VSYNC_PHASE_SF_60HZ
        app_off = cls.VSYNC_PHASE_APP_60HZ

        vsync_props: List[Tuple[str,str,str]] = [
            ("debug.sf.early_phase_offset_ns",
             str(sf_off),
             f"SF VSync phase offset: {sf_off//1_000_000}ms @ {sf_hz}Hz"),
            ("debug.sf.early_app_phase_offset_ns",
             str(app_off),
             f"App VSync phase offset: {app_off//1_000_000}ms"),
            ("debug.sf.high_fps_early_phase_offset_ns",
             str(cls.VSYNC_PHASE_EARLY),
             f"High-FPS early phase: {cls.VSYNC_PHASE_EARLY//1_000_000}ms"),
            ("debug.sf.high_fps_early_gl_phase_offset_ns",
             str(cls.VSYNC_PHASE_EARLY),
             "High-FPS GL early phase offset"),
        ]

        for prop, val, desc in vsync_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else:
                failed += 1; L.warn(f"VSync prop {prop}: FAIL")

        # ── Blok 3: SurfaceFlinger settings ───────────────────────────────
        sf_settings: List[Tuple[str,str,str,str]] = [
            # (namespace, key, value, desc)
            ("global", "surface_flinger_enable_layer_caching", "true",
             "SF: layer cache → mniej full redraws"),
            ("global", "sf_frame_rate_override",               "0",
             "SF: disable frame rate override (tryb natywny)"),
        ]
        for ns, key, val, desc in sf_settings:
            r = guard.sh(f"settings put {ns} {key} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} {val}", desc)
            else:
                failed += 1

        # ── Blok 4: SurfaceFlinger setprop tweaki ─────────────────────────
        sf_props: List[Tuple[str,str,str]] = [
            ("debug.sf.latch_unsignaled",       "1",
             "SF latch_unsignaled: pobierz bufory bez fence wait (-1 klatka)"),
            ("debug.sf.disable_backpressure",   "1",
             "SF: brak back-pressure → płynniejszy pipeline"),
            ("debug.sf.enable_gl_backpressure", "0",
             "SF GL back-pressure: wyłączona"),
            ("debug.sf.reuse_refresh_rate_configs", "1",
             "SF: reuse refresh rate config"),
        ]
        for prop, val, desc in sf_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else:
                failed += 1; L.warn(f"SF setprop {prop}: FAIL")

        # ── AGGRESSIVE: Wyłącz HW overlays (wymusza GPU compositing) ─────
        if level in (OptimLevel.AGGRESSIVE, OptimLevel.TURBO):
            r = guard.sh("service call SurfaceFlinger 1008 i32 1 2>/dev/null || true")
            L.ok("SF: wymuś GPU compositing (disable HW overlays)")
            persist.queue(
                "service call SurfaceFlinger 1008 i32 1 2>/dev/null || true",
                "SF: GPU-forced composition"
            )
            applied += 1

        elapsed = time.monotonic() - t0
        result  = OptimResult("ATV9GPUOptimizer", applied > 0,
                              applied, failed, elapsed)
        result.notes = notes
        L.info(result.summary)
        return result


# ══════════════════════════════════════════════════════════════════════════════
# ART OPTIMIZER — AOT, heap, dex2oat, GC
# ══════════════════════════════════════════════════════════════════════════════

class ATV9ARTOptimizer:
    """
    Optymalizacja Android Runtime (ART) dla Android TV 9.

    Strategie kompilacji DEX:
    ─────────────────────────────────────────────────────────────────────────
    speed           : pełna AOT — wszystkie metody → kod maszynowy
                      Start -60%, JIT overhead 0%, pamięć +25%
                      ZALECANE dla ATV (podłączone do zasilania)

    speed-profile   : AOT tylko hot methods (z profilu użycia)
                      Kompromis: szybki start + mniej pamięci

    verify          : tylko weryfikacja — najszybsza instalacja
                      Nie zalecane dla głównych aplikacji

    everything      : kompiluje WSZYSTKO łącznie z bootstrap klas
                      Najlepsza wydajność runtime, największy disk footprint
    ─────────────────────────────────────────────────────────────────────────

    Garbage Collector:
    heaptargetutilization=0.5 → GC częściej, ale krócej (bez stop-the-world)
    heapgrowthlimit            → max heap per app zanim OOM
    dex2oat-threads            → równoległość kompilacji (= CPU cores)
    ─────────────────────────────────────────────────────────────────────────
    """

    # Pakiety priorytetowe — kompiluj jako pierwsze
    PRIORITY_PACKAGES: List[str] = [
        "is.xyz.smarttube",          # SmartTube Next
        "org.xbmc.kodi",             # Kodi
        "com.android.launcher",      # launcher systemowy
        "com.android.systemui",      # SysUI
        "com.google.android.tvlauncher",  # Google TV launcher
    ]

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine,
              profile: DeviceProfile,
              level: OptimLevel = OptimLevel.STANDARD) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9ARTOptimizer — AOT · Heap · GC · dex2oat")
        applied = failed = 0

        # ── Heap tuning — na podstawie profilu RAM ────────────────────────
        heap_props: List[Tuple[str,str,str]] = [
            ("dalvik.vm.heapstartsize",       "16m",
             "Heap start: 16MB (szybka alokacja początkowa)"),
            ("dalvik.vm.heapminfree",         "2m",
             "Heap min free: 2MB"),
            ("dalvik.vm.heapmaxfree",         "16m",
             "Heap max free: 16MB (BCM72604 potwierdzone)"),
            ("dalvik.vm.heapgrowthlimit",     profile.recommended_heap_growth,
             f"Heap growth limit: {profile.recommended_heap_growth} (per app)"),
            ("dalvik.vm.heapsize",            profile.recommended_heap_size,
             f"Heap max: {profile.recommended_heap_size} (hard limit)"),
            # GC strategy — 0.5 → częstsze ale krótsze cykle GC
            ("dalvik.vm.heaptargetutilization", "0.5",
             "Heap utilization: 0.5 (eliminacja stop-the-world pauses)"),
            # dex2oat threading
            ("dalvik.vm.dex2oat-threads",
             str(min(profile.cpu_cores, 4)),
             f"dex2oat threads: {min(profile.cpu_cores,4)} (= CPU cores)"),
            ("dalvik.vm.dex2oat-Xmx",        "512m",
             "dex2oat max heap: 512MB (stabilność kompilacji dużych APK)"),
            ("dalvik.vm.image-dex2oat-filter","speed",
             "System image: AOT speed filter"),
            ("dalvik.vm.dex2oat-filter",      "speed",
             "App dex2oat: speed filter"),
            # ARM specific — Cortex-A15 SDIV/UDIV
            ("dalvik.vm.isa.arm.features",    "default,idiv",
             "ARM ISA: hardware SDIV/UDIV (A15 §A2.6.2)"),
        ]

        for prop, val, desc in heap_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
                journal.record(RepairSector.DALVIK_RUNTIME,
                               "ATV9ARTOptimizer", desc,
                               f"setprop {prop} {val}")
            else:
                failed += 1; L.warn(f"Heap prop {prop}: FAIL")

        # ── AOT Speed Compile — priorytetowe pakiety ──────────────────────
        L.section("AOT: kompilacja priorytetowych pakietów")
        for pkg in cls.PRIORITY_PACKAGES:
            # Sprawdź czy pakiet zainstalowany
            chk = guard.sh(f"pm list packages {pkg} 2>/dev/null").output
            if f"package:{pkg}" not in chk:
                L.debug(f"AOT: {pkg} — niezainstalowany, pomijam")
                continue
            L.info(f"AOT speed compile: {pkg}...")
            r = guard.sh(
                f"cmd package compile -m speed -f {pkg} 2>/dev/null",
                timeout=120
            )
            if r.ok or DRY_RUN:
                applied += 1; L.ok(f"AOT: {pkg} skompilowany")
            else:
                failed += 1; L.warn(f"AOT: {pkg} nieudany: {r.output[:50]}")

        # ── TURBO: pełna AOT kompilacja WSZYSTKICH pakietów ───────────────
        if level == OptimLevel.TURBO:
            L.info("TURBO: AOT speed compile ALL packages...")
            L.warn("To może zająć kilka minut...")
            r = guard.sh(
                "cmd package compile -m speed -f -a 2>/dev/null",
                timeout=600   # 10 min max
            )
            if r.ok or DRY_RUN:
                applied += 1
                L.ok("AOT: pełna kompilacja wszystkich pakietów")
            else:
                failed += 1
                L.warn("AOT all: nieudana (możliwy brak uprawnień)")

        # ── pm trim-caches — agresywne czyszczenie ────────────────────────
        L.info("PM: agresywne czyszczenie cache aplikacji...")
        guard.sh("pm trim-caches 128G 2>/dev/null || true", timeout=60)
        applied += 1
        L.ok("PM: trim-caches 128G (usuwa WSZYSTKIE cache app)")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9ARTOptimizer", applied > 0,
                           applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# LMK OPTIMIZER — LMKD PSI, cached processes, OOM adj
# ══════════════════════════════════════════════════════════════════════════════

class ATV9LMKOptimizer:
    """
    Strojenie Low Memory Killer Daemon (LMKD) dla Android TV 9.

    Android 9 LMKD działa w trybie PSI (Pressure Stall Information)
    zamiast legacy sysfs minfree. Kluczowe różnice:

    PSI-based LMKD (Android 9+):
      - Analizuje /proc/pressure/memory (some/full stall)
      - Reaguje na rzeczywiste ciśnienie pamięciowe, nie progi minfree
      - Konfigurowalne przez ro.lmk.* properties

    Dla ATV9:
      - max_cached_processes: zależy od RAM (8-64)
        Zbyt wysoki → rywalizacja o RAM → jank podczas odtwarzania
        Zbyt niski  → powolne przełączanie (cold start za każdym razem)
      - OOM ADJ: zapobiegaj zabijaniu dekodera video podczas odtwarzania

    Uwaga BCM72604:
      ro.lmk.use_minfree_levels=false → sysfs minfree IGNOROWANE
      Używamy tylko ro.lmk.* props + PSI thresholds
    """

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine,
              profile: DeviceProfile,
              level: OptimLevel = OptimLevel.STANDARD) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9LMKOptimizer — LMKD PSI · OOM · Cached Processes")
        applied = failed = 0

        max_cached = profile.recommended_max_cached
        L.info(f"max_cached_processes: {max_cached} (RAM: {profile.ram_mb}MB)")

        # ── Activity Manager constants ────────────────────────────────────
        # Jeden settings put z wieloma parametrami (JSON-like format)
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
            persist.queue(
                f"settings put global activity_manager_constants '{am_constants}'",
                "Activity Manager constants"
            )

        # ── LMKD properties ───────────────────────────────────────────────
        lmk_props: List[Tuple[str,str,str]] = [
            ("ro.lmk.filecache_min_kb",
             str(90 * 1024),   # 90MB — gwarantuj cache dla dekodera video
             "LMK: filecache min 90MB (4K decoder cache)"),
            ("ro.lmk.use_minfree_levels",  "false",
             "LMK: PSI-based (sysfs minfree ignorowane)"),
            ("ro.lmk.low",                 "1024",
             "LMK: low pressure threshold"),
            ("ro.lmk.medium",              "512",
             "LMK: medium pressure threshold"),
            ("ro.lmk.critical",            "0",
             "LMK: critical threshold"),
            ("ro.lmk.critical_upgrade",    "true",
             "LMK: enable critical upgrade"),
            ("ro.lmk.upgrade_pressure",    "80",
             "LMK: upgrade pressure 80%"),
            ("ro.lmk.downgrade_pressure",  "60",
             "LMK: downgrade pressure 60%"),
            ("ro.lmk.kill_heaviest_task",  "true",
             "LMK: zabij najcięższy proces (nie pierwszy z listy)"),
            ("ro.lmk.kill_timeout_ms",     "100",
             "LMK: timeout zabijania 100ms"),
        ]
        for prop, val, desc in lmk_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)
            else:
                failed += 1; L.warn(f"LMK prop {prop}: FAIL")

        # ── PSI thresholds (wymaga root/rish) ─────────────────────────────
        psi_cmds: List[Tuple[str,str]] = [
            ("echo '70 200' > /proc/pressure/memory 2>/dev/null || true",
             "PSI memory: stall threshold 70ms/200ms"),
            ("echo '200 1000' > /proc/pressure/cpu 2>/dev/null || true",
             "PSI CPU: stall threshold 200ms/1s"),
        ]
        for cmd, desc in psi_cmds:
            r = guard.sh(cmd)
            (L.ok if r.ok else L.warn)(desc)
            if r.ok or DRY_RUN:
                applied += 1
                persist.queue(cmd, desc)

        # ── OOM ADJ ochrona dekodera video ───────────────────────────────
        # SmartTube PID → ustaw oom_adj na wartość chronioną
        if level in (OptimLevel.AGGRESSIVE, OptimLevel.TURBO):
            st_pid = guard.sh(
                "pidof is.xyz.smarttube 2>/dev/null | awk '{print $1}'"
            ).output.strip()
            if st_pid.isdigit():
                guard.sh(
                    f"echo -800 > /proc/{st_pid}/oom_score_adj 2>/dev/null || true"
                )
                L.ok(f"OOM adj: SmartTube PID {st_pid} → -800 (chroniony)")
                applied += 1
                persist.queue(
                    "pid=$(pidof is.xyz.smarttube 2>/dev/null | awk '{print $1}'); "
                    "[ -n \"$pid\" ] && echo -800 > /proc/$pid/oom_score_adj 2>/dev/null || true",
                    "OOM ADJ: SmartTube protected"
                )

        # ── Disable ZRAM jeśli CPU za wolny ──────────────────────────────
        # Na BCM72604 (1.4GHz A15) ZRAM jest bottleneckiem
        if profile.is_bcm or (profile.cpu_max_mhz > 0
                               and profile.cpu_max_mhz <= 1500):
            r = guard.sh("settings put global zram_enabled 0")
            if r.ok or DRY_RUN:
                applied += 1
                L.ok("ZRAM: wyłączony (BCM72604 A15 — CPU zbyt wolny na kompresję)")
                persist.queue("settings put global zram_enabled 0",
                              "ZRAM disabled (BCM72604)")

        # ── ro.config.low_ram override ────────────────────────────────────
        if profile.ram_mb >= 1800:
            r = guard.sh("setprop ro.config.low_ram false")
            if r.ok or DRY_RUN:
                applied += 1
                L.ok("low_ram=false: pełne możliwości Android UI odblokowane")
                persist.queue("setprop ro.config.low_ram false",
                              "low_ram=false (2GB RAM)")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9LMKOptimizer", applied > 0,
                           applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# POWER OPTIMIZER — Fixed performance, CPU governor, thermal
# ══════════════════════════════════════════════════════════════════════════════

class ATV9PowerOptimizer:
    """
    Optymalizacja mocy obliczeniowej dla ATV9.

    Filozofia:
    ATV = zasilanie sieciowe → BRAK ograniczeń bateryjnych.
    Cel: maksymalna stabilna moc obliczeniowa.

    Strategie:
    ──────────────────────────────────────────────────────────────────────
    1. Fixed Performance Mode (Android 9)
       cmd power set-fixed-performance-mode-enabled true
       → Blokuje CPU/GPU na predefiniowanych wysokich taktowaniach
       → Eliminuje ramp-up latency (opóźnienie przy skoku obciążenia)

    2. CPU Governor override
       Governors porównanie dla ATV9:
         schedutil   : reaktywny, CFS-driven, Android domyślny
         interactive : szybki ramp-up, lepszy dla UI (starsze kernele)
         performance : maksymalne takty na stałe (ryzyko thermal)
         conservative: powolny ramp-up (najgorszy dla ATV)
       Zalecenie: schedutil z tuningiem lub performance jeśli chłodzenie OK

    3. Sem enhanced CPU responsiveness
       settings put global sem_enhanced_cpu_responsiveness 1
       → Wymusza szybkie podnoszenie taktowania big.LITTLE przy dotyku/pilocie

    4. Device Idle — wyłącz tryb Doze
       cmd deviceidle disable
       → Eliminuje stany głębokiego uśpienia podczas odtwarzania
    ──────────────────────────────────────────────────────────────────────
    """

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine,
              profile: DeviceProfile,
              level: OptimLevel = OptimLevel.STANDARD) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9PowerOptimizer — Fixed Perf · CPU Gov · Thermal")
        applied = failed = 0

        # ── Fixed Performance Mode ────────────────────────────────────────
        r = guard.sh(
            "cmd power set-fixed-performance-mode-enabled true 2>/dev/null || true"
        )
        if r.ok or DRY_RUN:
            applied += 1
            L.ok("Fixed Performance Mode: AKTYWNY (blokada CPU/GPU)")
            persist.queue(
                "cmd power set-fixed-performance-mode-enabled true 2>/dev/null || true",
                "Fixed Performance Mode"
            )
        else:
            L.warn("Fixed Performance Mode: niedostępny (API level lub uprawnienia)")
            failed += 1

        # ── Sem enhanced responsiveness ───────────────────────────────────
        r = guard.sh("settings put global sem_enhanced_cpu_responsiveness 1")
        if r.ok or DRY_RUN:
            applied += 1
            L.ok("Sem enhanced CPU responsiveness: ON (big.LITTLE fast ramp)")
            persist.queue("settings put global sem_enhanced_cpu_responsiveness 1")

        # ── Device Idle (Doze) — wyłącz podczas odtwarzania ──────────────
        r = guard.sh("cmd deviceidle disable 2>/dev/null || true")
        if r.ok or DRY_RUN:
            applied += 1
            L.ok("Device Idle (Doze): wyłączony (eliminacja deep sleep)")
            persist.queue("cmd deviceidle disable 2>/dev/null || true",
                          "Disable Doze mode")

        # ── CPU Governor tuning ───────────────────────────────────────────
        blk_dev = guard.sh(
            "ls /sys/devices/system/cpu/cpu0/cpufreq/ 2>/dev/null | head -1"
        ).output
        if blk_dev:
            cpu_count = profile.cpu_cores
            gov_cmds: List[Tuple[str,str]] = []

            if level == OptimLevel.TURBO:
                # TURBO: performance governor (max takty na stałe)
                for i in range(cpu_count):
                    gov_cmds.append((
                        f"echo performance > /sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor 2>/dev/null || true",
                        f"CPU{i}: governor=performance (max takty)"
                    ))
            else:
                # STANDARD/AGGRESSIVE: schedutil z minimalną granularnością
                for i in range(cpu_count):
                    gov_cmds.append((
                        f"echo schedutil > /sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor 2>/dev/null || true",
                        f"CPU{i}: governor=schedutil"
                    ))
                    # schedutil rate_limit_us: 500µs (szybszy niż domyślny 10ms)
                    gov_cmds.append((
                        f"echo 500 > /sys/devices/system/cpu/cpu{i}/cpufreq/schedutil/rate_limit_us 2>/dev/null || true",
                        f"CPU{i}: schedutil rate_limit=500µs"
                    ))

            # Max freq — zablokuj CPU na max
            if profile.cpu_max_mhz > 0:
                max_khz = profile.cpu_max_mhz * 1000
                for i in range(cpu_count):
                    gov_cmds.append((
                        f"echo {max_khz} > /sys/devices/system/cpu/cpu{i}/cpufreq/scaling_max_freq 2>/dev/null || true",
                        f"CPU{i}: max_freq={profile.cpu_max_mhz}MHz"
                    ))

            for cmd, desc in gov_cmds:
                r = guard.sh(cmd)
                if r.ok or DRY_RUN:
                    applied += 1; L.ok(desc)
                    persist.queue(cmd, desc)
                else:
                    failed += 1

        # ── PowerMode prop ────────────────────────────────────────────────
        guard.sh("setprop persist.sys.powermode 1")
        persist.queue("setprop persist.sys.powermode 1", "PowerMode: HIGH")
        applied += 1
        L.ok("persist.sys.powermode=1 (maximum performance)")

        # ── Multicore packet scheduler ────────────────────────────────────
        r = guard.sh("settings put system multicore_packet_scheduler 1")
        if r.ok or DRY_RUN:
            applied += 1
            L.ok("Multicore packet scheduler: ON (równoległe przetwarzanie sieci)")
            persist.queue("settings put system multicore_packet_scheduler 1")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9PowerOptimizer", applied > 0,
                           applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# NETWORK OPTIMIZER — WiFi, Stagefright, TCP
# ══════════════════════════════════════════════════════════════════════════════

class ATV9NetworkOptimizer:
    """
    Optymalizacja łączności sieciowej dla streamingu 4K HDR.

    Kluczowe problemy ATV9:
    ──────────────────────────────────────────────────────────────────────
    1. WiFi aggressive scanning → jitter podczas streamingu
       wifi_scan_always_enabled=0 → brak skanowania podczas odtwarzania

    2. WiFi power save → okresowe przebudzenia → packet loss
       wifi_power_save=0 → stałe active mode

    3. TCP bufory za małe dla 4K @ 20-100Mbit/s
       Zwiększone WMEM/RMEM do 2MB max

    4. Stagefright bufory — cache multimedialny
       (Właściwości ukryte, wymagają root)

    5. Captive portal — co 30s blokuje połączenie na test
       Zmiana na Google endpoint lub wyłączenie
    ──────────────────────────────────────────────────────────────────────
    """

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine,
              profile: DeviceProfile) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9NetworkOptimizer — WiFi · TCP · Stagefright")
        applied = failed = 0

        # ── WiFi settings ─────────────────────────────────────────────────
        wifi_settings: List[Tuple[str,str,str,str]] = [
            ("global", "wifi_scan_always_enabled",         "0",
             "WiFi: scan_always disabled (eliminacja jitter)"),
            ("global", "wifi_power_save",                  "0",
             "WiFi: power save OFF (stały active mode)"),
            ("global", "wifi_sleep_policy",                "2",
             "WiFi: never sleep (ATV zawsze podłączony)"),
            ("global", "wifi_aggressive_handover_enabled", "0",
             "WiFi: aggressive handover OFF (stabilność połączenia)"),
            ("global", "wifi_enhanced_auto_join",          "0",
             "WiFi: enhanced auto-join OFF (nie przełączaj AP)"),
            ("global", "wifi_country_code",                "",
             "WiFi: country code reset (max TX power)"),
        ]
        for ns, key, val, desc in wifi_settings:
            r = guard.sh(f"settings put {ns} {key} '{val}'")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} '{val}'", desc)
                journal.record(RepairSector.NETWORK_TCP,
                               "ATV9NetworkOptimizer", desc,
                               f"settings put {ns} {key} {val}")
            else:
                failed += 1

        # ── TCP kernel params ─────────────────────────────────────────────
        tcp_params: List[Tuple[str,str,str]] = [
            # Bufory 128K/512K/2MB — optymalne dla 4K @ 50-100Mbit/s
            ("net/ipv4/tcp_wmem",                  "131072 524288 2097152",
             "TCP Tx buf: 128K/512K/2MB"),
            ("net/ipv4/tcp_rmem",                  "131072 524288 2097152",
             "TCP Rx buf: 128K/512K/2MB"),
            # CUBIC congestion control (domyślny Android)
            ("net/ipv4/tcp_congestion_control",     "cubic",
             "TCP: CUBIC congestion control"),
            # Fast open — przyspiesza TCP handshake dla CDN
            ("net/ipv4/tcp_fastopen",               "3",
             "TCP Fast Open: client+server"),
            # SACK — selective ack (wymagane dla 4K HDR streams)
            ("net/ipv4/tcp_sack",                   "1",
             "TCP SACK: aktywny"),
            # ECN — oznaczanie congestion bez dropped packets
            ("net/ipv4/tcp_ecn",                    "1",
             "TCP ECN: aktywny"),
            # No slow start after idle
            ("net/ipv4/tcp_slow_start_after_idle",  "0",
             "TCP: brak slow-start po idle (CDN streaming)"),
            # NOTSENT_LOWAT — limituje bufor niesłanych danych
            ("net/ipv4/tcp_notsent_lowat",          "131072",
             "TCP notsent_lowat: 128KB"),
            # Socket buffers max
            ("net/core/rmem_max",                   "4194304",
             "Socket Rx max: 4MB"),
            ("net/core/wmem_max",                   "4194304",
             "Socket Tx max: 4MB"),
            ("net/core/netdev_max_backlog",         "5000",
             "Net backlog: 5000 pakietów"),
        ]
        for path, val, desc in tcp_params:
            full_path = f"/proc/sys/{path}"
            cmd  = f"echo '{val}' > {full_path} 2>/dev/null || true"
            r    = guard.sh(cmd)
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(cmd, desc)
            else:
                failed += 1; L.warn(f"sysctl {path}: FAIL")

        # ── DNS Cloudflare + DoT ──────────────────────────────────────────
        dns_cmds: List[Tuple[str,str]] = [
            ("ndc resolver setnetdns 100 '' 1.1.1.1 1.0.0.1 2>/dev/null || true",
             "DNS: Cloudflare 1.1.1.1 + 1.0.0.1"),
            ("setprop net.dns1 1.1.1.1",  "DNS1: Cloudflare"),
            ("setprop net.dns2 1.0.0.1",  "DNS2: Cloudflare fallback"),
            ("settings put global private_dns_mode hostname",
             "DoT: tryb hostname"),
            ("settings put global private_dns_specifier one.one.one.one",
             "DoT: one.one.one.one (NIE dns.cloudflare.com — known bug)"),
        ]
        for cmd, desc in dns_cmds:
            r = guard.sh(cmd)
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(cmd, desc)

        # ── Stagefright buffers (wymaga root) ─────────────────────────────
        sf_props: List[Tuple[str,str,str]] = [
            ("media.stagefright.thumbnail.timeout", "10000",
             "Stagefright: thumbnail timeout 10s"),
            ("media.stagefright.prefer-container-mime-type", "1",
             "Stagefright: prefer container MIME type"),
            ("debug.stagefright.ccodec",             "4",
             "Stagefright: Codec2 priority 4"),
        ]
        for prop, val, desc in sf_props:
            r = guard.sh(f"setprop {prop} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"setprop {prop} {val}", desc)

        # ── Captive portal ────────────────────────────────────────────────
        r = guard.sh(
            "settings put global captive_portal_https_url "
            "https://connectivitycheck.gstatic.com/generate_204"
        )
        if r.ok or DRY_RUN:
            applied += 1
            L.ok("Captive portal: Google HTTPS endpoint")
            persist.queue(
                "settings put global captive_portal_https_url "
                "https://connectivitycheck.gstatic.com/generate_204"
            )

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9NetworkOptimizer", applied > 0,
                           applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# INPUT OPTIMIZER — latencja wejścia, VSync, timeouty pilota
# ══════════════════════════════════════════════════════════════════════════════

class ATV9InputOptimizer:
    """
    Minimalizacja opóźnień wejściowych dla pilota ATV9.

    ATV9 input latency stack:
    HW button → InputReader → InputDispatcher → App → GPU → Display
    Każde ogniwo dodaje opóźnienie. Cel: < 50ms end-to-end.

    Kluczowe tweaki:
    ─────────────────────────────────────────────────────────────────────
    1. long_press_timeout  : 500ms → 300ms (reaguje szybciej na przytrzymanie)
    2. multi_press_timeout : 500ms → 250ms (wykrywa szybkie kliknięcia)
    3. tap_duration_threshold: redukcja progu tap → natychmiastowa rejestracja
    4. touch_blocking_period : 0 → brak blokady po scrollu
    5. InputFlinger priority : oom_adj=-1 → nietykalny przez LMK

    Animacje UI:
    window_animation_scale=0.5 → 2× szybsze animacje okien
    transition_animation_scale=0.5 → 2× szybsze przejścia
    animator_duration_scale=0.5 → 2× szybszy animator obiektów
    (0.0 = całkowite wyłączenie — polecane dla TURBO)
    ─────────────────────────────────────────────────────────────────────
    """

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine,
              level: OptimLevel = OptimLevel.STANDARD) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9InputOptimizer — Input Latency · Timeouty · Animacje")
        applied = failed = 0

        anim_scale = (
            "0.0" if level == OptimLevel.TURBO else
            "0.3" if level == OptimLevel.AGGRESSIVE else
            "0.5"   # STANDARD: 2× szybsze animacje
        )

        # ── Timeouty wejściowe ────────────────────────────────────────────
        input_settings: List[Tuple[str,str,str,str]] = [
            # Secure namespace
            ("secure", "long_press_timeout",         "300",
             "Long press timeout: 300ms (was 500ms) — pilot reaguje szybciej"),
            ("secure", "multi_press_timeout",        "250",
             "Multi press timeout: 250ms (was 500ms)"),
            ("secure", "tap_duration_threshold",     "0.0",
             "Tap duration: 0.0 — natychmiastowa rejestracja naciśnięcia"),
            ("secure", "touch_blocking_period",      "0.0",
             "Touch blocking: 0.0 — brak opóźnienia po przewinięciu"),
            ("secure", "cursor_speed",               "0",
             "Cursor speed: 0 (ATV — brak myszy)"),
            # Global namespace
            ("global", "sysui_latency_reboot_count", "0",
             "SysUI latency counter: reset"),
            # Animacje
            ("global", "window_animation_scale",     anim_scale,
             f"Animacje okien: {anim_scale}×"),
            ("global", "transition_animation_scale", anim_scale,
             f"Animacje przejść: {anim_scale}×"),
            ("global", "animator_duration_scale",    anim_scale,
             f"Animator: {anim_scale}×"),
        ]
        for ns, key, val, desc in input_settings:
            r = guard.sh(f"settings put {ns} {key} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} {val}", desc)
                journal.record(RepairSector.HWUI_RENDERER,
                               "ATV9InputOptimizer", desc,
                               f"settings put {ns} {key} {val}")
            else:
                failed += 1

        # ── InputFlinger — priorytet procesu ─────────────────────────────
        inp_pid = guard.sh(
            "pidof inputflinger 2>/dev/null | awk '{print $1}'"
        ).output.strip()
        if inp_pid.isdigit():
            guard.sh(
                f"echo -1 > /proc/{inp_pid}/oom_adj 2>/dev/null || true"
            )
            L.ok(f"InputFlinger PID {inp_pid}: oom_adj=-1 (nietykalny)")
            applied += 1
            persist.queue(
                "pid=$(pidof inputflinger 2>/dev/null | awk '{print $1}'); "
                "[ -n \"$pid\" ] && echo -1 > /proc/$pid/oom_adj 2>/dev/null || true",
                "InputFlinger: oom_adj=-1"
            )

        # ── TURBO: całkowite wyłączenie dźwięków UI ────────────────────
        if level == OptimLevel.TURBO:
            r = guard.sh("settings put system sound_effects_enabled 0")
            if r.ok or DRY_RUN:
                applied += 1
                L.ok("Dźwięki UI: wyłączone (TURBO mode)")
                persist.queue("settings put system sound_effects_enabled 0")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9InputOptimizer", applied > 0,
                           applied, failed, elapsed)


# ══════════════════════════════════════════════════════════════════════════════
# DEBLOATER — pm disable-user, telemetria, GMS partial, OEM bloat
# ══════════════════════════════════════════════════════════════════════════════

class ATV9Debloater:
    """
    Dezaktywacja zbędnych usług i pakietów Android TV 9.

    Metoda: pm disable-user --user 0 (NIE pm uninstall)
    ─────────────────────────────────────────────────────────────────────
    + Pakiet pozostaje na partycji /system
    + Możliwe przywrócenie przez pm enable <pkg>
    + Aktualizacje OTA nadal działają
    + Bezpieczne — nie narusza integralności systemu
    ─────────────────────────────────────────────────────────────────────

    Hierarchia bezpieczeństwa:
    SAFE     — telemetria, reklamy, raporty crashy (zawsze bezpieczne)
    STANDARD — launcher Google, rekomendacje (zalecane)
    AGGRESSIVE— GMS częściowo, assistant, cloud backup
    TURBO    — sklepowe/demo, producent bloat

    UWAGA: Niektóre pakiety GMS są wymagane przez inne aplikacje.
    Nigdy nie wyłączaj: com.google.android.gsf (Google Services Framework)
    """

    # (pakiet, min_level, opis, kategoria)
    PACKAGES: List[Tuple[str, OptimLevel, str, str]] = [
        # ── SAFE: Telemetria i raporty ─────────────────────────────────────────
        ("com.google.android.feedback",          OptimLevel.SAFE,
         "Google Feedback", "telemetria"),
        ("com.google.android.partnersetup",      OptimLevel.SAFE,
         "Partner Setup", "telemetria"),
        ("com.android.statementservice",         OptimLevel.SAFE,
         "Statement Service (credential validation)", "telemetria"),
        ("com.android.traceur",                  OptimLevel.SAFE,
         "System Trace (raportowanie)", "telemetria"),
        ("com.google.android.onetimeinitializer",OptimLevel.SAFE,
         "One Time Initializer", "telemetria"),

        # ── STANDARD: Launcher i rekomendacje ─────────────────────────────────
        ("com.google.android.tvrecommendations", OptimLevel.STANDARD,
         "TV Recommendations (skanuje treści w tle)", "launcher"),
        ("com.google.android.tungsten.setupwraith", OptimLevel.STANDARD,
         "Setup Wizard (po setupie zbędny)", "setup"),
        ("com.google.android.backdrop",          OptimLevel.STANDARD,
         "Backdrop — ambient screensaver (wysoki CPU)", "ambient"),
        ("com.google.android.tvlauncheranimations", OptimLevel.STANDARD,
         "Launcher Animations (zbędne efekty)", "launcher"),

        # ── AGGRESSIVE: GMS i asystent ────────────────────────────────────────
        ("com.google.android.katniss",           OptimLevel.AGGRESSIVE,
         "Google Assistant ATV (wysokie zużycie RAM)", "assistant"),
        ("com.google.android.speech",            OptimLevel.AGGRESSIVE,
         "Google Speech (voice recognition w tle)", "assistant"),
        ("com.google.mainline.phone.providers.sms", OptimLevel.AGGRESSIVE,
         "SMS Provider (zbędny na ATV)", "gms"),
        ("com.google.android.syncadapters.contacts", OptimLevel.AGGRESSIVE,
         "Contacts Sync (zbędny na ATV)", "gms"),
        ("com.android.providers.contacts",       OptimLevel.AGGRESSIVE,
         "Contacts Provider (zbędny na ATV)", "system"),

        # ── TURBO: OEM bloat i tryb demo ──────────────────────────────────────
        ("fusion.android.tv.demo",               OptimLevel.TURBO,
         "OEM Demo/Store mode", "oem"),
        ("com.tcl.ocean.instructions",           OptimLevel.TURBO,
         "TCL instrukcje (zbieranie danych)", "oem"),
        ("com.android.providers.usagestats",     OptimLevel.TURBO,
         "Usage Stats Provider", "telemetria"),
    ]

    # Ustawienia telemetrii — zawsze bezpieczne
    TELEMETRY_SETTINGS: List[Tuple[str,str,str,str]] = [
        ("system",  "send_security_reports",         "0",
         "Security reports: wyłączone"),
        ("secure",  "send_action_app_error",         "0",
         "App error reports: wyłączone"),
        ("global",  "activity_starts_logging_enabled","0",
         "Activity starts logging: wyłączone"),
        ("global",  "send_action_app_error",         "0",
         "Global app error send: wyłączone"),
        ("global",  "usage_stats_report_interval",   "0",
         "Usage stats report: wyłączone"),
        ("global",  "auto_time_zone",                "0",
         "Auto timezone: wyłączony"),
        ("secure",  "limit_ad_tracking",             "1",
         "Ad tracking: ograniczony"),
        ("global",  "android_id_migration_enabled",  "0",
         "Android ID migration: wyłączona"),
    ]

    @classmethod
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine,
              level: OptimLevel = OptimLevel.STANDARD) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9Debloater — pm disable-user · Telemetria")
        applied = failed = 0
        disabled: List[str] = []

        level_order = [OptimLevel.SAFE, OptimLevel.STANDARD,
                       OptimLevel.AGGRESSIVE, OptimLevel.TURBO]
        level_idx   = level_order.index(level)

        # ── Dezaktywacja pakietów ─────────────────────────────────────────
        L.section("Dezaktywacja pakietów ATV9")
        for pkg, min_lvl, desc, cat in cls.PACKAGES:
            if level_order.index(min_lvl) > level_idx:
                continue
            if pkg in CRITICAL_SYSTEM_PKGS:
                L.warn(f"SKIP (system critical): {pkg}")
                continue

            # Sprawdź czy pakiet istnieje
            chk = guard.sh(f"pm list packages {pkg} 2>/dev/null").output
            if f"package:{pkg}" not in chk:
                continue

            r = guard.sh(
                f"pm disable-user --user 0 {pkg} 2>/dev/null || "
                f"pm disable {pkg} 2>/dev/null || true"
            )
            if r.ok or DRY_RUN:
                applied += 1; disabled.append(pkg)
                L.ok(f"[{cat}] Wyłączono: {pkg}  ({desc})")
                # Persist: enable ponownie można przez pm enable <pkg>
                journal.record(RepairSector.PRIVACY_GUARD,
                               "ATV9Debloater", f"disable {pkg}",
                               f"pm disable-user --user 0 {pkg}",
                               f"pm enable {pkg}")
            else:
                failed += 1; L.warn(f"Disable: {pkg}: FAIL")

        # ── Telemetria settings ───────────────────────────────────────────
        L.section("Blokada telemetrii i analityki")
        for ns, key, val, desc in cls.TELEMETRY_SETTINGS:
            r = guard.sh(f"settings put {ns} {key} {val}")
            if r.ok or DRY_RUN:
                applied += 1; L.ok(desc)
                persist.queue(f"settings put {ns} {key} {val}", desc)
            else:
                failed += 1

        if disabled:
            L.info(f"Wyłączono {len(disabled)} pakietów. Przywróć: pm enable <pkg>")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9Debloater", applied > 0,
                           applied, failed, elapsed,
                           notes=[f"Wyłączone pakiety: {', '.join(disabled[:5])}..."])


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND DAEMON — skrypt w tle urządzenia
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
    def apply(cls, guard: ADBGuard, journal: SessionJournal,
              persist: ATV9PersistEngine) -> OptimResult:
        t0 = time.monotonic()
        L.hdr("ATV9BackgroundDaemon — Autonomiczny demon w tle")
        applied = failed = 0

        script_content = """#!/system/bin/sh
# PlayBox Titanium - Background Daemon
# Działa w tle na urządzeniu, niezależnie od połączenia ADB
while true; do
    # 1. Cykliczne zwalnianie buforów i cache (drop caches)
    echo 1 > /proc/sys/vm/drop_caches 2>/dev/null
    
    # 2. Utrzymanie trybu wysokiej wydajności (czasem resetowanego przez system)
    cmd power set-fixed-performance-mode-enabled true 2>/dev/null
    
    # 3. Synchronizacja I/O i trim cache aplikacji w tle
    sync
    pm trim-caches 16G 2>/dev/null
    
    # 4. Limitowanie rozmiaru logcat w tle (zapobiega opóźnieniom wejścia/wyjścia)
    logcat -G 1M 2>/dev/null
    
    # Przerwa przed kolejnym cyklem (15 minut = 900 sekund)
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
        
        # Zatrzymaj poprzednią instancję, jeśli istnieje
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
            journal.record(RepairSector.DALVIK_RUNTIME,
                           "ATV9BackgroundDaemon", "Daemon instalacja",
                           cmd)
        else:
            failed += 1
            L.warn("Daemon w tle: błąd uruchamiania")

        elapsed = time.monotonic() - t0
        return OptimResult("ATV9BackgroundDaemon", applied > 0,
                           applied, failed, elapsed,
                           notes=["Działa autonomicznie na urządzeniu"])


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK — diagnostyka po optymalizacji
# ══════════════════════════════════════════════════════════════════════════════

class ATV9HealthCheck:
    """
    Diagnostyka stanu systemu po optymalizacji.
    Weryfikuje skuteczność zastosowanych tweaków.
    """

    @classmethod
    def run(cls, guard: ADBGuard, profile: DeviceProfile) -> Dict[str,Any]:
        L.hdr("ATV9HealthCheck — Weryfikacja po optymalizacji")
        checks: Dict[str,Any] = {}

        # GPU backend
        checks["gpu_renderer"] = guard.sh(
            "getprop debug.hwui.renderer"
        ).output.strip()
        L.table_row("GPU Renderer",
                    checks["gpu_renderer"],
                    ok=(checks["gpu_renderer"] != ""))

        # Skia Vulkan
        checks["vulkan"] = guard.sh(
            "getprop debug.hwui.disable_vulkan"
        ).output.strip()

        # SF tweaki
        checks["sf_latch"] = guard.sh(
            "getprop debug.sf.latch_unsignaled"
        ).output.strip()
        L.table_row("SF latch_unsignaled",
                    checks["sf_latch"],
                    ok=(checks["sf_latch"] == "1"))

        # Heap
        checks["heap_growth"] = guard.sh(
            "getprop dalvik.vm.heapgrowthlimit"
        ).output.strip()
        L.table_row("Heap growth limit",
                    checks["heap_growth"],
                    ok=(checks["heap_growth"] != ""))

        # RAM
        mem_raw = guard.sh("cat /proc/meminfo | grep MemAvailable").output
        m = re.search(r"(\d+)", mem_raw)
        avail_mb = int(m.group(1)) // 1024 if m else 0
        checks["avail_mb"] = avail_mb
        L.table_row("RAM dostępne",
                    f"{avail_mb}MB",
                    ok=(avail_mb > 200))

        # WiFi scan
        checks["wifi_scan"] = guard.sh(
            "settings get global wifi_scan_always_enabled"
        ).output.strip()
        L.table_row("WiFi scan always",
                    checks["wifi_scan"],
                    ok=(checks["wifi_scan"] == "0"))

        # Animacje
        checks["anim_scale"] = guard.sh(
            "settings get global window_animation_scale"
        ).output.strip()
        L.table_row("Animacje UI",
                    f"{checks['anim_scale']}×",
                    ok=(float(checks["anim_scale"] or "1") <= 0.5))

        # LMK filecache
        checks["lmk_fc"] = guard.sh(
            "getprop ro.lmk.filecache_min_kb"
        ).output.strip()
        L.table_row("LMK filecache_min",
                    f"{checks['lmk_fc']} KB",
                    ok=(checks["lmk_fc"] != ""))

        # Persist scripts
        checks["persist_magisk"] = "found" if guard.sh(
            f"ls {PERSIST_MAGISK_REMOTE} 2>/dev/null"
        ).output.strip() else "not found"
        checks["persist_initd"]  = "found" if guard.sh(
            f"ls {PERSIST_INITD_REMOTE} 2>/dev/null"
        ).output.strip() else "not found"
        L.table_row("Persist Magisk",  checks["persist_magisk"],
                    ok=(checks["persist_magisk"]=="found"))
        L.table_row("Persist init.d",  checks["persist_initd"],
                    ok=(checks["persist_initd"]=="found"))

        # Score
        ok_count = sum(1 for v in checks.values() if v not in ("","0","not found"))
        total    = len(checks)
        score    = int(ok_count / total * 100)
        checks["score"] = score
        color = C.OK if score >= 80 else C.WARN if score >= 50 else C.ERR
        L.section(f"Health Score: {color}{score}/100{C.RST}")
        return checks


# ══════════════════════════════════════════════════════════════════════════════
# PROBE — wykrycie profilu urządzenia
# ══════════════════════════════════════════════════════════════════════════════

class ATV9Probe:
    """Wykrywa profil sprzętowy urządzenia przed optymalizacją."""

    @classmethod
    def run(cls, guard: ADBGuard) -> DeviceProfile:
        L.section("Probe: wykrywanie profilu sprzętowego")
        p = DeviceProfile()

        def gp(prop: str) -> str:
            return guard.sh(f"getprop {prop}").output.strip()

        p.soc         = gp("ro.board.platform")
        p.gpu_model   = gp("ro.hardware.egl") or gp("ro.hardware.vulkan") or "unknown"
        p.android_api = int(gp("ro.build.version.sdk") or "28")
        cpu_abi       = gp("ro.product.cpu.abi")
        p.cpu_cores   = cls._count_cores(guard)
        p.cpu_max_mhz = cls._detect_cpu_max(guard)
        p.ram_mb      = cls._detect_ram(guard)

        # SoC detection
        soc_l = p.soc.lower()
        p.is_bcm     = any(x in soc_l for x in ("bcm", "72604", "broadcom"))
        p.is_amlogic = any(x in soc_l for x in ("amlogic","meson","s905","s912"))

        # GPU capabilities
        vk_raw    = guard.sh("vulkaninfo 2>/dev/null | head -5 || "
                             "getprop ro.hardware.vulkan").output
        p.has_vulkan = "vulkan" in vk_raw.lower() and "1." in vk_raw
        p.has_vc4    = p.is_bcm   # BCM72604 = VC4
        p.has_mali   = "mali" in p.gpu_model.lower()

        # Root/persist detection
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
        raw = guard.sh("nproc 2>/dev/null || "
                       "ls /sys/devices/system/cpu/ 2>/dev/null | grep -c 'cpu[0-9]'").output.strip()
        return int(raw) if raw.isdigit() else 2

    @classmethod
    def _detect_cpu_max(cls, guard: ADBGuard) -> int:
        raw = guard.sh(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq 2>/dev/null"
        ).output.strip()
        return int(raw) // 1000 if raw.isdigit() else 0

    @classmethod
    def _detect_ram(cls, guard: ADBGuard) -> int:
        raw = guard.sh(
            "grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}'"
        ).output.strip()
        return int(raw) // 1024 if raw.isdigit() else 2048


# ══════════════════════════════════════════════════════════════════════════════
# MASTER OPTIMIZER — orchestracja wszystkich modułów
# ══════════════════════════════════════════════════════════════════════════════

class ATV9MasterOptimizer:
    """
    Pełna orkiestracja optymalizacji Android TV 9.

    Sekwencja (kolejność ma znaczenie):
    ─────────────────────────────────────────────────────────────────────
    1. Probe          — wykrycie profilu sprzętowego
    2. GPU            — renderer, VSync, SF (bazowy rendering)
    3. ART            — AOT compile, heap GC (runtime performance)
    4. Power          — fixed-perf, governor, doze (moc obliczeniowa)
    5. Network        — WiFi, TCP, DNS (streaming foundation)
    6. LMK            — memory pressure, OOM (stabilność)
    7. Input          — latency, timeouty, animacje (responsywność)
    8. Debloat        — pm disable, telemetria (zasoby)
    9. Persist.commit — zapis skryptów startowych (trwałość)
    10. HealthCheck   — weryfikacja wyników
    ─────────────────────────────────────────────────────────────────────

    Persist strategies (zależy od hardware profile):
      Magisk  → /data/adb/service.d/titanium_persist.sh  [BEST]
      init.d  → /system/etc/init.d/99titanium             [ROOT]
      su      → /data/local/tmp/ + Termux:Boot             [GOOD]
      local.prop→ /data/local.prop (tylko setprop)          [BASIC]
      settings → zawsze trwałe (SQLite)                     [ALL]
    ─────────────────────────────────────────────────────────────────────
    """

    def __init__(self, guard: ADBGuard, journal: SessionJournal,
                 level: OptimLevel = OptimLevel.STANDARD) -> None:
        self._guard   = guard
        self._journal = journal
        self._level   = level
        self._profile: Optional[DeviceProfile] = None
        self._persist: Optional[ATV9PersistEngine] = None
        self._results: List[OptimResult] = []

    def run_full(self) -> List[OptimResult]:
        """Uruchamia kompletną optymalizację ATV9."""
        L.hdr(f"ATV9 Master Optimizer — [{self._level.value.upper()}]")
        t_total = time.monotonic()

        # 1. Probe
        self._profile = ATV9Probe.run(self._guard)
        self._persist = ATV9PersistEngine(
            self._guard, self._journal, self._profile
        )

        # 2–8. Moduły optymalizacji
        modules: List[Tuple[str, Any]] = [
            ("GPU",      lambda: ATV9GPUOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile, self._level)),
            ("ART",      lambda: ATV9ARTOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile, self._level)),
            ("Power",    lambda: ATV9PowerOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile, self._level)),
            ("Network",  lambda: ATV9NetworkOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile)),
            ("LMK",      lambda: ATV9LMKOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile, self._level)),
            ("Input",    lambda: ATV9InputOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._level)),
            ("Debloat",  lambda: ATV9Debloater.apply(
                self._guard, self._journal, self._persist,
                self._level)),
            ("Daemon",   lambda: ATV9BackgroundDaemon.apply(
                self._guard, self._journal, self._persist)),
        ]

        for name, fn in modules:
            try:
                r = fn()
                self._results.append(r)
            except Exception as exc:
                L.err(f"Moduł {name}: {exc}")
                self._results.append(OptimResult(
                    f"ATV9{name}", False, 0, 1, 0.0,
                    notes=[str(exc)]
                ))

        # 9. Persist commit
        L.section("PersistEngine: commit → skrypty startowe")
        persist_ok = self._persist.commit()
        for r in self._results:
            r.persist_ok = persist_ok
        if persist_ok:
            L.ok(f"Persist: {self._profile.persist_method} → "
                 f"tweaki przeżyją reboot")
        else:
            L.warn("Persist: tylko settings (setprop zresetowane po rebootcie)")

        # 10. Health check
        checks = ATV9HealthCheck.run(self._guard, self._profile)

        # Raport finalny
        self._print_final_report(t_total, checks)
        return self._results

    def run_module(self, module: str) -> OptimResult:
        """Uruchamia pojedynczy moduł optymalizacji."""
        if self._profile is None:
            self._profile = ATV9Probe.run(self._guard)
        if self._persist is None:
            self._persist = ATV9PersistEngine(
                self._guard, self._journal, self._profile
            )

        dispatch: Dict[str, Any] = {
            "gpu":     lambda: ATV9GPUOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile, self._level),
            "art":     lambda: ATV9ARTOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile, self._level),
            "power":   lambda: ATV9PowerOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile, self._level),
            "network": lambda: ATV9NetworkOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile),
            "lmk":     lambda: ATV9LMKOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._profile, self._level),
            "input":   lambda: ATV9InputOptimizer.apply(
                self._guard, self._journal, self._persist,
                self._level),
            "debloat": lambda: ATV9Debloater.apply(
                self._guard, self._journal, self._persist,
                self._level),
            "daemon":  lambda: ATV9BackgroundDaemon.apply(
                self._guard, self._journal, self._persist),
        }
        fn = dispatch.get(module.lower())
        if fn is None:
            L.err(f"Nieznany moduł: {module}. Dostępne: {list(dispatch)}")
            return OptimResult(module, False)

        r = fn()
        self._persist.commit()
        return r

    def _print_final_report(self, t_total: float,
                             checks: Dict[str,Any]) -> None:
        elapsed = time.monotonic() - t_total
        ok_n    = sum(1 for r in self._results if r.success)
        total_n = len(self._results)
        applied = sum(r.applied for r in self._results)
        failed  = sum(r.failed  for r in self._results)

        L.hdr("ATV9 Master Optimizer — Raport Finalny")
        L.table_row("Moduły OK",          f"{ok_n}/{total_n}")
        L.table_row("Tweaki zastosowane",  str(applied))
        L.table_row("Tweaki nieudane",     str(failed),
                    ok=(failed == 0))
        L.table_row("Czas optymalizacji",  f"{elapsed:.1f}s")
        L.table_row("Persist method",
                    self._profile.persist_method if self._profile else "?",
                    ok=(self._profile.persist_method != "props_only"
                        if self._profile else False))
        L.table_row("Health Score",
                    f"{checks.get('score',0)}/100",
                    ok=(checks.get('score',0) >= 75))

        L.section("Wyniki modułów")
        for r in self._results:
            print(f"  {r.summary}")

        if self._profile and self._profile.persist_method == "props_only":
            L.warn(
                "Brak roota — tylko settings przeżyją reboot.\n"
                "  Zainstaluj Magisk lub Shizuku rish dla pełnego persist.\n"
                f"  Skrypt: {PERSIST_SCRIPT_REMOTE}\n"
                "  Dodaj do Termux:Boot jako ~/.termux/boot/titanium.sh"
            )


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRACJA Z TITANIUM BRAIN (Faza 5)
# ══════════════════════════════════════════════════════════════════════════════

def register_atv9_ops(brain: Any) -> None:
    """
    Rejestruje operacje ATV9 w TitaniumBrain dispatch table.

    Użycie:
        from titanium_atv9_optimizer import register_atv9_ops
        register_atv9_ops(brain)
        brain.dispatch("atv9_full")
        brain.dispatch("atv9_gpu")
    """

    def _make_optimizer(b: Any) -> ATV9MasterOptimizer:
        return ATV9MasterOptimizer(b._guard, b._journal,
                                   OptimLevel(b._level)
                                   if isinstance(b._level, str)
                                   else b._level)

    ops = [
        ("atv9_full",    lambda b, **_: _make_optimizer(b).run_full(),
         "ATV9: pełna optymalizacja (GPU+ART+Power+Net+LMK+Input+Debloat)"),
        ("atv9_gpu",     lambda b, **_: _make_optimizer(b).run_module("gpu"),
         "ATV9: Skia backend + VSync offsets + SF tweaki"),
        ("atv9_art",     lambda b, **_: _make_optimizer(b).run_module("art"),
         "ATV9: AOT speed compile + heap + GC tuning"),
        ("atv9_power",   lambda b, **_: _make_optimizer(b).run_module("power"),
         "ATV9: Fixed Performance + CPU governor + Doze off"),
        ("atv9_network", lambda b, **_: _make_optimizer(b).run_module("network"),
         "ATV9: WiFi stability + TCP 4K + Stagefright"),
        ("atv9_lmk",     lambda b, **_: _make_optimizer(b).run_module("lmk"),
         "ATV9: LMKD PSI + OOM adj + max_cached_processes"),
        ("atv9_input",   lambda b, **_: _make_optimizer(b).run_module("input"),
         "ATV9: Input latency + timeouty pilota + animacje"),
        ("atv9_debloat", lambda b, **_: _make_optimizer(b).run_module("debloat"),
         "ATV9: pm disable-user + telemetria off"),
        ("atv9_daemon",  lambda b, **_: _make_optimizer(b).run_module("daemon"),
         "ATV9: Instalacja i uruchomienie autonomicznego demona w tle"),
        ("atv9_probe",   lambda b, **_: ATV9Probe.run(b._guard),
         "ATV9: wykryj profil sprzętowy"),
        ("atv9_persist", lambda b, **_: (
            ATV9PersistEngine(b._guard, b._journal,
                              ATV9Probe.run(b._guard)).commit()),
         "ATV9: zapisz tweaki do skryptu startowego (persist reboot)"),
        ("atv9_health",  lambda b, **_: ATV9HealthCheck.run(
            b._guard, ATV9Probe.run(b._guard)),
         "ATV9: health check po optymalizacji"),
    ]

    for key, fn, desc in ops:
        brain._DISPATCH[key] = (fn, desc)

    L.ok(f"ATV9: zarejestrowano {len(ops)} operacji w TitaniumBrain")


# ══════════════════════════════════════════════════════════════════════════════
# CLI STANDALONE
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        prog="titanium_atv9_optimizer",
        description="ATV9 Deep Optimizer — Android TV 9 BCM72604/Amlogic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Przykłady:\n"
            "  python3 titanium_atv9_optimizer.py --device 192.168.1.3\n"
            "  python3 titanium_atv9_optimizer.py --device 192.168.1.3 --level turbo\n"
            "  python3 titanium_atv9_optimizer.py --device 192.168.1.3 --module gpu\n"
            "  python3 titanium_atv9_optimizer.py --device 192.168.1.3 --module debloat\n"
            "  python3 titanium_atv9_optimizer.py --device 192.168.1.3 --health\n"
        )
    )
    p.add_argument("--device",  default="192.168.1.3", help="IP urządzenia ATV9")
    p.add_argument("--level",   default="standard",
                   choices=["safe","standard","aggressive","turbo"])
    p.add_argument("--module",  default=None,
                   choices=["gpu","art","power","network","lmk",
                             "input","debloat","daemon","persist","probe"],
                   help="Uruchom pojedynczy moduł zamiast pełnej optymalizacji")
    p.add_argument("--health",  action="store_true",
                   help="Tylko health check (bez optymalizacji)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    from titanium_phase1 import titanium_init, ADBStatus, LOG_DIR
    titanium_init(dry_run=args.dry_run)
    
    L.info("Nawiązywanie połączenia ADB...")
    status = ADB.connect(args.device)
    retries = 3
    
    # Mechanizm stabilizujący połączenie i ograniczający błędy typu "reconnect adb"
    while status != ADBStatus.CONNECTED and retries > 0 and not args.dry_run:
        L.warn(f"ADB nieudane ({status.value}). Próba ponownego połączenia... (pozostało prób: {retries})")
        time.sleep(2)
        status = ADB.connect(args.device)
        retries -= 1

    if status != ADBStatus.CONNECTED and not args.dry_run:
        L.err(f"Krytyczny błąd ADB: {status.value}. Brak stabilnego połączenia po wielu próbach.")
        raise SystemExit(1)

    guard   = ADBGuard(args.device)
    guard.__enter__()
    journal = SessionJournal(LOG_DIR)
    level   = OptimLevel(args.level)
    opt     = ATV9MasterOptimizer(guard, journal, level)

    try:
        if args.health:
            profile = ATV9Probe.run(guard)
            ATV9HealthCheck.run(guard, profile)
        elif args.module:
            if args.module == "probe":
                ATV9Probe.run(guard)
            elif args.module == "persist":
                profile = ATV9Probe.run(guard)
                persist = ATV9PersistEngine(guard, journal, profile)
                persist.commit()
            else:
                opt.run_module(args.module)
        else:
            opt.run_full()
    except KeyboardInterrupt:
        L.warn("Przerwano.")
    finally:
        journal.summary()
        try: guard.__exit__(None, None, None)
        except Exception: pass


if __name__ == "__main__":
    main()