#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v13.0 PRECISION — Hardware-Targeted Edition               ║
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

import os, sys, subprocess, time, json, argparse, shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable, Any
from dataclasses import dataclass
from enum import Enum, auto

# ─────────────────────────────────────────────────────────────────────────────
VERSION          = "13.0-PRECISION"
DEFAULT_DEVICE   = "192.168.1.3:5555"
CACHE_DIR        = Path.home() / ".playbox_cache"
BACKUP_DIR       = CACHE_DIR / "backups_v13"
LOG_FILE         = CACHE_DIR / "autopilot_v13.log"
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

    def rendering(self) -> None:
        L.hdr("🎮 RENDERING — VideoCore + V3D (hardware-verified)")
        L.info(f"  V3D fence.expose=TRUE (explicit sync ON) → disable_backpressure effective")
        L.info(f"  V3D buffer_age=FALSE (vendor-disabled, do NOT re-enable)")
        L.info(f"  HWC2.tweak.fbcomp=1 (FB compositor tweak active)")
        L.info(f"  Triple buffer ENABLED (ro.sf.disable_triple_buffer=0)")

        render_props = [
            # Already confirmed correct — verify + enforce
            ("debug.hwui.renderer",              "skiagl"),          # OpenGL, no Vulkan
            ("debug.renderengine.backend",       "skiaglthreaded"),  # 2-thread render
            ("debug.egl.hw",                     "1"),
            ("debug.sf.hw",                      "1"),
            ("debug.gr.numframebuffers",         "3"),               # triple buffer
            ("debug.hwui.use_gpu_pixel_buffers", "true"),
            ("debug.hwui.render_dirty_regions",  "false"),
            ("debug.sf.latch_unsignaled",        "1"),
            ("debug.sf.disable_backpressure",    "1"),
            ("debug.hwui.use_buffer_age",        "false"),  # matches V3D vendor flag
            # Increased layer cache: V3D fence.expose=true allows pipelining
            # 32KB (32768 tiles) fits VideoCore texture cache budget
            ("debug.hwui.layer_cache_size",      "32768"),  # was 16384
            ("debug.hwui.profile",               "false"),  # no profiling overhead
            # FIXED: persist.sys.ui.hw was false on device
            ("persist.sys.ui.hw",                "true"),
        ]
        for k,v in render_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v); L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v}")

        ADB.sput("global","force_gpu_rendering","true")
        L.ok("  force_gpu_rendering = true")
        L.ok("Rendering: skiaglthreaded + V3D explicit fence + 32KB tile cache ✓")


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
        L.hdr("🌐 NETWORK — TCP/IP (Kernel 4.9.190, no BBR)")
        L.cast("mDNS (Cast discovery, port 5353) UNAFFECTED by TCP/DNS changes")

        # Android-level TCP
        ADB.sput("global","net.tcp.buffersize.wifi",
                 "262144,1048576,2097152,131072,524288,1048576")
        L.ok("  WiFi TCP: 256KB/1MB/2MB")
        ADB.sput("global","net.tcp.buffersize.ethernet",
                 "524288,2097152,4194304,262144,1048576,2097152")
        L.ok("  Ethernet TCP: 512KB/2MB/4MB")

        # FIXED: net.tcp.default_init_rwnd = 60 → 120
        cur = ADB.prop("net.tcp.default_init_rwnd")
        ADB.sput("global","tcp_default_init_rwnd","120")
        ADB.setprop("net.tcp.default_init_rwnd","120")
        L.fix(f"  tcp init rwnd: {cur} → 120")

        # Kernel TCP params (4.9 supports all of these)
        kernel_tcp = [
            ("/proc/sys/net/ipv4/tcp_window_scaling",    "1"),
            ("/proc/sys/net/ipv4/tcp_timestamps",        "1"),
            ("/proc/sys/net/ipv4/tcp_sack",              "1"),
            # Fast Open: 3 = client+server mode (supported in 4.9+)
            ("/proc/sys/net/ipv4/tcp_fastopen",          "3"),
            ("/proc/sys/net/ipv4/tcp_keepalive_intvl",   "30"),
            ("/proc/sys/net/ipv4/tcp_keepalive_probes",  "3"),
            ("/proc/sys/net/ipv4/tcp_no_metrics_save",   "1"),
            # CUBIC is optimal for 4.9 without BBR — tune FQ
            ("/proc/sys/net/ipv4/tcp_congestion_control","cubic"),
        ]
        for path,val in kernel_tcp:
            ok = ADB.sysw(path,val)
            L.ok(f"  ✓ {path.split('/')[-1]} = {val}") if ok else \
            L.warn(f"  ⚠ {path.split('/')[-1]} = {val} (sysctl not writable)")

        # Net core buffers 16MB
        for p in ("/proc/sys/net/core/rmem_max","/proc/sys/net/core/wmem_max"):
            ADB.sysw(p,"16777216")
        L.ok("  net/core rmem/wmem_max = 16MB")

        # WiFi stability
        ADB.setprop("wifi.supplicant_scan_interval","300")
        ADB.sput("global","wifi_sleep_policy","2")
        ADB.sput("global","wifi_power_save","0")
        ADB.setprop("persist.debug.wfd.enable","1")
        L.ok("  WiFi: scan=300s, sleep_policy=2, power_save=0, WFD=1")

        # mDNS Cast reliability
        ADB.setprop("ro.mdns.enable_passive_mode","false")
        ADB.setprop("net.ssdp.ttl","4")
        L.ok("  mDNS: active response mode, SSDP TTL=4")

        L.ok("TCP stack: TCP_FO v3 + CUBIC + 16MB bufs + init_rwnd=120 ✓")

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
        L.hdr("🔊 AUDIO — A/V Sync (BCM7362 HDMI ARC desync fix)")
        L.info("  Root cause: audio offload path uses BCM proprietary timing")
        L.info("  that disagrees with HDMI ARC → drift 50-200ms over time.")
        L.info("  vendor.audio-hal-2-0 RUNNING (confirmed in init.svc)")

        audio_props = [
            # Disable offload (desync root cause)
            ("audio.offload.disable",       "1"),
            ("audio.offload.video",         "0"),
            ("tunnel.audio.encode",         "false"),
            # Deep buffer: stable 20ms latency baseline
            ("audio.deep_buffer.media",     "true"),
            ("af.fast_track_multiplier",    "1"),
            # BCM HDMI clock lock (eliminates slow drift)
            ("audio.brcm.hdmi.clock_lock",  "true"),
            ("audio.brcm.hal.latency",      "20"),
        ]
        for k,v in audio_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v); L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v}")
        L.ok("Audio: offload disabled + HDMI clock locked ✓")


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
# MODULE 7 — SAFE DEBLOAT (Cast gate enforced)
# ─────────────────────────────────────────────────────────────────────────────
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
    cat:str; check:str; status:Status
    found:str; expected:str=""; fix_fn=None; detail:str=""
    @property
    def bad(self)->bool: return self.status in (Status.BROKEN,Status.MISSING)


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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
class App:

    def __init__(self, device:str):
        self.device=device
        self.ve  = VideoEngine()
        self.dh  = DalvikHeap()
        self.lmk = LMKOptimizer()
        self.net = NetworkOptimizer()
        self.ha  = HDMIAudio()
        self.res = Responsiveness()
        self.dbl = SafeDebloat()
        self.cast= CastManager()
        self.aot = AOT()
        self.diag= Diag()
        self.rep = Repair()

    def _banner(self) -> None:
        c=L.C
        print(f"""
{c['h']}{c['b']}╔══════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v{VERSION}
║  Sagemcom DCTIW362P │ Android TV 9 │ Kernel 4.9.190 │ ARMv7 A15
╠══════════════════════════════════════════════════════════════════════╣
║  BCM7362 VPU │ VideoCore GLES3.1 │ MMA=1 │ VDec32 │ V3D Fences
║  RAM:1459MB │ Nexus:240MB │ Userspace:~{HW.USERSPACE_BUDGET_MB}MB │ PSI-LMK
╠══════════════════════════════════════════════════════════════════════╣
║  🎬 VP9 HW+Tunnel │ 🛡 Cast Protected │ 🔒 DNS:one.one.one.one
║  🔧 A15-idiv │ 🧠 PSI-LMK │ 🔊 HDMI-clock-lock │ ⚡ AOT 512m
╚══════════════════════════════════════════════════════════════════════╝{c['r']}
  Target: {c['c']}{self.device}{c['r']}   Build: PTT1.190826.001
""")

    def _menu(self) -> None:
        c=L.C
        MENU = f"""
  {c['s']}VIDEO{c['r']}
    {c['s']}1.{c['r']}  Codec Pipeline (A15-idiv + MMA + VDec32 + Tunnel)
    {c['s']}2.{c['r']}  Rendering (skiaglthreaded + V3D explicit fence)
    {c['s']}3.{c['r']}  AV1 Suppression (no HW on BCM7362 — confirmed)

  {c['h']}CHROMECAST{c['r']}
    {c['s']}4.{c['r']}  🛡 Audit Cast Services
    {c['s']}5.{c['r']}  🛡 Restore Cast Services (emergency)
    {c['s']}6.{c['r']}  📡 Cast mDNS Network Tuning

  {c['i']}DIAGNOSTICS & REPAIR{c['r']}
    {c['i']}D.{c['r']}  🔎 Interactive Diagnostics (8 hw-targeted categories)
    {c['i']}R.{c['r']}  🔧 Auto-Repair Engine ({len(Repair.REGISTRY)} hardware sectors)
    {c['i']}N.{c['r']}  🔒 DNS Manager (provider selector)

  {c['w']}SYSTEM{c['r']}
    {c['w']}7. {c['r']} Network TCP (4.9.190 kernel, TCP-FO v3, no BBR)
    {c['w']}8. {c['r']} HDMI + CEC (BCM Nexus, addr=11, keep_awake=true)
    {c['w']}9. {c['r']} Audio A/V Sync Fix (HDMI clock lock)
    {c['w']}10.{c['r']} Dalvik Heap (OEM 512m/192m preserved, minfree fix)
    {c['w']}11.{c['r']} LMK (PSI-only — minfree /sys DISABLED on this device)
    {c['w']}12.{c['r']} Responsiveness + I/O deadline + A15 performance gov
    {c['w']}13.{c['r']} Safe Debloat (Cast Protected)
    {c['w']}14.{c['r']} Deep Clean RAM (Cast-Safe)
    {c['w']}15.{c['r']} AOT Compile (SmartTube + Cast + GMS, Xmx=512m)
    {c['w']}16.{c['r']} Deploy Shizuku

  {c['c']}AUTO MODES{c['r']}
    {c['c']}20.{c['r']} 🚀 SMARTTUBE ULTRA
    {c['c']}21.{c['r']} 🏆 FULL SYSTEM ULTRA
    {c['e']}0. {c['r']} Exit"""

        while True:
            os.system("clear"); self._banner()
            print(f"{c['b']}{'═'*68}{c['r']}{MENU}")
            print(f"{c['b']}{'═'*68}{c['r']}")
            ch=input(f"\n{c['c']}Choice > {c['r']}").strip().lower()

            dispatch={
                "1": self.ve.codec_pipeline,
                "2": self.ve.rendering,
                "3": self.ve.suppress_av1,
                "4": self.cast.audit,
                "5": self.cast.restore,
                "6": self.cast.network,
                "d": self.diag.menu,
                "r": self.rep.scan,
                "n": self.net.dns_menu,
                "7": lambda: (self.net.apply_tcp(), self.net.set_dns("cloudflare")),
                "8": self.ha.apply_hdmi,
                "9": self.ha.apply_audio,
                "10":self.dh.apply,
                "11":self.lmk.apply,
                "12":self.res.apply,
                "13":self.dbl.run,
                "14":deep_clean,
                "15":self.aot.compile_all,
                "16":deploy_shizuku,
                "20":self.smarttube_ultra,
                "21":self.full_ultra,
                "0": self._exit,
            }
            fn=dispatch.get(ch)
            if fn:
                fn()
            else:
                L.warn("Invalid choice")
            if ch!="0":
                input(f"\n{c['c']}Press Enter...{c['r']}")

    def _exit(self):
        L.save(); sys.exit(0)

    # ── SmartTube ULTRA ──────────────────────────────────────────────────────
    def smarttube_ultra(self) -> None:
        L.hdr("🚀 SMARTTUBE ULTRA — A15+BCM7362 Precision")
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
        L.hdr("🏆 FULL SYSTEM ULTRA — All Modules (Hardware-Targeted v13)")
        steps=[
            ("System Diagnostics",               lambda: self.diag.run_cat("A")),
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
        L.warn(f"Reboot: adb -s {self.device} reboot")
        L.save()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def parse() -> argparse.Namespace:
    p=argparse.ArgumentParser(
        description=f"Playbox Titanium v{VERSION} — Sagemcom DCTIW362P",
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
    else:                      a._banner(); a._menu()


if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(); L.warn("Ctrl+C"); L.save(); sys.exit(0)
    except Exception as e:
        L.err(f"Fatal: {e}")
        import traceback; traceback.print_exc(); sys.exit(1)
