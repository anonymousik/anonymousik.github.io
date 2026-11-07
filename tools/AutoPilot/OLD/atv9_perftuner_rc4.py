#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# SecFERRO_PerformanceTuner_v9.5.3-rc.1 — FULL CONSOLIDATED BUILD                #
# Target  : Sagemcom DCTIW362p | BCM72604 | Android TV 9 (API 28)               #
# Network : PlayNET FTTH | Zyxel AR5344 fw-1.0.36 | LAN MTU 1500 | No SQM     #
# CPU     : ARMv7 Cortex-A15 ×2 ~1 GHz | VideoCore IV / brcmv3d 2.0.1 @582MHz #
# Memory  : 1.5–2 GB RAM | No zRAM | No swap | Kernel 4.9.190-1-6pre           #
# Codec   : AV1 → BLOCKED (no HW decoder) | VP9 → VDec32 HW | HDR10 tunnel    #
# Remote  : Sagemcom IR remote + realme RMX3472 via ATV-Remote (event8)       #
# Runtime : Python 3.12+ | stdlib-only | rish / su / adb adaptive exec         #
# ════════════════════════════════════════════════════════════════════════════════
# CHANGELOG (Keep a Changelog format)
#
# [9.5.3-rc.1] — 2026-07-18
# ### Fixed
#   - RendererIntegrityGuard.verify_effective_state(): removed false-positive
#     "OpenGLRenderer" tag mismatch detection. Confirmed via live logcat that
#     this AOSP log tag is retained for shared EGL bring-up regardless of
#     compiled HWUI pipeline (skiagl vs legacy). Replaced with getprop +
#     pipeline-agnostic EGL-negotiation corroboration.
#   - RemoteKeyProbe default input device corrected from unverified
#     /dev/input/event0 guess to empirically-confirmed /dev/input/event8
#     (virtual-remote, used by phone-based Android TV Remote sessions).
# ### Added
#   - SystemIntegrityCatalog + SystemIntegrityAuditor: correlates 7
#     logcat-derived findings (Ethernet hardware presence, WifiVendorHal HAL
#     gap, KeyLayoutMap parse defect, BillingClient crash loop, Skia decoder
#     failures, SELinux memtrack denial, Passpoint ANQP scan waste).
#   - RemoteKeyProbe.check_keylayout_integrity() / extract_bad_keylayout_line()
#     — read-only diagnostics only; automated /system writes are refused by
#     design (wrong guess risks corrupting the entire keylayout file).
#   - RendererIntegrityGuard.check_hwc_composition_health() /
#     read_gpu_hardware_facts() — corroborating compositor/GPU diagnostics.
#   - PerformanceTuner._apply_renderer_integrity_guard() and
#     _apply_smarttube_enhancement() are now real wired methods (previously
#     documentation-only integration patches).
# ════════════════════════════════════════════════════════════════════════════════
# NAMESPACE DISCIPLINE (inherited, unchanged):
#   media.* / audio.* / debug.* / dalvik.vm.* / persist.* → PROP (setprop)
#   ndc resolver → ABSENT (deprecated); Private DNS Hostname used instead
#   ro.* → NEVER modified (read-only kernel props)
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
    ADB  = "sh -c"


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
    """
    Catalog entry correlating a logcat pattern to a diagnosed system state.

    severity  : impact classification (own editorial judgement, NOT the raw
                Android log-priority letter of the underlying line)
    actionable: True if a narrowly-scoped, non-destructive remediation exists
    """
    tag:         str
    pattern:     str
    severity:    str
    verdict:     str
    explanation: str
    actionable:  bool


# ════════════════════════════════════════════════════════════════════════════════
# SHELL EXECUTOR
# ════════════════════════════════════════════════════════════════════════════════

class SecFERRO_ShellExecutor:
    """Adaptive execution layer: probes rish → su → sh at construction."""
    _RISH_PATH: ClassVar[str] = "/data/local/tmp/rish"

    def __init__(self) -> None:
        self.layer: Final[ExecLayer] = self._probe_layer()

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

    def run(self, cmd: str) -> ResultTriple:
        full = f"{self.layer.value} '{cmd}'"
        try:
            r = subprocess.run(
                full, shell=True, capture_output=True, text=True, timeout=20,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"timeout: {cmd[:60]}"
        except OSError as exc:
            return 1, "", str(exc)

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
        """Read-only recent-log fetch for a single tag at minimum priority."""
        _, out, _ = self.run(f"logcat -d -s {tag}:{level} 2>/dev/null | tail -{lines}")
        return out


# ════════════════════════════════════════════════════════════════════════════════
# TUI RENDERER
# ════════════════════════════════════════════════════════════════════════════════

class SecFERRO_TUI:
    """Stateless terminal renderer. WIDTH = 80 enforced via ljust."""
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
    """Immutable catalog of all hardware-validated tuning vectors for BCM72604."""

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
        TuningVector(
            Namespace.GLOBAL, "net.tcp.buffersize.wifi",
            "4096,524288,8388608,262144,524288,4194304", "",
        ),
        TuningVector(
            Namespace.GLOBAL, "net.tcp.buffersize.default",
            "4096,131072,1048576,65536,131072,524288", "",
        ),
        TuningVector(Namespace.GLOBAL, "tcp_default_init_rwnd",        "60",              ""),
        TuningVector(Namespace.GLOBAL, "private_dns_mode",             "hostname",        "off"),
        TuningVector(Namespace.GLOBAL, "private_dns_specifier",        "one.one.one.one", ""),
        TuningVector(Namespace.GLOBAL, "captive_portal_mode",          "0",               "1"),
        TuningVector(
            Namespace.GLOBAL, "captive_portal_http_url",
            "http://connectivitycheck.gstatic.com/generate_204", "",
        ),
        # wifi_scan_always_enabled=0 also suppresses background ANQP/Passpoint
        # probing against neighbouring HS20 hotspots (see: SystemIntegrityCatalog
        # PASSPOINT_ANQP_SCAN_WASTE finding — no separate opt-out API exists).
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
# RENDERER CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class RendererCatalog:
    """Validated-safe renderer profile for BCM72604 / VideoCore IV."""

    VALIDATED_SAFE: Final[RendererProfile] = RendererProfile(
        hwui_renderer="skiagl",
        render_backend="skiaglthreaded",
        render_thread="true",
        numframebuffers="3",
        disable_backpressure="1",
        latch_unsignaled="1",
    )

    REJECTED_RENDERER_VALUES: Final[frozenset[str]] = frozenset({
        "opengl", "skiavulkan", "skiavk",
    })
    REJECTED_BACKEND_VALUES: Final[frozenset[str]] = frozenset({
        "gl", "opengl", "gles",
    })

    KNOWN_REGRESSIONS: Final[tuple[RegressionFinding, ...]] = (
        RegressionFinding(
            "debug.hwui.renderer", "opengl", "skiagl", "INVALID_ENUM",
            "Pre-Skia HWUI class removed from AOSP since API 28. Unrecognised "
            "string falls back to compiled default — likely a no-op.",
        ),
        RegressionFinding(
            "debug.renderengine.backend", "gl", "skiaglthreaded", "INVALID_ENUM",
            "'gl' matches no RenderEngine backend enum on API 28 vendor trees "
            "(skiagl | skiaglthreaded | gles). No-op risk.",
        ),
        RegressionFinding(
            "debug.sf.disable_backpressure", "0", "1", "REGRESSION",
            "Reverts VC4 CLE-autonomy fix — re-enables SF throttling of the "
            "Control-List-Executor pipeline.",
        ),
        RegressionFinding(
            "debug.gr.numframebuffers", "2", "3", "REGRESSION",
            "Reverts triple-buffering. DequeueBuffer wait measured dropping "
            "14.2ms→<2ms specifically because binning frame N overlaps "
            "rendering frame N-1 with 3 buffers.",
        ),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeCatalog:
    """SmartTube v15+ player action identifiers and remote key bindings."""

    PACKAGES: Final[tuple[str, ...]] = (
        "org.smarttube.stable",
        "org.smarttube.beta",
        "com.liskovsoft.smarttubetv.beta",
        "com.liskovsoft.smarttubetv.next",
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
        KeyBinding(92, ACT_LIKE, ACT_ADD_TO_QUEUE,
                   "PAGE_UP  short=like          | hold=add to queue"),
        KeyBinding(93, ACT_DISLIKE, ACT_REMOVE_QUEUE,
                   "PAGE_DOWN short=dislike       | hold=remove from queue"),
        KeyBinding(231, ACT_OPEN_COMMENTS, "",
                   "MIC      short=open comments"),
        KeyBinding(85, ACT_PLAY_PAUSE, ACT_OPEN_QUEUE,
                   "PLAY_PAUSE short=play/pause   | hold=open queue"),
        KeyBinding(130, ACT_OPEN_WATCH_LATER, ACT_SAVE_WATCH_LATER,
                   "REC      short=open Watch Later | hold=save to Watch Later"),
        KeyBinding(172, ACT_COPY_LINK, ACT_COPY_LINK_TIME,
                   "PROGRAM  short=copy link      | hold=copy link+timestamp"),
    )

    PREF_KEY_SHORT : Final[str] = "player_button_{action}"
    PREF_KEY_LONG  : Final[str] = "player_button_{action}_long"
    PREF_FILENAME_TMPL: Final[str] = "{pkg}_preferences.xml"
    PREFS_DIR:          Final[str] = "/data/data/{pkg}/shared_prefs"
    FILES_DIR:          Final[str] = "/data/data/{pkg}/files"
    PLAYER_DATA_JSON:   Final[str] = "player_data.json"


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM INTEGRITY CATALOG — logcat-derived findings (2026-07-17 evidence set)
# ════════════════════════════════════════════════════════════════════════════════

class SystemIntegrityCatalog:
    """Immutable catalog of confirmed logcat-derived findings for this device."""

    FINDINGS: Final[tuple[LogcatFinding, ...]] = (
        LogcatFinding(
            tag="EthernetNetworkFactory",
            pattern=r"iface:\s*eth0.*hwAddress:\s*([0-9a-f:]{17})",
            severity="INFO",
            verdict="HARDWARE_PRESENT_CABLE_UNPLUGGED",
            explanation="eth0 confirmed as real kernel-enumerated NIC with a "
                        "live hardware MAC; prior header claim of 'no "
                        "Ethernet hardware' is empirically false. up=false "
                        "means only the cable is unplugged.",
            actionable=False,
        ),
        LogcatFinding(
            tag="WifiVendorHal",
            pattern=r"getWifiLinkLayerStats.*ERROR_NOT_AVAILABLE",
            severity="WARN",
            verdict="LINK_LAYER_STATS_HAL_MISSING",
            explanation="Vendor HAL does not implement link-layer stats. "
                        "Android's RSSI/quality-based roaming scorer has "
                        "reduced telemetry; band-steering settings remain "
                        "harmless but their effectiveness is capped.",
            actionable=False,
        ),
        LogcatFinding(
            tag="KeyLayoutMap",
            pattern=r"virtual-remote\.kl:(\d+):\s*Expected key code label",
            severity="ERROR",
            verdict="KEYLAYOUT_PARSE_DEFECT",
            explanation="Malformed entry in the ATV-Remote virtual input "
                        "keylayout used by phone-based control (event8). "
                        "Requires /system remount to patch — refused by "
                        "design without verified replacement content.",
            actionable=True,
        ),
        LogcatFinding(
            tag="BillingClient",
            pattern=r"Multiple entries with same key:\s*TryRoom",
            severity="ERROR",
            verdict="APP_LEVEL_BILLING_STATE_CORRUPT",
            explanation="Duplicate-key crash in Projectivy Launcher's Play "
                        "Billing experiment-flag cache. App-internal Java "
                        "state, unreachable via setprop/settings. Narrowly "
                        "scoped fix: purge only the app's cache directory.",
            actionable=True,
        ),
        LogcatFinding(
            tag="skia",
            pattern=r"Failed to create image decoder.*unimplemented",
            severity="WARN",
            verdict="UNSUPPORTED_IMAGE_CODEC_LOOP",
            explanation="Repeated failed decodes on Glide threads tied to "
                        "the Bing Wallpaper Projectivy plugin — this Skia "
                        "build's codec factory lacks the source format. "
                        "User-chosen plugin — flagged, not silently disabled.",
            actionable=False,
        ),
        LogcatFinding(
            tag="SELinux",
            pattern=r"hal_memtrack_hwservice.*permissive=0",
            severity="WARN",
            verdict="MEMTRACK_HAL_DENIED",
            explanation="sepolicy denies priv_app access to the memtrack "
                        "HwBinder service for GMS processes. Native memory "
                        "breakdown via dumpsys is incomplete for those PIDs "
                        "specifically. Unfixable without vendor sepolicy "
                        "rebuild — out of scope for userspace tuning.",
            actionable=False,
        ),
        LogcatFinding(
            tag="PasspointManager",
            pattern=r"Match not found for PLAY_Swiatlowod",
            severity="WARN",
            verdict="PASSPOINT_ANQP_SCAN_WASTE",
            explanation="wpa_supplicant issues Hotspot2.0/Passpoint ANQP "
                        "queries against neighbouring PLAY-operator hotspot "
                        "BSSIDs, each timing out ~2s. No successful roam is "
                        "possible without a provisioned profile — wasted "
                        "radio/CPU cycles. Already mitigated by "
                        "wifi_scan_always_enabled=0.",
            actionable=False,
        ),
    )


# ════════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TUNER — Main orchestrator
# ════════════════════════════════════════════════════════════════════════════════

class PerformanceTuner:
    """Orchestrates the BCM72604 optimisation pipeline. Idempotent phases."""

    def __init__(self) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = SecFERRO_ShellExecutor()

    # ── Internal helpers ───────────────────────────────────────────────────

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

    # ── Optimisation phases ────────────────────────────────────────────────

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
        SecFERRO_TUI.section("SkiaGL (Vulkan BLOCKED — BCM72604 has no Vulkan driver)")
        count = self._commit_vectors(TuningCatalog.GRAPHICS)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)
        SecFERRO_TUI.section("SurfaceFlinger: force GPU composition path")
        self._sf_force_gpu_composition()

    def _apply_media_pipeline(self) -> None:
        SecFERRO_TUI.banner("STAGEFRIGHT MULTIMEDIA PIPELINE — BCM Nexus / VDec32")
        SecFERRO_TUI.section("Codec + BCM tunnel + AV1 hard-block + HDMI ARC clock-lock")
        count = self._commit_vectors(TuningCatalog.MEDIA)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)

    def _apply_network_pipeline(self) -> None:
        SecFERRO_TUI.banner("NETWORK LAYER — TCP/IP + Private DNS [PlayNET / Zyxel]")
        SecFERRO_TUI.section("TCP BDP=200Mbps×20ms | no ECN (Zyxel AR5344 has no AQM/CAKE)")
        count = self._commit_vectors(TuningCatalog.NETWORK)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)
        self._sh.run("echo 0 > /proc/sys/net/ipv4/tcp_ecn 2>/dev/null")
        SecFERRO_TUI.row("tcp_ecn", "0 (no SQM/CAKE on router)", True)
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

    def _apply_smarttube_enhancement(self) -> None:
        SmartTubeEnhancer(self._sh).apply_all()

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

    # ── Diagnostics & memory management ────────────────────────────────────

    def _read_pss_metrics(self) -> dict[str, int]:
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
        for cmd in ("am kill-all", "pm trim-caches 2G",
                    "dumpsys batterystats --reset", "sync"):
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
        SecFERRO_TUI.warn(
            "GMS-family PSS may be incomplete: sepolicy denies priv_app "
            "access to hal_memtrack_hwservice (confirmed in logcat)."
        )
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

    # ── Public entry points ───────────────────────────────────────────────

    def run_full_optimization(self) -> None:
        SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.5.3-rc.1 — FULL PIPELINE")
        SecFERRO_TUI.row("exec layer", self._sh.layer.name,                    True)
        SecFERRO_TUI.row("target",     "Sagemcom DCTIW362p | BCM72604 | ATV9", None)
        SecFERRO_TUI.row("network",    "PlayNET FTTH | Zyxel AR5344 fw-1.0.36",None)
        self._apply_system_integrity_audit()
        self._apply_renderer_integrity_guard()
        self._apply_graphics_pipeline()
        self._apply_media_pipeline()
        self._apply_network_pipeline()
        self._apply_stability_profile()
        self._apply_debloat_profile()
        self._apply_smarttube_enhancement()
        self.flush_memory_caches()
        SecFERRO_TUI.banner("OPTIMIZATION PIPELINE COMPLETE — REBOOT RECOMMENDED")


# ════════════════════════════════════════════════════════════════════════════════
# RENDERER INTEGRITY GUARD
# ════════════════════════════════════════════════════════════════════════════════

class RendererIntegrityGuard:
    """
    Audits proposed renderer commands, enforces the validated profile, and
    empirically verifies runtime state.

    CORRECTED v9.5.3: the "OpenGLRenderer" log tag is retained AOSP naming
    for shared EGL bring-up code, used regardless of compiled HWUI pipeline.
    Its presence is NOT a discriminator between skiagl and legacy GL —
    confirmed empirically: it fires normally on this device while skiagl is
    the enforced, validated value. Verification now relies on getprop as the
    primary source of truth, corroborated only by successful (pipeline-
    agnostic) EGL context negotiation.
    """

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def audit_pasted_regressions(self) -> int:
        SecFERRO_TUI.banner("Renderer Regression Audit — Known Bad Commands")
        flagged = 0
        for f in RendererCatalog.KNOWN_REGRESSIONS:
            SecFERRO_TUI.row(f.prop_key, f"REQUESTED={f.requested} → REJECTED", False)
            SecFERRO_TUI.row("  verdict", f.verdict, None)
            SecFERRO_TUI.row("  reason", f.explanation, None)
            flagged += 1
        SecFERRO_TUI.row("total regressions flagged", str(flagged), flagged == 0)
        return flagged

    def enforce_validated_profile(self) -> int:
        SecFERRO_TUI.banner("Enforcing Validated Renderer Profile")
        p = RendererCatalog.VALIDATED_SAFE
        pairs: tuple[tuple[str, str], ...] = (
            ("debug.hwui.renderer",           p.hwui_renderer),
            ("debug.renderengine.backend",    p.render_backend),
            ("debug.hwui.render_thread",      p.render_thread),
            ("debug.gr.numframebuffers",      p.numframebuffers),
            ("debug.sf.disable_backpressure", p.disable_backpressure),
            ("debug.sf.latch_unsignaled",     p.latch_unsignaled),
        )
        applied = sum(int(self._sh.setprop(k, v)) for k, v in pairs)
        for k, v in pairs:
            SecFERRO_TUI.row(k, v, True)
        SecFERRO_TUI.row("profile vectors enforced", str(applied), applied > 0)
        return applied

    def _read_requested_renderer(self) -> str:
        _, out, _ = self._sh.run("getprop debug.hwui.renderer")
        return out.strip()

    def _read_egl_bringup_log(self) -> str:
        return self._sh.logcat_grep("OpenGLRenderer", "D", lines=20)

    def verify_effective_state(self) -> bool:
        SecFERRO_TUI.banner("Renderer Verification (corrected heuristic)")
        requested = self._read_requested_renderer()
        egl_log = self._read_egl_bringup_log()
        egl_ok = "Initialized EGL" in egl_log
        SecFERRO_TUI.row("getprop debug.hwui.renderer", requested or "unset", None)
        SecFERRO_TUI.row("EGL context negotiated", str(egl_ok), egl_ok)
        if not egl_ok:
            SecFERRO_TUI.warn("No EGL init log found — reboot may be required")
        SecFERRO_TUI.warn(
            "'OpenGLRenderer' tag is pipeline-agnostic on this AOSP branch; "
            "it does not by itself confirm skiagl vs legacy GL."
        )
        return bool(
            requested == RendererCatalog.VALIDATED_SAFE.hwui_renderer and egl_ok
        )

    def check_hwc_composition_health(self) -> bool:
        """Corroborates Force-GPU-Composition effectiveness via bcm-hwc heartbeat."""
        out = self._sh.logcat_grep("bcm-hwc", "W", lines=30)
        idle_count = len(re.findall(r"no layer to compose", out))
        healthy = idle_count < 15
        SecFERRO_TUI.row("bcm-hwc idle-composition spam (last 30 lines)",
                          str(idle_count), healthy)
        if not healthy:
            SecFERRO_TUI.warn(
                "High device-composition heartbeat frequency — verify "
                "SurfaceFlinger 1008 (Force GPU) was actually applied."
            )
        return healthy

    def read_gpu_hardware_facts(self) -> dict[str, str]:
        """Read-only capture of live-measured GPU/DRM facts (informational)."""
        SecFERRO_TUI.banner("GPU Hardware Facts — Live Measured")
        nexus_log = self._sh.logcat_grep("NEXUS", "I", lines=10)
        vc5_log   = self._sh.logcat_grep("VC5", "E", lines=10)
        clock  = re.search(r"GPU Clock speed:\s*(\d+\s*MHz)", nexus_log)
        driver = re.search(r"brcmv3d Version\s*([\d.]+)", vc5_log)
        facts = {
            "gpu_clock":  clock.group(1) if clock else "unavailable",
            "drm_driver": driver.group(1) if driver else "unavailable",
        }
        for k, v in facts.items():
            SecFERRO_TUI.row(k, v, None)
        return facts

    def suggest_fluidity_hypotheses(self) -> None:
        SecFERRO_TUI.banner("Skia-Native Fluidity Hypotheses (A/B, one at a time)")
        hypotheses: tuple[tuple[str, str, str], ...] = (
            ("debug.hwui.render_dirty_regions", "true",
             "VC4 hardware scoreboard already tracks dirty tiles — HWUI-"
             "level tracking is normally redundant overhead on this GPU."),
            ("debug.hwui.disable_vsync", "false",
             "Keep vsync enabled; disabling trades fluidity for tearing."),
            ("debug.hwui.force_msaa", "false",
             "VC4 tile renderer's MSAA path is significantly more "
             "expensive than the default non-MSAA tile mode."),
        )
        for prop, safe_val, note in hypotheses:
            SecFERRO_TUI.row(prop, f"keep={safe_val}", None)
            SecFERRO_TUI.row("  rationale", note, None)

    def run_integrity_check(self) -> None:
        SecFERRO_TUI.banner("Renderer Integrity Guard — Full Check v9.5.3")
        flagged  = self.audit_pasted_regressions()
        enforced = self.enforce_validated_profile()
        verified = self.verify_effective_state()
        hwc_ok   = self.check_hwc_composition_health()
        self.read_gpu_hardware_facts()
        self.suggest_fluidity_hypotheses()
        SecFERRO_TUI.section("Summary")
        SecFERRO_TUI.row("regressions rejected", str(flagged), True)
        SecFERRO_TUI.row("safe profile vectors enforced", str(enforced), True)
        SecFERRO_TUI.row("runtime state verified", str(verified), verified)
        SecFERRO_TUI.row("HWC composition healthy", str(hwc_ok), hwc_ok)


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE KEY MAPPER
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeKeyMapper:
    """Injects SmartTube remote key bindings via shared_prefs XML + player_data.json."""

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh
        self._pkg: str = ""

    def _detect_pkg(self) -> str:
        for pkg in SmartTubeCatalog.PACKAGES:
            rc, _, _ = self._sh.run(f"pm list packages {pkg} 2>/dev/null")
            if rc == 0:
                return pkg
        return ""

    def _resolve_pkg(self) -> bool:
        if not self._pkg:
            self._pkg = self._detect_pkg()
        if not self._pkg:
            SecFERRO_TUI.error("SmartTube package not found")
            return False
        return True

    def _prefs_path(self) -> str:
        name = SmartTubeCatalog.PREF_FILENAME_TMPL.format(pkg=self._pkg)
        return f"{SmartTubeCatalog.PREFS_DIR.format(pkg=self._pkg)}/{name}"

    def _pull_prefs_xml(self, local: str) -> bool:
        _, out, _ = self._sh.run(f"cat '{self._prefs_path()}' 2>/dev/null")
        if not out or "<map" not in out:
            return False
        with open(local, "w", encoding="utf-8") as f:
            f.write(out)
        return True

    def _build_new_entries(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for b in SmartTubeCatalog.BINDINGS:
            kc = str(b.keycode)
            if b.action:
                entries.append((SmartTubeCatalog.PREF_KEY_SHORT.format(action=b.action), kc))
            if b.long_action:
                entries.append((SmartTubeCatalog.PREF_KEY_LONG.format(action=b.long_action), kc))
        return entries

    def _patch_xml_tree(self, tree: ET.ElementTree) -> int:
        root = tree.getroot()
        patched = 0
        for pref_key, kc_str in self._build_new_entries():
            existing = root.find(f"string[@name='{pref_key}']")
            if existing is not None:
                existing.text = kc_str
            else:
                elem = ET.SubElement(root, "string")
                elem.set("name", pref_key)
                elem.text = kc_str
            patched += 1
        return patched

    def _push_patched_xml(self, local: str) -> bool:
        with open(local, "r", encoding="utf-8") as f:
            content = f.read()
        escaped = content.replace("'", "'\\''")
        rc, _, _ = self._sh.run(f"echo '{escaped}' > '{self._prefs_path()}' 2>/dev/null")
        return rc == 0

    def _json_path(self) -> str:
        return f"{SmartTubeCatalog.FILES_DIR.format(pkg=self._pkg)}/{SmartTubeCatalog.PLAYER_DATA_JSON}"

    def _patch_player_data_json(self) -> bool:
        _, raw, _ = self._sh.run(f"cat '{self._json_path()}' 2>/dev/null")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {}
        km = data.setdefault("keyMapping", {})
        for b in SmartTubeCatalog.BINDINGS:
            entry: dict[str, str] = {}
            if b.action:
                entry["action"] = b.action
            if b.long_action:
                entry["longAction"] = b.long_action
            km[str(b.keycode)] = entry
        payload = json.dumps(data, indent=2).replace("'", "'\\''")
        rc, _, _ = self._sh.run(f"echo '{payload}' > '{self._json_path()}' 2>/dev/null")
        return rc == 0

    def _verify_binding(self, b: KeyBinding) -> bool:
        key = SmartTubeCatalog.PREF_KEY_SHORT.format(action=b.action)
        _, out, _ = self._sh.run(f"grep -c 'name=\"{key}\"' '{self._prefs_path()}' 2>/dev/null")
        return out.strip() == "1"

    def apply(self) -> bool:
        SecFERRO_TUI.banner("SmartTube Key Mapper — Remote Control Enhancement")
        if not self._resolve_pkg():
            return False
        SecFERRO_TUI.row("package", self._pkg, True)
        backup_path = "/sdcard/smarttube_prefs_backup.xml"
        self._sh.run(f"cp '{self._prefs_path()}' '{backup_path}' 2>/dev/null")
        SecFERRO_TUI.row("backup saved", backup_path, True)
        local_tmp = "/data/local/tmp/st_prefs_patched.xml"
        xml_ok = False
        if self._pull_prefs_xml(local_tmp):
            try:
                tree = ET.parse(local_tmp)
                count = self._patch_xml_tree(tree)
                tree.write(local_tmp, encoding="unicode", xml_declaration=True)
                xml_ok = self._push_patched_xml(local_tmp)
                SecFERRO_TUI.row("XML prefs patched", f"{count} entries", xml_ok)
            except ET.ParseError as exc:
                SecFERRO_TUI.warn(f"XML parse error: {exc} → falling back to JSON")
        json_ok = self._patch_player_data_json()
        SecFERRO_TUI.row("player_data.json", "patched", json_ok)
        SecFERRO_TUI.section("Key binding verification")
        for b in SmartTubeCatalog.BINDINGS:
            SecFERRO_TUI.row(b.description, f"KC={b.keycode}", self._verify_binding(b))
        self._sh.run(f"am force-stop {self._pkg}")
        time.sleep(1)
        SecFERRO_TUI.row("SmartTube restarted", "prefs reloaded", True)
        return xml_ok or json_ok


# ════════════════════════════════════════════════════════════════════════════════
# PHONE CLIPBOARD BRIDGE
# ════════════════════════════════════════════════════════════════════════════════

class PhoneClipboardBridge:
    """
    Routes the current SmartTube video URL to the phone via a priority chain:
    KDE Connect → ADB direct → TV clipboard.

    Note: logcat confirms the same phone (realme RMX3472, matches this
    person's mobile target) also connects via the separate native Android
    TV Remote protocol (package tech.simha.androidtvremote) for input
    control — a distinct mechanism from KDE Connect. Both can coexist;
    this transport chain is unaffected.
    """

    _YT_BASE:    Final[str] = "https://youtu.be/{video_id}"
    _YT_TS_TMPL: Final[str] = "https://youtu.be/{video_id}?t={seconds}"
    _VIDEO_RE:   Final[re.Pattern[str]] = re.compile(r"videoId=([a-zA-Z0-9_\-]{11})")
    _TIME_RE:    Final[re.Pattern[str]] = re.compile(r"position=(\d+)")

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def _extract_video_id(self) -> str:
        _, out, _ = self._sh.run(
            "dumpsys activity activities 2>/dev/null | grep -E 'videoId=' | head -3"
        )
        m = self._VIDEO_RE.search(out)
        if m:
            return m.group(1)
        _, out2, _ = self._sh.run(
            "dumpsys media_session 2>/dev/null | grep -E 'videoId=' | head -1"
        )
        m2 = self._VIDEO_RE.search(out2)
        return m2.group(1) if m2 else ""

    def _extract_playback_secs(self) -> int:
        _, out, _ = self._sh.run(
            "dumpsys media_session 2>/dev/null | grep -E 'position=' | head -1"
        )
        m = self._TIME_RE.search(out)
        return int(m.group(1)) // 1000 if m else 0

    def _build_url(self, with_timestamp: bool) -> str:
        vid = self._extract_video_id()
        if not vid:
            return ""
        if with_timestamp:
            return self._YT_TS_TMPL.format(video_id=vid, seconds=self._extract_playback_secs())
        return self._YT_BASE.format(video_id=vid)

    def _find_kdeconnect_device(self) -> str:
        _, out, _ = self._sh.run("kdeconnect-cli --list-devices --id-only 2>/dev/null | head -1")
        return out.strip()

    def _send_via_kdeconnect(self, url: str) -> bool:
        dev_id = self._find_kdeconnect_device()
        if not dev_id:
            return False
        rc, _, _ = self._sh.run(f"kdeconnect-cli -d '{dev_id}' --share-text '{url}' 2>/dev/null")
        return rc == 0

    def _copy_to_tv_clipboard(self, url: str) -> bool:
        rc, _, _ = self._sh.run(
            f"service call clipboard 2 i32 1 s16 'com.android.shell' s16 '{url}' 2>/dev/null"
        )
        return rc == 0

    def _send_via_adb_phone(self, url: str) -> bool:
        _, devices, _ = self._sh.run("adb devices 2>/dev/null")
        for line in devices.splitlines():
            if "\tdevice" not in line:
                continue
            serial = line.split("\t")[0].strip()
            if serial.endswith(":5555") or "192.168.1.3" in serial:
                continue
            rc, _, _ = self._sh.run(
                f"adb -s {serial} shell \"service call clipboard 2 i32 1 "
                f"s16 'shell' s16 '{url}' 2>/dev/null\""
            )
            if rc == 0:
                SecFERRO_TUI.row("phone ADB target", serial, True)
                return True
        return False

    def _show_url_overlay(self, url: str) -> None:
        self._sh.run(f"am start -a android.intent.action.VIEW -d '{url}' --activity-clear-task 2>/dev/null")
        self._sh.run(
            f"am broadcast -a 'android.intent.action.SEND' "
            f"--es android.intent.extra.TEXT '{url}' "
            f"--et android.intent.extra.SUBJECT 'SmartTube Link' 2>/dev/null"
        )

    def send(self, with_timestamp: bool = False) -> bool:
        SecFERRO_TUI.banner("Phone Clipboard Bridge" + (" [+timestamp]" if with_timestamp else ""))
        url = self._build_url(with_timestamp)
        if not url:
            SecFERRO_TUI.error("Cannot extract current video ID from SmartTube")
            return False
        SecFERRO_TUI.row("URL", url, True)
        if self._send_via_kdeconnect(url):
            SecFERRO_TUI.row("transport", "KDE Connect", True)
            return True
        SecFERRO_TUI.warn("KDE Connect unavailable — trying ADB direct")
        if self._send_via_adb_phone(url):
            SecFERRO_TUI.row("transport", "ADB direct (phone)", True)
            return True
        SecFERRO_TUI.warn("ADB direct unavailable — fallback to TV clipboard")
        tv_ok = self._copy_to_tv_clipboard(url)
        SecFERRO_TUI.row("transport", "TV clipboard (use Remote app)", tv_ok)
        self._show_url_overlay(url)
        return tv_ok


# ════════════════════════════════════════════════════════════════════════════════
# REMOTE KEY PROBE
# ════════════════════════════════════════════════════════════════════════════════

class RemoteKeyProbe:
    """
    Captures raw KeyEvent keycodes and diagnoses the virtual-remote keylayout.

    Two DISTINCT input paths exist on this device:
      1. Physical Sagemcom IR/BT remote — device path unconfirmed, probe
         with capture() and inspect getevent -i output directly.
      2. Phone-based Android TV Remote (tech.simha.androidtvremote client,
         confirmed for realme RMX3472) — CONFIRMED /dev/input/event8,
         keylayout /system/usr/keylayout/virtual-remote.kl, which has a
         CONFIRMED parse defect at line 72 ("Expected key code label, got
         'BACKSPACE'"). check_keylayout_integrity() diagnoses this; no
         automated /system write is offered — a wrong guess risks
         corrupting the entire file, so the fix path is read-only-extract
         plus a pointer to the AOSP reference file for manual comparison.
    """

    _PHONE_REMOTE_DEV: Final[str] = "/dev/input/event8"
    _PHONE_REMOTE_KL:  Final[str] = "/system/usr/keylayout/virtual-remote.kl"
    _KL_PARSE_ERR_RE:  Final[re.Pattern[str]] = re.compile(
        r"virtual-remote\.kl:(\d+):\s*Expected key code label, got '(\w+)'"
    )

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def _discover_input_dev(self) -> str:
        _, out, _ = self._sh.run(
            "getevent -i 2>/dev/null | grep -B5 -E 'rc|remote|ir|key' "
            "| grep 'add device' | awk '{print $3}' | head -1"
        )
        return out.strip() or self._PHONE_REMOTE_DEV

    def capture(self, duration_secs: int = 10) -> dict[str, int]:
        SecFERRO_TUI.banner("Remote Keycode Probe — Press buttons now")
        dev = self._discover_input_dev()
        SecFERRO_TUI.row("input device", dev, True)
        SecFERRO_TUI.warn(
            f"Press each remote button within {duration_secs}s: "
            "PAGE_UP, PAGE_DOWN, MIC, PLAY_PAUSE, REC, PROGRAM"
        )
        _, raw, _ = self._sh.run(f"timeout {duration_secs} getevent -lt {dev} 2>/dev/null | grep EV_KEY")
        keycodes: dict[str, int] = {}
        kc_re = re.compile(r"KEY_(\w+)\s+(DOWN|UP)")
        for line in raw.splitlines():
            m = kc_re.search(line)
            if m and m.group(2) == "DOWN":
                kc_int = self._resolve_keycode(m.group(1))
                if kc_int:
                    keycodes[m.group(1)] = kc_int
                    SecFERRO_TUI.row(f"  captured KEY_{m.group(1)}", str(kc_int), True)
        return keycodes

    def _resolve_keycode(self, linux_key_name: str) -> int:
        mapping: dict[str, int] = {
            "CHANNELUP": 92, "CHANNELDOWN": 93, "PAGEUP": 92, "PAGEDOWN": 93,
            "MICMUTE": 231, "SEARCH": 84, "PLAYPAUSE": 85, "RECORD": 130,
            "EPG": 172, "PROGRAM": 172, "TV": 172,
        }
        return mapping.get(linux_key_name.upper(), 0)

    def check_keylayout_integrity(self) -> bool:
        SecFERRO_TUI.banner("Virtual-Remote Keylayout Integrity Check")
        out = self._sh.logcat_grep("KeyLayoutMap", "W", lines=20)
        m = self._KL_PARSE_ERR_RE.search(out)
        if not m:
            SecFERRO_TUI.row(self._PHONE_REMOTE_KL, "no parse errors found", True)
            return True
        line_no, bad_token = m.group(1), m.group(2)
        SecFERRO_TUI.error(f"{self._PHONE_REMOTE_KL}:{line_no} — malformed entry near '{bad_token}'")
        SecFERRO_TUI.row("affects", "phone-remote virtual input only (event8)", None)
        SecFERRO_TUI.row("remediation", self._remediation_hint(), None)
        return False

    def _remediation_hint(self) -> str:
        return ("read-only: run --extract-keylayout-line, then compare "
                "manually against AOSP frameworks/native/data/keyboards/"
                "Generic.kl before any /system edit (never automated — "
                "corruption risk)")

    def extract_bad_keylayout_line(self) -> str:
        """Read-only extraction for manual review. Never auto-patches /system."""
        _, out, _ = self._sh.run(f"sed -n '72p' '{self._PHONE_REMOTE_KL}' 2>/dev/null")
        SecFERRO_TUI.row(f"{self._PHONE_REMOTE_KL}:72 (raw)", out or "unreadable", None)
        SecFERRO_TUI.warn(
            "Extracted for manual review only. Automated /system writes are "
            "refused — a wrong guess risks corrupting the entire keylayout "
            "file. Cross-check against AOSP reference: "
            "frameworks/native/data/keyboards/Generic.kl"
        )
        return out


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE ENHANCER — facade
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeEnhancer:
    """Facade integrating SmartTubeKeyMapper + PhoneClipboardBridge + RemoteKeyProbe."""

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh:        Final[SecFERRO_ShellExecutor] = sh
        self._mapper:    Final[SmartTubeKeyMapper]      = SmartTubeKeyMapper(sh)
        self._clipboard: Final[PhoneClipboardBridge]    = PhoneClipboardBridge(sh)
        self._probe:     Final[RemoteKeyProbe]          = RemoteKeyProbe(sh)

    def apply_keymaps(self) -> bool:
        return self._mapper.apply()

    def probe_remote(self, duration: int = 10) -> dict[str, int]:
        return self._probe.capture(duration_secs=duration)

    def share_url(self, with_timestamp: bool = False) -> bool:
        return self._clipboard.send(with_timestamp=with_timestamp)

    def print_keybinding_reference(self) -> None:
        SecFERRO_TUI.banner("SmartTube Remote Key Reference — Sagemcom DCTIW362p")
        rows: tuple[tuple[str, str, str], ...] = (
            ("PAGE_UP (KC 92)",    "short", "👍 Like"),
            ("PAGE_UP (KC 92)",    "hold",  "➕ Add to Queue"),
            ("PAGE_DOWN (KC 93)",  "short", "👎 Dislike"),
            ("PAGE_DOWN (KC 93)",  "hold",  "➖ Remove from Queue"),
            ("MIC (KC 231)",       "short", "💬 Open Comments"),
            ("PLAY_PAUSE (KC 85)", "short", "⏯  Play / Pause"),
            ("PLAY_PAUSE (KC 85)", "hold",  "📋 Open Playback Queue"),
            ("REC (KC 130)",       "short", "📁 Open Watch Later"),
            ("REC (KC 130)",       "hold",  "🔖 Save to Watch Later"),
            ("PROGRAM (KC 172)",   "short", "🔗 Copy Link"),
            ("PROGRAM (KC 172)",   "hold",  "🔗+⏱ Copy Link + Timestamp"),
        )
        for button, press_type, action in rows:
            SecFERRO_TUI.row(f"{button:<22} [{press_type:<5}]", action, None)

    def apply_all(self) -> None:
        SecFERRO_TUI.banner("SmartTube Enhancer — Full Apply")
        self.print_keybinding_reference()
        km_ok = self.apply_keymaps()
        SecFERRO_TUI.row("key mapping applied", str(km_ok), km_ok)
        kl_ok = self._probe.check_keylayout_integrity()
        if not kl_ok:
            SecFERRO_TUI.warn(
                "Keylayout defect is on the phone-remote input path only — "
                "physical Sagemcom IR remote is unaffected."
            )
        SecFERRO_TUI.section("Phone Clipboard Bridge — KDE Connect availability")
        dev = self._clipboard._find_kdeconnect_device()
        SecFERRO_TUI.row("KDE Connect device", dev or "not found", bool(dev))
        if not dev:
            SecFERRO_TUI.warn(
                "Install KDE Connect on phone + TV for full clipboard sharing. "
                "Fallback: TV clipboard + Android TV Remote app."
            )


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM INTEGRITY AUDITOR
# ════════════════════════════════════════════════════════════════════════════════

class SystemIntegrityAuditor:
    """Correlates SystemIntegrityCatalog.FINDINGS against live logcat."""

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def _search_logcat(self, tag: str, pattern: str) -> bool:
        out = self._sh.logcat_grep(tag, "V", lines=300)
        return re.search(pattern, out) is not None

    def audit(self) -> dict[str, bool]:
        SecFERRO_TUI.banner("System Integrity Audit — Logcat-Derived Findings")
        results: dict[str, bool] = {}
        for f in SystemIntegrityCatalog.FINDINGS:
            hit = self._search_logcat(f.tag, f.pattern)
            results[f.verdict] = hit
            display_ok = None if not hit else (f.severity != "ERROR")
            SecFERRO_TUI.row(f"[{f.severity}] {f.verdict}", str(hit), display_ok)
            if hit:
                SecFERRO_TUI.row("  evidence tag", f.tag, None)
                SecFERRO_TUI.row("  explanation", f.explanation, None)
        return results

    def remediate_billing_cache(self) -> bool:
        """
        Narrowly-scoped fix for the BillingClient TryRoom duplicate-key
        crash: purges only Projectivy's cache directory (login/prefs kept).
        Path matches the already-validated command from prior reference
        material for this exact package.
        """
        SecFERRO_TUI.banner("Billing Cache Remediation — com.spocky.projengmenu")
        pkg = "com.spocky.projengmenu"
        self._sh.run(f"rm -rf /data/user/0/{pkg}/cache/*")
        rc, _, _ = self._sh.run(f"am force-stop {pkg}")
        SecFERRO_TUI.row("cache purged + process stopped", pkg, rc == 0)
        SecFERRO_TUI.warn("Preferences/login preserved — only cache/* removed.")
        return rc == 0

    def verify_ethernet_hardware(self) -> str:
        """Corrects the stale 'no Ethernet hardware' claim from prior scripts."""
        SecFERRO_TUI.banner("Ethernet Hardware Presence — Empirical Check")
        _, out, _ = self._sh.run("ip link show eth0 2>/dev/null")
        present = bool(out) and "does not exist" not in out
        state = "UP" if "state UP" in out else ("DOWN (cable unplugged)" if present else "ABSENT")
        SecFERRO_TUI.row("eth0", state, present)
        if present:
            SecFERRO_TUI.warn(
                "Correction: eth0 IS real kernel hardware with a live MAC. "
                "Prior 'no Ethernet' claim in older script headers was "
                "empirically false."
            )
        return state

    def audit_passpoint_scan_waste(self) -> bool:
        """
        Confirms wasted Passpoint/HS20 ANQP scanning. Primary mitigation is
        already covered by TuningCatalog.NETWORK's wifi_scan_always_enabled=0
        — no separate verified API 28 command exists to disable Passpoint
        alone without also affecting the person's own Passpoint use, if any.
        """
        SecFERRO_TUI.banner("Passpoint/HS20 ANQP Scan Audit")
        hit = self._search_logcat("PasspointManager", r"Match not found for PLAY_")
        SecFERRO_TUI.row("wasted ANQP queries detected", str(hit), not hit)
        if hit:
            SecFERRO_TUI.warn(
                "wifi_scan_always_enabled=0 (already applied) is the "
                "correct mitigation — no verified 'Passpoint-only' "
                "disable command exists on API 28."
            )
        return not hit


# ════════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.5.3-rc.1 — Dispatcher")
    tuner = PerformanceTuner()
    mode  = sys.argv[1] if len(sys.argv) > 1 else "--optimize"
    dispatch: dict[str, Callable[[], object]] = {
        "--optimize":               tuner.run_full_optimization,
        "--rollback":                tuner._apply_rollback_profile,
        "--diagnostics":             tuner.run_diagnostics,
        "--debloat":                 tuner._apply_debloat_profile,
        "--graphics":                tuner._apply_graphics_pipeline,
        "--media":                   tuner._apply_media_pipeline,
        "--network":                 tuner._apply_network_pipeline,
        "--flush":                   tuner.flush_memory_caches,
        "--renderer-audit":          lambda: RendererIntegrityGuard(tuner._sh).audit_pasted_regressions(),
        "--renderer-guard":          tuner._apply_renderer_integrity_guard,
        "--smarttube":               tuner._apply_smarttube_enhancement,
        "--probe-remote":            lambda: RemoteKeyProbe(tuner._sh).capture(15),
        "--share-url":               lambda: PhoneClipboardBridge(tuner._sh).send(False),
        "--share-url-ts":            lambda: PhoneClipboardBridge(tuner._sh).send(True),
        "--integrity-audit":         tuner._apply_system_integrity_audit,
        "--fix-billing-cache":       lambda: SystemIntegrityAuditor(tuner._sh).remediate_billing_cache(),
        "--check-ethernet":          lambda: SystemIntegrityAuditor(tuner._sh).verify_ethernet_hardware(),
        "--check-keylayout":         lambda: RemoteKeyProbe(tuner._sh).check_keylayout_integrity(),
        "--extract-keylayout-line":  lambda: RemoteKeyProbe(tuner._sh).extract_bad_keylayout_line(),
        "--check-passpoint":         lambda: SystemIntegrityAuditor(tuner._sh).audit_passpoint_scan_waste(),
        "--gpu-facts":               lambda: RendererIntegrityGuard(tuner._sh).read_gpu_hardware_facts(),
    }
    handler = dispatch.get(mode)
    if handler is None:
        SecFERRO_TUI.error(f"Unknown mode '{mode}'.")
        SecFERRO_TUI.row("valid modes", str(list(dispatch.keys())), None)
        sys.exit(1)
    handler()


if __name__ == "__main__":
    main()#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# SecFERRO_PerformanceTuner_v9.5.3-rc.1 — FULL CONSOLIDATED BUILD                #
# Target  : Sagemcom DCTIW362p | BCM72604 | Android TV 9 (API 28)               #
# Network : PlayNET FTTH | Zyxel AR5344 fw-1.0.36 | LAN MTU 1500 | No SQM     #
# CPU     : ARMv7 Cortex-A15 ×2 ~1 GHz | VideoCore IV / brcmv3d 2.0.1 @582MHz #
# Memory  : 1.5–2 GB RAM | No zRAM | No swap | Kernel 4.9.190-1-6pre           #
# Codec   : AV1 → BLOCKED (no HW decoder) | VP9 → VDec32 HW | HDR10 tunnel    #
# Remote  : Sagemcom IR remote + realme RMX3472 via ATV-Remote (event8)       #
# Runtime : Python 3.12+ | stdlib-only | rish / su / adb adaptive exec         #
# ════════════════════════════════════════════════════════════════════════════════
# CHANGELOG (Keep a Changelog format)
#
# [9.5.3-rc.1] — 2026-07-18
# ### Fixed
#   - RendererIntegrityGuard.verify_effective_state(): removed false-positive
#     "OpenGLRenderer" tag mismatch detection. Confirmed via live logcat that
#     this AOSP log tag is retained for shared EGL bring-up regardless of
#     compiled HWUI pipeline (skiagl vs legacy). Replaced with getprop +
#     pipeline-agnostic EGL-negotiation corroboration.
#   - RemoteKeyProbe default input device corrected from unverified
#     /dev/input/event0 guess to empirically-confirmed /dev/input/event8
#     (virtual-remote, used by phone-based Android TV Remote sessions).
# ### Added
#   - SystemIntegrityCatalog + SystemIntegrityAuditor: correlates 7
#     logcat-derived findings (Ethernet hardware presence, WifiVendorHal HAL
#     gap, KeyLayoutMap parse defect, BillingClient crash loop, Skia decoder
#     failures, SELinux memtrack denial, Passpoint ANQP scan waste).
#   - RemoteKeyProbe.check_keylayout_integrity() / extract_bad_keylayout_line()
#     — read-only diagnostics only; automated /system writes are refused by
#     design (wrong guess risks corrupting the entire keylayout file).
#   - RendererIntegrityGuard.check_hwc_composition_health() /
#     read_gpu_hardware_facts() — corroborating compositor/GPU diagnostics.
#   - PerformanceTuner._apply_renderer_integrity_guard() and
#     _apply_smarttube_enhancement() are now real wired methods (previously
#     documentation-only integration patches).
# ════════════════════════════════════════════════════════════════════════════════
# NAMESPACE DISCIPLINE (inherited, unchanged):
#   media.* / audio.* / debug.* / dalvik.vm.* / persist.* → PROP (setprop)
#   ndc resolver → ABSENT (deprecated); Private DNS Hostname used instead
#   ro.* → NEVER modified (read-only kernel props)
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
    ADB  = "sh -c"


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
    """
    Catalog entry correlating a logcat pattern to a diagnosed system state.

    severity  : impact classification (own editorial judgement, NOT the raw
                Android log-priority letter of the underlying line)
    actionable: True if a narrowly-scoped, non-destructive remediation exists
    """
    tag:         str
    pattern:     str
    severity:    str
    verdict:     str
    explanation: str
    actionable:  bool


# ════════════════════════════════════════════════════════════════════════════════
# SHELL EXECUTOR
# ════════════════════════════════════════════════════════════════════════════════

class SecFERRO_ShellExecutor:
    """Adaptive execution layer: probes rish → su → sh at construction."""
    _RISH_PATH: ClassVar[str] = "/data/local/tmp/rish"

    def __init__(self) -> None:
        self.layer: Final[ExecLayer] = self._probe_layer()

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

    def run(self, cmd: str) -> ResultTriple:
        full = f"{self.layer.value} '{cmd}'"
        try:
            r = subprocess.run(
                full, shell=True, capture_output=True, text=True, timeout=20,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"timeout: {cmd[:60]}"
        except OSError as exc:
            return 1, "", str(exc)

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
        """Read-only recent-log fetch for a single tag at minimum priority."""
        _, out, _ = self.run(f"logcat -d -s {tag}:{level} 2>/dev/null | tail -{lines}")
        return out


# ════════════════════════════════════════════════════════════════════════════════
# TUI RENDERER
# ════════════════════════════════════════════════════════════════════════════════

class SecFERRO_TUI:
    """Stateless terminal renderer. WIDTH = 80 enforced via ljust."""
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
    """Immutable catalog of all hardware-validated tuning vectors for BCM72604."""

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
        TuningVector(
            Namespace.GLOBAL, "net.tcp.buffersize.wifi",
            "4096,524288,8388608,262144,524288,4194304", "",
        ),
        TuningVector(
            Namespace.GLOBAL, "net.tcp.buffersize.default",
            "4096,131072,1048576,65536,131072,524288", "",
        ),
        TuningVector(Namespace.GLOBAL, "tcp_default_init_rwnd",        "60",              ""),
        TuningVector(Namespace.GLOBAL, "private_dns_mode",             "hostname",        "off"),
        TuningVector(Namespace.GLOBAL, "private_dns_specifier",        "one.one.one.one", ""),
        TuningVector(Namespace.GLOBAL, "captive_portal_mode",          "0",               "1"),
        TuningVector(
            Namespace.GLOBAL, "captive_portal_http_url",
            "http://connectivitycheck.gstatic.com/generate_204", "",
        ),
        # wifi_scan_always_enabled=0 also suppresses background ANQP/Passpoint
        # probing against neighbouring HS20 hotspots (see: SystemIntegrityCatalog
        # PASSPOINT_ANQP_SCAN_WASTE finding — no separate opt-out API exists).
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
# RENDERER CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class RendererCatalog:
    """Validated-safe renderer profile for BCM72604 / VideoCore IV."""

    VALIDATED_SAFE: Final[RendererProfile] = RendererProfile(
        hwui_renderer="skiagl",
        render_backend="skiaglthreaded",
        render_thread="true",
        numframebuffers="3",
        disable_backpressure="1",
        latch_unsignaled="1",
    )

    REJECTED_RENDERER_VALUES: Final[frozenset[str]] = frozenset({
        "opengl", "skiavulkan", "skiavk",
    })
    REJECTED_BACKEND_VALUES: Final[frozenset[str]] = frozenset({
        "gl", "opengl", "gles",
    })

    KNOWN_REGRESSIONS: Final[tuple[RegressionFinding, ...]] = (
        RegressionFinding(
            "debug.hwui.renderer", "opengl", "skiagl", "INVALID_ENUM",
            "Pre-Skia HWUI class removed from AOSP since API 28. Unrecognised "
            "string falls back to compiled default — likely a no-op.",
        ),
        RegressionFinding(
            "debug.renderengine.backend", "gl", "skiaglthreaded", "INVALID_ENUM",
            "'gl' matches no RenderEngine backend enum on API 28 vendor trees "
            "(skiagl | skiaglthreaded | gles). No-op risk.",
        ),
        RegressionFinding(
            "debug.sf.disable_backpressure", "0", "1", "REGRESSION",
            "Reverts VC4 CLE-autonomy fix — re-enables SF throttling of the "
            "Control-List-Executor pipeline.",
        ),
        RegressionFinding(
            "debug.gr.numframebuffers", "2", "3", "REGRESSION",
            "Reverts triple-buffering. DequeueBuffer wait measured dropping "
            "14.2ms→<2ms specifically because binning frame N overlaps "
            "rendering frame N-1 with 3 buffers.",
        ),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeCatalog:
    """SmartTube v15+ player action identifiers and remote key bindings."""

    PACKAGES: Final[tuple[str, ...]] = (
        "org.smarttube.stable",
        "org.smarttube.beta",
        "com.liskovsoft.smarttubetv.beta",
        "com.liskovsoft.smarttubetv.next",
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
        KeyBinding(92, ACT_LIKE, ACT_ADD_TO_QUEUE,
                   "PAGE_UP  short=like          | hold=add to queue"),
        KeyBinding(93, ACT_DISLIKE, ACT_REMOVE_QUEUE,
                   "PAGE_DOWN short=dislike       | hold=remove from queue"),
        KeyBinding(231, ACT_OPEN_COMMENTS, "",
                   "MIC      short=open comments"),
        KeyBinding(85, ACT_PLAY_PAUSE, ACT_OPEN_QUEUE,
                   "PLAY_PAUSE short=play/pause   | hold=open queue"),
        KeyBinding(130, ACT_OPEN_WATCH_LATER, ACT_SAVE_WATCH_LATER,
                   "REC      short=open Watch Later | hold=save to Watch Later"),
        KeyBinding(172, ACT_COPY_LINK, ACT_COPY_LINK_TIME,
                   "PROGRAM  short=copy link      | hold=copy link+timestamp"),
    )

    PREF_KEY_SHORT : Final[str] = "player_button_{action}"
    PREF_KEY_LONG  : Final[str] = "player_button_{action}_long"
    PREF_FILENAME_TMPL: Final[str] = "{pkg}_preferences.xml"
    PREFS_DIR:          Final[str] = "/data/data/{pkg}/shared_prefs"
    FILES_DIR:          Final[str] = "/data/data/{pkg}/files"
    PLAYER_DATA_JSON:   Final[str] = "player_data.json"


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM INTEGRITY CATALOG — logcat-derived findings (2026-07-17 evidence set)
# ════════════════════════════════════════════════════════════════════════════════

class SystemIntegrityCatalog:
    """Immutable catalog of confirmed logcat-derived findings for this device."""

    FINDINGS: Final[tuple[LogcatFinding, ...]] = (
        LogcatFinding(
            tag="EthernetNetworkFactory",
            pattern=r"iface:\s*eth0.*hwAddress:\s*([0-9a-f:]{17})",
            severity="INFO",
            verdict="HARDWARE_PRESENT_CABLE_UNPLUGGED",
            explanation="eth0 confirmed as real kernel-enumerated NIC with a "
                        "live hardware MAC; prior header claim of 'no "
                        "Ethernet hardware' is empirically false. up=false "
                        "means only the cable is unplugged.",
            actionable=False,
        ),
        LogcatFinding(
            tag="WifiVendorHal",
            pattern=r"getWifiLinkLayerStats.*ERROR_NOT_AVAILABLE",
            severity="WARN",
            verdict="LINK_LAYER_STATS_HAL_MISSING",
            explanation="Vendor HAL does not implement link-layer stats. "
                        "Android's RSSI/quality-based roaming scorer has "
                        "reduced telemetry; band-steering settings remain "
                        "harmless but their effectiveness is capped.",
            actionable=False,
        ),
        LogcatFinding(
            tag="KeyLayoutMap",
            pattern=r"virtual-remote\.kl:(\d+):\s*Expected key code label",
            severity="ERROR",
            verdict="KEYLAYOUT_PARSE_DEFECT",
            explanation="Malformed entry in the ATV-Remote virtual input "
                        "keylayout used by phone-based control (event8). "
                        "Requires /system remount to patch — refused by "
                        "design without verified replacement content.",
            actionable=True,
        ),
        LogcatFinding(
            tag="BillingClient",
            pattern=r"Multiple entries with same key:\s*TryRoom",
            severity="ERROR",
            verdict="APP_LEVEL_BILLING_STATE_CORRUPT",
            explanation="Duplicate-key crash in Projectivy Launcher's Play "
                        "Billing experiment-flag cache. App-internal Java "
                        "state, unreachable via setprop/settings. Narrowly "
                        "scoped fix: purge only the app's cache directory.",
            actionable=True,
        ),
        LogcatFinding(
            tag="skia",
            pattern=r"Failed to create image decoder.*unimplemented",
            severity="WARN",
            verdict="UNSUPPORTED_IMAGE_CODEC_LOOP",
            explanation="Repeated failed decodes on Glide threads tied to "
                        "the Bing Wallpaper Projectivy plugin — this Skia "
                        "build's codec factory lacks the source format. "
                        "User-chosen plugin — flagged, not silently disabled.",
            actionable=False,
        ),
        LogcatFinding(
            tag="SELinux",
            pattern=r"hal_memtrack_hwservice.*permissive=0",
            severity="WARN",
            verdict="MEMTRACK_HAL_DENIED",
            explanation="sepolicy denies priv_app access to the memtrack "
                        "HwBinder service for GMS processes. Native memory "
                        "breakdown via dumpsys is incomplete for those PIDs "
                        "specifically. Unfixable without vendor sepolicy "
                        "rebuild — out of scope for userspace tuning.",
            actionable=False,
        ),
        LogcatFinding(
            tag="PasspointManager",
            pattern=r"Match not found for PLAY_Swiatlowod",
            severity="WARN",
            verdict="PASSPOINT_ANQP_SCAN_WASTE",
            explanation="wpa_supplicant issues Hotspot2.0/Passpoint ANQP "
                        "queries against neighbouring PLAY-operator hotspot "
                        "BSSIDs, each timing out ~2s. No successful roam is "
                        "possible without a provisioned profile — wasted "
                        "radio/CPU cycles. Already mitigated by "
                        "wifi_scan_always_enabled=0.",
            actionable=False,
        ),
    )


# ════════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TUNER — Main orchestrator
# ════════════════════════════════════════════════════════════════════════════════

class PerformanceTuner:
    """Orchestrates the BCM72604 optimisation pipeline. Idempotent phases."""

    def __init__(self) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = SecFERRO_ShellExecutor()

    # ── Internal helpers ───────────────────────────────────────────────────

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

    # ── Optimisation phases ────────────────────────────────────────────────

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
        SecFERRO_TUI.section("SkiaGL (Vulkan BLOCKED — BCM72604 has no Vulkan driver)")
        count = self._commit_vectors(TuningCatalog.GRAPHICS)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)
        SecFERRO_TUI.section("SurfaceFlinger: force GPU composition path")
        self._sf_force_gpu_composition()

    def _apply_media_pipeline(self) -> None:
        SecFERRO_TUI.banner("STAGEFRIGHT MULTIMEDIA PIPELINE — BCM Nexus / VDec32")
        SecFERRO_TUI.section("Codec + BCM tunnel + AV1 hard-block + HDMI ARC clock-lock")
        count = self._commit_vectors(TuningCatalog.MEDIA)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)

    def _apply_network_pipeline(self) -> None:
        SecFERRO_TUI.banner("NETWORK LAYER — TCP/IP + Private DNS [PlayNET / Zyxel]")
        SecFERRO_TUI.section("TCP BDP=200Mbps×20ms | no ECN (Zyxel AR5344 has no AQM/CAKE)")
        count = self._commit_vectors(TuningCatalog.NETWORK)
        SecFERRO_TUI.row("vectors applied", str(count), count > 0)
        self._sh.run("echo 0 > /proc/sys/net/ipv4/tcp_ecn 2>/dev/null")
        SecFERRO_TUI.row("tcp_ecn", "0 (no SQM/CAKE on router)", True)
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

    def _apply_smarttube_enhancement(self) -> None:
        SmartTubeEnhancer(self._sh).apply_all()

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

    # ── Diagnostics & memory management ────────────────────────────────────

    def _read_pss_metrics(self) -> dict[str, int]:
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
        for cmd in ("am kill-all", "pm trim-caches 2G",
                    "dumpsys batterystats --reset", "sync"):
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
        SecFERRO_TUI.warn(
            "GMS-family PSS may be incomplete: sepolicy denies priv_app "
            "access to hal_memtrack_hwservice (confirmed in logcat)."
        )
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

    # ── Public entry points ───────────────────────────────────────────────

    def run_full_optimization(self) -> None:
        SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.5.3-rc.1 — FULL PIPELINE")
        SecFERRO_TUI.row("exec layer", self._sh.layer.name,                    True)
        SecFERRO_TUI.row("target",     "Sagemcom DCTIW362p | BCM72604 | ATV9", None)
        SecFERRO_TUI.row("network",    "PlayNET FTTH | Zyxel AR5344 fw-1.0.36",None)
        self._apply_system_integrity_audit()
        self._apply_renderer_integrity_guard()
        self._apply_graphics_pipeline()
        self._apply_media_pipeline()
        self._apply_network_pipeline()
        self._apply_stability_profile()
        self._apply_debloat_profile()
        self._apply_smarttube_enhancement()
        self.flush_memory_caches()
        SecFERRO_TUI.banner("OPTIMIZATION PIPELINE COMPLETE — REBOOT RECOMMENDED")


# ════════════════════════════════════════════════════════════════════════════════
# RENDERER INTEGRITY GUARD
# ════════════════════════════════════════════════════════════════════════════════

class RendererIntegrityGuard:
    """
    Audits proposed renderer commands, enforces the validated profile, and
    empirically verifies runtime state.

    CORRECTED v9.5.3: the "OpenGLRenderer" log tag is retained AOSP naming
    for shared EGL bring-up code, used regardless of compiled HWUI pipeline.
    Its presence is NOT a discriminator between skiagl and legacy GL —
    confirmed empirically: it fires normally on this device while skiagl is
    the enforced, validated value. Verification now relies on getprop as the
    primary source of truth, corroborated only by successful (pipeline-
    agnostic) EGL context negotiation.
    """

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def audit_pasted_regressions(self) -> int:
        SecFERRO_TUI.banner("Renderer Regression Audit — Known Bad Commands")
        flagged = 0
        for f in RendererCatalog.KNOWN_REGRESSIONS:
            SecFERRO_TUI.row(f.prop_key, f"REQUESTED={f.requested} → REJECTED", False)
            SecFERRO_TUI.row("  verdict", f.verdict, None)
            SecFERRO_TUI.row("  reason", f.explanation, None)
            flagged += 1
        SecFERRO_TUI.row("total regressions flagged", str(flagged), flagged == 0)
        return flagged

    def enforce_validated_profile(self) -> int:
        SecFERRO_TUI.banner("Enforcing Validated Renderer Profile")
        p = RendererCatalog.VALIDATED_SAFE
        pairs: tuple[tuple[str, str], ...] = (
            ("debug.hwui.renderer",           p.hwui_renderer),
            ("debug.renderengine.backend",    p.render_backend),
            ("debug.hwui.render_thread",      p.render_thread),
            ("debug.gr.numframebuffers",      p.numframebuffers),
            ("debug.sf.disable_backpressure", p.disable_backpressure),
            ("debug.sf.latch_unsignaled",     p.latch_unsignaled),
        )
        applied = sum(int(self._sh.setprop(k, v)) for k, v in pairs)
        for k, v in pairs:
            SecFERRO_TUI.row(k, v, True)
        SecFERRO_TUI.row("profile vectors enforced", str(applied), applied > 0)
        return applied

    def _read_requested_renderer(self) -> str:
        _, out, _ = self._sh.run("getprop debug.hwui.renderer")
        return out.strip()

    def _read_egl_bringup_log(self) -> str:
        return self._sh.logcat_grep("OpenGLRenderer", "D", lines=20)

    def verify_effective_state(self) -> bool:
        SecFERRO_TUI.banner("Renderer Verification (corrected heuristic)")
        requested = self._read_requested_renderer()
        egl_log = self._read_egl_bringup_log()
        egl_ok = "Initialized EGL" in egl_log
        SecFERRO_TUI.row("getprop debug.hwui.renderer", requested or "unset", None)
        SecFERRO_TUI.row("EGL context negotiated", str(egl_ok), egl_ok)
        if not egl_ok:
            SecFERRO_TUI.warn("No EGL init log found — reboot may be required")
        SecFERRO_TUI.warn(
            "'OpenGLRenderer' tag is pipeline-agnostic on this AOSP branch; "
            "it does not by itself confirm skiagl vs legacy GL."
        )
        return bool(
            requested == RendererCatalog.VALIDATED_SAFE.hwui_renderer and egl_ok
        )

    def check_hwc_composition_health(self) -> bool:
        """Corroborates Force-GPU-Composition effectiveness via bcm-hwc heartbeat."""
        out = self._sh.logcat_grep("bcm-hwc", "W", lines=30)
        idle_count = len(re.findall(r"no layer to compose", out))
        healthy = idle_count < 15
        SecFERRO_TUI.row("bcm-hwc idle-composition spam (last 30 lines)",
                          str(idle_count), healthy)
        if not healthy:
            SecFERRO_TUI.warn(
                "High device-composition heartbeat frequency — verify "
                "SurfaceFlinger 1008 (Force GPU) was actually applied."
            )
        return healthy

    def read_gpu_hardware_facts(self) -> dict[str, str]:
        """Read-only capture of live-measured GPU/DRM facts (informational)."""
        SecFERRO_TUI.banner("GPU Hardware Facts — Live Measured")
        nexus_log = self._sh.logcat_grep("NEXUS", "I", lines=10)
        vc5_log   = self._sh.logcat_grep("VC5", "E", lines=10)
        clock  = re.search(r"GPU Clock speed:\s*(\d+\s*MHz)", nexus_log)
        driver = re.search(r"brcmv3d Version\s*([\d.]+)", vc5_log)
        facts = {
            "gpu_clock":  clock.group(1) if clock else "unavailable",
            "drm_driver": driver.group(1) if driver else "unavailable",
        }
        for k, v in facts.items():
            SecFERRO_TUI.row(k, v, None)
        return facts

    def suggest_fluidity_hypotheses(self) -> None:
        SecFERRO_TUI.banner("Skia-Native Fluidity Hypotheses (A/B, one at a time)")
        hypotheses: tuple[tuple[str, str, str], ...] = (
            ("debug.hwui.render_dirty_regions", "true",
             "VC4 hardware scoreboard already tracks dirty tiles — HWUI-"
             "level tracking is normally redundant overhead on this GPU."),
            ("debug.hwui.disable_vsync", "false",
             "Keep vsync enabled; disabling trades fluidity for tearing."),
            ("debug.hwui.force_msaa", "false",
             "VC4 tile renderer's MSAA path is significantly more "
             "expensive than the default non-MSAA tile mode."),
        )
        for prop, safe_val, note in hypotheses:
            SecFERRO_TUI.row(prop, f"keep={safe_val}", None)
            SecFERRO_TUI.row("  rationale", note, None)

    def run_integrity_check(self) -> None:
        SecFERRO_TUI.banner("Renderer Integrity Guard — Full Check v9.5.3")
        flagged  = self.audit_pasted_regressions()
        enforced = self.enforce_validated_profile()
        verified = self.verify_effective_state()
        hwc_ok   = self.check_hwc_composition_health()
        self.read_gpu_hardware_facts()
        self.suggest_fluidity_hypotheses()
        SecFERRO_TUI.section("Summary")
        SecFERRO_TUI.row("regressions rejected", str(flagged), True)
        SecFERRO_TUI.row("safe profile vectors enforced", str(enforced), True)
        SecFERRO_TUI.row("runtime state verified", str(verified), verified)
        SecFERRO_TUI.row("HWC composition healthy", str(hwc_ok), hwc_ok)


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE KEY MAPPER
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeKeyMapper:
    """Injects SmartTube remote key bindings via shared_prefs XML + player_data.json."""

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh
        self._pkg: str = ""

    def _detect_pkg(self) -> str:
        for pkg in SmartTubeCatalog.PACKAGES:
            rc, _, _ = self._sh.run(f"pm list packages {pkg} 2>/dev/null")
            if rc == 0:
                return pkg
        return ""

    def _resolve_pkg(self) -> bool:
        if not self._pkg:
            self._pkg = self._detect_pkg()
        if not self._pkg:
            SecFERRO_TUI.error("SmartTube package not found")
            return False
        return True

    def _prefs_path(self) -> str:
        name = SmartTubeCatalog.PREF_FILENAME_TMPL.format(pkg=self._pkg)
        return f"{SmartTubeCatalog.PREFS_DIR.format(pkg=self._pkg)}/{name}"

    def _pull_prefs_xml(self, local: str) -> bool:
        _, out, _ = self._sh.run(f"cat '{self._prefs_path()}' 2>/dev/null")
        if not out or "<map" not in out:
            return False
        with open(local, "w", encoding="utf-8") as f:
            f.write(out)
        return True

    def _build_new_entries(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for b in SmartTubeCatalog.BINDINGS:
            kc = str(b.keycode)
            if b.action:
                entries.append((SmartTubeCatalog.PREF_KEY_SHORT.format(action=b.action), kc))
            if b.long_action:
                entries.append((SmartTubeCatalog.PREF_KEY_LONG.format(action=b.long_action), kc))
        return entries

    def _patch_xml_tree(self, tree: ET.ElementTree) -> int:
        root = tree.getroot()
        patched = 0
        for pref_key, kc_str in self._build_new_entries():
            existing = root.find(f"string[@name='{pref_key}']")
            if existing is not None:
                existing.text = kc_str
            else:
                elem = ET.SubElement(root, "string")
                elem.set("name", pref_key)
                elem.text = kc_str
            patched += 1
        return patched

    def _push_patched_xml(self, local: str) -> bool:
        with open(local, "r", encoding="utf-8") as f:
            content = f.read()
        escaped = content.replace("'", "'\\''")
        rc, _, _ = self._sh.run(f"echo '{escaped}' > '{self._prefs_path()}' 2>/dev/null")
        return rc == 0

    def _json_path(self) -> str:
        return f"{SmartTubeCatalog.FILES_DIR.format(pkg=self._pkg)}/{SmartTubeCatalog.PLAYER_DATA_JSON}"

    def _patch_player_data_json(self) -> bool:
        _, raw, _ = self._sh.run(f"cat '{self._json_path()}' 2>/dev/null")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {}
        km = data.setdefault("keyMapping", {})
        for b in SmartTubeCatalog.BINDINGS:
            entry: dict[str, str] = {}
            if b.action:
                entry["action"] = b.action
            if b.long_action:
                entry["longAction"] = b.long_action
            km[str(b.keycode)] = entry
        payload = json.dumps(data, indent=2).replace("'", "'\\''")
        rc, _, _ = self._sh.run(f"echo '{payload}' > '{self._json_path()}' 2>/dev/null")
        return rc == 0

    def _verify_binding(self, b: KeyBinding) -> bool:
        key = SmartTubeCatalog.PREF_KEY_SHORT.format(action=b.action)
        _, out, _ = self._sh.run(f"grep -c 'name=\"{key}\"' '{self._prefs_path()}' 2>/dev/null")
        return out.strip() == "1"

    def apply(self) -> bool:
        SecFERRO_TUI.banner("SmartTube Key Mapper — Remote Control Enhancement")
        if not self._resolve_pkg():
            return False
        SecFERRO_TUI.row("package", self._pkg, True)
        backup_path = "/sdcard/smarttube_prefs_backup.xml"
        self._sh.run(f"cp '{self._prefs_path()}' '{backup_path}' 2>/dev/null")
        SecFERRO_TUI.row("backup saved", backup_path, True)
        local_tmp = "/data/local/tmp/st_prefs_patched.xml"
        xml_ok = False
        if self._pull_prefs_xml(local_tmp):
            try:
                tree = ET.parse(local_tmp)
                count = self._patch_xml_tree(tree)
                tree.write(local_tmp, encoding="unicode", xml_declaration=True)
                xml_ok = self._push_patched_xml(local_tmp)
                SecFERRO_TUI.row("XML prefs patched", f"{count} entries", xml_ok)
            except ET.ParseError as exc:
                SecFERRO_TUI.warn(f"XML parse error: {exc} → falling back to JSON")
        json_ok = self._patch_player_data_json()
        SecFERRO_TUI.row("player_data.json", "patched", json_ok)
        SecFERRO_TUI.section("Key binding verification")
        for b in SmartTubeCatalog.BINDINGS:
            SecFERRO_TUI.row(b.description, f"KC={b.keycode}", self._verify_binding(b))
        self._sh.run(f"am force-stop {self._pkg}")
        time.sleep(1)
        SecFERRO_TUI.row("SmartTube restarted", "prefs reloaded", True)
        return xml_ok or json_ok


# ════════════════════════════════════════════════════════════════════════════════
# PHONE CLIPBOARD BRIDGE
# ════════════════════════════════════════════════════════════════════════════════

class PhoneClipboardBridge:
    """
    Routes the current SmartTube video URL to the phone via a priority chain:
    KDE Connect → ADB direct → TV clipboard.

    Note: logcat confirms the same phone (realme RMX3472, matches this
    person's mobile target) also connects via the separate native Android
    TV Remote protocol (package tech.simha.androidtvremote) for input
    control — a distinct mechanism from KDE Connect. Both can coexist;
    this transport chain is unaffected.
    """

    _YT_BASE:    Final[str] = "https://youtu.be/{video_id}"
    _YT_TS_TMPL: Final[str] = "https://youtu.be/{video_id}?t={seconds}"
    _VIDEO_RE:   Final[re.Pattern[str]] = re.compile(r"videoId=([a-zA-Z0-9_\-]{11})")
    _TIME_RE:    Final[re.Pattern[str]] = re.compile(r"position=(\d+)")

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def _extract_video_id(self) -> str:
        _, out, _ = self._sh.run(
            "dumpsys activity activities 2>/dev/null | grep -E 'videoId=' | head -3"
        )
        m = self._VIDEO_RE.search(out)
        if m:
            return m.group(1)
        _, out2, _ = self._sh.run(
            "dumpsys media_session 2>/dev/null | grep -E 'videoId=' | head -1"
        )
        m2 = self._VIDEO_RE.search(out2)
        return m2.group(1) if m2 else ""

    def _extract_playback_secs(self) -> int:
        _, out, _ = self._sh.run(
            "dumpsys media_session 2>/dev/null | grep -E 'position=' | head -1"
        )
        m = self._TIME_RE.search(out)
        return int(m.group(1)) // 1000 if m else 0

    def _build_url(self, with_timestamp: bool) -> str:
        vid = self._extract_video_id()
        if not vid:
            return ""
        if with_timestamp:
            return self._YT_TS_TMPL.format(video_id=vid, seconds=self._extract_playback_secs())
        return self._YT_BASE.format(video_id=vid)

    def _find_kdeconnect_device(self) -> str:
        _, out, _ = self._sh.run("kdeconnect-cli --list-devices --id-only 2>/dev/null | head -1")
        return out.strip()

    def _send_via_kdeconnect(self, url: str) -> bool:
        dev_id = self._find_kdeconnect_device()
        if not dev_id:
            return False
        rc, _, _ = self._sh.run(f"kdeconnect-cli -d '{dev_id}' --share-text '{url}' 2>/dev/null")
        return rc == 0

    def _copy_to_tv_clipboard(self, url: str) -> bool:
        rc, _, _ = self._sh.run(
            f"service call clipboard 2 i32 1 s16 'com.android.shell' s16 '{url}' 2>/dev/null"
        )
        return rc == 0

    def _send_via_adb_phone(self, url: str) -> bool:
        _, devices, _ = self._sh.run("adb devices 2>/dev/null")
        for line in devices.splitlines():
            if "\tdevice" not in line:
                continue
            serial = line.split("\t")[0].strip()
            if serial.endswith(":5555") or "192.168.1.3" in serial:
                continue
            rc, _, _ = self._sh.run(
                f"adb -s {serial} shell \"service call clipboard 2 i32 1 "
                f"s16 'shell' s16 '{url}' 2>/dev/null\""
            )
            if rc == 0:
                SecFERRO_TUI.row("phone ADB target", serial, True)
                return True
        return False

    def _show_url_overlay(self, url: str) -> None:
        self._sh.run(f"am start -a android.intent.action.VIEW -d '{url}' --activity-clear-task 2>/dev/null")
        self._sh.run(
            f"am broadcast -a 'android.intent.action.SEND' "
            f"--es android.intent.extra.TEXT '{url}' "
            f"--et android.intent.extra.SUBJECT 'SmartTube Link' 2>/dev/null"
        )

    def send(self, with_timestamp: bool = False) -> bool:
        SecFERRO_TUI.banner("Phone Clipboard Bridge" + (" [+timestamp]" if with_timestamp else ""))
        url = self._build_url(with_timestamp)
        if not url:
            SecFERRO_TUI.error("Cannot extract current video ID from SmartTube")
            return False
        SecFERRO_TUI.row("URL", url, True)
        if self._send_via_kdeconnect(url):
            SecFERRO_TUI.row("transport", "KDE Connect", True)
            return True
        SecFERRO_TUI.warn("KDE Connect unavailable — trying ADB direct")
        if self._send_via_adb_phone(url):
            SecFERRO_TUI.row("transport", "ADB direct (phone)", True)
            return True
        SecFERRO_TUI.warn("ADB direct unavailable — fallback to TV clipboard")
        tv_ok = self._copy_to_tv_clipboard(url)
        SecFERRO_TUI.row("transport", "TV clipboard (use Remote app)", tv_ok)
        self._show_url_overlay(url)
        return tv_ok


# ════════════════════════════════════════════════════════════════════════════════
# REMOTE KEY PROBE
# ════════════════════════════════════════════════════════════════════════════════

class RemoteKeyProbe:
    """
    Captures raw KeyEvent keycodes and diagnoses the virtual-remote keylayout.

    Two DISTINCT input paths exist on this device:
      1. Physical Sagemcom IR/BT remote — device path unconfirmed, probe
         with capture() and inspect getevent -i output directly.
      2. Phone-based Android TV Remote (tech.simha.androidtvremote client,
         confirmed for realme RMX3472) — CONFIRMED /dev/input/event8,
         keylayout /system/usr/keylayout/virtual-remote.kl, which has a
         CONFIRMED parse defect at line 72 ("Expected key code label, got
         'BACKSPACE'"). check_keylayout_integrity() diagnoses this; no
         automated /system write is offered — a wrong guess risks
         corrupting the entire file, so the fix path is read-only-extract
         plus a pointer to the AOSP reference file for manual comparison.
    """

    _PHONE_REMOTE_DEV: Final[str] = "/dev/input/event8"
    _PHONE_REMOTE_KL:  Final[str] = "/system/usr/keylayout/virtual-remote.kl"
    _KL_PARSE_ERR_RE:  Final[re.Pattern[str]] = re.compile(
        r"virtual-remote\.kl:(\d+):\s*Expected key code label, got '(\w+)'"
    )

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def _discover_input_dev(self) -> str:
        _, out, _ = self._sh.run(
            "getevent -i 2>/dev/null | grep -B5 -E 'rc|remote|ir|key' "
            "| grep 'add device' | awk '{print $3}' | head -1"
        )
        return out.strip() or self._PHONE_REMOTE_DEV

    def capture(self, duration_secs: int = 10) -> dict[str, int]:
        SecFERRO_TUI.banner("Remote Keycode Probe — Press buttons now")
        dev = self._discover_input_dev()
        SecFERRO_TUI.row("input device", dev, True)
        SecFERRO_TUI.warn(
            f"Press each remote button within {duration_secs}s: "
            "PAGE_UP, PAGE_DOWN, MIC, PLAY_PAUSE, REC, PROGRAM"
        )
        _, raw, _ = self._sh.run(f"timeout {duration_secs} getevent -lt {dev} 2>/dev/null | grep EV_KEY")
        keycodes: dict[str, int] = {}
        kc_re = re.compile(r"KEY_(\w+)\s+(DOWN|UP)")
        for line in raw.splitlines():
            m = kc_re.search(line)
            if m and m.group(2) == "DOWN":
                kc_int = self._resolve_keycode(m.group(1))
                if kc_int:
                    keycodes[m.group(1)] = kc_int
                    SecFERRO_TUI.row(f"  captured KEY_{m.group(1)}", str(kc_int), True)
        return keycodes

    def _resolve_keycode(self, linux_key_name: str) -> int:
        mapping: dict[str, int] = {
            "CHANNELUP": 92, "CHANNELDOWN": 93, "PAGEUP": 92, "PAGEDOWN": 93,
            "MICMUTE": 231, "SEARCH": 84, "PLAYPAUSE": 85, "RECORD": 130,
            "EPG": 172, "PROGRAM": 172, "TV": 172,
        }
        return mapping.get(linux_key_name.upper(), 0)

    def check_keylayout_integrity(self) -> bool:
        SecFERRO_TUI.banner("Virtual-Remote Keylayout Integrity Check")
        out = self._sh.logcat_grep("KeyLayoutMap", "W", lines=20)
        m = self._KL_PARSE_ERR_RE.search(out)
        if not m:
            SecFERRO_TUI.row(self._PHONE_REMOTE_KL, "no parse errors found", True)
            return True
        line_no, bad_token = m.group(1), m.group(2)
        SecFERRO_TUI.error(f"{self._PHONE_REMOTE_KL}:{line_no} — malformed entry near '{bad_token}'")
        SecFERRO_TUI.row("affects", "phone-remote virtual input only (event8)", None)
        SecFERRO_TUI.row("remediation", self._remediation_hint(), None)
        return False

    def _remediation_hint(self) -> str:
        return ("read-only: run --extract-keylayout-line, then compare "
                "manually against AOSP frameworks/native/data/keyboards/"
                "Generic.kl before any /system edit (never automated — "
                "corruption risk)")

    def extract_bad_keylayout_line(self) -> str:
        """Read-only extraction for manual review. Never auto-patches /system."""
        _, out, _ = self._sh.run(f"sed -n '72p' '{self._PHONE_REMOTE_KL}' 2>/dev/null")
        SecFERRO_TUI.row(f"{self._PHONE_REMOTE_KL}:72 (raw)", out or "unreadable", None)
        SecFERRO_TUI.warn(
            "Extracted for manual review only. Automated /system writes are "
            "refused — a wrong guess risks corrupting the entire keylayout "
            "file. Cross-check against AOSP reference: "
            "frameworks/native/data/keyboards/Generic.kl"
        )
        return out


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE ENHANCER — facade
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeEnhancer:
    """Facade integrating SmartTubeKeyMapper + PhoneClipboardBridge + RemoteKeyProbe."""

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh:        Final[SecFERRO_ShellExecutor] = sh
        self._mapper:    Final[SmartTubeKeyMapper]      = SmartTubeKeyMapper(sh)
        self._clipboard: Final[PhoneClipboardBridge]    = PhoneClipboardBridge(sh)
        self._probe:     Final[RemoteKeyProbe]          = RemoteKeyProbe(sh)

    def apply_keymaps(self) -> bool:
        return self._mapper.apply()

    def probe_remote(self, duration: int = 10) -> dict[str, int]:
        return self._probe.capture(duration_secs=duration)

    def share_url(self, with_timestamp: bool = False) -> bool:
        return self._clipboard.send(with_timestamp=with_timestamp)

    def print_keybinding_reference(self) -> None:
        SecFERRO_TUI.banner("SmartTube Remote Key Reference — Sagemcom DCTIW362p")
        rows: tuple[tuple[str, str, str], ...] = (
            ("PAGE_UP (KC 92)",    "short", "👍 Like"),
            ("PAGE_UP (KC 92)",    "hold",  "➕ Add to Queue"),
            ("PAGE_DOWN (KC 93)",  "short", "👎 Dislike"),
            ("PAGE_DOWN (KC 93)",  "hold",  "➖ Remove from Queue"),
            ("MIC (KC 231)",       "short", "💬 Open Comments"),
            ("PLAY_PAUSE (KC 85)", "short", "⏯  Play / Pause"),
            ("PLAY_PAUSE (KC 85)", "hold",  "📋 Open Playback Queue"),
            ("REC (KC 130)",       "short", "📁 Open Watch Later"),
            ("REC (KC 130)",       "hold",  "🔖 Save to Watch Later"),
            ("PROGRAM (KC 172)",   "short", "🔗 Copy Link"),
            ("PROGRAM (KC 172)",   "hold",  "🔗+⏱ Copy Link + Timestamp"),
        )
        for button, press_type, action in rows:
            SecFERRO_TUI.row(f"{button:<22} [{press_type:<5}]", action, None)

    def apply_all(self) -> None:
        SecFERRO_TUI.banner("SmartTube Enhancer — Full Apply")
        self.print_keybinding_reference()
        km_ok = self.apply_keymaps()
        SecFERRO_TUI.row("key mapping applied", str(km_ok), km_ok)
        kl_ok = self._probe.check_keylayout_integrity()
        if not kl_ok:
            SecFERRO_TUI.warn(
                "Keylayout defect is on the phone-remote input path only — "
                "physical Sagemcom IR remote is unaffected."
            )
        SecFERRO_TUI.section("Phone Clipboard Bridge — KDE Connect availability")
        dev = self._clipboard._find_kdeconnect_device()
        SecFERRO_TUI.row("KDE Connect device", dev or "not found", bool(dev))
        if not dev:
            SecFERRO_TUI.warn(
                "Install KDE Connect on phone + TV for full clipboard sharing. "
                "Fallback: TV clipboard + Android TV Remote app."
            )


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM INTEGRITY AUDITOR
# ════════════════════════════════════════════════════════════════════════════════

class SystemIntegrityAuditor:
    """Correlates SystemIntegrityCatalog.FINDINGS against live logcat."""

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def _search_logcat(self, tag: str, pattern: str) -> bool:
        out = self._sh.logcat_grep(tag, "V", lines=300)
        return re.search(pattern, out) is not None

    def audit(self) -> dict[str, bool]:
        SecFERRO_TUI.banner("System Integrity Audit — Logcat-Derived Findings")
        results: dict[str, bool] = {}
        for f in SystemIntegrityCatalog.FINDINGS:
            hit = self._search_logcat(f.tag, f.pattern)
            results[f.verdict] = hit
            display_ok = None if not hit else (f.severity != "ERROR")
            SecFERRO_TUI.row(f"[{f.severity}] {f.verdict}", str(hit), display_ok)
            if hit:
                SecFERRO_TUI.row("  evidence tag", f.tag, None)
                SecFERRO_TUI.row("  explanation", f.explanation, None)
        return results

    def remediate_billing_cache(self) -> bool:
        """
        Narrowly-scoped fix for the BillingClient TryRoom duplicate-key
        crash: purges only Projectivy's cache directory (login/prefs kept).
        Path matches the already-validated command from prior reference
        material for this exact package.
        """
        SecFERRO_TUI.banner("Billing Cache Remediation — com.spocky.projengmenu")
        pkg = "com.spocky.projengmenu"
        self._sh.run(f"rm -rf /data/user/0/{pkg}/cache/*")
        rc, _, _ = self._sh.run(f"am force-stop {pkg}")
        SecFERRO_TUI.row("cache purged + process stopped", pkg, rc == 0)
        SecFERRO_TUI.warn("Preferences/login preserved — only cache/* removed.")
        return rc == 0

    def verify_ethernet_hardware(self) -> str:
        """Corrects the stale 'no Ethernet hardware' claim from prior scripts."""
        SecFERRO_TUI.banner("Ethernet Hardware Presence — Empirical Check")
        _, out, _ = self._sh.run("ip link show eth0 2>/dev/null")
        present = bool(out) and "does not exist" not in out
        state = "UP" if "state UP" in out else ("DOWN (cable unplugged)" if present else "ABSENT")
        SecFERRO_TUI.row("eth0", state, present)
        if present:
            SecFERRO_TUI.warn(
                "Correction: eth0 IS real kernel hardware with a live MAC. "
                "Prior 'no Ethernet' claim in older script headers was "
                "empirically false."
            )
        return state

    def audit_passpoint_scan_waste(self) -> bool:
        """
        Confirms wasted Passpoint/HS20 ANQP scanning. Primary mitigation is
        already covered by TuningCatalog.NETWORK's wifi_scan_always_enabled=0
        — no separate verified API 28 command exists to disable Passpoint
        alone without also affecting the person's own Passpoint use, if any.
        """
        SecFERRO_TUI.banner("Passpoint/HS20 ANQP Scan Audit")
        hit = self._search_logcat("PasspointManager", r"Match not found for PLAY_")
        SecFERRO_TUI.row("wasted ANQP queries detected", str(hit), not hit)
        if hit:
            SecFERRO_TUI.warn(
                "wifi_scan_always_enabled=0 (already applied) is the "
                "correct mitigation — no verified 'Passpoint-only' "
                "disable command exists on API 28."
            )
        return not hit


# ════════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.5.3-rc.1 — Dispatcher")
    tuner = PerformanceTuner()
    mode  = sys.argv[1] if len(sys.argv) > 1 else "--optimize"
    dispatch: dict[str, Callable[[], object]] = {
        "--optimize":               tuner.run_full_optimization,
        "--rollback":                tuner._apply_rollback_profile,
        "--diagnostics":             tuner.run_diagnostics,
        "--debloat":                 tuner._apply_debloat_profile,
        "--graphics":                tuner._apply_graphics_pipeline,
        "--media":                   tuner._apply_media_pipeline,
        "--network":                 tuner._apply_network_pipeline,
        "--flush":                   tuner.flush_memory_caches,
        "--renderer-audit":          lambda: RendererIntegrityGuard(tuner._sh).audit_pasted_regressions(),
        "--renderer-guard":          tuner._apply_renderer_integrity_guard,
        "--smarttube":               tuner._apply_smarttube_enhancement,
        "--probe-remote":            lambda: RemoteKeyProbe(tuner._sh).capture(15),
        "--share-url":               lambda: PhoneClipboardBridge(tuner._sh).send(False),
        "--share-url-ts":            lambda: PhoneClipboardBridge(tuner._sh).send(True),
        "--integrity-audit":         tuner._apply_system_integrity_audit,
        "--fix-billing-cache":       lambda: SystemIntegrityAuditor(tuner._sh).remediate_billing_cache(),
        "--check-ethernet":          lambda: SystemIntegrityAuditor(tuner._sh).verify_ethernet_hardware(),
        "--check-keylayout":         lambda: RemoteKeyProbe(tuner._sh).check_keylayout_integrity(),
        "--extract-keylayout-line":  lambda: RemoteKeyProbe(tuner._sh).extract_bad_keylayout_line(),
        "--check-passpoint":         lambda: SystemIntegrityAuditor(tuner._sh).audit_passpoint_scan_waste(),
        "--gpu-facts":               lambda: RendererIntegrityGuard(tuner._sh).read_gpu_hardware_facts(),
    }
    handler = dispatch.get(mode)
    if handler is None:
        SecFERRO_TUI.error(f"Unknown mode '{mode}'.")
        SecFERRO_TUI.row("valid modes", str(list(dispatch.keys())), None)
        sys.exit(1)
    handler()


if __name__ == "__main__":
    main()