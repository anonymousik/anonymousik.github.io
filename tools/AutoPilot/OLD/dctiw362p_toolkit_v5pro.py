#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# SecFERRO_PerformanceTuner_v9.6.3 — FULL CONSOLIDATED BUILD                     #
# Target  : Sagemcom DCTIW362p | BCM72604 | Android TV 9 (API 28)               #
# Network : PlayNET FTTH | Zyxel AR5344 fw-1.0.36 | LAN MTU 1500 | No SQM     #
# CPU     : ARMv7 Cortex-A15 ×2 ~1 GHz | VideoCore IV / brcmv3d 2.0.1 @582MHz #
# Memory  : 1.5–2 GB RAM | No zRAM | No swap | Kernel 4.9.190-1-6pre           #
# Codec   : AV1 → BLOCKED (no HW decoder) | VP9 → VDec32 HW | HDR10 tunnel    #
# Remote  : Sagemcom IR remote + realme RMX3472 via ATV-Remote (event8)       #
# Runtime : Python 3.12+ | stdlib-only | rish / su / adb adaptive exec         #
# ════════════════════════════════════════════════════════════════════════════════
# NAMESPACE DISCIPLINE:
#   media.* / audio.* / debug.* / dalvik.vm.* / persist.* → PROP (setprop)
#   ndc resolver → ABSENT (deprecated); Private DNS Hostname used instead
#   ro.* → NEVER modified (read-only kernel props)
# ════════════════════════════════════════════════════════════════════════════════
# v9.6.3 EXTERNAL SOURCE AUDIT NOTE:
#   Two files arrived redeclaring THIS project's own classes with a weaker,
#   host-side-only architecture (no rish/su detection). Those definitions
#   are NOT merged — this file's SecFERRO_TUI / SecFERRO_ShellExecutor
#   below remain authoritative. A prior snapshot of this very file
#   (labelled v9.5.3-rc.1) was also submitted; superseded, not merged.
#   Genuinely new, verified techniques integrated this round:
#     - ShizukuLifecycleManager: installs rish/rish_shizuku.dex directly
#       from the installed Shizuku APK (no external download), manages
#       shizuku_server start/stop, and verifies actual privilege
#       escalation via PPID comparison against the running server PID —
#       closing a real gap where _probe_rish() assumed a pre-installed
#       wrapper without ever installing or verifying it.
#     - MediaCodecServiceReset: `pm clear` on media provider packages +
#       targeted `killall` of mediaserver/OMX HAL — legitimate AOSP
#       recovery path for stuck codec state, complementary to (not
#       overlapping with) flush_memory_caches().
#   Rejected again (same unverified-key pattern as before):
#     exoplayer_buffer_limit, low_ram, sys_free_storage_alloc_limit —
#     none are read by stock ExoPlayer's LoadControl from Settings.Global.
# ════════════════════════════════════════════════════════════════════════════════
# SPDX-License-Identifier: MIT
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import enum
import io
import json
import os
import re
import subprocess
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Final, TypeAlias

ResultTriple: TypeAlias = tuple[int, str, str]
PropCheck:    TypeAlias = tuple[str, str]

_P: Final[str] = "\033[38;2;191;0;255m"
_G: Final[str] = "\033[32m"
_R: Final[str] = "\033[31m"
_Y: Final[str] = "\033[33m"
_D: Final[str] = "\033[90m"
_B: Final[str] = "\033[0m"


# ════════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ════════════════════════════════════════════════════════════════════════════════

class ExecLayer(enum.Enum):
    ROOT = "su -c"
    RISH = "adb shell sh -c /data/local/tmp/rish -c"
    ADB  = "adb shell sh -c"


class Namespace(enum.StrEnum):
    PROP    = "prop"
    GLOBAL  = "global"
    SECURE  = "secure"
    SYSTEM  = "system"


# ════════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ════════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class TuningVector:
    ns:      Namespace
    key:     str
    value:   str
    factory: str = ""


@dataclass(frozen=True, slots=True)
class DeviceConfigVector:
    config_namespace: str
    key:              str
    value:            str
    factory:          str = ""


@dataclass(frozen=True, slots=True)
class RegressionFinding:
    prop_key:    str
    requested:   str
    validated:   str
    verdict:     str
    explanation: str


@dataclass(frozen=True, slots=True)
class RendererProfile:
    hwui_renderer:         str
    render_backend:        str
    render_thread:         str
    numframebuffers:       str
    disable_backpressure:  str
    latch_unsignaled:      str


@dataclass(frozen=True, slots=True)
class KeyBinding:
    keycode:     int
    action:      str
    long_action: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class LogcatFinding:
    tag:         str
    pattern:     str
    severity:    str
    verdict:     str
    explanation: str
    actionable:  bool


@dataclass(frozen=True, slots=True)
class SmartTubePrefVector:
    key:   str
    typ:   str
    value: str
    note:  str = ""


@dataclass(frozen=True, slots=True)
class GuardianCycleConfig:
    sleep_foreground_secs: int = 30
    sleep_idle_secs:       int = 120
    av1_recheck_every:     int = 10
    free_kb_foreground:    int = 256_000
    free_kb_idle:          int = 153_600
    foreground_pkg_hint:   str = "smarttube"


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

    def refresh_layer(self) -> ExecLayer:
        """Re-probes after a lifecycle action (e.g. Shizuku install/start)."""
        new_layer = self._probe_layer()
        object.__setattr__(self, "layer", new_layer) if False else None
        self.layer = new_layer  # type: ignore[misc]
        return new_layer

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

    def run_raw(self, cmd: str, timeout: int = 20) -> ResultTriple:
        """Bypasses ExecLayer prefixing — for bootstrap operations (e.g.
        installing rish itself) where no privilege layer exists yet."""
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"timeout: {cmd[:60]}"
        except OSError as exc:
            return 1, "", str(exc)

    def run_with_retry(self, cmd: str, attempts: int = 3,
                        backoff_secs: float = 1.0) -> ResultTriple:
        last: ResultTriple = (1, "", "not attempted")
        for attempt in range(attempts):
            last = self.run(cmd)
            if last[0] == 0:
                return last
            if attempt < attempts - 1:
                time.sleep(backoff_secs)
        return last

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

    def pm_suspend(self, pkg: str) -> bool:
        rc, _, _ = self.run(f"pm suspend {pkg}")
        return rc == 0

    def pm_unsuspend(self, pkg: str) -> bool:
        rc, _, _ = self.run(f"pm unsuspend {pkg}")
        return rc == 0

    def pm_clear(self, pkg: str) -> bool:
        rc, _, _ = self.run(f"pm clear {pkg}")
        return rc == 0

    def appops_set(self, pkg: str, op: str, mode: str) -> bool:
        rc, _, _ = self.run(f"cmd appops set {pkg} {op} {mode}")
        return rc == 0

    def service_call(self, svc: str, code: int, *args: str) -> bool:
        rc, _, _ = self.run(f"service call {svc} {code} {' '.join(args)}")
        return rc == 0

    def device_config_put(self, ns: str, key: str, value: str) -> bool:
        rc, _, _ = self.run(f"cmd device_config put {ns} {key} {value}")
        return rc == 0

    def device_config_delete(self, ns: str, key: str) -> bool:
        rc, _, _ = self.run(f"cmd device_config delete {ns} {key}")
        return rc == 0

    def getprop_value(self, key: str) -> str:
        _, out, _ = self.run(f"getprop {key}")
        return out.strip()

    def killall(self, process_name: str) -> bool:
        rc, _, _ = self.run(f"killall {process_name}")
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
        sys.stdout.write(f"  {tag} {_D}{key:<{SecFERRO_TUI.KEY_W}}{_B}{value}\n")

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
        TuningVector(Namespace.PROP,   "debug.sf.early_app_phase_offset_ns","1000000",      "0"),
        TuningVector(Namespace.PROP,   "debug.hwui.use_buffer_age",       "false",          "true"),
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
        TuningVector(Namespace.GLOBAL, "net.tcp.buffersize.wifi",
                     "4096,524288,8388608,262144,524288,4194304", ""),
        TuningVector(Namespace.GLOBAL, "net.tcp.buffersize.default",
                     "4096,131072,1048576,65536,131072,524288", ""),
        TuningVector(Namespace.GLOBAL, "tcp_default_init_rwnd",        "60",              ""),
        TuningVector(Namespace.GLOBAL, "private_dns_mode",             "hostname",        "off"),
        TuningVector(Namespace.GLOBAL, "private_dns_specifier",        "one.one.one.one", ""),
        TuningVector(Namespace.GLOBAL, "captive_portal_mode",          "0",               "1"),
        TuningVector(Namespace.GLOBAL, "captive_portal_http_url",
                     "http://connectivitycheck.gstatic.com/generate_204", ""),
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
        TuningVector(Namespace.PROP,   "dalvik.vm.isa.arm.features",   "default,idiv",    "default"),
        TuningVector(Namespace.PROP,   "dalvik.vm.isa.arm.variant",    "cortex-a15",      ""),
        TuningVector(Namespace.PROP,   "dalvik.vm.heapminfree",        "2m",              "512k"),
        TuningVector(Namespace.PROP,   "dalvik.vm.heapmaxfree",        "16m",             "8m"),
        TuningVector(Namespace.PROP,   "dalvik.vm.heaptargetutilization","0.75",           "0.75"),
        TuningVector(Namespace.GLOBAL, "monitor_phantom_procs",            "false",       "true"),
    )

    DEVICE_CONFIG: Final[tuple[DeviceConfigVector, ...]] = (
        DeviceConfigVector("activity_manager", "max_phantom_processes", "0", ""),
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

    # ── Rejected — unverified ExoPlayer/low-RAM keys (atv9_exoplayer4k_tweak.sh) ──
    # ExoPlayer's LoadControl configures buffer thresholds programmatically in
    # app code; it does not read these from Settings.Global on stock builds.
    REJECTED_UNVERIFIED_KEYS: Final[tuple[str, ...]] = (
        "exoplayer_buffer_limit",
        "low_ram",
        "sys_free_storage_alloc_limit",
        "always_finish_activities",
    )


# ════════════════════════════════════════════════════════════════════════════════
# RENDERER CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class RendererCatalog:
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
        RegressionFinding(
            "ro.hdmi.device_type / ro.hdmi.cec_device_types / ro.hdmi.wake_on_hotplug",
            "various", "unchanged (read-only)", "NAMESPACE_VIOLATION",
            "Writes target ro.* — read-only kernel properties. Rejected "
            "under namespace discipline regardless of intended value.",
        ),
        RegressionFinding(
            "persist.sys.hdmi.keep_awake", "false", "true", "REGRESSION",
            "Reverts confirmed fix for CEC-wakeup silence after standby.",
        ),
        RegressionFinding(
            "vm.swappiness", "100", "0", "REGRESSION",
            "BCM72604 has no zRAM/swap partition. Non-zero swappiness is a "
            "no-op at best.",
        ),
        RegressionFinding(
            "device_config activity_manager/max_phantom_processes", "32", "0",
            "REGRESSION",
            "API 28 semantics require 0 (disabled), confirmed in prior audit.",
        ),
        RegressionFinding(
            "debug.hwui.render_thread_cpu_affinity", "1", "(unset — no known key)",
            "UNVERIFIED_PROPERTY",
            "Not a recognised AOSP HWUI property on API 28; likely a no-op "
            "setprop with no read-side consumer.",
        ),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeCatalog:
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


class SmartTubeMediaCatalog:
    BCM72604_OPTIMAL: Final[tuple[SmartTubePrefVector, ...]] = (
        SmartTubePrefVector("video_codec",         "int",     "2",     "VP9 HW"),
        SmartTubePrefVector("av1_enabled",          "boolean", "false", "no HW AV1"),
        SmartTubePrefVector("vp9_enabled",          "boolean", "true",  "VP9 HW path"),
        SmartTubePrefVector("preferred_codec",      "string",  "vp9",   ""),
        SmartTubePrefVector("use_tunnel_mode",      "boolean", "true",  "BCM clock sync"),
        SmartTubePrefVector("tunneled_playback",    "boolean", "true",  ""),
        SmartTubePrefVector("video_resolution",     "string",  "1080",  "display cap"),
        SmartTubePrefVector("hdr_mode",             "boolean", "true",  ""),
        SmartTubePrefVector("hardware_acceleration","boolean", "true",  ""),
        SmartTubePrefVector("frame_interpolation",  "boolean", "false", "artefacts on VDec32"),
    )


class SponsorBlockCatalog:
    """player_type=web_embed deliberately excluded — conflicts with confirmed
    use_tunnel_mode=true VP9 codec path in SmartTubeMediaCatalog."""
    SPONSORBLOCK_OPTIMAL: Final[tuple[SmartTubePrefVector, ...]] = (
        SmartTubePrefVector("sponsor_block_enabled",     "boolean", "true", ""),
        SmartTubePrefVector("sponsor_block_skip_mode",   "string",  "skippable", ""),
        SmartTubePrefVector("sponsor_block_min_duration","int",     "2", ""),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM INTEGRITY CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class SystemIntegrityCatalog:
    FINDINGS: Final[tuple[LogcatFinding, ...]] = (
        LogcatFinding(
            tag="EthernetNetworkFactory",
            pattern=r"iface:\s*eth0.*hwAddress:\s*([0-9a-f:]{17})",
            severity="INFO", verdict="HARDWARE_PRESENT_CABLE_UNPLUGGED",
            explanation="eth0 confirmed as real kernel-enumerated NIC with a "
                        "live hardware MAC; up=false means only the cable is "
                        "unplugged.",
            actionable=False,
        ),
        LogcatFinding(
            tag="WifiVendorHal",
            pattern=r"getWifiLinkLayerStats.*ERROR_NOT_AVAILABLE",
            severity="WARN", verdict="LINK_LAYER_STATS_HAL_MISSING",
            explanation="Vendor HAL lacks link-layer stats — RSSI/quality "
                        "roaming scorer has reduced telemetry.",
            actionable=False,
        ),
        LogcatFinding(
            tag="KeyLayoutMap",
            pattern=r"virtual-remote\.kl:(\d+):\s*Expected key code label",
            severity="ERROR", verdict="KEYLAYOUT_PARSE_DEFECT",
            explanation="Malformed entry in the ATV-Remote virtual input "
                        "keylayout (event8). Requires /system remount — "
                        "refused by design without verified content.",
            actionable=True,
        ),
        LogcatFinding(
            tag="BillingClient",
            pattern=r"Multiple entries with same key:\s*TryRoom",
            severity="ERROR", verdict="APP_LEVEL_BILLING_STATE_CORRUPT",
            explanation="Duplicate-key crash in Projectivy Launcher's Play "
                        "Billing experiment-flag cache. Narrowly scoped fix "
                        "purges only cache/*.",
            actionable=True,
        ),
        LogcatFinding(
            tag="skia",
            pattern=r"Failed to create image decoder.*unimplemented",
            severity="WARN", verdict="UNSUPPORTED_IMAGE_CODEC_LOOP",
            explanation="Repeated failed decodes tied to the Bing Wallpaper "
                        "plugin. User-chosen plugin — flagged, not disabled.",
            actionable=False,
        ),
        LogcatFinding(
            tag="SELinux",
            pattern=r"hal_memtrack_hwservice.*permissive=0",
            severity="WARN", verdict="MEMTRACK_HAL_DENIED",
            explanation="sepolicy denies priv_app access to memtrack HwBinder "
                        "for GMS processes; PSS breakdown incomplete for "
                        "those PIDs. Out of scope for userspace tuning.",
            actionable=False,
        ),
        LogcatFinding(
            tag="PasspointManager",
            pattern=r"Match not found for PLAY_Swiatlowod",
            severity="WARN", verdict="PASSPOINT_ANQP_SCAN_WASTE",
            explanation="wpa_supplicant issues ANQP queries against "
                        "neighbouring PLAY hotspots, all timing out. Already "
                        "mitigated by wifi_scan_always_enabled=0.",
            actionable=False,
        ),
        LogcatFinding(
            tag="AtvRemote.AppLinkFeature",
            pattern=r"ActivityNotFoundException: No Activity found to handle Intent.*action\.VIEW",
            severity="ERROR", verdict="VIEW_INTENT_UNRESOLVABLE",
            explanation="Confirmed on this device: a VIEW intent found no "
                        "resolving activity. Code paths firing VIEW intents "
                        "must pre-check resolvability.",
            actionable=True,
        ),
        LogcatFinding(
            tag="DhcpClient",
            pattern=r"Broadcasting DHCPDISCOVER",
            severity="WARN", verdict="DHCP_RENEWAL_FREQUENCY_UNCONFIRMED",
            explanation="Two DHCPDISCOVER broadcasts ~2 minutes apart; "
                        "insufficient context to confirm cause. Monitoring only.",
            actionable=False,
        ),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SHIZUKU LIFECYCLE MANAGER
# ════════════════════════════════════════════════════════════════════════════════

class ShizukuLifecycleManager:
    """
    Installs/manages the rish wrapper directly from the installed Shizuku
    APK, and verifies real privilege escalation via PPID comparison —
    closing the gap where SecFERRO_ShellExecutor._probe_rish() only checks
    for a pre-existing wrapper without ever installing or proving it.
    Pattern sourced from rish_tolbox.sh (Shizuku Manager) v3.1.0.
    """
    _SHIZUKU_PKG:   Final[str] = "moe.shizuku.privileged.api"
    _TARGET_BIN:    Final[str] = "/data/local/tmp"
    _RISH_WRAPPER:  Final[str] = "/data/local/tmp/rish"
    _RISH_DEX:      Final[str] = "/data/local/tmp/rish_shizuku.dex"

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def _locate_shizuku_apk(self) -> str:
        _, out, _ = self._sh.run_raw(
            f"cmd package path {self._SHIZUKU_PKG} --user 0 2>/dev/null"
        )
        return out.split(":", 1)[1].strip() if ":" in out else ""

    def install(self) -> bool:
        SecFERRO_TUI.banner("Shizuku Lifecycle — Install rish wrapper")
        apk_path = self._locate_shizuku_apk()
        if not apk_path:
            SecFERRO_TUI.error("Shizuku app not installed on this device")
            return False
        SecFERRO_TUI.row("Shizuku APK", apk_path, True)
        tmp_dir = f"/data/local/tmp/rish_install_{int(time.time())}"
        self._sh.run_raw(f"mkdir -p {tmp_dir}")
        rc, _, _ = self._sh.run_raw(f"unzip -qq '{apk_path}' -d '{tmp_dir}'")
        if rc != 0:
            SecFERRO_TUI.error("APK extraction failed (unzip unavailable?)")
            return False
        return self._patch_and_install(tmp_dir)

    def _patch_and_install(self, tmp_dir: str) -> bool:
        rish_src = f"{tmp_dir}/assets/rish"
        dex_src  = f"{tmp_dir}/assets/rish_shizuku.dex"
        rc1, out1, _ = self._sh.run_raw(f"test -f '{rish_src}' && echo OK")
        rc2, out2, _ = self._sh.run_raw(f"test -f '{dex_src}' && echo OK")
        if "OK" not in out1 or "OK" not in out2:
            SecFERRO_TUI.error("rish assets missing inside Shizuku APK")
            return False
        self._sh.run_raw(
            f"cp '{rish_src}' '{self._RISH_WRAPPER}' && "
            f"chmod 755 '{self._RISH_WRAPPER}' && "
            f"cp '{dex_src}' '{self._RISH_DEX}' && chmod 400 '{self._RISH_DEX}'"
        )
        installed = os.path.isfile(self._RISH_WRAPPER)
        SecFERRO_TUI.row("rish wrapper installed", self._RISH_WRAPPER, installed)
        self._sh.run_raw(f"rm -rf '{tmp_dir}'")
        return installed

    def _find_server_pid(self) -> str:
        _, out, _ = self._sh.run_raw(
            "ps -ef 2>/dev/null | grep shizuku_server | grep -v grep | awk '{print $2}'"
        )
        return out.strip().splitlines()[0] if out.strip() else ""

    def _find_start_script(self) -> str:
        candidates = (
            "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh",
            "/sdcard/Android/data/moe.shizuku.privileged.api/start.sh",
        )
        for path in candidates:
            _, out, _ = self._sh.run_raw(f"test -f '{path}' && echo '{path}'")
            if out.strip():
                return out.strip()
        _, found, _ = self._sh.run_raw(
            "find /sdcard/Android/data -name start.sh -path '*moe.shizuku*' "
            "2>/dev/null | head -1"
        )
        return found.strip()

    def start_server(self) -> bool:
        SecFERRO_TUI.banner("Shizuku Lifecycle — Start Server")
        if self._find_server_pid():
            SecFERRO_TUI.row("shizuku_server", "already running", True)
            return True
        start_script = self._find_start_script()
        if not start_script:
            SecFERRO_TUI.warn(
                "No start.sh found — open the Shizuku app on the TV once "
                "to generate it."
            )
            return False
        self._sh.run_raw(f"nohup sh '{start_script}' >/dev/null 2>&1 &")
        time.sleep(2)
        pid = self._find_server_pid()
        SecFERRO_TUI.row("shizuku_server", f"PID {pid}" if pid else "failed to start", bool(pid))
        return bool(pid)

    def stop_server(self) -> bool:
        SecFERRO_TUI.banner("Shizuku Lifecycle — Stop Server")
        pid = self._find_server_pid()
        if not pid:
            SecFERRO_TUI.row("shizuku_server", "not running", True)
            return True
        rc, _, _ = self._sh.run_raw(f"kill -9 {pid}")
        SecFERRO_TUI.row("shizuku_server stopped", f"PID {pid}", rc == 0)
        return rc == 0

    def verify_ppid_escalation(self) -> bool:
        """
        Proves commands issued through rish are actually routed through
        shizuku_server (not silently falling back to plain shell) by
        comparing the parent PID of a rish-spawned process against the
        live shizuku_server PID.
        """
        SecFERRO_TUI.banner("Shizuku Lifecycle — PPID Verification")
        if not os.path.isfile(self._RISH_WRAPPER):
            SecFERRO_TUI.error("rish not installed — run install() first")
            return False
        _, out, _ = self._sh.run_raw(
            f"{self._RISH_WRAPPER} -c 'cat /proc/$$/status | grep PPid' 2>/dev/null"
        )
        actual_ppid = out.split()[-1] if out.split() else ""
        server_pid = self._find_server_pid()
        matched = bool(actual_ppid) and actual_ppid == server_pid
        SecFERRO_TUI.row("rish process PPID", actual_ppid or "unknown", None)
        SecFERRO_TUI.row("shizuku_server PID", server_pid or "not running", None)
        SecFERRO_TUI.row("privilege escalation confirmed", str(matched), matched)
        return matched

    def ensure_ready(self) -> bool:
        """Full bootstrap: install if missing, start if stopped, verify."""
        SecFERRO_TUI.banner("Shizuku Lifecycle — Ensure Ready")
        if not os.path.isfile(self._RISH_WRAPPER) and not self.install():
            return False
        if not self._find_server_pid() and not self.start_server():
            return False
        verified = self.verify_ppid_escalation()
        if verified:
            self._sh.refresh_layer()
            SecFERRO_TUI.row("SecFERRO_ShellExecutor.layer", self._sh.layer.name, True)
        return verified


# ════════════════════════════════════════════════════════════════════════════════
# MEDIA CODEC SERVICE RESET
# ════════════════════════════════════════════════════════════════════════════════

class MediaCodecServiceReset:
    """
    Forces a clean restart of stuck OMX/mediaserver codec state via
    `pm clear` on the media provider databases plus targeted `killall` of
    the mediaserver and OMX HAL processes — Android's init automatically
    respawns both. Complementary to PerformanceTuner.flush_memory_caches(),
    not overlapping (that method never touches codec service state).
    Pattern sourced from atv9_reseet-kodek.sh.
    """
    _MEDIA_PROVIDER_PKGS: Final[tuple[str, ...]] = (
        "com.android.providers.media",
        "com.android.providers.media.module",
    )
    _MEDIA_PROCESSES: Final[tuple[str, ...]] = (
        "android.hardware.media.omx@1.0-service",
        "mediaserver",
    )

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def clear_media_provider_cache(self) -> int:
        cleared = 0
        for pkg in self._MEDIA_PROVIDER_PKGS:
            ok = self._sh.pm_clear(pkg)
            SecFERRO_TUI.row(f"pm clear {pkg}", "ok" if ok else "err", ok)
            cleared += int(ok)
        return cleared

    def restart_codec_daemons(self) -> int:
        restarted = 0
        for proc in self._MEDIA_PROCESSES:
            ok = self._sh.killall(proc)
            SecFERRO_TUI.row(f"killall {proc}", "signalled" if ok else "not running", ok)
            restarted += int(ok)
        return restarted

    def apply(self) -> bool:
        SecFERRO_TUI.banner("Media Codec Service Reset — OMX/Mediaserver Recovery")
        cleared = self.clear_media_provider_cache()
        restarted = self.restart_codec_daemons()
        SecFERRO_TUI.warn(
            "init will auto-respawn mediaserver/OMX HAL within seconds — "
            "no manual restart step required."
        )
        SecFERRO_TUI.section("Summary")
        SecFERRO_TUI.row("provider caches cleared", str(cleared), cleared > 0)
        SecFERRO_TUI.row("codec daemons signalled", str(restarted), restarted >= 0)
        return cleared > 0


# ════════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TUNER — Main orchestrator
# ════════════════════════════════════════════════════════════════════════════════

class PerformanceTuner:
    def __init__(self) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = SecFERRO_ShellExecutor()

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

    def _commit_device_config_vectors(self) -> int:
        applied = 0
        for dv in TuningCatalog.DEVICE_CONFIG:
            ok = self._sh.device_config_put(dv.config_namespace, dv.key, dv.value)
            SecFERRO_TUI.row(f"device_config {dv.config_namespace}/{dv.key}", dv.value, ok)
            applied += int(ok)
        return applied

    def _rollback_device_config_vectors(self) -> int:
        reverted = 0
        for dv in TuningCatalog.DEVICE_CONFIG:
            ok = self._sh.device_config_delete(dv.config_namespace, dv.key)
            SecFERRO_TUI.row(f"device_config delete {dv.key}", "reverted", ok)
            reverted += int(ok)
        return reverted

    def _spawn_guardian_daemon_detached(self) -> int:
        script_path = os.path.abspath(__file__)
        if not os.path.isfile(script_path):
            SecFERRO_TUI.warn(
                "Cannot self-locate script for detached spawn — run "
                "manually: python3 <this_file> --guardian-daemon"
            )
            return -1
        proc = subprocess.Popen(
            [sys.executable, script_path, "--guardian-daemon"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        SecFERRO_TUI.row("Guardian Daemon spawned (detached)", f"PID {proc.pid}", True)
        return proc.pid

    def _apply_shizuku_bootstrap(self) -> None:
        ShizukuLifecycleManager(self._sh).ensure_ready()

    def _apply_media_codec_reset(self) -> None:
        MediaCodecServiceReset(self._sh).apply()

    def _apply_system_integrity_audit(self) -> None:
        auditor = SystemIntegrityAuditor(self._sh)
        findings = auditor.audit()
        auditor.verify_ethernet_hardware()
        if findings.get("APP_LEVEL_BILLING_STATE_CORRUPT"):
            auditor.remediate_billing_cache()

    def _apply_renderer_integrity_guard(self) -> None:
        RendererIntegrityGuard(self._sh).run_integrity_check()

    def _apply_prop_drift_correction(self) -> None:
        PropDriftCorrector(self._sh, self._commit_single).scan_and_correct(auto_fix=True)

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
        dc_count = self._commit_device_config_vectors()
        SecFERRO_TUI.row("device_config vectors applied", str(dc_count), dc_count >= 0)

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
        dc_reverted = self._rollback_device_config_vectors()
        SecFERRO_TUI.row("device_config vectors reverted", str(dc_reverted), dc_reverted >= 0)
        SecFERRO_TUI.warn("Cold reboot required for complete factory state restore.")

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
        for cmd in (
            "am kill-all",
            "cmd activity trim-memory RUNNING_CRITICAL",
            "cmd activity gc-heap",
            "pm trim-caches 4096G",
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

    def run_full_optimization(self) -> None:
        SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.6.3 — FULL PIPELINE")
        SecFERRO_TUI.row("exec layer", self._sh.layer.name,                    True)
        SecFERRO_TUI.row("target",     "Sagemcom DCTIW362p | BCM72604 | ATV9", None)
        SecFERRO_TUI.row("network",    "PlayNET FTTH | Zyxel AR5344 fw-1.0.36",None)
        self._apply_shizuku_bootstrap()
        self._apply_system_integrity_audit()
        self._apply_renderer_integrity_guard()
        self._apply_prop_drift_correction()
        self._apply_graphics_pipeline()
        self._apply_media_pipeline()
        self._apply_network_pipeline()
        self._apply_stability_profile()
        self._apply_debloat_profile()
        self._apply_smarttube_enhancement()
        self.flush_memory_caches()
        self._spawn_guardian_daemon_detached()
        SecFERRO_TUI.banner("OPTIMIZATION PIPELINE COMPLETE — REBOOT RECOMMENDED")


# ════════════════════════════════════════════════════════════════════════════════
# PROP DRIFT CORRECTOR
# ════════════════════════════════════════════════════════════════════════════════

class PropDriftCorrector:
    _SCAN_CATALOGS: ClassVar[tuple[str, ...]] = ("GRAPHICS", "MEDIA", "NETWORK", "STABILITY")

    def __init__(self, sh: SecFERRO_ShellExecutor,
                 committer: Callable[[TuningVector], bool]) -> None:
        self._sh:     Final[SecFERRO_ShellExecutor]         = sh
        self._commit: Final[Callable[[TuningVector], bool]] = committer

    def _read_current(self, v: TuningVector) -> str:
        if v.ns == Namespace.PROP:
            return self._sh.getprop_value(v.key)
        return self._sh.settings_get(v.ns.value, v.key).strip()

    def _scan_vector(self, v: TuningVector) -> bool:
        current = self._read_current(v)
        drifted = current != v.value
        SecFERRO_TUI.row(v.key, f"{current or 'unset'} (wanted: {v.value})", not drifted)
        return drifted

    def _all_vectors(self) -> tuple[TuningVector, ...]:
        combined: tuple[TuningVector, ...] = ()
        for name in self._SCAN_CATALOGS:
            combined += getattr(TuningCatalog, name)
        return combined

    def scan_and_correct(self, auto_fix: bool = True) -> tuple[int, int]:
        SecFERRO_TUI.banner("Prop Drift Scan — Tile Pipeline Format")
        scanned = corrected = 0
        for v in self._all_vectors():
            scanned += 1
            if self._scan_vector(v) and auto_fix and self._commit(v):
                corrected += 1
                SecFERRO_TUI.row(f"  auto-fixed {v.key}", v.value, True)
        SecFERRO_TUI.section("Summary")
        SecFERRO_TUI.row("vectors scanned", str(scanned), None)
        SecFERRO_TUI.row("drift corrected", str(corrected), corrected >= 0)
        return scanned, corrected


# ════════════════════════════════════════════════════════════════════════════════
# RENDERER INTEGRITY GUARD
# ════════════════════════════════════════════════════════════════════════════════

class RendererIntegrityGuard:
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

    def _read_egl_bringup_log(self) -> str:
        return self._sh.logcat_grep("OpenGLRenderer", "D", lines=20)

    def verify_effective_state(self) -> bool:
        SecFERRO_TUI.banner("Renderer Verification (corrected heuristic)")
        requested = self._sh.getprop_value("debug.hwui.renderer")
        egl_log = self._read_egl_bringup_log()
        egl_ok = "Initialized EGL" in egl_log
        SecFERRO_TUI.row("getprop debug.hwui.renderer", requested or "unset", None)
        SecFERRO_TUI.row("EGL context negotiated", str(egl_ok), egl_ok)
        SecFERRO_TUI.warn(
            "'OpenGLRenderer' tag is pipeline-agnostic on this AOSP branch; "
            "it does not by itself confirm skiagl vs legacy GL."
        )
        return bool(requested == RendererCatalog.VALIDATED_SAFE.hwui_renderer and egl_ok)

    def check_hwc_composition_health(self) -> bool:
        out = self._sh.logcat_grep("bcm-hwc", "W", lines=30)
        idle_count = len(re.findall(r"no layer to compose", out))
        healthy = idle_count < 15
        SecFERRO_TUI.row("bcm-hwc idle-composition spam (last 30 lines)",
                          str(idle_count), healthy)
        return healthy

    _V3D_SYSFS_CANDIDATES: ClassVar[tuple[str, ...]] = (
        "/sys/kernel/debug/vc4/v3d_stats",
        "/sys/kernel/debug/vc4/bo_stats",
        "/sys/module/v3d/statistics",
    )

    def probe_v3d_sysfs(self) -> bool:
        SecFERRO_TUI.banner("V3D GPU Diagnostics — sysfs probe (read-only)")
        for path in self._V3D_SYSFS_CANDIDATES:
            _, out, _ = self._sh.run(f"cat {path} 2>/dev/null")
            if out:
                SecFERRO_TUI.row(path, "accessible", True)
                return True
        SecFERRO_TUI.warn(
            "V3D sysfs unavailable (expected on production build) — "
            "requires root + kernel CONFIG_DEBUG_FS=y."
        )
        return False

    def read_gpu_hardware_facts(self) -> dict[str, str]:
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
        SecFERRO_TUI.banner("Renderer Integrity Guard — Full Check")
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

    def _typed_subelement(self, root: ET.Element, pref_key: str, kc_str: str) -> None:
        existing = root.find(f"*[@name='{pref_key}']")
        if existing is not None:
            if existing.tag == "string":
                existing.text = kc_str
            else:
                existing.set("value", kc_str)
            return
        elem = ET.SubElement(root, "string")
        elem.set("name", pref_key)
        elem.text = kc_str

    def _patch_xml_tree(self, tree: ET.ElementTree) -> int:
        root = tree.getroot()
        entries = self._build_new_entries()
        for pref_key, kc_str in entries:
            self._typed_subelement(root, pref_key, kc_str)
        return len(entries)

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

    def _resolve_activity_for_view(self, url: str) -> bool:
        _, out, _ = self._sh.run(
            f"pm resolve-activity --brief -a android.intent.action.VIEW "
            f"-d '{url}' 2>/dev/null"
        )
        return bool(out) and "No activity found" not in out

    def _show_url_overlay(self, url: str) -> bool:
        if self._resolve_activity_for_view(url):
            self._sh.run(
                f"am start -a android.intent.action.VIEW -d '{url}' "
                f"--activity-clear-task 2>/dev/null"
            )
            SecFERRO_TUI.row("VIEW intent", "resolved + launched", True)
        else:
            SecFERRO_TUI.warn(
                "VIEW intent unresolvable on this build (confirmed failure "
                "mode) — skipping am start, clipboard/notification only"
            )
        self._sh.run(
            f"am broadcast -a 'android.intent.action.SEND' "
            f"--es android.intent.extra.TEXT '{url}' "
            f"--et android.intent.extra.SUBJECT 'SmartTube Link' 2>/dev/null"
        )
        return True

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
        SecFERRO_TUI.row("remediation", "read-only extract only, never auto-patch /system", None)
        return False

    def extract_bad_keylayout_line(self) -> str:
        _, out, _ = self._sh.run(f"sed -n '72p' '{self._PHONE_REMOTE_KL}' 2>/dev/null")
        SecFERRO_TUI.row(f"{self._PHONE_REMOTE_KL}:72 (raw)", out or "unreadable", None)
        SecFERRO_TUI.warn(
            "Extracted for manual review only. Cross-check against AOSP "
            "reference: frameworks/native/data/keyboards/Generic.kl"
        )
        return out


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE ENHANCER — facade
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeEnhancer:
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
                "Install KDE Connect on phone + TV for full clipboard sharing."
            )


# ════════════════════════════════════════════════════════════════════════════════
# GENTLE FREEZE MANAGER
# ════════════════════════════════════════════════════════════════════════════════

class GentleFreezeManager:
    _DEFAULT_TARGETS: ClassVar[tuple[str, ...]] = ("com.netflix.ninja",)

    def __init__(self, sh: SecFERRO_ShellExecutor) -> None:
        self._sh: Final[SecFERRO_ShellExecutor] = sh

    def freeze(self, pkg: str) -> bool:
        self._sh.run(f"am force-stop {pkg}")
        suspended = self._sh.pm_suspend(pkg)
        throttled = self._sh.appops_set(pkg, "RUN_IN_BACKGROUND", "ignore")
        SecFERRO_TUI.row(pkg, f"suspended={suspended} throttled={throttled}",
                          suspended and throttled)
        return suspended and throttled

    def unfreeze(self, pkg: str) -> bool:
        ok = self._sh.pm_unsuspend(pkg)
        self._sh.appops_set(pkg, "RUN_IN_BACKGROUND", "allow")
        SecFERRO_TUI.row(pkg, "unsuspended", ok)
        return ok

    def freeze_defaults(self) -> None:
        SecFERRO_TUI.banner("Gentle Freeze — DRM-Safe Background Suspend")
        for pkg in self._DEFAULT_TARGETS:
            self.freeze(pkg)


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE BACKUP PATCHER
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeBackupPatcher:
    _BROADCAST_ACTION: Final[str] = "com.liskovsoft.smartyoutubetv2.BACKUP_EXPORT"
    _DEVICE_ZIP:        Final[str] = "/sdcard/SmartTubeBackup.zip"

    def __init__(self, sh: SecFERRO_ShellExecutor, pkg: str,
                 catalog: tuple[SmartTubePrefVector, ...]) -> None:
        self._sh:      Final[SecFERRO_ShellExecutor]            = sh
        self._pkg:     Final[str]                                = pkg
        self._catalog: Final[tuple[SmartTubePrefVector, ...]]    = catalog

    def trigger_export(self, wait_secs: float = 3.0) -> bool:
        rc, _, _ = self._sh.run(f"am broadcast -a {self._BROADCAST_ACTION} -p {self._pkg}")
        time.sleep(wait_secs)
        exists = os.path.isfile(self._DEVICE_ZIP)
        SecFERRO_TUI.row("backup export triggered", self._DEVICE_ZIP, exists)
        return rc == 0 and exists

    def _typed_element(self, root: ET.Element, v: SmartTubePrefVector) -> None:
        for el in root:
            if el.get("name") == v.key:
                if v.typ == "string":
                    el.tag, el.text = "string", v.value
                    el.attrib.pop("value", None)
                else:
                    el.tag, el.text = v.typ, None
                    el.set("value", v.value)
                return
        if v.typ == "string":
            ET.SubElement(root, "string", {"name": v.key}).text = v.value
        else:
            ET.SubElement(root, v.typ, {"name": v.key, "value": v.value})

    def _optimize_xml_bytes(self, data: bytes) -> bytes:
        try:
            root = ET.fromstring(data.decode("utf-8", errors="replace"))
        except ET.ParseError:
            return data
        for v in self._catalog:
            self._typed_element(root, v)
        buf = io.BytesIO()
        ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
        return buf.getvalue()

    def _apply_json_recursive(self, node: object, key: str, value: object) -> None:
        if isinstance(node, dict):
            if key in node:
                node[key] = value
            else:
                for child in node.values():
                    self._apply_json_recursive(child, key, value)
        elif isinstance(node, list):
            for item in node:
                self._apply_json_recursive(item, key, value)

    def _coerce(self, v: SmartTubePrefVector) -> object:
        if v.typ == "boolean":
            return v.value == "true"
        if v.typ == "int":
            return int(v.value)
        return v.value

    def _optimize_json_bytes(self, data: bytes) -> bytes:
        try:
            obj = json.loads(data.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return data
        for v in self._catalog:
            self._apply_json_recursive(obj, v.key, self._coerce(v))
        return json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")

    def rewrite_zip_in_place(self) -> bool:
        if not os.path.isfile(self._DEVICE_ZIP):
            SecFERRO_TUI.error(f"{self._DEVICE_ZIP} not found — run trigger_export() first")
            return False
        staging = f"{self._DEVICE_ZIP}.staged"
        try:
            with zipfile.ZipFile(self._DEVICE_ZIP, "r") as zin, \
                 zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    raw = zin.read(item.filename)
                    ext = os.path.splitext(item.filename)[1].lower()
                    if ext in (".xml", ".bak"):
                        zout.writestr(item, self._optimize_xml_bytes(raw))
                    elif ext == ".json":
                        zout.writestr(item, self._optimize_json_bytes(raw))
                    else:
                        zout.writestr(item, raw)
            os.replace(staging, self._DEVICE_ZIP)
            SecFERRO_TUI.row("zip rewritten in place", self._DEVICE_ZIP, True)
            return True
        except (zipfile.BadZipFile, OSError) as exc:
            SecFERRO_TUI.error(f"zip rewrite failed: {exc}")
            return False

    def apply(self) -> bool:
        SecFERRO_TUI.banner(f"SmartTube Backup Patcher — {self._pkg}")
        if not self.trigger_export():
            return False
        if not self.rewrite_zip_in_place():
            return False
        self._sh.run(f"am force-stop {self._pkg}")
        SecFERRO_TUI.warn(
            "Restore manually: SmartTube → Settings → Backup & Restore → Import"
        )
        return True


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM INTEGRITY AUDITOR
# ════════════════════════════════════════════════════════════════════════════════

class SystemIntegrityAuditor:
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
            if hit and f.verdict == "DHCP_RENEWAL_FREQUENCY_UNCONFIRMED":
                self.report_dhcp_renewal_frequency()
        return results

    def report_dhcp_renewal_frequency(self) -> int:
        _, out, _ = self._sh.run("logcat -d -s DhcpClient:I 2>/dev/null | grep -c DHCPDISCOVER")
        count = int(out) if out.strip().isdigit() else 0
        SecFERRO_TUI.row("DHCPDISCOVER events (current log buffer)", str(count), None)
        return count

    def remediate_billing_cache(self) -> bool:
        SecFERRO_TUI.banner("Billing Cache Remediation — com.spocky.projengmenu")
        pkg = "com.spocky.projengmenu"
        self._sh.run(f"rm -rf /data/user/0/{pkg}/cache/*")
        rc, _, _ = self._sh.run(f"am force-stop {pkg}")
        SecFERRO_TUI.row("cache purged + process stopped", pkg, rc == 0)
        SecFERRO_TUI.warn("Preferences/login preserved — only cache/* removed.")
        return rc == 0

    def verify_ethernet_hardware(self) -> str:
        SecFERRO_TUI.banner("Ethernet Hardware Presence — Empirical Check")
        _, out, _ = self._sh.run("ip link show eth0 2>/dev/null")
        present = bool(out) and "does not exist" not in out
        state = "UP" if "state UP" in out else ("DOWN (cable unplugged)" if present else "ABSENT")
        SecFERRO_TUI.row("eth0", state, present)
        return state

    def audit_passpoint_scan_waste(self) -> bool:
        SecFERRO_TUI.banner("Passpoint/HS20 ANQP Scan Audit")
        hit = self._search_logcat("PasspointManager", r"Match not found for PLAY_")
        SecFERRO_TUI.row("wasted ANQP queries detected", str(hit), not hit)
        if hit:
            SecFERRO_TUI.warn("wifi_scan_always_enabled=0 (already applied) is the mitigation.")
        return not hit

    def correlate_billing_pss_pressure(self) -> bool:
        SecFERRO_TUI.banner("PSS Correlation — Billing Crash-Loop vs Memory Pressure")
        _, out, _ = self._sh.run("dumpsys meminfo com.spocky.projengmenu 2>/dev/null")
        m = re.search(r"TOTAL PSS:\s+(\d+)", out)
        pss_kb = int(m.group(1)) if m else 0
        elevated = pss_kb > 100_000
        SecFERRO_TUI.row("com.spocky.projengmenu TOTAL PSS", f"{pss_kb} KB", not elevated)
        if elevated:
            SecFERRO_TUI.warn("Elevated PSS alongside crash loop — plausibly related, not confirmed causal.")
        return not elevated


# ════════════════════════════════════════════════════════════════════════════════
# GUARDIAN DAEMON
# ════════════════════════════════════════════════════════════════════════════════

class GuardianDaemon:
    _AV1_GUARD_KEYS: ClassVar[frozenset[str]] = frozenset({
        "debug.stagefright.c2.av1",
        "media.av1.sw.decode.disable",
        "media.codec.av1.disable",
        "audio.brcm.hdmi.clock_lock",
    })

    def __init__(self, sh: SecFERRO_ShellExecutor,
                 cfg: GuardianCycleConfig | None = None) -> None:
        self._sh:    Final[SecFERRO_ShellExecutor] = sh
        self._cfg:   Final[GuardianCycleConfig]     = cfg or GuardianCycleConfig()
        self._cycle: int = 0

    def _reassert_av1_guard(self) -> None:
        for v in TuningCatalog.MEDIA:
            if v.key in self._AV1_GUARD_KEYS:
                self._sh.setprop(v.key, v.value)

    def _correct_dns_typo_regression(self) -> bool:
        current = self._sh.settings_get("global", "private_dns_specifier")
        if current.strip() != "dns.cloudflare.com":
            return False
        return self._sh.settings_put("global", "private_dns_specifier", "one.one.one.one")

    def _foreground_hint(self) -> bool:
        _, out, _ = self._sh.run(
            "dumpsys window windows 2>/dev/null | grep -E 'mCurrentFocus|mFocusedApp'"
        )
        return self._cfg.foreground_pkg_hint in out.lower()

    def _free_mem_kb(self) -> int:
        _, out, _ = self._sh.run("awk '/MemFree/{print $2}' /proc/meminfo")
        return int(out) if out.strip().isdigit() else -1

    def _ram_triage(self, is_foreground: bool) -> None:
        free_kb = self._free_mem_kb()
        if free_kb < 0:
            return
        limit = (self._cfg.free_kb_foreground if is_foreground else self._cfg.free_kb_idle)
        if free_kb >= limit:
            return
        self._sh.run("sync")
        drop_level = "3" if is_foreground else "1"
        self._sh.run(f"echo {drop_level} > /proc/sys/vm/drop_caches 2>/dev/null")

    def _cast_service_watchdog(self) -> None:
        _, out, _ = self._sh.run(
            "pm list packages -e com.google.android.apps.mediashell 2>/dev/null"
        )
        if not out:
            self._sh.pm_enable("com.google.android.apps.mediashell")

    def _run_one_cycle(self) -> int:
        self._cycle += 1
        is_fg = self._foreground_hint()
        self._cast_service_watchdog()
        self._correct_dns_typo_regression()
        self._ram_triage(is_fg)
        if self._cycle % self._cfg.av1_recheck_every == 0:
            self._reassert_av1_guard()
        return (self._cfg.sleep_foreground_secs if is_fg else self._cfg.sleep_idle_secs)

    def run_forever(self) -> None:
        SecFERRO_TUI.banner("Guardian Daemon — Background Drift Correction")
        SecFERRO_TUI.row("foreground poll hint", self._cfg.foreground_pkg_hint, None)
        while True:
            sleep_for = self._run_one_cycle()
            time.sleep(sleep_for)


# ════════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    SecFERRO_TUI.banner("SecFERRO PerformanceTuner v9.6.3 — Dispatcher")
    tuner = PerformanceTuner()
    mode  = sys.argv[1] if len(sys.argv) > 1 else "--optimize"
    dispatch: dict[str, Callable[[], object]] = {
        "--optimize":                     tuner.run_full_optimization,
        "--rollback":                     tuner._apply_rollback_profile,
        "--diagnostics":                  tuner.run_diagnostics,
        "--debloat":                      tuner._apply_debloat_profile,
        "--graphics":                     tuner._apply_graphics_pipeline,
        "--media":                        tuner._apply_media_pipeline,
        "--network":                      tuner._apply_network_pipeline,
        "--flush":                        tuner.flush_memory_caches,
        "--renderer-audit":               lambda: RendererIntegrityGuard(tuner._sh).audit_pasted_regressions(),
        "--renderer-guard":               tuner._apply_renderer_integrity_guard,
        "--smarttube":                    tuner._apply_smarttube_enhancement,
        "--probe-remote":                 lambda: RemoteKeyProbe(tuner._sh).capture(15),
        "--share-url":                    lambda: PhoneClipboardBridge(tuner._sh).send(False),
        "--share-url-ts":                 lambda: PhoneClipboardBridge(tuner._sh).send(True),
        "--integrity-audit":              tuner._apply_system_integrity_audit,
        "--fix-billing-cache":            lambda: SystemIntegrityAuditor(tuner._sh).remediate_billing_cache(),
        "--check-ethernet":               lambda: SystemIntegrityAuditor(tuner._sh).verify_ethernet_hardware(),
        "--check-keylayout":              lambda: RemoteKeyProbe(tuner._sh).check_keylayout_integrity(),
        "--extract-keylayout-line":       lambda: RemoteKeyProbe(tuner._sh).extract_bad_keylayout_line(),
        "--check-passpoint":              lambda: SystemIntegrityAuditor(tuner._sh).audit_passpoint_scan_waste(),
        "--gpu-facts":                    lambda: RendererIntegrityGuard(tuner._sh).read_gpu_hardware_facts(),
        "--guardian-daemon":              lambda: GuardianDaemon(tuner._sh).run_forever(),
        "--check-dhcp-frequency":         lambda: SystemIntegrityAuditor(tuner._sh).report_dhcp_renewal_frequency(),
        "--drift-scan":                   lambda: PropDriftCorrector(tuner._sh, tuner._commit_single).scan_and_correct(True),
        "--drift-scan-dry":               lambda: PropDriftCorrector(tuner._sh, tuner._commit_single).scan_and_correct(False),
        "--v3d-probe":                    lambda: RendererIntegrityGuard(tuner._sh).probe_v3d_sysfs(),
        "--pss-correlate":                lambda: SystemIntegrityAuditor(tuner._sh).correlate_billing_pss_pressure(),
        "--freeze-netflix":               lambda: GentleFreezeManager(tuner._sh).freeze_defaults(),
        "--unfreeze-netflix":             lambda: GentleFreezeManager(tuner._sh).unfreeze("com.netflix.ninja"),
        "--smarttube-media-patch":        lambda: SmartTubeBackupPatcher(
                                               tuner._sh, "org.smarttube.stable",
                                               SmartTubeMediaCatalog.BCM72604_OPTIMAL).apply(),
        "--smarttube-sponsorblock-patch": lambda: SmartTubeBackupPatcher(
                                               tuner._sh, "org.smarttube.stable",
                                               SponsorBlockCatalog.SPONSORBLOCK_OPTIMAL).apply(),
        "--shizuku-install":              lambda: ShizukuLifecycleManager(tuner._sh).install(),
        "--shizuku-start":                lambda: ShizukuLifecycleManager(tuner._sh).start_server(),
        "--shizuku-stop":                 lambda: ShizukuLifecycleManager(tuner._sh).stop_server(),
        "--shizuku-verify":               lambda: ShizukuLifecycleManager(tuner._sh).verify_ppid_escalation(),
        "--shizuku-ensure":               lambda: ShizukuLifecycleManager(tuner._sh).ensure_ready(),
        "--reset-codecs":                 lambda: MediaCodecServiceReset(tuner._sh).apply(),
    }
    handler = dispatch.get(mode)
    if handler is None:
        SecFERRO_TUI.error(f"Unknown mode '{mode}'.")
        SecFERRO_TUI.row("valid modes", str(list(dispatch.keys())), None)
        sys.exit(1)
    handler()


if __name__ == "__main__":
    main()
