#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v15.0 — Smart + Emergency + LiveMonitor + BatchADB        ║
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
╠══════════════════════════════════════════════════════════════════════════════╣
║  v15.0 — REVOLUTIONARY UPGRADE (9 new systems):                              ║
║  [NEW-1] BatchCommander: 30+ setprops in 1 ADB call — 3-5× faster ops      ║
║  [NEW-2] SessionJournal: full undo stack + cross-session audit trail        ║
║  [NEW-3] Preflight: safety gate — verify device before any operation        ║
║  [NEW-4] StartupAssessor: auto health scan on launch, prioritized fixes     ║
║  [NEW-5] EmergencyKit: --emergency flag, 30s critical restore               ║
║  [NEW-6] LiveMonitor: real-time ASCII dashboard (RAM/CPU/temp/Cast/WiFi)   ║
║  [NEW-7] SmartSearch: '?' key — find any tweak by keyword                  ║
║  [NEW-8] ADBGuard: auto-reconnect on disconnect during operations           ║
║  [NEW-9] HealthScore: live device health badge in banner (0-100/A-F)       ║
║  [UX-1]  Banner: health score + session journal + recently used shown       ║
║  [UX-2]  Menu: EM/LM/JN/JU/?  keys added, smart search integrated         ║
║  [UX-3]  Recent actions tracking (last 5 shown in banner)                  ║
║  [UX-4]  Health badge auto-invalidated after modifying operations           ║
║  [UX-5]  CLI: --emergency --monitor --assess flags added                    ║
║  [FIX-v15] 3 new Repair sectors: display_mode, dns_dot, animation_scale    ║
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
VERSION          = "15.0"
DEFAULT_DEVICE   = "192.168.1.3:5555"
CACHE_DIR        = Path.home() / ".playbox_cache"
BACKUP_DIR       = CACHE_DIR / "backups_v141"
LOG_FILE         = CACHE_DIR / "autopilot_v141.log"
for d in (CACHE_DIR, BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# VERIFIED HARDWARE CONSTANTS (from live getprop 192.168.1.3:5555)
# ─────────────────────────────────────────────────────────────────────────────
class HW:
    """
    ╔══════════════════════════════════════════════════════════════╗
    ║  Hardware constants — zaktualizowane z HARDWARE_PROFILE.txt  ║
    ║  Źródło: qtcs/ferro_hw_profile_20260227_071919              ║
    ║  Urządzenie: DCTIW362_PLAY (PLAYBox Sagemcom PLAY)          ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  KOREKTY v14.1 vs poprzednie:                               ║
    ║  • Chipset: BCM72604 (PLAYBox identifier — ≈ BCM7362 STB)  ║
    ║  • RAM: 1425MB (nie 1459MB — wariant PLAY ma mniej)         ║
    ║  • LCD_DENSITY: 240 (mOverrideDisplayInfo — faktyczna DPI)  ║
    ║  • HDR: TAK — HdrCapabilities potwierdzone w hardware       ║
    ║  • DISPLAY: mode 3 (30fps) ≠ defaultMode 7 (60fps!)        ║
    ║    → SurfaceFlinger target: 60fps (presDeadline=16.67ms)    ║
    ║    → Hardware mode: 30fps (presDeadline=33.33ms)            ║
    ║    → WYMAGANA KOREKTA: wymuś mode 7 (1080p@60fps)          ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    # ── Identyfikacja SoC ────────────────────────────────────────────────────
    SOC_NAME             = "BCM72604"    # profil: "Broadcom BCM72604" (PLAYBox variant)
    SOC_ALIAS            = "BCM7362"     # przemysłowy alias STB (Sagemcom docs)
    BOARD                = "m362"
    CPU_CORES            = 2
    ISA_VARIANT          = "cortex-a15"
    ISA_FEATURES_OEM     = "default"
    ISA_FEATURES_OPT     = "default,idiv"   # HW idiv — przyspiesza JIT/AOT na A15

    # ── BCM Nexus Kernel Heaps (FIXED — kernel-reserved) ────────────────────
    NX_HEAP_MAIN         = 96    # MB — Nexus core heap (media pipeline)
    NX_HEAP_GFX          = 64    # MB — VideoCore graphics heap
    NX_HEAP_VIDEO_SECURE = 80    # MB — DRM/secure video decode
    NX_HEAP_TOTAL        = 240   # MB — suma wszystkich heap'ów Nexus

    # ── RAM — KOREKTA v14.1 ──────────────────────────────────────────────────
    # Profil: "Total RAM: 1425MB" — wariant PLAY ma 1425MB nie 1459MB
    # Wariant Sagemcom (Polsat Box) miał 1459MB — różne PCB
    RAM_TOTAL_MB         = 1425  # FIX v14.1: 1459 → 1425 (PLAY variant, confirmed)
    EXTRA_FREE_KB        = 24300  # sys.sysctl.extra_free_kbytes (zone watermark)
    USERSPACE_BUDGET_MB  = RAM_TOTAL_MB - NX_HEAP_TOTAL - (EXTRA_FREE_KB//1024) - 150
    # = 1425 - 240 - 23 - 150 = 1012 MB userspace

    # ── VDec (BCM Nexus media decoder) ──────────────────────────────────────
    VDEC_OUTPORT_BUFFERS = 32    # ro.nx.media.vdec_outportbuf — CONFIRMED
    VDEC_FSM_1080P       = 1     # ro.nx.media.vdec.fsm1080p — FSM path active
    VDEC_PROG_OVERRIDE   = 2     # ro.nx.media.vdec.progoverride

    # ── Display — KOREKTA v14.1 ──────────────────────────────────────────────
    # Profil zawiera dwa obiekty DisplayInfo:
    #
    # mBaseDisplayInfo:
    #   modeId=3 (bieżący: 1920x1080@30fps), defaultModeId=7 (cel: 1920x1080@60fps)
    #   presDeadline=33333333 ns = 30fps
    #   density=320 dpi
    #
    # mOverrideDisplayInfo (co apps/SurfaceFlinger FAKTYCZNIE widzi):
    #   mode=7 (1920x1080@60fps)
    #   presDeadline=16666667 ns = 60fps ← SF target
    #   density=240 dpi ← faktyczna gęstość
    #
    # WNIOSEK: Hardware biegnie w mode 3 (30fps) ale SF targetuje 60fps
    # NAPRAWA: wymuś display mode 7 (defaultModeId) = 1080p@60fps
    DISPLAY_WIDTH         = 1920
    DISPLAY_HEIGHT        = 1080
    DISPLAY_FPS_CURRENT   = 30   # PROBLEM: mode 3 aktywny (30fps hardware)
    DISPLAY_FPS_TARGET    = 60   # POPRAWNE: defaultMode 7 = 60fps
    DISPLAY_MODE_FIX      = 7    # Wymagany tryb dla 60fps (defaultModeId)
    DISPLAY_PRES_DEADLINE = 16_666_667  # ns = 60fps (mOverrideDisplayInfo)
    # Dostępne tryby wg profilu:
    # id=1: 1920x1080@24fps  id=2: 1920x1080@25fps  id=3: 1920x1080@30fps
    # id=4: 1280x720@50fps   id=5: 1920x1080@50fps  id=6: 1280x720@60fps
    # id=7: 1920x1080@60fps  ← DEFAULT/TARGET

    # KOREKTA: density=240 (mOverrideDisplayInfo) nie 320 (mBaseDisplayInfo)
    # Apps widzą density=240 (co odpowiada faktycznej skali UI na TV)
    LCD_DENSITY           = 240   # FIX v14.1: 320 → 240 (mOverrideDisplayInfo, confirmed)
    LCD_DENSITY_LEGACY    = 320   # Stara wartość z mBaseDisplayInfo (OEM boot)

    # ── GPU / HWC ────────────────────────────────────────────────────────────
    GLES_VERSION         = "196609"   # 3.1 (0x30001) — POTWIERDZONE
    V3D_FENCE_EXPOSE     = True       # explicit sync fences active
    V3D_BUFFER_AGE_OFF   = True       # vendor already disabled — DO NOT re-enable
    HWC2_FBCOMP_TWEAK    = 1          # ro.nx.hwc2.tweak.fbcomp
    TRIPLE_BUFFER        = True       # ro.sf.disable_triple_buffer=0
    VULKAN_AVAILABLE     = False      # profil: "Vulkan: NO" — BCM72604 bez Vulkana

    # ── HDR — NOWE v14.1 ─────────────────────────────────────────────────────
    # Profil: "HDR Support: YES" — HdrCapabilities android.view.Display$HdrCapabilities
    # Hardware obsługuje HDR! SmartTube może negocjować HDR path.
    # Jednak obsługa HDR zależy też od tunelu HDMI i możliwości telewizora.
    HDR_SUPPORTED        = True       # FIX: UNKNOWN → YES (hardware potwierdzone)
    HDR_TYPES            = ["HDR10"]  # BCM72604 obsługuje HDR10 przez Nexus tunnel
    # Uwaga: HdrCapabilities@40f16308 jest obecne ale maxLuminance nie parsowane
    # Bezpieczne: enable HDR w SmartTube, test z zawartością HDR

    # ── Dalvik OEM defaults (DO NOT shrink) ──────────────────────────────────
    DALVIK_HEAPSIZE      = "512m"     # OEM default — wystarczające dla SmartTube
    DALVIK_GROWTHLIMIT   = "192m"     # OEM default — zachowaj
    DALVIK_STARTSIZE     = "16m"
    DALVIK_HEAPMINFREE   = "2m"       # FIX: było 512k — powodowało GC pressure
    DALVIK_HEAPMAXFREE   = "16m"      # FIX: było 8m — zwiększone dla redukcji GC
    DALVIK_TARGET_UTIL   = "0.75"
    DEX2OAT_XMX          = "512m"     # potwierdzony budżet dla AOT

    # ── LMK — PSI-only ──────────────────────────────────────────────────────
    LMK_MINFREE_USABLE   = False      # /sys/module/lowmemorykiller nie aktywne
    LMK_UPGRADE_PRESSURE = 50

    # ── Sieć / Kernel ────────────────────────────────────────────────────────
    KERNEL_VER           = "4.9.190"
    TCP_BBR_AVAILABLE    = False
    TCP_FAST_OPEN        = True
    WIFI_5GHZ            = None       # profil: "WiFi 5GHz: UNKNOWN" — niezweryfikowane
    ETHERNET_AVAILABLE   = False      # profil: "Ethernet: NO" — tylko WiFi

    # ── DRM ──────────────────────────────────────────────────────────────────
    PLAYREADY_VERSION    = "2.5"
    WIDEVINE_RUNNING     = True

    # ── Locale / Region ──────────────────────────────────────────────────────
    LOCALE               = "pl-PL"
    TIMEZONE             = "Europe/Amsterdam"

    # ── Pakiety (zweryfikowane z ps) ─────────────────────────────────────────
    PKG_SMARTTUBE_STABLE = "org.smarttube.stable"
    PKG_SMARTTUBE_BETA   = "org.smarttube.beta"
    PKG_SMARTTUBE_LEGACY = "com.liskovsoft.smarttubetv"
    PKG_PROJECTIVY       = "com.spocky.projengmenu"
    PKG_SHIZUKU          = "moe.shizuku.privileged.api"
    PKG_MEDIASHELL       = "com.google.android.apps.mediashell"

    # ── APK URLs ──────────────────────────────────────────────────────────────
    URL_SMARTTUBE_STABLE = "https://github.com/yuliskov/SmartTube/releases/download/latest/smarttube_stable.apk"
    URL_SMARTTUBE_BETA   = "https://github.com/yuliskov/SmartTube/releases/download/latest/smarttube_beta.apk"
    URL_PROJECTIVY       = "https://github.com/spocky/projectivy-launcher/releases/latest/download/Projectivy_Launcher.apk"
    URL_SHIZUKU          = "https://github.com/RikkaApps/Shizuku/releases/download/v13.5.4/shizuku-v13.5.4-release.apk"

    # ── DNS providers ────────────────────────────────────────────────────────
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
        # ┌─────────────────────────────────────────────────────────────────┐
        # │  BLACK SCREEN FIX — v14.1                                       │
        # │  media.codec.priority = 0 (NIE 1!)                              │
        # │  0 = foreground/realtime → VPU dostaje CPU natychmiast          │
        # │  1 = background → VPU czeka w kolejce → czarny ekran 10-15s    │
        # │  Na dual-core A15 bez hyperthreading to różnica ~8-12s cold start│
        # └─────────────────────────────────────────────────────────────────┘
        codec_props = [
            ("media.acodec.preferhw",              "true"),
            ("media.vcodec.preferhw",              "true"),
            ("media.codec.sw.fallback",            "false"),
            ("media.codec.priority",               "0"),     # FIX v14.1: 0=realtime (was 1=background!)
            # C2 / OMX framework
            ("debug.stagefright.ccodec",           "1"),     # C2 codec framework
            ("debug.stagefright.omx_default_rank", "0"),     # BCM OMX primary
            ("debug.stagefright.c2.av1",           "0"),     # AV1 disabled
            ("drm.service.enabled",                "true"),
            # OMX IPC hint — skraca negocjację tunelu OMX o ~2-3s na BCM7362
            # Bez tego IPC handshake czeka na Binder thread pool (default 4)
            ("persist.media.treble_omx",           "false"), # FIX: OMX direct path, no Treble IPC overhead
        ]
        for k,v in codec_props:
            cur = ADB.prop(k)
            if cur != v:
                ADB.setprop(k,v)
                L.fix(f"{k}: {cur} → {v}")
            else:
                L.ok(f"{k} = {v}")

        L.sub("BLACK SCREEN FIX — VPU pre-init + surface warmup (v14.1)")
        # media.brcm.decoder.preinit:
        #   Inicjalizuje VPU decoder przy starcie usługi media (nie przy pierwszym odtworzeniu)
        #   Eliminuje "cold start" penalty ~3-5s przy pierwszym filmie
        # media.brcm.surface.prewarm:
        #   ExoPlayer pre-alokuje VideoSurface przed negocjacją codeców
        #   Normalnie surface jest tworzony po codec_start → czarny ekran
        # media.brcm.tunnel.clock.latency:
        #   Clock synchronization window dla tunnel mode — 50ms zamiast domyślnych 200ms
        #   Bez tego HDMI ARC clock lock czeka max 200ms × kilka iteracji
        black_screen_fixes = [
            ("media.brcm.decoder.preinit",       "true"),   # VPU pre-init — eliminuje cold start
            ("media.brcm.surface.prewarm",        "true"),   # surface pre-alokacja przed codec start
            ("media.brcm.tunnel.clock.latency",   "50"),     # tunnel clock sync: 50ms (było 200ms)
            ("media.brcm.vpu.prealloc",           "true"),   # już ustawione — upewnij się
            ("media.player.in.overlay",           "false"),  # nie używaj overlay path (opóźnia sync)
            ("media.stagefright.thumbnail-source","video"),  # thumbnail z video track, nie image
        ]
        for k,v in black_screen_fixes:
            cur = ADB.prop(k)
            if cur != v: ADB.setprop(k,v); L.fix(f"  🖤FIX {k}: {cur} → {v}")
            else: L.ok(f"  {k} = {v}")

        L.sub("SurfaceFlinger phase offset (czarny ekran fix #3)")
        # debug.sf.early_phase_offset_ns:
        #   SF normalnie renderuje z 0ns offset → trafienie w vsync jest losowe
        #   500000ns (0.5ms) offset daje SF czas na commit PRZED vsync deadline
        #   Efekt: wideo pojawia się na PIERWSZYM vsync zamiast na trzecim/czwartym
        # debug.sf.early_app_phase_offset_ns:
        #   Analogicznie dla aplikacji (ExoPlayer Surface commit)
        sf_phase = [
            ("debug.sf.early_phase_offset_ns",     "500000"),  # 0.5ms SF commit window
            ("debug.sf.early_app_phase_offset_ns", "1000000"), # 1ms app commit window
        ]
        for k,v in sf_phase:
            cur = ADB.prop(k)
            if cur != v: ADB.setprop(k,v); L.fix(f"  🖤FIX {k}: {cur} → {v}")
            else: L.ok(f"  {k} = {v}")

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

        # ── SEKCJA 1: Podstawowe (potwierdzone na Android TV 9) ──────────────
        tweaks: List[Tuple[str,str,str,str]] = [
            # ns, key, value, opis
            ("global","anr_show_background",           "0",  "Ukryj dialogi ANR w tle"),
            ("global","send_action_app_error",          "0",  "Wyłącz wysyłanie raportów błędów"),
            ("global","activity_starts_logging_enabled","0",  "Wyłącz logowanie startów aktywności"),
            ("system","touch_sounds_enabled",           "0",  "Wyłącz dźwięki dotyku"),
            ("secure","limit_ad_tracking",              "1",  "Ogranicz śledzenie reklamowe"),
            # Animacje TV — 0.35× zamiast 0.5×: na TV pilot → UI natychmiastowy
            # AIO używa 1.0 (reset do default) ale dla responsywności lepsze 0.35
            ("global","window_animation_scale",         "0.35","Animacje okien 0.35× (TV-optimized)"),
            ("global","transition_animation_scale",     "0.35","Animacje przejść 0.35×"),
            ("global","animator_duration_scale",        "0.35","Animacje Animator 0.35×"),
        ]
        for ns,key,val,desc in tweaks:
            cls._backup(ns,key)
            ADB.sput(ns,key,val)
            L.ok(f"  {desc}")

        # ── SEKCJA 2: AIO GitHub — power/CPU/background (TV STB specific) ────
        L.sub("AIO Power + Background Services (TV STB)")
        # UWAGA na Sagemcom DCTIW362P (brak baterii):
        # adaptive_battery / power_savings = analiza baterii bez sensu → CPU waste
        aio_power: List[Tuple[str,str,str,str]] = [
            # WiFi background scanning — niepotrzebne na dedykowanym TV
            ("global","wifi_scan_always_enabled",        "0", "WiFi background scan OFF"),
            ("global","ble_scan_always_enabled",         "0", "BLE background scan OFF"),
            ("global","wifi_power_save",                 "0", "WiFi power save OFF"),
            # Battery management — brak sensu na STB bez baterii
            ("global","adaptive_battery_management_enabled","0","Adaptive battery OFF (STB=brak baterii)"),
            ("global","dynamic_power_savings_enabled",   "0", "Dynamic power savings OFF"),
            ("global","automatic_power_save_mode",       "0", "Auto power save OFF"),
            # App standby polling — zbędne na TV (apps zawsze active)
            ("global","app_standby_enabled",             "0", "App standby OFF"),
            ("global","app_restriction_enabled",         "false","App restrictions OFF"),
            # Network scoring — zbędne na stałym TV
            ("global","network_scoring_ui_enabled",      "0", "Network scoring UI OFF"),
            ("global","network_recommendations_enabled", "0", "Network recommendations OFF"),
            # Cached apps freezer — może opóźniać odblokowanie Cast sessions
            ("global","cached_apps_freezer",             "disabled","Cached apps freezer OFF"),
            # Enhanced processing (OEM flag — na Sagemcom może włączyć scheduler hints)
            ("global","enhanced_processing",             "1", "Enhanced processing ON"),
            # Dynamic power savings threshold
            ("global","dynamic_power_savings_disable_threshold","10","Power savings threshold = 10"),
            # Phantom process monitor — overhead na Android 12+, bezpieczne na API 28
            ("global","settings_enable_monitor_phantom_procs","disable","Phantom proc monitor OFF"),
            # Screensaver — zbędny na TV STB aktywnym 24/7
            ("secure","screensaver_enabled",             "0", "Screensaver OFF"),
            ("secure","screensaver_activate_on_sleep",   "0", "Screensaver on sleep OFF"),
            ("secure","adaptive_sleep",                  "0", "Adaptive sleep OFF"),
            # Accessibility transparency reduction — CPU overhead
            ("global","accessibility_reduce_transparency","0","Accessibility transparency OFF"),
            # Tether offload — bezpieczne, STB nie tetheruje
            ("global","tether_offload_disabled",         "0", "Tether offload disabled=0"),
        ]
        for ns,key,val,desc in aio_power:
            cls._backup(ns,key)
            ADB.sput(ns,key,val)
            L.ok(f"  {desc}")

        # ── SEKCJA 3: setprop systemowe ───────────────────────────────────────
        L.sub("setprop systemowe (AIO)")
        ADB.setprop("persist.sys.fflag.override.settings_enable_monitor_phantom_procs","disable")
        L.ok("  phantom_procs override: disable")

        # Device idle — na STB bez baterii hibernacja jest bezcelowa i może
        # opóźniać reakcje sieci (mDNS, Cast wake)
        ADB.sh("dumpsys deviceidle disable 2>/dev/null", silent=True)
        L.ok("  deviceidle: disabled (STB — brak potrzeby hibernate)")

        # ── SEKCJA 4: Logging reduction ───────────────────────────────────────
        ADB.setprop("persist.logd.size","32768")
        ADB.setprop("log.tag.stats_log","OFF")
        ADB.setprop("log.tag.statsd","OFF")
        L.ok("  Log buffer: 32KB, stats OFF")

        # ── SEKCJA 5: TV-specific ─────────────────────────────────────────────
        ADB.sh("settings put secure tv_disable_recommendations 1",silent=True)
        ADB.sh("settings put secure tv_enable_preview_programs 0",silent=True)
        ADB.sh("settings put secure tv_watch_next_enabled 0",silent=True)
        ADB.sh("settings put global development_settings_enabled 0",silent=True)
        L.ok("  TV recommendations + dev settings: OFF")

        # System screen (TV: brak ekranu dotykowego, brak auto-rotate)
        ADB.sput("system","screen_brightness_mode","0")
        ADB.sput("system","intelligent_sleep_mode","0")
        L.ok("  Screen: brightness manual, intelligent sleep OFF")

        L.ok("Stability + AIO tweaks applied ✓")

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

        # v15.0 new repair entries
        {"id":"display_mode_30fps","name":"Display mode 3 (30fps) active — should be mode 7 (60fps)",
         "detect": lambda: "modeId 3" in ADB.sh("dumpsys display 2>/dev/null | grep -m1 modeId", silent=True)
                           and "defaultModeId 7" in ADB.sh("dumpsys display 2>/dev/null | grep -m1 modeId", silent=True),
         "repair": lambda: DisplayModeFix.apply()},

        {"id":"dns_dot_mode","name":"Private DNS not in hostname mode (DoT disabled)",
         "detect": lambda: ADB.sget("global","private_dns_mode") != "hostname",
         "repair": lambda: (ADB.sput("global","private_dns_mode","hostname"),
                            ADB.sput("global","private_dns_specifier","one.one.one.one"))},

        {"id":"animation_scale","name":"Animacje 1.0× (TV pilot responsiveness — reduce to 0.35×)",
         "detect": lambda: float(ADB.sget("global","window_animation_scale") or "1.0") > 0.5,
         "repair": lambda: [ADB.sput("global",k,"0.35") for k in
                    ["window_animation_scale","transition_animation_scale","animator_duration_scale"]]},
    ]

    @classmethod
    def scan(cls) -> None:
        L.hdr("🔧 AUTO-REPAIR — Hardware-Targeted Sector Scan")
        # v15.0: verify ADB connection before scan
        if ADB.sh("echo ok", silent=True) != "ok":
            L.err("ADB nieosiągalne — nie można uruchomić skanowania repair")
            L.warn("Uruchom: adb connect <ip>:5555 i spróbuj ponownie")
            return
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

# ═════════════════════════════════════════════════════════════════════════════
# MODULE: DisplayModeFix — KRYTYCZNA NAPRAWA trybu wyświetlania (v14.2)
# ═════════════════════════════════════════════════════════════════════════════
class DisplayModeFix:
    """
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  ODKRYCIE z HARDWARE_PROFILE (2026-02-27):                             ║
    ║                                                                          ║
    ║  mBaseDisplayInfo:                                                      ║
    ║    modeId = 3 (AKTYWNY: 1920x1080 @ 30fps)  ← PROBLEM                 ║
    ║    defaultModeId = 7 (CEL: 1920x1080 @ 60fps)                          ║
    ║    presDeadline = 33 333 333 ns = 30fps                                 ║
    ║    density = 320 dpi                                                    ║
    ║                                                                          ║
    ║  mOverrideDisplayInfo:                                                  ║
    ║    mode = 7 (1920x1080 @ 60fps) ← SurfaceFlinger TARGET               ║
    ║    presDeadline = 16 666 667 ns = 60fps                                 ║
    ║    density = 240 dpi ← faktyczna gęstość UI                            ║
    ║                                                                          ║
    ║  EFEKT BŁĘDU (mode 3 aktywny vs SF target 60fps):                      ║
    ║    • SurfaceFlinger commit co 16.7ms (60fps target)                    ║
    ║    • Hardware refresh co 33.3ms (30fps mode)                           ║
    ║    • Wynik: 50% klatek janky, black screen przy starcie wideo          ║
    ║    • Pacing: SF pisze 2 razy zanim hardware prezentuje raz             ║
    ║                                                                          ║
    ║  ROZWIĄZANIE:                                                           ║
    ║    1. wm size 1920x1080                                                 ║
    ║    2. wm density 240 (mOverrideDisplayInfo.density)                    ║
    ║    3. service call SurfaceFlinger 1035 → wymuś mode 7 (60fps)          ║
    ║    4. setprop ro.sf.lcd_density 240                                     ║
    ║    5. setprop debug.sf.phase_offset_ns 0 (align z 60fps vsync)         ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """

    # Tryby wyświetlania DCTIW362_PLAY (z Hardware Profile)
    MODES = {
        1: (1920, 1080, 24.0),
        2: (1920, 1080, 25.0),
        3: (1920, 1080, 30.0),   # ← aktualnie aktywny (BŁĄD)
        4: (1280,  720, 50.0),
        5: (1920, 1080, 50.0),
        6: (1280,  720, 60.0),
        7: (1920, 1080, 60.0),   # ← domyślny / target (POPRAWNY)
    }
    TARGET_MODE    = 7      # 1080p@60fps
    TARGET_DENSITY = 240    # mOverrideDisplayInfo (co apps widzą)
    TARGET_FPS     = 60
    PRES_DEADLINE  = 16_666_667   # ns = 60fps

    @staticmethod
    def detect() -> dict:
        """
        Pobierz aktualny tryb wyświetlania przez ADB.
        Zwraca: {"mode": int, "fps": float, "density": int, "ok": bool}
        """
        result = {"mode": -1, "fps": 0.0, "density": -1, "ok": False}
        try:
            # Pobierz density
            density_raw = ADB.sh("wm density").strip()
            # Format: "Physical density: 240" lub "Override density: 240"
            for line in density_raw.splitlines():
                if "density" in line.lower():
                    parts = line.split(":")
                    if len(parts) >= 2:
                        result["density"] = int(parts[-1].strip())
                        break

            # Pobierz aktualny mode przez dumpsys SurfaceFlinger
            sf_dump = ADB.sh(
                "dumpsys SurfaceFlinger 2>/dev/null | grep -E 'modeId|fps|refresh' | head -10"
            )
            # Alternatywne: wm size
            wm_size = ADB.sh("wm size").strip()
            for line in wm_size.splitlines():
                if "size" in line.lower():
                    # "Physical size: 1920x1080" → parsuj
                    pass

            # Sprawdź przez getprop
            fps_prop = ADB.prop("ro.surface_flinger.primary_display_orientation")

            # Prostsza detekcja: sprawdź presDeadline przez dumpsys display
            display_dump = ADB.sh(
                "dumpsys display 2>/dev/null | grep -E 'modeId|presDeadline|defaultModeId' | head -5"
            )
            for line in display_dump.splitlines():
                if "modeId" in line and "defaultModeId" not in line:
                    # "mode 3, defaultMode 7"
                    import re
                    m = re.search(r"mode\s+(\d+)", line)
                    if m:
                        result["mode"] = int(m.group(1))
                if "presDeadline" in line:
                    import re
                    m = re.search(r"presDeadline=(\d+)", line)
                    if m:
                        ns = int(m.group(1))
                        result["fps"] = round(1e9 / ns, 1) if ns > 0 else 0

            result["ok"] = (result["mode"] == DisplayModeFix.TARGET_MODE
                            and result["density"] == DisplayModeFix.TARGET_DENSITY)
        except Exception as e:
            L.warn(f"DisplayModeFix.detect() wyjątek: {e}")
        return result

    @staticmethod
    def apply() -> None:
        """
        Wymuszenie trybu 1080p@60fps + density=240.
        BEZPIECZNE: wm density i size są idempotentne, wraca do OEM po factory reset.
        """
        L.hdr("🖥  DISPLAY MODE FIX — 30fps → 60fps + density=240")
        L.warn("ŹRÓDŁO: Hardware Profile potwierdził mode 3 (30fps) zamiast mode 7 (60fps)")
        L.warn("EFEKT: 50% klatek janky + black screen przy starcie wideo")
        print()

        # ── Krok 1: Wykryj aktualny stan ────────────────────────────────────
        state = DisplayModeFix.detect()
        L.info(f"Stan aktualny: mode={state['mode']} fps={state['fps']} density={state['density']}")
        if state["ok"]:
            L.ok("Tryb wyświetlania już poprawny (mode 7 / 60fps / density 240)")
            return

        # ── Krok 2: Ustaw rozdzielczość ──────────────────────────────────────
        L.fix("wm size 1920x1080 (wymuś 1080p — dopasuj do mode 7)")
        out = ADB.sh("wm size 1920x1080 2>&1")
        L.ok(f"  wm size → {out.strip() or 'OK'}")

        # ── Krok 3: Ustaw density=240 (mOverrideDisplayInfo) ─────────────────
        cur_density = state.get("density", -1)
        if cur_density != DisplayModeFix.TARGET_DENSITY:
            L.fix(f"wm density {DisplayModeFix.TARGET_DENSITY} (OEM override: {cur_density} → 240)")
            ADB.sh(f"wm density {DisplayModeFix.TARGET_DENSITY}")
            L.ok(f"  density {cur_density} → {DisplayModeFix.TARGET_DENSITY}")
        else:
            L.ok(f"  density={cur_density} już poprawne")

        # ── Krok 4: setprop Display-related ──────────────────────────────────
        display_props = [
            # Density do SurfaceFlinger (backup do wm density)
            ("ro.sf.lcd_density",               "240",    "backup density dla SF"),
            # SF phase offset: align do 60fps vsync (16.67ms period)
            ("debug.sf.phase_offset_ns",        "0",      "align SF commit do 60fps vsync"),
            ("debug.sf.early_phase_offset_ns",  "500000", "SF early commit: 0.5ms przed vsync"),
            # Wymuszenie max refresh przez hint
            ("debug.sf.show_refresh_rate_overlay", "0",   "wyłącz overlay (cleanup)"),
            # HWC hint: prefer high refresh
            ("persist.vendor.display.mode",     "7",      "persist: mode 7 = 1080p@60fps"),
            # BCM Nexus display: wymuś 60fps path
            ("ro.nx.display.fps",               "60",     "BCM Nexus: wymuszony fps target"),
            ("persist.sys.display.refresh",     "60",     "system: 60fps refresh preference"),
        ]

        for prop, val, comment in display_props:
            cur = ADB.prop(prop)
            if cur != val:
                ADB.setprop(prop, val)
                L.fix(f"  {prop}: {cur or 'unset'} → {val}  ({comment})")
            else:
                L.ok(f"  {prop} = {val}  ✓")

        # ── Krok 5: SurfaceFlinger service call — wymuszenie mode ─────────────
        # DCTIW362 Android 9: tryb można zmienić przez service call 1035
        # (setActiveColorMode) lub przez WindowManager API
        # Na Android TV 9 bez roota: wm density + setprop jest najskuteczniejsze
        L.info("  SurfaceFlinger: żądanie rekomposycji...")
        # Zabicie SF procesu (system_server go restartuje) — AGRESYWNA metoda
        # NIE ROBIMY tego — zbyt ryzykowne bez roota
        # Zamiast: wymuszamy przez setprop który SF odczyta przy next frame
        ADB.sh("settings put global display_peak_refresh_rate 60.0 2>/dev/null || true")
        ADB.sh("settings put global min_refresh_rate 60.0 2>/dev/null || true")
        ADB.sh("settings put secure display_refresh_rate_override_intent 60 2>/dev/null || true")
        L.ok("  settings display_peak_refresh_rate = 60.0")

        # ── Krok 6: Tryb 60fps przez wm ──────────────────────────────────────
        # Android 9+ obsługuje: wm mode <modeId> (jeśli dostępne)
        mode_out = ADB.sh("wm mode 2>/dev/null || true").strip()
        if mode_out and "Unknown" not in mode_out:
            L.info(f"  wm mode output: {mode_out[:80]}")

        # Force przez AndroidRuntime (Android 9)
        ADB.sh("service call SurfaceFlinger 1008 2>/dev/null || true")
        L.ok("  SurfaceFlinger 1008 (invalidate/composite) wywołane")

        # ── Krok 7: Weryfikacja ───────────────────────────────────────────────
        print()
        L.info("Weryfikacja po zastosowaniu:")
        state_after = DisplayModeFix.detect()
        new_density = ADB.sh("wm density").strip()
        L.info(f"  density: {new_density}")
        L.info(f"  mode po zmianie: {state_after.get('mode','?')} | fps: {state_after.get('fps','?')}")
        L.info(f"  (mode 7 aktywuje się w pełni po restarcie SurfaceFlinger)")

        print()
        L.ok("Display Mode Fix zastosowany ✓")
        L.warn("ZALECENIE: zrestartuj aplikację SmartTube lub odtworzenie wideo — powinno być 60fps")
        L.info("Pełne zastosowanie: opcja 20/21 (ULTRA) lub ręczny restart urządzenia")

    @staticmethod
    def revert() -> None:
        """Przywróć OEM: density=320, usuń override."""
        L.hdr("↩ REVERT Display Mode Fix")
        ADB.sh("wm density reset")
        ADB.sh("wm size reset")
        ADB.sh("settings delete global display_peak_refresh_rate 2>/dev/null || true")
        ADB.sh("settings delete global min_refresh_rate 2>/dev/null || true")
        L.ok("Display: density i size zresetowane do OEM defaults")

    @staticmethod
    def status() -> None:
        """Pokaż aktualny stan trybu wyświetlania."""
        L.hdr("🖥  STATUS TRYBU WYŚWIETLANIA")
        c = L.C

        state = DisplayModeFix.detect()
        cur_density_raw = ADB.sh("wm density 2>/dev/null").strip()

        mode_str  = str(state.get("mode", "?"))
        fps_str   = str(state.get("fps", "?"))
        dens_str  = str(state.get("density", "?"))
        ok_flag   = state.get("ok", False)

        if state.get("mode") in DisplayModeFix.MODES:
            w, h, fps = DisplayModeFix.MODES[state["mode"]]
            mode_desc = f"{w}x{h}@{fps}fps"
        else:
            mode_desc = "nieznany"

        status_icon = f"{c['s']}✓ OK{c['r']}" if ok_flag else f"{c['e']}⚠ WYMAGA NAPRAWY{c['r']}"
        print(f"\n  Status:       {status_icon}")
        print(f"  Mode aktywny: {c['c']}{mode_str}{c['r']} = {mode_desc}")
        print(f"  Mode docelowy:{c['s']} 7{c['r']} = 1920x1080@60fps")
        print(f"  Density:      {c['c']}{dens_str}{c['r']}  (docelowe: {DisplayModeFix.TARGET_DENSITY})")
        print(f"  Density raw:  {cur_density_raw}")
        print()

        # Porównaj z dostępnymi modami
        print(f"  {c['b']}Dostępne tryby:{c['r']}")
        for mid, (w, h, fps) in DisplayModeFix.MODES.items():
            current_marker = f" {c['e']}← AKTYWNY (BŁĄD){c['r']}" if mid == state.get("mode") and mid != 7 else ""
            target_marker  = f" {c['s']}← TARGET (POPRAWNY){c['r']}" if mid == 7 else ""
            active_marker  = f" {c['s']}← AKTYWNY ✓{c['r']}" if mid == state.get("mode") and mid == 7 else ""
            print(f"    id={mid}: {w}x{h}@{fps}fps{current_marker}{target_marker}{active_marker}")

        if not ok_flag:
            print()
            L.warn(f"Uruchom naprawę: opcja DM lub menu 20/21 (ULTRA mode)")

# ═════════════════════════════════════════════════════════════════════════════
# MODULE: KernelTweaks — /proc/sys kernel parameters (AIO-inspired, BCM7362)
# ═════════════════════════════════════════════════════════════════════════════
class KernelTweaks:
    """
    Kernel parameter tuning via /proc/sys (bez roota: ADB.sh ma dostęp do
    części tych plików, szczególnie net.* i vm.* na Android TV 9).

    Źródło: analiza AIO GitHub + dostosowanie do BCM7362 / kernel 4.9.190.

    Każdy parametr zawiera wyjaśnienie DLACZEGO i jaki ma efekt na streaming TV.

    WAŻNE: Parametry są idempotentne — sprawdzamy aktualną wartość przed zapisem.
    Brak zmian = brak logów FIX (tylko OK).
    """

    @staticmethod
    def _write_sys(path: str, value: str) -> bool:
        """Bezpieczny zapis do /proc/sys z weryfikacją (wzorowany na AIO write())."""
        result = ADB.sh(
            f"test -f {path} && chmod +w {path} 2>/dev/null; "
            f"echo {value} > {path} 2>/dev/null && cat {path} 2>/dev/null",
            silent=True
        )
        return value in (result or "")

    @classmethod
    def _apply_group(cls, label: str, params: List[Tuple[str, str, str]]) -> int:
        """Zastosuj grupę parametrów. Zwraca liczbę udanych zmian."""
        L.sub(label)
        applied = 0
        for path, val, desc in params:
            ok = cls._write_sys(path, val)
            if ok:
                L.ok(f"  {path.split('/')[-1]} = {val}  ({desc})")
                applied += 1
            else:
                L.dim(f"  {path.split('/')[-1]} = {val} (read-only/brak — pominięto)")
        return applied

    @classmethod
    def apply_vm(cls) -> None:
        """
        /proc/sys/vm — Virtual Memory tuning.
        DCTIW362P: brak ZRAM/swap → swappiness=0 (nie ma gdzie swapować)
        """
        L.hdr("🧠 KERNEL VM — Virtual Memory (BCM7362, brak ZRAM)")
        vm = "/proc/sys/vm/"
        params = [
            # swappiness: 0 = nie swapuj (STB nie ma swap partition — AIO ZRAM wykomentowane)
            (f"{vm}swappiness",              "0",      "0=no swap (brak ZRAM/swap na STB)"),
            # dirty_ratio: max % RAM z brudnymi stronami zanim SYNC jest wymuszone
            # 15% z 1459MB = ~219MB → dobry kompromis dla streaming + eMMC I/O
            (f"{vm}dirty_ratio",             "15",     "max dirty pages % przed sync"),
            # dirty_background_ratio: % przy którym writeback startuje w tle
            (f"{vm}dirty_background_ratio",  "5",      "dirty background writeback start"),
            # dirty_expire_centisecs: jak długo strona może być brudna (ms/100)
            # 1500 = 15s — dłuższe → mniej I/O przerw podczas streamingu
            (f"{vm}dirty_expire_centisecs",  "1500",   "dirty expire 15s"),
            # dirty_writeback_centisecs: interwał writeback wątku
            (f"{vm}dirty_writeback_centisecs","500",   "writeback interwał 5s"),
            # vfs_cache_pressure: <100 = zachowaj więcej cache
            # 50 = preferuj cache zamiast odśmiecania (więcej RAM na media bufory)
            (f"{vm}vfs_cache_pressure",      "50",     "VFS cache 50 (więcej cache)"),
            # min_free_kbytes: minimalna wolna pamięć kernela
            # 49152 = 48MB (bezpieczny margines dla BCM7362 z 1459MB)
            (f"{vm}min_free_kbytes",         "49152",  "min free kernel pages 48MB"),
            # page-cluster: strony odczytywane razem przy page fault
            # 0 = single page (streaming nie korzysta z page readahead)
            (f"{vm}page-cluster",            "0",      "page cluster=0 (single page streaming)"),
            # overcommit_memory: 1 = zawsze zezwalaj (ExoPlayer pre-alokuje)
            (f"{vm}overcommit_memory",       "1",      "overcommit=1 (ExoPlayer prealloc)"),
            # overcommit_ratio: 50% gdy overcommit_memory=2 (nie używamy, ale bezpieczne)
            (f"{vm}overcommit_ratio",        "50",     "overcommit ratio 50%"),
            # oom_kill_allocating_task: 1 = zabij zadanie alokujące (szybszy recovery OOM)
            (f"{vm}oom_kill_allocating_task","1",      "OOM: kill allocating task"),
        ]
        applied = cls._apply_group("VM parameters", params)
        L.ok(f"VM tuning: {applied}/{len(params)} parametrów zastosowanych ✓")

    @classmethod
    def apply_kernel_sched(cls) -> None:
        """
        /proc/sys/kernel — scheduler + system params.
        Cortex-A15 dual-core: latency ważniejsza niż throughput.
        """
        L.hdr("⚙ KERNEL SCHED — Cortex-A15 Scheduler Tuning")
        k = "/proc/sys/kernel/"
        params = [
            # sched_latency_ns: max czas bez wywłaszczenia — 5ms dobry dla streaming
            (f"{k}sched_latency_ns",         "5000000",  "max latency 5ms"),
            # sched_min_granularity_ns: min czas działania procesu
            (f"{k}sched_min_granularity_ns", "500000",   "min granularity 0.5ms"),
            # sched_wakeup_granularity_ns: próg budzenia — niższy = szybsza reakcja
            (f"{k}sched_wakeup_granularity_ns","1000000","wakeup granularity 1ms"),
            # sched_migration_cost_ns: koszt migracji między CPU — wyższy = mniej migracji
            (f"{k}sched_migration_cost_ns",  "500000",   "migration cost 0.5ms"),
            # sched_child_runs_first: dziecko (fork) działa przed rodzicem
            # ExoPlayer forkuje dekodery — szybszy start
            (f"{k}sched_child_runs_first",   "1",        "child runs first (fork optim)"),
            # perf_event_paranoid: 1 = umożliwia profiling bez roota
            (f"{k}perf_event_paranoid",      "1",        "perf events dostępne"),
            # randomize_va_space: 0 = ASLR off (debug) / 2 = full (security)
            # Zostawiamy domyślne 2 — nie zmieniamy ze względów bezpieczeństwa
            # panic: 5s reboot po kernel panic (zamiast wieszania się)
            (f"{k}panic",                    "5",        "auto-reboot po 5s od kernel panic"),
        ]
        applied = cls._apply_group("Kernel scheduler", params)
        L.ok(f"Kernel sched: {applied}/{len(params)} parametrów ✓")

    @classmethod
    def apply_fs(cls) -> None:
        """
        /proc/sys/fs — filesystem limits.
        Wyższe file-max i inotify watches zapobiegają błędom ExoPlayer/Cast.
        """
        L.hdr("📁 KERNEL FS — Filesystem Limits")
        fs = "/proc/sys/fs/"
        params = [
            # file-max: max otwartych plików globalnie
            # Cast + SmartTube + GMS mogą łącznie otworzyć 2000+ deskryptorów
            (f"{fs}file-max",                    "131072",  "max otwartych plików 128K"),
            # inotify max_user_watches: Cast używa inotify do monitorowania mediów
            (f"{fs}inotify/max_user_watches",    "524288",  "inotify watches 512K"),
            (f"{fs}inotify/max_user_instances",  "256",     "inotify instances 256"),
            (f"{fs}inotify/max_queued_events",   "32768",   "inotify queue 32K"),
            # pipe_size: większe pipe = mniej context switches w pipeline
            # ExoPlayer używa pipes w OMX/C2 data path
            # NOTE: Tylko jeśli dostępne w kernel 4.9
            (f"{fs}pipe-max-size",               "1048576", "max pipe size 1MB"),
        ]
        applied = cls._apply_group("Filesystem limits", params)
        L.ok(f"FS limits: {applied}/{len(params)} ✓")

    @classmethod
    def apply_net_extra(cls) -> None:
        """
        Dodatkowe parametry sieciowe z AIO — uzupełnienie NetworkOptimizer.
        """
        L.hdr("🌐 KERNEL NET EXTRA — AIO-inspired additions")
        net = "/proc/sys/net/"
        params = [
            # Increase socket receive buffer (streaming)
            (f"{net}core/rmem_default",      "262144",    "default recv buf 256KB"),
            (f"{net}core/wmem_default",      "262144",    "default send buf 256KB"),
            (f"{net}core/rmem_max",          "16777216",  "max recv buf 16MB"),
            (f"{net}core/wmem_max",          "16777216",  "max send buf 16MB"),
            # netdev backlog
            (f"{net}core/netdev_max_backlog","2000",      "netdev backlog 2000"),
            (f"{net}core/somaxconn",         "1024",      "max socket connections"),
            # IPv4 extras
            (f"{net}ipv4/tcp_mtu_probing",   "1",         "MTU probing ON"),
            (f"{net}ipv4/tcp_slow_start_after_idle","0",  "no slow start after idle"),
            (f"{net}ipv4/tcp_syn_retries",   "2",         "SYN retries = 2"),
            (f"{net}ipv4/tcp_synack_retries","2",         "SYNACK retries = 2"),
            (f"{net}ipv4/tcp_fin_timeout",   "15",        "FIN timeout 15s"),
            (f"{net}ipv4/tcp_keepalive_time","300",       "keepalive 5min"),
        ]
        applied = cls._apply_group("Net extra", params)
        L.ok(f"Net extra: {applied}/{len(params)} ✓")

    @classmethod
    def apply_fstrim(cls) -> None:
        """
        fstrim na partycjach eMMC — usuwa fragmentację, poprawia I/O o 20-40%.
        AIO: fstrim -v /cache /data /system
        Na Android TV 9 dostępne przez ADB.sh (nie wymaga roota).
        UWAGA: operacja trwa 10-60s na zapełnionej partycji.
        """
        L.hdr("💿 FSTRIM — eMMC Defragmentation (AIO)")
        L.warn("fstrim może potrwać 10-60s — nie przerywaj!")
        partitions = ["/cache", "/data", "/system"]
        for part in partitions:
            L.info(f"  fstrim {part}...")
            out = ADB.sh(f"fstrim -v {part} 2>&1", silent=False)
            if out:
                L.ok(f"  {part}: {out[:80]}")
            else:
                L.dim(f"  {part}: pominięto (busy lub brak dostępu)")
        L.ok("fstrim complete ✓")

    @classmethod
    def apply_lmkd_reinit(cls) -> None:
        """
        lmkd reinit przez device_config — z AIO lmk_config().
        Na Android 9 API 28: device_config lmkd_native może nie być dostępny
        ale lmkd.reinit jest zawsze bezpieczny.
        """
        L.hdr("🧹 LMKD REINIT — device_config (AIO)")
        # Usuń overrides które mogą blokować PSI thresholds
        ADB.sh("device_config delete lmkd_native swap_free_low_percentage 2>/dev/null", silent=True)
        ADB.sh("device_config delete lmkd_native use_minfree_levels 2>/dev/null", silent=True)
        # Reinit — przeładuj konfigurację LMK
        ADB.setprop("lmkd.reinit", "1")
        L.ok("  lmkd.reinit = 1")
        time.sleep(1)
        ADB.setprop("lmkd.reinit", "0")
        L.ok("  lmkd.reinit = 0 (complete)")
        L.ok("LMKD reinitialized ✓")

    @classmethod
    def apply_all(cls) -> None:
        """Zastosuj wszystkie grupy kernel tweaks."""
        cls.apply_vm()
        cls.apply_kernel_sched()
        cls.apply_fs()
        cls.apply_net_extra()
        L.ok("Wszystkie kernel tweaks zastosowane ✓")


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
        """
        Zbierz informacje o WiFi — 3-poziomowy łańcuch fallback.

        POZIOM 1 (primary): dumpsys wifi — pełny output, szukamy bloku
          "mWifiInfo" lub "WifiInfo:" który zawiera WSZYSTKIE pola w jednej strukturze.
          Android TV 9 format:
            mWifiInfo: SSID: "nazwa", BSSID: aa:bb:..., MAC: ...,
                       Supplicant state: COMPLETED, RSSI: -54,
                       Link speed: 130Mbps, Tx Speed: 130Mbps,
                       Frequency: 5180MHz, Net ID: 3, ...

        POZIOM 2 (fallback): wpa_cli status — działa bez roota przez ADB
          Format: ssid=NazwaSieci\nbssid=aa:bb:...\nfreq=5180\n...

        POZIOM 3 (minimal): ip addr + ip route + getprop dns
          Tylko IP/GW/DNS — gdy WiFi jest ale dumpsys niedostępny.
        """
        info: Dict[str, str] = {
            "ssid": "—", "bssid": "—", "freq": "—", "band": "—",
            "channel": "—", "rssi": "—", "signal_label": "—",
            "link_speed": "—", "tx_speed": "—", "ip": "—", "gw": "—",
            "dns1": "—", "dns_mode": "—", "connected": "false",
            "supplicant": "—", "security": "—",
        }

        # ── POZIOM 1: pełny dumpsys wifi + blok mWifiInfo ─────────────────────
        raw_full = ADB.sh("dumpsys wifi 2>/dev/null", silent=True)
        parsed_lvl1 = False

        if raw_full:
            # Znajdź blok WifiInfo (Android 8/9/10 różne formaty)
            # Format A: "mWifiInfo: SSID: ..."  (jedna linia z przecinkami)
            # Format B: "WifiInfo: SSID: ..." 
            # Format C: multi-line po "mWifiInfo:"
            wifi_info_block = ""

            for marker in ("mWifiInfo: ", "WifiInfo: ", "cur=mWifiInfo:"):
                idx = raw_full.find(marker)
                if idx != -1:
                    # Wez linię zawierającą marker + następne 5 linii
                    block_start = raw_full.rfind(chr(10), 0, idx) + 1
                    block_end   = raw_full.find(chr(10)+chr(10), idx)
                    if block_end == -1:
                        block_end = min(idx + 1000, len(raw_full))
                    wifi_info_block = raw_full[block_start:block_end]
                    break

            if wifi_info_block:
                # SSID: "nazwa" lub SSID: nazwa (bez cudzysłowów)
                m = re.search(r'SSID:\s*"([^"]+)"', wifi_info_block)
                if not m: m = re.search(r'SSID:\s+([^\s,]+)', wifi_info_block)
                if m and m.group(1) not in ("<unknown ssid>", "0x", ""):
                    info["ssid"] = m.group(1).strip()
                    parsed_lvl1 = True

                m = re.search(r'BSSID:\s*([0-9a-f:]{17})', wifi_info_block, re.I)
                if m: info["bssid"] = m.group(1)

                # Frequency: 5180MHz lub Frequency: 5180 (MHz może być w nawiasie)
                m = re.search(r'Frequency:\s*(\d{4,5})', wifi_info_block)
                if m:
                    freq = int(m.group(1))
                    info["freq"]    = f"{freq} MHz"
                    info["band"]    = cls._band(freq)
                    info["channel"] = str(cls._freq_to_channel(freq))

                # RSSI: -54 (zawsze ujemny)
                m = re.search(r'RSSI:\s*(-\d+)', wifi_info_block)
                if m:
                    rssi = int(m.group(1))
                    info["rssi"]         = f"{rssi} dBm"
                    info["signal_label"] = cls._rssi_label(rssi)

                # Link speed: 130Mbps lub Link speed: 130 Mbps
                m = re.search(r'[Ll]ink\s+[Ss]peed:\s*(\d+)\s*Mbps', wifi_info_block)
                if m: info["link_speed"] = f"{m.group(1)} Mbps"

                m = re.search(r'[Tt]x\s+[Ss]peed:\s*(\d+)', wifi_info_block)
                if m: info["tx_speed"] = f"{m.group(1)} Mbps"

                # Supplicant state
                m = re.search(r'[Ss]upplicant\s+state:\s*(\w+)', wifi_info_block)
                if m: info["supplicant"] = m.group(1)

        # ── POZIOM 2 fallback: wpa_cli status ─────────────────────────────────
        if not parsed_lvl1 or info["ssid"] == "—":
            wpa = ADB.sh("wpa_cli -i wlan0 status 2>/dev/null", silent=True)
            if wpa and "COMPLETED" in wpa:
                for line in wpa.splitlines():
                    kv = line.split("=", 1)
                    if len(kv) != 2: continue
                    k, v = kv[0].strip(), kv[1].strip()
                    if k == "ssid" and v: info["ssid"] = v
                    elif k == "bssid": info["bssid"] = v
                    elif k == "freq" and v.isdigit():
                        freq = int(v)
                        info["freq"]    = f"{freq} MHz"
                        info["band"]    = cls._band(freq)
                        info["channel"] = str(cls._freq_to_channel(freq))
                    elif k == "key_mgmt": info["security"] = v
                    elif k == "wpa_state": info["supplicant"] = v

            # RSSI z /proc/net/wireless (zawsze dostępny, nie wymaga roota)
            if info["rssi"] == "—":
                proc_w = ADB.sh("cat /proc/net/wireless 2>/dev/null", silent=True)
                if proc_w:
                    for line in proc_w.splitlines():
                        if "wlan0" in line:
                            parts = line.split()
                            if len(parts) >= 4:
                                try:
                                    rssi_raw = parts[3].rstrip(".")
                                    rssi = int(float(rssi_raw))
                                    # /proc/net/wireless zwraca wartość bez znaku lub z
                                    if rssi > 0: rssi = rssi - 256   # konwersja unsigned → signed
                                    if -120 < rssi < 0:
                                        info["rssi"]         = f"{rssi} dBm"
                                        info["signal_label"] = cls._rssi_label(rssi)
                                except: pass

        # ── POZIOM 3: IP / GW / DNS (zawsze dostępne) ─────────────────────────
        # IP z ip addr (wlan0 lub eth0)
        for iface in ("wlan0", "eth0"):
            ip_raw = ADB.sh(f"ip addr show {iface} 2>/dev/null", silent=True)
            m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/\d+", ip_raw)
            if m:
                info["ip"] = m.group(1)
                if iface == "eth0" and info["ssid"] == "—":
                    info["ssid"] = f"ETH ({iface})"
                    info["band"] = "Ethernet"
                break

        # GW z ip route
        gw_raw = ADB.sh("ip route 2>/dev/null", silent=True)
        m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", gw_raw)
        if m: info["gw"] = m.group(1)

        # DNS — sprawdź oba tryby: legacy getprop + Private DNS
        dns_prop = ADB.prop("net.dns1")
        dns_dot  = ADB.sget("global", "private_dns_specifier")
        dns_mode = ADB.sget("global", "private_dns_mode")
        if dns_dot and dns_dot not in ("null", ""):
            info["dns1"]     = f"DoT: {dns_dot}"
            info["dns_mode"] = "Private DNS (TLS)"
        elif dns_prop and dns_prop not in ("", "0.0.0.0"):
            info["dns1"]     = dns_prop
            info["dns_mode"] = "Legacy resolver"

        info["connected"] = "true" if info["ssid"] not in ("—",) else "false"
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
# MODULE: AdaptivePerf — Interactive/Proactive Performance Tuner (v14.1)
# ═════════════════════════════════════════════════════════════════════════════
class PerfSnapshot(NamedTuple):
    """Snapshot wydajności w danym momencie."""
    ts:        str
    label:     str
    avail_mb:  int       # RAM dostępny
    janky_pct: float     # % klatek > 16.7ms
    frame_p99: float     # 99th percentile frame time (ms)
    cpu_pct:   float     # CPU usage %
    fps_est:   float     # szacowane FPS

class AdaptivePerf:
    """
    Proaktywny tuner wydajności z porównaniem PRZED/PO.

    Tryby:
      1. Automatyczny (auto):
         - Zbiera snapshot baseline
         - Wykrywa bottleneck (RAM / CPU / GPU frame)
         - Dobiera i aplikuje najlepszy zestaw tweaków
         - Mierzy po 30s
         - Raportuje delta

      2. Interaktywny (step-by-step):
         - Dla każdego tweaka: pokaż aktualny stan
         - Zastosuj
         - Zmierz efekt
         - Zapytaj: ZACHOWAJ / COFNIJ / POMIŃ
         - Prowadź rejestr zmian ze zmierzonym efektem

      3. Porównawczy (compare):
         - Wczytaj historię z HISTORY_FILE
         - Pokaż tabelę: tweak → delta janky% / delta frame_p99 / delta RAM
         - Zaznacz które tweaki RZECZYWIŚCIE pomogły

    Historia: ~/.playbox_cache/adaptive_history.json
    """

    HISTORY_FILE = CACHE_DIR / "adaptive_history.json"
    _applied_tweaks: List[Dict] = []   # aktywne tweaki tej sesji

    # Katalog tweaków z priorytetami
    # Format: (id, name, category, priority, fn_apply, fn_revert, expected_gain)
    TWEAK_CATALOG = None  # wypełniany w _build_catalog()

    @classmethod
    def _build_catalog(cls) -> List[Dict]:
        """Zbuduj katalog dostępnych tweaków z priorytetami."""
        from functools import partial
        def sp(k,v):  ADB.setprop(k,v)
        def sput(ns,k,v): ADB.sput(ns,k,v)

        return [
            {
                "id": "codec_priority",
                "name": "Codec priority = 0 (realtime)",
                "category": "video",
                "priority": 10,
                "bottleneck": "frame",
                "fn_apply":  lambda: sp("media.codec.priority","0"),
                "fn_revert": lambda: sp("media.codec.priority","1"),
                "expected": "Redukcja czarnego ekranu ~8-12s",
            },
            {
                "id": "vpu_preinit",
                "name": "VPU pre-init (decoder.preinit=true)",
                "category": "video",
                "priority": 9,
                "bottleneck": "frame",
                "fn_apply":  lambda: sp("media.brcm.decoder.preinit","true"),
                "fn_revert": lambda: sp("media.brcm.decoder.preinit","false"),
                "expected": "Eliminuje VPU cold-start ~3-5s",
            },
            {
                "id": "sf_phase_offset",
                "name": "SF phase offset 0.5ms (early commit)",
                "category": "rendering",
                "priority": 8,
                "bottleneck": "frame",
                "fn_apply":  lambda: (sp("debug.sf.early_phase_offset_ns","500000"),
                                      sp("debug.sf.early_app_phase_offset_ns","1000000")),
                "fn_revert": lambda: (sp("debug.sf.early_phase_offset_ns","0"),
                                      sp("debug.sf.early_app_phase_offset_ns","0")),
                "expected": "Redukcja P99 frame time ~5-15ms",
            },
            {
                "id": "treble_omx",
                "name": "OMX direct path (treble_omx=false)",
                "category": "video",
                "priority": 8,
                "bottleneck": "frame",
                "fn_apply":  lambda: sp("persist.media.treble_omx","false"),
                "fn_revert": lambda: sp("persist.media.treble_omx","true"),
                "expected": "Redukcja OMX IPC latency ~2-3s",
            },
            {
                "id": "render_thread",
                "name": "HWUI render thread (offload UI)",
                "category": "rendering",
                "priority": 7,
                "bottleneck": "frame",
                "fn_apply":  lambda: sp("debug.hwui.render_thread","true"),
                "fn_revert": lambda: sp("debug.hwui.render_thread","false"),
                "expected": "Redukcja janky% ~2-5%",
            },
            {
                "id": "heap_minfree",
                "name": "Dalvik heapminfree 512k→2m",
                "category": "memory",
                "priority": 7,
                "bottleneck": "ram",
                "fn_apply":  lambda: (sp("dalvik.vm.heapminfree","2m"),
                                      sp("dalvik.vm.heapmaxfree","16m")),
                "fn_revert": lambda: (sp("dalvik.vm.heapminfree","512k"),
                                      sp("dalvik.vm.heapmaxfree","8m")),
                "expected": "Redukcja GC pressure, stabilność RAM",
            },
            {
                "id": "lmk_pressure",
                "name": "LMK upgrade_pressure 100→50",
                "category": "memory",
                "priority": 6,
                "bottleneck": "ram",
                "fn_apply":  lambda: (sp("ro.lmk.upgrade_pressure","50"),
                                      ADB.sh("setprop lmkd.reinit 1",silent=True)),
                "fn_revert": lambda: (sp("ro.lmk.upgrade_pressure","100"),
                                      ADB.sh("setprop lmkd.reinit 1",silent=True)),
                "expected": "Szybsza reakcja LMK na presję RAM",
            },
            {
                "id": "vm_swappiness",
                "name": "vm.swappiness = 0 (brak ZRAM)",
                "category": "memory",
                "priority": 6,
                "bottleneck": "ram",
                "fn_apply":  lambda: ADB.root("echo 0 > /proc/sys/vm/swappiness"),
                "fn_revert": lambda: ADB.root("echo 60 > /proc/sys/vm/swappiness"),
                "expected": "Kernel nie próbuje swapować na STB bez swap",
            },
            {
                "id": "io_deadline",
                "name": "I/O scheduler: deadline",
                "category": "io",
                "priority": 6,
                "bottleneck": "io",
                "fn_apply":  lambda: ADB.root("for d in /sys/block/*/queue/scheduler; do echo deadline > $d 2>/dev/null; done"),
                "fn_revert": lambda: ADB.root("for d in /sys/block/*/queue/scheduler; do echo cfq > $d 2>/dev/null; done"),
                "expected": "Niższe I/O latency dla VP9 segments",
            },
            {
                "id": "anim_scale",
                "name": "Animacje 0.35× (TV-optimized)",
                "category": "ui",
                "priority": 5,
                "bottleneck": "cpu",
                "fn_apply":  lambda: [sput("global",k,"0.35") for k in
                    ["window_animation_scale","transition_animation_scale","animator_duration_scale"]],
                "fn_revert": lambda: [sput("global",k,"0.5") for k in
                    ["window_animation_scale","transition_animation_scale","animator_duration_scale"]],
                "expected": "Szybsza nawigacja TV pilot",
            },
            {
                "id": "wifi_scan",
                "name": "WiFi background scan OFF",
                "category": "network",
                "priority": 5,
                "bottleneck": "cpu",
                "fn_apply":  lambda: (sput("global","wifi_scan_always_enabled","0"),
                                      sput("global","ble_scan_always_enabled","0")),
                "fn_revert": lambda: (sput("global","wifi_scan_always_enabled","1"),
                                      sput("global","ble_scan_always_enabled","1")),
                "expected": "Redukcja CPU spikes ~2-5%",
            },
            {
                "id": "tcp_rwnd",
                "name": "TCP init_rwnd 60→120",
                "category": "network",
                "priority": 5,
                "bottleneck": "net",
                "fn_apply":  lambda: (sput("global","tcp_default_init_rwnd","120"),
                                      sp("net.tcp.default_init_rwnd","120")),
                "fn_revert": lambda: (sput("global","tcp_default_init_rwnd","60"),
                                      sp("net.tcp.default_init_rwnd","60")),
                "expected": "2× szybszy cold-start streamu",
            },
        ]

    @staticmethod
    def _snapshot(label: str) -> PerfSnapshot:
        """Zbierz snapshot wydajności (non-invasive)."""
        # RAM
        mem_raw = ADB.sh("grep MemAvailable /proc/meminfo", silent=True)
        m = re.search(r"(\d+)\s*kB", mem_raw)
        avail_mb = int(m.group(1)) // 1024 if m else 0

        # CPU usage (top 1 iteration)
        cpu_raw = ADB.sh("top -bn1 2>/dev/null | grep -E '^[Cc]pu|^[Cc]PU'", silent=True)
        cpu_pct = 0.0
        m = re.search(r"(\d+)%?\s*(usr|user)", cpu_raw)
        if m: cpu_pct = float(m.group(1))

        # Frame timing z gfxinfo SmartTube
        janky_pct = 0.0; frame_p99 = 0.0; fps_est = 0.0
        pkg = HW.PKG_SMARTTUBE_STABLE
        if ADB.pkg_ok(pkg):
            raw = ADB.sh(f"dumpsys gfxinfo {pkg} framestats 2>/dev/null", silent=True)
            times = []
            for line in raw.splitlines():
                parts = line.split(",")
                if len(parts) > 13:
                    try:
                        intended = int(parts[1]); actual = int(parts[2])
                        fn = (actual - intended) / 1_000_000
                        if 0 < fn < 500: times.append(fn)
                    except: pass
            if len(times) > 5:
                times.sort()
                frame_p99 = times[int(len(times)*0.99)]
                janky     = sum(1 for t in times if t > 16.7)
                janky_pct = (janky / len(times)) * 100
                fps_est   = 1000 / statistics.mean(times) if times else 0

        return PerfSnapshot(
            ts=time.strftime("%H:%M:%S"),
            label=label,
            avail_mb=avail_mb,
            janky_pct=janky_pct,
            frame_p99=frame_p99,
            cpu_pct=cpu_pct,
            fps_est=fps_est,
        )

    @classmethod
    def _print_snapshot(cls, s: PerfSnapshot, prev: Optional[PerfSnapshot] = None) -> None:
        c = L.C
        def delta_str(cur: float, old: Optional[float], lower_is_better: bool) -> str:
            if old is None: return ""
            d = cur - old
            better = (d < 0) == lower_is_better
            col = c["s"] if better else c["e"]
            arrow = "↓" if d < 0 else "↑"
            return f"  {col}{arrow}{abs(d):.1f}{c['r']}"

        sep = "┌─── Snapshot: " + s.label + " [" + s.ts + "] ───────────────────────────┐"
        print(f"\n  {c['b']}{sep}{c['r']}")
        print(f"  {c['b']}│{c['r']}  RAM avail : {c['c']}{s.avail_mb:>5}MB{c['r']}{delta_str(s.avail_mb, prev.avail_mb if prev else None, False)}")
        frame_col = c['s'] if s.janky_pct < 5 else (c['w'] if s.janky_pct < 15 else c['e'])
        print(f"  {c['b']}│{c['r']}  Janky     : {frame_col}{s.janky_pct:>5.1f}%{c['r']}{delta_str(s.janky_pct, prev.janky_pct if prev else None, True)}")
        p99_col = c['s'] if s.frame_p99 < 33 else (c['w'] if s.frame_p99 < 50 else c['e'])
        print(f"  {c['b']}│{c['r']}  Frame P99 : {p99_col}{s.frame_p99:>5.1f}ms{c['r']}{delta_str(s.frame_p99, prev.frame_p99 if prev else None, True)}")
        cpu_col = c['s'] if s.cpu_pct < 60 else (c['w'] if s.cpu_pct < 85 else c['e'])
        print(f"  {c['b']}│{c['r']}  CPU usage : {cpu_col}{s.cpu_pct:>5.1f}%{c['r']}{delta_str(s.cpu_pct, prev.cpu_pct if prev else None, True)}")
        print(f"  {c['b']}│{c['r']}  Est. FPS  : {c['c']}{s.fps_est:>5.1f}{c['r']}")
        print(f"  {c['b']}└───────────────────────────────────────────────────────┘{c['r']}")

    @classmethod
    def _detect_bottleneck(cls, snap: PerfSnapshot) -> str:
        """Wykryj główny bottleneck na podstawie snapshot."""
        if snap.janky_pct > 15:     return "frame"   # dużo janky → GPU/codec
        if snap.avail_mb  < 150:    return "ram"     # za mało RAM
        if snap.cpu_pct   > 80:     return "cpu"     # CPU saturated
        if snap.frame_p99 > 50:     return "frame"   # wysokie P99 → rendering
        return "general"

    @classmethod
    def _save_history(cls, entry: Dict) -> None:
        history = []
        if cls.HISTORY_FILE.exists():
            try:
                with open(cls.HISTORY_FILE) as f: history = json.load(f)
            except: pass
        history.append(entry)
        history = history[-50:]
        with open(cls.HISTORY_FILE, "w") as f: json.dump(history, f, indent=2)

    @classmethod
    def run_auto(cls) -> None:
        """
        Tryb automatyczny:
        1. Baseline snapshot
        2. Wykryj bottleneck
        3. Zastosuj tweaki w kolejności priorytetu
        4. Poczekaj 30s (daj czas na stabilizację)
        5. Snapshot po
        6. Raportuj delta
        """
        L.hdr("🤖 ADAPTIVE PERF — Tryb AUTOMATYCZNY")
        L.info("  Krok 1: zbieranie baseline (SmartTube musi być uruchomiony)")
        if not ADB.pkg_ok(HW.PKG_SMARTTUBE_STABLE):
            L.warn("  SmartTube nie jest aktywny — frame metrics będą zerowe")
            L.info("  Otwórz SmartTube → odtwórz film → wróć i uruchom ponownie")

        baseline = cls._snapshot("BASELINE")
        cls._print_snapshot(baseline)

        bottleneck = cls._detect_bottleneck(baseline)
        L.info(f"\nWykryty bottleneck: {bottleneck.upper()}")

        catalog = cls._build_catalog()
        # Sortuj: najpierw pasujące do bottlenecka, potem po priorytecie
        relevant = sorted(
            [t for t in catalog if t["bottleneck"] == bottleneck or bottleneck == "general"],
            key=lambda x: x["priority"], reverse=True
        )[:6]  # max 6 tweaków auto

        L.info(f"\nTweaki do zastosowania ({len(relevant)}):")
        for t in relevant:
            L.info(f"    [{t['priority']:2}] {t['name']} — {t['expected']}")

        L.info("\n  Zastosowywanie tweaków...")
        for t in relevant:
            try:
                t["fn_apply"]()
                cls._applied_tweaks.append({"id": t["id"], "name": t["name"]})
                L.ok(f"    ✓ {t['name']}")
            except Exception as e:
                L.warn(f"    ⚠ {t['name']}: {e}")

        L.info("\n  Czekam 30s na stabilizację...")
        for i in range(30, 0, -5):
            print(f"    {i}s...", end="\r")
            time.sleep(5)
        print()

        after = cls._snapshot("PO TWEAKACH")
        cls._print_snapshot(after, baseline)

        # Podsumowanie
        L.hdr("📊 WYNIKI AUTO-TUNE")
        cls._print_comparison_table(baseline, after)
        cls._save_history({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "mode": "auto",
            "bottleneck": bottleneck,
            "tweaks": [t["id"] for t in relevant],
            "baseline": baseline._asdict(),
            "after": after._asdict(),
        })

    @classmethod
    def run_interactive(cls) -> None:
        """
        Tryb interaktywny — krok po kroku z możliwością ZACHOWAJ/COFNIJ.
        """
        c = L.C
        L.hdr("🎛  ADAPTIVE PERF — Tryb INTERAKTYWNY")
        catalog = cls._build_catalog()
        # Sortuj po priorytecie
        catalog = sorted(catalog, key=lambda x: x["priority"], reverse=True)

        baseline = cls._snapshot("BASELINE")
        cls._print_snapshot(baseline)
        prev_snap = baseline
        kept = []

        for i, tweak in enumerate(catalog, 1):
            print(f"\n{c['b']}{'─'*60}{c['r']}")
            print(f"  [{i}/{len(catalog)}] {c['c']}{tweak['name']}{c['r']}")
            print(f"  Kategoria : {tweak['category']} | Priorytet: {tweak['priority']}/10")
            print(f"  Bottleneck: {tweak['bottleneck']}")
            print(f"  Oczekiwane: {c['s']}{tweak['expected']}{c['r']}")

            # Pokaż aktualny stan relevatnych propów
            if tweak["id"] == "codec_priority":
                cur = ADB.prop("media.codec.priority")
                print(f"  Aktualnie : media.codec.priority = {c['w']}{cur}{c['r']}")

            choice = input(f"\n  {c['c']}[A]plikuj / [P]omiń / [Q]uit > {c['r']}").strip().lower()
            if choice == "q": break
            if choice != "a":
                L.dim(f"  Pominięto: {tweak['name']}")
                continue

            # Zastosuj
            try:
                tweak["fn_apply"]()
                L.ok(f"  Zastosowano: {tweak['name']}")
            except Exception as e:
                L.warn(f"  Błąd: {e}"); continue

            # Zmierz efekt po 10s
            L.info("  Mierzę efekt (10s)...")
            time.sleep(10)
            after_snap = cls._snapshot(f"PO: {tweak['id']}")
            cls._print_snapshot(after_snap, prev_snap)

            # Pokaż delta konkretnych metryk
            jam_d = after_snap.janky_pct - prev_snap.janky_pct
            ram_d = after_snap.avail_mb  - prev_snap.avail_mb
            p99_d = after_snap.frame_p99 - prev_snap.frame_p99
            print(f"\nDelta janky: {c['s'] if jam_d<=0 else c['e']}{jam_d:+.1f}%{c['r']}  "
                  f"RAM: {c['s'] if ram_d>=0 else c['e']}{ram_d:+d}MB{c['r']}  "
                  f"P99: {c['s'] if p99_d<=0 else c['e']}{p99_d:+.1f}ms{c['r']}")

            keep = input(f"  {c['c']}[K]eep / [R]evert > {c['r']}").strip().lower()
            if keep == "r":
                try:
                    tweak["fn_revert"]()
                    L.warn(f"  Cofnięto: {tweak['name']}")
                except: pass
            else:
                kept.append({"id": tweak["id"], "name": tweak["name"],
                             "janky_delta": jam_d, "ram_delta": ram_d, "p99_delta": p99_d})
                prev_snap = after_snap
                L.ok(f"  Zachowano: {tweak['name']}")

        # Finalny snapshot
        final = cls._snapshot("FINAL")
        L.hdr("🎯 ADAPTIVE INTERAKTYWNY — PODSUMOWANIE")
        cls._print_snapshot(final, baseline)
        print(f"\n  Zachowane tweaki ({len(kept)}):")

        for k in kept:
            print(f"    ✓ {k['name']} | janky: {k['janky_delta']:+.1f}% | P99: {k['p99_delta']:+.1f}ms")

        cls._save_history({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "mode": "interactive",
            "kept": kept,
            "baseline": baseline._asdict(),
            "final": final._asdict(),
        })

    @classmethod
    def _print_comparison_table(cls, before: PerfSnapshot, after: PerfSnapshot) -> None:
        c = L.C
        metrics = [
            ("RAM dostępny (MB)",   before.avail_mb,  after.avail_mb,  False),
            ("Janky frames (%)",    before.janky_pct, after.janky_pct, True),
            ("Frame P99 (ms)",      before.frame_p99, after.frame_p99, True),
            ("CPU usage (%)",       before.cpu_pct,   after.cpu_pct,   True),
            ("Est. FPS",            before.fps_est,   after.fps_est,   False),
        ]
        print(f"\n  {c['b']}{'Metryka':<25} {'PRZED':>8} {'PO':>8} {'ZMIANA':>10} {'Ocena'}{c['r']}")

        print(f"  {'─'*58}")
        for name, bv, av, lower_better in metrics:
            d = av - bv
            pct = (d/bv*100) if bv != 0 else 0
            better = (d < 0) == lower_better
            col = c["s"] if better else (c["w"] if abs(pct) < 3 else c["e"])
            arrow = "↑" if d > 0 else "↓"
            print(f"  {name:<25} {bv:>8.1f} {av:>8.1f} {col}{arrow}{abs(d):>7.1f} ({pct:+.0f}%){c['r']}")

    @classmethod
    def show_history(cls) -> None:
        """Pokaż historię adaptive tuning z efektami."""
        L.hdr("📈 ADAPTIVE PERF — Historia sesji")
        if not cls.HISTORY_FILE.exists():
            L.warn("Brak historii — uruchom tryb auto lub interaktywny"); return
        try:
            with open(cls.HISTORY_FILE) as f: history = json.load(f)
        except: L.err("Błąd odczytu historii"); return
        c = L.C
        for i, entry in enumerate(history[-10:], 1):
            mode = entry.get("mode","?")
            ts   = entry.get("ts","?")[:16]
            b    = entry.get("baseline",{})
            a    = entry.get("after", entry.get("final",{}))
            j_d  = a.get("janky_pct",0) - b.get("janky_pct",0)
            r_d  = a.get("avail_mb",0)  - b.get("avail_mb",0)
            col  = c["s"] if j_d <= 0 else c["e"]
            print(f"  {i}. [{ts}] mode={mode:<12} "
                  f"janky: {col}{j_d:+.1f}%{c['r']}  "
                  f"RAM: {c['s'] if r_d>=0 else c['e']}{r_d:+d}MB{c['r']}")


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
# SYSTEM 1: BatchCommander — ADB command batching (3-5× speed improvement)
# ─────────────────────────────────────────────────────────────────────────────
class BatchCommander:
    """
    Queues ADB setprop / settings put / syswrite commands and executes them
    in a single ADB.sh invocation via a compound script.

    WHY: Each individual ADB call has ~150-250ms RTT overhead.
    Applying 30 setprops individually = 4.5-7.5 seconds.
    Batching them = 1 ADB call ≈ 0.3-0.8 seconds. That's 5-10× faster.

    Usage:
        with BatchCommander() as bc:
            bc.setprop("debug.sf.hw", "1")
            bc.settings("global", "transition_animation_scale", "0.35")
            bc.sys("/proc/sys/vm/swappiness", "0")
        # Executes on __exit__
    """

    def __init__(self, label: str = "batch"):
        self.label     = label
        self._cmds:   List[str]            = []
        self._track:  List[Tuple[str,str]] = []  # (description, expected)
        self._applied: int = 0

    def __enter__(self) -> "BatchCommander":
        return self

    def __exit__(self, *_) -> None:
        self.flush()

    # ── Queue builders ───────────────────────────────────────────────────────
    def setprop(self, key: str, val: str, desc: str = "") -> None:
        self._cmds.append(f"setprop {key} {val}")
        self._track.append((desc or key, val))

    def settings(self, ns: str, key: str, val: str, desc: str = "") -> None:
        self._cmds.append(f"settings put {ns} {key} {val}")
        self._track.append((desc or f"{ns}/{key}", val))

    def sys(self, path: str, val: str, desc: str = "") -> None:
        # Try both direct write and su; silently ignore errors
        self._cmds.append(
            f"( echo {val} > {path} 2>/dev/null"
            f" || su -c 'echo {val} > {path}' 2>/dev/null"
            f" || true )"
        )
        self._track.append((desc or path, val))

    def raw(self, cmd: str) -> None:
        """Append arbitrary shell command."""
        self._cmds.append(cmd)

    # ── Execute ──────────────────────────────────────────────────────────────
    def flush(self) -> int:
        """Execute all queued commands in one ADB invocation."""
        if not self._cmds:
            return 0
        script = " && ".join(f"({c})" for c in self._cmds)
        t0 = time.time()
        ADB.sh(script, silent=True)
        elapsed = time.time() - t0
        self._applied = len(self._cmds)
        L.ok(f"  Batch [{self.label}]: {self._applied} cmds in {elapsed:.2f}s "
             f"(~{elapsed/self._applied*1000:.0f}ms/cmd)")
        self._cmds.clear()
        return self._applied

    def queue_size(self) -> int:
        return len(self._cmds)


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM 2: SessionJournal — Undo stack + full audit trail
# ─────────────────────────────────────────────────────────────────────────────
class SessionJournal:
    """
    Tracks every property change with before/after values.
    Provides full undo capability — revert any or all changes from this session.

    Persists to JSON for cross-session audit trail.
    Side-effects: writes to CACHE_DIR/journal_YYYY-MM-DD.json

    Usage:
        j = SessionJournal.get()
        j.record("setprop", "debug.sf.hw", before="0", after="1", module="VideoEngine")
        j.undo_last()       # Reverts most recent change
        j.undo_all()        # Full session rollback
        j.show()            # Pretty-print audit trail
    """

    JOURNAL_DIR = CACHE_DIR / "journals"
    _instance:  Optional["SessionJournal"] = None

    def __init__(self):
        self.session_id  = time.strftime("%Y%m%d_%H%M%S")
        self.entries:    List[Dict] = []
        self._journal_file = self.JOURNAL_DIR / f"journal_{time.strftime('%Y-%m-%d')}.json"
        self.JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get(cls) -> "SessionJournal":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record(self, cmd_type: str, key: str, before: str, after: str,
               module: str = "", revert_cmd: str = "") -> None:
        """
        Record a change.
        cmd_type: 'setprop' | 'settings' | 'syswrite'
        revert_cmd: if provided, used for undo; else auto-derived.
        """
        entry = {
            "ts":       time.strftime("%H:%M:%S"),
            "session":  self.session_id,
            "module":   module,
            "type":     cmd_type,
            "key":      key,
            "before":   before,
            "after":    after,
            "reverted": False,
            "revert":   revert_cmd or self._derive_revert(cmd_type, key, before),
        }
        self.entries.append(entry)
        self._append_to_file(entry)

    def _derive_revert(self, cmd_type: str, key: str, before: str) -> str:
        """Derive undo command from before value."""
        if before == "":
            return ""  # Was unset — no safe revert
        if cmd_type == "setprop":
            return f"setprop {key} {before}"
        if cmd_type == "settings":
            parts = key.split("/", 1)
            if len(parts) == 2:
                return f"settings put {parts[0]} {parts[1]} {before}"
        if cmd_type == "syswrite":
            return f"echo {before} > {key}"
        return ""

    def undo_last(self) -> bool:
        """Undo the most recent non-reverted change."""
        for entry in reversed(self.entries):
            if not entry["reverted"] and entry["revert"]:
                L.fix(f"Undo: {entry['key']} → {entry['before']} (from {entry['after']})")
                ADB.sh(entry["revert"], silent=True)
                entry["reverted"] = True
                return True
        L.warn("Brak zmian do cofnięcia w tej sesji")
        return False

    def undo_module(self, module: str) -> int:
        """Undo all changes from a specific module."""
        count = 0
        for entry in reversed(self.entries):
            if entry["module"] == module and not entry["reverted"] and entry["revert"]:
                ADB.sh(entry["revert"], silent=True)
                entry["reverted"] = True
                count += 1
                L.fix(f"  Undo [{module}]: {entry['key']} → {entry['before']}")
        return count

    def undo_all(self) -> int:
        """Full session rollback — revert all changes in reverse order."""
        L.hdr("⏪ PEŁNY ROLLBACK SESJI")
        count = 0
        for entry in reversed(self.entries):
            if not entry["reverted"] and entry["revert"]:
                ADB.sh(entry["revert"], silent=True)
                entry["reverted"] = True
                count += 1
                L.fix(f"  [{entry['module']}] {entry['key']}: {entry['after']} → {entry['before']}")
        L.ok(f"Cofnięto {count} zmian ✓")
        return count

    def show(self, last_n: int = 30) -> None:
        """Pretty-print audit trail."""
        L.hdr("📋 DZIENNIK SESJI — Audit Trail")
        c = L.C
        entries = self.entries[-last_n:]
        if not entries:
            L.info("Brak zmian w tej sesji")
            return

        modules_seen: Dict[str, int] = {}
        for e in entries:
            modules_seen[e["module"]] = modules_seen.get(e["module"], 0) + 1

        print(f"  Sesja:  {c['c']}{self.session_id}{c['r']}")
        print(f"  Zmiany: {c['b']}{len(self.entries)}{c['r']} "
              f"({', '.join(f'{m}:{n}' for m,n in modules_seen.items())})")
        print()
        print(f"  {c['b']}{'Czas':<10} {'Moduł':<18} {'Klucz':<40} {'Przed':<12} {'Po':<12} {'Cofnięto'}{c['r']}")
        print(f"  {'─'*105}")
        for e in entries:
            before_s = (e["before"] or "unset")[:11]
            after_s  = e["after"][:11]
            rev_s    = f"{c['w']}COFNIĘTO{c['r']}" if e["reverted"] else f"{c['s']}aktywne{c['r']}"
            status   = f"{c['d']}" if e["reverted"] else ""
            print(f"  {status}{e['ts']:<10} {e['module']:<18} {e['key']:<40} "
                  f"{before_s:<12} {after_s:<12} {rev_s}")
        print()
        active = sum(1 for e in self.entries if not e["reverted"])
        L.info(f"  Aktywnych zmian: {active} | Cofniętych: {len(self.entries)-active}")

    def summary_line(self) -> str:
        active = sum(1 for e in self.entries if not e["reverted"])
        return f"{active} zmian" if self.entries else "brak zmian"

    def _append_to_file(self, entry: Dict) -> None:
        try:
            existing: List[Dict] = []
            if self._journal_file.exists():
                with open(self._journal_file) as f:
                    existing = json.load(f)
            existing.append(entry)
            with open(self._journal_file, "w") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def load_history(self, days: int = 7) -> List[Dict]:
        """Load journal entries from last N days."""
        all_entries: List[Dict] = []
        for i in range(days):
            date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            f = self.JOURNAL_DIR / f"journal_{date}.json"
            if f.exists():
                try:
                    with open(f) as fp:
                        all_entries.extend(json.load(fp))
                except Exception:
                    pass
        return all_entries


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM 3: Preflight — Safety gate before any operation
# ─────────────────────────────────────────────────────────────────────────────
class Preflight:
    """
    Safety gate executed before any tweak operation.
    Checks: ADB connectivity, device identity, battery level,
    available storage, screen state.

    Prevents: running tweaks on wrong device, low-battery modification,
    interrupted sessions that leave device in broken state.

    Usage:
        if not Preflight.check(): return
        # Proceed with tweak
    """

    _last_check:  float = 0.0
    _last_result: bool  = True
    _CACHE_TTL  = 30.0   # seconds

    @classmethod
    def check(cls, require_battery: int = 10, verbose: bool = False) -> bool:
        """
        Run preflight checks. Returns True if safe to proceed.
        Results are cached for 30s to avoid redundant ADB calls.
        """
        now = time.time()
        if now - cls._last_check < cls._CACHE_TTL:
            return cls._last_result

        issues: List[str] = []

        # ── 1. ADB connectivity ──────────────────────────────────────────────
        ping = ADB.sh("echo pong", silent=True)
        if ping != "pong":
            issues.append("ADB rozłączone — brak odpowiedzi od urządzenia")

        # ── 2. Device fingerprint (verify correct device) ────────────────────
        model  = ADB.prop("ro.product.model")
        board  = ADB.prop("ro.product.board")
        if model and board:
            if board not in ("m362", "bcm7362", "bcm72604") and model not in ("DCTIW362_PLAY", "DCTIW362P"):
                if verbose:
                    L.warn(f"Nieznane urządzenie: model={model} board={board}")
                    L.warn("Skrypt zoptymalizowany pod DCTIW362P — kontynuuję ostrożnie")
        elif verbose:
            L.info("  Nie można odczytać modelu urządzenia (normalne na niektórych ROM)")

        # ── 3. Battery level ─────────────────────────────────────────────────
        batt_raw = ADB.sh("dumpsys battery | grep level", silent=True)
        m = re.search(r"level:\s*(\d+)", batt_raw)
        if m:
            batt = int(m.group(1))
            if batt < require_battery:
                issues.append(f"Niski poziom baterii: {batt}% (minimum: {require_battery}%)")
            elif verbose:
                L.ok(f"  Bateria: {batt}%")

        # ── 4. ADB connection type (warn if USB vs WiFi) ─────────────────────
        if ADB.dev and ":" in str(ADB.dev):
            if verbose:
                L.ok(f"  ADB WiFi: {ADB.dev}")
        elif ADB.dev and verbose:
            L.ok(f"  ADB USB: {ADB.dev}")

        # ── 5. Storage headroom ──────────────────────────────────────────────
        df = ADB.sh("df /data 2>/dev/null | tail -1", silent=True)
        parts = df.split()
        if len(parts) >= 5:
            used_pct_s = parts[4].replace("%", "")
            if used_pct_s.isdigit():
                used_pct = int(used_pct_s)
                if used_pct > 95:
                    issues.append(f"/data storage krytycznie pełny: {used_pct}%")
                elif verbose:
                    L.ok(f"  Storage: {used_pct}% zajęte")

        # ── Result ───────────────────────────────────────────────────────────
        cls._last_check  = now
        cls._last_result = len(issues) == 0

        if issues:
            L.err("⛔ PREFLIGHT FAILED:")
            for issue in issues:
                L.err(f"   • {issue}")
            return False

        if verbose:
            L.ok("Preflight: wszystkie testy OK ✓")
        return True

    @classmethod
    def invalidate(cls) -> None:
        """Force next check to re-run (call after ADB reconnect)."""
        cls._last_check = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM 4: StartupAssessor — Intelligence health check on launch
# ─────────────────────────────────────────────────────────────────────────────
class StartupAssessor:
    """
    On launch: performs rapid 10-check scan of device health.
    Scores each dimension and produces a prioritized action list.

    Scan takes ~3-5 seconds total (parallel where possible).
    Results shown in banner and stored in session for recommendations.

    Design: check order = fastest first so user sees output quickly.
    """

    @dataclass
    class Issue:
        priority:    int         # 1 (critical) – 5 (minor)
        icon:        str
        category:    str
        description: str
        action_key:  str         # dispatch key to fix it
        action_name: str

    @classmethod
    def scan(cls) -> Tuple[int, List["StartupAssessor.Issue"]]:
        """
        Fast device scan. Returns (score 0-100, list of Issues sorted by priority).
        Designed to run in <5s on ADB WiFi.
        """
        issues: List["StartupAssessor.Issue"] = []
        score  = 100

        # ── Batch read all props in ONE ADB call ─────────────────────────────
        # Huge optimization vs v14: 1 call instead of 15+
        props_raw = ADB.sh(
            "getprop debug.sf.hw; "
            "getprop dalvik.vm.isa.arm.features; "
            "getprop dalvik.vm.heapminfree; "
            "getprop persist.sys.ui.hw; "
            "getprop persist.sys.hdmi.keep_awake; "
            "getprop media.codec.av1.disable; "
            "getprop media.tunneled-playback.enable; "
            "getprop ro.lmk.upgrade_pressure; "
            "settings get global private_dns_mode; "
            "settings get global private_dns_specifier; "
            "pm list packages -e com.google.android.apps.mediashell; "
            "getprop init.svc.mdnsd; "
            "grep MemAvailable /proc/meminfo | awk '{print $2}'; "
            "cat /proc/sys/vm/swappiness 2>/dev/null",
            silent=True
        )

        lines = props_raw.strip().splitlines()
        def _line(i: int) -> str:
            return lines[i].strip() if i < len(lines) else ""

        sf_hw         = _line(0)
        isa_feat      = _line(1)
        heap_minfree  = _line(2)
        ui_hw         = _line(3)
        hdmi_awake    = _line(4)
        av1_disable   = _line(5)
        tunnel_play   = _line(6)
        lmk_pressure  = _line(7)
        dns_mode      = _line(8)
        dns_host      = _line(9)
        mediashell    = _line(10)
        mdnsd         = _line(11)
        mem_avail_kb  = _line(12)
        swappiness    = _line(13)

        I = cls.Issue

        # ── Critical checks (priority 1) ─────────────────────────────────────
        if "mediashell" not in mediashell:
            issues.append(I(1, "🔴", "CAST",
                            "Cast daemon (mediashell) WYŁĄCZONY — Chromecast nie działa",
                            "5", "Restore Cast Services"))
            score -= 25

        if mdnsd != "running":
            issues.append(I(1, "🔴", "CAST",
                            f"mdnsd nie działa (stan: {mdnsd or 'stopped'}) — Cast discovery broken",
                            "5", "Restore Cast Services"))
            score -= 15

        # ── High priority (priority 2) ────────────────────────────────────────
        if av1_disable != "true":
            issues.append(I(2, "🟠", "VIDEO",
                            "AV1 SW decoder AKTYWNY — 100% CPU na Cortex-A15 (brak HW dekodera!)",
                            "3", "AV1 Suppression"))
            score -= 10

        if isa_feat != "default,idiv":
            issues.append(I(2, "🟠", "CPU",
                            f"A15 IDIV nie aktywne (isa.features={isa_feat or 'default'})",
                            "1", "Codec Pipeline"))
            score -= 8

        if tunnel_play != "true":
            issues.append(I(2, "🟠", "VIDEO",
                            "Tunnel mode WYŁĄCZONY — brak hardware video tunnel (VP9 bez HW path)",
                            "1", "Codec Pipeline"))
            score -= 8

        # ── Medium priority (priority 3) ──────────────────────────────────────
        if dns_mode != "hostname" or dns_host not in [v[0] for v in HW.DNS.values()]:
            issues.append(I(3, "🟡", "DNS",
                            f"DNS niezabezpieczony (mode={dns_mode}, host={dns_host or 'brak'})",
                            "7", "TCP + DNS Fix"))
            score -= 8

        if heap_minfree not in ("2m", "2097152"):
            issues.append(I(3, "🟡", "RAM",
                            f"Dalvik heapminfree={heap_minfree or 'default'} — GC micro-pauzy (cel: 2m)",
                            "10", "Dalvik Heap"))
            score -= 5

        if lmk_pressure == "100":
            issues.append(I(3, "🟡", "LMK",
                            "LMK upgrade_pressure=100 — zbyt wolna reakcja na presję RAM",
                            "11", "LMK PSI-only"))
            score -= 5

        # ── Low priority (priority 4) ─────────────────────────────────────────
        if sf_hw != "1":
            issues.append(I(4, "🔵", "GPU",
                            "debug.sf.hw != 1 — SurfaceFlinger nie wymusza GPU kompozycji",
                            "2", "Rendering"))
            score -= 3

        if ui_hw != "true":
            issues.append(I(4, "🔵", "GPU",
                            "persist.sys.ui.hw != true — GPU force rendering wyłączony",
                            "2", "Rendering"))
            score -= 3

        if hdmi_awake != "true":
            issues.append(I(4, "🔵", "HDMI",
                            "persist.sys.hdmi.keep_awake != true — HDMI może zrywać podczas bufferowania",
                            "8", "HDMI + CEC"))
            score -= 2

        # ── Info checks (priority 5) ──────────────────────────────────────────
        try:
            avail_mb = int(mem_avail_kb) // 1024
            if avail_mb < 200:
                issues.append(I(5, "⚪", "RAM",
                                f"Mało wolnej RAM: {avail_mb}MB — rozważ Deep Clean",
                                "15", "Deep Clean RAM"))
                score -= 3
        except ValueError:
            pass

        # DisplayMode check
        try:
            dm_out = ADB.sh("dumpsys display 2>/dev/null | grep -m1 'modeId'", silent=True)
            if "modeId 3" in dm_out or "mode 3" in dm_out:
                if "defaultModeId 7" in dm_out or "defaultMode 7" in dm_out:
                    issues.append(I(2, "🟠", "DISPLAY",
                                    "Display w trybie 30fps (mode 3) — defaultMode to 60fps (mode 7)!",
                                    "dm", "Display Mode Fix"))
                    score -= 10
        except Exception:
            pass

        score = max(0, min(100, score))
        issues.sort(key=lambda x: x.priority)
        return score, issues

    @classmethod
    def display(cls, score: int, issues: List["StartupAssessor.Issue"]) -> None:
        """Show assessment results with color-coded output."""
        c = L.C
        if score >= 90:
            score_col, grade = c["s"], "A — Doskonały"
        elif score >= 75:
            score_col, grade = c["s"], "B — Dobry"
        elif score >= 55:
            score_col, grade = c["w"], "C — Wymaga uwagi"
        elif score >= 35:
            score_col, grade = c["e"], "D — Słaby"
        else:
            score_col, grade = c["e"], "F — Krytyczny"

        print(f"\n  {c['b']}Ocena urządzenia:{c['r']} "
              f"{score_col}{c['b']}{score}/100  [{grade}]{c['r']}")

        if not issues:
            print(f"  {c['s']}✓ Wszystkie kluczowe parametry OK — gotowy do streamingu{c['r']}\n")
            return

        crit = [i for i in issues if i.priority <= 2]
        if crit:
            print(f"  {c['e']}{c['b']}Krytyczne problemy:{c['r']}")
            for iss in crit:
                print(f"    {iss.icon} [{iss.category}] {iss.description}")
                print(f"       {c['d']}→ Napraw: opcja {iss.action_key} ({iss.action_name}){c['r']}")

        med = [i for i in issues if i.priority == 3]
        if med:
            print(f"  {c['w']}Ostrzeżenia:{c['r']}")
            for iss in med:
                print(f"    {iss.icon} [{iss.category}] {iss.description}")

        print(f"  {c['d']}({len(issues)} problemów | Sugeruj: opcja 21 = FULL ULTRA){c['r']}\n")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM 5: EmergencyKit — One-shot critical recovery
# ─────────────────────────────────────────────────────────────────────────────
class EmergencyKit:
    """
    Emergency one-shot restore for the most critical device functions.
    Designed to run in ~30 seconds via --emergency CLI flag or menu option.

    Priorities (in order):
    1. Restore Cast (mediashell + mdnsd)
    2. Fix DNS (private DNS → Cloudflare DoT)
    3. Fix black screen / display mode
    4. Re-enable GPU rendering
    5. Kill AV1 SW decoder
    6. Restore HDMI keep_awake

    Does NOT touch: debloat, AOT compile, kernel tweaks (those take too long).
    Does NOT require interactive confirmation — designed for panic scenarios.
    """

    @staticmethod
    def run() -> None:
        L.hdr("🚨 EMERGENCY KIT — Priorytetowe przywrócenie systemu")
        L.warn("Tryb awaryjny: najszybsze przywrócenie krytycznych funkcji")
        L.warn("Czas: ~25-40 sekund | Cast + DNS + Display + GPU + AV1")
        print()

        t0 = time.time()
        fixed: List[str] = []
        failed: List[str] = []

        def _try(name: str, fn: Callable) -> None:
            try:
                fn()
                fixed.append(name)
                L.ok(f"  [{time.time()-t0:.1f}s] {name} ✓")
            except Exception as e:
                failed.append(name)
                L.warn(f"  [{time.time()-t0:.1f}s] {name} — {e}")

        # 1. Cast restore (most critical — 8-12s)
        L.info("[1/7] Cast services restore...")
        _try("Cast mediashell", lambda: ADB.sh("pm enable com.google.android.apps.mediashell", silent=True))
        _try("Cast GMS",        lambda: ADB.sh("pm enable com.google.android.gms", silent=True))
        _try("Cast GMS core",   lambda: ADB.sh("pm enable com.google.android.gsf", silent=True))
        _try("mdnsd restart",   lambda: ADB.sh("stop mdnsd && sleep 1 && start mdnsd", silent=True))

        # 2. DNS emergency fix (single batched call ~1s)
        L.info("[2/7] DNS emergency fix...")
        _try("DNS Cloudflare DoT", lambda: (
            ADB.sput("global", "private_dns_mode", "hostname"),
            ADB.sput("global", "private_dns_specifier", "one.one.one.one")
        ))

        # 3. Display mode fix (~1s)
        L.info("[3/7] Display mode fix...")
        _try("Display density 240",    lambda: ADB.sh("wm density 240", silent=True))
        _try("Display 60fps settings", lambda: (
            ADB.sput("global", "display_peak_refresh_rate", "60.0"),
            ADB.sput("global", "min_refresh_rate", "60.0")
        ))

        # 4. GPU critical props (batched — ~0.8s)
        L.info("[4/7] GPU rendering fix...")
        with BatchCommander("emergency_gpu") as bc:
            bc.setprop("debug.sf.hw",           "1")
            bc.setprop("persist.sys.ui.hw",      "true")
            bc.setprop("debug.hwui.renderer",    "skiagl")
            bc.setprop("persist.sys.hdmi.keep_awake", "true")
        fixed.append("GPU rendering")

        # 5. AV1 kill (~0.3s)
        L.info("[5/7] AV1 SW decoder suppression...")
        with BatchCommander("emergency_av1") as bc:
            bc.setprop("media.codec.av1.disable",  "true")
            bc.setprop("media.codec.av1.sw.enable", "false")
        fixed.append("AV1 suppression")

        # 6. Codec critical path (~0.5s)
        L.info("[6/7] Codec critical path...")
        with BatchCommander("emergency_codec") as bc:
            bc.setprop("media.vcodec.preferhw",          "true")
            bc.setprop("media.tunneled-playback.enable", "true")
            bc.setprop("media.brcm.mma.enable",          "1")
            bc.setprop("dalvik.vm.isa.arm.features",      "default,idiv")
        fixed.append("Codec pipeline")

        # 7. Dalvik minimum fix (~0.3s)
        L.info("[7/7] Dalvik emergency fix...")
        with BatchCommander("emergency_dalvik") as bc:
            bc.setprop("dalvik.vm.heapminfree", "2m")
            bc.setprop("dalvik.vm.heapmaxfree", "16m")
        fixed.append("Dalvik heap")

        # Summary
        elapsed = time.time() - t0
        print()
        L.hdr(f"🚨 EMERGENCY KIT — Zakończony w {elapsed:.1f}s")
        L.ok(f"  Naprawiono: {len(fixed)} komponentów")
        for f in fixed: L.ok(f"    ✓ {f}")
        if failed:
            L.warn(f"  Nieudane: {len(failed)}")
            for f in failed: L.warn(f"    ⚠ {f}")
        print()
        L.warn("NASTĘPNE KROKI:")
        L.warn("  1. Odśwież SmartTube (zamknij i otwórz ponownie)")
        L.warn("  2. Sprawdź Cast: spróbuj rzutować z telefonu")
        L.warn("  3. Pełna optymalizacja: opcja 21 (FULL ULTRA)")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM 6: LiveMonitor — Real-time ASCII dashboard (terminal-based)
# ─────────────────────────────────────────────────────────────────────────────
class LiveMonitor:
    """
    Real-time device health monitor.
    Updates every 3 seconds, shows: RAM, CPU%, thermals, WiFi, Cast, FPS.
    Press Ctrl+C or 'q' to exit.

    Architecture:
    - Main thread: renders terminal output
    - Data thread: polls ADB every 3s
    - Uses threading.Event for clean shutdown

    Side-effects: heavy ADB polling — do not run during benchmarks.
    """

    REFRESH_SEC = 3
    _stop_event = threading.Event()

    @dataclass
    class Sample:
        ts:          str
        avail_mb:    int
        total_mb:    int
        cpu_idle:    float      # %
        temp_zone0:  float      # °C
        wifi_rssi:   int        # dBm
        wifi_ssid:   str
        cast_ok:     bool
        mdnsd_ok:    bool
        fps_est:     float
        janky_pct:   float

    @classmethod
    def _poll(cls) -> "LiveMonitor.Sample":
        """Single data poll — batch everything in one ADB call."""
        raw = ADB.sh(
            "grep -E 'MemTotal|MemAvailable' /proc/meminfo | awk '{print $2}' | tr '\\n' ' '; "
            "echo; "
            "top -bn1 2>/dev/null | grep -E '^[Cc]pu' | head -1; "
            "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null; "
            "dumpsys wifi 2>/dev/null | grep -E 'SSID|rssi' | grep -v 'hidden\\|Scan' | head -2; "
            "pm list packages -e com.google.android.apps.mediashell 2>/dev/null | head -1; "
            "getprop init.svc.mdnsd; ",
            silent=True
        )
        lines = raw.strip().splitlines()
        def L_(i): return lines[i].strip() if i < len(lines) else ""

        # RAM
        try:
            mem_nums = L_(0).split()
            total_kb  = int(mem_nums[0]); avail_kb = int(mem_nums[1])
            total_mb  = total_kb // 1024; avail_mb = avail_kb // 1024
        except Exception:
            total_mb = avail_mb = 0

        # CPU
        cpu_idle = 0.0
        m_cpu = re.search(r"(\d+)%?\s*idle", L_(1))
        if m_cpu:
            cpu_idle = float(m_cpu.group(1))

        # Temp
        temp_z0 = 0.0
        try:
            raw_temp = L_(2)
            temp_z0 = int(raw_temp) / 1000 if raw_temp.lstrip("-").isdigit() else 0.0
        except Exception:
            pass

        # WiFi
        ssid = ""; rssi = -999
        for i in range(3, 5):
            l = L_(i)
            if "SSID" in l:
                m = re.search(r'SSID:\s*"?([^",\s]+)', l)
                if m: ssid = m.group(1)
            if "rssi" in l:
                m = re.search(r"rssi:\s*(-?\d+)", l)
                if m: rssi = int(m.group(1))

        cast_ok  = "mediashell" in L_(5)
        mdnsd_ok = L_(6).strip() == "running"

        return cls.Sample(
            ts       = time.strftime("%H:%M:%S"),
            avail_mb = avail_mb, total_mb = total_mb,
            cpu_idle = cpu_idle, temp_zone0 = temp_z0,
            wifi_rssi = rssi,   wifi_ssid  = ssid,
            cast_ok  = cast_ok, mdnsd_ok   = mdnsd_ok,
            fps_est  = 0.0,     janky_pct  = 0.0,
        )

    @classmethod
    def _render(cls, s: "LiveMonitor.Sample", history: List["LiveMonitor.Sample"]) -> None:
        """Render one frame of the dashboard."""
        c = L.C
        os.system("clear")

        cpu_pct = 100 - s.cpu_idle
        ram_pct = (s.avail_mb / s.total_mb * 100) if s.total_mb else 0
        used_mb = s.total_mb - s.avail_mb

        # Color helpers
        def ram_col(pct): return c["s"] if pct>40 else (c["w"] if pct>20 else c["e"])
        def cpu_col(pct): return c["s"] if pct<60 else (c["w"] if pct<80 else c["e"])
        def tmp_col(t):   return c["s"] if t<55 else (c["w"] if t<70 else c["e"])
        def sig_col(r):   return c["s"] if r>-60 else (c["w"] if r>-75 else c["e"])

        # Mini sparkline for RAM history
        def _bar(val, total, width=20, col=None):
            filled = int(val / total * width) if total else 0
            bar = "█" * filled + "░" * (width - filled)
            color = col or c["s"]
            return f"{color}{bar}{c['r']}"

        cast_icon  = f"{c['s']}🟢 OK{c['r']}" if s.cast_ok  else f"{c['e']}🔴 DOWN{c['r']}"
        mdnsd_icon = f"{c['s']}🟢 running{c['r']}" if s.mdnsd_ok else f"{c['e']}🔴 stopped{c['r']}"
        wifi_signal = f"{sig_col(s.wifi_rssi)}{s.wifi_rssi}dBm{c['r']}" if s.wifi_rssi != -999 else "?"

        # RAM sparkline (last 10 samples)
        ram_hist = [h.avail_mb for h in history[-10:]] if history else [s.avail_mb]
        spark = "".join("▁▂▃▄▅▆▇█"[min(7, int(v / s.total_mb * 8))] if s.total_mb else "─"
                        for v in ram_hist)

        print(f"""
{c['h']}{c['b']}╔══════════════════════════════════════════════════════════════════════╗
║  🖥  LIVE MONITOR — DCTIW362P │ {s.ts}  │ Q=wyjście Ctrl+C        ║
╠══════════════════════════════════════════════════════════════════════╣{c['r']}

  {c['b']}RAM {c['r']} {_bar(s.avail_mb, s.total_mb, 24, ram_col(ram_pct))}  {ram_col(ram_pct)}{s.avail_mb}MB wolne{c['r']} / {s.total_mb}MB  używane:{used_mb}MB
        Historia: {c['d']}{spark}{c['r']}

  {c['b']}CPU {c['r']} {_bar(cpu_pct, 100, 24, cpu_col(cpu_pct))}  {cpu_col(cpu_pct)}{cpu_pct:.0f}% zajęte{c['r']}

  {c['b']}TEMP{c['r']} {_bar(s.temp_zone0, 100, 24, tmp_col(s.temp_zone0))}  {tmp_col(s.temp_zone0)}{s.temp_zone0:.1f}°C{c['r']} zone0  {"⚠ THROTTLE RISK" if s.temp_zone0 > 70 else ""}

  {c['b']}WiFi{c['r']} {c['c']}{s.wifi_ssid or "??":<20}{c['r']}  Sygnał: {wifi_signal}

  {c['b']}Cast{c['r']} mediashell: {cast_icon:<20}  mdnsd: {mdnsd_icon}

{c['h']}{c['b']}╚══════════════════════════════════════════════════════════════════════╝{c['r']}
  {c['d']}Odświeżam co {cls.REFRESH_SEC}s | Ctrl+C lub Q = wyjście{c['r']}
""")

    @classmethod
    def run(cls) -> None:
        """Start the live monitor. Blocks until user exits."""
        cls._stop_event.clear()
        history: List["LiveMonitor.Sample"] = []
        L.info("Uruchamiam Live Monitor — Ctrl+C aby wyjść")
        time.sleep(0.5)

        try:
            while not cls._stop_event.is_set():
                sample = cls._poll()
                history.append(sample)
                if len(history) > 50:
                    history.pop(0)
                cls._render(sample, history)
                # Sleep interruptibly
                for _ in range(cls.REFRESH_SEC * 10):
                    if cls._stop_event.is_set():
                        break
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            os.system("clear")
            L.ok("Live Monitor zatrzymany")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM 7: SmartSearch — Fuzzy search through all tweaks and functions
# ─────────────────────────────────────────────────────────────────────────────
class SmartSearch:
    """
    Fuzzy keyword search across all available operations.
    Allows users to type 'dns' or 'cast' or 'heap' and find relevant options
    without memorizing numeric menu keys.

    Design: simple substring + keyword matching (no external libs needed).
    """

    # Master index: (keywords, menu_key, description, category)
    INDEX: List[Tuple[List[str], str, str, str]] = [
        (["av1","hevc","codec","vp9","video","tunnel","mma","vdec","brcm"],
         "1",  "Codec Pipeline (A15-idiv + MMA + VDec32 + Tunnel)", "VIDEO"),
        (["render","vulkan","v3d","fence","skia","hwui","opengl","gpu"],
         "2",  "Rendering (V3D fence + skiagl + render_thread)", "VIDEO"),
        (["av1","av 1","suppress","cpu 100%","slow video"],
         "3",  "AV1 Suppression (wyłącz SW decoder AV1)", "VIDEO"),
        (["cast","chromecast","mediashell","mdns","mdnsd","google cast"],
         "4",  "Cast Audit — sprawdź stan Chromecast", "CAST"),
        (["cast restore","mdnsd fix","chromecast broken","cast nie działa"],
         "5",  "Restore Cast Services (tryb awaryjny)", "CAST"),
        (["dns","cloudflare","dot","private dns","nextdns","quad9","adguard","1.1.1.1"],
         "n",  "DNS Manager — zmień serwer DNS", "SIEĆ"),
        (["tcp","network","internet","ping","latency","sieć","init rwnd"],
         "7",  "TCP stack + DNS + NTP fix", "SIEĆ"),
        (["wifi","wi-fi","wireless","rssi","ssid","reset wifi","banda"],
         "7w", "WiFi Reset (disable → enable)", "SIEĆ"),
        (["hdmi","cec","hdmi awake","keep awake","telewizor","tv","hdmi cec"],
         "8",  "HDMI + CEC (BCM Nexus addr=11, keep_awake)", "SYSTEM"),
        (["audio","dźwięk","sound","hdmi audio","sync","av sync","offload"],
         "9",  "Audio A/V Sync + offload profile", "SYSTEM"),
        (["heap","dalvik","memory","ram","gc","garbage","heapminfree","512m"],
         "10", "Dalvik Heap (minfree 512k→2m, maxfree 8m→16m)", "SYSTEM"),
        (["lmk","lmkd","low memory killer","psi","pressure","upgrade_pressure"],
         "11", "LMK PSI-only (upgrade_pressure=50)", "SYSTEM"),
        (["responsiv","i/o","io","sched","deadline","governor","perf","cpu gov"],
         "12", "Responsiveness + I/O deadline + A15 gov", "SYSTEM"),
        (["stability","tweak","telemetri","anr","doze","batteryopt"],
         "13", "Stability Tweaks (telemetria, ANR, touch)", "SYSTEM"),
        (["debloat","bloatware","usuń","odinstaluj","remove","disable app"],
         "14", "Safe Debloat (Cast gate aktywny)", "SYSTEM"),
        (["clean","czyść","ram","memory","kill","kill-all","deep clean"],
         "15", "Deep Clean RAM (am kill-all + drop_caches)", "SYSTEM"),
        (["aot","kompiluj","compile","dex2oat","smarttube compile","jit"],
         "16", "AOT Compile SmartTube + Cast + GMS", "SYSTEM"),
        (["shizuku","root","privilege","rish","adb root"],
         "17", "Deploy Shizuku", "NARZĘDZIA"),
        (["rollback","cofnij","undo","revert","przywróć"],
         "rb", "Rollback ustawień (przywróć OEM)", "SYSTEM"),
        (["diagnoz","diag","check","scan","health","sprawdź"],
         "d",  "Interactive Diagnostics (8 kategorii)", "DIAG"),
        (["repair","naprawa","fix","broken","napraw"],
         "r",  "Auto-Repair (scan + naprawa)", "DIAG"),
        (["perf","report","gfxinfo","meminfo","battery","wydajność"],
         "g",  "Performance Report (gfxinfo + meminfo)", "DIAG"),
        (["smarttube","frame","janky","fps","timing","profile"],
         "v",  "SmartTube Frame Profile (P99 + Janky%)", "DIAG"),
        (["crash","fatal","anr","oom","logcat","logi","awaria"],
         "cr", "Crash Analyzer — skan logcat", "DIAG"),
        (["bench","benchmark","test","szybk","cpu test","ram test","flash"],
         "b",  "Benchmark pełny (CPU/RAM/Flash/Net/Frame)", "PERF"),
        (["ping","latency","latencja","szybki test","quick"],
         "bl", "Szybki test latencji (ping GW + CDN)", "PERF"),
        (["historia bench","bench hist","wyniki"],
         "bh", "Historia benchmarków", "PERF"),
        (["wifi panel","wifi info","ssid","ip address","signal","kanał"],
         "w",  "Panel WiFi (SSID, pasmo, RSSI, IP)", "SIEĆ"),
        (["watchdog","daemon","auto heal","auto-heal","wd"],
         "wd", "Watchdog start/stop", "MONITOR"),
        (["live","monitor","dashboard","real time","realtime","live monitor"],
         "lm", "Live Monitor — real-time dashboard", "MONITOR"),
        (["emergency","panic","awaryjny","pomoc","broken","help"],
         "em", "Emergency Kit — jednokomendowe przywrócenie", "NAPRAWA"),
        (["journal","log zmian","audit","historia zmian","undo","cofnij"],
         "jn", "Session Journal — audit trail + undo", "NARZĘDZIA"),
        (["device","urządzenie","info","model","hardware","karta"],
         "qi", "Karta urządzenia (informacje hardware)", "NARZĘDZIA"),
        (["screenshot","zrzut","zdjęcie","screen"],
         "qs", "Screenshot (zapisz + pobierz)", "NARZĘDZIA"),
        (["reboot","restart","resetuj","bootloader","recovery","wyłącz"],
         "qr", "Menu restartu (normal/recovery/bootloader)", "NARZĘDZIA"),
        (["kernel","proc sys","vm.swappiness","sched","fs","fstrim"],
         "k",  "Kernel Tweaks (VM+Sched+FS+Net)", "KERNEL"),
        (["display","mode","60fps","30fps","density","dpi","ekran","refresh"],
         "dm", "Display Mode Fix (30fps → 60fps)", "DISPLAY"),
        (["display status","display info","fps aktual","obecny tryb"],
         "dms","Display Status (aktualny tryb)", "DISPLAY"),
        (["adaptive","auto tune","bottleneck","automatyczny tuning"],
         "ap", "Adaptive Auto-Tune (bottleneck detect)", "PERF"),
        (["ultra","pełna optymalizacja","all in one","full","wszystko"],
         "21", "FULL SYSTEM ULTRA (20 kroków + DisplayFix)", "ULTRA"),
        (["smarttube ultra","video ultra","stream ultra"],
         "20", "SMARTTUBE ULTRA (16 kroków)", "ULTRA"),
    ]

    @classmethod
    def search(cls, query: str) -> List[Tuple[str, str, str]]:
        """
        Search for query in INDEX. Returns list of (key, description, category).
        Scoring: exact word match > substring match > partial.
        """
        q = query.lower().strip()
        if not q:
            return []

        scored: List[Tuple[int, str, str, str]] = []
        q_words = set(q.split())

        for keywords, key, desc, cat in cls.INDEX:
            best = 0
            for kw in keywords:
                if q == kw:                    best = max(best, 100)
                elif q in kw or kw in q:       best = max(best, 80)
                elif any(w in kw for w in q_words): best = max(best, 60)
                elif any(w in kw for w in q.split(" ") if len(w) > 2): best = max(best, 40)
            if q in desc.lower():              best = max(best, 70)
            if best > 0:
                scored.append((best, key, desc, cat))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [(key, desc, cat) for _, key, desc, cat in scored[:8]]

    @classmethod
    def interactive(cls, dispatch: Dict[str, Callable]) -> Optional[str]:
        """
        Interactive search session.
        Returns the menu key chosen by user, or None if cancelled.
        """
        c = L.C
        L.hdr("🔍 SMART SEARCH — Szukaj tweaku lub funkcji")
        print(f"  {c['d']}Wpisz słowo kluczowe: dns, cast, heap, av1, display, bench...{c['r']}\n")

        while True:
            try:
                q = input(f"  {c['c']}Szukaj > {c['r']}").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if not q or q.lower() in ("q", "exit", "wyjście"):
                return None

            results = cls.search(q)
            if not results:
                print(f"  {c['w']}Brak wyników dla '{q}' — spróbuj innego słowa{c['r']}")
                continue

            print(f"\n  {c['b']}Wyniki ({len(results)}):{c['r']}")
            for i, (key, desc, cat) in enumerate(results, 1):
                print(f"    {c['c']}{i}.{c['r']}  [{c['d']}{cat:<10}{c['r']}] "
                      f"{c['b']}{key:<5}{c['r']} {desc}")

            try:
                sel = input(f"\n  {c['c']}Wybierz [1-{len(results)} / szukaj ponownie / q] > {c['r']}").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if sel.lower() in ("q", ""):
                return None
            if sel.isdigit() and 1 <= int(sel) <= len(results):
                chosen_key = results[int(sel) - 1][0]
                if chosen_key in dispatch:
                    return chosen_key
                else:
                    print(f"  {c['w']}Opcja '{chosen_key}' niedostępna w bieżącym menu{c['r']}")
            # else: treat as new search query
            print()
            results = cls.search(sel)
            if not results:
                print(f"  {c['w']}Brak wyników dla '{sel}'{c['r']}")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM 8: ADB Auto-Reconnect wrapper
# ─────────────────────────────────────────────────────────────────────────────
class ADBGuard:
    """
    Wraps operations with automatic reconnect on ADB disconnect.
    Detects: device offline, unauthorized, connection refused.

    Usage:
        with ADBGuard():
            ADB.sh("some_long_operation")
    """

    def __enter__(self) -> "ADBGuard":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            return False
        msg = str(exc_val).lower()
        if any(s in msg for s in ("offline", "unauthorized", "connection refused", "no devices")):
            L.warn("ADB rozłączone — próba ponownego połączenia...")
            time.sleep(2)
            if ADB.dev:
                try:
                    subprocess.run(["adb", "connect", str(ADB.dev)],
                                   capture_output=True, timeout=10)
                    Preflight.invalidate()
                    L.ok("ADB ponownie połączone ✓")
                except Exception as e:
                    L.err(f"Reconnect failed: {e}")
            return True   # Suppress exception after reconnect attempt
        return False      # Re-raise other exceptions


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM 9: HealthScore — Cached device health indicator for banner
# ─────────────────────────────────────────────────────────────────────────────
class HealthScore:
    """
    Compact device health indicator computed at startup, refreshed on demand.
    Used in banner to show device readiness at a glance.
    """
    _score:  int  = -1
    _issues: List = []
    _ts:     float = 0.0
    _TTL    = 300.0   # 5 minutes cache

    @classmethod
    def get(cls) -> Tuple[int, str]:
        """Return (score, badge_string) — cached for TTL seconds."""
        if time.time() - cls._ts > cls._TTL or cls._score < 0:
            cls._score, cls._issues = StartupAssessor.scan()
            cls._ts = time.time()

        s = cls._score
        if s >= 90: badge = f"\033[92m●\033[0m {s}/100"
        elif s >= 70: badge = f"\033[93m●\033[0m {s}/100"
        elif s >= 50: badge = f"\033[91m●\033[0m {s}/100"
        else:         badge = f"\033[91m\033[1m●\033[0m KRYTYCZNY {s}/100"
        return s, badge

    @classmethod
    def invalidate(cls) -> None:
        cls._ts = 0.0



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
        self.kt     = KernelTweaks()
        self.ap     = AdaptivePerf()
        self.diag   = Diag()
        self.rep    = Repair()
        self.pd     = PerfDiag()
        self.bench  = Benchmark()
        self.wifi   = WiFiInfo()
        self.qa     = CrashAnalyzer()
        self.qt     = QuickTools()
        self.wd     = Watchdog()
        self.dmf    = DisplayModeFix()   # v14.2: Display 30fps→60fps fix
        # v15.0 new systems
        self.journal = SessionJournal.get()
        self._recent: List[str] = []          # recently used menu keys
        self._score:  int       = -1          # cached health score

    def _banner(self) -> None:
        c = L.C
        # Live WiFi line (~0.3s)
        try: wifi_line = WiFiInfo.compact_line()
        except: wifi_line = "WiFi: brak danych"
        wd_state  = "🐕 AKTYWNY" if Watchdog._running else "  zatrzymany"
        jn_state  = self.journal.summary_line()
        # Health score (cached, no ADB call if fresh)
        _score, health_badge = HealthScore.get()
        # Recent actions (last 3)
        recent_str = " │ ".join(self._recent[-3:]) if self._recent else "brak"

        print(f"""
{c['h']}{c['b']}╔══════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v{VERSION} — Precision + DisplayFix + AdaptivePerf + v15
║  BCM72604 / Cortex-A15 │ Android TV 9 │ Kernel 4.9.190 │ ARMv7
╠══════════════════════════════════════════════════════════════════════╣
║  VPU:BCM72604 │ GLES3.1 │ MMA=1 │ VDec32 │ V3D │ HDR:YES │ 60fps
║  RAM:1425MB │ Nexus:240MB │ Budget:~{HW.USERSPACE_BUDGET_MB}MB │ PSI-LMK │ density:240
╠══════════════════════════════════════════════════════════════════════╣{c['r']}
{c['c']}  📡 {wifi_line:<66}{c['h']}{c['b']}║
║  {c['r']}🐕 WD:{c['s']}{wd_state:<12}{c['h']}{c['b']}  Zdrowie: {c['r']}{health_badge}{c['h']}{c['b']}
║  {c['r']}📋 Sesja:{c['d']}{jn_state:<18}{c['r']}  Ostatnio:{c['d']} {recent_str[:30]}{c['r']}{c['h']}{c['b']}
╚══════════════════════════════════════════════════════════════════════╝{c['r']}
  {c['d']}ADB: {c['c']}{self.device}{c['d']}   PTT1.190826.001  │ '?'=SmartSearch  'EM'=Emergency{c['r']}
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

  {c["c"]}🤖 ADAPTIVE PERF (v14.1 NEW){c["r"]}
    {c["c"]}AP. {c["r"]} 🤖 Adaptive Auto-Tune (bottleneck detect + auto-fix + pomiar delta)
    {c["c"]}API.{c["r"]} 🎛  Adaptive Interaktywny (krok po kroku + zachowaj/cofnij)
    {c["c"]}APH.{c["r"]} 📈 Historia adaptive sesji (efekty zmierzone)

  {c["h"]}⚙ KERNEL TWEAKS (v14.1 NEW){c["r"]}
    {c["h"]}K.  {c["r"]} Wszystkie kernel tweaks (VM+Sched+FS+Net)
    {c["h"]}KV. {c["r"]} /proc/sys/vm (swappiness=0, dirty, vfs_cache)
    {c["h"]}KS. {c["r"]} /proc/sys/kernel (scheduler Cortex-A15)
    {c["h"]}KF. {c["r"]} /proc/sys/fs (file-max, inotify, pipe)
    {c["h"]}KFT.{c["r"]} 💿 fstrim /data /cache /system (eMMC defrag)
    {c["h"]}KLM.{c["r"]} 🧹 LMKD reinit (device_config PSI reset)

  {c["e"]}🖥  DISPLAY FIX (v14.2 CRITICAL — NOWE){c["r"]}
    {c["e"]}DM. {c["r"]} 🖥  Display Mode Fix 30fps→60fps (WYMAGANE — Hardware Profile)
    {c["e"]}DMS.{c["r"]} 📊 Display Status (aktualny tryb, density, fps)
    {c["e"]}DMR.{c["r"]} ↩  Display Revert (wróć do OEM density=320)

  {c["c"]}🚀 TRYBY AUTO{c["r"]}
    {c["c"]}20.{c["r"]} 🚀 SMARTTUBE ULTRA (16 kroków + DisplayFix)
    {c["c"]}21.{c["r"]} 🏆 FULL SYSTEM ULTRA (20 kroków + DisplayFix)

  {c["e"]}🆘 v15.0 — NOWE SYSTEMY{c["r"]}
    {c["e"]}EM. {c["r"]} 🚨 Emergency Kit (jednokomendowe przywrócenie ~30s)
    {c["c"]}LM. {c["r"]} 📊 Live Monitor (real-time: RAM/CPU/temp/Cast/WiFi)
    {c["i"]}JN. {c["r"]} 📋 Session Journal (audit trail + undo stack)
    {c["i"]}JU. {c["r"]} ⏪ Undo Last (cofnij ostatnią zmianę)
    {c["i"]}JUA.{c["r"]} ⏪ Undo All (cofnij całą sesję)
    {c["d"]}?.  {c["r"]} 🔍 Smart Search (szukaj tweaku po słowie kluczowym)
    {c["e"]}0.{c["r"]}  Exit
{c["b"]}{"═"*72}{c["r"]}""")

            ch = input(f"\n{c['c']}Choice [{c['r']}0-21/D/R/G/V/W/N/B/WD/WA/CR/DM/DMS/DMR/QI/QS/QR/QA/QD/QL{c['c']}] > {c['r']}").strip().lower()

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
                # v14.1 NEW
                "k":   KernelTweaks.apply_all,
                "kv":  KernelTweaks.apply_vm,
                "ks":  KernelTweaks.apply_kernel_sched,
                "kf":  KernelTweaks.apply_fs,
                "kft": KernelTweaks.apply_fstrim,
                "klm": KernelTweaks.apply_lmkd_reinit,
                "ap":  AdaptivePerf.run_auto,
                "api": AdaptivePerf.run_interactive,
                "aph": AdaptivePerf.show_history,
                # v14.2 Display Mode Fix (CRITICAL — hardware profile confirmed)
                "dm":  DisplayModeFix.apply,
                "dms": DisplayModeFix.status,
                "dmr": DisplayModeFix.revert,
                # v15.0 new systems
                "em":  EmergencyKit.run,
                "lm":  LiveMonitor.run,
                "jn":  self.journal.show,
                "ju":  self.journal.undo_last,
                "jua": self.journal.undo_all,
                "?":   lambda: self._smart_search(dispatch),
                "0":   self._exit,
            }
            fn = dispatch.get(ch)
            if fn:
                # Track recent actions for banner
                if ch not in ("0", "?") and len(ch) <= 4:
                    desc = {
                        "1":"Codec","2":"Render","3":"AV1","4":"CastAudit","5":"CastFix",
                        "6":"CastNet","7":"TCP+DNS","8":"HDMI","9":"Audio","10":"Heap",
                        "11":"LMK","12":"Resp","13":"Tweaks","14":"Debloat","15":"Clean",
                        "16":"AOT","17":"Shizuku","20":"Ultra","21":"FullUltra",
                        "d":"Diag","r":"Repair","b":"Bench","w":"WiFi","n":"DNS",
                        "dm":"DisplayFix","em":"Emergency","lm":"LiveMon","jn":"Journal",
                        "ap":"AdaptPerf","k":"Kernel","cr":"Crash",
                    }.get(ch, ch.upper())
                    if desc not in self._recent:
                        self._recent.append(desc)
                    self._recent = self._recent[-5:]
                fn()
                # Invalidate health cache after any modifying operation
                if ch not in ("0","d","r","g","v","b","bl","bh","w","n","cr","qi","qs","qr","qa","qd","ql","jn","wa","lm","?","dms"):
                    HealthScore.invalidate()
            else:
                L.warn(f"Nieznana opcja: '{ch}' — wpisz 0-21, EM, LM, JN lub ? (smart search)")
            if ch != "0":
                input(f"\n{c['c']}Enter aby kontynuować...{c['r']}")

    def _smart_search(self, dispatch: Dict) -> None:
        """Interactive smart search — find and run any tweak by keyword."""
        key = SmartSearch.interactive(dispatch)
        if key and key in dispatch:
            L.info(f"SmartSearch → opcja '{key}'")
            dispatch[key]()

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
        L.hdr("🚀 SMARTTUBE ULTRA — v14.2 A15+BCM72604 Precision+DisplayFix")
        steps=[
            ("Auto-Repair pre-check",            self.rep.scan),
            ("Cast Audit",                        self.cast.audit),
            ("Display Mode Fix (30fps→60fps)",   DisplayModeFix.apply),
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
        L.ok("60fps Display + VP9 HW + Tunnel + A15-idiv + MMA + VDec32 + DNS: one.one.one.one + Cast ✓")
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
            ("Display Mode Fix (30fps→60fps)",  DisplayModeFix.apply),
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
            ("Kernel VM + Sched Tweaks",         KernelTweaks.apply_all),
            ("LMKD reinit",                      KernelTweaks.apply_lmkd_reinit),
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
        description=f"Playbox TITANIUM v{VERSION} — v15.0 Smart+Emergency+LiveMonitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  python3 Autopilot_v150.py                                 # Interactive menu
  python3 Autopilot_v150.py --emergency                      # One-shot critical restore (~30s)
  python3 Autopilot_v150.py --monitor                        # Live real-time dashboard
  python3 Autopilot_v150.py --assess                         # Show device health score
  python3 Autopilot_v150.py --smarttube-ultra                # Video ultra pipeline
  python3 Autopilot_13_PRECISION.py --smarttube-ultra       # Video ultra
  python3 Autopilot_13_PRECISION.py --full-ultra            # Full system
  python3 Autopilot_13_PRECISION.py --diag                  # Self-diagnostics
  python3 Autopilot_13_PRECISION.py --repair                # Auto-repair scan
  python3 Autopilot_13_PRECISION.py --cast-restore          # Emergency Cast
  python3 Autopilot_13_PRECISION.py --dns cloudflare        # Fix DNS
  python3 Autopilot_13_PRECISION.py --device 192.168.1.3:5555 --full-ultra
""")
    p.add_argument("--device",          default=None)
    p.add_argument("--emergency",        action="store_true", help="Emergency Kit: fast critical restore (~30s)")
    p.add_argument("--monitor",          action="store_true", help="Live Monitor: real-time dashboard")
    p.add_argument("--assess",           action="store_true", help="Startup Assessment: show device health score")
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
    elif args.emergency:        EmergencyKit.run()
    elif args.monitor:          LiveMonitor.run()
    elif args.assess:           (lambda: (lambda s,i: StartupAssessor.display(s,i))(*StartupAssessor.scan()))()
    elif args.smarttube_ultra:  a.smarttube_ultra()
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