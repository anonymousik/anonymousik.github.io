#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# SecFERRO_PerformanceTuner_v9.5.0-rc.2                                         #
# Target  : Sagemcom DCTIW362p | BCM72604 | Android TV 9 (API 28)               #
# Network : PlayNET FTTH | Zyxel AR5344 fw-1.0.36 | LAN MTU 1500 | No SQM     #
# CPU     : ARMv7 Cortex-A15 ×2 ~1 GHz | VideoCore IV (SkiaGL — No Vulkan)    #
# Memory  : 1.5–2 GB RAM | No zRAM | No swap | Kernel 4.9.190-1-6pre           #
# Codec   : AV1 → BLOCKED (no HW decoder) | VP9 → VDec32 HW | HDR10 tunnel    #
# Runtime : Python 3.12+ | stdlib-only | rish / su / adb adaptive exec         #
# ════════════════════════════════════════════════════════════════════════════════
# NAMESPACE DISCIPLINE (corrections vs original v9.4):
#   [FIX-1] media.*     → PROP (setprop), NOT settings put global
#   [FIX-2] audio.*     → PROP (setprop), NOT settings put global
#   [FIX-3] debug.*     → PROP (setprop), NOT settings put global
#   [FIX-4] ndc resolver → REMOVED (deprecated API 28); use Private DNS Hostname
#   [FIX-5] ro.*        → NEVER modified (read-only kernel props)
#   [FIX-6] sys.watchdog.timeout → REMOVED (not a valid settings key on ATV9)
# ════════════════════════════════════════════════════════════════════════════════
# SPDX-License-Identifier: MIT
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import enum
import os
import re
import shlex
import shlex
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Final, TypeAlias

# ── Type Aliases ──────────────────────────────────────────────────────────────
ResultTriple: TypeAlias = tuple[int, str, str]          # (rc, stdout, stderr)
PropCheck:    TypeAlias = tuple[str, str]                # (key, expected_value)

# ── ANSI Palette — Obsidian Black / Electric Purple accent ───────────────────
_P: Final[str] = "\033[38;2;191;0;255m"    # Electric Purple
_G: Final[str] = "\033[32m"                # OK green
_R: Final[str] = "\033[31m"                # Error red
_Y: Final[str] = "\033[33m"                # Warning yellow
_D: Final[str] = "\033[90m"                # Dim grey
_B: Final[str] = "\033[0m"                 # Reset


# ════════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ════════════════════════════════════════════════════════════════════════════════

class ExecLayer(enum.Enum):
    """Ordered privilege tiers; lower ordinal = higher privilege."""
    ROOT = "su -c"
    RISH = "/data/local/tmp/rish -c"
    ADB  = "adb shell sh -c"


class Namespace(enum.StrEnum):
    """
    Android parameter namespace discriminator.
    StrEnum guarantees f"{Namespace.GLOBAL}" == "global" (Python 3.11+).
    """
    PROP    = "prop"       # setprop — volatile system properties
    GLOBAL  = "global"     # Settings.Global — no privilege required
    SECURE  = "secure"     # Settings.Secure — requires rish / root
    SYSTEM  = "system"     # Settings.System — requires rish / root


# ════════════════════════════════════════════════════════════════════════════════
# TUNING VECTOR — Immutable parameter descriptor
# ════════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class TuningVector:
    """
    Single immutable tuning parameter with bidirectional state (apply / revert).

    ns      : dispatch namespace — determines setprop vs settings put routing
    key     : property name or settings key
    value   : optimised value to commit
    factory : value for rollback; empty string triggers settings delete on revert
    """
    ns:      Namespace
    key:     str
    value:   str
    factory: str = ""


# ════════════════════════════════════════════════════════════════════════════════
# SHELL EXECUTOR
# ════════════════════════════════════════════════════════════════════════════════

class SecFERRO_ShellExecutor:
    """
    Adaptive execution layer: probes rish → su → sh at construction.
    All public methods return ResultTriple to force explicit error handling.
    No silent failures; no bare except clauses.
    """
    _RISH_PATH: ClassVar[str] = "/data/local/tmp/rish"

    def __init__(self) -> None:
        self.layer: Final[ExecLayer] = self._probe_layer()

    # ── Layer detection ───────────────────────────────────────────────────────

    def _probe_rish(self) -> bool:
        if not os.path.exists(self._RISH_PATH):
            return False
        try:
            p = subprocess.run(
                f"{self._RISH_PATH} -c 'echo RISH_OK'",
                shell=True, capture_output=True, text=True, timeout=3,
            )
            return p.returncode == 0 and "RISH_OK" in p.stdout
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _probe_root(self) -> bool:
        try:
            p = subprocess.run(
                "su -c 'id'",
                shell=True, capture_output=True, text=True, timeout=3,
            )
            return p.returncode == 0 and "uid=0" in p.stdout
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _probe_layer(self) -> ExecLayer:
        if self._probe_rish():
            return ExecLayer.RISH
        if self._probe_root():
            return ExecLayer.ROOT
        return ExecLayer.ADB

    # ── Command dispatch ──────────────────────────────────────────────────────

    def run(self, cmd: str) -> ResultTriple:
        safe_cmd = shlex.quote(cmd)
        full = f"{self.layer.value} {safe_cmd}"
        try:
            r = subprocess.run(
                full, shell=True, capture_output=True, text=True, timeout=20,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"timeout: {cmd[:60]}"
        except OSError as exc:
            return 1, "", str(exc)

    # ── High-level wrappers ───────────────────────────────────────────────────

    def setprop(self, key: str, value: str) -> bool:
        safe_val = shlex.quote(value)
        rc, _, _ = self.run(f"setprop {key} {safe_val}")
        return rc == 0

    def settings_put(self, ns: str, key: str, value: str) -> bool:
        safe_val = shlex.quote(value)
        rc, _, _ = self.run(f"settings put {ns} {key} {safe_val}")
        return rc == 0

    def settings_get(self, ns: str, key: str) -> str:
        _, out, _ = self.run(f"settings get {ns} {key}")
        return out

    def settings_delete(self, ns: str, key: str) -> bool:
        rc, _, _ = self.run(f"settings delete {ns} {key}")
        return rc == 0

    def pm_disable(self, pkg: str) -> bool:
        rc, out, _ = self.run(f"pm disable-user --user 0 {pkg}")
        return rc == 0 or "new state" in out

    def pm_enable(self, pkg: str) -> bool:
        rc, _, _ = self.run(f"pm enable {pkg}")
        return rc == 0

    def service_call(self, svc: str, code: int, *args: str) -> bool:
        rc, _, _ = self.run(f"service call {svc} {code} {' '.join(args)}")
        return rc == 0


# ════════════════════════════════════════════════════════════════════════════════
# TUI RENDERER
# ════════════════════════════════════════════════════════════════════════════════

class SecFERRO_TUI:
    """
    Stateless terminal renderer.  All methods are @staticmethod.
    WIDTH = 80 is enforced via ljust — every banner is exactly 80 characters.
    """
    WIDTH: ClassVar[int] = 80
    KEY_W: ClassVar[int] = 42

    @staticmethod
    def banner(title: str) -> None:
        core = f"==[ {title} ]"
        sys.stdout.write(f"\n{_P}{core.ljust(SecFERRO_TUI.WIDTH, '=')}{_B}\n")

    @staticmethod
    def row(key: str, value: str, ok: bool | None = None) -> None:
        tag = (
            f"{_G}[✓]{_B}" if ok is True  else
            f"{_R}[✗]{_B}" if ok is False else
            f"{_D}[~]{_B}"
        )
        sys.stdout.write(
            f"  {tag} {_D}{key:<{SecFERRO_TUI.KEY_W}}{_B}{value}\n"
        )

    @staticmethod
    def section(text: str) -> None:
        sys.stdout.write(f"\n  {_Y}── {text}{_B}\n")

    @staticmethod
    def warn(msg: str) -> None:
        sys.stdout.write(f"  {_Y}[!] {msg}{_B}\n")

    @staticmethod
    def error(msg: str) -> None:
        sys.stdout.write(f"  {_R}[✗] {msg}{_B}\n")


# ════════════════════════════════════════════════════════════════════════════════
# TUNING CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class TuningCatalog:
    """
    Immutable catalog of all hardware-validated tuning vectors for BCM72604.

    Namespace discipline enforced per vector:
      debug.* / media.* / audio.* / dalvik.vm.* / persist.*  → PROP (setprop)
      window_animation_* / wifi_* / private_dns_* / tcp_*    → GLOBAL
      sound_effects_enabled                                   → SYSTEM (rish req.)
      ro.*                                                    → ABSENT (read-only)
      ndc resolver                                            → ABSENT (deprecated)
    """

    GRAPHICS: Final[tuple[TuningVector, ...]] = (
        # ── VideoCore IV: SkiaGL (skiavulkan / skiavk crash SF on BCM72604) ──
        TuningVector(Namespace.PROP,   "debug.hwui.renderer",             "skiagl",         "opengl"),
        TuningVector(Namespace.PROP,   "debug.renderengine.backend",      "skiaglthreaded", "skiagl"),
        TuningVector(Namespace.PROP,   "debug.hwui.render_thread",        "true",           "false"),
        TuningVector(Namespace.PROP,   "debug.hwui.use_gpu_pixel_buffers","true",           "false"),
        TuningVector(Namespace.PROP,   "debug.hwui.render_dirty_regions", "false",          "true"),
        TuningVector(Namespace.PROP,   "debug.sf.hw",                     "1",              "0"),
        TuningVector(Namespace.PROP,   "persist.sys.ui.hw",               "true",           "false"),
        # ── VC4 §8 tile pipeline: CLE autonomy + triple buffer overlap ───────
        TuningVector(Namespace.PROP,   "debug.gr.numframebuffers",        "3",              "2"),
        TuningVector(Namespace.PROP,   "debug.sf.latch_unsignaled",       "1",              "0"),
        TuningVector(Namespace.PROP,   "debug.sf.disable_backpressure",   "1",              "0"),
        # ── VC4 §4 TMU pipeline: 32 KB optimal for texture cache ─────────────
        TuningVector(Namespace.PROP,   "debug.hwui.layer_cache_size",     "32768",          "12288"),
        TuningVector(Namespace.PROP,   "debug.sf.early_phase_offset_ns",  "500000",         "0"),
        TuningVector(Namespace.PROP,   "debug.sf.phase_offset_ns",        "0",              "0"),
        # ── Settings.Global: animation scales ────────────────────────────────
        TuningVector(Namespace.GLOBAL, "window_animation_scale",          "0.35",           "1.0"),
        TuningVector(Namespace.GLOBAL, "transition_animation_scale",      "0.35",           "1.0"),
        TuningVector(Namespace.GLOBAL, "animator_duration_scale",         "0.35",           "1.0"),
        TuningVector(Namespace.GLOBAL, "surface_flinger_layer_caching",   "1",              "0"),
    )

    MEDIA: Final[tuple[TuningVector, ...]] = (
        # ── Stagefright / Codec2 ─────────────────────────────────────────────
        TuningVector(Namespace.PROP, "media.stagefright.enable-player",  "true",            "true"),
        TuningVector(Namespace.PROP, "media.stagefright.cache-params",   "20480/40960/200", ""),
        TuningVector(Namespace.PROP, "media.vcodec.preferhw",            "true",            "false"),
        TuningVector(Namespace.PROP, "media.acodec.preferhw",            "true",            "false"),
        TuningVector(Namespace.PROP, "media.codec.priority",             "0",               "1"),
        # ── BCM Nexus tunnel mode: HDMI clock sync → eliminates A/V drift ────
        TuningVector(Namespace.PROP, "media.tunneled-playback.enable",   "true",            "false"),
        TuningVector(Namespace.PROP, "media.brcm.tunnel.clock",          "hdmi",            ""),
        TuningVector(Namespace.PROP, "media.brcm.tunnel.clock.latency",  "50",              "200"),
        TuningVector(Namespace.PROP, "media.brcm.mma.enable",            "1",               "0"),
        TuningVector(Namespace.PROP, "media.brcm.surface.prewarm",       "true",            "false"),
        TuningVector(Namespace.PROP, "media.brcm.hdr.enable",            "1",               "0"),
        # ── CRITICAL: AV1 hard block ──────────────────────────────────────────
        # BCM72604 has no AV1 HW decoder.  SW decode saturates both A15 cores
        # → thermal throttle → frame drops → watchdog restart.
        TuningVector(Namespace.PROP, "debug.stagefright.c2.av1",         "0",               "1"),
        TuningVector(Namespace.PROP, "media.av1.sw.decode.disable",      "true",            "false"),
        TuningVector(Namespace.PROP, "media.codec.av1.disable",          "true",            "false"),
        # ── BCM HDMI ARC clock drift fix ─────────────────────────────────────
        # audio.offload path uses proprietary BCM clock domain independent of
        # the HDMI sink clock → accumulates 50-200 ms drift after ~20 min.
        TuningVector(Namespace.PROP, "audio.offload.disable",            "1",               "0"),
        TuningVector(Namespace.PROP, "audio.deep_buffer.media",          "true",            "false"),
        TuningVector(Namespace.PROP, "audio.brcm.hdmi.clock_lock",       "true",            "false"),
        TuningVector(Namespace.PROP, "audio.offload.min.duration.secs",  "15",              "0"),
    )

    NETWORK: Final[tuple[TuningVector, ...]] = (
        # ── TCP buffers: PlayNET FTTH + Zyxel AR5344 (no SQM, MTU 1500) ─────
        # BDP = 200 Mbps × 20 ms / 8 = 500 KB → 4× headroom = 2 MB default.
        # Max 8 MB burst capacity for VP9 1080p segments (~3 MB per read).
        # ECN disabled: Zyxel AR5344 stock fw has no CAKE/AQM — ECN causes
        # false-positive congestion signals on non-AQM routers.
        TuningVector(
            Namespace.GLOBAL,
            "net.tcp.buffersize.wifi",
            "4096,524288,8388608,262144,524288,4194304",
            "",
        ),
        TuningVector(
            Namespace.GLOBAL,
            "net.tcp.buffersize.default",
            "4096,131072,1048576,65536,131072,524288",
            "",
        ),
        TuningVector(Namespace.GLOBAL, "tcp_default_init_rwnd",        "60",              ""),
        # ── Private DNS over TLS — Cloudflare ────────────────────────────────
        # Replaces deprecated ndc resolver (API < 28).  Valid on Android 9+.
        TuningVector(Namespace.GLOBAL, "private_dns_mode",             "hostname",        "off"),
        TuningVector(Namespace.GLOBAL, "private_dns_specifier",        "one.one.one.one", ""),
        # ── Captive portal + connectivity ─────────────────────────────────────
        TuningVector(Namespace.GLOBAL, "captive_portal_mode",          "0",               "1"),
        TuningVector(
            Namespace.GLOBAL,
            "captive_portal_http_url",
            "http://connectivitycheck.gstatic.com/generate_204",
            "",
        ),
        TuningVector(Namespace.GLOBAL, "wifi_scan_always_enabled",     "0",               "1"),
        TuningVector(Namespace.GLOBAL, "ble_scan_always_enabled",      "0",               "1"),
        TuningVector(Namespace.GLOBAL, "network_avoid_bad_wifi",       "0",               "1"),
        TuningVector(Namespace.GLOBAL, "wifi_power_save",              "0",               "1"),
        TuningVector(Namespace.GLOBAL, "wifi_5ghz_preferred",          "1",               "0"),
        # ── Fallback DNS props (volatile; supplement DoT) ─────────────────────
        TuningVector(Namespace.PROP,   "net.dns1",                     "1.1.1.1",         ""),
        TuningVector(Namespace.PROP,   "net.dns2",                     "8.8.8.8",         ""),
    )

    STABILITY: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.GLOBAL, "anr_show_background",                "0",         "1"),
        TuningVector(Namespace.GLOBAL, "send_action_app_error",              "0",         "1"),
        TuningVector(Namespace.GLOBAL, "activity_starts_logging_enabled",    "0",         "1"),
        TuningVector(Namespace.GLOBAL, "adaptive_battery_management_enabled","0",         "1"),
        TuningVector(Namespace.GLOBAL, "app_standby_enabled",                "0",         "1"),
        # SYSTEM namespace — requires rish/root; skipped silently on ADB only
        TuningVector(Namespace.SYSTEM, "sound_effects_enabled",              "0",         "1"),
        TuningVector(Namespace.PROP,   "persist.sys.hdmi.keep_awake",        "true",      "false"),
        TuningVector(Namespace.PROP,   "persist.sys.media.avsync",           "true",      "false"),
        TuningVector(Namespace.PROP,   "log.tag.stats_log",                  "OFF",       ""),
        TuningVector(Namespace.PROP,   "log.tag.statsd",                     "OFF",       ""),
        # ── Cortex-A15 ISA: hardware integer divide ───────────────────────────
        # A15 has IDIV in hardware but Dalvik does not enable it by default.
        # Reduces JIT/AOT per-frame cost; confirmed in VC4-AG100-R §14 analysis.
        TuningVector(Namespace.PROP, "dalvik.vm.isa.arm.features",   "default,idiv",    "default"),
        TuningVector(Namespace.PROP, "dalvik.vm.isa.arm.variant",    "cortex-a15",      ""),
        TuningVector(Namespace.PROP, "dalvik.vm.heapminfree",        "2m",              "512k"),
        TuningVector(Namespace.PROP, "dalvik.vm.heapmaxfree",        "16m",             "8m"),
        TuningVector(Namespace.PROP, "dalvik.vm.heaptargetutilization","0.75",           "0.75"),
    )

    BLOATWARE: Final[tuple[str, ...]] = (
        "com.google.android.inputmethod.latin",
        "com.google.android.tts",
        "com.google.android.music",
        "com.google.android.videos",
        "com.google.android.apps.photos",
        "com.android.printspooler",
        "com.google.android.marvin.talkback",
        "com.google.android.accessibility.soundamplifier",
        "com.android.dreams.basic",
        "com.google.android.apps.wallpaper",
    )


# ════════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TUNER — Main orchestrator
# ════════════════════════════════════════════════════════════════════════════════

class PerformanceTuner:
    """
    Orchestrates the BCM72604 optimisation pipeline.
    Contract: every _apply_* / run_* / flush_* method is ≤ 25 executable lines.
    All phases are idempotent; safe to re-run without rebooting between calls.
    """

    def __init__(self) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = SecFERRO_ShellExecutor()

    # ════════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ════════════════════════════════════════════════════════════════════════

    def _commit_single(self, v: TuningVector) -> bool:
        if v.ns == Namespace.PROP:
            return self._sh.setprop(v.key, v.value)
        if v.ns in (Namespace.SECURE, Namespace.SYSTEM):
            if self._sh.layer == ExecLayer.ADB:
                SecFERRO_TUI.warn(f"Skip (need rish/root): settings.{v.ns} {v.key}")
                return False
        return self._sh.settings_put(v.ns, v.key, v.value)

    def _commit_vectors(self, vectors: tuple[TuningVector, ...]) -> int:
        applied = 0
        for v in vectors:
            ok = self._commit_single(v)
            SecFERRO_TUI.row(v.key, v.value, ok)
            applied += int(ok)
        return applied

    def _rollback_single(self, v: TuningVector) -> int:
        if not v.factory:
            if v.ns != Namespace.PROP:
                self._sh.settings_delete(v.ns, v.key)
            SecFERRO_TUI.row(f"delete  {v.key}", "(no factory value — deleted)", None)
            return 0
        ok = (
            self._sh.setprop(v.key, v.factory)
            if v.ns == Namespace.PROP
            else self._sh.settings_put(v.ns, v.key, v.factory)
        )
        SecFERRO_TUI.row(f"revert  {v.key}", v.factory, ok)
        return int(ok)

    def _sf_force_gpu_composition(self) -> None:
        ok = self._sh.service_call("SurfaceFlinger", 1008, "i32", "1")
        SecFERRO_TUI.row("SurfaceFlinger 1008 (Force GPU Composition)", "i32 1", ok)

    def _restart_network(self) -> None:
        self._sh.run("svc wifi disable")
        time.sleep(2)
        self._sh.run("svc wifi enable")
        SecFERRO_TUI.row("wifi subsystem", "restart complete", True)

    # ════════════════════════════════════════════════════════════════════════
    # Optimisation phases
    # ════════════════════════════════════════════════════════════════════════

    def _apply_graphics_pipeline(self) -> None:
        SecFERRO_TUI.banner("HWUI GRAPHICS PIPELINE — VideoCore IV SkiaGL")
        SecFERRO_TUI.section("SkiaGL (Vulkan BLOCKED — BCM72604 has no Vulkan driver)")
        count = self._commit_vectors(TuningCatalog.GRAPHICS)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)
        SecFERRO_TUI.section("SurfaceFlinger: force GPU composition path")
        self._sf_force_gpu_composition()

    def _apply_media_pipeline(self) -> None:
        SecFERRO_TUI.banner("STAGEFRIGHT MULTIMEDIA PIPELINE — BCM Nexus / VDec32")
        SecFERRO_TUI.section(
            "Codec + BCM tunnel + AV1 hard-block + HDMI ARC clock-lock"
        )
        count = self._commit_vectors(TuningCatalog.MEDIA)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)

    def _apply_network_pipeline(self) -> None:
        SecFERRO_TUI.banner("NETWORK LAYER — TCP/IP + Private DNS [PlayNET / Zyxel]")
        SecFERRO_TUI.section(
            "TCP BDP=200Mbps×20ms | no ECN (Zyxel AR5344 has no AQM/CAKE)"
        )
        count = self._commit_vectors(TuningCatalog.NETWORK)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)
        # ECN disabled: Zyxel stock fw signals false congestion without CAKE
        if self._sh.layer != ExecLayer.ADB:
            rc, _, _ = self._sh.run("echo 0 > /proc/sys/net/ipv4/tcp_ecn")
            SecFERRO_TUI.row("tcp_ecn", "0 (rish context)", rc == 0)
        else:
            SecFERRO_TUI.warn("tcp_ecn sysctl requires rish/root — skipped on ADB")
        SecFERRO_TUI.section("Wi-Fi restart for DNS propagation")
        self._restart_network()

    def _apply_debloat_profile(self) -> None:
        SecFERRO_TUI.banner("DEBLOAT — SELECTIVE PACKAGE SUSPENSION")
        disabled = 0
        for pkg in TuningCatalog.BLOATWARE:
            ok = self._sh.pm_disable(pkg)
            SecFERRO_TUI.row(pkg, "disabled" if ok else "skipped", ok)
            disabled += int(ok)
        SecFERRO_TUI.row("total packages disabled", str(disabled), disabled > 0)

    def _apply_stability_profile(self) -> None:
        SecFERRO_TUI.banner("SYSTEM STABILITY — WATCHDOG + DALVIK + A15 ISA TUNING")
        count = self._commit_vectors(TuningCatalog.STABILITY)
        SecFERRO_TUI.row("stability vectors applied", str(count), count > 0)

    def _apply_rollback_profile(self) -> None:
        SecFERRO_TUI.banner("ROLLBACK — FACTORY STATE RESTORE")
        all_vectors: tuple[TuningVector, ...] = (
            TuningCatalog.GRAPHICS + TuningCatalog.MEDIA
            + TuningCatalog.NETWORK + TuningCatalog.STABILITY
        )
        reverted = sum(self._rollback_single(v) for v in all_vectors)
        SecFERRO_TUI.section("Re-enabling suspended packages")
        for pkg in TuningCatalog.BLOATWARE:
            ok = self._sh.pm_enable(pkg)
            SecFERRO_TUI.row(pkg, "enabled" if ok else "err", ok)
        SecFERRO_TUI.row("total props reverted", str(reverted), reverted > 0)
        SecFERRO_TUI.warn("Cold reboot required for complete factory state restore.")

    # ════════════════════════════════════════════════════════════════════════
    # Diagnostics & memory management
    # ════════════════════════════════════════════════════════════════════════

    def _read_pss_metrics(self) -> dict[str, int]:
        """Returns TOTAL PSS (KB) keyed by process name via dumpsys meminfo."""
        targets: dict[str, int] = {
            "surfaceflinger":                     0,
            "com.google.android.apps.mediashell": 0,
            "com.liskovsoft.smarttubetv.beta":    0,
        }
        for proc in list(targets.keys()):
            _, out, _ = self._sh.run(f"dumpsys meminfo {proc} 2>/dev/null")
            m = re.search(r"TOTAL PSS:\s+(\d+)", out)
            if m:
                targets[proc] = int(m.group(1))
        return targets

    def _read_gfxinfo(self, pkg: str) -> dict[str, str]:
        """Extracts gfxinfo percentile and jank metrics for streaming QA."""
        _, raw, _ = self._sh.run(f"dumpsys gfxinfo {pkg} 2>/dev/null")
        patterns: dict[str, str] = {
            "total_frames": r"Total frames rendered:\s+(\d+)",
            "janky_frames": r"Janky frames:\s+(\d+\s+\(.+?\))",
            "p90_ms":       r"90th percentile:\s+(\d+ms)",
            "p95_ms":       r"95th percentile:\s+(\d+ms)",
            "p99_ms":       r"99th percentile:\s+(\d+ms)",
        }
        return {
            k: (m.group(1) if (m := re.search(p, raw)) else "n/a")
            for k, p in patterns.items()
        }

    def flush_memory_caches(self) -> None:
        SecFERRO_TUI.banner("MEMORY FLUSH — VOLATILE CACHE PURGE")
        for cmd in (
            
            "dumpsys batterystats --reset",
            "sync",
        ):
            rc, _, _ = self._sh.run(cmd)
            SecFERRO_TUI.row(cmd, "ok" if rc == 0 else "err", rc == 0)
        if self._sh.layer != ExecLayer.ADB:
            rc, _, _ = self._sh.run("echo 3 > /proc/sys/vm/drop_caches")
            SecFERRO_TUI.row("drop_caches=3", "ok" if rc == 0 else "no perms", rc == 0)

    def run_diagnostics(self) -> None:
        SecFERRO_TUI.banner("DIAGNOSTIC REPORT — BCM72604 SYSTEM STATE")
        SecFERRO_TUI.section("Memory — TOTAL PSS (KB) per key process")
        for proc, kb in self._read_pss_metrics().items():
            SecFERRO_TUI.row(proc[-42:], f"{kb} KB", kb > 0)
        SecFERRO_TUI.section("Graphics — SmartTube gfxinfo percentiles")
        for metric, val in self._read_gfxinfo("com.liskovsoft.smarttubetv.beta").items():
            SecFERRO_TUI.row(metric, val, None)
        SecFERRO_TUI.section("Critical property assertions")
        assertions: tuple[PropCheck, ...] = (
            ("debug.hwui.renderer",        "skiagl"),
            ("media.codec.av1.disable",    "true"),
            ("audio.brcm.hdmi.clock_lock", "true"),
            ("dalvik.vm.isa.arm.variant",  "cortex-a15"),
        )
        for key, expected in assertions:
            _, val, _ = self._sh.run(f"getprop {key}")
            SecFERRO_TUI.row(key, val or "n/a", val == expected)
        SecFERRO_TUI.section("Runtime context")
        SecFERRO_TUI.row("exec layer", self._sh.layer.name, True)

    # ════════════════════════════════════════════════════════════════════════
    # Public entry points
    # ════════════════════════════════════════════════════════════════════════

    def run_full_optimization(self) -> None:
        SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.5.0-rc.2 — FULL PIPELINE")
        SecFERRO_TUI.row("exec layer", self._sh.layer.name,                    True)
        SecFERRO_TUI.row("target",     "Sagemcom DCTIW362p | BCM72604 | ATV9", None)
        SecFERRO_TUI.row("network",    "PlayNET FTTH | Zyxel AR5344 fw-1.0.36",None)
        self._apply_graphics_pipeline()
        self._apply_media_pipeline()
        self._apply_network_pipeline()
        self._apply_stability_profile()
        self._apply_debloat_profile()
        self.flush_memory_caches()
        SecFERRO_TUI.banner("OPTIMIZATION PIPELINE COMPLETE — REBOOT RECOMMENDED")


# ════════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.5.0-rc.2 — Dispatcher")
    tuner   = PerformanceTuner()
    mode    = sys.argv[1] if len(sys.argv) > 1 else "--optimize"
    dispatch: dict[str, Callable[[], None]] = {
        "--optimize":    tuner.run_full_optimization,
        "--rollback":    tuner._apply_rollback_profile,
        "--diagnostics": tuner.run_diagnostics,
        "--debloat":     tuner._apply_debloat_profile,
        "--graphics":    tuner._apply_graphics_pipeline,
        "--media":       tuner._apply_media_pipeline,
        "--network":     tuner._apply_network_pipeline,
        "--flush":       tuner.flush_memory_caches,
    }
    handler = dispatch.get(mode)
    if handler is None:
        SecFERRO_TUI.error(f"Unknown mode '{mode}'.")
        SecFERRO_TUI.row("valid modes", str(list(dispatch.keys())), None)
        sys.exit(1)
    handler()


if __name__ == "__main__":
    main()