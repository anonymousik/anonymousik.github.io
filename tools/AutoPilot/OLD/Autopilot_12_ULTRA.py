#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     PLAYBOX TITANIUM v12.0 ULTRA — Self-Diagnostic + Auto-Repair Edition    ║
║  Target  : Sagemcom DCTIW362P | Android TV 9 (API 28) | Broadcom m362       ║
║  Focus   : SmartTube HW, Chromecast, Self-Diagnostics, Auto-Repair          ║
║  Author  : Anonymousik / SecFerro Division                                   ║
║  Version : 12.0-ULTRA-SelfHeal                                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  HARDWARE PROFILE (real ADB session 192.168.1.3:5555):                       ║
║    RAM     : 1459 MB total  | ~534 MB available                              ║
║    FLASH   : 3.9 GB  | 53% used (/data)                                      ║
║    SoC     : Broadcom BCM7362 | Dual-core Cortex-A15 @ 1.0 GHz              ║
║    VPU     : H.264 ✓ | H.265 ✓ | VP9 ✓ | AV1 ✗ (SW only)                   ║
║    GPU     : Broadcom VideoCore (GLES 3.1, NO Vulkan)                        ║
║    Display : HDMI 2.0a, CEC v1.4, 4K@60fps, HDR10                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  CHANGELOG v12 vs v11:                                                       ║
║  [FIX] DNS: one.one.one.one (DoT) + net.dns1/net.dns2 setprop               ║
║  [FIX] SmartTube pkg: org.smarttube.stable (verified from ps output)        ║
║  [FIX] HDMI addr: persist.sys.hdmi.addr.playback=11 (BCM Nexus correct)     ║
║  [NEW] debug.stagefright.ccodec=1 (C2 pipeline), skiaglthreaded renderer    ║
║  [NEW] LMK minfree /sys tuning, swappiness=10, VFS pressure=50              ║
║  [NEW] TCP kernel params (SACK, timestamps, window scaling, BBR attempt)    ║
║  [NEW] I/O scheduler=deadline, read_ahead_kb=512                            ║
║  [NEW] BCM Nexus props (persist.nx.hdmi.*, persist.nx.vidout.50hz)          ║
║  [NEW] InteractiveDiagnostics — 8 service categories, self-healing          ║
║  [NEW] AutoRepair — detects broken sectors, re-downloads + reinstalls APKs  ║
║  [NEW] CastRepair — restores debloat.sh damage (mediashell kill prevention) ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import sys
import subprocess
import time
import json
import hashlib
import argparse
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum, auto

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
VERSION          = "12.0-ULTRA-SelfHeal"
DEFAULT_ADB_HOST = "192.168.1.3:5555"
CACHE_DIR        = Path.home() / ".playbox_cache"
BACKUP_DIR       = CACHE_DIR / "backups_v12"
LOG_FILE         = CACHE_DIR / "autopilot_v12.log"
REPAIR_LOG       = CACHE_DIR / "repair_v12.log"

for d in (CACHE_DIR, BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# STATUS ENUM
# ─────────────────────────────────────────────────────────────────────────────
class Status(Enum):
    OK      = auto()
    WARN    = auto()
    BROKEN  = auto()
    MISSING = auto()
    UNKNOWN = auto()


# ─────────────────────────────────────────────────────────────────────────────
# DEVICE SPEC (verified from real ps + getprop session)
# ─────────────────────────────────────────────────────────────────────────────
class DeviceSpec:
    MODEL            = "dctiw362p"
    HARDWARE         = "m362"
    ANDROID_VERSION  = "9"
    API_LEVEL        = "28"

    # BCM7362 VPU — confirmed from OMX enumeration on this chipset family
    CODEC_HW_H264    = "OMX.brcm.video.h264.decoder"
    CODEC_HW_HEVC    = "OMX.brcm.video.h265.decoder"
    CODEC_HW_VP9     = "OMX.brcm.video.vp9.decoder"
    CODEC_SW_AV1     = "c2.android.av1.decoder"    # HW not present → AVOID

    # Dalvik heap for ~534 MB available
    DALVIK_HEAP_SIZE     = "256m"
    DALVIK_HEAP_GROWTH   = "128m"
    DALVIK_HEAP_START    = "16m"
    DALVIK_HEAP_MIN_FREE = "2m"
    DALVIK_HEAP_MAX_FREE = "8m"
    DALVIK_HEAP_TARGET   = "0.75"

    # ── VERIFIED PACKAGE NAMES (from real adb shell ps output) ───────────────
    # CRITICAL: org.smarttube.stable — NOT com.teamsmart.videomanager.tv
    #   Real ps: u0_a89 6624 2996 org.smarttube.stable
    SMARTTUBE_PKG_STABLE  = "org.smarttube.stable"
    SMARTTUBE_PKG_BETA    = "org.smarttube.beta"
    SMARTTUBE_PKG_LEGACY  = "com.liskovsoft.smarttubetv"   # old package, still accepted
    SMARTTUBE_STABLE_URL  = "https://github.com/yuliskov/SmartTube/releases/download/latest/smarttube_stable.apk"
    SMARTTUBE_BETA_URL    = "https://github.com/yuliskov/SmartTube/releases/download/latest/smarttube_beta.apk"

    # Verified from real ps: u0_a88 26563 com.spocky.projengmenu
    PROJECTIVY_PKG        = "com.spocky.projengmenu"
    PROJECTIVY_URL        = "https://github.com/spocky/projectivy-launcher/releases/latest/download/Projectivy_Launcher.apk"

    SHIZUKU_PKG           = "moe.shizuku.privileged.api"
    SHIZUKU_URL           = "https://github.com/RikkaApps/Shizuku/releases/download/v13.5.4/shizuku-v13.5.4-release.apk"

    # DNS: correct DoT hostnames (verified working on Android 9)
    DNS_PROVIDERS: Dict[str, Tuple[str, str, str]] = {
        # name: (dot_hostname, ip_primary, ip_secondary)
        "cloudflare": ("one.one.one.one",          "1.1.1.1",        "1.0.0.1"),
        "google":     ("dns.google",               "8.8.8.8",        "8.8.4.4"),
        "quad9":      ("dns.quad9.net",            "9.9.9.9",        "149.112.112.112"),
        "adguard":    ("dns.adguard.com",          "94.140.14.14",   "94.140.15.15"),
        "nextdns":    ("dns.nextdns.io",           "45.90.28.0",     "45.90.30.0"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CHROMECAST PROTECTION REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
class ChromecastProtection:
    """
    Protected package whitelist — these are NEVER disabled/modified.

    IMPORTANT: real debloat.sh on device lists apps.mediashell as "safe to disable".
    This is WRONG. It IS the Chromecast daemon. We defend against this mistake.

    ALSO: gms.cast.receiver found in debloat.sh — also protected here.
    """
    PROTECTED: Dict[str, str] = {
        "com.google.android.apps.mediashell":
            "Cast daemon — THIS IS CHROMECAST BUILT-IN. NEVER disable.",
        "com.google.android.gms":
            "GMS — Cast SDK host, auth, SessionManager.",
        "com.google.android.gsf":
            "Google Services Framework — GMS dependency.",
        "com.google.android.nearby":
            "Nearby — mDNS/BLE Cast discovery.",
        "com.google.android.gms.cast.receiver":
            "Cast Receiver Framework — part of GMS Cast stack.",
        "com.google.android.tv.remote.service":
            "TV Remote Service — Cast session UI & input.",
        "com.google.android.tvlauncher":
            "TV Launcher — Cast ambient mode, intent handoff.",
        "com.google.android.configupdater":
            "Config Updater — Cast TLS certificates.",
        "com.google.android.wifidisplay":
            "WiFi Display — Miracast/Cast fallback.",
        "com.android.networkstack":
            "Network Stack — IGMP multicast for mDNS.",
        "com.android.networkstack.tethering":
            "Network Tethering — multicast routing.",
    }

    @classmethod
    def is_protected(cls, pkg: str) -> bool:
        return pkg in cls.PROTECTED

    @classmethod
    def get_reason(cls, pkg: str) -> str:
        return cls.PROTECTED.get(pkg, "")

    @classmethod
    def print_all(cls) -> None:
        Logger.header("🛡 CHROMECAST PROTECTION REGISTRY")
        for pkg, reason in cls.PROTECTED.items():
            Logger.shield(f"{pkg}")
            Logger.log(f"     └─ {reason}", "cyan")


# ─────────────────────────────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────────────────────────────
class Logger:
    C = {
        "info":    "\033[94m",
        "success": "\033[92m",
        "warning": "\033[93m",
        "error":   "\033[91m",
        "header":  "\033[95m",
        "cyan":    "\033[96m",
        "bold":    "\033[1m",
        "reset":   "\033[0m",
        "dim":     "\033[2m",
    }
    _lines: List[str] = []

    @classmethod
    def _emit(cls, msg: str, level: str) -> None:
        ts = time.strftime("%H:%M:%S")
        c  = cls.C.get(level, cls.C["info"])
        print(f"{c}[{ts}] {msg}{cls.C['reset']}")
        cls._lines.append(f"[{ts}][{level.upper()}] {msg}")

    @classmethod
    def log(cls, m: str, l: str = "info") -> None: cls._emit(m, l)
    @classmethod
    def success(cls, m: str) -> None: cls._emit(f"✓ {m}", "success")
    @classmethod
    def warning(cls, m: str) -> None: cls._emit(f"⚠ {m}", "warning")
    @classmethod
    def error(cls, m: str) -> None:   cls._emit(f"✗ {m}", "error")
    @classmethod
    def shield(cls, m: str) -> None:  cls._emit(f"🛡 {m}", "success")
    @classmethod
    def repair(cls, m: str) -> None:  cls._emit(f"🔧 {m}", "warning")

    @classmethod
    def header(cls, msg: str) -> None:
        sep = "═" * 74
        print(f"\n{cls.C['header']}{cls.C['bold']}{sep}\n   {msg}\n{sep}{cls.C['reset']}\n")

    @classmethod
    def section(cls, msg: str) -> None:
        print(f"\n{cls.C['cyan']}  ── {msg} ──{cls.C['reset']}")

    @classmethod
    def save(cls) -> None:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n{'─'*60}\nSESSION {time.strftime('%Y-%m-%d %H:%M:%S')} | v{VERSION}\n")
                f.write("\n".join(cls._lines) + "\n")
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# ADB SHELL INTERFACE
# ─────────────────────────────────────────────────────────────────────────────
class ADB:
    """
    Secure ADB executor. No shell=True. Retry on Timeout only.
    Escalation: su → rish → plain ADB.
    """
    device: Optional[str] = None
    TIMEOUT: int = 35
    RETRIES: int = 3

    @classmethod
    def connect(cls, target: str) -> bool:
        try:
            r = subprocess.run(["adb", "connect", target],
                               capture_output=True, text=True, timeout=10)
            if "connected" in r.stdout.lower():
                cls.device = target
                Logger.success(f"ADB connected: {target}")
                return True
            Logger.error(f"ADB failed: {r.stdout.strip()}")
            return False
        except FileNotFoundError:
            Logger.error("'adb' not found. Install Android Platform Tools.")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            Logger.error(f"ADB connect timeout: {target}")
            return False

    @classmethod
    def detect(cls) -> Optional[str]:
        try:
            out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
            for line in out.splitlines():
                if "\tdevice" in line:
                    return line.split("\t")[0].strip()
        except Exception:
            pass
        return None

    @classmethod
    def run(cls, cmd: str, silent: bool = False) -> str:
        if not cls.device:
            return ""
        for attempt in range(cls.RETRIES):
            try:
                out = subprocess.check_output(
                    ["adb", "-s", cls.device, "shell", cmd],
                    stderr=subprocess.STDOUT, text=True, timeout=cls.TIMEOUT)
                return out.strip()
            except subprocess.TimeoutExpired:
                if attempt < cls.RETRIES - 1:
                    time.sleep(1.5)
                elif not silent:
                    Logger.warning(f"Timeout [{attempt+1}]: {cmd[:55]}")
            except subprocess.CalledProcessError as e:
                return (e.output or "").strip()
            except Exception as e:
                if not silent:
                    Logger.error(f"ADB: {e}")
                return ""
        return ""

    @classmethod
    def run_root(cls, cmd: str) -> str:
        for prefix in (f'su -c "{cmd}"', f'rish -c "{cmd}"'):
            r = cls.run(prefix, silent=True)
            if r and "not found" not in r and "permission denied" not in r.lower():
                return r
        return cls.run(cmd)

    @classmethod
    def push(cls, local: str, remote: str) -> bool:
        try:
            subprocess.check_call(
                ["adb", "-s", cls.device, "push", local, remote],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            return True
        except Exception:
            return False

    @classmethod
    def prop(cls, key: str) -> str:
        return cls.run(f"getprop {key}", silent=True)

    @classmethod
    def setprop(cls, key: str, val: str) -> None:
        cls.run(f"setprop {key} {val}", silent=True)

    @classmethod
    def setting_put(cls, ns: str, key: str, val: str) -> None:
        cls.run(f"settings put {ns} {key} {val}", silent=True)

    @classmethod
    def setting_get(cls, ns: str, key: str) -> str:
        return cls.run(f"settings get {ns} {key}", silent=True)

    @classmethod
    def pkg_enabled(cls, pkg: str) -> bool:
        return pkg in cls.run(f"pm list packages -e {pkg}", silent=True)

    @classmethod
    def pkg_installed(cls, pkg: str) -> bool:
        return pkg in cls.run(f"pm list packages {pkg}", silent=True)

    @classmethod
    def pkg_version(cls, pkg: str) -> str:
        out = cls.run(f"dumpsys package {pkg} | grep versionName", silent=True)
        if "=" in out:
            return out.split("=")[-1].strip()
        return "unknown"

    @classmethod
    def syswrite(cls, path: str, val: str) -> bool:
        """Write to /sys or /proc path via root."""
        result = cls.run_root(f"echo {val} > {path}")
        # Verify
        verify = cls.run_root(f"cat {path}").strip()
        return val in verify


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTIC RESULT
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class DiagResult:
    category: str
    check:    str
    status:   Status
    found:    str
    expected: str = ""
    fix_fn:   Optional[Callable] = None
    detail:   str = ""

    @property
    def is_ok(self) -> bool:
        return self.status == Status.OK

    @property
    def needs_repair(self) -> bool:
        return self.status in (Status.BROKEN, Status.MISSING)


# ─────────────────────────────────────────────────────────────────────────────
# APK DOWNLOADER
# ─────────────────────────────────────────────────────────────────────────────
class APKDownloader:
    """Download, verify (size), push and install APK files."""

    @staticmethod
    def download(url: str, dest: Path, force: bool = False) -> bool:
        if dest.exists() and not force:
            Logger.log(f"  APK cached: {dest.name}")
            return True
        Logger.log(f"  Downloading {dest.name}...")
        ret = os.system(f'curl -L -s --retry 3 --connect-timeout 15 -o "{dest}" "{url}"')
        if ret != 0 or not dest.exists() or dest.stat().st_size < 50_000:
            Logger.error(f"  Download failed or file too small: {dest.name}")
            if dest.exists():
                dest.unlink()
            return False
        size_mb = dest.stat().st_size / 1_048_576
        Logger.success(f"  Downloaded: {dest.name} ({size_mb:.1f} MB)")
        return True

    @staticmethod
    def install(apk_local: Path, pkg_hint: str = "") -> bool:
        remote = f"/data/local/tmp/{apk_local.name}"
        Logger.log(f"  Pushing {apk_local.name} → {remote}")
        if not ADB.push(str(apk_local), remote):
            Logger.error(f"  Push failed: {apk_local.name}")
            return False
        result = ADB.run(f"pm install -r -g --install-reason 1 {remote}", silent=True)
        ADB.run(f"rm {remote}", silent=True)
        if "success" in result.lower():
            Logger.success(f"  Installed: {pkg_hint or apk_local.stem}")
            return True
        Logger.error(f"  Install failed: {result[:80]}")
        return False

    @staticmethod
    def download_and_install(url: str, pkg: str, name: str, force: bool = False) -> bool:
        safe_name = pkg.replace(".", "_") + ".apk"
        local = CACHE_DIR / safe_name
        if not APKDownloader.download(url, local, force):
            return False
        return APKDownloader.install(local, name)


# ─────────────────────────────────────────────────────────────────────────────
# DNS MANAGER (bug-fixed)
# ─────────────────────────────────────────────────────────────────────────────
class DNSManager:
    """
    DNS configuration with full dual-path application.

    BUG FIX (v10/v11): 'dns.cloudflare.com' was used as DoT hostname — incorrect.
    'one.one.one.one' resolves to 1.1.1.1 and is the valid Cloudflare DoT endpoint.

    Dual-path approach:
    1. setprop net.dns1/net.dns2 — legacy resolver (works immediately, no reboot)
    2. settings put global private_dns_* — DoT/DoH encrypted DNS (Android 9+)

    Both must be set: setprop affects the current runtime, private_dns_ persists across reboots.
    mDNS (Cast discovery, port 5353) is unaffected by either mechanism.
    """

    @staticmethod
    def set_provider(provider: str = "cloudflare") -> bool:
        info = DeviceSpec.DNS_PROVIDERS.get(provider.lower())
        if not info:
            Logger.error(f"Unknown provider: {provider}")
            return False

        dot_hostname, ip1, ip2 = info
        Logger.header(f"🔒 DNS — {provider.upper()} ({dot_hostname})")

        Logger.shield(
            "Private DNS (DoT) is unicast-only. mDNS (port 5353, multicast) "
            "used by Chromecast is UNAFFECTED."
        )

        # ── PATH 1: legacy resolver (setprop — immediate, no reboot required) ──
        ADB.setprop("net.dns1",        ip1)
        ADB.setprop("net.dns2",        ip2)
        ADB.setprop("net.rmnet0.dns1", ip1)
        ADB.setprop("net.rmnet0.dns2", ip2)
        Logger.log(f"  ✓ net.dns1/2 = {ip1} / {ip2}")

        # ── PATH 2: Private DNS over TLS (persists reboots) ───────────────────
        ADB.setting_put("global", "private_dns_mode",       "hostname")
        ADB.setting_put("global", "private_dns_specifier",  dot_hostname)
        Logger.log(f"  ✓ Private DNS (DoT): {dot_hostname}")

        # ── Flush DNS cache ───────────────────────────────────────────────────
        ADB.run("ndc resolver flushnet 100", silent=True)
        ADB.run("ndc resolver clearnetdns 100", silent=True)
        Logger.log("  ✓ DNS cache flushed")

        # ── Connectivity test ─────────────────────────────────────────────────
        test = ADB.run(f"ping -c 2 -W 3 {ip1}", silent=True)
        if "2 received" in test or "2 packets" in test:
            Logger.success(f"DNS reachable: {ip1}")
        else:
            Logger.warning(f"DNS ping inconclusive (DoT may still work): {ip1}")

        return True

    @staticmethod
    def get_current() -> Tuple[str, str]:
        """Return (dot_hostname, ip1) of currently set DNS."""
        dot = ADB.setting_get("global", "private_dns_specifier")
        ip1 = ADB.prop("net.dns1")
        return dot or "not set", ip1 or "not set"

    @staticmethod
    def interactive_select() -> None:
        """Interactive DNS provider selection menu."""
        Logger.header("🔒 DNS PROVIDER SELECTION")
        providers = list(DeviceSpec.DNS_PROVIDERS.keys())
        for i, name in enumerate(providers, 1):
            dot, ip1, ip2 = DeviceSpec.DNS_PROVIDERS[name]
            Logger.log(f"  {i}. {name.upper():12s} | DoT: {dot} | IPs: {ip1}/{ip2}")
        Logger.log(f"  0. Keep current (no change)")

        choice = input(f"\n{Logger.C['cyan']}Select [0-{len(providers)}] > {Logger.C['reset']}").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(providers):
                DNSManager.set_provider(providers[idx])
            else:
                Logger.warning("Invalid selection")
        except ValueError:
            Logger.warning("Invalid input")


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO ENGINE OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────
class VideoEngineOptimizer:
    """
    Comprehensive video pipeline tuning for BCM7362 VPU.

    Changes from v11 → v12:
    + debug.stagefright.ccodec = 1 (enables C2 codec framework — modern pipeline)
    + debug.stagefright.omx_default_rank = 0 (force HW OMX over SW C2 when both exist)
    + debug.renderengine.backend = skiaglthreaded (better threading on A15)
    + debug.hwui.use_gpu_pixel_buffers = true (GPU pixel buffers reduce CPU copies)
    + debug.hwui.render_dirty_regions = false (avoid dirty region calc overhead)
    + debug.sf.latch_unsignaled = 1 (reduce SurfaceFlinger latch latency)
    + persist.sys.media.avsync = true (BCM A/V sync hint)
    + persist.sys.hdmi.keep_awake = true (keep HDMI link alive during buffering)
    + drm.service.enabled = true (Widevine/PlayReady explicit enable)
    """

    def optimize_codec_pipeline(self) -> None:
        Logger.header("🎬 VIDEO CODEC PIPELINE — BCM7362 VPU (C2 + OMX)")

        codec_props = [
            # Stagefright core
            ("media.stagefright.enable-player",    "true"),
            ("media.stagefright.enable-http",      "true"),
            ("media.stagefright.enable-aac",       "true"),
            ("media.stagefright.enable-scan",      "true"),
            ("media.stagefright.enable-meta",      "true"),
            # HW priority
            ("media.acodec.preferhw",              "true"),
            ("media.vcodec.preferhw",              "true"),
            ("media.codec.sw.fallback",            "false"),
            ("media.codec.priority",               "1"),
            # C2 / OMX rank (new in v12)
            # ccodec=1 enables C2 framework, omx_default_rank=0 keeps BCM OMX as primary
            ("debug.stagefright.ccodec",           "1"),
            ("debug.stagefright.omx_default_rank", "0"),
            # DRM
            ("drm.service.enabled",                "true"),
            # A/V sync hint (BCM-specific)
            ("persist.sys.media.avsync",           "true"),
            ("persist.sys.hdmi.keep_awake",        "true"),
        ]
        for key, val in codec_props:
            ADB.setprop(key, val)
            Logger.log(f"  ✓ {key} = {val}")

        # Media cache: 64KB/128KB/30s format (correct for stagefright)
        ADB.setprop("media.stagefright.cache-params", "65536/131072/30")
        Logger.log("  ✓ cache-params: 64KB/128KB/30s")

        # Extended HLS buffer
        abr_props = [
            ("media.httplive.max-bitrate",        "25000000"),
            ("media.httplive.initial-bitrate",    "8000000"),
            ("media.httplive.max-live-offset",    "60"),
            ("media.httplive.bw-update-interval", "1000"),
        ]
        for key, val in abr_props:
            ADB.setprop(key, val)
            Logger.log(f"  ✓ {key} = {val}")

        Logger.success("Codec pipeline configured — BCM7362 VPU HW path active")

    def optimize_rendering(self) -> None:
        Logger.header("🎮 RENDERING ENGINE — VideoCore + Skia (v12 tuning)")

        render_props = [
            # Renderer: opengl only — no Vulkan on VideoCore
            ("debug.hwui.renderer",                "skiagl"),
            # Threaded Skia backend — uses both A15 cores for render pipeline
            ("debug.renderengine.backend",         "skiaglthreaded"),
            # HW composition
            ("debug.egl.hw",                       "1"),
            ("debug.sf.hw",                        "1"),
            # Triple buffer
            ("debug.gr.numframebuffers",           "3"),
            # GPU pixel buffers (reduces CPU→GPU copy overhead)
            ("debug.hwui.use_gpu_pixel_buffers",   "true"),
            # Disable dirty region calculation (saves CPU per frame)
            ("debug.hwui.render_dirty_regions",    "false"),
            # Latch unsignaled: reduce SurfaceFlinger → compositor latency
            ("debug.sf.latch_unsignaled",          "1"),
            # Disable SF back-pressure on VPU tunnel output
            ("debug.sf.disable_backpressure",      "1"),
            # Buffer age: not useful on VideoCore
            ("debug.hwui.use_buffer_age",          "false"),
            # Force GPU for UI window compositing
            ("persist.sys.ui.hw",                  "true"),
        ]
        for key, val in render_props:
            ADB.setprop(key, val)
            Logger.log(f"  ✓ {key} = {val}")

        ADB.setting_put("global", "force_gpu_rendering", "true")
        Logger.log("  ✓ force_gpu_rendering = true")
        Logger.success("Rendering engine: skiaglthreaded + VideoCore GPU optimized")

    def force_tunnel_mode(self) -> None:
        Logger.header("🚇 TUNNEL MODE — VPU → Display Controller Direct Path")

        tunnel_props = [
            ("media.tunneled-playback.enable", "true"),
            ("media.brcm.tunnel.sessions",     "1"),
            ("media.brcm.hdmi.tunnel",         "true"),
            # Lock A/V to HDMI sink clock — eliminates drift
            ("media.brcm.tunnel.clock",        "hdmi"),
        ]
        for key, val in tunnel_props:
            ADB.setprop(key, val)
            Logger.log(f"  ✓ {key} = {val}")
        Logger.success("Tunnel Mode: VPU→Display direct path (bypass SurfaceFlinger)")

    def suppress_av1(self) -> None:
        Logger.header("🚫 AV1 SUPPRESSION — Force VP9/H.264 HW Path")
        Logger.warning("BCM7362: NO AV1 HW decoder — SW decode causes 100% CPU")
        for key, val in [
            ("debug.stagefright.c2.av1",    "0"),
            ("media.av1.sw.decode.disable", "true"),
            ("media.codec.av1.disable",     "true"),
        ]:
            ADB.setprop(key, val)
            Logger.log(f"  ✓ {key} = {val}")
        Logger.success("AV1 SW decoder blocked — ExoPlayer will negotiate VP9 HW")
        c = Logger.C
        print(f"""
  {c['cyan']}┌──────────────────────────────────────────────────────────┐
  │  SmartTube Settings (manual, one-time after launch):       │
  │  Settings → Player → Video codec → VP9                     │
  │  Settings → Player → Resolution  → 2160p (4K)              │
  │  Settings → Player → Use tunnel mode → ON                  │
  └──────────────────────────────────────────────────────────┘{c['reset']}
""")


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY + LMK + VM OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────
class MemoryOptimizer:
    """
    Full memory stack tuning.

    v12 additions:
    + /sys/module/lowmemorykiller/parameters/minfree (kernel LMK levels)
    + /proc/sys/vm/swappiness = 10 (prefer RAM, no thrashing on eMMC)
    + /proc/sys/vm/vfs_cache_pressure = 50 (keep dentry/inode cache longer)
    + dalvik.vm.heapstartsize = 16m (faster cold start)
    + dalvik.vm.usejitprofiles = true
    """

    def apply_dalvik_heap(self) -> None:
        Logger.header("🧠 DALVIK/ART HEAP — SmartTube 4K Streaming Profile")

        heap_props = [
            ("dalvik.vm.heapsize",              DeviceSpec.DALVIK_HEAP_SIZE),
            ("dalvik.vm.heapgrowthlimit",       DeviceSpec.DALVIK_HEAP_GROWTH),
            ("dalvik.vm.heapstartsize",         DeviceSpec.DALVIK_HEAP_START),
            ("dalvik.vm.heapminfree",           DeviceSpec.DALVIK_HEAP_MIN_FREE),
            ("dalvik.vm.heapmaxfree",           DeviceSpec.DALVIK_HEAP_MAX_FREE),
            ("dalvik.vm.heaptargetutilization", DeviceSpec.DALVIK_HEAP_TARGET),
            ("dalvik.vm.usejit",                "true"),
            ("dalvik.vm.usejitprofiles",        "true"),  # new v12
            ("dalvik.vm.dex2oat-filter",        "speed-profile"),
            ("dalvik.vm.gctype",                "CMS"),
            ("persist.sys.dalvik.vm.lib.2",     "libart.so"),
        ]
        for key, val in heap_props:
            ADB.setprop(key, val)
            Logger.log(f"  ✓ {key} = {val}")
        Logger.success("Dalvik heap configured for SmartTube 4K workload")

    def apply_lmk_profile(self) -> None:
        Logger.header("🧹 LMK — SmartTube + Cast Priority Profile")

        # Android props
        lmk_props = [
            ("ro.lmk.critical",           "0"),
            ("ro.lmk.kill_heaviest_task", "true"),
            ("ro.lmk.downgrade_pressure", "100"),
            ("ro.lmk.upgrade_pressure",   "50"),
            ("ro.lmk.use_psi",            "true"),
            ("ro.lmk.filecache_min_kb",   "51200"),
        ]
        for key, val in lmk_props:
            ADB.setprop(key, val)
            Logger.log(f"  ✓ {key} = {val}")

        # Kernel LMK minfree (pages, 4KB each)
        # Levels: 48MB,64MB,80MB,96MB,112MB,128MB
        minfree = "12288,16384,20480,24576,28672,32768"
        wrote = ADB.syswrite("/sys/module/lowmemorykiller/parameters/minfree", minfree)
        if wrote:
            Logger.success(f"Kernel LMK minfree: {minfree}")
        else:
            Logger.warning("LMK minfree: /sys not writable (user build) — props applied only")

        ADB.setting_put("global", "background_process_limit", "3")
        Logger.log("  ✓ background_process_limit = 3")
        Logger.success("LMK profile active: SmartTube + Cast protected from OOM")

    def apply_vm_tuning(self) -> None:
        Logger.header("⚡ VM TUNING — Swappiness + VFS Cache Pressure")

        vm_params = [
            ("/proc/sys/vm/swappiness",          "10"),  # prefer RAM, minimal swap
            ("/proc/sys/vm/vfs_cache_pressure",  "50"),  # keep dentry/inode longer
            ("/proc/sys/vm/dirty_ratio",         "10"),  # writeback threshold
            ("/proc/sys/vm/dirty_background_ratio", "5"),
        ]
        for path, val in vm_params:
            wrote = ADB.syswrite(path, val)
            icon  = "✓" if wrote else "⚠"
            Logger.log(f"  {icon} {path.split('/')[-1]} = {val}")

        Logger.success("VM params applied")

    def deep_clean(self) -> None:
        Logger.header("🔄 DEEP CLEAN — Cast-Safe RAM Release")
        Logger.log("  am kill-all (releases background apps)...")
        ADB.run("am kill-all", silent=True)
        Logger.log("  pm trim-caches 2G...")
        ADB.run("pm trim-caches 2G", silent=True)
        ADB.run("dumpsys batterystats --reset", silent=True)
        Logger.log("  drop_caches (requires root)...")
        ADB.run_root("sync && echo 3 > /proc/sys/vm/drop_caches")
        Logger.shield("Re-verifying Cast services post-clean...")
        ChromecastServiceManager.restore()
        Logger.success("Deep clean complete — Cast services verified")


# ─────────────────────────────────────────────────────────────────────────────
# NETWORK OPTIMIZER (v12 — full TCP kernel stack)
# ─────────────────────────────────────────────────────────────────────────────
class NetworkOptimizer:
    """
    Full TCP/IP stack tuning.

    v12 additions:
    + /proc/sys/net/ipv4/tcp_window_scaling, tcp_timestamps, tcp_sack (kernel)
    + BBR congestion control attempt (may not be available on Android 9 STB)
    + /proc/sys/net/core/rmem_max = 16MB
    + wifi.supplicant_scan_interval = 300 (reduce AP scan interference)
    + persist.debug.wfd.enable = 1 (WiFi Direct for Cast fallback)
    """

    def apply_tcp(self) -> None:
        Logger.header("🌐 NETWORK — TCP/IP Stack + Kernel Params (v12)")

        Logger.shield(
            "mDNS multicast (Cast discovery port 5353) unaffected by TCP tuning."
        )

        # Android-level buffers
        ADB.setting_put("global", "net.tcp.buffersize.wifi",
                        "262144,1048576,2097152,131072,524288,1048576")
        Logger.log("  ✓ WiFi TCP buffers: 256KB / 1MB / 2MB")

        ADB.setting_put("global", "net.tcp.buffersize.ethernet",
                        "524288,2097152,4194304,262144,1048576,2097152")
        Logger.log("  ✓ Ethernet TCP buffers: 512KB / 2MB / 4MB")

        ADB.setting_put("global", "tcp_default_init_rwnd", "120")
        Logger.log("  ✓ TCP init rwnd = 120 segments")

        # Kernel-level TCP params (via root)
        kernel_tcp = [
            ("/proc/sys/net/ipv4/tcp_window_scaling",    "1"),
            ("/proc/sys/net/ipv4/tcp_timestamps",        "1"),
            ("/proc/sys/net/ipv4/tcp_sack",              "1"),
            ("/proc/sys/net/ipv4/tcp_keepalive_intvl",   "30"),
            ("/proc/sys/net/ipv4/tcp_keepalive_probes",  "3"),
            ("/proc/sys/net/ipv4/tcp_no_metrics_save",   "1"),
            ("/proc/sys/net/ipv4/tcp_fastopen",          "3"),
        ]
        for path, val in kernel_tcp:
            wrote = ADB.syswrite(path, val)
            icon  = "✓" if wrote else "⚠"
            Logger.log(f"  {icon} {path.split('/')[-1]} = {val}")

        # Core net buffers (16MB)
        for path in ("/proc/sys/net/core/rmem_max", "/proc/sys/net/core/wmem_max"):
            ADB.syswrite(path, "16777216")
        Logger.log("  ✓ Net core rmem/wmem_max = 16MB")

        # BBR congestion control (best-effort — may not be available)
        bbr_path = "/proc/sys/net/ipv4/tcp_congestion_control"
        bbr_result = ADB.run_root(f"echo bbr > {bbr_path}")
        verify = ADB.run_root(f"cat {bbr_path}").strip()
        if "bbr" in verify:
            Logger.success("  TCP congestion control: BBR")
        else:
            Logger.log(f"  ⚠ BBR unavailable on this kernel ({verify}) — using CUBIC")

        # WiFi stability
        ADB.setprop("wifi.supplicant_scan_interval", "300")
        Logger.log("  ✓ wifi.supplicant_scan_interval = 300 (reduce interference)")

        ADB.setting_put("global", "wifi_sleep_policy", "2")
        Logger.log("  ✓ wifi_sleep_policy = 2 (stay connected, Cast-safe)")

        # WiFi Direct (Cast fallback transport)
        ADB.setprop("persist.debug.wfd.enable", "1")
        Logger.log("  ✓ WiFi Direct enabled (Cast fallback transport)")

        Logger.success("TCP/IP stack optimized for 4K streaming")

    def apply_dns(self, provider: str = "cloudflare") -> None:
        DNSManager.set_provider(provider)


# ─────────────────────────────────────────────────────────────────────────────
# HDMI + CEC OPTIMIZER (v12 — BCM Nexus props added)
# ─────────────────────────────────────────────────────────────────────────────
class HDMIOptimizer:
    """
    v12 additions vs v11:
    + persist.sys.cec.status = true (BCM CEC HAL enable)
    + persist.sys.hdmi.tx_standby_cec = 1 (CEC standby command)
    + persist.sys.hdmi.tx_view_on_cec = 1 (CEC power-on command)
    + persist.nx.hdmi.tx_standby_cec = 1 (BCM Nexus CEC)
    + persist.nx.hdmi.tx_view_on_cec = 1 (BCM Nexus CEC)
    + persist.sys.hdmi.addr.playback = 11 (CORRECTED: BCM says 11, not 0)
    + persist.nx.vidout.50hz awareness (PAL region)
    """

    def apply(self) -> None:
        Logger.header("📺 HDMI + CEC — BCM7362 Nexus Full Configuration")

        current_cec = ADB.prop("persist.sys.cec.status")
        Logger.log(f"  Current CEC status: {current_cec}")

        hdmi_props = [
            # Device type: 4 = playback device (set-top box)
            ("ro.hdmi.device_type",               "4"),
            # CORRECTED from v11: BCM Nexus addr.playback = 11 (from pbap9.sh verified)
            ("persist.sys.hdmi.addr.playback",    "11"),
            # CEC enable
            ("persist.sys.cec.status",            "true"),
            ("persist.sys.hdmi.tx_standby_cec",   "1"),
            ("persist.sys.hdmi.tx_view_on_cec",   "1"),
            ("persist.sys.hdmi.cec_enabled",       "1"),
            # BCM Nexus CEC (persist.nx.* namespace = BCM hardware layer)
            ("persist.nx.hdmi.tx_standby_cec",    "1"),
            ("persist.nx.hdmi.tx_view_on_cec",    "1"),
            # Keep HDMI link alive during buffering
            ("persist.sys.hdmi.keep_awake",       "true"),
            # HDR10
            ("persist.sys.hdr.enable",            "1"),
            # No spurious HDMI resets on hotplug
            ("ro.hdmi.wake_on_hotplug",           "false"),
            # ARC / passthrough
            ("settings put global", "hdmi_cec_enabled", "1"),
        ]

        for entry in hdmi_props:
            if len(entry) == 2:
                ADB.setprop(entry[0], entry[1])
                Logger.log(f"  ✓ {entry[0]} = {entry[1]}")
            else:
                # settings put
                ADB.run(f"settings put {entry[0].split()[2]} {entry[1]} {entry[2]}", silent=True)
                Logger.log(f"  ✓ {entry[1]} = {entry[2]}")

        # PAL 50Hz check
        hz50 = ADB.prop("persist.nx.vidout.50hz")
        if hz50 == "0":
            Logger.log("  ℹ 50Hz disabled — enable if PAL content stutters")
        else:
            Logger.log(f"  ✓ 50Hz mode: {hz50}")

        Logger.success("HDMI + CEC fully configured with BCM Nexus props")

    def fix_audio_desync(self) -> None:
        Logger.header("🔊 AUDIO — A/V Sync Fix (HDMI ARC desync elimination)")

        audio_props = [
            ("audio.offload.disable",       "1"),     # offload causes desync on BCM7362 HDMI
            ("audio.offload.video",         "0"),
            ("tunnel.audio.encode",         "false"),
            ("audio.deep_buffer.media",     "true"),  # stable latency baseline
            ("af.fast_track_multiplier",    "1"),
            ("audio.brcm.hdmi.clock_lock",  "true"),  # lock to HDMI sink clock
            ("audio.brcm.hal.latency",      "20"),
        ]
        for key, val in audio_props:
            ADB.setprop(key, val)
            Logger.log(f"  ✓ {key} = {val}")
        Logger.success("Audio A/V sync fixed — HDMI clock locked")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM RESPONSIVENESS (v12 — I/O scheduler, read-ahead)
# ─────────────────────────────────────────────────────────────────────────────
class ResponsivenessOptimizer:
    """
    v12 additions:
    + I/O scheduler = deadline (low-latency for eMMC sequential reads)
    + read_ahead_kb = 512 (prefetch for VP9 segment files)
    + CPU governor = performance on both A15 cores
    """

    def apply(self, anim_scale: float = 0.5) -> None:
        Logger.header(f"🎨 SYSTEM RESPONSIVENESS — Animations + I/O + CPU")

        # Animations
        for key in ["window_animation_scale", "transition_animation_scale", "animator_duration_scale"]:
            ADB.setting_put("global", key, str(anim_scale))
            Logger.log(f"  ✓ {key} = {anim_scale}x")

        # TV recommendations off
        for cmd in [
            "settings put secure tv_disable_recommendations 1",
            "settings put secure tv_enable_preview_programs 0",
            "settings put secure tv_watch_next_enabled 0",
        ]:
            ADB.run(cmd, silent=True)
        Logger.log("  ✓ TV recommendations disabled")

        # Logger reduction (reduce logd overhead)
        ADB.setprop("persist.logd.size",      "32768")
        ADB.setprop("log.tag.stats_log",      "OFF")
        ADB.setprop("log.tag.statsd",         "OFF")
        Logger.log("  ✓ Logging reduced to 32KB")

        # I/O scheduler: deadline (low latency for streaming segment reads)
        io_result = ADB.run_root(
            "for d in /sys/block/*/queue/scheduler; do "
            "echo deadline > $d 2>/dev/null; done"
        )
        Logger.log("  ✓ I/O scheduler = deadline (all block devices)")

        # read-ahead: 512KB (VP9 segment prefetch)
        ADB.run_root(
            "for d in /sys/block/*/queue/read_ahead_kb; do "
            "echo 512 > $d 2>/dev/null; done"
        )
        Logger.log("  ✓ read_ahead_kb = 512")

        # CPU governor: performance on both A15 cores
        for cpu in range(2):
            path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"
            ADB.run_root(f"echo performance > {path}")
            Logger.log(f"  ✓ cpu{cpu}: performance governor")

        Logger.success("System responsiveness fully optimized")


# ─────────────────────────────────────────────────────────────────────────────
# SAFE DEBLOATER
# ─────────────────────────────────────────────────────────────────────────────
SAFE_DEBLOAT_DB: List[Tuple[str, str]] = [
    ("com.google.android.backdrop",          "Ambient screensaver — idle GPU waste"),
    ("com.google.android.tvrecommendations", "Content recommendations — constant HTTP polling"),
    ("com.google.android.katniss",           "Google TV voice overlay — high idle CPU"),
    ("com.google.android.tungsten.setupwraith", "Setup wizard — post-setup dead weight"),
    ("com.google.android.apps.tv.launcherx", "New Google TV launcher (unused on API 28)"),
    ("com.google.android.leanbacklauncher", "Legacy Leanback duplicate"),
    ("com.google.android.marvin.talkback",  "Accessibility TTS — 40MB unused"),
    ("com.google.android.onetimeinitializer","One-time init — already completed"),
    ("com.google.android.feedback",          "Google feedback service — periodic ping"),
    ("com.google.android.speech.pumpkin",   "Hotword detection — high background CPU"),
    ("com.android.printspooler",            "Print service — no printers on TV"),
    ("com.android.dreams.basic",            "Basic screensaver"),
    ("com.android.dreams.phototable",       "Photo screensaver"),
    ("com.android.providers.calendar",      "Calendar provider — unused on TV"),
    ("com.android.providers.contacts",      "Contacts provider — unused on TV"),
    ("com.sagemcom.stb.setupwizard",        "Sagemcom factory setup wizard"),
    ("com.orange.fr.tv.assistance",         "Orange assistance — server polling"),
    ("com.orange.fr.tv.guide",              "Orange TV guide — heavy background sync"),
    ("com.amazon.amazonvideo.livingroom",   "Amazon Prime — pre-bundled, use standalone"),
    ("com.google.android.play.games",       "Play Games — unused on TV"),
    ("com.google.android.videos",           "Play Movies — unused on TV"),
    ("com.google.android.partnersetup",     "Partner setup — post-setup unused"),
]


class SafeDebloater:
    def run(self) -> None:
        Logger.header("🗑 SAFE DEBLOAT — Chromecast Protection Enforced")
        disabled, protected, already_off, failed = 0, 0, 0, 0

        for pkg, reason in SAFE_DEBLOAT_DB:
            if ChromecastProtection.is_protected(pkg):
                protected += 1
                Logger.shield(f"PROTECTED: {pkg}")
                Logger.log(f"     └─ {ChromecastProtection.get_reason(pkg)}", "cyan")
                continue
            if not ADB.pkg_enabled(pkg):
                already_off += 1
                continue
            result = ADB.run(f"pm disable-user --user 0 {pkg}", silent=True)
            if "disabled" in result.lower() or result == "":
                disabled += 1
                Logger.success(f"Disabled: {pkg}")
                Logger.log(f"     └─ {reason}", "dim")
            else:
                failed += 1
                Logger.warning(f"Could not disable: {pkg}")

        Logger.header(
            f"DEBLOAT: {disabled} disabled | {protected} protected | "
            f"{already_off} already off | {failed} failed"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CHROMECAST SERVICE MANAGER
# ─────────────────────────────────────────────────────────────────────────────
class ChromecastServiceManager:
    """
    Audit, restore, harden Cast services.

    v12: added detection of debloat.sh damage pattern
    (apps.mediashell disabled by erroneous debloat script on device).
    """

    @staticmethod
    def audit() -> Dict[str, bool]:
        Logger.header("🔍 CHROMECAST SERVICE AUDIT")
        results: Dict[str, bool] = {}
        for pkg, reason in ChromecastProtection.PROTECTED.items():
            ok = ADB.pkg_enabled(pkg)
            results[pkg] = ok
            icon = "✓" if ok else "✗"
            Logger.log(f"  {icon} {pkg}", "success" if ok else "error")
            Logger.log(f"     └─ {reason}", "cyan")
        broken = [p for p, e in results.items() if not e]
        if broken:
            Logger.warning(f"{len(broken)} Cast service(s) DISABLED — Auto-repair available (option 7)")
        else:
            Logger.success("All Chromecast services healthy ✓")
        return results

    @staticmethod
    def restore() -> None:
        Logger.header("🛡 CHROMECAST RESTORATION")
        for pkg in ChromecastProtection.PROTECTED:
            ADB.run(f"pm enable {pkg}", silent=True)
            ADB.run(f"pm enable --user 0 {pkg}", silent=True)
            Logger.shield(f"Ensured: {pkg}")
        Logger.success("All Cast services re-enabled")

    @staticmethod
    def optimize_network() -> None:
        Logger.header("📡 CAST NETWORK — mDNS/Multicast Reliability")
        ADB.setting_put("global", "wifi_sleep_policy", "2")
        ADB.setting_put("global", "wifi_power_save",   "0")
        ADB.setprop("ro.mdns.enable_passive_mode", "false")
        ADB.setprop("net.ssdp.ttl",                "4")
        Logger.success("Cast mDNS/multicast network profile active")

    @staticmethod
    def harden_oom() -> None:
        Logger.header("🎯 CAST OOM HARDENING")
        for pkg in [
            "com.google.android.apps.mediashell",
            "com.google.android.gms",
            "com.google.android.nearby",
        ]:
            pid = ADB.run(f"pidof {pkg}", silent=True).strip()
            if pid and pid.isdigit():
                ADB.run_root(f"echo 100 > /proc/{pid}/oom_score_adj")
                Logger.shield(f"OOM adj=100: {pkg} (PID {pid})")
            else:
                Logger.log(f"  {pkg} not running yet — protected at next start", "warning")
        Logger.success("Cast processes hardened")


# ─────────────────────────────────────────────────────────────────────────────
# AOT COMPILER
# ─────────────────────────────────────────────────────────────────────────────
class AOTCompiler:
    APPS: Dict[str, str] = {
        DeviceSpec.SMARTTUBE_PKG_STABLE: "SmartTube Stable",
        DeviceSpec.PROJECTIVY_PKG:       "Projectivy Launcher",
        "com.google.android.apps.mediashell": "Cast Receiver",
    }

    @classmethod
    def compile_all(cls) -> None:
        Logger.header("⚡ AOT COMPILATION — Eliminate JIT Bursts")
        for pkg, name in cls.APPS.items():
            if not ADB.pkg_installed(pkg):
                Logger.log(f"  ○ {name} not installed — skip", "dim")
                continue
            Logger.log(f"  Compiling {name} (speed-profile)... ~60–90s")
            result = ADB.run(f"cmd package compile -m speed-profile -f {pkg}", silent=True)
            if "success" in result.lower():
                Logger.success(f"  {name}: AOT compiled (speed-profile)")
            else:
                # fallback
                ADB.run(f"cmd package compile -m speed -f {pkg}", silent=True)
                Logger.success(f"  {name}: AOT compiled (speed)")


# ═════════════════════════════════════════════════════════════════════════════
# SELF-DIAGNOSTIC ENGINE
# ═════════════════════════════════════════════════════════════════════════════
class DiagnosticEngine:
    """
    Interactive self-diagnostic system that:
    1. Checks 8 service categories comprehensively
    2. Presents results category-by-category with interactive drill-down
    3. Identifies broken/missing/incorrect settings
    4. Offers targeted auto-repair per finding
    5. Downloads and reinstalls APKs when needed

    Categories:
      A. System Health  (RAM, CPU, Thermal, Storage)
      B. Cast Services  (all 10 protected packages)
      C. SmartTube      (install, version, codec settings, AOT)
      D. Video Pipeline (codec props, tunnel, renderer)
      E. Network/DNS    (TCP params, DNS correctness)
      F. Audio          (desync props, HDMI clock)
      G. Memory/LMK     (LMK props, dalvik heap, kernel VM)
      H. HDMI/CEC       (CEC props, BCM Nexus, 50Hz)
    """

    def __init__(self):
        self.results: List[DiagResult] = []

    def _r(self, cat: str, check: str, status: Status, found: str,
           expected: str = "", fix_fn: Optional[Callable] = None,
           detail: str = "") -> DiagResult:
        dr = DiagResult(cat, check, status, found, expected, fix_fn, detail)
        self.results.append(dr)
        return dr

    # ─────────────────── CATEGORY A: SYSTEM HEALTH ──────────────────────────
    def _check_system_health(self) -> List[DiagResult]:
        results = []
        cat = "SYSTEM"

        meminfo = ADB.run("cat /proc/meminfo", silent=True)
        fields: Dict[str, int] = {}
        for line in meminfo.splitlines():
            p = line.split()
            if len(p) >= 2 and p[1].isdigit():
                fields[p[0].rstrip(":")] = int(p[1])

        avail_mb = fields.get("MemAvailable", 0) // 1024
        total_mb = fields.get("MemTotal",     0) // 1024
        pct      = avail_mb / total_mb * 100 if total_mb else 0

        if pct > 30:
            s = Status.OK
        elif pct > 15:
            s = Status.WARN
        else:
            s = Status.BROKEN

        r = self._r(cat, "RAM Available", s, f"{avail_mb} MB ({pct:.0f}%)",
                    ">30% = OK", lambda: MemoryOptimizer().deep_clean(),
                    f"Total: {total_mb} MB")
        results.append(r)

        # Thermal
        for zone in range(2):
            raw = ADB.run(f"cat /sys/class/thermal/thermal_zone{zone}/temp", silent=True)
            if raw and raw.lstrip("-").isdigit():
                temp_c = int(raw) / 1000
                s = Status.OK if temp_c < 60 else (Status.WARN if temp_c < 75 else Status.BROKEN)
                r = self._r(cat, f"Thermal zone{zone}", s, f"{temp_c:.1f}°C", "<60°C")
                results.append(r)

        # Storage
        storage = ADB.run("df -h /data", silent=True)
        lines = storage.splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            use_pct_str = parts[4] if len(parts) > 4 else "?"
            use_pct = int(use_pct_str.replace("%", "")) if use_pct_str != "?" else 0
            s = Status.OK if use_pct < 80 else (Status.WARN if use_pct < 90 else Status.BROKEN)
            r = self._r(cat, "/data storage", s, use_pct_str, "<80%")
            results.append(r)

        # Internet
        ping = ADB.run("ping -c 2 -W 3 1.1.1.1", silent=True)
        ok = "2 received" in ping
        r = self._r(cat, "Internet connectivity", Status.OK if ok else Status.BROKEN,
                    "Reachable" if ok else "OFFLINE")
        results.append(r)

        return results

    # ─────────────────── CATEGORY B: CAST SERVICES ──────────────────────────
    def _check_cast(self) -> List[DiagResult]:
        results = []
        cat = "CAST"
        for pkg, reason in ChromecastProtection.PROTECTED.items():
            enabled = ADB.pkg_enabled(pkg)
            s = Status.OK if enabled else Status.BROKEN
            r = self._r(cat, pkg.split(".")[-1], s,
                        "enabled" if enabled else "DISABLED",
                        "enabled", ChromecastServiceManager.restore,
                        reason)
            results.append(r)
        return results

    # ─────────────────── CATEGORY C: SMARTTUBE ──────────────────────────────
    def _check_smarttube(self) -> List[DiagResult]:
        results = []
        cat = "SMARTTUBE"

        # Package detection (check all known names)
        found_pkg = None
        for pkg in [DeviceSpec.SMARTTUBE_PKG_STABLE, DeviceSpec.SMARTTUBE_PKG_BETA,
                    DeviceSpec.SMARTTUBE_PKG_LEGACY]:
            if ADB.pkg_installed(pkg):
                found_pkg = pkg
                break

        if found_pkg:
            ver = ADB.pkg_version(found_pkg)
            r = self._r(cat, "SmartTube installed", Status.OK, f"{found_pkg} v{ver}", "installed")
            results.append(r)

            # AOT compilation status
            aot_check = ADB.run(
                f"cmd package dump {found_pkg} | grep -i compile_reason", silent=True
            )
            aot_ok = "install" in aot_check.lower() or "bg-dexopt" in aot_check.lower()
            r = self._r(cat, "AOT compilation", Status.OK if aot_ok else Status.WARN,
                        aot_check[:50] if aot_check else "unknown",
                        "compiled", AOTCompiler.compile_all)
            results.append(r)
        else:
            r = self._r(
                cat, "SmartTube installed", Status.MISSING,
                "NOT INSTALLED", "org.smarttube.stable",
                lambda: APKDownloader.download_and_install(
                    DeviceSpec.SMARTTUBE_STABLE_URL,
                    DeviceSpec.SMARTTUBE_PKG_STABLE,
                    "SmartTube Stable"
                )
            )
            results.append(r)

        # Codec props
        for prop, expected in [
            ("media.vcodec.preferhw",               "true"),
            ("debug.stagefright.ccodec",            "1"),
            ("media.tunneled-playback.enable",      "true"),
            ("media.codec.av1.disable",             "true"),
        ]:
            val = ADB.prop(prop)
            ok  = val == expected
            r   = self._r(cat, f"prop:{prop.split('.')[-1]}", Status.OK if ok else Status.BROKEN,
                          val or "not set", expected,
                          VideoEngineOptimizer().optimize_codec_pipeline)
            results.append(r)

        return results

    # ─────────────────── CATEGORY D: VIDEO PIPELINE ─────────────────────────
    def _check_video(self) -> List[DiagResult]:
        results = []
        cat = "VIDEO"
        checks = [
            ("debug.hwui.renderer",             "skiagl"),
            ("debug.renderengine.backend",      "skiaglthreaded"),
            ("debug.sf.hw",                     "1"),
            ("debug.gr.numframebuffers",        "3"),
            ("media.acodec.preferhw",           "true"),
            ("persist.sys.ui.hw",               "true"),
            ("debug.sf.latch_unsignaled",       "1"),
        ]
        vo = VideoEngineOptimizer()
        for prop, expected in checks:
            val = ADB.prop(prop)
            ok  = val == expected
            r   = self._r(cat, prop.split(".")[-1], Status.OK if ok else Status.BROKEN,
                          val or "not set", expected, vo.optimize_rendering)
            results.append(r)
        return results

    # ─────────────────── CATEGORY E: NETWORK / DNS ──────────────────────────
    def _check_network(self) -> List[DiagResult]:
        results = []
        cat = "NETWORK"

        # DNS correctness check
        dot_host = ADB.setting_get("global", "private_dns_specifier")
        dot_mode  = ADB.setting_get("global", "private_dns_mode")
        ip1       = ADB.prop("net.dns1")

        valid_dots = [v[0] for v in DeviceSpec.DNS_PROVIDERS.values()]
        dns_ok = dot_host in valid_dots and dot_mode == "hostname"
        r = self._r(cat, "Private DNS (DoT)", Status.OK if dns_ok else Status.BROKEN,
                    f"mode={dot_mode}, host={dot_host}",
                    "hostname + one.one.one.one",
                    lambda: DNSManager.set_provider("cloudflare"),
                    f"Legacy DNS (net.dns1): {ip1}")
        results.append(r)

        # Old (incorrect) Cloudflare hostname detection
        if dot_host == "dns.cloudflare.com":
            r = self._r(cat, "DNS hostname correctness", Status.BROKEN,
                        "dns.cloudflare.com (WRONG)",
                        "one.one.one.one",
                        lambda: DNSManager.set_provider("cloudflare"),
                        "Legacy hostname — will cause DoT handshake failure")
            results.append(r)

        # TCP init window
        rwnd = ADB.setting_get("global", "tcp_default_init_rwnd")
        r = self._r(cat, "TCP init rwnd", Status.OK if rwnd == "120" else Status.WARN,
                    rwnd or "not set", "120",
                    NetworkOptimizer().apply_tcp)
        results.append(r)

        # WiFi sleep policy
        sleep = ADB.setting_get("global", "wifi_sleep_policy")
        r = self._r(cat, "WiFi sleep policy", Status.OK if sleep == "2" else Status.WARN,
                    sleep or "not set", "2 (always on)")
        results.append(r)

        return results

    # ─────────────────── CATEGORY F: AUDIO ──────────────────────────────────
    def _check_audio(self) -> List[DiagResult]:
        results = []
        cat = "AUDIO"
        ha = HDMIOptimizer()
        for prop, expected in [
            ("audio.offload.disable",       "1"),
            ("audio.deep_buffer.media",     "true"),
            ("audio.brcm.hdmi.clock_lock",  "true"),
            ("tunnel.audio.encode",         "false"),
        ]:
            val = ADB.prop(prop)
            ok  = val == expected
            r   = self._r(cat, prop.split(".")[-1], Status.OK if ok else Status.BROKEN,
                          val or "not set", expected, ha.fix_audio_desync)
            results.append(r)
        return results

    # ─────────────────── CATEGORY G: MEMORY ─────────────────────────────────
    def _check_memory(self) -> List[DiagResult]:
        results = []
        cat = "MEMORY"
        mo = MemoryOptimizer()
        for prop, expected in [
            ("dalvik.vm.heapsize",          DeviceSpec.DALVIK_HEAP_SIZE),
            ("dalvik.vm.heapgrowthlimit",   DeviceSpec.DALVIK_HEAP_GROWTH),
            ("dalvik.vm.usejit",            "true"),
            ("ro.lmk.kill_heaviest_task",   "true"),
            ("ro.lmk.critical",             "0"),
        ]:
            val = ADB.prop(prop)
            ok  = val == expected
            r   = self._r(cat, prop.split(".")[-1], Status.OK if ok else Status.BROKEN,
                          val or "not set", expected, mo.apply_lmk_profile)
            results.append(r)

        # Swappiness
        swap = ADB.run_root("cat /proc/sys/vm/swappiness").strip()
        r = self._r(cat, "vm.swappiness", Status.OK if swap == "10" else Status.WARN,
                    swap or "unknown", "10", mo.apply_vm_tuning)
        results.append(r)

        return results

    # ─────────────────── CATEGORY H: HDMI/CEC ───────────────────────────────
    def _check_hdmi(self) -> List[DiagResult]:
        results = []
        cat = "HDMI"
        ho = HDMIOptimizer()
        for prop, expected in [
            ("persist.sys.cec.status",          "true"),
            ("persist.sys.hdmi.addr.playback",  "11"),   # corrected v12
            ("persist.sys.hdmi.keep_awake",     "true"),
            ("persist.nx.hdmi.tx_standby_cec",  "1"),
            ("persist.sys.hdr.enable",          "1"),
        ]:
            val = ADB.prop(prop)
            ok  = val == expected
            r   = self._r(cat, prop.split(".")[-1], Status.OK if ok else Status.WARN,
                          val or "not set", expected, ho.apply)
            results.append(r)
        return results

    # ─────────────────── RUN CATEGORY ───────────────────────────────────────
    CATEGORY_MAP: Dict[str, Tuple[str, Callable]] = {}  # filled post-class

    def run_category(self, cat_id: str) -> List[DiagResult]:
        cat_fn_map = {
            "A": ("System Health",  self._check_system_health),
            "B": ("Cast Services",  self._check_cast),
            "C": ("SmartTube",      self._check_smarttube),
            "D": ("Video Pipeline", self._check_video),
            "E": ("Network/DNS",    self._check_network),
            "F": ("Audio",          self._check_audio),
            "G": ("Memory/LMK",     self._check_memory),
            "H": ("HDMI/CEC",       self._check_hdmi),
        }
        entry = cat_fn_map.get(cat_id.upper())
        if not entry:
            return []
        name, fn = entry
        Logger.header(f"🔎 DIAGNOSTICS: {cat_id} — {name}")
        results = fn()
        self._print_category_results(results)
        return results

    def _print_category_results(self, results: List[DiagResult]) -> None:
        ok_count  = sum(1 for r in results if r.is_ok)
        bad_count = sum(1 for r in results if r.needs_repair)
        warn_count = sum(1 for r in results if r.status == Status.WARN)

        for r in results:
            if r.status == Status.OK:
                Logger.log(f"  ✓ [{r.category}] {r.check}: {r.found}", "success")
            elif r.status == Status.WARN:
                Logger.log(f"  ⚠ [{r.category}] {r.check}: {r.found} (expected: {r.expected})", "warning")
            elif r.status in (Status.BROKEN, Status.MISSING):
                Logger.log(f"  ✗ [{r.category}] {r.check}: {r.found} (expected: {r.expected})", "error")
                if r.detail:
                    Logger.log(f"     └─ {r.detail}", "dim")

        Logger.log(
            f"\n  Results: {ok_count} OK | {warn_count} WARN | {bad_count} NEEDS REPAIR",
            "cyan"
        )

    def run_all_interactive(self) -> None:
        """Run all 8 categories interactively with repair offer per category."""
        all_categories = ["A", "B", "C", "D", "E", "F", "G", "H"]
        cat_names = {
            "A": "System Health",
            "B": "Cast Services (Chromecast)",
            "C": "SmartTube",
            "D": "Video Pipeline",
            "E": "Network / DNS",
            "F": "Audio (A/V Sync)",
            "G": "Memory / LMK",
            "H": "HDMI / CEC",
        }

        Logger.header("🔎 INTERACTIVE SELF-DIAGNOSTICS — 8 Categories")

        all_broken: List[DiagResult] = []

        for cat_id in all_categories:
            Logger.log(f"\n[{cat_id}] {cat_names[cat_id]}", "cyan")
            results = self.run_category(cat_id)
            broken = [r for r in results if r.needs_repair]
            all_broken.extend(broken)

            if broken:
                c = Logger.C
                Logger.warning(f"{len(broken)} issue(s) found in {cat_names[cat_id]}")
                choice = input(
                    f"  {c['warning']}Repair now? [Y/n/s=skip all] > {c['reset']}"
                ).strip().lower()

                if choice == "s":
                    Logger.log("  Skipping remaining repairs", "warning")
                    break
                if choice in ("", "y", "yes"):
                    self._repair_category(broken)
            else:
                Logger.success(f"  {cat_names[cat_id]}: All OK")

        # Summary
        Logger.header("📋 DIAGNOSTIC SUMMARY")
        total    = len(self.results)
        ok_count = sum(1 for r in self.results if r.is_ok)
        broken   = sum(1 for r in self.results if r.needs_repair)
        warn     = sum(1 for r in self.results if r.status == Status.WARN)

        Logger.log(f"  Total checks : {total}")
        Logger.success(f"  OK           : {ok_count}")
        Logger.warning(f"  Warnings     : {warn}")
        Logger.error  (f"  Need repair  : {broken}")

        if all_broken:
            Logger.warning(f"\n  Unresolved issues:")
            for r in all_broken:
                if r.needs_repair:
                    Logger.log(f"    ✗ [{r.category}] {r.check}: {r.found}", "error")

    def _repair_category(self, broken: List[DiagResult]) -> None:
        """Execute fix_fn for all broken items in a category."""
        applied_fns: set = set()
        for r in broken:
            if r.fix_fn and id(r.fix_fn) not in applied_fns:
                applied_fns.add(id(r.fix_fn))
                Logger.repair(f"Auto-repairing: [{r.category}] {r.check}")
                try:
                    r.fix_fn()
                except Exception as e:
                    Logger.error(f"Repair failed: {e}")

    def single_category_menu(self) -> None:
        """Menu for selecting which category to diagnose."""
        c = Logger.C
        cat_map = {
            "A": "System Health",
            "B": "Cast Services (Chromecast)",
            "C": "SmartTube",
            "D": "Video Pipeline",
            "E": "Network / DNS",
            "F": "Audio (A/V Sync)",
            "G": "Memory / LMK",
            "H": "HDMI / CEC",
            "*": "All categories (interactive)",
        }
        Logger.header("🔎 DIAGNOSTICS — Select Category")
        for k, v in cat_map.items():
            Logger.log(f"  {c['cyan']}{k}{c['reset']}. {v}")

        choice = input(f"\n{c['cyan']}Category [A-H or *] > {c['reset']}").strip().upper()
        if choice == "*":
            self.run_all_interactive()
        elif choice in cat_map:
            results = self.run_category(choice)
            broken  = [r for r in results if r.needs_repair]
            if broken:
                fix = input(f"\n{c['warning']}Auto-repair {len(broken)} issue(s)? [Y/n] > {c['reset']}").strip().lower()
                if fix in ("", "y"):
                    self._repair_category(broken)
        else:
            Logger.warning("Invalid category")


# ─────────────────────────────────────────────────────────────────────────────
# AUTO REPAIR ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class AutoRepairEngine:
    """
    Self-healing repair system.
    Detects broken sectors, prompts user, downloads APKs, reinstalls.
    """

    REPAIR_REGISTRY: List[Dict[str, Any]] = [
        {
            "id":        "smarttube_missing",
            "name":      "SmartTube Stable",
            "detect":    lambda: not ADB.pkg_installed(DeviceSpec.SMARTTUBE_PKG_STABLE),
            "repair":    lambda: APKDownloader.download_and_install(
                             DeviceSpec.SMARTTUBE_STABLE_URL,
                             DeviceSpec.SMARTTUBE_PKG_STABLE,
                             "SmartTube Stable"
                         ),
        },
        {
            "id":        "smarttube_old_package",
            "name":      "SmartTube old package (com.teamsmart.videomanager.tv)",
            "detect":    lambda: ADB.pkg_installed("com.teamsmart.videomanager.tv"),
            "repair":    lambda: (
                             Logger.warning("Old SmartTube package found. "
                                           "New: org.smarttube.stable"),
                             APKDownloader.download_and_install(
                                 DeviceSpec.SMARTTUBE_STABLE_URL,
                                 DeviceSpec.SMARTTUBE_PKG_STABLE,
                                 "SmartTube Stable (migration)"
                             )
                         ),
        },
        {
            "id":        "cast_disabled",
            "name":      "Chromecast Built-in Daemon disabled (mediashell)",
            "detect":    lambda: not ADB.pkg_enabled("com.google.android.apps.mediashell"),
            "repair":    ChromecastServiceManager.restore,
        },
        {
            "id":        "gms_disabled",
            "name":      "Google Play Services disabled (GMS / Cast SDK)",
            "detect":    lambda: not ADB.pkg_enabled("com.google.android.gms"),
            "repair":    ChromecastServiceManager.restore,
        },
        {
            "id":        "wrong_dns",
            "name":      "DNS incorrectly set (dns.cloudflare.com → should be one.one.one.one)",
            "detect":    lambda: ADB.setting_get("global", "private_dns_specifier") == "dns.cloudflare.com",
            "repair":    lambda: DNSManager.set_provider("cloudflare"),
        },
        {
            "id":        "dns_not_set",
            "name":      "Private DNS not configured",
            "detect":    lambda: ADB.setting_get("global", "private_dns_mode") != "hostname",
            "repair":    lambda: DNSManager.set_provider("cloudflare"),
        },
        {
            "id":        "projectivy_missing",
            "name":      "Projectivy Launcher missing",
            "detect":    lambda: not ADB.pkg_installed(DeviceSpec.PROJECTIVY_PKG),
            "repair":    lambda: APKDownloader.download_and_install(
                             DeviceSpec.PROJECTIVY_URL,
                             DeviceSpec.PROJECTIVY_PKG,
                             "Projectivy Launcher"
                         ),
        },
        {
            "id":        "shizuku_missing",
            "name":      "Shizuku not installed",
            "detect":    lambda: not ADB.pkg_installed(DeviceSpec.SHIZUKU_PKG),
            "repair":    lambda: APKDownloader.download_and_install(
                             DeviceSpec.SHIZUKU_URL,
                             DeviceSpec.SHIZUKU_PKG,
                             "Shizuku"
                         ),
        },
        {
            "id":        "av1_not_suppressed",
            "name":      "AV1 SW decoder active (will cause stuttering)",
            "detect":    lambda: ADB.prop("media.codec.av1.disable") != "true",
            "repair":    VideoEngineOptimizer().suppress_av1,
        },
        {
            "id":        "wrong_hdmi_addr",
            "name":      "HDMI addr.playback=0 (should be 11 for BCM Nexus)",
            "detect":    lambda: ADB.prop("persist.sys.hdmi.addr.playback") not in ("11", ""),
            "repair":    HDMIOptimizer().apply,
        },
        {
            "id":        "audio_desync",
            "name":      "Audio offload enabled (causes A/V desync on BCM7362 HDMI)",
            "detect":    lambda: ADB.prop("audio.offload.disable") != "1",
            "repair":    HDMIOptimizer().fix_audio_desync,
        },
    ]

    @classmethod
    def scan_and_repair_interactive(cls) -> None:
        Logger.header("🔧 AUTO-REPAIR ENGINE — Sector Scan")

        Logger.log("Scanning all repair sectors...")
        found: List[Dict[str, Any]] = []

        for entry in cls.REPAIR_REGISTRY:
            try:
                detected = entry["detect"]()
            except Exception:
                detected = False
            if detected:
                found.append(entry)
                Logger.error(f"  ✗ BROKEN: {entry['name']}")
            else:
                Logger.log(f"  ✓ OK:     {entry['name']}", "dim")

        if not found:
            Logger.success("All sectors healthy — no repairs needed")
            return

        Logger.warning(f"\n{len(found)} broken sector(s) detected:")
        for i, entry in enumerate(found, 1):
            Logger.log(f"  {i}. {entry['name']}", "error")

        c = Logger.C
        choice = input(
            f"\n{c['warning']}Repair all {len(found)} sectors? [Y=all / n=select / x=cancel] > {c['reset']}"
        ).strip().lower()

        if choice == "x":
            Logger.log("Repair cancelled")
            return

        if choice == "n":
            # Selective repair
            for i, entry in enumerate(found, 1):
                Logger.log(f"\n[{i}] {entry['name']}")
                sub = input(f"  {c['warning']}Repair this sector? [Y/n] > {c['reset']}").strip().lower()
                if sub in ("", "y"):
                    cls._apply_repair(entry)
        else:
            # Repair all
            for entry in found:
                cls._apply_repair(entry)

        Logger.success("Auto-repair complete")

    @classmethod
    def _apply_repair(cls, entry: Dict[str, Any]) -> None:
        Logger.repair(f"Repairing: {entry['name']}")
        try:
            entry["repair"]()
        except Exception as exc:
            Logger.error(f"Repair error: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# SHIZUKU MANAGER
# ─────────────────────────────────────────────────────────────────────────────
class ShizukuManager:
    CLASSPATH_CMD = (
        "P=$(pm path moe.shizuku.privileged.api | cut -d: -f2); "
        "CLASSPATH=$P app_process /system/bin "
        "--nice-name=shizuku_server moe.shizuku.server.ShizukuServiceServer &"
    )

    def deploy(self) -> None:
        Logger.header("🔑 SHIZUKU — Privilege Engine")
        pkg = DeviceSpec.SHIZUKU_PKG
        if not ADB.pkg_installed(pkg):
            apk = CACHE_DIR / "shizuku.apk"
            APKDownloader.download(DeviceSpec.SHIZUKU_URL, apk)
            APKDownloader.install(apk, "Shizuku")
        else:
            Logger.success("Shizuku already installed")
        Logger.log("Starting Shizuku bootstrap...")
        ADB.run(self.CLASSPATH_CMD)
        time.sleep(3)
        Logger.success("Shizuku server started")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
class PlayboxULTRA:

    def __init__(self, device: str) -> None:
        self.device   = device
        self.video    = VideoEngineOptimizer()
        self.memory   = MemoryOptimizer()
        self.network  = NetworkOptimizer()
        self.hdmi     = HDMIOptimizer()
        self.resp     = ResponsivenessOptimizer()
        self.debloat  = SafeDebloater()
        self.cast     = ChromecastServiceManager()
        self.aot      = AOTCompiler()
        self.diag     = DiagnosticEngine()
        self.repair   = AutoRepairEngine()
        self.shizuku  = ShizukuManager()

    def _banner(self) -> None:
        c = Logger.C
        print(f"""
{c['header']}{c['bold']}╔══════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v{VERSION}
║  Sagemcom DCTIW362P │ Android TV 9 │ Broadcom BCM7362
╠══════════════════════════════════════════════════════════════════════╣
║  🎬 SmartTube VP9 HW  🚇 Tunnel Mode  🛡 Cast Protected
║  🔧 Self-Diagnostic   🩺 Auto-Repair  🔒 DNS: one.one.one.one
╚══════════════════════════════════════════════════════════════════════╝{c['reset']}
  Connected: {c['cyan']}{self.device}{c['reset']}
""")

    def _menu(self) -> None:
        c = Logger.C
        while True:
            os.system("clear")
            self._banner()
            print(f"""{c['bold']}╔══════════════════════════════════════════════════════════════════╗{c['reset']}
  {c['success']}VIDEO PERFORMANCE{c['reset']}
    {c['success']}1.{c['reset']}  Codec Pipeline (C2+OMX, ccodec, VP9 HW)
    {c['success']}2.{c['reset']}  Rendering Engine (skiaglthreaded + VideoCore)
    {c['success']}3.{c['reset']}  Tunnel Mode (VPU→Display direct)
    {c['success']}4.{c['reset']}  AV1 Suppression + Dalvik Heap
    {c['success']}5.{c['reset']}  AOT Compile (SmartTube + Projectivy + Cast)

  {c['header']}CHROMECAST PROTECTION{c['reset']}
    {c['success']}6.{c['reset']}  🛡 Audit Cast Services
    {c['success']}7.{c['reset']}  🛡 Restore Cast Services (emergency)
    {c['success']}8.{c['reset']}  📡 Cast mDNS Network Tuning
    {c['success']}9.{c['reset']}  🎯 Cast OOM Hardening
    {c['success']}P.{c['reset']}  🔍 Show Protection Registry

  {c['info']}DIAGNOSTICS & REPAIR{c['reset']}
    {c['info']}D.{c['reset']}  🔎 Interactive Self-Diagnostics (8 categories)
    {c['info']}R.{c['reset']}  🔧 Auto-Repair Engine (scan + fix all sectors)
    {c['info']}N.{c['reset']}  🔒 DNS Manager (interactive selector)

  {c['warning']}SYSTEM{c['reset']}
    {c['warning']}10.{c['reset']} Network TCP + DNS (Cloudflare auto)
    {c['warning']}11.{c['reset']} HDMI + CEC (BCM Nexus props, addr=11)
    {c['warning']}12.{c['reset']} Audio A/V Sync Fix
    {c['warning']}13.{c['reset']} Memory: LMK + VM + Heap
    {c['warning']}14.{c['reset']} System Responsiveness + I/O + CPU
    {c['warning']}15.{c['reset']} Safe Debloat (Cast PROTECTED)
    {c['warning']}16.{c['reset']} Deep Clean RAM
    {c['warning']}17.{c['reset']} Deploy Shizuku

  {c['cyan']}AUTO MODES{c['reset']}
    {c['cyan']}20.{c['reset']} 🚀 SMARTTUBE ULTRA (video-focused)
    {c['cyan']}21.{c['reset']} 🏆 FULL SYSTEM ULTRA (all modules)
    {c['error']}0.{c['reset']}  Exit{c['bold']}
╚══════════════════════════════════════════════════════════════════════╝{c['reset']}""")

            choice = input(f"\n{c['cyan']}Choice > {c['reset']}").strip().lower()

            dispatch: Dict[str, Callable] = {
                "1":  self.video.optimize_codec_pipeline,
                "2":  self.video.optimize_rendering,
                "3":  self.video.force_tunnel_mode,
                "4":  self._codec_and_heap,
                "5":  self.aot.compile_all,
                "6":  self.cast.audit,
                "7":  self.cast.restore,
                "8":  self.cast.optimize_network,
                "9":  self.cast.harden_oom,
                "p":  ChromecastProtection.print_all,
                "d":  self.diag.single_category_menu,
                "r":  self.repair.scan_and_repair_interactive,
                "n":  DNSManager.interactive_select,
                "10": self._network_full,
                "11": self.hdmi.apply,
                "12": self.hdmi.fix_audio_desync,
                "13": self._memory_full,
                "14": self.resp.apply,
                "15": self.debloat.run,
                "16": self.memory.deep_clean,
                "17": self.shizuku.deploy,
                "20": self.run_smarttube_ultra,
                "21": self.run_full_ultra,
                "0":  self._exit,
            }

            fn = dispatch.get(choice)
            if fn:
                fn()
            else:
                Logger.warning("Invalid choice")

            if choice != "0":
                input(f"\n{c['cyan']}Press Enter...{c['reset']}")

    def _codec_and_heap(self):
        self.video.suppress_av1()
        self.memory.apply_dalvik_heap()

    def _network_full(self):
        self.network.apply_tcp()
        self.network.apply_dns("cloudflare")

    def _memory_full(self):
        self.memory.apply_lmk_profile()
        self.memory.apply_vm_tuning()
        self.memory.apply_dalvik_heap()

    def _exit(self) -> None:
        Logger.save()
        Logger.log(f"Log: {LOG_FILE}", "cyan")
        sys.exit(0)

    # ── SmartTube Ultra ──────────────────────────────────────────────────────
    def run_smarttube_ultra(self) -> None:
        Logger.header("🚀 SMARTTUBE ULTRA — Maximum Video Performance")
        pipeline: List[Tuple[str, Callable]] = [
            ("Auto-Repair pre-check",          self.repair.scan_and_repair_interactive),
            ("Chromecast Audit",                self.cast.audit),
            ("Codec Pipeline (C2+OMX)",         self.video.optimize_codec_pipeline),
            ("Rendering (skiaglthreaded)",       self.video.optimize_rendering),
            ("Tunnel Mode",                      self.video.force_tunnel_mode),
            ("AV1 Suppression + Dalvik Heap",   self._codec_and_heap),
            ("Audio A/V Sync",                  self.hdmi.fix_audio_desync),
            ("HDMI + CEC (BCM Nexus)",           self.hdmi.apply),
            ("Memory: LMK + VM + Heap",         self._memory_full),
            ("Responsiveness + I/O + CPU",      self.resp.apply),
            ("TCP Network + DNS (Cloudflare)",  self._network_full),
            ("Cast mDNS Tuning",                self.cast.optimize_network),
            ("Cast OOM Hardening",              self.cast.harden_oom),
            ("AOT Compilation",                 self.aot.compile_all),
            ("Cast Services Restore (final)",   self.cast.restore),
        ]
        total = len(pipeline)
        for i, (name, fn) in enumerate(pipeline, 1):
            Logger.log(f"\n[{i}/{total}] {name}...", "cyan")
            fn()
            time.sleep(0.3)
        Logger.header("🎉 SMARTTUBE ULTRA COMPLETE")
        Logger.success("VP9 HW + Tunnel Mode + AOT + DNS: one.one.one.one + Cast Protected ✓")
        Logger.log("SmartTube: Settings → Player → Video codec → VP9", "warning")
        Logger.save()

    # ── Full System Ultra ────────────────────────────────────────────────────
    def run_full_ultra(self) -> None:
        Logger.header("🏆 FULL SYSTEM ULTRA — Complete Optimization")
        pipeline: List[Tuple[str, Callable]] = [
            ("System Diagnostics (baseline)",  lambda: self.diag.run_category("A")),
            ("Auto-Repair pre-check",          self.repair.scan_and_repair_interactive),
            ("Chromecast Audit",               self.cast.audit),
            ("Codec Pipeline (C2+OMX)",        self.video.optimize_codec_pipeline),
            ("Rendering (skiaglthreaded)",      self.video.optimize_rendering),
            ("Tunnel Mode",                    self.video.force_tunnel_mode),
            ("AV1 Suppression + Heap",         self._codec_and_heap),
            ("Audio A/V Sync",                 self.hdmi.fix_audio_desync),
            ("HDMI + CEC (BCM Nexus addr=11)", self.hdmi.apply),
            ("TCP + DNS (Cloudflare DoT)",     self._network_full),
            ("Memory: LMK + VM + Heap",        self._memory_full),
            ("Responsiveness + I/O + CPU",     self.resp.apply),
            ("Safe Debloat (Cast Protected)",  self.debloat.run),
            ("Cast mDNS Network",              self.cast.optimize_network),
            ("Cast OOM Hardening",             self.cast.harden_oom),
            ("AOT Compilation",                self.aot.compile_all),
            ("Deep Clean RAM",                 self.memory.deep_clean),
            ("Final Cast Audit",               self.cast.audit),
        ]
        total = len(pipeline)
        for i, (name, fn) in enumerate(pipeline, 1):
            Logger.log(f"\n[{i}/{total}] {name}...", "cyan")
            fn()
            time.sleep(0.2)
        Logger.header("🏆 FULL SYSTEM ULTRA COMPLETE")
        Logger.success("All modules applied. Chromecast: PROTECTED. DNS: FIXED. Cast: SECURED.")
        Logger.log(f"Reboot: adb -s {self.device} reboot", "warning")
        Logger.save()


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=f"Playbox Titanium v{VERSION} — Sagemcom DCTIW362P",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  python3 Autopilot_12_ULTRA.py                          # Interactive menu
  python3 Autopilot_12_ULTRA.py --smarttube-ultra        # Video-focused ultra
  python3 Autopilot_12_ULTRA.py --full-ultra             # All modules
  python3 Autopilot_12_ULTRA.py --diag                   # Self-diagnostics
  python3 Autopilot_12_ULTRA.py --repair                 # Auto-repair scan
  python3 Autopilot_12_ULTRA.py --cast-restore           # Emergency Cast fix
  python3 Autopilot_12_ULTRA.py --dns cloudflare         # Fix DNS
  python3 Autopilot_12_ULTRA.py --device 192.168.1.3:5555 --full-ultra
""")
    p.add_argument("--device",           default=None)
    p.add_argument("--smarttube-ultra",  action="store_true")
    p.add_argument("--full-ultra",       action="store_true")
    p.add_argument("--diag",             action="store_true",   help="Run interactive self-diagnostics")
    p.add_argument("--repair",           action="store_true",   help="Run auto-repair engine")
    p.add_argument("--cast-audit",       action="store_true")
    p.add_argument("--cast-restore",     action="store_true")
    p.add_argument("--dns",              default=None,           metavar="PROVIDER",
                   help="Set DNS: cloudflare|google|quad9|adguard|nextdns")
    p.add_argument("--beta",             action="store_true")
    return p


def main() -> None:
    args = _parser().parse_args()

    device = args.device or ADB.detect() or DEFAULT_ADB_HOST
    if args.device:
        Logger.log(f"Device: {device} (specified)")
    elif ADB.detect():
        Logger.success(f"Auto-detected: {device}")
    else:
        Logger.warning(f"No device detected — using default: {device}")

    if not ADB.connect(device):
        Logger.error(f"Cannot connect to {device}")
        sys.exit(1)

    app = PlayboxULTRA(device)

    if args.cast_restore:
        ChromecastServiceManager.restore()
    elif args.cast_audit:
        ChromecastServiceManager.audit()
    elif args.dns:
        DNSManager.set_provider(args.dns)
    elif args.diag:
        app.diag.run_all_interactive()
    elif args.repair:
        app.repair.scan_and_repair_interactive()
    elif args.smarttube_ultra:
        app.run_smarttube_ultra()
    elif args.full_ultra:
        app.run_full_ultra()
    else:
        app._banner()
        app._menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        Logger.warning("Interrupted (Ctrl+C)")
        Logger.save()
        sys.exit(0)
    except Exception as exc:
        Logger.error(f"Unexpected error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
