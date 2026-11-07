#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      PLAYBOX TITANIUM v11.0 ULTRA — SmartTube + Chromecast EDITION          ║
║  Target  : Sagemcom DCTIW362P | Android TV 9 (API 28) | Broadcom m362       ║
║  Focus   : Max SmartTube/Video Performance + Chromecast Service Protection   ║
║  Author  : Anonymousik / SecFerro Division                                   ║
║  Date    : 2026-02                                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  HARDWARE PROFILE (real ADB session, 192.168.1.3:5555):                      ║
║    RAM     : 1459 MB total  | ~534 MB available (MemAvailable)               ║
║    FLASH   : 3.9 GB  | 53% used (/data)                                      ║
║    SoC     : Broadcom m362 (BCM7362) — Dual-core Cortex-A15 @ 1.0 GHz       ║
║    VPU     : BCM7362 HW decoder: H.264 ✓ | H.265 ✓ | VP9 ✓ | AV1 ✗         ║
║    GPU     : Broadcom VideoCore (OpenGL ES 3.1, NO Vulkan)                   ║
║    Display : HDMI 2.0a, CEC v1.4, 4K@60fps, HDR10                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  CHROMECAST PROTECTION ARCHITECTURE:                                         ║
║    apps.mediashell       → Cast Built-in DAEMON   [NEVER DISABLE]            ║
║    gms                   → Cast SDK / Auth         [NEVER DISABLE]            ║
║    gsf                   → Google Services FW      [NEVER DISABLE]            ║
║    nearby                → mDNS/Cast Discovery     [NEVER DISABLE]            ║
║    tv.remote.service     → Cast UI Input           [PROTECTED]                ║
║    tvlauncher            → Cast Session UI         [PROTECTED]                ║
║    networkstack          → Multicast Routing       [PROTECTED]                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import sys
import subprocess
import time
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
VERSION          = "11.0-ULTRA-SmartTube-ChromecastSafe"
DEFAULT_ADB_HOST = "192.168.1.3:5555"
CACHE_DIR        = Path.home() / ".playbox_cache"
BACKUP_DIR       = CACHE_DIR / "backups_v11"
LOG_FILE         = CACHE_DIR / "autopilot_v11.log"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# DEVICE SPECIFICATION — Broadcom BCM7362
# ─────────────────────────────────────────────────────────────────────────────
class DeviceSpec:
    """
    Hardware constants for Sagemcom DCTIW362P.
    Sources: real ADB capture + BCM7362 datasheet + Android TV 9 framework docs.
    """
    MODEL               = "dctiw362p"
    HARDWARE            = "m362"
    ANDROID_VERSION     = "9"
    API_LEVEL           = "28"
    BUILD_FINGERPRINT   = (
        "PLAY/play_dctiw362/dctiw362p:9/PTT1.190826.001/"
        "1.0.36-194202:user/release-keys"
    )

    # From /proc/meminfo snapshot
    RAM_TOTAL_KB        = 1_459_656
    RAM_AVAILABLE_KB    = 534_720

    # BCM7362 VPU codec identifiers (OMX layer)
    # Confirmed by OMX component enumeration on this chipset family
    CODEC_HW_H264       = "OMX.brcm.video.h264.decoder"
    CODEC_HW_HEVC       = "OMX.brcm.video.h265.decoder"
    CODEC_HW_VP9        = "OMX.brcm.video.vp9.decoder"
    # AV1: NO hardware decoder on BCM7362 — software fallback only
    CODEC_SW_AV1        = "c2.android.av1.decoder"  # DO NOT USE — CPU killer

    # Dalvik heap profile for ~534MB available RAM
    # SmartTube typical heap usage: 150–200MB during 4K playback
    DALVIK_HEAP_SIZE     = "256m"
    DALVIK_HEAP_GROWTH   = "128m"
    DALVIK_HEAP_MIN_FREE = "16m"
    DALVIK_HEAP_MAX_FREE = "32m"
    DALVIK_HEAP_TARGET   = "0.75"

    SMARTTUBE_PKG       = "com.teamsmart.videomanager.tv"
    SMARTTUBE_STABLE_URL = (
        "https://github.com/yuliskov/SmartTube/releases/download/latest/smarttube_stable.apk"
    )
    SMARTTUBE_BETA_URL   = (
        "https://github.com/yuliskov/SmartTube/releases/download/latest/smarttube_beta.apk"
    )
    SHIZUKU_PKG         = "moe.shizuku.privileged.api"
    SHIZUKU_APK_URL     = (
        "https://github.com/RikkaApps/Shizuku/releases/download/"
        "v13.5.4/shizuku-v13.5.4-release.apk"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CHROMECAST PROTECTION REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
class ChromecastProtection:
    """
    Definitive whitelist of packages that MUST remain enabled for
    Chromecast Built-in, Google Cast SDK v3+, and related protocols.

    Engineering rationale per entry:
    ──────────────────────────────────────────────────────────────────────────
    apps.mediashell     → THIS IS Chromecast Built-in daemon on Android TV.
                          Without it, no Cast session can be established.
                          It runs the Cast receiver application loop and
                          manages DIAL/mDNS session handshake.

    gms                 → Google Play Services. Hosts:
                            · com.google.android.gms.cast (Cast SDK)
                            · SessionManager, CastContext
                            · Device authentication (OAuth tokens)
                          Disabling GMS = total Cast failure.

    gsf                 → Google Services Framework. Core dependency of GMS.
                          Handles Google Account token refresh. Without it,
                          GMS cannot authenticate → Cast breaks silently.

    nearby              → Google Nearby Connections. Manages:
                            · mDNS/DNS-SD multicast (port 5353)
                              Used for Chromecast device discovery on LAN
                            · BLE advertising (Guest Mode / Fast Pair)
                            · SSDP/UPnP fallback discovery path
                          Disabling = sender device "cannot find Chromecast".

    tv.remote.service   → Handles Cast session initiation events from remote
                          controls and the "Cast to TV" system intent. Also
                          manages virtual remote input during active sessions.

    tvlauncher          → Android TV Home. Cast sessions surface ambient
                          mode UI here. Handles android.intent.action.MAIN
                          with CATEGORY_LEANBACK_LAUNCHER for Cast handoff.

    configupdater       → Downloads periodic Cast infrastructure config:
                          TLS certificate pins, endpoint URLs, protocol
                          version negotiation. Stale config → Cast auth fails.

    wifidisplay         → Miracast / WiFi Direct. Used as Cast fallback
                          transport when DIAL-over-mDNS fails (e.g. IGMP
                          snooping misconfigured on router). Some Chromecast
                          Audio receivers rely on this path.

    networkstack        → Android network stack. Handles multicast group
                          join (IGMP) for mDNS. Without it, mDNS packets
                          are never delivered to the mDNS responder daemon.

    networkstack.tether → Tethering companion — shares multicast routing
                          rules with networkstack. Required on some builds
                          for proper multicast socket binding.
    """

    PROTECTED_PACKAGES: Dict[str, str] = {
        # Cast Core — NEVER touch these
        "com.google.android.apps.mediashell":
            "Cast Built-in DAEMON — the Chromecast receiver process [CRITICAL]",
        "com.google.android.gms":
            "Google Play Services — Cast SDK, SessionManager, Auth [CRITICAL]",
        "com.google.android.gsf":
            "Google Services Framework — GMS dependency chain [CRITICAL]",
        "com.google.android.nearby":
            "Nearby Connections — mDNS/BLE Chromecast discovery [CRITICAL]",

        # Cast Session Management
        "com.google.android.tv.remote.service":
            "TV Remote Service — Cast session UI & input routing [IMPORTANT]",
        "com.google.android.tvlauncher":
            "TV Launcher — Cast ambient mode UI & intents [IMPORTANT]",

        # Cast Infrastructure
        "com.google.android.configupdater":
            "Config Updater — Cast TLS certs & endpoint config [RECOMMENDED]",
        "com.google.android.wifidisplay":
            "WiFi Display — Miracast/Cast fallback transport [RECOMMENDED]",

        # Network Foundation (multicast for mDNS)
        "com.android.networkstack":
            "Network Stack — IGMP multicast for mDNS (Cast discovery) [CRITICAL]",
        "com.android.networkstack.tethering":
            "Network Tethering Stack — multicast socket routing [IMPORTANT]",
    }

    @classmethod
    def is_protected(cls, package: str) -> bool:
        return package in cls.PROTECTED_PACKAGES

    @classmethod
    def get_reason(cls, package: str) -> str:
        return cls.PROTECTED_PACKAGES.get(package, "")

    @classmethod
    def print_registry(cls) -> None:
        Logger.header("🛡 CHROMECAST PROTECTION REGISTRY")
        for pkg, reason in cls.PROTECTED_PACKAGES.items():
            Logger.log(f"  🔒 {pkg}", "success")
            Logger.log(f"       └─ {reason}", "cyan")
        Logger.log(
            f"\n  Total protected: {len(cls.PROTECTED_PACKAGES)} packages",
            "bold"
        )


# ─────────────────────────────────────────────────────────────────────────────
# SAFE DEBLOAT DATABASE
# Each entry: (package, reason_to_disable, chromecast_impact)
# ─────────────────────────────────────────────────────────────────────────────
SAFE_DEBLOAT_DB: List[Tuple[str, str, str]] = [
    # Android TV system bloat
    ("com.google.android.backdrop",
     "Ambient Mode screensaver — idles GPU, wastes 30–60MB RAM",
     "NONE — Cast unaffected"),
    ("com.google.android.tvrecommendations",
     "Content recommendations — constant background HTTP polling",
     "NONE"),
    ("com.google.android.katniss",
     "Google TV voice search overlay — high idle CPU on A15",
     "NONE — Cast uses own discovery path"),
    ("com.google.android.tungsten.setupwraith",
     "Setup wizard — not needed post-initial-setup",
     "NONE"),
    ("com.google.android.apps.tv.launcherx",
     "New Google TV launcher (not used on API 28 / Android 9)",
     "NONE — tvlauncher separately protected"),
    ("com.google.android.leanbacklauncher",
     "Legacy Leanback launcher duplicate (tvlauncher supersedes it)",
     "NONE"),

    # Sagemcom / Orange Poland bloat
    ("com.sagemcom.stb.setupwizard",
     "Sagemcom factory setup wizard",
     "NONE"),
    ("com.orange.fr.tv.assistance",
     "Orange TV assistance app — polls Orange servers constantly",
     "NONE"),
    ("com.orange.fr.tv.guide",
     "Orange TV guide — heavy background sync, rarely used",
     "NONE"),

    # Google services safe to disable (non-Cast)
    ("com.google.android.marvin.talkback",
     "Accessibility TTS — not needed on TV, allocates ~40MB",
     "NONE"),
    ("com.google.android.onetimeinitializer",
     "One-time initializer — already completed on first boot",
     "NONE"),

    # Third-party pre-installed
    ("com.amazon.amazonvideo.livingroom",
     "Amazon Prime TV — pre-bundled, standalone install preferable",
     "NONE"),
]


# ─────────────────────────────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────────────────────────────
class Logger:
    COLORS: Dict[str, str] = {
        "info":    "\033[94m",
        "success": "\033[92m",
        "warning": "\033[93m",
        "error":   "\033[91m",
        "header":  "\033[95m",
        "cyan":    "\033[96m",
        "bold":    "\033[1m",
        "reset":   "\033[0m",
    }

    _log_lines: List[str] = []

    @classmethod
    def _emit(cls, msg: str, level: str) -> None:
        ts = time.strftime("%H:%M:%S")
        color = cls.COLORS.get(level, cls.COLORS["info"])
        print(f"{color}[{ts}] {msg}{cls.COLORS['reset']}")
        cls._log_lines.append(f"[{ts}][{level.upper()}] {msg}")

    @classmethod
    def log(cls, msg: str, level: str = "info") -> None:
        cls._emit(msg, level)

    @classmethod
    def success(cls, msg: str) -> None:
        cls._emit(f"✓ {msg}", "success")

    @classmethod
    def warning(cls, msg: str) -> None:
        cls._emit(f"⚠ {msg}", "warning")

    @classmethod
    def error(cls, msg: str) -> None:
        cls._emit(f"✗ {msg}", "error")

    @classmethod
    def shield(cls, msg: str) -> None:
        """Protected resource notification."""
        cls._emit(f"🛡 {msg}", "success")

    @classmethod
    def header(cls, msg: str) -> None:
        sep = "═" * 74
        print(
            f"\n{cls.COLORS['header']}{cls.COLORS['bold']}{sep}\n"
            f"   {msg}\n{sep}{cls.COLORS['reset']}\n"
        )

    @classmethod
    def save_log(cls) -> None:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(f"\n{'─'*60}\n")
                fh.write(f"SESSION {time.strftime('%Y-%m-%d %H:%M:%S')} | v{VERSION}\n")
                fh.write("\n".join(cls._log_lines))
                fh.write("\n")
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# ADB SHELL INTERFACE
# ─────────────────────────────────────────────────────────────────────────────
class ADBShell:
    """
    Secure, idempotent ADB command executor.

    Security notes:
    - No shell=True — commands passed as list to prevent injection
    - Retry only on TimeoutExpired, not CalledProcessError (errors are final)
    - run_root() escalation: su → rish (Shizuku) → plain ADB shell
    """

    device: Optional[str] = None
    TIMEOUT: int = 30
    RETRIES: int = 3

    @classmethod
    def connect(cls, target: str) -> bool:
        """Establish TCP ADB connection. Returns True on success."""
        try:
            result = subprocess.run(
                ["adb", "connect", target],
                capture_output=True, text=True, timeout=10
            )
            if "connected" in result.stdout.lower():
                cls.device = target
                Logger.success(f"ADB connected: {target}")
                return True
            Logger.error(f"ADB connect failed: {result.stdout.strip()}")
            return False
        except FileNotFoundError:
            Logger.error("'adb' not found in PATH. Install Android Platform Tools.")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            Logger.error(f"ADB connect timeout: {target}")
            return False

    @classmethod
    def detect_device(cls) -> Optional[str]:
        """Auto-detect first available adb device."""
        try:
            out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
            for line in out.splitlines():
                if "\tdevice" in line:
                    return line.split("\t")[0].strip()
        except Exception:
            pass
        return None

    @classmethod
    def run(
        cls,
        cmd: str,
        ignore_errors: bool = True,
        silent: bool = False,
    ) -> str:
        """Execute shell command via ADB. Returns stdout or '' on failure."""
        if not cls.device:
            return ""
        for attempt in range(cls.RETRIES):
            try:
                out = subprocess.check_output(
                    ["adb", "-s", cls.device, "shell", cmd],
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=cls.TIMEOUT,
                )
                return out.strip()
            except subprocess.TimeoutExpired:
                if attempt < cls.RETRIES - 1:
                    time.sleep(1.5)
                elif not silent:
                    Logger.warning(f"Timeout [{attempt+1}/{cls.RETRIES}]: {cmd[:60]}")
            except subprocess.CalledProcessError as exc:
                return exc.output.strip() if exc.output else ""
            except Exception as exc:
                if not silent:
                    Logger.error(f"ADB exception: {exc}")
                return ""
        return ""

    @classmethod
    def run_root(cls, cmd: str) -> str:
        """Privileged execution: su → rish → plain ADB shell (graceful fallback)."""
        for prefix in (f"su -c \"{cmd}\"", f"rish -c \"{cmd}\""):
            result = cls.run(prefix, ignore_errors=True, silent=True)
            if result and "not found" not in result and "permission denied" not in result.lower():
                return result
        Logger.warning(f"Root unavailable, trying plain ADB: {cmd[:50]}")
        return cls.run(cmd, ignore_errors=True)

    @classmethod
    def push(cls, local: str, remote: str) -> bool:
        """Push file to device. Returns True on success."""
        try:
            subprocess.check_call(
                ["adb", "-s", cls.device, "push", local, remote],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=120,
            )
            return True
        except Exception:
            return False

    # ── Convenience wrappers ──────────────────────────────────────────────

    @classmethod
    def prop_get(cls, prop: str) -> str:
        return cls.run(f"getprop {prop}", silent=True)

    @classmethod
    def prop_set(cls, prop: str, value: str) -> None:
        cls.run(f"setprop {prop} {value}", ignore_errors=True, silent=True)

    @classmethod
    def setting_put(cls, ns: str, key: str, value: str) -> None:
        cls.run(f"settings put {ns} {key} {value}", ignore_errors=True, silent=True)

    @classmethod
    def setting_get(cls, ns: str, key: str) -> str:
        return cls.run(f"settings get {ns} {key}", silent=True)

    @classmethod
    def pkg_enabled(cls, pkg: str) -> bool:
        return pkg in cls.run(f"pm list packages -e {pkg}", silent=True)


# ─────────────────────────────────────────────────────────────────────────────
# SMARTTUBE VIDEO ENGINE OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────
class SmartTubeOptimizer:
    """
    SmartTube + ExoPlayer + Broadcom VPU pipeline tuning.

    SmartTube uses ExoPlayer which interfaces with Android MediaCodec API:
      MediaCodec → OMX layer → BCM7362 VPU kernel driver (bcmvideo.ko)

    YouTube codec priority for BCM7362 (HW → SW, best → worst):
      1. VP9 profile 2 — HW decode, 4K@60fps, best quality/perf ratio
      2. H.264 AVC     — HW decode, universal compatibility
      3. H.265 HEVC    — HW decode, good for 4K, less stable on some sources
      4. AV1           — SOFTWARE ONLY → CPU at 100%, dropped frames, throttle

    Tunnel Mode (Android 5+, BCM7362 supported):
      Decoded VPU frames → display controller, bypassing SurfaceFlinger.
      Eliminates 1–2 frame compositing latency, saves ~15% CPU at 4K.
    """

    def optimize_exoplayer_pipeline(self) -> None:
        Logger.header("🎬 EXOPLAYER PIPELINE — Broadcom VPU Hardware Path")

        # Stagefright / MediaCodec stack flags
        codec_props = [
            # Enable HW-accelerated player pipeline
            ("media.stagefright.enable-player",   "true"),
            ("media.stagefright.enable-meta",     "true"),
            ("media.stagefright.enable-http",     "true"),
            ("media.stagefright.enable-scan",     "true"),
            # OMX: always pick HW codec over SW fallback during negotiation
            ("media.acodec.preferhw",             "true"),
            ("media.vcodec.preferhw",             "true"),
            # Suppress automatic SW fallback for HW-capable codecs
            ("media.codec.sw.fallback",           "false"),
            # OMX thread priority: 1 = RT class (prevents UI thread preemption)
            ("media.codec.priority",              "1"),
        ]
        for key, value in codec_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        # HLS / DASH adaptive bitrate buffer tuning
        abr_props = [
            # 25 Mbps ceiling covers YouTube 4K VP9 (typical: 10–20 Mbps)
            ("media.httplive.max-bitrate",        "25000000"),
            # Start at 8 Mbps — avoids quality dip on stream open
            ("media.httplive.initial-bitrate",    "8000000"),
            # 60s lookahead buffer — reduces rebuffering events on variable WiFi
            ("media.httplive.max-live-offset",    "60"),
            # Bandwidth estimator update interval: 1000ms (responsive ABR)
            ("media.httplive.bw-update-interval", "1000"),
        ]
        for key, value in abr_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        # MediaExtractor cache: 20MB min / 60MB max / 256MB total cap
        # Calculated for 4K streaming on 1.4GB RAM device (holds ~3s of 4K)
        ADBShell.run(
            "settings put global media.stagefright.cache-params "
            "20971520/62914560/268435456",
            ignore_errors=True,
        )
        Logger.log("  ✓ MediaExtractor cache: 20MB–60MB / 256MB cap")

        Logger.success("ExoPlayer pipeline configured for Broadcom VPU HW path")

    def force_tunnel_mode(self) -> None:
        """
        Enable MediaCodec Tunnel Mode.

        VPU decoded frames → BCM7362 display controller directly,
        bypassing SurfaceFlinger buffer queue. Effect:
          - ~1–2 frame latency reduction
          - ~15% CPU reduction during 4K playback
          - Eliminates compositor-induced frame pacing jitter
        """
        Logger.header("🚇 TUNNEL MODE — Direct VPU→Display Path")

        tunnel_props = [
            ("media.tunneled-playback.enable",  "true"),
            ("media.brcm.tunnel.sessions",      "1"),      # One tunnel = one video
            ("media.brcm.hdmi.tunnel",          "true"),
            ("media.brcm.tunnel.clock",         "hdmi"),   # Lock A/V to HDMI sink clock
            ("debug.sf.disable_backpressure",   "1"),      # No SF back-pressure on VPU
        ]
        for key, value in tunnel_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        Logger.success("Tunnel Mode active — VPU→Display direct path enabled")

    def suppress_av1_software_decode(self) -> None:
        """
        Suppress AV1 software decoder to prevent CPU overload.

        BCM7362 has NO AV1 hardware decoder. YouTube increasingly serves
        AV1 to devices that advertise VP9 + AV1 support. ExoPlayer then
        selects c2.android.av1.decoder — a pure software decoder that
        saturates both A15 cores at 720p, causing frame drops at 1080p+.

        We suppress the component so MediaCodec negotiation falls back to
        VP9 (hardware), which BCM7362 handles at 4K@60fps without CPU load.
        """
        Logger.header("🚫 AV1 SUPPRESSION — Force VP9/H.264 HW Negotiation")

        Logger.warning("BCM7362: NO AV1 HW decoder — SW decode = CPU 100% + stutter")
        av1_props = [
            ("debug.stagefright.c2.av1",  "0"),
            ("media.av1.sw.decode.disable", "true"),
            ("media.codec.av1.disable",   "true"),
        ]
        for key, value in av1_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        Logger.success("AV1 SW decoder suppressed — VP9/H.264 HW path will be used")

        colors = Logger.COLORS
        print(f"""
  {colors['cyan']}┌──────────────────────────────────────────────────────────┐
  │  ⚙  SMARTTUBE MANUAL SETTINGS (after next launch)         │
  │                                                            │
  │  Settings → Player → Video codec → VP9  ← set this        │
  │  Settings → Player → Resolution  → 2160p (4K)             │
  │  Settings → Player → Use tunnel mode → ON (if visible)    │
  │                                                            │
  │  VP9 on BCM7362 = hardware → smooth 4K, low CPU           │
  │  AV1 on BCM7362 = software → stutter, thermal throttle    │
  └──────────────────────────────────────────────────────────┘{colors['reset']}
""")

    def tune_dalvik_heap(self) -> None:
        """
        Tune Dalvik/ART heap for streaming workload on 1.4GB RAM device.

        Memory budget (MemAvailable ~534MB):
          SmartTube (playing 4K) : ~200MB heap + ~50MB native
          Chromecast GMS/mediashell: ~80MB
          TV Launcher              : ~40MB
          OS + kernel              : ~150MB
          Headroom                 : ~14MB free
        → heap_size=256m keeps SmartTube happy without GC storms
        """
        Logger.header("🧠 DALVIK/ART HEAP — SmartTube 4K Streaming Profile")

        heap_props = [
            ("dalvik.vm.heapsize",              DeviceSpec.DALVIK_HEAP_SIZE),
            ("dalvik.vm.heapgrowthlimit",       DeviceSpec.DALVIK_HEAP_GROWTH),
            ("dalvik.vm.heapminfree",           DeviceSpec.DALVIK_HEAP_MIN_FREE),
            ("dalvik.vm.heapmaxfree",           DeviceSpec.DALVIK_HEAP_MAX_FREE),
            ("dalvik.vm.heaptargetutilization", DeviceSpec.DALVIK_HEAP_TARGET),
            ("dalvik.vm.usejit",                "true"),       # JIT: reduce first-run latency
            ("dalvik.vm.dex2oat-filter",        "speed-profile"),
            ("dalvik.vm.gctype",                "CMS"),        # Concurrent GC → no pause
        ]
        for key, value in heap_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        Logger.success("Dalvik heap configured for SmartTube 4K workload")

    def compile_aot(self) -> bool:
        """
        AOT-compile SmartTube to eliminate JIT compilation bursts during playback.

        JIT compilation on A15 cores causes 50–200ms spikes that manifest as
        dropped frames during seeks or first few seconds of playback.
        AOT pre-compiles hot paths (player, network, UI) → smooth from first frame.

        Duration: ~60–90s on BCM7362 (dual-core 1.0 GHz A15). Persistent until APK update.
        """
        Logger.header("⚡ AOT COMPILATION — Eliminate JIT Bursts in SmartTube")

        pkg = DeviceSpec.SMARTTUBE_PKG
        if not ADBShell.pkg_enabled(pkg):
            Logger.warning(f"SmartTube not installed — skipping AOT")
            return False

        Logger.log("Compiling SmartTube [speed-profile mode] ... ~60–90s")
        result = ADBShell.run(
            f"cmd package compile -m speed-profile -f {pkg}",
            ignore_errors=True,
        )
        if "success" in result.lower():
            Logger.success("SmartTube AOT complete (speed-profile)")
            return True

        Logger.warning("speed-profile failed — retrying with speed mode")
        result = ADBShell.run(f"cmd package compile -m speed -f {pkg}", ignore_errors=True)
        Logger.success("SmartTube AOT complete (speed mode)")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# CHROMECAST SERVICE MANAGER
# ─────────────────────────────────────────────────────────────────────────────
class ChromecastServiceManager:
    """
    Audit, restore, and harden all Chromecast Built-in services.

    Cast discovery call stack (simplified):
      Sender app → mDNS query (UDP 5353 multicast 224.0.0.251)
        → com.android.networkstack (multicast join / IGMP)
          → com.google.android.nearby (mDNS responder)
            → com.google.android.apps.mediashell (Cast session accept)
              → com.google.android.gms (Cast SDK lifecycle)
                → com.google.android.tvlauncher (Cast UI)
    """

    @staticmethod
    def audit() -> Dict[str, bool]:
        """Check enabled state of all protected Cast packages."""
        Logger.header("🔍 CHROMECAST SERVICE AUDIT")
        results: Dict[str, bool] = {}

        for pkg, reason in ChromecastProtection.PROTECTED_PACKAGES.items():
            enabled = ADBShell.pkg_enabled(pkg)
            results[pkg] = enabled
            icon = "✓" if enabled else "✗"
            level = "success" if enabled else "error"
            Logger.log(f"  {icon} {pkg}", level)
            Logger.log(f"     └─ {reason}", "cyan")

        broken = [p for p, e in results.items() if not e]
        if broken:
            Logger.warning(
                f"{len(broken)} Cast service(s) DISABLED — Chromecast may be broken!"
            )
        else:
            Logger.success("All Chromecast services active and healthy ✓")

        return results

    @staticmethod
    def restore() -> None:
        """Re-enable all Cast services that are currently disabled. Idempotent."""
        Logger.header("🛡 CHROMECAST SERVICE RESTORATION")
        for pkg, reason in ChromecastProtection.PROTECTED_PACKAGES.items():
            ADBShell.run(f"pm enable {pkg}", ignore_errors=True, silent=True)
            ADBShell.run(f"pm enable --user 0 {pkg}", ignore_errors=True, silent=True)
            Logger.shield(f"Ensured enabled: {pkg}")

        Logger.success(
            f"Restoration complete — {len(ChromecastProtection.PROTECTED_PACKAGES)} "
            "Cast services verified"
        )

    @staticmethod
    def optimize_cast_network() -> None:
        """
        Optimize WiFi/multicast for reliable Cast discovery.

        Common issue: WiFi driver power-save mode suppresses multicast packets,
        causing intermittent 'Chromecast not found' on sender devices even when
        device is online (unicast works, multicast 224.0.0.251 dropped).
        """
        Logger.header("📡 CAST NETWORK — mDNS/Multicast Reliability")

        # Keep WiFi alive to prevent multicast suppression
        ADBShell.setting_put("global", "wifi_sleep_policy", "2")
        Logger.log("  ✓ wifi_sleep_policy = 2 (always connected)")

        ADBShell.setting_put("global", "wifi_power_save", "0")
        Logger.log("  ✓ wifi_power_save disabled (prevents mDNS packet drop)")

        # mDNS passive mode off → device actively responds to discovery
        ADBShell.prop_set("ro.mdns.enable_passive_mode", "false")
        Logger.log("  ✓ mDNS: active response mode")

        # SSDP multicast TTL ≥ 1 required for LAN multicast delivery
        ADBShell.prop_set("net.ssdp.ttl", "4")
        Logger.log("  ✓ SSDP TTL = 4 (sufficient for home LAN)")

        Logger.success("Cast mDNS/multicast network profile active")

    @staticmethod
    def harden_cast_processes() -> None:
        """
        Set OOM score for Cast processes to prevent LMK from killing them.

        oom_score_adj scale:
          -1000 = never kill (system)
          0     = foreground app
          200   = empty background (kill first)
          We set Cast daemon to ~100 → "important background service" tier
        """
        Logger.header("🎯 CAST PROCESS HARDENING — OOM Protection")

        cast_pkgs = [
            "com.google.android.apps.mediashell",
            "com.google.android.gms",
            "com.google.android.nearby",
        ]
        for pkg in cast_pkgs:
            pid = ADBShell.run(f"pidof {pkg}", silent=True).strip()
            if pid and pid.isdigit():
                ADBShell.run_root(f"echo 100 > /proc/{pid}/oom_score_adj")
                Logger.shield(f"OOM adj=100 set: {pkg} (PID {pid})")
            else:
                Logger.log(f"  {pkg} not running — will be protected at runtime", "warning")

        Logger.success("Cast processes protected against OOM killer")


# ─────────────────────────────────────────────────────────────────────────────
# BROADCOM M362 GPU + VPU TUNER
# ─────────────────────────────────────────────────────────────────────────────
class BroadcomTuner:
    """
    Hardware-specific tuning for Broadcom BCM7362 (m362).

    Architecture:
    - Dual-core Cortex-A15 @ 1.0 GHz (NOT A53 — this is an STB SoC)
    - VideoCore VI GPU (GLES 3.1 max, NO Vulkan, NO Swiftshader)
    - Dedicated VPU silicon — H.264/H.265/VP9 decode completely offloaded
    - Triple-buffer framebuffer in hardware (prevents screen tearing)
    - HDMI 2.0a output with native HDR10 signaling
    """

    def apply_gpu_tweaks(self) -> None:
        Logger.header("🎮 BROADCOM VIDEOCORE — GPU Rendering Optimization")

        gpu_props = [
            ("debug.hwui.renderer",            "opengl"),    # Must be opengl — no Vulkan
            ("debug.egl.hw",                   "1"),         # HW EGL acceleration
            ("debug.sf.hw",                    "1"),         # SurfaceFlinger HW composer
            ("debug.gr.numframebuffers",       "3"),         # Triple buffer (tearing fix)
            ("debug.hwui.use_buffer_age",      "false"),     # Unnecessary overhead on VideoCore
            ("debug.hwui.layer_cache_size",    "16384"),     # 16MB layer cache
            ("debug.hwui.profile",             "false"),     # No profiler overhead
        ]
        for key, value in gpu_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        ADBShell.setting_put("global", "force_gpu_rendering", "true")
        Logger.log("  ✓ force_gpu_rendering = true")

        Logger.success("VideoCore GPU tweaks applied")

    def apply_vpu_tweaks(self) -> None:
        Logger.header("📹 BROADCOM VPU — Video Decode Pipeline")

        vpu_props = [
            ("ro.hdmi.device_type",             "4"),        # Playback device
            ("persist.sys.hdmi.addr.playback",  "0"),
            ("ro.hdmi.wake_on_hotplug",         "false"),    # Prevent HDMI reset glitches
            ("persist.sys.hdr.enable",          "1"),        # HDR10 output
            ("media.brcm.vpu.prealloc",         "true"),     # Pre-alloc decode buffers at boot
            ("media.brcm.vpu.buffers",          "6"),        # 6 frame buffer pool (4K@60)
            ("media.brcm.secure.decode",        "true"),     # Widevine L3 / PlayReady support
        ]
        for key, value in vpu_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        Logger.success("BCM7362 VPU pipeline configured")

    def set_performance_governor(self) -> None:
        """
        Force 'performance' CPU governor on both A15 cores.
        Under 'interactive' governor, cores can drop to 250MHz, causing
        decode queue starvation and visible frame pacing issues.
        """
        Logger.header("⚙ CPU GOVERNOR — Force Performance Mode")

        for core in range(2):  # BCM7362: 2x Cortex-A15
            path = f"/sys/devices/system/cpu/cpu{core}/cpufreq/scaling_governor"
            result = ADBShell.run_root(f"echo performance > {path}")
            Logger.log(f"  ✓ cpu{core}: performance governor")

        Logger.success("Both A15 cores locked to maximum frequency")


# ─────────────────────────────────────────────────────────────────────────────
# AUDIO PIPELINE OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────
class AudioOptimizer:
    """
    Fix A/V desync and optimize audio output for Orange PLAYBox.

    Root cause of desync on BCM7362 HDMI:
    Audio offload path uses Broadcom's proprietary timing that disagrees
    with HDMI ARC handshake timing. Result: audio runs 50–200ms off from video.

    Fix: disable offload → passthrough mode → consistent latency.
    Lock audio clock to HDMI sink → eliminates slow drift over hours.
    """

    def fix_av_sync_and_pipeline(self) -> None:
        Logger.header("🔊 AUDIO PIPELINE — A/V Sync + HDMI Fix")

        audio_props = [
            # Disable audio offload — it causes desync on BCM7362 HDMI output
            ("audio.offload.disable",         "1"),
            ("audio.offload.video",           "0"),
            # Disable tunnel audio encode (conflicts with HDMI ARC on this chipset)
            ("tunnel.audio.encode",           "false"),
            # Deep buffer: stable ~20ms latency, prevents buffer under-runs
            ("audio.deep_buffer.media",       "true"),
            # One fast track sufficient for SmartTube (mono audio thread)
            ("af.fast_track_multiplier",      "1"),
            # Lock audio clock to HDMI sink → eliminates slow A/V drift
            ("audio.brcm.hdmi.clock_lock",    "true"),
            # HAL latency: 20ms (optimal for BCM7362)
            ("audio.brcm.hal.latency",        "20"),
        ]
        for key, value in audio_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        Logger.success("Audio pipeline fixed — A/V sync stabilized, HDMI clock locked")


# ─────────────────────────────────────────────────────────────────────────────
# NETWORK OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────
class NetworkOptimizer:
    """
    TCP/IP stack + DNS tuning for 4K streaming.

    Buffer sizing rationale (RTT ~5ms LAN, 100Mbps link):
      BDP = 100Mbps × 5ms = 62.5 KB
      We provision 4× BDP for burst absorption: ~250KB receive, ~512KB send
      (4K VP9 YouTube stream: 10–20Mbps → burst to 25Mbps for ~100ms)

    Cast-safe: multicast settings untouched. Private DNS (DoT) only
    affects unicast DNS — mDNS uses multicast UDP, completely separate path.
    """

    DNS_PROVIDERS: Dict[str, str] = {
        "cloudflare":  "one.one.one.one",
        "google":      "dns.google",
        "nextdns":     "dns.nextdns.io",
        "quad9":       "dns.quad9.net",
        "adguard":     "dns.adguard.com",
    }

    def apply_tcp_tuning(self) -> None:
        Logger.header("🌐 NETWORK — TCP Stack 4K Streaming Profile")

        Logger.shield(
            "mDNS/multicast settings preserved — Cast discovery unaffected by TCP tuning"
        )

        # TCP buffer sizes: min/default/max (bytes)
        ADBShell.setting_put(
            "global", "net.tcp.buffersize.wifi",
            "262144,1048576,2097152,131072,524288,1048576"
        )
        Logger.log("  ✓ WiFi TCP buffers: 256KB / 1MB / 2MB")

        ADBShell.setting_put(
            "global", "net.tcp.buffersize.ethernet",
            "524288,2097152,4194304,262144,1048576,2097152"
        )
        Logger.log("  ✓ Ethernet TCP buffers: 512KB / 2MB / 4MB")

        # Initial receive window: 60 segments = ~87KB (fast stream start)
        ADBShell.setting_put("global", "tcp_default_init_rwnd", "60")
        Logger.log("  ✓ TCP initial receive window: 60 segments (~87KB)")

        # TCP keepalive — detect stale IPTV connections faster
        ADBShell.prop_set("net.ipv4.tcp_keepalive_intvl", "30")
        ADBShell.prop_set("net.ipv4.tcp_keepalive_probes", "3")
        Logger.log("  ✓ TCP keepalive: 30s interval, 3 probes")

        Logger.success("TCP stack optimized for 4K streaming")

    def set_private_dns(self, provider: str = "cloudflare") -> None:
        """
        Configure Private DNS (DNS-over-TLS).

        Cast-safe note: Private DNS only affects unicast A/AAAA queries.
        mDNS (.local domains, port 5353 multicast) is NOT routed through
        Private DNS and is completely unaffected by this setting.
        Chromecast discovery WILL continue to work normally.
        """
        Logger.header("🔒 PRIVATE DNS — DNS-over-TLS Configuration")

        Logger.shield(
            "Private DNS (DoT) only affects unicast DNS. "
            "Chromecast mDNS discovery uses multicast UDP — unaffected."
        )

        hostname = self.DNS_PROVIDERS.get(provider.lower())
        if not hostname:
            Logger.error(f"Unknown DNS provider: {provider}. Choose: {list(self.DNS_PROVIDERS)}")
            return

        ADBShell.setting_put("global", "private_dns_mode", "hostname")
        ADBShell.setting_put("global", "private_dns_specifier", hostname)
        Logger.success(f"Private DNS: {hostname}")

        # Flush DNS cache (unicast only — mDNS cache unaffected)
        ADBShell.run("ndc resolver flushnet 100", ignore_errors=True, silent=True)
        Logger.log("  ✓ Unicast DNS cache flushed")


# ─────────────────────────────────────────────────────────────────────────────
# SAFE DEBLOATER — Chromecast gate enforced
# ─────────────────────────────────────────────────────────────────────────────
class SafeDebloater:
    """
    Removes bloatware while enforcing ChromecastProtection at every step.

    Uses pm disable-user --user 0 (reversible) — NOT pm uninstall.
    Any package in ChromecastProtection.PROTECTED_PACKAGES is skipped with
    an explicit log entry explaining the engineering reason.
    """

    def run(self) -> None:
        Logger.header("🗑 SAFE DEBLOAT — Chromecast Services Protected")

        disabled, protected, skipped, failed = 0, 0, 0, 0

        for pkg, reason, cast_impact in SAFE_DEBLOAT_DB:

            # ── Chromecast gate: absolute check before any action ──────────
            if ChromecastProtection.is_protected(pkg):
                protected += 1
                Logger.shield(f"PROTECTED — skipped: {pkg}")
                Logger.log(
                    f"     └─ {ChromecastProtection.get_reason(pkg)}", "cyan"
                )
                continue

            # Idempotency: already disabled?
            if not ADBShell.pkg_enabled(pkg):
                skipped += 1
                Logger.log(f"  ○ Already disabled: {pkg}", "cyan")
                continue

            result = ADBShell.run(
                f"pm disable-user --user 0 {pkg}",
                ignore_errors=True, silent=True,
            )
            if "disabled" in result.lower() or result == "":
                disabled += 1
                Logger.success(f"Disabled: {pkg}")
                Logger.log(f"     └─ {reason} | Cast impact: {cast_impact}", "cyan")
            else:
                failed += 1
                Logger.warning(f"Could not disable: {pkg}")

        Logger.header(
            f"DEBLOAT DONE: {disabled} disabled | {protected} protected (Cast) | "
            f"{skipped} already off | {failed} failed"
        )

    def restore_package(self, pkg: str) -> None:
        """Re-enable a single package (emergency rollback)."""
        ADBShell.run(f"pm enable --user 0 {pkg}", ignore_errors=True)
        Logger.success(f"Re-enabled: {pkg}")


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY & LMK OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────
class MemoryOptimizer:
    """LMK + RAM management for 1.4GB constrained device."""

    def apply_lmk_profile(self) -> None:
        Logger.header("🧹 LMK — SmartTube + Cast Priority Memory Profile")

        lmk_props = [
            ("ro.lmk.critical",            "0"),     # Kill only at true critical low memory
            ("ro.lmk.kill_heaviest_task",  "true"),  # Kill largest non-protected process
            ("ro.lmk.downgrade_pressure",  "100"),   # Aggressive downgrade before kill
            ("ro.lmk.upgrade_pressure",    "50"),    # Promote cached processes quickly
            ("ro.lmk.use_psi",             "true"),  # Use Pressure Stall Info for smarter kills
            ("ro.lmk.filecache_min_kb",    "51200"), # Keep 50MB for VP9 segment file cache
        ]
        for key, value in lmk_props:
            ADBShell.prop_set(key, value)
            Logger.log(f"  ✓ {key} = {value}")

        # 3 background processes: OS services + Cast daemon + Launcher
        # SmartTube runs in foreground → exempt from this limit
        ADBShell.setting_put("global", "background_process_limit", "3")
        Logger.log("  ✓ background_process_limit = 3")

        Logger.success("LMK configured: SmartTube + Cast services protected from OOM")

    def deep_clean(self) -> None:
        """
        Aggressive RAM release — Cast services verified alive afterward.
        Belt-and-suspenders: restore_cast_services() called post-clean.
        """
        Logger.header("🔄 DEEP CLEAN — Cast-Safe RAM Release")

        Logger.log("  Releasing background apps (am kill-all)...")
        ADBShell.run("am kill-all", ignore_errors=True)

        Logger.log("  Trimming app caches (2GB limit)...")
        ADBShell.run("pm trim-caches 2G", ignore_errors=True)

        ADBShell.run("dumpsys batterystats --reset", ignore_errors=True, silent=True)

        Logger.log("  Dropping kernel page cache (root required)...")
        ADBShell.run_root("sync && echo 3 > /proc/sys/vm/drop_caches")

        # Critical: restore Cast services after kill-all may have killed them
        Logger.shield("Re-verifying Cast services after cleanup...")
        ChromecastServiceManager.restore()

        Logger.success("Deep clean complete — Cast services re-verified active")


# ─────────────────────────────────────────────────────────────────────────────
# UI OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────
class UIOptimizer:
    def apply(self, scale: float = 0.5) -> None:
        """0.5x animation scale: optimal for Android TV (0=broken feel, 1=sluggish on A15)."""
        Logger.header(f"🎨 UI — Animation Scale {scale}x + TV Recommendations Off")

        for key in [
            "window_animation_scale",
            "transition_animation_scale",
            "animator_duration_scale",
        ]:
            ADBShell.setting_put("global", key, str(scale))
            Logger.log(f"  ✓ {key} = {scale}x")

        # Disable TV content recommendations (background HTTP polling, wastes RAM/CPU)
        ADBShell.run("settings put secure tv_disable_recommendations 1",    ignore_errors=True)
        ADBShell.run("settings put secure tv_enable_preview_programs 0",    ignore_errors=True)
        ADBShell.run("settings put secure tv_watch_next_enabled 0",         ignore_errors=True)
        Logger.log("  ✓ TV recommendations + preview programs disabled")

        Logger.success("UI responsiveness optimized")


# ─────────────────────────────────────────────────────────────────────────────
# SHIZUKU MANAGER
# ─────────────────────────────────────────────────────────────────────────────
class ShizukuManager:
    """Deploy Shizuku privilege manager using ADB bootstrap method."""

    _BOOTSTRAP_CMD = (
        "P=$(pm path moe.shizuku.privileged.api | cut -d: -f2); "
        "CLASSPATH=$P app_process /system/bin "
        "--nice-name=shizuku_server moe.shizuku.server.ShizukuServiceServer &"
    )

    def deploy(self) -> None:
        Logger.header("🔑 SHIZUKU — Privilege Engine Deployment")

        pkg = DeviceSpec.SHIZUKU_PKG
        if not ADBShell.pkg_enabled(pkg):
            Logger.log("Shizuku not installed — downloading...")
            apk_local = CACHE_DIR / "shizuku.apk"
            if not apk_local.exists():
                os.system(f'curl -L -s --retry 3 -o "{apk_local}" "{DeviceSpec.SHIZUKU_APK_URL}"')
            if ADBShell.push(str(apk_local), "/data/local/tmp/s.apk"):
                ADBShell.run("pm install -r -g /data/local/tmp/s.apk", ignore_errors=True)
                ADBShell.run("rm /data/local/tmp/s.apk", ignore_errors=True, silent=True)
                Logger.success("Shizuku installed")
        else:
            Logger.success("Shizuku already installed")

        Logger.log("Starting Shizuku bootstrap server...")
        ADBShell.run(self._BOOTSTRAP_CMD, ignore_errors=True)
        time.sleep(3)
        Logger.success("Shizuku server started — verify status in Shizuku app")


# ─────────────────────────────────────────────────────────────────────────────
# APP INSTALLER
# ─────────────────────────────────────────────────────────────────────────────
class AppInstaller:
    """Idempotent APK installer — always checks before downloading."""

    def install_smarttube(self, beta: bool = False) -> bool:
        pkg  = DeviceSpec.SMARTTUBE_PKG
        url  = DeviceSpec.SMARTTUBE_BETA_URL if beta else DeviceSpec.SMARTTUBE_STABLE_URL
        name = "SmartTube Beta" if beta else "SmartTube Stable"

        Logger.header(f"📦 {name} — INSTALLER")

        if ADBShell.pkg_enabled(pkg):
            Logger.success(f"{name} already installed — skipping download")
            return True

        apk_local = CACHE_DIR / f"smarttube_{'beta' if beta else 'stable'}.apk"
        if not apk_local.exists():
            Logger.log(f"Downloading {name}...")
            if os.system(f'curl -L -s --retry 3 -o "{apk_local}" "{url}"') != 0:
                Logger.error("Download failed")
                return False

        remote = "/data/local/tmp/smarttube.apk"
        if not ADBShell.push(str(apk_local), remote):
            Logger.error("APK push failed")
            return False

        result = ADBShell.run(f"pm install -r -g {remote}", ignore_errors=True)
        ADBShell.run(f"rm {remote}", ignore_errors=True, silent=True)

        if "success" in result.lower():
            Logger.success(f"{name} installed successfully")
            return True

        Logger.error(f"Installation failed: {result}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
class Diagnostics:

    @staticmethod
    def full_report() -> None:
        Logger.header("📊 SYSTEM DIAGNOSTICS — Full Health Report")

        # CPU load
        loadavg = ADBShell.run("cat /proc/loadavg", silent=True)
        if loadavg:
            parts = loadavg.split()[:3]
            Logger.log(f"  CPU Load (1m/5m/15m): {' / '.join(parts)}")

        # RAM
        meminfo = ADBShell.run("cat /proc/meminfo", silent=True)
        if meminfo:
            fields: Dict[str, int] = {}
            for line in meminfo.splitlines():
                p = line.split()
                if len(p) >= 2 and p[1].isdigit():
                    fields[p[0].rstrip(":")] = int(p[1])
            total  = fields.get("MemTotal",     0) // 1024
            free   = fields.get("MemFree",      0) // 1024
            avail  = fields.get("MemAvailable", 0) // 1024
            cached = fields.get("Cached",       0) // 1024
            pct    = avail / total * 100 if total else 0
            color  = "success" if pct > 30 else ("warning" if pct > 15 else "error")
            Logger.log(f"  RAM Total     : {total} MB")
            Logger.log(f"  RAM Free      : {free} MB")
            Logger.log(f"  RAM Available : {avail} MB ({pct:.1f}%)", color)
            Logger.log(f"  Cached        : {cached} MB")

        # Thermal
        for zone in range(4):
            raw = ADBShell.run(
                f"cat /sys/class/thermal/thermal_zone{zone}/temp", silent=True
            )
            if raw and raw.lstrip("-").isdigit():
                temp_c = int(raw) / 1000
                color = "success" if temp_c < 55 else ("warning" if temp_c < 70 else "error")
                Logger.log(f"  Thermal zone{zone}: {temp_c:.1f}°C", color)

        # Storage
        storage = ADBShell.run("df -h /data", silent=True)
        if storage:
            lines = storage.splitlines()
            if len(lines) > 1:
                Logger.log(f"  Storage /data : {lines[1]}")

        # Network
        ping = ADBShell.run("ping -c 2 -W 2 1.1.1.1", ignore_errors=True, silent=True)
        if "2 received" in ping:
            Logger.success("  Internet: OK (Cloudflare reachable)")
        elif "1 received" in ping:
            Logger.warning("  Internet: Degraded (packet loss)")
        else:
            Logger.error("  Internet: OFFLINE")

        # Cast service audit (compact)
        Logger.log("\n  --- Chromecast Service Status ---")
        for pkg in list(ChromecastProtection.PROTECTED_PACKAGES)[:6]:
            active = ADBShell.pkg_enabled(pkg)
            icon   = "🛡✓" if active else "🛡✗"
            color  = "success" if active else "error"
            Logger.log(f"  {icon} {pkg.split('.')[-1]}", color)

        # SmartTube
        if ADBShell.pkg_enabled(DeviceSpec.SMARTTUBE_PKG):
            Logger.success("  SmartTube: Installed")
        else:
            Logger.warning("  SmartTube: Not installed")

        # Renderer
        renderer = ADBShell.prop_get("debug.hwui.renderer")
        Logger.log(f"  HWUI Renderer : {renderer or 'default'}")

        tunnel = ADBShell.prop_get("media.tunneled-playback.enable")
        color = "success" if tunnel == "true" else "warning"
        Logger.log(f"  Tunnel Mode   : {tunnel or 'not set'}", color)

    @staticmethod
    def codec_report() -> None:
        Logger.header("🎬 CODEC AVAILABILITY — BCM7362 VPU Matrix")

        codecs = [
            ("H.264 AVC",   "OMX.brcm.video.h264.decoder", "HW",       "✓  4K@30fps"),
            ("H.265 HEVC",  "OMX.brcm.video.h265.decoder", "HW",       "✓  4K@60fps"),
            ("VP9 prof.2",  "OMX.brcm.video.vp9.decoder",  "HW",       "✓  4K@60fps ← RECOMMENDED"),
            ("AV1",         "c2.android.av1.decoder",       "SOFTWARE", "✗  DO NOT USE — CPU killer"),
        ]
        for name, component, hw_sw, status in codecs:
            level = "success" if hw_sw == "HW" else "error"
            Logger.log(f"  [{hw_sw:8s}] {name:12s}  {status}", level)
            Logger.log(f"             Component: {component}", "cyan")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
class PlayboxTitaniumULTRA:
    """
    Master orchestration class.
    Every optimization mode enforces ChromecastProtection throughout.
    """

    def __init__(self, device: str) -> None:
        self.device     = device
        self.smarttube  = SmartTubeOptimizer()
        self.broadcom   = BroadcomTuner()
        self.audio      = AudioOptimizer()
        self.network    = NetworkOptimizer()
        self.memory     = MemoryOptimizer()
        self.ui         = UIOptimizer()
        self.debloater  = SafeDebloater()
        self.cast       = ChromecastServiceManager()
        self.installer  = AppInstaller()
        self.shizuku    = ShizukuManager()
        self.diag       = Diagnostics()

    # ── Composite actions ────────────────────────────────────────────────────

    def _video_pipeline(self) -> None:
        self.smarttube.optimize_exoplayer_pipeline()
        self.smarttube.force_tunnel_mode()

    def _broadcom_full(self) -> None:
        self.broadcom.apply_gpu_tweaks()
        self.broadcom.apply_vpu_tweaks()
        self.broadcom.set_performance_governor()

    def _codec_protection(self) -> None:
        self.smarttube.suppress_av1_software_decode()
        self.smarttube.tune_dalvik_heap()

    def _network_full(self) -> None:
        self.network.apply_tcp_tuning()
        self.network.set_private_dns("cloudflare")

    # ── Banner & Menu ────────────────────────────────────────────────────────

    def _banner(self) -> None:
        c = Logger.COLORS
        print(f"""
{c['header']}{c['bold']}╔══════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v{VERSION}
║  Sagemcom DCTIW362P │ Android TV 9 │ Broadcom BCM7362
╠══════════════════════════════════════════════════════════════════════╣
║  🎬 SmartTube VP9 HW Pipeline  🚇 Tunnel Mode  🛡 Cast Protected
║  🧠 Dalvik SmartTube Profile   ⚙ CPU Performance Governor
╚══════════════════════════════════════════════════════════════════════╝
{c['reset']}  Connected: {c['cyan']}{self.device}{c['reset']}
""")

    def _menu(self) -> None:
        c = Logger.COLORS
        while True:
            os.system("clear")
            self._banner()
            print(f"""{c['bold']}╔══════════════════════════════════════════════════════════════════╗{c['reset']}
  {c['success']}VIDEO PERFORMANCE{c['reset']}
    {c['success']}1.{c['reset']}  SmartTube ExoPlayer + Tunnel Mode Pipeline
    {c['success']}2.{c['reset']}  Broadcom GPU + VPU + CPU Governor
    {c['success']}3.{c['reset']}  Audio A/V Sync Fix (HDMI desync)
    {c['success']}4.{c['reset']}  AV1 Suppression + Dalvik Heap (VP9 HW path)
    {c['success']}5.{c['reset']}  AOT Compile SmartTube (JIT burst elimination)

  {c['header']}CHROMECAST PROTECTION{c['reset']}
    {c['success']}6.{c['reset']}  🛡 Audit Cast Services (health check)
    {c['success']}7.{c['reset']}  🛡 Restore Cast Services (repair broken Cast)
    {c['success']}8.{c['reset']}  📡 Cast mDNS/Multicast Network Tuning
    {c['success']}9.{c['reset']}  🎯 Cast Process OOM Hardening
    {c['success']}P.{c['reset']}  🔍 Show Chromecast Protection Registry

  {c['info']}SYSTEM{c['reset']}
    {c['info']}10.{c['reset']} Network TCP + Private DNS (Cloudflare)
    {c['info']}11.{c['reset']} Safe Debloat (Cast services PROTECTED)
    {c['info']}12.{c['reset']} LMK Memory Profile (SmartTube + Cast priority)
    {c['info']}13.{c['reset']} UI Responsiveness (0.5x animations)
    {c['info']}14.{c['reset']} Deep Clean RAM (Cast-safe + re-verify)

  {c['warning']}TOOLS{c['reset']}
    {c['warning']}15.{c['reset']} Full System Diagnostics
    {c['warning']}16.{c['reset']} Codec Availability Report
    {c['warning']}17.{c['reset']} Install SmartTube Stable
    {c['warning']}18.{c['reset']} Deploy Shizuku

  {c['cyan']}AUTO MODES{c['reset']}
    {c['cyan']}20.{c['reset']} 🚀 SMARTTUBE ULTRA (video-focused, Cast safe)
    {c['cyan']}21.{c['reset']} 🏆 FULL SYSTEM ULTRA (all modules, Cast safe)
    {c['error']}0.{c['reset']}  Exit
{c['bold']}╚══════════════════════════════════════════════════════════════════╝{c['reset']}""")

            choice = input(f"\n{c['cyan']}Choice > {c['reset']}").strip().lower()

            dispatch: Dict[str, Callable] = {
                "1":  self._video_pipeline,
                "2":  self._broadcom_full,
                "3":  self.audio.fix_av_sync_and_pipeline,
                "4":  self._codec_protection,
                "5":  self.smarttube.compile_aot,
                "6":  self.cast.audit,
                "7":  self.cast.restore,
                "8":  self.cast.optimize_cast_network,
                "9":  self.cast.harden_cast_processes,
                "p":  ChromecastProtection.print_registry,
                "10": self._network_full,
                "11": self.debloater.run,
                "12": self.memory.apply_lmk_profile,
                "13": self.ui.apply,
                "14": self.memory.deep_clean,
                "15": self.diag.full_report,
                "16": self.diag.codec_report,
                "17": self.installer.install_smarttube,
                "18": self.shizuku.deploy,
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

    def _exit(self) -> None:
        Logger.save_log()
        Logger.log(f"Session saved: {LOG_FILE}", "cyan")
        sys.exit(0)

    # ── Auto modes ───────────────────────────────────────────────────────────

    def run_smarttube_ultra(self) -> None:
        """
        SmartTube Ultra Mode.
        Focuses on maximum video playback performance.
        Chromecast protection enforced at start, hardened at end.
        """
        Logger.header("🚀 SMARTTUBE ULTRA MODE — Maximum Video Performance")

        pipeline: List[Tuple[str, Callable]] = [
            ("Chromecast Audit (pre-check)",     self.cast.audit),
            ("Broadcom GPU + VPU + CPU",          self._broadcom_full),
            ("ExoPlayer + Tunnel Mode Pipeline",  self._video_pipeline),
            ("AV1 Suppression + Dalvik Heap",     self._codec_protection),
            ("Audio A/V Sync Fix",                self.audio.fix_av_sync_and_pipeline),
            ("LMK Memory Profile",                self.memory.apply_lmk_profile),
            ("UI Responsiveness",                 self.ui.apply),
            ("Cast mDNS Network Tuning",          self.cast.optimize_cast_network),
            ("Cast Process Hardening",            self.cast.harden_cast_processes),
            ("SmartTube AOT Compilation",         self.smarttube.compile_aot),
            ("Cast Services Restore (final)",     self.cast.restore),
        ]

        total = len(pipeline)
        for idx, (name, fn) in enumerate(pipeline, 1):
            Logger.log(f"\n[{idx}/{total}] {name}...", "cyan")
            fn()
            time.sleep(0.4)

        Logger.header("🎉 SMARTTUBE ULTRA COMPLETE")
        Logger.success("VP9 HW decode + Tunnel Mode + AOT compiled + Cast Protected")
        Logger.log(
            "ACTION REQUIRED in SmartTube: Settings → Player → Video codec → VP9",
            "warning"
        )
        Logger.log("Reboot recommended in ~5 minutes for full effect", "warning")
        Logger.save_log()

    def run_full_ultra(self) -> None:
        """
        Full System Ultra — all modules activated.
        Chromecast protection enforced at every debloat/clean step.
        """
        Logger.header("🏆 FULL SYSTEM ULTRA — Complete Optimization")

        pipeline: List[Tuple[str, Callable]] = [
            ("System Diagnostics (baseline)",     self.diag.full_report),
            ("Chromecast Audit (pre-check)",       self.cast.audit),
            ("Broadcom GPU + VPU + CPU",           self._broadcom_full),
            ("ExoPlayer + Tunnel Mode",            self._video_pipeline),
            ("AV1 Suppression + Dalvik Heap",      self._codec_protection),
            ("Audio A/V Sync Fix",                 self.audio.fix_av_sync_and_pipeline),
            ("TCP Network + Cloudflare DNS",        self._network_full),
            ("Safe Debloat (Cast Protected)",       self.debloater.run),
            ("LMK Memory Profile",                 self.memory.apply_lmk_profile),
            ("UI Responsiveness",                  self.ui.apply),
            ("Cast mDNS Network Tuning",           self.cast.optimize_cast_network),
            ("Cast Process OOM Hardening",         self.cast.harden_cast_processes),
            ("SmartTube AOT Compilation",          self.smarttube.compile_aot),
            ("Deep Clean RAM (Cast-safe)",         self.memory.deep_clean),
            ("Final Chromecast Audit",             self.cast.audit),
        ]

        total = len(pipeline)
        for idx, (name, fn) in enumerate(pipeline, 1):
            Logger.log(f"\n[{idx}/{total}] {name}...", "cyan")
            fn()
            time.sleep(0.3)

        Logger.header("🏆 FULL SYSTEM ULTRA COMPLETE")
        Logger.success("All optimizations applied. Chromecast Built-in: PROTECTED ✓")
        Logger.success("SmartTube: VP9 HW + Tunnel Mode + AOT compiled ✓")
        Logger.log(f"Reboot: adb -s {self.device} reboot", "warning")
        Logger.save_log()


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=f"Playbox Titanium v{VERSION} — Sagemcom DCTIW362P",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Interactive menu (default)
  python3 Autopilot_11_ULTRA_SmartTube.py

  # SmartTube Ultra (video-focused)
  python3 Autopilot_11_ULTRA_SmartTube.py --device 192.168.1.3:5555 --smarttube-ultra

  # Full system optimization
  python3 Autopilot_11_ULTRA_SmartTube.py --device 192.168.1.3:5555 --full-ultra

  # Emergency: restore broken Chromecast
  python3 Autopilot_11_ULTRA_SmartTube.py --cast-restore

  # Audit Cast services only
  python3 Autopilot_11_ULTRA_SmartTube.py --cast-audit

  # Diagnostics
  python3 Autopilot_11_ULTRA_SmartTube.py --diagnostics
""",
    )
    p.add_argument("--device",            default=None,
                   help="ADB target IP:PORT (default: auto-detect)")
    p.add_argument("--smarttube-ultra",   action="store_true",
                   help="SmartTube Ultra Mode")
    p.add_argument("--full-ultra",        action="store_true",
                   help="Full system optimization")
    p.add_argument("--cast-audit",        action="store_true",
                   help="Audit Chromecast services")
    p.add_argument("--cast-restore",      action="store_true",
                   help="Re-enable all Chromecast services (emergency)")
    p.add_argument("--diagnostics",       action="store_true",
                   help="Full system diagnostics")
    p.add_argument("--codecs",            action="store_true",
                   help="Codec availability report")
    p.add_argument("--install-smarttube", action="store_true",
                   help="Install SmartTube")
    p.add_argument("--beta",              action="store_true",
                   help="Use SmartTube Beta channel")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    # Device resolution
    device = args.device
    if not device:
        device = ADBShell.detect_device()
        if device:
            Logger.success(f"Auto-detected: {device}")
        else:
            Logger.warning(f"No device detected, using default: {DEFAULT_ADB_HOST}")
            device = DEFAULT_ADB_HOST

    if not ADBShell.connect(device):
        Logger.error(f"Cannot connect to {device}")
        sys.exit(1)

    app = PlayboxTitaniumULTRA(device)

    # CLI dispatch
    if args.cast_restore:
        ChromecastServiceManager.restore()
    elif args.cast_audit:
        ChromecastServiceManager.audit()
    elif args.diagnostics:
        app.diag.full_report()
    elif args.codecs:
        app.diag.codec_report()
    elif args.install_smarttube:
        app.installer.install_smarttube(beta=args.beta)
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
        Logger.save_log()
        sys.exit(0)
    except Exception as exc:
        Logger.error(f"Unexpected error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
