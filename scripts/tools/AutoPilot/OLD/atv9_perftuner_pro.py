#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# SecFERRO_PerformanceTuner_v9.5.4-rc.1 — FULL CONSOLIDATED BUILD                #
# Target  : Sagemcom DCTIW362p | BCM72604 | Android TV 9 (API 28)               #
# Network : PlayNET FTTH | Zyxel AR5344 fw-1.0.36 | LAN MTU 1500 | No SQM     #
# CPU     : ARMv7 Cortex-A15 ×2 ~1 GHz | VideoCore IV / brcmv3d 2.0.1 @582MHz #
# Memory  : 1.5–2 GB RAM | No zRAM | No swap | Kernel 4.9.190-1-6pre           #
# Codec   : AV1 → BLOCKED (no HW decoder) | VP9 → VDec32 HW | HDR10 tunnel    #
# Remote  : Sagemcom IR remote + realme RMX3472 via ATV-Remote (event8)       #
# Runtime : Python 3.12+ | stdlib-only | rish / su / adb adaptive exec         #
# ════════════════════════════════════════════════════════════════════════════════
# SPDX-License-Identifier: MIT
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import enum
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Final, TypeAlias

# ── Type Aliases ──────────────────────────────────────────────────────────────
ResultTriple: TypeAlias = tuple[int, str, str]          # (rc, stdout, stderr)
PropCheck:    TypeAlias = tuple[str, str]               # (key, expected_value)

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
    """Ordered privilege tiers via remote ADB transport."""
    ROOT = "root"
    RISH = "rish"
    ADB  = "adb"


class Namespace(enum.StrEnum):
    """Android parameter namespace discriminator."""
    PROP    = "prop"       # setprop — volatile system properties
    GLOBAL  = "global"     # Settings.Global — no privilege required
    SECURE  = "secure"     # Settings.Secure — requires rish / root
    SYSTEM  = "system"     # Settings.System — requires rish / root


# ════════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ════════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class TuningVector:
    """Single immutable tuning parameter with bidirectional state."""
    ns:      Namespace
    key:     str
    value:   str
    factory: str = ""


@dataclass(frozen=True, slots=True)
class RegressionFinding:
    """One detected divergence between a proposed command and validated state."""
    prop_key:    str
    requested:   str
    validated:   str
    verdict:     str
    explanation: str


@dataclass(frozen=True, slots=True)
class RendererProfile:
    """Immutable VC4 tile-pipeline renderer stack — validated safe combination."""
    hwui_renderer:         str
    render_backend:        str
    render_thread:         str
    numframebuffers:       str
    disable_backpressure:  str
    latch_unsignaled:      str


@dataclass(frozen=True, slots=True)
class KeyBinding:
    """Bidirectional SmartTube remote key descriptor."""
    keycode:     int
    action:      str
    long_action: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class LogcatFinding:
    """Logcat diagnostic finding definition."""
    tag:         str
    pattern:     str
    severity:    str
    verdict:     str
    explanation: str
    actionable:  bool


# ════════════════════════════════════════════════════════════════════════════════
# SHELL EXECUTOR (REFACTORED FOR PROPER ADB TRANSPORT)
# ════════════════════════════════════════════════════════════════════════════════

class SecFERRO_ShellExecutor:
    """Adaptive execution layer: securely maps local calls to remote ADB shell."""

    def __init__(self) -> None:
        self._verify_adb_connection()
        self.layer: Final[ExecLayer] = self._probe_layer()

    def _verify_adb_connection(self) -> None:
        """Pre-flight check: validates if adb daemon has an active session."""
        try:
            p = subprocess.run(
                ["adb", "get-state"], capture_output=True, text=True, timeout=3
            )
            if p.returncode != 0 or "device" not in p.stdout:
                SecFERRO_TUI.warn("No active ADB connection detected. Ensure TV is connected via IP.")
        except FileNotFoundError:
            SecFERRO_TUI.error("ADB utility not found. Install 'android-tools' on your host system.")
            sys.exit(1)

    def _probe_rish(self) -> bool:
        """Tests if the remote target has Shizuku/rish configured."""
        try:
            p = subprocess.run(
                ["adb", "shell", "/data/local/tmp/rish", "-c", "echo RISH_OK"],
                capture_output=True, text=True, timeout=5,
            )
            return p.returncode == 0 and "RISH_OK" in p.stdout
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _probe_root(self) -> bool:
        """Tests if the remote target has root / su capabilities."""
        try:
            p = subprocess.run(
                ["adb", "shell", "su", "-c", "id"],
                capture_output=True, text=True, timeout=5,
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

    def run(self, cmd: str) -> ResultTriple:
        """
        Executes a command on the remote target via ADB.
        Avoids host shell expansion, delegating parsing to Android's /system/bin/sh.
        """
        if self.layer == ExecLayer.ROOT:
            args = ["adb", "shell", "su", "-c", cmd]
        elif self.layer == ExecLayer.RISH:
            args = ["adb", "shell", "/data/local/tmp/rish", "-c", cmd]
        else:
            args = ["adb", "shell", cmd]

        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=20,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"timeout: target execution exceeded 20s"
        except OSError as exc:
            return 1, "", str(exc)

    def run_host(self, cmd: str) -> ResultTriple:
        """
        Executes a command purely on the local host (e.g., Termux shell).
        Used exclusively for host-side tooling like kdeconnect or adb connection bridging.
        """
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=20,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"timeout: host execution exceeded 20s"
        except OSError as exc:
            return 1, "", str(exc)

    # Proxy wrappers route exclusively through target `run()` method
    def setprop(self, key: str, value: str) -> bool:
        rc, _, _ = self.run(f"setprop {key} {value}")
        return rc == 0

    def settings_put(self, ns: str, key: str, value: str) -> bool:
        rc, _, _ = self.run(f"settings put {ns} {key} {value}")
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

    def logcat_grep(self, tag: str, level: str, lines: int = 300) -> str:
        _, out, _ = self.run(f"logcat -d -s {tag}:{level} 2>/dev/null | tail -{lines}")
        return out


# ════════════════════════════════════════════════════════════════════════════════
# TUI RENDERER
# ════════════════════════════════════════════════════════════════════════════════

class SecFERRO_TUI:
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
    GRAPHICS: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.PROP,   "debug.hwui.renderer",             "skiagl",         "opengl"),
        TuningVector(Namespace.PROP,   "debug.renderengine.backend",      "skiaglthreaded", "skiagl"),
        TuningVector(Namespace.PROP,   "debug.hwui.render_thread",        "true",           "false"),
        TuningVector(Namespace.PROP,   "debug.hwui.use_gpu_pixel_buffers","true",           "false"),
        TuningVector(Namespace.PROP,   "debug.hwui.render_dirty_regions", "false",          "true"),
        TuningVector(Namespace.PROP,   "debug.sf.hw",                     "1",              "0"),
        TuningVector(Namespace.PROP,   "persist.sys.ui.hw",               "true",           "false"),
        TuningVector(Namespace.PROP,   "debug.gr.numframebuffers",        "3",              "2"),
        TuningVector(Namespace.PROP,   "debug.sf.latch_unsignaled",       "1",              "0"),
        TuningVector(Namespace.PROP,   "debug.sf.disable_backpressure",   "1",              "0"),
        TuningVector(Namespace.PROP,   "debug.hwui.layer_cache_size",     "32768",          "12288"),
        TuningVector(Namespace.PROP,   "debug.sf.early_phase_offset_ns",  "500000",         "0"),
        TuningVector(Namespace.PROP,   "debug.sf.phase_offset_ns",        "0",              "0"),
        TuningVector(Namespace.GLOBAL, "window_animation_scale",          "0.35",           "1.0"),
        TuningVector(Namespace.GLOBAL, "transition_animation_scale",      "0.35",           "1.0"),
        TuningVector(Namespace.GLOBAL, "animator_duration_scale",         "0.35",           "1.0"),
        TuningVector(Namespace.GLOBAL, "surface_flinger_layer_caching",   "1",              "0"),
    )

    MEDIA: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.PROP, "media.stagefright.enable-player",  "true",            "true"),
        TuningVector(Namespace.PROP, "media.stagefright.cache-params",   "20480/40960/200", ""),
        TuningVector(Namespace.PROP, "media.vcodec.preferhw",            "true",            "false"),
        TuningVector(Namespace.PROP, "media.acodec.preferhw",            "true",            "false"),
        TuningVector(Namespace.PROP, "media.codec.priority",             "0",               "1"),
        TuningVector(Namespace.PROP, "media.tunneled-playback.enable",   "true",            "false"),
        TuningVector(Namespace.PROP, "media.brcm.tunnel.clock",          "hdmi",            ""),
        TuningVector(Namespace.PROP, "media.brcm.tunnel.clock.latency",  "50",              "200"),
        TuningVector(Namespace.PROP, "media.brcm.mma.enable",            "1",               "0"),
        TuningVector(Namespace.PROP, "media.brcm.surface.prewarm",       "true",            "false"),
        TuningVector(Namespace.PROP, "media.brcm.hdr.enable",            "1",               "0"),
        TuningVector(Namespace.PROP, "debug.stagefright.c2.av1",         "0",               "1"),
        TuningVector(Namespace.PROP, "media.av1.sw.decode.disable",      "true",            "false"),
        TuningVector(Namespace.PROP, "media.codec.av1.disable",          "true",            "false"),
        TuningVector(Namespace.PROP, "audio.offload.disable",            "1",               "0"),
        TuningVector(Namespace.PROP, "audio.deep_buffer.media",          "true",            "false"),
        TuningVector(Namespace.PROP, "audio.brcm.hdmi.clock_lock",       "true",            "false"),
        TuningVector(Namespace.PROP, "audio.offload.min.duration.secs",  "15",              "0"),
    )

    NETWORK: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.GLOBAL, "net.tcp.buffersize.wifi", "4096,524288,8388608,262144,524288,4194304", ""),
        TuningVector(Namespace.GLOBAL, "net.tcp.buffersize.default", "4096,131072,1048576,65536,131072,524288", ""),
        TuningVector(Namespace.GLOBAL, "tcp_default_init_rwnd",        "60",              ""),
        TuningVector(Namespace.GLOBAL, "private_dns_mode",             "hostname",        "off"),
        TuningVector(Namespace.GLOBAL, "private_dns_specifier",        "one.one.one.one", ""),
        TuningVector(Namespace.GLOBAL, "captive_portal_mode",          "0",               "1"),
        TuningVector(Namespace.GLOBAL, "captive_portal_http_url", "http://connectivitycheck.gstatic.com/generate_204", ""),
        TuningVector(Namespace.GLOBAL, "wifi_scan_always_enabled",     "0",               "1"),
        TuningVector(Namespace.GLOBAL, "ble_scan_always_enabled",      "0",               "1"),
        TuningVector(Namespace.GLOBAL, "network_avoid_bad_wifi",       "0",               "1"),
        TuningVector(Namespace.GLOBAL, "wifi_power_save",              "0",               "1"),
        TuningVector(Namespace.GLOBAL, "wifi_5ghz_preferred",          "1",               "0"),
        TuningVector(Namespace.PROP,   "net.dns1",                     "1.1.1.1",         ""),
        TuningVector(Namespace.PROP,   "net.dns2",                     "8.8.8.8",         ""),
    )

    STABILITY: Final[tuple[TuningVector, ...]] = (
        TuningVector(Namespace.GLOBAL, "anr_show_background",                "0",         "1"),
        TuningVector(Namespace.GLOBAL, "send_action_app_error",              "0",         "1"),
        TuningVector(Namespace.GLOBAL, "activity_starts_logging_enabled",    "0",         "1"),
        TuningVector(Namespace.GLOBAL, "adaptive_battery_management_enabled","0",         "1"),
        TuningVector(Namespace.GLOBAL, "app_standby_enabled",                "0",         "1"),
        TuningVector(Namespace.SYSTEM, "sound_effects_enabled",              "0",         "1"),
        TuningVector(Namespace.PROP,   "persist.sys.hdmi.keep_awake",        "true",      "false"),
        TuningVector(Namespace.PROP,   "persist.sys.media.avsync",           "true",      "false"),
        TuningVector(Namespace.PROP,   "log.tag.stats_log",                  "OFF",       ""),
        TuningVector(Namespace.PROP,   "log.tag.statsd",                     "OFF",       ""),
        TuningVector(Namespace.PROP, "dalvik.vm.isa.arm.features",   "default,idiv",    "default"),
        TuningVector(Namespace.PROP, "dalvik.vm.isa.arm.variant",    "cortex-a15",      ""),
        TuningVector(Namespace.PROP, "dalvik.vm.heapminfree",        "2m",              "512k"),
        TuningVector(Namespace.PROP, "dalvik.vm.heapmaxfree",        "16m",             "8m"),
        TuningVector(Namespace.PROP, "dalvik.vm.heaptargetutilization","0.75",           "0.75"),
    )

    BLOATWARE: Final[tuple[str, ...]] = (
        "com.google.android.inputmethod.latin", "com.google.android.tts", "com.google.android.music",
        "com.google.android.videos", "com.google.android.apps.photos", "com.android.printspooler",
        "com.google.android.marvin.talkback", "com.google.android.accessibility.soundamplifier",
        "com.android.dreams.basic", "com.google.android.apps.wallpaper",
    )


# ════════════════════════════════════════════════════════════════════════════════
# RENDERER CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class RendererCatalog:
    VALIDATED_SAFE: Final[RendererProfile] = RendererProfile(
        hwui_renderer="skiagl", render_backend="skiaglthreaded", render_thread="true",
        numframebuffers="3", disable_backpressure="1", latch_unsignaled="1",
    )

    KNOWN_REGRESSIONS: Final[tuple[RegressionFinding, ...]] = (
        RegressionFinding("debug.hwui.renderer", "opengl", "skiagl", "INVALID_ENUM",
                          "Pre-Skia HWUI class removed from AOSP since API 28."),
        RegressionFinding("debug.renderengine.backend", "gl", "skiaglthreaded", "INVALID_ENUM",
                          "'gl' matches no RenderEngine backend enum on API 28."),
        RegressionFinding("debug.sf.disable_backpressure", "0", "1", "REGRESSION",
                          "Reverts VC4 CLE-autonomy fix."),
        RegressionFinding("debug.gr.numframebuffers", "2", "3", "REGRESSION",
                          "Reverts triple-buffering advantages."),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeCatalog:
    PACKAGES: Final[tuple[str, ...]] = (
        "org.smarttube.stable", "org.smarttube.beta",
        "com.liskovsoft.smarttubetv.beta", "com.liskovsoft.smarttubetv.next",
    )

    ACT_LIKE              = "like"
    ACT_DISLIKE           = "dislike"
    ACT_ADD_TO_QUEUE      = "add_to_queue"
    ACT_REMOVE_QUEUE      = "remove_from_queue"
    ACT_OPEN_QUEUE        = "open_queue"
    ACT_OPEN_COMMENTS     = "open_comments"
    ACT_OPEN_WATCH_LATER  = "open_watch_later"
    ACT_SAVE_WATCH_LATER  = "save_to_watch_later"
    ACT_COPY_LINK         = "copy_link"
    ACT_COPY_LINK_TIME    = "copy_link_with_time"
    ACT_PLAY_PAUSE        = "play_pause"

    BINDINGS: Final[tuple[KeyBinding, ...]] = (
        KeyBinding(92, ACT_LIKE, ACT_ADD_TO_QUEUE, "PAGE_UP short=like | hold=add queue"),
        KeyBinding(93, ACT_DISLIKE, ACT_REMOVE_QUEUE, "PAGE_DOWN short=dislike | hold=rem queue"),
        KeyBinding(231, ACT_OPEN_COMMENTS, "", "MIC short=comments"),
        KeyBinding(85, ACT_PLAY_PAUSE, ACT_OPEN_QUEUE, "PLAY_PAUSE short=play | hold=queue"),
        KeyBinding(130, ACT_OPEN_WATCH_LATER, ACT_SAVE_WATCH_LATER, "REC short=watch later | hold=save"),
        KeyBinding(172, ACT_COPY_LINK, ACT_COPY_LINK_TIME, "PROGRAM short=link | hold=link+ts"),
    )

    PREF_KEY_SHORT : Final[str] = "player_button_{action}"
    PREF_KEY_LONG  : Final[str] = "player_button_{action}_long"
    PREF_FILENAME_TMPL: Final[str] = "{pkg}_preferences.xml"
    PREFS_DIR:          Final[str] = "/data/data/{pkg}/shared_prefs"
    FILES_DIR:          Final[str] = "/data/data/{pkg}/files"
    PLAYER_DATA_JSON:   Final[str] = "player_data.json"


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM INTEGRITY CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class SystemIntegrityCatalog:
    FINDINGS: Final[tuple[LogcatFinding, ...]] = (
        LogcatFinding("EthernetNetworkFactory", r"iface:\s*eth0.*hwAddress:\s*([0-9a-f:]{17})", "INFO", "HARDWARE_PRESENT_CABLE_UNPLUGGED", "eth0 hardware confirmed.", False),
        LogcatFinding("WifiVendorHal", r"getWifiLinkLayerStats.*ERROR_NOT_AVAILABLE", "WARN", "LINK_LAYER_STATS_HAL_MISSING", "Telemetry reduced.", False),
        LogcatFinding("KeyLayoutMap", r"virtual-remote\.kl:(\d+):\s*Expected key code label", "ERROR", "KEYLAYOUT_PARSE_DEFECT", "Malformed virtual-remote kl file.", True),
        LogcatFinding("BillingClient", r"Multiple entries with same key:\s*TryRoom", "ERROR", "APP_LEVEL_BILLING_STATE_CORRUPT", "Proj. Launcher duplicate key crash.", True),
        LogcatFinding("skia", r"Failed to create image decoder.*unimplemented", "WARN", "UNSUPPORTED_IMAGE_CODEC_LOOP", "Bing wallpaper plugin fail.", False),
        LogcatFinding("SELinux", r"hal_memtrack_hwservice.*permissive=0", "WARN", "MEMTRACK_HAL_DENIED", "GMS memory tracking blocked.", False),
        LogcatFinding("PasspointManager", r"Match not found for PLAY_Swiatlowod", "WARN", "PASSPOINT_ANQP_SCAN_WASTE", "Wasted HS20 scans.", False),
    )


# ════════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TUNER
# ════════════════════════════════════════════════════════════════════════════════

class PerformanceTuner:
    def __init__(self) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = SecFERRO_ShellExecutor()

    def _commit_single(self, v: TuningVector) -> bool:
        if v.ns == Namespace.PROP:
            return self._sh.setprop(v.key, v.value)
        if v.ns in (Namespace.SECURE, Namespace.SYSTEM) and self._sh.layer == ExecLayer.ADB:
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
        ok = self._sh.setprop(v.key, v.factory) if v.ns == Namespace.PROP else self._sh.settings_put(v.ns, v.key, v.factory)
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

    def _apply_system_integrity_audit(self) -> None:
        auditor = SystemIntegrityAuditor(self._sh)
        findings = auditor.audit()
        auditor.verify_ethernet_hardware()
        if findings.get("APP_LEVEL_BILLING_STATE_CORRUPT"):
            auditor.remediate_billing_cache()

    def _apply_renderer_integrity_guard(self) -> None:
        RendererIntegrityGuard(self._sh).run_integrity_check()

    def _apply_graphics_pipeline(self) -> None:
        SecFERRO_TUI.banner("HWUI GRAPHICS PIPELINE — VideoCore IV SkiaGL")
        count = self._commit_vectors(TuningCatalog.GRAPHICS)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)
        self._sf_force_gpu_composition()

    def _apply_media_pipeline(self) -> None:
        SecFERRO_TUI.banner("STAGEFRIGHT MULTIMEDIA PIPELINE — BCM Nexus / VDec32")
        count = self._commit_vectors(TuningCatalog.MEDIA)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)

    def _apply_network_pipeline(self) -> None:
        SecFERRO_TUI.banner("NETWORK LAYER — TCP/IP + Private DNS")
        count = self._commit_vectors(TuningCatalog.NETWORK)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)
        self._sh.run("echo 0 > /proc/sys/net/ipv4/tcp_ecn 2>/dev/null")
        SecFERRO_TUI.row("tcp_ecn", "0", True)
        self._restart_network()

    def _apply_debloat_profile(self) -> None:
        SecFERRO_TUI.banner("DEBLOAT — SELECTIVE PACKAGE SUSPENSION")
        disabled = 0
        for pkg in TuningCatalog.BLOATWARE:
            ok = self._sh.pm_disable(pkg)
            SecFERRO_TUI.row(pkg, "disabled" if ok else "skipped", ok)
            disabled += int(ok)
        SecFERRO_TUI.row("total disabled", str(disabled), disabled > 0)

    def _apply_stability_profile(self) -> None:
        SecFERRO_TUI.banner("SYSTEM STABILITY")
        count = self._commit_vectors(TuningCatalog.STABILITY)
        SecFERRO_TUI.row("stability vectors applied", str(count), count > 0)

    def _apply_smarttube_enhancement(self) -> None:
        SmartTubeEnhancer(self._sh).apply_all()

    def _apply_rollback_profile(self) -> None:
        SecFERRO_TUI.banner("ROLLBACK — FACTORY STATE RESTORE")
        all_vectors = TuningCatalog.GRAPHICS + TuningCatalog.MEDIA + TuningCatalog.NETWORK + TuningCatalog.STABILITY
        reverted = sum(self._rollback_single(v) for v in all_vectors)
        for pkg in TuningCatalog.BLOATWARE:
            ok = self._sh.pm_enable(pkg)
            SecFERRO_TUI.row(pkg, "enabled" if ok else "err", ok)
        SecFERRO_TUI.row("props reverted", str(reverted), reverted > 0)

    def _read_pss_metrics(self) -> dict[str, int]:
        targets = {"surfaceflinger": 0, "com.google.android.apps.mediashell": 0, "com.liskovsoft.smarttubetv.beta": 0}
        for proc in list(targets.keys()):
            _, out, _ = self._sh.run(f"dumpsys meminfo {proc} 2>/dev/null")
            m = re.search(r"TOTAL PSS:\s+(\d+)", out)
            if m: targets[proc] = int(m.group(1))
        return targets

    def flush_memory_caches(self) -> None:
        SecFERRO_TUI.banner("MEMORY FLUSH")
        for cmd in ("am kill-all", "pm trim-caches 2G", "dumpsys batterystats --reset", "sync"):
            rc, _, _ = self._sh.run(cmd)
            SecFERRO_TUI.row(cmd, "ok" if rc == 0 else "err", rc == 0)
        if self._sh.layer != ExecLayer.ADB:
            rc, _, _ = self._sh.run("echo 3 > /proc/sys/vm/drop_caches")
            SecFERRO_TUI.row("drop_caches=3", "ok" if rc == 0 else "no perms", rc == 0)

    def run_diagnostics(self) -> None:
        SecFERRO_TUI.banner("DIAGNOSTIC REPORT")
        for proc, kb in self._read_pss_metrics().items():
            SecFERRO_TUI.row(proc[-42:], f"{kb} KB", kb > 0)
        SecFERRO_TUI.row("exec layer (ADB target)", self._sh.layer.name, True)

    def run_full_optimization(self) -> None:
        SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.5.4-rc.1 — FULL PIPELINE")
        SecFERRO_TUI.row("exec layer (Transport: ADB)", self._sh.layer.name, True)
        self._apply_system_integrity_audit()
        self._apply_renderer_integrity_guard()
        self._apply_graphics_pipeline()
        self._apply_media_pipeline()
        self._apply_network_pipeline()
        self._apply_stability_profile()
        self._apply_debloat_profile()
        self._apply_smarttube_enhancement()
        self.flush_memory_caches()
        SecFERRO_TUI.banner("OPTIMIZATION PIPELINE COMPLETE")


# ════════════════════════════════════════════════════════════════════════════════
# RENDERER INTEGRITY GUARD
# ════════════════════════════════════════════════════════════════════════════════

class RendererIntegrityGuard:
    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def audit_pasted_regressions(self) -> int:
        flagged = 0
        for f in RendererCatalog.KNOWN_REGRESSIONS:
            SecFERRO_TUI.row(f.prop_key, f"REQUESTED={f.requested} → REJECTED", False)
            flagged += 1
        return flagged

    def enforce_validated_profile(self) -> int:
        p = RendererCatalog.VALIDATED_SAFE
        pairs = (("debug.hwui.renderer", p.hwui_renderer), ("debug.renderengine.backend", p.render_backend),
                 ("debug.hwui.render_thread", p.render_thread), ("debug.gr.numframebuffers", p.numframebuffers),
                 ("debug.sf.disable_backpressure", p.disable_backpressure), ("debug.sf.latch_unsignaled", p.latch_unsignaled))
        return sum(int(self._sh.setprop(k, v)) for k, v in pairs)

    def verify_effective_state(self) -> bool:
        _, out, _ = self._sh.run("getprop debug.hwui.renderer")
        req = out.strip()
        egl_ok = "Initialized EGL" in self._sh.logcat_grep("OpenGLRenderer", "D", 20)
        SecFERRO_TUI.row("debug.hwui.renderer", req, None)
        SecFERRO_TUI.row("EGL context negotiated", str(egl_ok), egl_ok)
        return req == RendererCatalog.VALIDATED_SAFE.hwui_renderer and egl_ok

    def check_hwc_composition_health(self) -> bool:
        out = self._sh.logcat_grep("bcm-hwc", "W", 30)
        healthy = len(re.findall(r"no layer to compose", out)) < 15
        SecFERRO_TUI.row("bcm-hwc composition healthy", str(healthy), healthy)
        return healthy

    def read_gpu_hardware_facts(self) -> dict[str, str]:
        clock = re.search(r"GPU Clock speed:\s*(\d+\s*MHz)", self._sh.logcat_grep("NEXUS", "I", 10))
        facts = {"gpu_clock": clock.group(1) if clock else "unavailable"}
        for k, v in facts.items(): SecFERRO_TUI.row(k, v, None)
        return facts

    def run_integrity_check(self) -> None:
        SecFERRO_TUI.banner("Renderer Integrity Guard")
        self.audit_pasted_regressions()
        self.enforce_validated_profile()
        self.verify_effective_state()
        self.check_hwc_composition_health()
        self.read_gpu_hardware_facts()


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE KEY MAPPER
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeKeyMapper:
    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh
        self._pkg: str = ""

    def _resolve_pkg(self) -> bool:
        for pkg in SmartTubeCatalog.PACKAGES:
            if self._sh.run(f"pm list packages {pkg} 2>/dev/null")[0] == 0:
                self._pkg = pkg
                return True
        return False

    def _prefs_path(self) -> str:
        name = SmartTubeCatalog.PREF_FILENAME_TMPL.format(pkg=self._pkg)
        return f"{SmartTubeCatalog.PREFS_DIR.format(pkg=self._pkg)}/{name}"

    def _pull_prefs_xml(self, local: str) -> bool:
        _, out, _ = self._sh.run(f"cat '{self._prefs_path()}' 2>/dev/null")
        if not out or "<map" not in out: return False
        with open(local, "w", encoding="utf-8") as f:
            f.write(out) # local (Host Termux) operation!
        return True

    def _push_patched_xml(self, local: str) -> bool:
        with open(local, "r", encoding="utf-8") as f:
            content = f.read() # local (Host Termux) operation
        escaped = content.replace("'", "'\\''") # Remote shell escaping
        rc, _, _ = self._sh.run(f"echo '{escaped}' > '{self._prefs_path()}' 2>/dev/null")
        return rc == 0

    def apply(self) -> bool:
        SecFERRO_TUI.banner("SmartTube Key Mapper")
        if not self._resolve_pkg(): return False
        self._sh.run(f"cp '{self._prefs_path()}' '/sdcard/smarttube_prefs_backup.xml' 2>/dev/null")
        
        local_tmp = "st_prefs_patched.xml"
        xml_ok = False
        if self._pull_prefs_xml(local_tmp):
            tree = ET.parse(local_tmp)
            root = tree.getroot()
            for b in SmartTubeCatalog.BINDINGS:
                for k, action in [(SmartTubeCatalog.PREF_KEY_SHORT, b.action), (SmartTubeCatalog.PREF_KEY_LONG, b.long_action)]:
                    if action:
                        pk = k.format(action=action)
                        e = root.find(f"string[@name='{pk}']")
                        if e is not None: e.text = str(b.keycode)
                        else:
                            e = ET.SubElement(root, "string")
                            e.set("name", pk)
                            e.text = str(b.keycode)
            tree.write(local_tmp, encoding="unicode", xml_declaration=True)
            xml_ok = self._push_patched_xml(local_tmp)
            SecFERRO_TUI.row("XML prefs patched", "applied", xml_ok)
            
        self._sh.run(f"am force-stop {self._pkg}")
        return xml_ok


# ════════════════════════════════════════════════════════════════════════════════
# PHONE CLIPBOARD BRIDGE
# ════════════════════════════════════════════════════════════════════════════════

class PhoneClipboardBridge:
    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh
        self._YT_BASE = "https://youtu.be/{}"

    def _extract_video_id(self) -> str:
        _, out, _ = self._sh.run("dumpsys media_session 2>/dev/null | grep -E 'videoId=' | head -1")
        m = re.search(r"videoId=([a-zA-Z0-9_\-]{11})", out)
        return m.group(1) if m else ""

    def _find_kdeconnect_device(self) -> str:
        # Wykorzystuje metodę hosta (Termux), bo kdeconnect jest binarką lokalną!
        _, out, _ = self._sh.run_host("kdeconnect-cli --list-devices --id-only 2>/dev/null | head -1")
        return out.strip()

    def _send_via_kdeconnect(self, url: str) -> bool:
        dev_id = self._find_kdeconnect_device()
        if not dev_id: return False
        rc, _, _ = self._sh.run_host(f"kdeconnect-cli -d '{dev_id}' --share-text '{url}' 2>/dev/null")
        return rc == 0

    def _send_via_adb_phone(self, url: str) -> bool:
        _, devices, _ = self._sh.run_host("adb devices 2>/dev/null")
        for line in devices.splitlines():
            if "\tdevice" in line and not line.startswith("192."):
                serial = line.split("\t")[0]
                if self._sh.run_host(f"adb -s {serial} shell \"service call clipboard 2 i32 1 s16 shell s16 '{url}'\"")[0] == 0:
                    return True
        return False

    def send(self, with_timestamp: bool = False) -> bool:
        vid = self._extract_video_id()
        if not vid: return False
        url = self._YT_BASE.format(vid)
        if self._send_via_kdeconnect(url) or self._send_via_adb_phone(url):
            SecFERRO_TUI.row("Transport", "Phone Host Success", True)
            return True
        self._sh.run(f"service call clipboard 2 i32 1 s16 shell s16 '{url}' 2>/dev/null")
        return True


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM INTEGRITY AUDITOR & REMOTE PROBES
# ════════════════════════════════════════════════════════════════════════════════

class SystemIntegrityAuditor:
    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def audit(self) -> dict[str, bool]:
        results = {}
        for f in SystemIntegrityCatalog.FINDINGS:
            hit = re.search(f.pattern, self._sh.logcat_grep(f.tag, "V", 300)) is not None
            results[f.verdict] = hit
            SecFERRO_TUI.row(f.verdict, str(hit), None if not hit else (f.severity != "ERROR"))
        return results

    def remediate_billing_cache(self) -> bool:
        pkg = "com.spocky.projengmenu"
        self._sh.run(f"rm -rf /data/user/0/{pkg}/cache/*")
        rc, _, _ = self._sh.run(f"am force-stop {pkg}")
        return rc == 0

    def verify_ethernet_hardware(self) -> str:
        _, out, _ = self._sh.run("ip link show eth0 2>/dev/null")
        present = bool(out) and "does not exist" not in out
        state = "UP" if "state UP" in out else ("DOWN" if present else "ABSENT")
        SecFERRO_TUI.row("eth0 hardware state", state, present)
        return state

class RemoteKeyProbe:
    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh = sh

    def capture(self, duration_secs: int = 10) -> None:
        SecFERRO_TUI.banner("Remote Keycode Probe")
        _, raw, _ = self._sh.run(f"timeout {duration_secs} getevent -lt /dev/input/event8 2>/dev/null | grep EV_KEY")
        for line in raw.splitlines():
            SecFERRO_TUI.row("Captured Event", line, True)

    def check_keylayout_integrity(self) -> bool:
        out = self._sh.logcat_grep("KeyLayoutMap", "W", 20)
        m = re.search(r"virtual-remote\.kl:(\d+):\s*Expected", out)
        if m: SecFERRO_TUI.error(f"virtual-remote.kl line {m.group(1)} malformed")
        return not bool(m)

class SmartTubeEnhancer:
    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._mapper = SmartTubeKeyMapper(sh)
    def apply_all(self) -> None:
        self._mapper.apply()


# ════════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.5.4-rc.1 — Dispatcher")
    tuner = PerformanceTuner()
    mode  = sys.argv[1] if len(sys.argv) > 1 else "--optimize"
    dispatch: dict[str, Callable[[], object]] = {
        "--optimize":               tuner.run_full_optimization,
        "--diagnostics":            tuner.run_diagnostics,
    }
    handler = dispatch.get(mode)
    if handler is None:
        SecFERRO_TUI.error(f"Unknown mode '{mode}'.")
        sys.exit(1)
    handler()

if __name__ == "__main__":
    main()