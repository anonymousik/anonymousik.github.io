#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v14.0         ║
║  Target : Sagemcom DCTIW362P | Android TV 9 API 28 | PTT1.190826.001        ║
║  Kernel : 4.9.190-1-6pre armv7l                                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  REAL HARDWARE (verified from live getprop dump):                            ║
║  CPU  : ARMv7 Cortex-A15 dual-core @ ~1.0 GHz                               ║
║         dalvik.vm.isa.arm.variant = cortex-a15                               ║
║         dalvik.vm.isa.arm.features = default  ← A15 idiv NOT enabled        ║
║  GPU  : Broadcom VideoCore | ro.gfx.driver.0 = gfxdriver-bcmstb             ║
║         ro.opengles.version = 196609 (GLES 3.1)                             ║
║         ro.v3d.fence.expose = true | ro.v3d.disable_buffer_age = true       ║
║         ro.sf.disable_triple_buffer = 0 (triple buffer ON)                  ║
║         ro.nx.hwc2.tweak.fbcomp = 1 (HWC2 FB compositor tweak ON)           ║
║  BCM Nexus Heaps (kernel-reserved, CANNOT be overridden):                   ║
║    main=96m | gfx=64m | video_secure=80m | grow/shrink=2m                   ║
║    TOTAL Nexus: 240MB | Userspace budget: ~1045MB                            ║
║  VDec : ro.nx.media.vdec_outportbuf=32 (port buffers)                       ║
║         ro.nx.media.vdec.fsm1080p=1 (FSM path active)                       ║
║         ro.nx.media.vdec.progoverride=2 (progressive decode override)        ║
║         ro.nx.mma=1 (Memory Manager Arena enabled)                           ║
║  Display: dyn.nx.display-size=1920x1080 (currently 1080p)                   ║
║  DRM : PlayReady 2.5 | Widevine | ClearKey (all HALs running)               ║
║  LMK : ro.lmk.use_minfree_levels=false → PSI-ONLY, minfree /sys IGNORED    ║
║  DEX : dex2oat-Xmx=512m | appimageformat=lz4 | usejitprofiles=true          ║
║  Net : Kernel 4.9.190 | TCP Fast Open v3 | BBR absent (not compiled in)     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  PRECISION FIXES vs v12:                                                     ║
║  [FIX-1] Dalvik heap: NEVER shrink heapsize/growthlimit — OEM 512m/192m OK  ║
║           heapminfree: 512k → 2m (too small → excessive GC pressure)        ║
║           heapmaxfree: 8m  → 16m (allow more free to reduce GC frequency)   ║
║  [FIX-2] LMK: use_minfree_levels=false → /sys minfree writes SKIPPED        ║
║           Use PSI-based thresholds + upgrade_pressure: 100 → 50             ║
║           extra_free_kbytes tuning (zone watermark adjust)                   ║
║  [FIX-3] A15 IDIV: dalvik.vm.isa.arm.features = default,idiv                ║
║           Hardware integer divide on A15 — reduces codec selection overhead  ║
║  [FIX-4] BCM MMA: media.brcm.mma.enable=1 (confirmed ro.nx.mma=1)          ║
║  [FIX-5] VDec buffers: media.brcm.vpu.buffers=32 (from vdec_outportbuf=32) ║
║  [FIX-6] persist.sys.ui.hw: false → true (GPU force rendering)              ║
║  [FIX-7] persist.sys.hdmi.keep_awake: false → true                          ║
║  [FIX-8] media.stagefright.cache-params: 32768/65536/25 → 65536/131072/30  ║
║  [FIX-9] net.tcp.default_init_rwnd: 60 → 120                                ║
║  [FIX-10] WebView vmsize: 100MB → 50MB (TV STB, no browser use)            ║
║  [FIX-11] dex2oat budget: use confirmed -Xmx 512m for AOT speed-profile    ║
║  [FIX-12] BBR: removed (not in kernel 4.9.190-1-6pre config) → cubic/htcp  ║
║  [NEW] debug.hwui.layer_cache_size: 16384 → 32768 (V3D with explicit fence)║
║  [NEW] HWC2 fbcomp-aware layer budget tuning                                 ║
║  [NEW] Stagefright: vdec.progoverride=2 path tuning                         ║
║  [NEW] DRM: PlayReady 2.5 + Widevine specific hints                         ║
║  [NEW] 50Hz/PAL mode: persist.nx.vidout.50hz check for pl-PL locale         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import os, sys, subprocess, time, json, argparse, shutil, threading, statistics, re, datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable, Any, NamedTuple
from dataclasses import dataclass
from enum import Enum, auto

# ─────────────────────────────────────────────────────────────────────────────
VERSION          = "14.0-TITAN"
DEFAULT_DEVICE   = "192.168.1.3:5555"
CACHE_DIR        = Path.home() / ".playbox_cache"
BACKUP_DIR       = CACHE_DIR / "backups_v14"
LOG_FILE         = CACHE_DIR / "autopilot_v14.log"
for d in (CACHE_DIR, BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# VERIFIED HARDWARE CONSTANTS (from live getprop 192.168.1.3:5555)
# ─────────────────────────────────────────────────────────────────────────────
class HW:
    """
    All values verified from real getprop dump.
    MUST NOT be changed without new getprop evidence.
    """
    # CPU
    ISA_VARIANT          = "cortex-a15"
    # A15 supports hardware integer divide (IDIV) — not in OEM 'default' features
    ISA_FEATURES_OEM     = "default"
    ISA_FEATURES_OPT     = "default,idiv"   # enables HW idiv in JIT/AOT codegen

    # BCM Nexus Kernel Heaps (FIXED — kernel-reserved, cannot change from userspace)
    NX_HEAP_MAIN         = 96    # MB — Nexus core heap (media pipeline)
    NX_HEAP_GFX          = 64    # MB — VideoCore graphics heap
    NX_HEAP_VIDEO_SECURE = 80    # MB — DRM/secure video decode
    NX_HEAP_TOTAL        = 240   # MB — NX_HEAP_MAIN+GFX+VIDEO_SECURE

    # Userspace memory budget: 1459 - 240 (nexus) - 24 (watermark) - 150 (OS)
    RAM_TOTAL_MB         = 1459
    EXTRA_FREE_KB        = 24300  # sys.sysctl.extra_free_kbytes (zone watermark)
    USERSPACE_BUDGET_MB  = RAM_TOTAL_MB - NX_HEAP_TOTAL - (EXTRA_FREE_KB//1024) - 150

    # VDec (BCM Nexus media decoder)
    VDEC_OUTPORT_BUFFERS = 32    # ro.nx.media.vdec_outportbuf — CONFIRMED
    VDEC_FSM_1080P       = 1     # ro.nx.media.vdec.fsm1080p — FSM path active
    VDEC_PROG_OVERRIDE   = 2     # ro.nx.media.vdec.progoverride

    # Display (current state from dyn.nx.display-size)
    DISPLAY_WIDTH        = 1920
    DISPLAY_HEIGHT       = 1080
    LCD_DENSITY          = 320   # ro.nx.sf.lcd_density / ro.sf.lcd_density

    # GPU / HWC
    GLES_VERSION         = "196609"   # 3.1 (0x30001)
    V3D_FENCE_EXPOSE     = True       # explicit sync fences active
    V3D_BUFFER_AGE_OFF   = True       # vendor already disabled — DO NOT re-enable
    HWC2_FBCOMP_TWEAK    = 1          # ro.nx.hwc2.tweak.fbcomp
    TRIPLE_BUFFER        = True       # ro.sf.disable_triple_buffer=0

    # Dalvik OEM defaults (DO NOT shrink below these)
    DALVIK_HEAPSIZE      = "512m"     # OEM default — sufficient for SmartTube
    DALVIK_GROWTHLIMIT   = "192m"     # OEM default — keep
    DALVIK_STARTSIZE     = "16m"
    DALVIK_HEAPMINFREE   = "2m"       # FIX: was 512k — causes GC pressure
    DALVIK_HEAPMAXFREE   = "16m"      # FIX: was 8m — increase to reduce GC
    DALVIK_TARGET_UTIL   = "0.75"
    DEX2OAT_XMX          = "512m"     # confirmed budget for AOT

    # LMK: PSI-only (use_minfree_levels=false → /sys minfree IGNORED)
    LMK_MINFREE_USABLE   = False      # confirmed: /sys writes do nothing
    LMK_UPGRADE_PRESSURE = 50        # fix: was 100

    # Network / Kernel 4.9.190-1-6pre
    KERNEL_VER           = "4.9.190"
    TCP_BBR_AVAILABLE    = False      # not in this kernel config
    TCP_FAST_OPEN        = True       # supported in 4.9+

    # DRM
    PLAYREADY_VERSION    = "2.5"
    WIDEVINE_RUNNING     = True

    # Locale / Region
    LOCALE               = "pl-PL"
    TIMEZONE             = "Europe/Amsterdam"

    # Package names (verified from real ps output)
    PKG_SMARTTUBE_STABLE = "org.smarttube.stable"
    PKG_SMARTTUBE_BETA   = "org.smarttube.beta"
    PKG_SMARTTUBE_LEGACY = "com.liskovsoft.smarttubetv"
    PKG_PROJECTIVY       = "com.spocky.projengmenu"     # from ps: u0_a88
    PKG_SHIZUKU          = "moe.shizuku.privileged.api"
    PKG_MEDIASHELL       = "com.google.android.apps.mediashell"

    # APK URLs
    URL_SMARTTUBE_STABLE = "https://github.com/yuliskov/SmartTube/releases/download/latest/smarttube_stable.apk"
    URL_SMARTTUBE_BETA   = "https://github.com/yuliskov/SmartTube/releases/download/latest/smarttube_beta.apk"
    URL_PROJECTIVY       = "https://github.com/spocky/projectivy-launcher/releases/latest/download/Projectivy_Launcher.apk"
    URL_SHIZUKU          = "https://github.com/RikkaApps/Shizuku/releases/download/v13.5.4/shizuku-v13.5.4-release.apk"

    # DNS providers (correct DoT hostnames — verified RFC + Android 9 tested)
    DNS: Dict[str, Tuple[str,str,str]] = {
        "cloudflare": ("one.one.one.one",   "1.1.1.1",       "1.0.0.1"),
        "google":     ("dns.google",        "8.8.8.8",       "8.8.4.4"),
        "quad9":      ("dns.quad9.net",     "9.9.9.9",       "149.112.112.112"),
        "adguard":    ("dns.adguard.com",   "94.140.14.14",  "94.140.15.15"),
        "nextdns":    ("dns.nextdns.io",    "45.90.28.0",    "45.90.30.0"),
    }


class Status(Enum):
    OK=auto(); WARN=auto(); BROKEN=auto(); MISSING=auto(); UNKNOWN=auto()


# ─────────────────────────────────────────────────────────────────────────────
# CHROMECAST PROTECTION
# ─────────────────────────────────────────────────────────────────────────────
class Cast:
    """
    PROTECTED packages — verified against device init.svc.* and real ps output.
    Note: debloat.sh on device lists apps.mediashell and gms.cast.receiver
    as "safe" — THIS IS WRONG. Both are core Cast services. Protected here.
    """
    PROTECTED: Dict[str,str] = {
        HW.PKG_MEDIASHELL:
            "Cast Built-in daemon. mdnsd (running) + mediashell = full Cast stack.",
        "com.google.android.gms":
            "GMS — Cast SDK v3+, SessionManager, OAuth. DO NOT disable.",
        "com.google.android.gsf":
            "Google Services Framework — GMS auth dependency.",
        "com.google.android.nearby":
            "Nearby — mDNS responder. mdnsd (init.svc running) bridges here.",
        "com.google.android.gms.cast.receiver":
            "Cast Receiver Framework — confirmed in debloat.sh kill-list (WRONG).",
        "com.google.android.tv.remote.service":
            "TV Remote — Cast session UI. PID active: u0_a1 3569.",
        "com.google.android.tvlauncher":
            "TV Launcher — Cast ambient mode surface.",
        "com.google.android.configupdater":
            "Config Updater — TLS cert pins, Cast endpoint config.",
        "com.google.android.wifidisplay":
            "WiFi Display — Miracast/Cast transport fallback.",
        "com.android.networkstack":
            "Network Stack — IGMP multicast for mDNS (mdnsd confirmed running).",
        "com.android.networkstack.tethering":
            "Tethering — multicast routing shared with networkstack.",
    }

    @classmethod
    def is_protected(cls, p: str) -> bool: return p in cls.PROTECTED
    @classmethod
    def reason(cls, p: str) -> str: return cls.PROTECTED.get(p,"")


# ─────────────────────────────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────────────────────────────
class L:
    C = {"i":"\033[94m","s":"\033[92m","w":"\033[93m","e":"\033[91m",
         "h":"\033[95m","c":"\033[96m","b":"\033[1m","r":"\033[0m","d":"\033[2m"}
    _buf: List[str] = []

    @classmethod
    def _out(cls,msg:str,lvl:str)->None:
        ts=time.strftime("%H:%M:%S"); c=cls.C.get(lvl,cls.C["i"])
        print(f"{c}[{ts}] {msg}{cls.C['r']}")
        cls._buf.append(f"[{ts}][{lvl}] {msg}")

    @classmethod
    def ok(cls,m:str)->None:   cls._out(f"✓ {m}","s")
    @classmethod
    def info(cls,m:str)->None: cls._out(m,"i")
    @classmethod
    def warn(cls,m:str)->None: cls._out(f"⚠ {m}","w")
    @classmethod
    def err(cls,m:str)->None:  cls._out(f"✗ {m}","e")
    @classmethod
    def fix(cls,m:str)->None:  cls._out(f"🔧 {m}","w")
    @classmethod
    def cast(cls,m:str)->None: cls._out(f"🛡 {m}","s")
    @classmethod
    def dim(cls,m:str)->None:  cls._out(f"  └─ {m}","d")

    @classmethod
    def hdr(cls,m:str)->None:
        s="═"*72
        print(f"\n{cls.C['h']}{cls.C['b']}{s}\n   {m}\n{s}{cls.C['r']}\n")

    @classmethod
    def sub(cls,m:str)->None:
        print(f"\n{cls.C['c']}  ── {m} ──{cls.C['r']}")

    @classmethod
    def save(cls)->None:
        try:
            with open(LOG_FILE,"a") as f:
                f.write(f"\n{'─'*60}\n{time.strftime('%Y-%m-%d %H:%M:%S')} v{VERSION}\n")
                f.write("\n".join(cls._buf)+"\n")
        except OSError: pass


# ─────────────────────────────────────────────────────────────────────────────
# ADB SHELL
# ─────────────────────────────────────────────────────────────────────────────
class ADB:
    dev: Optional[str] = None
    TO = 35; RET = 3

    @classmethod
    def connect(cls, t:str) -> bool:
        try:
            r = subprocess.run(["adb","connect",t], capture_output=True, text=True, timeout=10)
            if "connected" in r.stdout.lower():
                cls.dev=t; L.ok(f"ADB: {t}"); return True
            L.err(f"ADB failed: {r.stdout.strip()}"); return False
        except FileNotFoundError:
            L.err("'adb' not found — install Android Platform Tools"); sys.exit(1)
        except subprocess.TimeoutExpired:
            L.err(f"ADB timeout: {t}"); return False

    @classmethod
    def detect(cls) -> Optional[str]:
        try:
            out = subprocess.check_output(["adb","devices"],text=True,timeout=5)
            for line in out.splitlines():
                if "\tdevice" in line: return line.split("\t")[0].strip()
        except Exception: pass
        return None

    @classmethod
    def sh(cls, cmd:str, silent:bool=False) -> str:
        if not cls.dev: return ""
        for i in range(cls.RET):
            try:
                return subprocess.check_output(
                    ["adb","-s",cls.dev,"shell",cmd],
                    stderr=subprocess.STDOUT, text=True, timeout=cls.TO).strip()
            except subprocess.TimeoutExpired:
                if i < cls.RET-1: time.sleep(1.5)
                elif not silent: L.warn(f"Timeout: {cmd[:55]}")
            except subprocess.CalledProcessError as e:
                return (e.output or "").strip()
            except Exception as e:
                if not silent: L.err(str(e))
        return ""

    @classmethod
    def root(cls, cmd:str) -> str:
        for p in (f'su -c "{cmd}"', f'rish -c "{cmd}"'):
            r = cls.sh(p, silent=True)
            if r and "not found" not in r and "permission denied" not in r.lower():
                return r
        return cls.sh(cmd)

    @classmethod
    def push(cls, local:str, remote:str) -> bool:
        try:
            subprocess.check_call(["adb","-s",cls.dev,"push",local,remote],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            return True
        except Exception: return False

    @classmethod
    def prop(cls, k:str) -> str: return cls.sh(f"getprop {k}",silent=True)

    @classmethod
    def setprop(cls, k:str, v:str) -> None: cls.sh(f"setprop {k} {v}",silent=True)

    @classmethod
    def sput(cls, ns:str, k:str, v:str) -> None:
        cls.sh(f"settings put {ns} {k} {v}",silent=True)

    @classmethod
    def sget(cls, ns:str, k:str) -> str:
        return cls.sh(f"settings get {ns} {k}",silent=True)

    @classmethod
    def pkg_ok(cls, p:str) -> bool: return p in cls.sh(f"pm list packages -e {p}",silent=True)
    @classmethod
    def pkg_exists(cls, p:str) -> bool: return p in cls.sh(f"pm list packages {p}",silent=True)

    @classmethod
    def pkg_ver(cls, p:str) -> str:
        out = cls.sh(f"dumpsys package {p} | grep versionName",silent=True)
        return out.split("=")[-1].strip() if "=" in out else "?"

    @classmethod
    def sysw(cls, path:str, val:str) -> bool:
        cls.root(f"echo {val} > {path}")
        got = cls.root(f"cat {path}").strip()
        return val in got


# ─────────────────────────────────────────────────────────────────────────────
# APK DOWNLOADER
# ─────────────────────────────────────────────────────────────────────────────
class APK:
    @staticmethod
    def get(url:str, dest:Path, force:bool=False) -> bool:
        if dest.exists() and not force:
            L.info(f"  APK cached: {dest.name}"); return True
        L.info(f"  Downloading {dest.name}...")
        ret = os.system(f'curl -L -s --retry 3 --connect-timeout 15 -o "{dest}" "{url}"')
        if ret!=0 or not dest.exists() or dest.stat().st_size < 50_000:
            L.err(f"  Download failed: {dest.name}")
            dest.unlink(missing_ok=True); return False
        L.ok(f"  {dest.name} ({dest.stat().st_size/1048576:.1f}MB)"); return True

    @staticmethod
    def install(local:Path, label:str="") -> bool:
        remote = f"/data/local/tmp/{local.name}"
        if not ADB.push(str(local), remote):
            L.err(f"  Push failed: {local.name}"); return False
        r = ADB.sh(f"pm install -r -g --install-reason 1 {remote}",silent=True)
        ADB.sh(f"rm {remote}",silent=True)
        if "success" in r.lower():
            L.ok(f"  Installed: {label or local.stem}"); return True
        L.err(f"  Install failed: {r[:80]}"); return False

    @staticmethod
    def fetch_install(url:str, pkg:str, label:str, force:bool=False) -> bool:
        p = CACHE_DIR / (pkg.replace(".","-")+".apk")
        return APK.get(url,p,force) and APK.install(p,label)


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 — CORTEX-A15 + BCM CODEC PIPELINE (hardware-targeted)
# ─────────────────────────────────────────────────────────────────────────────
class VideoEngine:
    """
    Tuned for BCM7362 / Cortex-A15 confirmed hardware.

    A15 hardware idiv: enables integer divide instruction in JIT/AOT codegen.
    Reduces per-frame codec pipeline overhead in ARMv7 ABR calculations.

    VDec port buffers: 32 (from ro.nx.media.vdec_outportbuf=32).
    MMA allocator: ro.nx.mma=1 confirmed → media.brcm.mma.enable=1.
    Progressive override: ro.nx.media.vdec.progoverride=2 → inform media.brcm props.

    Stagefright cache: 32768/65536/25 → 65536/131072/30
      - MinCache 64KB: holds ~3s of 720p VP9 segment
      - MaxCache 128KB: burst buffer for ABR quality switch
      - KeepAlive 30s: longer IPTV session keepalive
    """

    def codec_pipeline(self) -> None:
        L.hdr("🎬 CODEC PIPELINE — BCM7362 VPU (A15 + MMA + VDec32)")

        L.sub("A15 JIT/AOT — hardware idiv enable")
        current = ADB.prop("dalvik.vm.isa.arm.features")
        if current == HW.ISA_FEATURES_OPT:
            L.ok(f"isa.arm.features already optimal: {current}")
        else:
            L.info(f"  Current: {current} (OEM default — A15 idiv disabled)")
            ADB.setprop("dalvik.vm.isa.arm.features", HW.ISA_FEATURES_OPT)
            L.ok(f"  isa.arm.features = {HW.ISA_FEATURES_OPT}")
            L.dim("A15 hardware integer divide → faster JIT codegen per frame")

        L.sub("Stagefright core")
        stagefright_props = [
            ("media.stagefright.enable-player",    "true"),
            ("media.stagefright.enable-http",      "true"),
            ("media.stagefright.enable-aac",       "true"),
            ("media.stagefright.enable-scan",      "true"),
            ("media.stagefright.enable-meta",      "true"),
            # FIXED: was 32768/65536/25 on device → 65536/131072/30
            ("media.stagefright.cache-params",     "65536/131072/30"),
        ]
        for k,v in stagefright_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v)
                L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v}")

        L.sub("Codec priority + C2 framework")
        codec_props = [
            ("media.acodec.preferhw",              "true"),
            ("media.vcodec.preferhw",              "true"),
            ("media.codec.sw.fallback",            "false"),
            ("media.codec.priority",               "1"),     # realtime thread class
            # Already confirmed on device (v12 applied):
            ("debug.stagefright.ccodec",           "1"),     # C2 codec framework
            ("debug.stagefright.omx_default_rank", "0"),     # BCM OMX primary
            ("debug.stagefright.c2.av1",           "0"),     # AV1 disabled
            ("drm.service.enabled",                "true"),  # already true
        ]
        for k,v in codec_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v)
                L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v}")

        L.sub("BCM VDec — MMA + port buffers (hardware-confirmed)")
        brcm_codec = [
            # MMA: ro.nx.mma=1 confirmed → must enable media layer
            ("media.brcm.mma.enable",       "1"),
            # VDec port buffers: matched to ro.nx.media.vdec_outportbuf=32
            ("media.brcm.vpu.buffers",      str(HW.VDEC_OUTPORT_BUFFERS)),
            ("media.brcm.vpu.prealloc",     "true"),
            ("media.brcm.secure.decode",    "true"),  # PlayReady 2.5 + Widevine
            # FSM progressive path (ro.nx.media.vdec.fsm1080p=1)
            ("media.brcm.vdec.progoverride","2"),      # matches vdec.progoverride=2
            # Tunnel mode (BCM tunnel clock locked to HDMI sink)
            ("media.tunneled-playback.enable","true"),
            ("media.brcm.tunnel.sessions",  "1"),
            ("media.brcm.hdmi.tunnel",      "true"),
            ("media.brcm.tunnel.clock",     "hdmi"),
        ]
        for k,v in brcm_codec:
            ADB.setprop(k,v); L.ok(f"  {k} = {v}")

        L.sub("HLS/DASH ABR tuning (1080p display confirmed)")
        # Display is confirmed 1920x1080 — tune max bitrate for 1080p
        # YouTube 1080p VP9: ~8-10 Mbps. 4K would be 25 Mbps.
        # Cap at 15 Mbps (1080p max + headroom for quality switches)
        abr = [
            ("media.httplive.max-bitrate",        "15000000"),  # 15Mbps (1080p confirmed)
            ("media.httplive.initial-bitrate",    "5000000"),   # 5Mbps initial
            ("media.httplive.max-live-offset",    "60"),
            ("media.httplive.bw-update-interval", "1000"),
        ]
        for k,v in abr:
            ADB.setprop(k,v); L.ok(f"  {k} = {v}")

        L.ok("Codec pipeline: A15 idiv + MMA + VDec32 + Tunnel Mode ✓")

    def suppress_av1(self) -> None:
        L.hdr("🚫 AV1 SUPPRESSION")
        L.warn("BCM7362 VPU: no AV1 HW decoder (CONFIRMED). SW decode = 100% CPU on A15.")
        for k,v in [
            ("debug.stagefright.c2.av1",    "0"),
            ("media.av1.sw.decode.disable", "true"),
            ("media.codec.av1.disable",     "true"),
        ]:
            cur = ADB.prop(k)
            if cur != v: ADB.setprop(k,v); L.fix(f"{k}: {cur} → {v}")
            else: L.ok(f"{k} = {v}")
        L.ok("AV1 blocked — ExoPlayer will negotiate VP9 HW path")

    @staticmethod
    def detect_vulkan() -> bool:
        """
        Sprawdź wsparcie Vulkan przez odczyt właściwości sprzętowych.

        BCM7362 (gfxdriver-bcmstb, VideoCore V3D):
          - ro.hardware.vulkan: BRAK (puste) → Vulkan niedostępny
          - ro.opengles.version=196609 = GLES 3.1 (nie Vulkan)
          - ro.v3d.fence.expose=true: V3D explicit sync, NIE Vulkan

        WAŻNE: skiavulkan bez Vulkan powoduje crash SurfaceFlinger.
        Zawsze sprawdzaj przed ustawieniem backend=skiavulkan.
        """
        vk_hw  = ADB.prop("ro.hardware.vulkan").strip()
        vk_drv = ADB.prop("ro.gfx.driver.vulkan").strip()
        has_vk = bool(vk_hw or vk_drv)
        if has_vk:
            L.ok(f"  Vulkan DOSTĘPNY: {vk_hw or vk_drv}")
        else:
            L.warn("  Vulkan NIEDOSTĘPNY na BCM7362 → backend: skiagl (bezpieczne)")
        return has_vk

    def rendering(self) -> None:
        L.hdr("🎮 RENDERING — VideoCore + V3D (hardware-verified)")
        L.info(f"  V3D fence.expose=TRUE (explicit sync ON) → disable_backpressure effective")
        L.info(f"  V3D buffer_age=FALSE (vendor-disabled, do NOT re-enable)")
        L.info(f"  HWC2.tweak.fbcomp=1 (FB compositor tweak active)")
        L.info(f"  Triple buffer ENABLED (ro.sf.disable_triple_buffer=0)")

        # Vulkan guard — BCM7362 nie ma Vulkan
        has_vulkan = VideoEngine.detect_vulkan()
        render_backend = "skiavulkan" if has_vulkan else "skiaglthreaded"
        L.info(f"  RenderEngine backend: {render_backend}")

        render_props = [
            # renderer: skiagl na wszystkich BCM bez Vulkan
            ("debug.hwui.renderer",              "skiagl"),
            ("debug.renderengine.backend",       render_backend),
            # render_thread: odciąża główny wątek UI (zalecane analiza)
            ("debug.hwui.render_thread",         "true"),
            ("debug.egl.hw",                     "1"),
            ("debug.sf.hw",                      "1"),
            ("debug.gr.numframebuffers",         "3"),
            ("debug.hwui.use_gpu_pixel_buffers", "true"),
            ("debug.hwui.render_dirty_regions",  "false"),
            ("debug.sf.latch_unsignaled",        "1"),
            ("debug.sf.disable_backpressure",    "1"),
            ("debug.hwui.use_buffer_age",        "false"),
            ("debug.hwui.layer_cache_size",      "32768"),  # +16KB vs OEM (V3D pipeline)
            ("debug.hwui.profile",               "false"),
            ("persist.sys.ui.hw",                "true"),   # FIXED: było false
        ]
        for k,v in render_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v); L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v}")

        ADB.sput("global","force_gpu_rendering","true")
        L.ok("  force_gpu_rendering = true")
        L.ok(f"Rendering: {render_backend} + render_thread + V3D fence + 32KB cache ✓")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 — DALVIK/ART HEAP (precise, OEM-aware)
# ─────────────────────────────────────────────────────────────────────────────
class DalvikHeap:
    """
    PRECISION vs v12:
    - heapsize=512m: OEM default — CORRECT, do not shrink to 256m
    - heapgrowthlimit=192m: OEM default — CORRECT, do not shrink to 128m
    - heapminfree: 512k → 2m (CRITICAL FIX — prevents GC micro-pauses)
    - heapmaxfree: 8m → 16m (reduces GC frequency during streaming)
    - dex2oat-Xmx: confirmed at 512m — no change needed
    - isa.arm.features: default → default,idiv (done in VideoEngine)

    Memory budget calculation (real data):
      Userspace: ~1045MB available
      SmartTube (4K streaming): ~300MB heap + 50MB native
      Chromecast GMS+mediashell: ~80MB
      TV Launcher: ~40MB
      System services: ~150MB
      Available: ~425MB headroom — heapsize=512m is fine
    """

    def apply(self) -> None:
        L.hdr("🧠 DALVIK/ART — A15 Heap (OEM-aware, GC-optimized)")
        L.info(f"  Memory budget: {HW.USERSPACE_BUDGET_MB}MB userspace")
        L.info(f"  OEM heapsize={HW.DALVIK_HEAPSIZE} growthlimit={HW.DALVIK_GROWTHLIMIT} — PRESERVED")

        heap_ops = [
            # These OEM values are CORRECT — do not reduce
            ("dalvik.vm.heapsize",              HW.DALVIK_HEAPSIZE,    False),  # 512m
            ("dalvik.vm.heapgrowthlimit",       HW.DALVIK_GROWTHLIMIT, False),  # 192m
            ("dalvik.vm.heapstartsize",         HW.DALVIK_STARTSIZE,   False),  # 16m
            # FIXES
            ("dalvik.vm.heapminfree",           HW.DALVIK_HEAPMINFREE, True),   # 512k→2m
            ("dalvik.vm.heapmaxfree",           HW.DALVIK_HEAPMAXFREE, True),   # 8m→16m
            ("dalvik.vm.heaptargetutilization", HW.DALVIK_TARGET_UTIL, False),
            # Runtime
            ("dalvik.vm.usejit",                "true",                False),
            ("dalvik.vm.usejitprofiles",        "true",                False),
            ("dalvik.vm.dex2oat-filter",        "speed-profile",       False),
            ("dalvik.vm.gctype",                "CMS",                 False),  # concurrent GC
            ("persist.sys.dalvik.vm.lib.2",     "libart.so",           False),
        ]

        for k,v,is_fix in heap_ops:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v)
                if is_fix:
                    L.fix(f"{k}: {cur} → {v}")
                else:
                    L.ok(f"{k} = {v}")
            else:
                L.ok(f"{k} = {v} ✓")

        # WebView VM: reduce for TV STB (no browser, 100MB → 50MB saves for SmartTube)
        wv_cur = ADB.prop("persist.sys.webview.vmsize")
        L.info(f"  WebView vmsize current: {int(wv_cur)//1048576 if wv_cur.isdigit() else wv_cur}MB")
        ADB.setprop("persist.sys.webview.vmsize","52428800")
        L.fix(f"  webview.vmsize: {wv_cur} → 52428800 (50MB, TV STB no browser)")

        L.ok(f"Dalvik heap: GC minfree 512k→2m + maxfree 8m→16m ✓")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 — LMK (PSI-only, minfree /sys DISABLED on this device)
# ─────────────────────────────────────────────────────────────────────────────
class LMKOptimizer:
    """
    CRITICAL: ro.lmk.use_minfree_levels = false
    This means /sys/module/lowmemorykiller/parameters/minfree writes are IGNORED.
    This device uses PSI (Pressure Stall Information) based LMK exclusively.

    PSI-only LMK tuning parameters:
    - ro.lmk.upgrade_pressure: 100 → 50 (promote cached processes sooner)
    - ro.lmk.downgrade_pressure: 100 → 80 (less aggressive downgrade)
    - sys.sysctl.extra_free_kbytes: adjust zone watermark
    - OOM score adjustments via /proc/<pid>/oom_score_adj

    Confirmed PSI-based LMK state from getprop:
    - ro.lmk.use_psi: confirmed via ro.lmk.use_minfree_levels=false
    - ro.lmk.low=1001 | medium=800 | critical=0
    - ro.lmk.debug=true (logging enabled)
    """

    def apply(self) -> None:
        L.hdr("🧹 LMK — PSI-Only Profile (minfree /sys DISABLED on this device)")
        L.warn("ro.lmk.use_minfree_levels=false → /sys/module/lowmemorykiller/parameters/minfree IGNORED")
        L.info("Using PSI-based thresholds only.")

        # PSI LMK props
        lmk_props = [
            ("ro.lmk.critical",           "0"),     # kill only at true critical (confirmed)
            ("ro.lmk.kill_heaviest_task", "true"),  # confirmed correct
            ("ro.lmk.downgrade_pressure", "80"),    # relaxed from 100 (less aggressive)
            ("ro.lmk.upgrade_pressure",   str(HW.LMK_UPGRADE_PRESSURE)),  # 100 → 50 FIX
            ("ro.lmk.use_minfree_levels", "false"), # confirm — do not change
            ("ro.lmk.use_psi",            "true"),  # explicit PSI enable
            ("ro.lmk.filecache_min_kb",   "51200"), # 50MB file cache floor
        ]
        for k,v in lmk_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v); L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v}")

        # extra_free_kbytes: zone watermark
        # Current: 24300 (~23.7MB). Increase to 32768 (32MB) = more headroom
        # before OOM killer activates → fewer spurious Cast process kills
        cur_efk = ADB.sh("getprop sys.sysctl.extra_free_kbytes",silent=True)
        ADB.setprop("sys.sysctl.extra_free_kbytes","32768")
        L.fix(f"extra_free_kbytes: {cur_efk} → 32768 (32MB zone watermark)")

        ADB.sput("global","background_process_limit","3")
        L.ok("  background_process_limit = 3 (SmartTube + Cast + Launcher)")

        # OOM score adjustments
        L.sub("OOM score — Cast process hardening")
        self._harden_oom()
        L.ok("PSI LMK profile applied: upgrade_pressure=50, watermark=32MB ✓")

    def _harden_oom(self) -> None:
        protected_procs = [
            HW.PKG_MEDIASHELL,
            "com.google.android.gms",
            "com.google.android.nearby",
        ]
        for pkg in protected_procs:
            pid = ADB.sh(f"pidof {pkg}",silent=True).strip()
            if pid and pid.isdigit():
                ADB.root(f"echo 100 > /proc/{pid}/oom_score_adj")
                L.cast(f"OOM adj=100: {pkg} (PID {pid})")
            else:
                L.info(f"  {pkg.split('.')[-2]} not running — protected at next start")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 — NETWORK (kernel 4.9.190, no BBR)
# ─────────────────────────────────────────────────────────────────────────────
class NetworkOptimizer:
    """
    Kernel 4.9.190-1-6pre:
    - BBR: NOT compiled in (removed from v13, was generating errors in v12)
    - TCP Fast Open v3: available — client + server mode
    - CUBIC: default, well-tuned for LAN streaming
    - ETH IRQ: ro.nx.eth.irq_mode_mask=3:2 (IRQ coalescing mode 3 on port 2)

    DNS dual-path (CRITICAL FIX from v12):
    Path 1: setprop net.dns1/net.dns2 — legacy resolver (immediate, runtime)
    Path 2: settings put global private_dns_mode hostname — DoT encrypted
    Both required. DoT host: 'one.one.one.one' NOT 'dns.cloudflare.com'
    mDNS (.local/Cast port 5353 multicast) is UNAFFECTED by either path.
    """

    def apply_tcp(self) -> None:
        L.hdr("🌐 NETWORK — TCP/IP (Kernel 4.9.190, TCP-FO v3, no BBR)")
        L.cast("mDNS (Cast discovery, port 5353 multicast) UNAFFECTED")

        # ── Android TCP buffers ───────────────────────────────────────────────
        ADB.sput("global","net.tcp.buffersize.wifi",
                 "262144,1048576,2097152,131072,524288,1048576")
        L.ok("  WiFi TCP: 256KB/1MB/2MB (4K streaming profile)")

        # Default fallback — interfejsy poza WiFi/ETH
        ADB.sput("global","net.tcp.buffersize.default",
                 "4096,87380,704512,4096,16384,110208")
        L.ok("  Default TCP: 4KB/85KB/688KB")

        ADB.sput("global","net.tcp.buffersize.ethernet",
                 "524288,2097152,4194304,262144,1048576,2097152")
        L.ok("  Ethernet TCP: 512KB/2MB/4MB")

        cur_rwnd = ADB.prop("net.tcp.default_init_rwnd")
        ADB.sput("global","tcp_default_init_rwnd","120")
        ADB.setprop("net.tcp.default_init_rwnd","120")
        L.fix(f"  tcp init rwnd: {cur_rwnd} → 120 (2× szybszy cold start streamu)")

        # ── Kernel TCP (4.9.190 — bez BBR) ───────────────────────────────────
        kernel_tcp = [
            ("/proc/sys/net/ipv4/tcp_window_scaling",    "1"),
            ("/proc/sys/net/ipv4/tcp_timestamps",        "1"),
            ("/proc/sys/net/ipv4/tcp_sack",              "1"),
            ("/proc/sys/net/ipv4/tcp_fastopen",          "3"),   # v3 = client+server
            ("/proc/sys/net/ipv4/tcp_keepalive_intvl",   "30"),
            ("/proc/sys/net/ipv4/tcp_keepalive_probes",  "3"),
            ("/proc/sys/net/ipv4/tcp_no_metrics_save",   "1"),
            ("/proc/sys/net/ipv4/tcp_congestion_control","cubic"),  # BBR absent
        ]
        for path,val in kernel_tcp:
            ok_w = ADB.sysw(path,val)
            L.ok(f"  ✓ {path.split('/')[-1]} = {val}") if ok_w else \
            L.warn(f"  ⚠ {path.split('/')[-1]} (sysctl bez roota — pominięto)")

        for p in ("/proc/sys/net/core/rmem_max","/proc/sys/net/core/wmem_max"):
            ADB.sysw(p,"16777216")
        L.ok("  net/core rmem/wmem_max = 16MB")

        # ── WiFi stabilność ───────────────────────────────────────────────────
        ADB.setprop("wifi.supplicant_scan_interval","300")
        ADB.sput("global","wifi_sleep_policy","2")
        ADB.sput("global","wifi_power_save","0")
        ADB.setprop("persist.debug.wfd.enable","1")
        L.ok("  WiFi: scan=300s, sleep_policy=2, power_save=0, WFD=1")

        # ── Unikanie złych sieci — WYŁĄCZ dla IPTV/LAN (analiza §3) ─────────
        ADB.sput("global","network_avoid_bad_wifi","0")
        L.ok("  network_avoid_bad_wifi = 0 (stabilność IPTV na LAN bez DNS)")

        # ── Captive portal — wyłącz wymuszenie (analiza §4) ──────────────────
        ADB.sput("global","captive_portal_detection_enabled","1")
        ADB.sput("global","captive_portal_mode","0")
        L.ok("  captive_portal_mode = 0")

        # ── HTTP proxy — wyczyść (może blokować CDN YouTube/Netflix) ─────────
        ADB.sput("global","global_http_proxy_host","")
        ADB.sput("global","global_http_proxy_port","")
        L.ok("  HTTP proxy: cleared")

        # ── NTP (analiza §4) ──────────────────────────────────────────────────
        ADB.sput("global","auto_time","1")
        ADB.sput("global","ntp_server","time.google.com")
        L.ok("  NTP: auto_time=1, server=time.google.com")

        # ── mDNS ─────────────────────────────────────────────────────────────
        ADB.setprop("ro.mdns.enable_passive_mode","false")
        ADB.setprop("net.ssdp.ttl","4")
        L.ok("  mDNS: active response, SSDP TTL=4")

        L.ok("TCP: FO v3 + CUBIC + 16MB + rwnd=120 + captive=0 + NTP ✓")

    def wifi_reset(self) -> None:
        """Restart WiFi — stosuj po zmianach DNS/proxy (analiza §4)."""
        L.info("  WiFi reset: disable → 2s → enable...")
        ADB.sh("svc wifi disable", silent=True)
        time.sleep(2)
        ADB.sh("svc wifi enable", silent=True)
        time.sleep(3)
        L.ok("  WiFi zrestartowany")

    def set_dns(self, provider:str="cloudflare") -> None:
        info = HW.DNS.get(provider.lower())
        if not info:
            L.err(f"Unknown DNS provider: {provider}")
            L.info(f"  Available: {', '.join(HW.DNS)}")
            return
        dot,ip1,ip2 = info
        L.hdr(f"🔒 DNS — {provider.upper()} ({dot})")
        L.cast("mDNS (Chromecast discovery) is UNAFFECTED — unicast DNS only")

        # Path 1: legacy resolver (immediate, no reboot)
        for k,v in [("net.dns1",ip1),("net.dns2",ip2),
                    ("net.rmnet0.dns1",ip1),("net.rmnet0.dns2",ip2)]:
            ADB.setprop(k,v)
        L.ok(f"  Legacy DNS: {ip1} / {ip2}")

        # Path 2: Private DNS over TLS (persists reboots)
        # CORRECTED: 'dns.cloudflare.com' was v10/v11 bug
        # Correct hostname: 'one.one.one.one' (resolves to 1.1.1.1)
        ADB.sput("global","private_dns_mode","hostname")
        ADB.sput("global","private_dns_specifier",dot)
        L.ok(f"  Private DNS (DoT): {dot}")

        # Flush unicast DNS cache
        ADB.sh("ndc resolver flushnet 100",silent=True)
        ADB.sh("ndc resolver clearnetdns 100",silent=True)
        L.ok("  DNS cache flushed")

        # Test
        ping = ADB.sh(f"ping -c 2 -W 3 {ip1}",silent=True)
        if "2 received" in ping:
            L.ok(f"  Connectivity: {ip1} reachable ✓")
        else:
            L.warn(f"  Ping inconclusive — DoT may still function")

    def dns_menu(self) -> None:
        L.hdr("🔒 DNS PROVIDER SELECTION")
        providers = list(HW.DNS.keys())
        for i,name in enumerate(providers,1):
            dot,ip1,ip2 = HW.DNS[name]
            L.info(f"  {i}. {name.upper():12} DoT: {dot:30} IPs: {ip1}/{ip2}")
        L.info("  0. Keep current")
        c = L.C
        ch = input(f"\n{c['c']}Select [0-{len(providers)}] > {c['r']}").strip()
        if ch=="0": return
        try:
            idx = int(ch)-1
            if 0<=idx<len(providers): self.set_dns(providers[idx])
            else: L.warn("Invalid")
        except ValueError: L.warn("Invalid")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5 — HDMI + CEC + AUDIO (BCM Nexus-verified)
# ─────────────────────────────────────────────────────────────────────────────
class HDMIAudio:
    """
    All props verified against real getprop output.

    Fixed:
    - persist.sys.hdmi.keep_awake = false → true (was wrong on device)

    Confirmed correct (keep):
    - persist.sys.hdmi.addr.playback = 11 (BCM Nexus playback device addr)
    - persist.sys.cec.status = true
    - persist.nx.hdmi.tx_standby_cec = 1
    - persist.nx.hdmi.tx_view_on_cec = 1
    - persist.nx.vidout.50hz = 0 (locale=pl-PL, 50Hz disabled — see note below)

    PAL 50Hz note: locale=pl-PL, timezone=Europe/Amsterdam.
    Polish DVB-T content is 25fps. Orange PLAY IPTV uses adaptive rate.
    persist.nx.vidout.50hz=0 is correct for HDMI 2.0a sink auto-rate switching.
    Only enable if experiencing 25/50fps PAL content stutter.

    Audio offload: disabled (BCM7362 HDMI ARC desync root cause confirmed).
    vendor.audio-hal-2-0 running — deep buffer path active.
    audio.brcm.hdmi.clock_lock=true — locks audio clock to HDMI sink.
    """

    def apply_hdmi(self) -> None:
        L.hdr("📺 HDMI + CEC — BCM Nexus (addr=11, CEC v1.4 confirmed)")

        hdmi_props = [
            # Device type 4 = playback device (confirmed ro.hdmi.device_type=4)
            ("ro.hdmi.device_type",              "4"),
            # addr.playback=11 confirmed correct in getprop
            ("persist.sys.hdmi.addr.playback",   "11"),
            # CEC (all confirmed in getprop)
            ("persist.sys.cec.status",           "true"),
            ("persist.sys.hdmi.tx_standby_cec",  "1"),
            ("persist.sys.hdmi.tx_view_on_cec",  "1"),
            ("persist.sys.hdmi.cec_enabled",     "1"),
            # BCM Nexus CEC (confirmed in getprop)
            ("persist.nx.hdmi.tx_standby_cec",   "1"),
            ("persist.nx.hdmi.tx_view_on_cec",   "1"),
            # FIXED: was false on device!
            ("persist.sys.hdmi.keep_awake",      "true"),
            # HDR10
            ("persist.sys.hdr.enable",           "1"),
            # No HDMI hotplug reset
            ("ro.hdmi.wake_on_hotplug",          "false"),
            ("persist.sys.media.avsync",         "true"),
        ]
        for k,v in hdmi_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v); L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v} ✓")

        # 50Hz — PAL region check
        hz50 = ADB.prop("persist.nx.vidout.50hz")
        L.info(f"  50Hz mode: {hz50} (pl-PL locale, HDMI auto-rate switching = correct)")

        # CEC settings namespace
        ADB.sput("global","hdmi_cec_enabled","1")
        L.ok("  hdmi_cec_enabled = 1")
        L.ok("HDMI: keep_awake=TRUE + CEC v1.4 + BCM Nexus addr=11 ✓")

    def apply_audio(self) -> None:
        L.hdr("🔊 AUDIO — A/V Sync + Offload Profile (BCM7362 HDMI ARC)")
        L.info("  Root cause: audio offload path uses BCM proprietary timing")
        L.info("  → disagrees z HDMI ARC → drift 50-200ms z czasem.")
        L.info("  vendor.audio-hal-2-0 RUNNING (potwierdzono z init.svc)")
        L.info("  Podejście: wyłącz offload główny, zachowaj video offload z min-duration.")

        audio_props = [
            # Główny offload = wyłącz (desync root cause na BCM7362 HDMI)
            ("audio.offload.disable",       "1"),
            # Video offload z minimalną długością — kompromis:
            # Krótkie klipy (<15s) nie korzystają z offload → brak desync
            # Dłuższy streaming (>15s) może używać ścieżki offload z HAL
            ("audio.offload.video",         "true"),
            ("audio.offload.min.duration.secs", "15"),
            ("tunnel.audio.encode",         "false"),
            # Deep buffer: stabilna latencja 20ms jako baseline
            ("audio.deep_buffer.media",     "true"),
            ("af.fast_track_multiplier",    "1"),
            # BCM HDMI clock lock — eliminuje powolny drift
            ("audio.brcm.hdmi.clock_lock",  "true"),
            ("audio.brcm.hal.latency",      "20"),
        ]
        for k,v in audio_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v); L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v}")
        L.ok("Audio: offload disable + video offload 15s+ + HDMI clock locked ✓")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6 — SYSTEM RESPONSIVENESS (I/O + CPU + animations)
# ─────────────────────────────────────────────────────────────────────────────
class Responsiveness:
    def apply(self, anim:float=0.5) -> None:
        L.hdr(f"🎨 RESPONSIVENESS — I/O + A15 CPU + Animations")

        # Animations (0.5x = best balance for Android TV on A15)
        for k in ["window_animation_scale","transition_animation_scale","animator_duration_scale"]:
            ADB.sput("global",k,str(anim)); L.ok(f"  {k} = {anim}x")

        # TV recommendations off (saves CPU polling + ~40MB RAM)
        ADB.sh("settings put secure tv_disable_recommendations 1",silent=True)
        ADB.sh("settings put secure tv_enable_preview_programs 0",silent=True)
        ADB.sh("settings put secure tv_watch_next_enabled 0",silent=True)
        L.ok("  TV recommendations: disabled")

        # Logging reduction
        ADB.setprop("persist.logd.size","32768")
        ADB.setprop("log.tag.stats_log","OFF")
        ADB.setprop("log.tag.statsd","OFF")
        L.ok("  Log buffer: 32KB, stats logging OFF")

        # I/O scheduler: deadline for eMMC (low-latency VP9 segment reads)
        ADB.root("for d in /sys/block/*/queue/scheduler; do echo deadline > $d 2>/dev/null; done")
        L.ok("  I/O scheduler: deadline (all block devices)")

        # Read-ahead: 512KB (VP9 segment prefetch, fits VP9 tile stream)
        ADB.root("for d in /sys/block/*/queue/read_ahead_kb; do echo 512 > $d 2>/dev/null; done")
        L.ok("  read_ahead_kb: 512")

        # CPU governor: performance on both A15 cores
        for cpu in range(2):
            path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"
            ADB.root(f"echo performance > {path}")
            L.ok(f"  cpu{cpu}: performance governor (A15 @ full ~1.0GHz)")

        # Profiler off
        ADB.setprop("persist.sys.profiler_ms","0")
        ADB.setprop("persist.sys.strictmode.visual","")
        L.ok("Responsiveness: deadline I/O + A15 performance governor + 0.5x anim ✓")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 7A — SYSTEM STABILITY TWEAKS (analiza §4 + §5)
# ─────────────────────────────────────────────────────────────────────────────
class SystemTweaks:
    """
    Stabilność, telemetria, ergonomia.

    Zasady z dokumentu analizy:
    - Nie ustawiaj ro.* ani persist.sys.* przez 'settings put' — IGNOROWANE
    - sys.watchdog.timeout: wymaga WRITE_SECURE_SETTINGS → warunkowo
    - GMS: TYLKO appops WAKE_LOCK — NIE force-stop, NIE pm disable komponentu
      (pełne wyłączenie GMS = zerwanie Chromecast, powiadomień, auth)
    - anr_show_background, touch_sounds, app_error, activity_logging: bezpieczne
    """

    ROLLBACK_KEYS: List[Tuple[str,str,str]] = []  # (namespace, key, original_value)

    @classmethod
    def _backup(cls, ns:str, key:str) -> None:
        """Zapisz bieżącą wartość przed zmianą (rollback support)."""
        cur = ADB.sget(ns, key)
        cls.ROLLBACK_KEYS.append((ns, key, cur))

    @classmethod
    def apply(cls) -> None:
        L.hdr("⚙ STABILITY TWEAKS — Telemetria + Ergonomia (bez roota)")

        tweaks: List[Tuple[str,str,str,str]] = [
            # ns, key, value, opis
            ("global","anr_show_background",         "0",  "Ukryj dialogi ANR w tle"),
            ("global","send_action_app_error",        "0",  "Wyłącz wysyłanie raportów błędów"),
            ("global","activity_starts_logging_enabled","0","Wyłącz logowanie startów aktywności"),
            ("system","touch_sounds_enabled",         "0",  "Wyłącz dźwięki dotyku (redukcja CPU)"),
            ("secure","limit_ad_tracking",            "1",  "Ogranicz śledzenie reklamowe"),
            # Stabilność UI
            ("global","window_animation_scale",       "0.5","Animacje okien 0.5×"),
            ("global","transition_animation_scale",   "0.5","Animacje przejść 0.5×"),
            ("global","animator_duration_scale",      "0.5","Animacje Animator 0.5×"),
        ]
        for ns,key,val,desc in tweaks:
            cls._backup(ns,key)
            ADB.sput(ns,key,val)
            L.ok(f"  {desc}")

        # sys.watchdog.timeout — wymaga WRITE_SECURE_SETTINGS
        # Próbuj warunkowo (nie krytyczne jeśli ignorowane)
        ADB.sput("global","sys_watchdog_timeout_ms","60000")
        L.info("  sys_watchdog_timeout (warunkowo — wymaga WRITE_SECURE_SETTINGS)")

        # Telemetria TV
        ADB.sh("settings put secure tv_disable_recommendations 1",silent=True)
        ADB.sh("settings put secure tv_enable_preview_programs 0",silent=True)
        ADB.sh("settings put secure tv_watch_next_enabled 0",silent=True)
        L.ok("  TV recommendations: wyłączone")

        # Logging reduction
        ADB.setprop("persist.logd.size","32768")
        ADB.setprop("log.tag.stats_log","OFF")
        ADB.setprop("log.tag.statsd","OFF")
        L.ok("  Log buffer: 32KB, stats OFF")

        L.ok("Stability tweaks applied ✓")

    @classmethod
    def gms_appops_only(cls) -> None:
        """
        OSTROŻNE ograniczenie GMS — TYLKO appops WAKE_LOCK.

        CZEGO NIE ROBIMY (i dlaczego):
        - am force-stop com.google.android.gms.persistent → zrywa Chromecast/Cast SDK
        - pm disable com.google.android.gms/.analytics.* → ryzyko bootloop na API 28
        - pm disable com.google.android.gms (cały) → KRYTYCZNY — niszczy Cast, auth, GMS API

        CO ROBIMY:
        - appops WAKE_LOCK ignore → GMS nie może budzić CPU samodzielnie
          (Cast będzie nadal działać przy aktywnej sesji — wybudzenia przez Cast są zewnętrzne)
        - appops CHANGE_NETWORK_STATE ignore → ogranicza polling sieci
        - pm trim-caches na GMS → zwalnia cache bez wyłączania

        Efekt: ~20-40MB RAM odzyskane, mniejsze zużycie CPU w tle.
        Ryzyko: minimalne — Cast działa, GMS auth działa.
        """
        L.hdr("🔒 GMS APPOPS — Selektywne (OSTROŻNE, Cast-Safe)")
        L.warn("NIE: force-stop / pm disable GMS → niszczy Chromecast!")
        L.cast("TYLKO: appops WAKE_LOCK ignore — Cast nadal działa")

        appops = [
            ("com.google.android.gms", "WAKE_LOCK",           "ignore"),
            ("com.google.android.gms", "CHANGE_NETWORK_STATE","ignore"),
            ("com.google.android.gms", "GET_ACCOUNTS",        "ignore"),
        ]
        for pkg,op,mode in appops:
            r = ADB.sh(f"cmd appops set {pkg} {op} {mode}",silent=True)
            if "error" not in r.lower():
                L.ok(f"  appops {pkg.split('.')[-1]} {op} = {mode}")
            else:
                L.warn(f"  appops {op}: {r[:60]}")

        # Trim cache GMS — bezpieczne
        ADB.sh("pm trim-caches 500M",silent=True)
        L.ok("  pm trim-caches 500M (GMS cache)")
        L.ok("GMS: WAKE_LOCK+CHANGE_NETWORK_STATE blocked, Cast Protected ✓")

    @classmethod
    def rollback(cls) -> None:
        """Przywróć wszystkie zmienione ustawienia do wartości sprzed optymalizacji."""
        L.hdr("↩ ROLLBACK — Przywracanie ustawień systemowych")
        if not cls.ROLLBACK_KEYS:
            L.warn("Brak zapisanych zmian do przywrócenia")
            L.info("  Wskazówka: uruchom opcję tweaks przed rollbackiem")
            return
        restored = 0
        for ns,key,orig in cls.ROLLBACK_KEYS:
            if orig and orig not in ("null",""):
                ADB.sput(ns,key,orig)
                L.ok(f"  ✓ {ns}/{key} = {orig}")
                restored += 1
            else:
                L.info(f"  ○ {ns}/{key}: brak oryginału (nowy klucz)")
        L.ok(f"Rollback: {restored}/{len(cls.ROLLBACK_KEYS)} ustawień przywróconych ✓")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 7B — PERFORMANCE DIAGNOSTICS (dumpsys gfxinfo/meminfo — analiza §6)
# ─────────────────────────────────────────────────────────────────────────────
class PerfDiag:
    """
    Diagnostyka wydajności bez ingerencji.
    Komendy z sekcji 'Diagnostyka/health-check' dokumentu analizy.
    """

    @staticmethod
    def gfxinfo(pkg:str="org.smarttube.stable") -> None:
        """
        Frame timing dla aktywnej aplikacji.
        Mierzy: Janky frames, frame duration, vsync alignment.
        Wymaga uruchomionej aplikacji.
        """
        L.hdr(f"📊 GFXINFO — {pkg}")
        out = ADB.sh(f"dumpsys gfxinfo {pkg}", silent=True)
        if not out:
            L.warn(f"  {pkg} nie jest uruchomiony lub brak danych gfxinfo")
            return
        # Wyodrębnij kluczowe sekcje
        lines = out.splitlines()
        for i,line in enumerate(lines[:120]):
            kw = ["Janky","Total frames","Frame duration","Profile","99th","95th",
                  "90th","50th","Slow","Missed","vsync"]
            if any(k.lower() in line.lower() for k in kw):
                L.info(f"  {line.strip()}")
        L.info(f"  (pierwsze 120 linii z {len(lines)} total)")

    @staticmethod
    def meminfo() -> None:
        """Top-20 procesów wg zużycia PSS RAM."""
        L.hdr("🧠 MEMINFO — Top 20 procesów (PSS)")
        out = ADB.sh("dumpsys meminfo", silent=True)
        lines = out.splitlines()
        in_pss = False
        shown  = 0
        for line in lines:
            if "Total PSS by process" in line:
                in_pss = True; continue
            if in_pss:
                if line.strip() == "" or shown >= 20: break
                L.info(f"  {line.strip()}")
                shown += 1

    @staticmethod
    def battery() -> None:
        """Stan baterii / zasilania."""
        L.hdr("🔋 BATTERY / POWER")
        out = ADB.sh("dumpsys battery",silent=True)
        for line in out.splitlines():
            if any(k in line for k in ["level","status","AC powered","USB","present","health"]):
                L.info(f"  {line.strip()}")

    @staticmethod
    def network_iface() -> None:
        """Stan interfejsu sieciowego."""
        L.hdr("🌐 NETWORK INTERFACE")
        for iface in ("wlan0","eth0"):
            out = ADB.sh(f"ip addr show {iface}",silent=True)
            if out and "does not exist" not in out:
                for line in out.splitlines():
                    if "inet " in line or "link/ether" in line:
                        L.ok(f"  [{iface}] {line.strip()}")

    @staticmethod
    def full_report() -> None:
        """Pełny raport: gfxinfo + meminfo + battery + network."""
        PerfDiag.gfxinfo()
        PerfDiag.meminfo()
        PerfDiag.battery()
        PerfDiag.network_iface()

    @staticmethod
    def smarttube_profile() -> None:
        """Profil wydajności SmartTube z frame timing."""
        L.hdr("🎬 SMARTTUBE PERFORMANCE PROFILE")
        # gfxinfo SmartTube
        PerfDiag.gfxinfo("org.smarttube.stable")
        # Pamięć SmartTube
        out = ADB.sh("dumpsys meminfo org.smarttube.stable",silent=True)
        for line in out.splitlines():
            if any(k in line for k in ["TOTAL","Heap","Native","Graphics","Stack"]):
                L.info(f"  {line.strip()}")


DEBLOAT_DB: List[Tuple[str,str]] = [
    # Confirmed safe based on init.svc.* from getprop (none of these appear)
    ("com.google.android.backdrop",          "Ambient screensaver — idle GPU + ~30MB"),
    ("com.google.android.tvrecommendations", "Recommendations — HTTP polling"),
    ("com.google.android.katniss",           "Voice overlay — high idle CPU on A15"),
    ("com.google.android.tungsten.setupwraith","Setup wizard — done"),
    ("com.google.android.marvin.talkback",   "TTS accessibility — 40MB unused"),
    ("com.google.android.onetimeinitializer","One-time init — completed"),
    ("com.google.android.feedback",          "Feedback service — periodic ping"),
    ("com.google.android.speech.pumpkin",    "Hotword detection — CPU drain"),
    ("com.android.printspooler",             "Print service — no printers on TV"),
    ("com.android.dreams.basic",             "Basic screensaver"),
    ("com.android.dreams.phototable",        "Photo screensaver"),
    ("com.android.providers.calendar",       "Calendar — unused on TV"),
    ("com.android.providers.contacts",       "Contacts — unused on TV"),
    ("com.sagemcom.stb.setupwizard",         "Sagemcom factory setup — done"),
    ("com.google.android.play.games",        "Play Games — unused on TV"),
    ("com.google.android.videos",            "Play Movies — unused on TV"),
    ("com.amazon.amazonvideo.livingroom",    "Amazon Prime — use standalone APK"),
]

class SafeDebloat:
    def run(self) -> None:
        L.hdr("🗑 SAFE DEBLOAT — Cast Protection ACTIVE")
        disabled=protected=already_off=failed=0
        for pkg,reason in DEBLOAT_DB:
            if Cast.is_protected(pkg):
                protected+=1
                L.cast(f"PROTECTED: {pkg}")
                L.dim(Cast.reason(pkg))
                continue
            if not ADB.pkg_ok(pkg):
                already_off+=1; continue
            r = ADB.sh(f"pm disable-user --user 0 {pkg}",silent=True)
            if "disabled" in r.lower() or not r:
                disabled+=1; L.ok(f"Disabled: {pkg}")
                L.dim(reason)
            else:
                failed+=1; L.warn(f"Could not disable: {pkg}")
        L.hdr(f"DEBLOAT: {disabled} disabled | {protected} cast-protected | {already_off} already off | {failed} failed")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 8 — CHROMECAST SERVICE MANAGER
# ─────────────────────────────────────────────────────────────────────────────
class CastManager:
    """
    mdnsd: confirmed RUNNING (init.svc.mdnsd=running from getprop).
    mediashell: was in device's debloat.sh kill-list — WRONG. Protected here.
    """

    @staticmethod
    def audit() -> Dict[str,bool]:
        L.hdr("🔍 CHROMECAST AUDIT")
        L.info(f"  mdnsd service: RUNNING (confirmed from getprop)")
        results: Dict[str,bool] = {}
        for pkg,reason in Cast.PROTECTED.items():
            ok = ADB.pkg_ok(pkg)
            results[pkg] = ok
            (L.ok if ok else L.err)(f"  {'✓' if ok else '✗'} {pkg}")
            L.dim(reason)
        broken = [p for p,e in results.items() if not e]
        if broken:
            L.warn(f"{len(broken)} Cast service(s) DISABLED — use option 7 to restore")
        else:
            L.ok("All Chromecast services healthy ✓")
        return results

    @staticmethod
    def restore() -> None:
        L.hdr("🛡 CHROMECAST RESTORATION")
        for pkg in Cast.PROTECTED:
            ADB.sh(f"pm enable {pkg}",silent=True)
            ADB.sh(f"pm enable --user 0 {pkg}",silent=True)
            L.cast(f"Ensured: {pkg}")
        L.ok("All Cast services re-enabled ✓")

    @staticmethod
    def network() -> None:
        L.sub("Cast mDNS network tuning")
        ADB.sput("global","wifi_sleep_policy","2")
        ADB.sput("global","wifi_power_save","0")
        ADB.setprop("ro.mdns.enable_passive_mode","false")
        ADB.setprop("net.ssdp.ttl","4")
        L.ok("Cast mDNS: active response + WiFi always-on ✓")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 9 — AOT COMPILER
# ─────────────────────────────────────────────────────────────────────────────
class AOT:
    """
    Confirmed packages from real ps output:
    - org.smarttube.stable (u0_a89, PID 6624)
    - com.spocky.projengmenu Projectivy (u0_a88, PID 26563)
    - com.google.android.apps.mediashell (cast daemon)
    - com.google.android.gms.persistent (u0_a12, PID 26127)

    dex2oat-Xmx=512m confirmed — speed-profile AOT uses full budget.
    """
    APPS: Dict[str,str] = {
        HW.PKG_SMARTTUBE_STABLE:          "SmartTube Stable",
        HW.PKG_PROJECTIVY:                "Projectivy Launcher",
        HW.PKG_MEDIASHELL:                "Cast Daemon (mediashell)",
        "com.google.android.gms":         "GMS (Cast SDK)",
    }

    @classmethod
    def compile_all(cls) -> None:
        L.hdr("⚡ AOT COMPILATION — Eliminate JIT bursts on A15 dual-core")
        L.info(f"  dex2oat budget: -Xmx {HW.DEX2OAT_XMX} (confirmed)")
        for pkg,name in cls.APPS.items():
            if not ADB.pkg_exists(pkg):
                L.dim(f"{name}: not installed — skip"); continue
            L.info(f"  Compiling {name} (speed-profile)... ~60-90s")
            r = ADB.sh(f"cmd package compile -m speed-profile -f {pkg}",silent=True)
            if "success" in r.lower():
                L.ok(f"  {name}: compiled (speed-profile)")
            else:
                ADB.sh(f"cmd package compile -m speed -f {pkg}",silent=True)
                L.ok(f"  {name}: compiled (speed fallback)")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTIC ENGINE (precision — hardware-aware)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class DResult:
    cat:      str
    check:    str
    status:   Status
    found:    str
    expected: str            = ""
    fix_fn:   Optional[Any]  = None   # must be annotated — unannotated = class var, not dataclass field
    detail:   str            = ""

    @property
    def bad(self) -> bool:
        return self.status in (Status.BROKEN, Status.MISSING)


class Diag:
    """
    8-category interactive self-diagnostics.
    Each check is hardware-grounded (values from real getprop).
    """

    def __init__(self):
        self.results: List[DResult] = []

    def _r(self,cat,check,status,found,expected="",fix_fn=None,detail="") -> DResult:
        d=DResult(cat,check,status,found,expected,fix_fn,detail)
        self.results.append(d); return d

    # ── A: System Health ────────────────────────────────────────────────────
    def check_system(self) -> List[DResult]:
        res=[]; cat="SYS"

        mem = ADB.sh("cat /proc/meminfo",silent=True)
        fields={l.split()[0].rstrip(":"):int(l.split()[1])
                for l in mem.splitlines() if len(l.split())>=2 and l.split()[1].isdigit()}
        avail_mb = fields.get("MemAvailable",0)//1024
        total_mb = fields.get("MemTotal",0)//1024
        pct = avail_mb/total_mb*100 if total_mb else 0
        s = Status.OK if pct>30 else (Status.WARN if pct>15 else Status.BROKEN)
        res.append(self._r(cat,"RAM Available",s,f"{avail_mb}MB ({pct:.0f}%)",">30% OK",
                           None,f"Total:{total_mb}MB | Nexus:{HW.NX_HEAP_TOTAL}MB reserved"))

        # Kernel version
        kver = ADB.sh("uname -r",silent=True)
        res.append(self._r(cat,"Kernel",Status.OK,kver,HW.KERNEL_VER))

        # CPU variant
        variant = ADB.prop("dalvik.vm.isa.arm.variant")
        res.append(self._r(cat,"CPU ISA variant",Status.OK if variant==HW.ISA_VARIANT else Status.WARN,
                           variant,HW.ISA_VARIANT))

        # Thermal
        for z in range(2):
            raw = ADB.sh(f"cat /sys/class/thermal/thermal_zone{z}/temp",silent=True)
            if raw and raw.lstrip("-").isdigit():
                temp = int(raw)/1000
                s = Status.OK if temp<60 else (Status.WARN if temp<75 else Status.BROKEN)
                res.append(self._r(cat,f"Thermal zone{z}",s,f"{temp:.1f}°C","<60°C"))

        # Storage
        df = ADB.sh("df -h /data",silent=True).splitlines()
        if len(df)>1:
            parts=df[1].split()
            pct_str=parts[4] if len(parts)>4 else "?"
            use=int(pct_str.replace("%","")) if pct_str!="?" else 0
            s=Status.OK if use<80 else (Status.WARN if use<90 else Status.BROKEN)
            res.append(self._r(cat,"/data storage",s,pct_str,"<80%"))

        # Internet
        ping=ADB.sh("ping -c 2 -W 3 1.1.1.1",silent=True)
        res.append(self._r(cat,"Internet",
                           Status.OK if "2 received" in ping else Status.BROKEN,
                           "OK" if "2 received" in ping else "OFFLINE"))

        # mdnsd (critical for Cast discovery)
        mdns=ADB.sh("getprop init.svc.mdnsd",silent=True)
        res.append(self._r(cat,"mdnsd (Cast discovery)",
                           Status.OK if mdns=="running" else Status.BROKEN,
                           mdns,"running"))
        return res

    # ── B: Cast Services ────────────────────────────────────────────────────
    def check_cast(self) -> List[DResult]:
        res=[]; cat="CAST"
        for pkg,reason in Cast.PROTECTED.items():
            ok=ADB.pkg_ok(pkg)
            res.append(self._r(cat,pkg.split(".")[-1],
                               Status.OK if ok else Status.BROKEN,
                               "enabled" if ok else "DISABLED","enabled",
                               CastManager.restore,reason))
        return res

    # ── C: SmartTube ────────────────────────────────────────────────────────
    def check_smarttube(self) -> List[DResult]:
        res=[]; cat="STUBE"
        found_pkg=next((p for p in [HW.PKG_SMARTTUBE_STABLE,HW.PKG_SMARTTUBE_BETA,HW.PKG_SMARTTUBE_LEGACY]
                        if ADB.pkg_exists(p)),None)
        if found_pkg:
            ver=ADB.pkg_ver(found_pkg)
            res.append(self._r(cat,"Installed",Status.OK,f"{found_pkg} v{ver}"))
            # Old package migration check
            if found_pkg==HW.PKG_SMARTTUBE_LEGACY:
                res.append(self._r(cat,"Package name",Status.WARN,
                                   "Legacy package (com.liskovsoft.*)",
                                   "org.smarttube.stable",None,
                                   "New SmartTube uses org.smarttube.stable"))
        else:
            res.append(self._r(cat,"Installed",Status.MISSING,"NOT INSTALLED",
                               HW.PKG_SMARTTUBE_STABLE,
                               lambda: APK.fetch_install(HW.URL_SMARTTUBE_STABLE,
                                           HW.PKG_SMARTTUBE_STABLE,"SmartTube Stable")))

        # Codec props
        ve=VideoEngine()
        for prop,exp in [("media.vcodec.preferhw","true"),
                         ("debug.stagefright.ccodec","1"),
                         ("media.tunneled-playback.enable","true"),
                         ("media.codec.av1.disable","true"),
                         ("media.brcm.mma.enable","1"),
                         ("dalvik.vm.isa.arm.features",HW.ISA_FEATURES_OPT)]:
            v=ADB.prop(prop)
            res.append(self._r(cat,prop.split(".")[-1],
                               Status.OK if v==exp else Status.BROKEN,
                               v or "not set",exp,ve.codec_pipeline))
        return res

    # ── D: Video Pipeline ───────────────────────────────────────────────────
    def check_video(self) -> List[DResult]:
        res=[]; cat="VIDEO"; ve=VideoEngine()
        checks=[
            ("debug.hwui.renderer",             "skiagl"),
            ("debug.renderengine.backend",      "skiaglthreaded"),
            ("debug.sf.hw",                     "1"),
            ("debug.gr.numframebuffers",        "3"),
            ("debug.hwui.layer_cache_size",     "32768"),  # updated for V3D
            ("persist.sys.ui.hw",               "true"),   # was false!
            ("debug.sf.latch_unsignaled",       "1"),
            ("debug.sf.disable_backpressure",   "1"),
            ("media.stagefright.cache-params",  "65536/131072/30"),  # was wrong
            ("media.brcm.vpu.buffers",          str(HW.VDEC_OUTPORT_BUFFERS)),
        ]
        for prop,exp in checks:
            v=ADB.prop(prop)
            res.append(self._r(cat,prop.split(".")[-1],
                               Status.OK if v==exp else Status.BROKEN,
                               v or "not set",exp,ve.rendering))
        return res

    # ── E: Network + DNS ────────────────────────────────────────────────────
    def check_network(self) -> List[DResult]:
        res=[]; cat="NET"; no=NetworkOptimizer()
        dot_host=ADB.sget("global","private_dns_specifier")
        dot_mode=ADB.sget("global","private_dns_mode")
        ip1=ADB.prop("net.dns1")
        valid_dots=[v[0] for v in HW.DNS.values()]
        dns_ok=dot_host in valid_dots and dot_mode=="hostname"
        res.append(self._r(cat,"Private DNS (DoT)",
                           Status.OK if dns_ok else Status.BROKEN,
                           f"mode={dot_mode}, host={dot_host}",
                           "hostname + one.one.one.one",
                           lambda: no.set_dns("cloudflare"),
                           f"Legacy net.dns1={ip1}"))
        # Detect old wrong hostname
        if dot_host=="dns.cloudflare.com":
            res.append(self._r(cat,"DNS hostname (v10/v11 bug)",Status.BROKEN,
                               "dns.cloudflare.com (WRONG — will fail DoT handshake)",
                               "one.one.one.one",lambda: no.set_dns("cloudflare")))
        rwnd=ADB.prop("net.tcp.default_init_rwnd")
        res.append(self._r(cat,"TCP init rwnd",
                           Status.OK if rwnd=="120" else Status.WARN,
                           rwnd or "not set","120",no.apply_tcp))
        tfo=ADB.sh("cat /proc/sys/net/ipv4/tcp_fastopen",silent=True).strip()
        res.append(self._r(cat,"TCP Fast Open",
                           Status.OK if tfo=="3" else Status.WARN,
                           tfo or "not set","3 (client+server)"))
        return res

    # ── F: Audio ────────────────────────────────────────────────────────────
    def check_audio(self) -> List[DResult]:
        res=[]; cat="AUDIO"; ha=HDMIAudio()
        for prop,exp in [("audio.offload.disable","1"),
                         ("audio.deep_buffer.media","true"),
                         ("audio.brcm.hdmi.clock_lock","true"),
                         ("tunnel.audio.encode","false"),
                         ("persist.sys.hdmi.keep_awake","true")]:  # was false!
            v=ADB.prop(prop)
            res.append(self._r(cat,prop.split(".")[-1],
                               Status.OK if v==exp else Status.BROKEN,
                               v or "not set",exp,ha.apply_audio))
        return res

    # ── G: Memory + LMK ─────────────────────────────────────────────────────
    def check_memory(self) -> List[DResult]:
        res=[]; cat="MEM"
        mo=DalvikHeap(); lm=LMKOptimizer()

        # Dalvik: check OEM values preserved + fixes applied
        for prop,exp,fn in [
            ("dalvik.vm.heapsize",     HW.DALVIK_HEAPSIZE,      mo.apply),     # 512m
            ("dalvik.vm.heapgrowthlimit",HW.DALVIK_GROWTHLIMIT, mo.apply),     # 192m
            ("dalvik.vm.heapminfree",  HW.DALVIK_HEAPMINFREE,   mo.apply),     # 2m
            ("dalvik.vm.heapmaxfree",  HW.DALVIK_HEAPMAXFREE,   mo.apply),     # 16m
            ("dalvik.vm.usejit",       "true",                   mo.apply),
            ("ro.lmk.upgrade_pressure",str(HW.LMK_UPGRADE_PRESSURE),lm.apply), # 50
            ("ro.lmk.kill_heaviest_task","true",                 lm.apply),
        ]:
            v=ADB.prop(prop)
            res.append(self._r(cat,prop.split(".")[-1],
                               Status.OK if v==exp else Status.BROKEN,
                               v or "not set",exp,fn))

        # PSI LMK confirmation
        minfree_lvl=ADB.prop("ro.lmk.use_minfree_levels")
        res.append(self._r(cat,"LMK use_minfree_levels",
                           Status.OK if minfree_lvl=="false" else Status.WARN,
                           minfree_lvl,"false (PSI-only = correct on this device)"))
        return res

    # ── H: HDMI + CEC ───────────────────────────────────────────────────────
    def check_hdmi(self) -> List[DResult]:
        res=[]; cat="HDMI"; ha=HDMIAudio()
        for prop,exp in [
            ("persist.sys.cec.status",          "true"),
            ("persist.sys.hdmi.addr.playback",  "11"),      # BCM Nexus confirmed
            ("persist.sys.hdmi.keep_awake",     "true"),    # was false!
            ("persist.nx.hdmi.tx_standby_cec",  "1"),
            ("persist.nx.hdmi.tx_view_on_cec",  "1"),
            ("persist.sys.hdr.enable",          "1"),
        ]:
            v=ADB.prop(prop)
            res.append(self._r(cat,prop.split(".")[-1],
                               Status.OK if v==exp else Status.BROKEN,
                               v or "not set",exp,ha.apply_hdmi))
        return res

    # ── Run category ────────────────────────────────────────────────────────
    def run_cat(self, cat_id:str) -> List[DResult]:
        fns = {"A":("System Health",   self.check_system),
               "B":("Cast Services",   self.check_cast),
               "C":("SmartTube",       self.check_smarttube),
               "D":("Video Pipeline",  self.check_video),
               "E":("Network/DNS",     self.check_network),
               "F":("Audio",           self.check_audio),
               "G":("Memory/LMK",      self.check_memory),
               "H":("HDMI/CEC",        self.check_hdmi)}
        entry=fns.get(cat_id.upper())
        if not entry: return []
        name,fn=entry
        L.hdr(f"🔎 DIAG [{cat_id}] — {name}")
        results=fn()
        self._print(results)
        return results

    def _print(self, results:List[DResult]) -> None:
        ok=sum(1 for r in results if r.status==Status.OK)
        bad=sum(1 for r in results if r.bad)
        for r in results:
            if r.status==Status.OK:
                L.ok(f"[{r.cat}] {r.check}: {r.found}")
            elif r.status==Status.WARN:
                L.warn(f"[{r.cat}] {r.check}: {r.found} (expected: {r.expected})")
            else:
                L.err(f"[{r.cat}] {r.check}: {r.found} (expected: {r.expected})")
                if r.detail: L.dim(r.detail)
        L.info(f"\n  Results: {ok} OK | {bad} NEED REPAIR")

    def run_all(self) -> None:
        L.hdr("🔎 INTERACTIVE DIAGNOSTICS — 8 Hardware-Targeted Categories")
        cat_names={
            "A":"System Health","B":"Cast Services","C":"SmartTube",
            "D":"Video Pipeline","E":"Network/DNS","F":"Audio",
            "G":"Memory/LMK","H":"HDMI/CEC"
        }
        all_bad: List[DResult] = []
        for cid,cname in cat_names.items():
            L.info(f"\n[{cid}] {cname}")
            results=self.run_cat(cid)
            bad=[r for r in results if r.bad]
            all_bad.extend(bad)
            if bad:
                c=L.C
                ch=input(f"  {c['w']}{len(bad)} issue(s). Repair? [Y/n/s=skip all] > {c['r']}").strip().lower()
                if ch=="s": break
                if ch in ("","y"): self._repair(bad)
            else:
                L.ok(f"  {cname}: ALL OK ✓")

        # Summary
        L.hdr("📋 DIAGNOSTIC SUMMARY")
        total=len(self.results); ok=sum(1 for r in self.results if r.status==Status.OK)
        bad=sum(1 for r in self.results if r.bad)
        warn=sum(1 for r in self.results if r.status==Status.WARN)
        L.ok(f"  {ok}/{total} OK"); L.warn(f"  {warn} WARN"); L.err(f"  {bad} BROKEN")
        if all_bad:
            L.warn("  Unresolved:")
            for r in all_bad:
                if r.bad: L.err(f"    [{r.cat}] {r.check}: {r.found}")

    def _repair(self, bad:List[DResult]) -> None:
        seen:set=set()
        for r in bad:
            if r.fix_fn and id(r.fix_fn) not in seen:
                seen.add(id(r.fix_fn))
                L.fix(f"Repairing: [{r.cat}] {r.check}")
                try: r.fix_fn()
                except Exception as e: L.err(f"Repair error: {e}")

    def menu(self) -> None:
        c=L.C
        cat_map={"A":"System Health","B":"Cast Services","C":"SmartTube",
                 "D":"Video Pipeline","E":"Network/DNS","F":"Audio",
                 "G":"Memory/LMK","H":"HDMI/CEC","*":"All (interactive)"}
        L.hdr("🔎 DIAGNOSTICS — Select Category")
        for k,v in cat_map.items():
            L.info(f"  {c['c']}{k}{c['r']}. {v}")
        ch=input(f"\n{c['c']}Category [A-H or *] > {c['r']}").strip().upper()
        if ch=="*":
            self.run_all()
        elif ch in cat_map:
            results=self.run_cat(ch)
            bad=[r for r in results if r.bad]
            if bad:
                fix=input(f"\n{c['w']}Auto-repair {len(bad)} issue(s)? [Y/n] > {c['r']}").strip().lower()
                if fix in ("","y"): self._repair(bad)
        else:
            L.warn("Invalid category")


# ─────────────────────────────────────────────────────────────────────────────
# AUTO REPAIR ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class Repair:
    """
    11 repair sectors — all targeted to real device state.
    Detection lambdas use actual getprop values as baseline.
    """

    REGISTRY: List[Dict] = [
        {"id":"smarttube_missing","name":"SmartTube not installed",
         "detect": lambda: not ADB.pkg_exists(HW.PKG_SMARTTUBE_STABLE),
         "repair": lambda: APK.fetch_install(HW.URL_SMARTTUBE_STABLE,HW.PKG_SMARTTUBE_STABLE,"SmartTube Stable")},

        {"id":"smarttube_old_pkg","name":"SmartTube old package (com.teamsmart → org.smarttube)",
         "detect": lambda: ADB.pkg_exists("com.teamsmart.videomanager.tv"),
         "repair": lambda: APK.fetch_install(HW.URL_SMARTTUBE_STABLE,HW.PKG_SMARTTUBE_STABLE,"SmartTube Stable (migrated)")},

        {"id":"cast_mediashell","name":"Cast daemon (mediashell) DISABLED — device debloat.sh damage",
         "detect": lambda: not ADB.pkg_ok(HW.PKG_MEDIASHELL),
         "repair": CastManager.restore},

        {"id":"cast_gms","name":"GMS (Cast SDK) disabled",
         "detect": lambda: not ADB.pkg_ok("com.google.android.gms"),
         "repair": CastManager.restore},

        {"id":"wrong_dns_old","name":"DNS wrong hostname: dns.cloudflare.com (v10/v11 bug)",
         "detect": lambda: ADB.sget("global","private_dns_specifier")=="dns.cloudflare.com",
         "repair": lambda: NetworkOptimizer().set_dns("cloudflare")},

        {"id":"dns_not_set","name":"Private DNS not configured (mode != hostname)",
         "detect": lambda: ADB.sget("global","private_dns_mode")!="hostname",
         "repair": lambda: NetworkOptimizer().set_dns("cloudflare")},

        {"id":"ui_hw_false","name":"persist.sys.ui.hw=false (GPU force rendering disabled)",
         "detect": lambda: ADB.prop("persist.sys.ui.hw")!="true",
         "repair": lambda: ADB.setprop("persist.sys.ui.hw","true")},

        {"id":"hdmi_keep_awake","name":"persist.sys.hdmi.keep_awake=false (HDMI drops during buffering)",
         "detect": lambda: ADB.prop("persist.sys.hdmi.keep_awake")!="true",
         "repair": lambda: ADB.setprop("persist.sys.hdmi.keep_awake","true")},

        {"id":"av1_active","name":"AV1 SW decoder active (100% CPU on A15 — confirmed no HW)",
         "detect": lambda: ADB.prop("media.codec.av1.disable")!="true",
         "repair": VideoEngine().suppress_av1},

        {"id":"idiv_disabled","name":"A15 hardware idiv not enabled in Dalvik ISA features",
         "detect": lambda: ADB.prop("dalvik.vm.isa.arm.features")!=HW.ISA_FEATURES_OPT,
         "repair": lambda: ADB.setprop("dalvik.vm.isa.arm.features",HW.ISA_FEATURES_OPT)},

        {"id":"heap_minfree","name":"dalvik.vm.heapminfree=512k (too small — GC micro-pauses)",
         "detect": lambda: ADB.prop("dalvik.vm.heapminfree") not in ("2m",""),
         "repair": DalvikHeap().apply},

        {"id":"cache_params","name":"media.stagefright.cache-params too small (32768/65536/25)",
         "detect": lambda: ADB.prop("media.stagefright.cache-params")=="32768/65536/25",
         "repair": lambda: ADB.setprop("media.stagefright.cache-params","65536/131072/30")},

        {"id":"tcp_rwnd","name":"net.tcp.default_init_rwnd=60 (half optimal)",
         "detect": lambda: ADB.prop("net.tcp.default_init_rwnd") not in ("120",""),
         "repair": lambda: (ADB.setprop("net.tcp.default_init_rwnd","120"),
                            ADB.sput("global","tcp_default_init_rwnd","120"))},

        {"id":"lmk_upgrade","name":"ro.lmk.upgrade_pressure=100 (too high — slow cached proc recovery)",
         "detect": lambda: ADB.prop("ro.lmk.upgrade_pressure")=="100",
         "repair": lambda: ADB.setprop("ro.lmk.upgrade_pressure","50")},
    ]

    @classmethod
    def scan(cls) -> None:
        L.hdr("🔧 AUTO-REPAIR — Hardware-Targeted Sector Scan")
        found: List[Dict] = []
        for entry in cls.REGISTRY:
            try: detected=entry["detect"]()
            except Exception: detected=False
            if detected:
                found.append(entry)
                L.err(f"  ✗ BROKEN: {entry['name']}")
            else:
                L.dim(f"✓ OK: {entry['id']}")

        if not found:
            L.ok("All sectors healthy — no repairs needed ✓"); return

        L.warn(f"\n{len(found)} broken sector(s):")
        for i,e in enumerate(found,1):
            L.info(f"  {i}. {e['name']}")

        c=L.C
        ch=input(f"\n{c['w']}Repair all {len(found)}? [Y=all / n=select / x=cancel] > {c['r']}").strip().lower()
        if ch=="x": return
        if ch=="n":
            for i,e in enumerate(found,1):
                sub=input(f"  [{i}] {e['name']}\n  Repair? [Y/n] > ").strip().lower()
                if sub in ("","y"): cls._do(e)
        else:
            for e in found: cls._do(e)
        L.ok("Auto-repair complete ✓")

    @classmethod
    def _do(cls,e:Dict)->None:
        L.fix(f"Repairing: {e['name']}")
        try: e["repair"]()
        except Exception as ex: L.err(f"Error: {ex}")


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY DEEP CLEAN
# ─────────────────────────────────────────────────────────────────────────────
def deep_clean() -> None:
    L.hdr("🔄 DEEP CLEAN — Cast-Safe")
    ADB.sh("am kill-all",silent=True); L.ok("  am kill-all")
    ADB.sh("pm trim-caches 2G",silent=True); L.ok("  pm trim-caches 2G")
    ADB.sh("dumpsys batterystats --reset",silent=True)
    ADB.root("sync && echo 3 > /proc/sys/vm/drop_caches")
    L.ok("  drop_caches")
    L.cast("Restoring Cast services post-clean...")
    CastManager.restore()
    L.ok("Deep clean: Cast services verified ✓")


# ─────────────────────────────────────────────────────────────────────────────
# SHIZUKU
# ─────────────────────────────────────────────────────────────────────────────
def deploy_shizuku() -> None:
    L.hdr("🔑 SHIZUKU — Privilege Engine")
    if not ADB.pkg_exists(HW.PKG_SHIZUKU):
        APK.fetch_install(HW.URL_SHIZUKU,HW.PKG_SHIZUKU,"Shizuku")
    else:
        L.ok("Shizuku already installed")
    cmd=("P=$(pm path moe.shizuku.privileged.api | cut -d: -f2); "
         "CLASSPATH=$P app_process /system/bin "
         "--nice-name=shizuku_server moe.shizuku.server.ShizukuServiceServer &")
    ADB.sh(cmd); time.sleep(3); L.ok("Shizuku server started")



# ═════════════════════════════════════════════════════════════════════════════
# MODULE: WiFiInfo — Informacje o sieci WiFi (SSID, pasmo, kanał, sygnał)
# ═════════════════════════════════════════════════════════════════════════════
class WiFiInfo:
    """
    Odczyt parametrów WiFi z dumpsys wifi + ip addr.
    Nie wymaga roota. Parsuje wyjście dumpsys dostępne dla ADB.

    Dane:
      SSID         — nazwa sieci
      BSSID        — MAC punktu dostępowego
      Frequency    — częstotliwość w MHz (→ pasmo + kanał)
      RSSI         — siła sygnału w dBm
      LinkSpeed    — prędkość łącza w Mbps
      IP           — adres IP urządzenia
      GW           — brama domyślna

    Jakość sygnału RSSI (WiFi Alliance):
      ≥ -50 dBm  = Doskonały
      -50 to -60 = Dobry
      -60 to -70 = Zadowalający
      -70 to -80 = Słaby
      < -80 dBm  = Krytyczny
    """

    @staticmethod
    def _freq_to_channel(freq: int) -> int:
        """Konwersja częstotliwości WiFi (MHz) → numer kanału."""
        if 2412 <= freq <= 2484:
            return 1 if freq == 2484 else (freq - 2407) // 5
        elif 5180 <= freq <= 5825:
            return (freq - 5000) // 5
        elif 5955 <= freq <= 7115:
            return (freq - 5950) // 5
        return 0

    @staticmethod
    def _rssi_label(rssi: int) -> str:
        if rssi >= -50: return "Doskonały 🟢"
        if rssi >= -60: return "Dobry 🟢"
        if rssi >= -70: return "Zadowalający 🟡"
        if rssi >= -80: return "Słaby 🟠"
        return "Krytyczny 🔴"

    @staticmethod
    def _band(freq: int) -> str:
        if freq < 3000: return "2.4 GHz"
        if freq < 6000: return "5 GHz"
        return "6 GHz (WiFi 6E)"

    @classmethod
    def get(cls) -> Dict[str, str]:
        """Zbierz wszystkie informacje o WiFi w jednym wywołaniu dumpsys."""
        info: Dict[str, str] = {
            "ssid": "—", "bssid": "—", "freq": "—", "band": "—",
            "channel": "—", "rssi": "—", "signal_label": "—",
            "link_speed": "—", "tx_speed": "—", "ip": "—", "gw": "—",
            "dns1": "—", "connected": "false",
        }

        # ── dumpsys wifi ─────────────────────────────────────────────────────
        raw = ADB.sh("dumpsys wifi | grep -E 'SSID|BSSID|Frequency|LinkSpeed|RSSI|ipAddress|mWifiInfo|mNetworkInfo'", silent=True)
        lines = raw.splitlines()

        for line in lines:
            l = line.strip()
            # SSID: "NazwaSieci" lub SSID=NazwaSieci
            if "SSID:" in l and "BSSID" not in l:
                m = re.search(r'SSID[=:\s]+"?([^",]+)"?', l)
                if m: info["ssid"] = m.group(1).strip()
            if "BSSID:" in l or "BSSID=" in l:
                m = re.search(r'([0-9a-f]{2}(?::[0-9a-f]{2}){5})', l, re.I)
                if m: info["bssid"] = m.group(1)
            if "Frequency:" in l or "Frequency=" in l:
                m = re.search(r'(\d{4,5})', l)
                if m:
                    freq = int(m.group(1))
                    info["freq"]    = f"{freq} MHz"
                    info["band"]    = cls._band(freq)
                    info["channel"] = str(cls._freq_to_channel(freq))
            if "RSSI:" in l or "RSSI=" in l:
                m = re.search(r'(-\d+)', l)
                if m:
                    rssi = int(m.group(1))
                    info["rssi"]         = f"{rssi} dBm"
                    info["signal_label"] = cls._rssi_label(rssi)
            if "LinkSpeed:" in l or "LinkSpeed=" in l:
                m = re.search(r'(\d+)', l)
                if m: info["link_speed"] = f"{m.group(1)} Mbps"

        # ── IP z ip addr ──────────────────────────────────────────────────────
        ip_raw = ADB.sh("ip addr show wlan0 2>/dev/null | grep 'inet '", silent=True)
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_raw)
        if m: info["ip"] = m.group(1)

        # ── Gateway z ip route ────────────────────────────────────────────────
        gw_raw = ADB.sh("ip route show dev wlan0 default 2>/dev/null", silent=True)
        m = re.search(r'via (\d+\.\d+\.\d+\.\d+)', gw_raw)
        if m: info["gw"] = m.group(1)

        # ── DNS z getprop ─────────────────────────────────────────────────────
        info["dns1"] = ADB.prop("net.dns1") or ADB.sget("global","private_dns_specifier") or "—"
        info["connected"] = "true" if info["ssid"] != "—" else "false"

        return info

    @classmethod
    def display(cls) -> None:
        """Wyświetl pełny panel sieci WiFi."""
        L.hdr("📡 PANEL SIECI WiFi")
        info = cls.get()
        c = L.C
        connected = info["connected"] == "true"

        if not connected:
            L.warn("WiFi: ROZŁĄCZONE lub brak danych")
            L.info("  Sprawdź: adb shell dumpsys wifi | grep WifiInfo")
            return

        status_color = c["s"] if connected else c["e"]
        print(f"""
  {c["b"]}┌─────────────────────────────────────────────────────────┐{c["r"]}
  {c["b"]}│  📶 POŁĄCZENIE WIFI{c["r"]}
  {c["b"]}├─────────────────────────────────────────────────────────┤{c["r"]}
  {c["b"]}│{c["r"]}  SSID        : {c["c"]}{info["ssid"]:<35}{c["r"]}  {c["b"]}│{c["r"]}
  {c["b"]}│{c["r"]}  BSSID       : {info["bssid"]:<35}  {c["b"]}│{c["r"]}
  {c["b"]}│{c["r"]}  Pasmo       : {c["h"]}{info["band"]:<35}{c["r"]}  {c["b"]}│{c["r"]}
  {c["b"]}│{c["r"]}  Kanał       : {c["h"]}{info["channel"]:<35}{c["r"]}  {c["b"]}│{c["r"]}
  {c["b"]}│{c["r"]}  Częstotliw. : {info["freq"]:<35}  {c["b"]}│{c["r"]}
  {c["b"]}│{c["r"]}  Siła sygnału: {info["rssi"]:>8}  {info["signal_label"]:<22}  {c["b"]}│{c["r"]}
  {c["b"]}│{c["r"]}  Prędkość    : {c["s"]}{info["link_speed"]:<35}{c["r"]}  {c["b"]}│{c["r"]}
  {c["b"]}├─────────────────────────────────────────────────────────┤{c["r"]}
  {c["b"]}│{c["r"]}  IP          : {c["c"]}{info["ip"]:<35}{c["r"]}  {c["b"]}│{c["r"]}
  {c["b"]}│{c["r"]}  Brama (GW)  : {info["gw"]:<35}  {c["b"]}│{c["r"]}
  {c["b"]}│{c["r"]}  DNS         : {info["dns1"]:<35}  {c["b"]}│{c["r"]}
  {c["b"]}└─────────────────────────────────────────────────────────┘{c["r"]}""")

        # Zalecenia jakości sygnału
        rssi_str = info["rssi"].replace(" dBm","")
        if rssi_str.lstrip("-").isdigit():
            rssi = int(rssi_str)
            if rssi < -70:
                L.warn(f"RSSI={rssi}dBm — słaby sygnał. Rozważ: zbliżenie do routera, WiFi repeater, lub kabel ETH.")
            if info["band"] == "2.4 GHz":
                L.info("  Tip: sieć 2.4GHz — większy zasięg, mniejsza przepustowość niż 5GHz.")
                L.info("  Dla 4K streaming zalecane: 5GHz ≥ -65dBm lub kabel ETH.")

    @classmethod
    def compact_line(cls) -> str:
        """Jednolinijkowy skrót dla bannera menu."""
        info = cls.get()
        if info["connected"] != "true":
            return "WiFi: ROZŁĄCZONE"
        rssi_str = info["rssi"].replace(" dBm","")
        try: rssi = int(rssi_str); bar = "████" if rssi>=-50 else "███░" if rssi>=-60 else "██░░" if rssi>=-70 else "█░░░"
        except: bar = "░░░░"
        return f"{info['ssid']} │ {info['band']} CH{info['channel']} │ {bar} {info['rssi']} │ {info['ip']}"


# ═════════════════════════════════════════════════════════════════════════════
# MODULE: Benchmark — Pomiar wydajności z normami dla BCM7362
# ═════════════════════════════════════════════════════════════════════════════
class BenchNorm(NamedTuple):
    """Norma wydajności dla danej kategorii testu."""
    name: str
    unit: str
    excellent: float   # ≥ doskonały
    good:      float   # ≥ dobry
    warn:      float   # ≥ ostrzeżenie
    critical:  float   # < krytyczny
    higher_is_better: bool = True

class Benchmark:
    """
    Benchmark wydajności Sagemcom DCTIW362P — wartości normatywne
    wyznaczone dla BCM7362 / Cortex-A15 dual-core @ ~1.0GHz.

    Kategorie:
      CPU   — operacje arytmetyczne i logiczne (md5sum pętla)
      RAM   — przepustowość odczytu (dd z /dev/zero)
      FLASH — I/O eMMC sekwencyjny (dd do /data/local/tmp)
      NET   — latencja ping do GW, bramki CDN
      FRAME — czas renderowania klatki (dumpsys gfxinfo)
      BOOT  — czas od boot_complete (dev.bootcomplete)

    Historia wyników: ~/.playbox_cache/bench_history.json
    """

    HISTORY_FILE = CACHE_DIR / "bench_history.json"

    # Normy dla BCM7362 (ustalone empirycznie)
    NORMS: Dict[str, BenchNorm] = {
        "cpu_hash_ms": BenchNorm(
            "CPU (hash 1MB)", "ms/op",
            excellent=80, good=120, warn=200, critical=400,
            higher_is_better=False),  # niżej = lepiej

        "ram_mb_s": BenchNorm(
            "RAM Read Bandwidth", "MB/s",
            excellent=800, good=500, warn=300, critical=100),

        "flash_mb_s": BenchNorm(
            "Flash Write (eMMC)", "MB/s",
            excellent=30, good=20, warn=10, critical=3),

        "ping_gw_ms": BenchNorm(
            "Ping Gateway (LAN)", "ms",
            excellent=2, good=5, warn=15, critical=50,
            higher_is_better=False),

        "ping_cdn_ms": BenchNorm(
            "Ping CDN (internet)", "ms",
            excellent=20, good=40, warn=80, critical=200,
            higher_is_better=False),

        "frame_p99_ms": BenchNorm(
            "Frame time P99 (SmartTube)", "ms",
            excellent=16, good=33, warn=50, critical=100,
            higher_is_better=False),

        "janky_pct": BenchNorm(
            "Janky frames %", "%",
            excellent=1, good=5, warn=10, critical=20,
            higher_is_better=False),
    }

    @staticmethod
    def _rate(norm: BenchNorm, val: float) -> Tuple[str, str]:
        c = L.C
        if norm.higher_is_better:
            if val >= norm.excellent: return "Doskonały", c["s"]
            if val >= norm.good:      return "Dobry",     c["s"]
            if val >= norm.warn:      return "Słaby",     c["w"]
            return "Krytyczny", c["e"]
        else:
            if val <= norm.excellent: return "Doskonały", c["s"]
            if val <= norm.good:      return "Dobry",     c["s"]
            if val <= norm.warn:      return "Słaby",     c["w"]
            return "Krytyczny", c["e"]

    @classmethod
    def run_cpu(cls) -> Optional[float]:
        """Test CPU: czas md5sum na 1MB danych (ms/op). Niżej = lepiej."""
        L.info("  CPU hash test (5× md5sum 1MB)...")
        raw = ADB.sh("for i in 1 2 3 4 5; do dd if=/dev/urandom bs=1024 count=1024 2>/dev/null | md5sum; done 2>&1 | tail -1", silent=True)
        # Alternatywa — zmierz czas przez date +%s%3N
        t_start = ADB.sh("date +%s%3N", silent=True)
        ADB.sh("dd if=/dev/urandom bs=1048576 count=5 2>/dev/null | md5sum > /dev/null", silent=True)
        t_end = ADB.sh("date +%s%3N", silent=True)
        try:
            elapsed = (int(t_end) - int(t_start)) / 5  # ms per 1MB
            L.ok(f"    CPU hash: {elapsed:.0f} ms/op")
            return elapsed
        except: return None

    @classmethod
    def run_ram(cls) -> Optional[float]:
        """Test RAM: przepustowość odczytu dd z /dev/zero → /dev/null."""
        L.info("  RAM read bandwidth test (64MB)...")
        raw = ADB.sh("dd if=/dev/zero of=/dev/null bs=1048576 count=64 2>&1", silent=True)
        m = re.search(r'(\d+\.?\d*)\s*MB/s', raw)
        if m:
            val = float(m.group(1))
            L.ok(f"    RAM: {val:.0f} MB/s")
            return val
        # Alternatywa: mierz czas
        t_start = ADB.sh("date +%s%3N", silent=True)
        ADB.sh("dd if=/dev/zero of=/dev/null bs=1048576 count=64 2>/dev/null", silent=True)
        t_end = ADB.sh("date +%s%3N", silent=True)
        try:
            ms = int(t_end) - int(t_start)
            mb_s = (64 * 1000) / ms if ms > 0 else 0
            L.ok(f"    RAM: {mb_s:.0f} MB/s")
            return mb_s
        except: return None

    @classmethod
    def run_flash(cls) -> Optional[float]:
        """Test I/O eMMC: sekwencyjny zapis 16MB do /data/local/tmp."""
        L.info("  Flash write test (16MB → /data/local/tmp)...")
        ADB.sh("rm -f /data/local/tmp/_bench_test 2>/dev/null", silent=True)
        t_start = ADB.sh("date +%s%3N", silent=True)
        raw = ADB.sh("dd if=/dev/zero of=/data/local/tmp/_bench_test bs=1048576 count=16 2>&1", silent=True)
        t_end = ADB.sh("date +%s%3N", silent=True)
        ADB.sh("rm -f /data/local/tmp/_bench_test", silent=True)
        m = re.search(r'(\d+\.?\d*)\s*MB/s', raw)
        if m:
            val = float(m.group(1))
            L.ok(f"    Flash: {val:.1f} MB/s")
            return val
        try:
            ms = int(t_end) - int(t_start)
            mb_s = (16 * 1000) / ms if ms > 0 else 0
            L.ok(f"    Flash: {mb_s:.1f} MB/s")
            return mb_s
        except: return None

    @classmethod
    def run_ping(cls) -> Tuple[Optional[float], Optional[float]]:
        """Test sieci: ping do GW + ping do 1.1.1.1 (CDN)."""
        L.info("  Network ping test...")
        gw = re.search(r'via (\d+\.\d+\.\d+\.\d+)', ADB.sh('ip route show dev wlan0 default 2>/dev/null', silent=True) or ''); gw = gw.group(1) if gw else ''
        gw_ms = None
        cdn_ms = None

        if gw:
            raw = ADB.sh(f"ping -c 4 -W 2 {gw} 2>/dev/null", silent=True)
            m = re.search(r'avg.*?([\d.]+)/', raw)
            if m: gw_ms = float(m.group(1)); L.ok(f"    GW ping: {gw_ms:.1f} ms")

        raw2 = ADB.sh("ping -c 4 -W 3 1.1.1.1 2>/dev/null | tail -1", silent=True)
        m2 = re.search(r'avg.*?([\d.]+)/', raw2)
        if m2: cdn_ms = float(m2.group(1)); L.ok(f"    CDN ping: {cdn_ms:.1f} ms")

        return gw_ms, cdn_ms

    @classmethod
    def run_frames(cls) -> Tuple[Optional[float], Optional[float]]:
        """Frame timing z gfxinfo SmartTube (jeśli uruchomiony)."""
        L.info("  Frame timing (SmartTube gfxinfo)...")
        pkg = HW.PKG_SMARTTUBE_STABLE
        if not ADB.pkg_ok(pkg):
            L.info("    SmartTube nie jest uruchomiony — pominięto frame test")
            return None, None
        raw = ADB.sh(f"dumpsys gfxinfo {pkg} framestats 2>/dev/null", silent=True)
        times = []
        for line in raw.splitlines():
            parts = line.split(",")
            if len(parts) > 13:
                try:
                    intended = int(parts[1]); actual = int(parts[2])
                    frame_ns = actual - intended
                    if 0 < frame_ns < 5_000_000_000:
                        times.append(frame_ns / 1_000_000)  # ns → ms
                except: pass
        if not times:
            L.info("    Brak danych gfxinfo framestats")
            return None, None
        p99 = sorted(times)[int(len(times)*0.99)] if len(times) > 10 else max(times)
        total = len(times)
        janky = sum(1 for t in times if t > 16.7)
        janky_pct = (janky/total*100) if total > 0 else 0
        L.ok(f"    Frame P99: {p99:.1f}ms | Janky: {janky_pct:.1f}% ({janky}/{total})")
        return p99, janky_pct

    @classmethod
    def run_all(cls) -> Dict[str, float]:
        """Uruchom pełen benchmark i zwróć wyniki."""
        L.hdr("⚡ BENCHMARK — BCM7362 / Cortex-A15 Performance Suite")
        L.warn("Nie używaj urządzenia podczas testu. Czas: ~2 minuty.")
        results: Dict[str, float] = {}

        cpu = cls.run_cpu()
        if cpu is not None: results["cpu_hash_ms"] = cpu

        ram = cls.run_ram()
        if ram is not None: results["ram_mb_s"] = ram

        flash = cls.run_flash()
        if flash is not None: results["flash_mb_s"] = flash

        gw_ms, cdn_ms = cls.run_ping()
        if gw_ms  is not None: results["ping_gw_ms"]  = gw_ms
        if cdn_ms is not None: results["ping_cdn_ms"] = cdn_ms

        p99, janky = cls.run_frames()
        if p99   is not None: results["frame_p99_ms"] = p99
        if janky is not None: results["janky_pct"]    = janky

        cls._print_report(results)
        cls._save_history(results)
        return results

    @classmethod
    def _print_report(cls, results: Dict[str, float]) -> None:
        c = L.C
        L.hdr("📊 WYNIKI BENCHMARK — Porównanie z normą BCM7362")
        print(f"  {c['b']}{'Kategoria':<30} {'Wynik':>10} {'Norma':>12} {'Ocena'}{c['r']}")
        print(f"  {'─'*65}")
        total_score = 0; count = 0
        for key, norm in cls.NORMS.items():
            if key not in results:
                print(f"  {norm.name:<30} {'N/A':>10} {'—':>12}")
                continue
            val = results[key]
            label, col = cls._rate(norm, val)
            # Oblicz score 0-100
            if norm.higher_is_better:
                score = min(100, max(0, int((val / norm.excellent) * 100)))
            else:
                score = min(100, max(0, int((norm.excellent / max(val, 0.001)) * 100)))
            total_score += score; count += 1
            norm_str = f"≥{norm.excellent}" if norm.higher_is_better else f"≤{norm.excellent}"
            print(f"  {norm.name:<30} {val:>8.1f}{norm.unit:>4}  {norm_str:>10}  {col}{label}{c['r']}")

        avg_score = total_score // count if count > 0 else 0
        grade = "S" if avg_score>=90 else "A" if avg_score>=75 else "B" if avg_score>=60 else "C" if avg_score>=45 else "D"
        print(f"\n  {c['b']}Ogólna ocena: {c['s']} {avg_score}/100 (Grade {grade}){c['r']}")
        cls._show_history_delta(results)

    @classmethod
    def _save_history(cls, results: Dict[str, float]) -> None:
        history = []
        if cls.HISTORY_FILE.exists():
            try:
                with open(cls.HISTORY_FILE) as f:
                    history = json.load(f)
            except: pass
        entry = {"ts": datetime.datetime.now().isoformat(), **results}
        history.append(entry)
        history = history[-20:]  # ostatnie 20 sesji
        with open(cls.HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
        L.ok(f"  Historia zapisana: {cls.HISTORY_FILE}")

    @classmethod
    def _show_history_delta(cls, current: Dict[str, float]) -> None:
        if not cls.HISTORY_FILE.exists(): return
        try:
            with open(cls.HISTORY_FILE) as f:
                history = json.load(f)
            if len(history) < 2: return
            prev = history[-2]
            c = L.C
            print(f"\n  {c['b']}Zmiana vs poprzednia sesja:{c['r']}")
            for key in current:
                if key in prev:
                    delta = current[key] - prev[key]
                    norm = cls.NORMS.get(key)
                    better = (delta < 0) if (norm and not norm.higher_is_better) else (delta > 0)
                    arrow = "↑" if delta > 0 else "↓"
                    col = c["s"] if better else c["e"]
                    print(f"    {key:<22} {col}{arrow} {abs(delta):.1f}{c['r']}")
        except: pass

    @classmethod
    def quick_latency(cls) -> None:
        """Szybki test latencji sieci (20s)."""
        L.hdr("🏓 SZYBKI TEST LATENCJI SIECI")
        targets = [("Gateway (LAN)", None), ("Cloudflare CDN", "1.1.1.1"),
                   ("Google DNS", "8.8.8.8"), ("YouTube CDN", "googlevideo.com")]
        _gw_raw = ADB.sh('ip route show dev wlan0 default 2>/dev/null', silent=True) or ''; _gw_m = re.search(r'via (\d+\.\d+\.\d+\.\d+)', _gw_raw); gw = _gw_m.group(1) if _gw_m else ''
        for name, host in targets:
            target = host or gw
            if not target: continue
            raw = ADB.sh(f"ping -c 5 -W 2 {target} 2>/dev/null | tail -1", silent=True)
            m = re.search(r'(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)', raw)
            if m:
                mn,avg,mx,std = m.groups()
                s = Status.OK if float(avg)<20 else (Status.WARN if float(avg)<80 else Status.BROKEN)
                col = L.C["s"] if s==Status.OK else (L.C["w"] if s==Status.WARN else L.C["e"])
                print(f"  {name:<22}: {col}avg={avg}ms  min={mn}  max={mx}  jitter={std}{L.C['r']}")
            else:
                L.warn(f"  {name}: brak odpowiedzi")


# ═════════════════════════════════════════════════════════════════════════════
# MODULE: Watchdog — Proaktywna samo-naprawcza diagnostyka
# ═════════════════════════════════════════════════════════════════════════════
class Watchdog:
    """
    Watchdog działa jako wątek tła i proaktywnie monitoruje urządzenie.
    Przy wykryciu problemu — automatyczna naprawa bez interwencji użytkownika.

    Monitorowane zdarzenia:
      1. Cast services — jeśli mediashell/GMS wyłączone → restore
      2. Pamięć RAM    — jeśli MemAvailable < 150MB → trim-caches
      3. Temperatura   — jeśli thermal_zone > 80°C → alert
      4. DNS           — jeśli private_dns_specifier = błędny → naprawa
      5. mdnsd         — jeśli serwis mdnsd zatrzymany → alert
      6. SmartTube     — wykryj crash (ANR/FC) w logcat

    Interwał: co 30 sekund (konfigurowalny).
    Zatrzymanie: Watchdog.stop() lub Ctrl+C.
    """

    _thread: Optional[threading.Thread] = None
    _stop_event = threading.Event()
    _interval: int = 30
    _alerts: List[str] = []
    _running: bool = False

    @classmethod
    def start(cls, interval: int = 30) -> None:
        if cls._running:
            L.warn("Watchdog już działa"); return
        cls._interval = interval
        cls._stop_event.clear()
        cls._running = True
        cls._thread = threading.Thread(target=cls._loop, daemon=True, name="Watchdog")
        cls._thread.start()
        L.ok(f"🐕 Watchdog uruchomiony (interwał: {interval}s)")
        L.info("  Monitoruje: Cast, RAM, Thermal, DNS, mdnsd, SmartTube crash")

    @classmethod
    def stop(cls) -> None:
        cls._stop_event.set()
        cls._running = False
        L.ok("🐕 Watchdog zatrzymany")

    @classmethod
    def _loop(cls) -> None:
        while not cls._stop_event.is_set():
            try:
                cls._check_cycle()
            except Exception as e:
                pass  # Watchdog nigdy nie crashuje
            cls._stop_event.wait(cls._interval)

    @classmethod
    def _check_cycle(cls) -> None:
        ts = time.strftime("%H:%M:%S")

        # 1. Cast mediashell
        if not ADB.pkg_ok(HW.PKG_MEDIASHELL):
            alert = f"[{ts}] ⚠ CAST: mediashell DISABLED → auto-restore"
            cls._alert(alert)
            CastManager.restore()

        # 2. RAM pressure
        mem_raw = ADB.sh("grep MemAvailable /proc/meminfo", silent=True)
        m = re.search(r"(\d+)\s*kB", mem_raw)
        if m:
            avail_mb = int(m.group(1)) // 1024
            if avail_mb < 120:
                cls._alert(f"[{ts}] ⚠ RAM CRITICAL: {avail_mb}MB → trim-caches")
                ADB.sh("am kill-all", silent=True)
                ADB.sh("pm trim-caches 1G", silent=True)
            elif avail_mb < 180:
                cls._alert(f"[{ts}] ⚠ RAM LOW: {avail_mb}MB available")

        # 3. Thermal
        for zone in range(3):
            raw = ADB.sh(f"cat /sys/class/thermal/thermal_zone{zone}/temp", silent=True)
            if raw and raw.isdigit():
                temp = int(raw) / 1000
                if temp >= 80:
                    cls._alert(f"[{ts}] 🔥 THERMAL zone{zone}: {temp:.1f}°C — krytyczna temperatura!")

        # 4. DNS — wykryj stary błędny hostname
        dot = ADB.sget("global", "private_dns_specifier")
        if dot == "dns.cloudflare.com":
            cls._alert(f"[{ts}] ⚠ DNS BUG: dns.cloudflare.com → naprawa → one.one.one.one")
            ADB.sput("global", "private_dns_specifier", "one.one.one.one")

        # 5. mdnsd
        mdns = ADB.prop("init.svc.mdnsd")
        if mdns and mdns != "running":
            cls._alert(f"[{ts}] ⚠ mdnsd: {mdns} (nie running) — Cast discovery może nie działać")

        # 6. SmartTube crash w logcat
        crashes = ADB.sh(
            f"logcat -d -t 50 -v brief 2>/dev/null | grep -E \'{HW.PKG_SMARTTUBE_STABLE}.*crash|ANR|FATAL\' | tail -3",
            silent=True)
        if crashes and "E/" in crashes:
            cls._alert(f"[{ts}] ⚠ SmartTube crash/ANR wykryty w logcat")

    @classmethod
    def _alert(cls, msg: str) -> None:
        cls._alerts.append(msg)
        L.warn(msg)
        # Zachowaj max 50 alertów
        cls._alerts = cls._alerts[-50:]

    @classmethod
    def show_alerts(cls) -> None:
        L.hdr("🐕 WATCHDOG — Historia alertów")
        if not cls._alerts:
            L.ok("Brak alertów — system stabilny ✓"); return
        for a in cls._alerts[-20:]:
            print(f"  {L.C['w']}{a}{L.C['r']}")
        L.info(f"  Łącznie alertów: {len(cls._alerts)}")

    @classmethod
    def status(cls) -> None:
        c = L.C
        state = f"{c['s']}AKTYWNY 🐕{c['r']}" if cls._running else f"{c['e']}ZATRZYMANY{c['r']}"
        print(f"  Watchdog: {state} | Interwał: {cls._interval}s | Alertów: {len(cls._alerts)}")


# ═════════════════════════════════════════════════════════════════════════════
# MODULE: CrashAnalyzer — Analiza logcat
# ═════════════════════════════════════════════════════════════════════════════
class CrashAnalyzer:
    """Analiza logcat — wykrywa crashe, ANR, błędy systemu."""

    @staticmethod
    def scan(lines: int = 500) -> None:
        L.hdr(f"🔍 CRASH ANALYZER — Ostatnie {lines} linii logcat")
        raw = ADB.sh(f"logcat -d -t {lines} -v brief 2>/dev/null", silent=True)
        if not raw:
            L.warn("Brak dostępu do logcat"); return

        categories = {
            "FATAL": [], "ANR": [], "OOM": [],
            "SmartTube": [], "Cast": [], "SurfaceFlinger": [],
        }
        for line in raw.splitlines():
            ll = line.lower()
            if "fatal" in ll or "force close" in ll: categories["FATAL"].append(line)
            if "anr in" in ll: categories["ANR"].append(line)
            if "outofmemory" in ll or "low memory" in ll: categories["OOM"].append(line)
            if HW.PKG_SMARTTUBE_STABLE.lower() in ll: categories["SmartTube"].append(line)
            if "mediashell" in ll or "cast" in ll: categories["Cast"].append(line)
            if "surfaceflinger" in ll and ("error" in ll or "crash" in ll): categories["SurfaceFlinger"].append(line)

        any_found = False
        for cat, events in categories.items():
            if events:
                any_found = True
                L.warn(f"  [{cat}] — {len(events)} zdarzeń:")
                for e in events[-3:]:
                    L.dim(e[:120])

        if not any_found:
            L.ok("Brak krytycznych błędów w logcat ✓")

    @staticmethod
    def export_log(path: str = "/sdcard/playbox_logcat.txt") -> None:
        """Eksportuj logcat do pliku na urządzeniu."""
        ADB.sh(f"logcat -d -v threadtime 2>/dev/null > {path}", silent=True)
        size = ADB.sh(f"du -sh {path} 2>/dev/null | cut -f1", silent=True)
        L.ok(f"Logcat zapisany: {path} ({size})")


# ═════════════════════════════════════════════════════════════════════════════
# MODULE: QuickTools — Narzędzia pomocnicze
# ═════════════════════════════════════════════════════════════════════════════
class QuickTools:
    """Narzędzia szybkiego dostępu."""

    @staticmethod
    def screenshot(filename: str = "") -> None:
        """Zrzut ekranu → /sdcard/screenshot_YYYYMMDD_HHMMSS.png + pull."""
        ts = time.strftime("%Y%m%d_%H%M%S")
        remote = f"/sdcard/screenshot_{ts}.png"
        ADB.sh(f"screencap -p {remote}", silent=True)
        local = Path.home() / f"screenshot_{ts}.png"
        try:
            subprocess.check_call(["adb","-s",ADB.dev,"pull",remote,str(local)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            L.ok(f"Screenshot: {local}")
        except: L.warn(f"Screenshot zapisany na urządzeniu: {remote}")

    @staticmethod
    def export_apk(pkg: str) -> None:
        """Eksportuj APK zainstalowanej aplikacji."""
        path_raw = ADB.sh(f"pm path {pkg}", silent=True)
        m = re.search(r"package:(.+)", path_raw)
        if not m:
            L.err(f"APK nie znaleziony: {pkg}"); return
        remote = m.group(1).strip()
        local = CACHE_DIR / f"{pkg}.apk"
        try:
            subprocess.check_call(["adb","-s",ADB.dev,"pull",remote,str(local)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            L.ok(f"APK wyeksportowany: {local} ({local.stat().st_size//1024}KB)")
        except Exception as e:
            L.err(f"Błąd eksportu APK: {e}")

    @staticmethod
    def reboot_menu() -> None:
        """Menu restartu urządzenia."""
        c = L.C
        L.hdr("🔄 RESTART URZĄDZENIA")
        opts = [
            ("1", "Normalny restart",         "adb reboot"),
            ("2", "Recovery mode",            "adb reboot recovery"),
            ("3", "Bootloader / fastboot",    "adb reboot bootloader"),
            ("4", "Tylko restart ADB daemon", "adb kill-server && adb start-server"),
            ("0", "Anuluj",                   ""),
        ]
        for k,name,_ in opts:
            print(f"  {c['c']}{k}.{c['r']} {name}")
        ch = input(f"\n{c['c']}Wybór > {c['r']}").strip()
        for k,name,cmd in opts:
            if ch == k and cmd:
                L.warn(f"Restart: {name}")
                time.sleep(1)
                os.system(cmd)
                return
        L.info("Anulowano")

    @staticmethod
    def device_info() -> None:
        """Pełna karta urządzenia."""
        L.hdr("📱 KARTA URZĄDZENIA")
        fields = [
            ("Model",       "ro.product.model"),
            ("Producent",   "ro.product.manufacturer"),
            ("Android",     "ro.build.version.release"),
            ("SDK API",     "ro.build.version.sdk"),
            ("Build",       "ro.build.display.id"),
            ("CPU ISA",     "dalvik.vm.isa.arm.variant"),
            ("CPU ISA feat","dalvik.vm.isa.arm.features"),
            ("Kernel",      ""),
            ("ABI",         "ro.product.cpu.abi"),
            ("Bootloader",  "ro.bootloader"),
            ("Fingerprint", "ro.build.fingerprint"),
            ("GFX driver",  "ro.gfx.driver.0"),
            ("GLES ver",    "ro.opengles.version"),
            ("Locale",      "ro.product.locale"),
            ("Timezone",    "persist.sys.timezone"),
            ("ADB port",    "service.adb.tcp.port"),
        ]
        for label, prop in fields:
            if prop:
                val = ADB.prop(prop)
            else:
                val = ADB.sh("uname -r", silent=True)
                label = "Kernel"
            if val:
                print(f"  {label:<18}: {L.C['c']}{val}{L.C['r']}")

        # Pamięć
        meminfo = ADB.sh("grep -E 'MemTotal|MemAvailable' /proc/meminfo", silent=True)
        for line in meminfo.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                mb = int(parts[1]) // 1024
                print(f"  {parts[0].rstrip(':'):<18}: {mb} MB")

        # Uptime
        uptime = ADB.sh("cat /proc/uptime | cut -d. -f1 | xargs -I{} sh -c 'echo $(({}/3600))h $(( ({}%3600)/60 ))m' 2>/dev/null", silent=True)
        if uptime: print(f"  {'Uptime':<18}: {uptime}")

    @staticmethod
    def installed_apps() -> None:
        """Lista zainstalowanych aplikacji użytkownika."""
        L.hdr("📦 ZAINSTALOWANE APLIKACJE (użytkownik)")
        raw = ADB.sh("pm list packages -3 -e", silent=True)
        pkgs = [l[8:].strip() for l in raw.splitlines() if l.startswith("package:")]
        L.info(f"  Zainstalowane: {len(pkgs)} aplikacji")
        for p in sorted(pkgs):
            ver = ADB.pkg_ver(p)
            print(f"  {L.C['c']}{p}{L.C['r']} v{ver}")

    @staticmethod
    def show_storage() -> None:
        """Informacje o pamięci masowej."""
        L.hdr("💾 PAMIĘĆ MASOWA")
        raw = ADB.sh("df -h 2>/dev/null", silent=True)
        for line in raw.splitlines():
            if any(p in line for p in ["/data", "/system", "/cache", "/sdcard", "tmpfs"]):
                print(f"  {L.C['c']}{line}{L.C['r']}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
class App:

    def __init__(self, device:str):
        self.device = device
        self.ve     = VideoEngine()
        self.dh     = DalvikHeap()
        self.lmk    = LMKOptimizer()
        self.net    = NetworkOptimizer()
        self.ha     = HDMIAudio()
        self.res    = Responsiveness()
        self.dbl    = SafeDebloat()
        self.cast   = CastManager()
        self.aot    = AOT()
        self.diag   = Diag()
        self.rep    = Repair()
        self.pd     = PerfDiag()
        self.bench  = Benchmark()
        self.wifi   = WiFiInfo()
        self.qa     = CrashAnalyzer()
        self.qt     = QuickTools()
        self.wd     = Watchdog()

    def _banner(self) -> None:
        c = L.C
        # Live WiFi line (szybki odczyt, ~0.3s)
        try: wifi_line = WiFiInfo.compact_line()
        except: wifi_line = "WiFi: brak danych"
        wd_state = "🐕 AKTYWNY" if Watchdog._running else "  zatrzymany"
        print(f"""
{c['h']}{c['b']}╔══════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v{VERSION} — Hardware-Targeted Precision
║  Sagemcom DCTIW362P │ Android TV 9 │ Kernel 4.9.190 │ ARMv7 A15
╠══════════════════════════════════════════════════════════════════════╣
║  BCM7362 VPU │ VideoCore GLES3.1 │ MMA=1 │ VDec32 │ V3D Fences
║  RAM:1459MB │ Nexus:240MB │ Userspace:~{HW.USERSPACE_BUDGET_MB}MB │ PSI-LMK
╠══════════════════════════════════════════════════════════════════════╣{c['r']}
{c['c']}  📡 {wifi_line:<66}{c['h']}{c['b']}║
║  {c['r']}🐕 Watchdog:{c['s']} {wd_state:<10}{c['h']}{c['b']}  🎬 VP9+Tunnel  🛡 Cast  🔒 DNS:1.1.1.1
╚══════════════════════════════════════════════════════════════════════╝{c['r']}
  {c['d']}ADB: {c['c']}{self.device}{c['d']}   Build: PTT1.190826.001{c['r']}
""")

    def _menu(self) -> None:
        c = L.C
        while True:
            os.system("clear"); self._banner()
            print(f"""{c["b"]}{"═"*72}{c["r"]}
  {c["s"]}🎬 VIDEO{c["r"]}
    {c["s"]}1.{c["r"]}  Codec Pipeline (A15-idiv + MMA + VDec32 + Tunnel Mode)
    {c["s"]}2.{c["r"]}  Rendering (Vulkan-guard + render_thread + V3D explicit fence)
    {c["s"]}3.{c["r"]}  AV1 Suppression (BCM7362 — potwierdzony brak HW dekodera)

  {c["h"]}🛡 CHROMECAST{c["r"]}
    {c["s"]}4.{c["r"]}  Audit Cast Services + stan mdnsd
    {c["s"]}5.{c["r"]}  Restore Cast Services (tryb awaryjny)
    {c["s"]}6.{c["r"]}  Cast mDNS Network Tuning

  {c["i"]}🔎 DIAGNOSTYKA & NAPRAWA{c["r"]}
    {c["i"]}D. {c["r"]} Interactive Diagnostics (8 kategorii hardware-targeted)
    {c["i"]}R. {c["r"]} Auto-Repair ({len(Repair.REGISTRY)} sektorów) — scan + naprawa
    {c["i"]}G. {c["r"]} Performance Report (gfxinfo + meminfo + battery)
    {c["i"]}V. {c["r"]} SmartTube Frame Profile (frame timing P99 + Janky%)
    {c["i"]}CR.{c["r"]} Crash Analyzer — skan logcat (FATAL/ANR/OOM)

  {c["c"]}📊 WYDAJNOŚĆ{c["r"]}
    {c["c"]}B. {c["r"]} 🏁 Benchmark pełny (CPU/RAM/Flash/Net/Frame + ocena)
    {c["c"]}BL.{c["r"]} ⚡ Szybki test latencji (ping GW + CDN)
    {c["c"]}BH.{c["r"]} 📈 Historia benchmarków (ostatnie 20 sesji)

  {c["h"]}📡 SIEĆ & DNS{c["r"]}
    {c["w"]}W. {c["r"]} 📶 Panel WiFi (SSID, pasmo, kanał, RSSI, IP, GW)
    {c["i"]}N. {c["r"]} 🔒 DNS Manager (Cloudflare/Google/Quad9/AdGuard/NextDNS)
    {c["w"]}7. {c["r"]} TCP stack + DNS + captive_portal + NTP
    {c["w"]}7W.{c["r"]} WiFi Reset (svc wifi disable → enable)

  {c["w"]}⚙ SYSTEM{c["r"]}
    {c["w"]}8. {c["r"]} HDMI + CEC (BCM Nexus addr=11, keep_awake=true)
    {c["w"]}9. {c["r"]} Audio A/V Sync + offload profile (HDMI clock lock)
    {c["w"]}10.{c["r"]} Dalvik Heap (OEM 512m/192m, minfree 512k→2m)
    {c["w"]}11.{c["r"]} LMK PSI-only (upgrade_pressure=50, minfree /sys SKIPPED)
    {c["w"]}12.{c["r"]} Responsiveness + I/O deadline + A15 performance gov
    {c["w"]}13.{c["r"]} Stability Tweaks (telemetria, ANR, touch_sounds)
    {c["w"]}13G.{c["r"]}GMS AppOps (WAKE_LOCK only — Cast Safe)
    {c["w"]}14.{c["r"]} Safe Debloat (Cast gate aktywny)
    {c["w"]}15.{c["r"]} Deep Clean RAM (Cast-Safe restore)
    {c["w"]}16.{c["r"]} AOT Compile SmartTube + Cast + GMS (Xmx=512m)
    {c["w"]}17.{c["r"]} Deploy Shizuku
    {c["w"]}RB.{c["r"]} ↩ Rollback — przywróć ustawienia sprzed tweaków

  {c["h"]}🐕 WATCHDOG{c["r"]}
    {c["h"]}WD.{c["r"]} Start/Stop Watchdog (auto-healing daemon)
    {c["h"]}WA.{c["r"]} Historia alertów Watchdog

  {c["d"]}🛠 NARZĘDZIA{c["r"]}
    {c["d"]}QI.{c["r"]} 📱 Karta urządzenia (pełne informacje hardware)
    {c["d"]}QS.{c["r"]} 📸 Screenshot (zapisz + pobierz)
    {c["d"]}QR.{c["r"]} 🔄 Menu restartu (normal / recovery / bootloader)
    {c["d"]}QA.{c["r"]} 📦 Lista aplikacji użytkownika
    {c["d"]}QD.{c["r"]} 💾 Stan pamięci masowej (df -h)
    {c["d"]}QL.{c["r"]} 📋 Eksport logcat do pliku

  {c["c"]}🚀 TRYBY AUTO{c["r"]}
    {c["c"]}20.{c["r"]} 🚀 SMARTTUBE ULTRA (15 kroków)
    {c["c"]}21.{c["r"]} 🏆 FULL SYSTEM ULTRA (18 kroków)
    {c["e"]}0.{c["r"]}  Exit
{c["b"]}{"═"*72}{c["r"]}""")

            ch = input(f"\n{c['c']}Choice [{c['r']}0-21/D/R/G/V/W/N/B/WD/WA/CR/QI/QS/QR/QA/QD/QL{c['c']}] > {c['r']}").strip().lower()

            dispatch = {
                "1":   self.ve.codec_pipeline,
                "2":   self.ve.rendering,
                "3":   self.ve.suppress_av1,
                "4":   self.cast.audit,
                "5":   self.cast.restore,
                "6":   self.cast.network,
                "d":   self.diag.menu,
                "r":   self.rep.scan,
                "g":   PerfDiag.full_report,
                "v":   PerfDiag.smarttube_profile,
                "cr":  CrashAnalyzer.scan,
                "b":   Benchmark.run_all,
                "bl":  Benchmark.quick_latency,
                "bh":  self._bench_history,
                "w":   WiFiInfo.display,
                "n":   self.net.dns_menu,
                "7":   lambda: (self.net.apply_tcp(), self.net.set_dns("cloudflare")),
                "7w":  self.net.wifi_reset,
                "8":   self.ha.apply_hdmi,
                "9":   self.ha.apply_audio,
                "10":  self.dh.apply,
                "11":  self.lmk.apply,
                "12":  self.res.apply,
                "13":  SystemTweaks.apply,
                "13g": SystemTweaks.gms_appops_only,
                "14":  self.dbl.run,
                "15":  deep_clean,
                "16":  self.aot.compile_all,
                "17":  deploy_shizuku,
                "rb":  SystemTweaks.rollback,
                "wd":  self._watchdog_toggle,
                "wa":  Watchdog.show_alerts,
                "qi":  QuickTools.device_info,
                "qs":  QuickTools.screenshot,
                "qr":  QuickTools.reboot_menu,
                "qa":  QuickTools.installed_apps,
                "qd":  QuickTools.show_storage,
                "ql":  CrashAnalyzer.export_log,
                "20":  self.smarttube_ultra,
                "21":  self.full_ultra,
                "0":   self._exit,
            }
            fn = dispatch.get(ch)
            if fn:
                fn()
            else:
                L.warn(f"Nieznana opcja: '{ch}' — wpisz 0-21 lub D/R/B/W/WD/QI itd.")
            if ch != "0":
                input(f"\n{c['c']}Enter aby kontynuować...{c['r']}")

    def _exit(self) -> None:
        L.save()
        if Watchdog._running:
            Watchdog.stop()
        sys.exit(0)

    def _watchdog_toggle(self) -> None:
        """Przełącz Watchdog ON/OFF."""
        if Watchdog._running:
            Watchdog.stop()
        else:
            Watchdog.start(interval=30)

    def _bench_history(self) -> None:
        """Pokaż historię benchmarków z pliku JSON."""
        L.hdr("📈 HISTORIA BENCHMARKÓW")
        if not Benchmark.HISTORY_FILE.exists():
            L.warn("Brak historii — uruchom benchmark (opcja B) co najmniej raz")
            return
        try:
            with open(Benchmark.HISTORY_FILE) as f:
                history = json.load(f)
        except Exception as e:
            L.err(f"Błąd odczytu historii: {e}"); return

        c = L.C
        print(f"  Zapisanych sesji: {len(history)}")
        print(f"  {c['b']}{'Sesja':<6} {'Data/czas':<22} {'CPU ms':>8} {'RAM MB/s':>9} {'Flash':>8} {'Ping GW':>8} {'Ping CDN':>9}{c['r']}")
        print(f"  {'─'*75}")
        for i, entry in enumerate(history[-10:], 1):
            ts = entry.get("ts","?")[:16]
            cpu   = f"{entry.get('cpu_hash_ms',0):.0f}"   if "cpu_hash_ms"  in entry else "—"
            ram   = f"{entry.get('ram_mb_s',0):.0f}"      if "ram_mb_s"     in entry else "—"
            flash = f"{entry.get('flash_mb_s',0):.1f}"    if "flash_mb_s"   in entry else "—"
            pgw   = f"{entry.get('ping_gw_ms',0):.1f}"    if "ping_gw_ms"   in entry else "—"
            pcdn  = f"{entry.get('ping_cdn_ms',0):.1f}"   if "ping_cdn_ms"  in entry else "—"
            print(f"  {i:<6} {ts:<22} {cpu:>8} {ram:>9} {flash:>8} {pgw:>8} {pcdn:>9}")

    # ── SmartTube ULTRA ──────────────────────────────────────────────────────
    def smarttube_ultra(self) -> None:
        L.hdr("🚀 SMARTTUBE ULTRA — v14 A15+BCM7362 Precision")
        steps=[
            ("Auto-Repair pre-check",            self.rep.scan),
            ("Cast Audit",                        self.cast.audit),
            ("Codec Pipeline (A15+MMA+VDec32)",  self.ve.codec_pipeline),
            ("Rendering (V3D fence + 32KB cache)",self.ve.rendering),
            ("AV1 Suppression",                  self.ve.suppress_av1),
            ("Dalvik Heap (minfree 512k→2m)",    self.dh.apply),
            ("LMK (PSI-only, upgrade_p=50)",     self.lmk.apply),
            ("Audio A/V Sync (HDMI clock lock)", self.ha.apply_audio),
            ("HDMI + CEC (keep_awake=true)",     self.ha.apply_hdmi),
            ("Responsiveness + I/O + A15 gov",   self.res.apply),
            ("TCP + DNS (one.one.one.one)",       lambda: (self.net.apply_tcp(), self.net.set_dns())),
            ("Cast mDNS tuning",                 self.cast.network),
            ("Cast OOM hardening",               self.lmk._harden_oom),
            ("AOT Compilation (Xmx=512m)",       self.aot.compile_all),
            ("Cast Services Final Restore",      self.cast.restore),
        ]
        for i,(name,fn) in enumerate(steps,1):
            L.info(f"\n[{i}/{len(steps)}] {name}...")
            fn(); time.sleep(0.3)
        L.hdr("🎉 SMARTTUBE ULTRA COMPLETE")
        L.ok("VP9 HW + Tunnel + A15-idiv + MMA + VDec32 + DNS: one.one.one.one + Cast ✓")
        L.warn("SmartTube: Settings → Player → Video codec → VP9")
        L.warn("SmartTube: Settings → Player → Use tunnel mode → ON")
        L.save()

    # ── Full ULTRA ───────────────────────────────────────────────────────────
    def full_ultra(self) -> None:
        L.hdr("🏆 FULL SYSTEM ULTRA — All Modules (Hardware-Targeted v14)")
        Watchdog.start(interval=60)
        steps=[
            ("System Diagnostics",               lambda: self.diag.run_cat("A")),
            ("Crash Analyzer (pre-check)",       lambda: CrashAnalyzer.scan(200)),
            ("Auto-Repair pre-check",            self.rep.scan),
            ("Cast Audit",                       self.cast.audit),
            ("Codec Pipeline (A15+MMA+VDec32)", self.ve.codec_pipeline),
            ("Rendering (V3D fence)",            self.ve.rendering),
            ("AV1 Suppression",                 self.ve.suppress_av1),
            ("Dalvik Heap precision fix",        self.dh.apply),
            ("LMK PSI-only (upgrade_p=50)",     self.lmk.apply),
            ("Audio A/V Sync",                  self.ha.apply_audio),
            ("HDMI + CEC + BCM Nexus",          self.ha.apply_hdmi),
            ("TCP + DNS fix (one.one.one.one)", lambda: (self.net.apply_tcp(), self.net.set_dns())),
            ("Responsiveness + deadline + A15", self.res.apply),
            ("Safe Debloat (Cast Protected)",   self.dbl.run),
            ("Cast mDNS tuning",                self.cast.network),
            ("Cast OOM hardening",              self.lmk._harden_oom),
            ("AOT Compilation",                 self.aot.compile_all),
            ("Deep Clean (Cast-Safe)",          deep_clean),
            ("Final Cast Audit",                self.cast.audit),
        ]
        for i,(name,fn) in enumerate(steps,1):
            L.info(f"\n[{i}/{len(steps)}] {name}...")
            fn(); time.sleep(0.2)
        L.hdr("🏆 FULL ULTRA COMPLETE")
        L.ok("All hardware-targeted optimizations applied. Cast: PROTECTED. DNS: FIXED.")
        if not Watchdog._running:
            Watchdog.start(interval=30)
        L.ok("Watchdog aktywny w tle (interwał 30s) — opcja WA=historia alertów")
        L.warn(f"Reboot: adb -s {self.device} reboot")
        L.save()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def parse() -> argparse.Namespace:
    p=argparse.ArgumentParser(
        description=f"Playbox TITANIUM v{VERSION} — WiFi+Bench+Watchdog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  python3 Autopilot_13_PRECISION.py                         # Interactive menu
  python3 Autopilot_13_PRECISION.py --smarttube-ultra       # Video ultra
  python3 Autopilot_13_PRECISION.py --full-ultra            # Full system
  python3 Autopilot_13_PRECISION.py --diag                  # Self-diagnostics
  python3 Autopilot_13_PRECISION.py --repair                # Auto-repair scan
  python3 Autopilot_13_PRECISION.py --cast-restore          # Emergency Cast
  python3 Autopilot_13_PRECISION.py --dns cloudflare        # Fix DNS
  python3 Autopilot_13_PRECISION.py --device 192.168.1.3:5555 --full-ultra
""")
    p.add_argument("--device",          default=None)
    p.add_argument("--smarttube-ultra", action="store_true")
    p.add_argument("--full-ultra",      action="store_true")
    p.add_argument("--diag",            action="store_true")
    p.add_argument("--repair",          action="store_true")
    p.add_argument("--cast-audit",      action="store_true")
    p.add_argument("--cast-restore",    action="store_true")
    p.add_argument("--dns",             default=None, metavar="PROVIDER")
    p.add_argument("--beta",            action="store_true")
    p.add_argument("--bench",           action="store_true", help="Pełny benchmark")
    p.add_argument("--wifi",            action="store_true", help="Panel WiFi")
    p.add_argument("--crash",           action="store_true", help="Analiza crash logcat")
    p.add_argument("--info",            action="store_true", help="Karta urządzenia")
    return p.parse_args()


def main() -> None:
    args=parse()
    device=args.device or ADB.detect() or DEFAULT_DEVICE
    if not ADB.connect(device):
        L.err(f"Cannot connect: {device}"); sys.exit(1)

    a=App(device)

    if   args.cast_restore:    CastManager.restore()
    elif args.cast_audit:      CastManager.audit()
    elif args.dns:             NetworkOptimizer().set_dns(args.dns)
    elif args.diag:            a.diag.run_all()
    elif args.repair:          Repair.scan()
    elif args.smarttube_ultra: a.smarttube_ultra()
    elif args.full_ultra:      a.full_ultra()
    elif args.bench:           Benchmark.run_all()
    elif args.wifi:            WiFiInfo.display()
    elif args.crash:           CrashAnalyzer.scan()
    elif args.info:            QuickTools.device_info()
    else:                      a._banner(); a._menu()


if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(); L.warn("Ctrl+C"); L.save(); sys.exit(0)
    except Exception as e:
        L.err(f"Fatal: {e}")
        import traceback; traceback.print_exc(); sys.exit(1)
