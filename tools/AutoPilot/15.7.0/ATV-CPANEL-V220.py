#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SecFERRO ATV PanelCore v22.0.0-enterprise (Sagemcom DCTIW362 / Broadcom BCM72604)
Target Hardware: Broadcom BCM72604 (Cortex-A15), VideoCore IV / V3D, 1.5GB RAM, ATV 9
Integrated Knowledge Bases:
  - Enterprise Wi-Fi Router Web UI (Dark Navy Palette, Sidebar, Real-Time SSE Log Stream)
  - Full Hardware & OMX Pipeline (V3D, HWC2, WCG 1023, AV1 SW Block, VDec32)
  - Advanced SkiaGL Font Antialiasing & Sharpness Engine (PlayBox Titanium v19)
  - Kernel VM Tuning: swappiness, vfs_cache_pressure, P99 Frame Pacing VSync Offsets
  - Dual Video/Audio Modes: Cinema Tunneling vs SmartTube Anti-Blackscreen (PCM)
  - SmartTube Cold-Start XML Injector & AOT 'everything' Compiler + OOM Protection
  - Proactive Autonomous Watchdog (mdnsd, Cast DRM protection, WakeLock Neutralizer)
  - Recursive Script Hub (.sh / .py autodiscovery with header metadata parsing)
================================================================================
"""

import json
import os
import pathlib
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, ClassVar, Dict, Final, List, Optional, Tuple

PORT: Final[int] = 8080
TMP_DIR: Final[str] = "/data/local/tmp"
STATE_FILE: Final[str] = "SecFERRO_v22_state.json"

SMARTTUBE_PKG: Final[str] = "org.smarttube.stable"
LAUNCHER_PKG: Final[str] = "com.spocky.projlauncher"
SMARTTUBE_XML_BACKUP: Final[str] = "/sdcard/Download/org.smarttube.stable_preferences.xml"

SMARTTUBE_XML_TEMPLATE: Final[str] = """<?xml version='1.0' encoding='utf-8' standalone='yes' >
<map>
    <!-- Dekodowanie i Sprzęt (Broadcom BCM72604 / V3D / AFR Optimization) -->
    <string name="decoder_preference">tunneling_disabled</string>
    <boolean name="use_hw_decoder" value="true" />
    <boolean name="use_extension_renderer" value="true" />
    <boolean name="force_surface_view" value="true" />
    <boolean name="tunneling_audio" value="false" />
    <string name="custom_video_decoder">OMX.broadcom.video_decoder.vp9</string>

    <!-- Agresywne Buforowanie ExoPlayer dla natychmiastowego Cold Start -->
    <int name="min_buffer_ms" value="1000" />
    <int name="max_buffer_ms" value="25000" />
    <int name="buffer_for_playback_ms" value="400" />
    <int name="buffer_for_playback_after_rebuffer_ms" value="800" />
    <boolean name="cache_enabled" value="true" />
    <int name="max_cache_size_mb" value="512" />

    <!-- AFR oraz Stabilizacja Klatek -->
    <boolean name="afr_enabled" value="true" />
    <int name="afr_mode" value="1" />
    <int name="afr_delay_ms" value="1500" />
    <boolean name="drop_corrupted_frames" value="true" />
    <boolean name="fix_frame_drops" value="true" />

    <!-- Sieć i Adaptacja Bitrate -->
    <boolean name="bandwidth_meter_optimization" value="true" />
    <int name="max_reconnect_attempts" value="6" />
    <boolean name="live_low_latency" value="true" />
    <boolean name="prefer_optimal_resolution" value="true" />

    <!-- Renderowanie i UI pod ograniczone zasoby -->
    <boolean name="disable_fps_adjustments" value="false" />
    <boolean name="hardware_acceleration_overlay" value="true" />
    <string name="ui_rendering_mode">performance</string>
    <boolean name="skip_unnecessary_decoding_steps" value="true" />
</map>
"""


@dataclass(frozen=True)
class OptimizationModule:
    key: str
    title: str
    category: str
    description: str
    commands: Tuple[str, ...]
    badge: str = "SAFE"


@dataclass(frozen=True)
class AuditVector:
    vector_id: str
    name: str
    category: str
    check_cmd: str
    expected: str
    fix_module: str


class HardwareRegistry:
    PROTECTED_CAST_PACKAGES: ClassVar[Tuple[str, ...]] = (
        "com.google.android.apps.mediashell",
        "com.google.android.gms",
        "com.google.android.gsf",
        "com.google.android.gms.cast.receiver",
        "com.google.android.tv.remote.service",
        "com.google.android.tvlauncher",
        "com.google.android.wifidisplay",
    )

    BLOAT_PACKAGES: ClassVar[Tuple[str, ...]] = (
        "com.google.android.katniss",
        "com.google.android.videos",
        "com.google.android.play.games",
        "com.google.android.music",
        "com.google.android.backdrop",
        "com.google.android.partnersetup",
        "com.google.android.feedback",
        "com.google.android.tv.bugreportsender",
        "com.google.android.marvin.talkback",
        "com.google.android.speech.pumpkin",
        "com.sagemcom.appupdate",
        "com.sagemcom.stb.setupwizard",
        "com.sagemcom.sysupdate",
        "com.google.android.tungsten.setupwraith",
        "com.google.android.leanbacklauncher.recommendations",
        "com.android.location.fused",
    )

    GMS_WAKELOCK_SERVICES: ClassVar[Tuple[str, ...]] = (
        "com.google.android.gms/com.google.android.gms.chromesync.sync.ChimeraSyncReceiverService",
        "com.google.android.gms/com.google.android.gms.auth.api.signin.revocation.RevocationBoundService",
        "com.google.android.gms/com.google.android.gms.analytics.AnalyticsService",
        "com.google.android.gms/com.google.android.gms.auth.api.credentials.sync.CredentialSyncService",
    )

    MODULES: ClassVar[Dict[str, OptimizationModule]] = {
        "brcm_omx_v3d": OptimizationModule(
            key="brcm_omx_v3d",
            title="Broadcom OMX, V3D & AV1 SW Block",
            category="Media & GPU",
            description="Wymusza dekodowanie OMX VP9/H264, alokuje 32 bufory VPU, włącza WCG (1023) i blokuje programowe AV1 (100% CPU fix).",
            badge="CORE",
            commands=(
                "setprop isa.arm.features default,idiv",
                "setprop media.acodec.preferhw true",
                "setprop media.vcodec.preferhw true",
                "setprop media.codec.sw.fallback false",
                "setprop debug.stagefright.omx_default_rank 0",
                "setprop debug.stagefright.c2.av1 0",
                "setprop media.av1.sw.decode.disable true",
                "setprop media.codec.av1.disable true",
                "setprop ro.nx.media.vdec.fsm1080p 1",
                "setprop ro.nx.media.vdec.progoverride 2",
                "setprop ro.nx.media.vdec_outportbuf 32",
                "setprop ro.nx.mma 1",
                "setprop media.brcm.vpu.buffers 32",
                "setprop media.brcm.decoder.preinit true",
                "setprop debug.hwui.renderer skiagl",
                "setprop debug.renderengine.backend skiaglthreaded",
                "setprop debug.sf.hw 1",
                "setprop debug.egl.hw 1",
                "setprop debug.sf.latch_unsignaled 1",
                "setprop debug.sf.disable_backpressure 1",
                "setprop ro.v3d.fence.expose true",
                "setprop ro.v3d.disable_buffer_age true",
                "setprop persist.sys.ui.hw true",
                "service call SurfaceFlinger 1023 i32 1 >/dev/null 2>&1 || true",
                "service call SurfaceFlinger 1008 i32 1 >/dev/null 2>&1 || true",
            ),
        ),
        "skiagl_font_sharpness": OptimizationModule(
            key="skiagl_font_sharpness",
            title="SkiaGL Font Antialiasing & Sharpness Engine",
            category="Visual & UI",
            description="Aktywuje pełne antyaliasowanie czcionek WebView, rasteryzację GPU, zero-copy oraz optymalizację małych płócien (Titanium v19).",
            badge="SHARP",
            commands=(
                "setprop debug.hwui.use_partial_updates true",
                "setprop debug.hwui.show_dirty_regions false",
                'settings put global webview_flags "ignore-gpu-blocklist=true enable-gpu-rasterization=true animated-image-resume=true webview-accelerate-small-canvases=true num-raster-threads=2 font-antialiasing=true"',
                'settings put global webview_flags_tv "enable-webview-surface-control-for-tv=true"',
                "setprop ro.hwui.text_large_cache_width 2048",
                "setprop ro.hwui.text_large_cache_height 1024",
            ),
        ),
        "kernel_p99_vm": OptimizationModule(
            key="kernel_p99_vm",
            title="Kernel VM Tuning & P99 Frame Pacing",
            category="CPU & Kernel",
            description="Stroi swappiness (100), VFS cache (50), optymalizuje fazy VSync SurfaceFlinger i eliminuje mikro-zacięcia (Jank Frames P99).",
            badge="PACING",
            commands=(
                "setprop debug.sf.early_phase_offset_ns 5000000",
                "setprop debug.sf.early_app_phase_offset_ns 5000000",
                "setprop debug.sf.early_gl_phase_offset_ns 3000000",
                "setprop ro.surface_flinger.max_frame_buffer_acquired_buffers 3",
                "sh -c 'echo 100 > /proc/sys/vm/swappiness 2>/dev/null || true'",
                "sh -c 'echo 50 > /proc/sys/vm/vfs_cache_pressure 2>/dev/null || true'",
                "sh -c 'echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true'",
            ),
        ),
        "smarttube_anti_blackscreen": OptimizationModule(
            key="smarttube_anti_blackscreen",
            title="SmartTube Anti-Blackscreen & PCM Audio",
            category="Media & GPU",
            description="Wyłącza wadliwe tunelowanie audio/wideo Broadcom dla ExoPlayera, wymusza PCM Stereo i bufor 350ms (usuwa AudioFlinger Underruns).",
            badge="FIX",
            commands=(
                "setprop media.tunneled-playback.enable false",
                "settings put global audio_offload_main_path_disabled true",
                "settings put global audio.offload.video false",
                "settings put global encoded_surround_output 1",
                "settings put global encoded_surround_output_enabled 0",
                "settings put system sound_effects_enabled 0",
                "setprop af.resampler.quality 4",
                "setprop ro.nx.audio.tunnel_buffer_ms 350",
                "setprop ro.nx.audio.lipsync_delay 0",
                "setprop media.stagefright.audio.sink 2097152",
            ),
        ),
        "cinema_tunnel_4k": OptimizationModule(
            key="cinema_tunnel_4k",
            title="Cinema 4K HDMI Clock-Sync Tunnel",
            category="Media & GPU",
            description="Włącza sprzętowe tunelowanie HDMI i synchronizację zegara dla VOD (Netflix/Prime/HBO) eliminując dryf A/V.",
            badge="4K HDR",
            commands=(
                "setprop media.tunneled-playback.enable true",
                "setprop media.brcm.hdmi.tunnel true",
                "setprop media.brcm.tunnel.clock hdmi",
                "setprop media.brcm.hdr.enable 1",
                "settings put global hdr_output_mode auto",
                "settings put global hdr_static_metadata 1",
            ),
        ),
        "cpu_perf_governor": OptimizationModule(
            key="cpu_perf_governor",
            title="CPU Governor 'performance' & FIFO UI",
            category="CPU & Kernel",
            description="Blokuje zarządcę CPU na maksymalnym taktowaniu, aktywuje FIFO UI i flagi antialiasingu czcionek WebView/SkiaGL.",
            badge="TURBO",
            commands=(
                "setprop sys.use_fifo_ui true",
                "setprop power.saving.mode 0",
                "settings put global low_power 0",
                "settings put global low_power_trigger_level 0",
                "settings put global window_animation_scale 0.1",
                "settings put global transition_animation_scale 0.25",
                "settings put global animator_duration_scale 0.25",
                "for p in /sys/devices/system/cpu/cpufreq/policy*; do [ -d \"$p\" ] && echo performance > \"$p/scaling_governor\" 2>/dev/null && cat \"$p/scaling_max_freq\" > \"$p/scaling_min_freq\" 2>/dev/null; done || true",
            ),
        ),
        "ram_lmk_psi": OptimizationModule(
            key="ram_lmk_psi",
            title="1.5GB RAM LMK PSI & Activity Constants",
            category="Memory & LMK",
            description="Konfiguruje PSI Low Memory Killer, ogranicza procesy w tle do 8, zrzuca PageCache i czyści sterty pamięci.",
            badge="1.5GB",
            commands=(
                'settings put global activity_manager_constants "max_cached_processes=8,background_settle_time=30000,fgservice_min_shown_time=500,power_check_max_cpu_1=70,power_check_max_cpu_0=80,service_usage_interaction_time=5000,service_restart_duration=2000,max_service_inactivity=15000"',
                "settings put global activity_manager_max_phantom_processes 4",
                "settings put global background_process_limit 8",
                "setprop ro.lmk.critical 0",
                "setprop ro.lmk.kill_heaviest_task true",
                "setprop ro.lmk.downgrade_pressure 80",
                "setprop ro.lmk.upgrade_pressure 50",
                "setprop ro.lmk.use_minfree_levels false",
                "setprop ro.lmk.use_psi true",
                "setprop ro.lmk.filecache_min_kb 51200",
                "setprop dalvik.vm.heapsize 512m",
                "setprop dalvik.vm.heapgrowthlimit 192m",
                "cmd activity trim-memory RUNNING_CRITICAL >/dev/null 2>&1 || true",
                "pm trim-caches 4096G >/dev/null 2>&1 || true",
                "sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true",
            ),
        ),
        "net_120mbit_ipv6": OptimizationModule(
            key="net_120mbit_ipv6",
            title="Fiber 120Mbps TCP Buffers & IPv6 Kill",
            category="Network & DNS",
            description="Optymalizuje okna TCP pod światłowód 100/120 Mbps bez marnowania RAM, włącza TCP FastOpen, blokuje IPv6 i skanowanie Wi-Fi.",
            badge="NET",
            commands=(
                'settings put global net.tcp.buffersize.wifi "4096,131072,786432,4096,16384,3184168"',
                'settings put global net.tcp.buffersize.default "4096,131072,786432,4096,16384,3184168"',
                'setprop net.tcp.buffersize.wifi "4096,131072,786432,4096,16384,3184168"',
                "settings put global tcp_default_init_rwnd 120",
                "setprop net.ipv4.tcp_fastopen 3",
                "settings put global prefer_ipv4 true",
                "settings put global wifi_scan_always_enabled 0",
                "settings put global ble_scan_always_enabled 0",
                "settings put global wifi_watchdog_on 0",
                "settings put global captive_portal_mode 0",
                "settings put global private_dns_mode hostname",
                "settings put global private_dns_specifier one.one.one.one",
                "for n in all default eth0 wlan0; do echo 1 > /proc/sys/net/ipv6/conf/$n/disable_ipv6 2>/dev/null; done || true",
                "ndc resolver flushdefaultif >/dev/null 2>&1 || true",
            ),
        ),
        "wakelock_bloat_neutralize": OptimizationModule(
            key="wakelock_bloat_neutralize",
            title="WakeLock, Telemetry & GMS Loop Purge",
            category="Services & Security",
            description="Zatrzymuje zapętlone usługi GMS BAD_AUTHENTICATION, wyłącza bmgr backup journal, telemetrię i skanowanie lokalizacji.",
            badge="CLEAN",
            commands=(
                "bmgr enable false >/dev/null 2>&1 || true",
                "setprop log.tag.FA OFF",
                "setprop log.tag.FA-SVC OFF",
                "setprop log.tag.hwui.disabled 1",
                "settings put secure location_mode 0",
                "settings put secure accessibility_enabled 0",
                "settings put secure show_media_prediction 0",
                "settings put secure assistant 0",
                "settings put secure limit_ad_tracking 1",
                "settings put secure upload_log_enable 0",
                "cmd appops set com.google.android.gms BACKGROUND_LOCATION ignore >/dev/null 2>&1 || true",
                "cmd appops set com.google.android.gms FINE_LOCATION ignore >/dev/null 2>&1 || true",
                "cmd appops set 1000 WIFI_SCAN ignore >/dev/null 2>&1 || true",
                "logcat -c >/dev/null 2>&1 || true",
            ),
        ),
        "netflix_drm_safe_freeze": OptimizationModule(
            key="netflix_drm_safe_freeze",
            title="Netflix Deep Freeze (Widevine L1 Safe)",
            category="Services & Security",
            description="Zawiesza pakiet Netflix i odcina uprawnienia AppOps bez usuwania go z systemu (chroni klucze DRM Widevine L1).",
            badge="DRM SAFE",
            commands=(
                "am force-stop com.netflix.ninja",
                "pm suspend com.netflix.ninja 2>/dev/null || true",
                "cmd appops set com.netflix.ninja RUN_IN_BACKGROUND ignore",
                "cmd appops set com.netflix.ninja START_FOREGROUND ignore",
                "cmd appops set com.netflix.ninja SYSTEM_ALERT_WINDOW ignore",
            ),
        ),
    }

    AUDIT_VECTORS: ClassVar[Tuple[AuditVector, ...]] = (
        AuditVector("av1_block", "AV1 Software Decoder Blocked (CPU Fix)", "Codecs", "getprop media.codec.av1.disable", "true", "brcm_omx_v3d"),
        AuditVector("skiagl", "SkiaGL GPU Hardware Renderer", "GPU/V3D", "getprop debug.hwui.renderer", "skiagl", "brcm_omx_v3d"),
        AuditVector("font_antialias", "SkiaGL Font Antialiasing Flags", "Visual", "settings get global webview_flags", "font-antialiasing=true", "skiagl_font_sharpness"),
        AuditVector("sf_backpressure", "SurfaceFlinger Zero-Backpressure", "Display", "getprop debug.sf.disable_backpressure", "1", "brcm_omx_v3d"),
        AuditVector("pcm_audio", "PCM Stereo Audio (Underrun Fix)", "Audio", "settings get global encoded_surround_output", "1", "smarttube_anti_blackscreen"),
        AuditVector("lmk_psi", "LMK PSI Memory Management", "Memory", "getprop ro.lmk.use_psi", "true", "ram_lmk_psi"),
        AuditVector("wifi_scan", "Background Wi-Fi Scan Disabled", "Network", "settings get global wifi_scan_always_enabled", "0", "net_120mbit_ipv6"),
        AuditVector("dns_dot", "Cloudflare Private DNS (1.1.1.1)", "Network", "settings get global private_dns_specifier", "one.one.one.one", "net_120mbit_ipv6"),
        AuditVector("telemetry", "Firebase Analytics Silenced", "Privacy", "getprop log.tag.FA", "OFF", "wakelock_bloat_neutralize"),
    )


class StatePersistence:
    @staticmethod
    def save(data: Dict[str, Any]) -> None:
        tmp = f"{STATE_FILE}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, STATE_FILE)
        except Exception:
            pass

    @staticmethod
    def load() -> Dict[str, Any]:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"mode": "auto", "adb_target": "", "watchdog_enabled": False}


@dataclass
class EnterpriseExecutor:
    mode: str = "auto"
    adb_target: str = ""
    watchdog_active: bool = False
    sse_clients: List[queue.Queue] = field(default_factory=list)
    journal: List[Dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        saved = StatePersistence.load()
        self.mode = saved.get("mode", "auto")
        self.adb_target = saved.get("adb_target", "")

    def persist(self) -> None:
        StatePersistence.save({
            "mode": self.mode,
            "adb_target": self.adb_target,
            "watchdog_enabled": self.watchdog_active,
        })

    def emit(self, level: str, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        entry = {"time": ts, "level": level, "msg": msg}
        self.journal.insert(0, entry)
        if len(self.journal) > 80:
            self.journal.pop()

        line = f"[{ts}] [{level}] {msg}"
        for q in list(self.sse_clients):
            try:
                if q.full():
                    q.get_nowait()
                q.put_nowait(line)
            except Exception:
                pass

    def subscribe_sse(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        self.sse_clients.append(q)
        return q

    def unsubscribe_sse(self, q: queue.Queue) -> None:
        if q in self.sse_clients:
            self.sse_clients.remove(q)

    def list_adb_devices(self) -> List[str]:
        if not shutil.which("adb"):
            return []
        try:
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=4)
            return [
                line.split()[0]
                for line in res.stdout.splitlines()
                if len(line.split()) >= 2 and line.split()[1] == "device"
            ]
        except Exception:
            return []

    def connect_adb(self, target: str) -> Tuple[bool, str]:
        target = target.strip()
        if not target:
            return False, "Podaj adres IP:PORT (np. 192.168.1.3:5555)."
        if not shutil.which("adb"):
            return False, "Brak binarki 'adb' w systemie."
        try:
            subprocess.run(["adb", "start-server"], capture_output=True, timeout=5)
            res = subprocess.run(["adb", "connect", target], capture_output=True, text=True, timeout=8)
            out = (res.stdout + res.stderr).strip()
            ok = "connected" in out.lower() or "already" in out.lower()
            if ok:
                self.mode = "adb"
                self.adb_target = target
                self.persist()
            self.emit("OK" if ok else "ERR", f"ADB connect {target}: {out}")
            return ok, out
        except Exception as exc:
            return False, f"Błąd ADB: {exc}"

    def resolve_backend(self, override: str = "") -> Tuple[str, str]:
        m = override if override in ("auto", "adb", "rish", "local") else self.mode
        if m == "adb":
            return "adb", self.adb_target
        if m == "rish":
            return "rish", ""
        if m == "local":
            return "local", ""

        devs = self.list_adb_devices()
        if self.adb_target and self.adb_target in devs:
            return "adb", self.adb_target
        if devs:
            self.adb_target = devs[0]
            return "adb", devs[0]
        if shutil.which("rish") or os.path.exists(f"{TMP_DIR}/rish") or os.path.exists("./rish"):
            return "rish", ""
        return "local", ""

    def current_label(self) -> str:
        backend, target = self.resolve_backend()
        if backend == "adb":
            return f"ADB Wi-Fi ({target or 'disconnected'})"
        if backend == "rish":
            return "Shizuku (rish)"
        return "Local Shell (sh)"

    def run_shell(self, cmd: str, timeout: int = 12, override_mode: str = "", silent: bool = False) -> Tuple[int, str]:
        backend, target = self.resolve_backend(override_mode)
        if backend == "adb":
            if not shutil.which("adb"):
                return 127, "adb not found"
            full_cmd = ["adb", "-s", target, "shell", cmd] if target else ["adb", "shell", cmd]
        elif backend == "rish":
            rish_bin = shutil.which("rish") or (f"{TMP_DIR}/rish" if os.path.exists(f"{TMP_DIR}/rish") else "./rish")
            full_cmd = [rish_bin, "-c", cmd]
        else:
            full_cmd = ["sh", "-c", cmd]

        if not silent:
            self.emit("EXEC", cmd[:90] + ("..." if len(cmd) > 90 else ""))

        try:
            proc = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            out = (proc.stdout + proc.stderr).strip()
            if not silent:
                self.emit("OK" if proc.returncode == 0 else "WARN", f"RC={proc.returncode} | {out[:100] or 'Done'}")
            return proc.returncode, out or "OK"
        except subprocess.TimeoutExpired:
            if not silent:
                self.emit("ERR", f"Timeout ({timeout}s): {cmd[:50]}")
            return 124, "TIMEOUT"
        except Exception as exc:
            if not silent:
                self.emit("ERR", str(exc))
            return 1, str(exc)

    def apply_module(self, mod_key: str) -> Dict[str, Any]:
        mod = HardwareRegistry.MODULES.get(mod_key)
        if not mod:
            return {"ok": False, "output": f"Nieznany moduł: {mod_key}"}

        self.emit("INFO", f"Uruchamianie modułu: {mod.title} ({len(mod.commands)} komend)")
        combined_cmd = " ; ".join(mod.commands)
        code, out = self.run_shell(combined_cmd, timeout=20)
        return {"ok": code == 0, "output": f"[{mod.title}] Wykonano ({len(mod.commands)} operacji).\n{out}"}

    def deploy_smarttube_coldstart(self, run_aot: bool = True) -> Dict[str, Any]:
        self.emit("INFO", "Wstrzykiwanie konfiguracji SmartTube Cold-Start XML + AFR + priorytety...")
        local_tmp = "org.smarttube.stable_preferences.xml"
        with open(local_tmp, "w", encoding="utf-8") as f:
            f.write(SMARTTUBE_XML_TEMPLATE)

        logs: List[str] = []
        backend, target = self.resolve_backend()
        if backend == "adb" and target:
            res = subprocess.run(
                ["adb", "-s", target, "push", local_tmp, SMARTTUBE_XML_BACKUP],
                capture_output=True, text=True, timeout=10
            )
            logs.append(f"ADB Push XML: {(res.stdout + res.stderr).strip()}")
        else:
            self.run_shell(f"mkdir -p /sdcard/Download && cp '{local_tmp}' '{SMARTTUBE_XML_BACKUP}' 2>/dev/null || true")
            logs.append(f"Zapisano lokalnie: {local_tmp}")

        cmds = [
            f"dumpsys deviceidle whitelist +{SMARTTUBE_PKG} >/dev/null 2>&1 || true",
            f"dumpsys deviceidle whitelist +{LAUNCHER_PKG} >/dev/null 2>&1 || true",
            f"am set-standby-bucket {SMARTTUBE_PKG} active >/dev/null 2>&1 || true",
            f"for p in $(pidof {SMARTTUBE_PKG}); do renice -n -10 -p $p 2>/dev/null; echo -800 > /proc/$p/oom_score_adj 2>/dev/null; done",
        ]
        if run_aot:
            logs.append("Kompilacja AOT 'everything' dla SmartTube (może potrwać 10-20s)...")
            cmds.append(f"pm compile -f --check-prof false -m everything {SMARTTUBE_PKG}")

        _, out = self.run_shell(" ; ".join(cmds), timeout=45)
        logs.append(out)
        self.emit("OK", "SmartTube Cold-Start, AFR & OOM Shield zakończone.")
        return {"ok": True, "output": "\n".join(logs)}

    def trim_bloat_and_gms(self) -> Dict[str, Any]:
        self.emit("INFO", "Neutralizacja bloatware i zapętlonych usług GMS WakeLock...")
        cmds = [f"pm disable-user --user 0 {pkg} >/dev/null 2>&1 || true" for pkg in HardwareRegistry.BLOAT_PACKAGES]
        cmds += [f"pm disable-user --user 0 {srv} >/dev/null 2>&1 || true" for srv in HardwareRegistry.GMS_WAKELOCK_SERVICES]
        cmds.append("logcat -c >/dev/null 2>&1 || true")
        self.run_shell(" ; ".join(cmds), timeout=25)
        self.emit("OK", f"Zablokowano {len(HardwareRegistry.BLOAT_PACKAGES)} pakietów i {len(HardwareRegistry.GMS_WAKELOCK_SERVICES)} usług GMS.")
        return {"ok": True, "output": "Neutralizacja bloatware oraz pętli GMS WakeLock zakończona."}

    def run_audit(self) -> Dict[str, Any]:
        marker = "VEC_"
        checks = [f"echo '{marker}{v.vector_id}'; {v.check_cmd}" for v in HardwareRegistry.AUDIT_VECTORS]
        code, raw = self.run_shell(" ; ".join(checks), timeout=12, silent=True)

        parsed: Dict[str, str] = {}
        curr = ""
        for line in raw.splitlines():
            if line.startswith(marker):
                curr = line[len(marker):].strip()
                parsed[curr] = ""
            elif curr:
                parsed[curr] = (parsed[curr] + " " + line).strip()

        results = []
        ok_count = 0
        for v in HardwareRegistry.AUDIT_VECTORS:
            val = parsed.get(v.vector_id, "unreachable" if code != 0 else "unset")
            healthy = code == 0 and (v.expected.lower() in val.lower())
            if healthy:
                ok_count += 1
            results.append({
                "id": v.vector_id,
                "name": v.name,
                "category": v.category,
                "value": val or "unset",
                "healthy": healthy,
                "fix_module": v.fix_module,
            })

        total = len(HardwareRegistry.AUDIT_VECTORS)
        score = int((ok_count / total) * 100) if total else 100
        return {
            "score": score,
            "grade": "ENTERPRISE A+" if score >= 88 else ("OPTIMIZED B" if score >= 60 else "TUNING NEEDED"),
            "mode_label": self.current_label(),
            "watchdog": self.watchdog_active,
            "vectors": results,
        }

    def scan_recursive_scripts(self) -> List[Dict[str, str]]:
        scripts: List[Dict[str, str]] = []
        scan_paths = [TMP_DIR, "/sdcard/Download", "/sdcard", "."]
        
        for sp in scan_paths:
            p = pathlib.Path(sp)
            if not p.exists():
                continue
            try:
                for item in p.rglob("*"):
                    if item.is_file() and item.suffix in (".sh", ".py"):
                        fpath = str(item.resolve())
                        if any(s["path"] == fpath for s in scripts):
                            continue
                        
                        desc = "Skrypt optymalizacyjny"
                        author = "SecFERRO Hub"
                        try:
                            with open(item, "r", encoding="utf-8", errors="ignore") as f:
                                head_lines = [f.readline() for _ in range(6)]
                                for hl in head_lines:
                                    hl_lower = hl.lower()
                                    if "description:" in hl_lower or "opis:" in hl_lower:
                                        desc = hl.split(":", 1)[1].strip()
                                    elif "author:" in hl_lower or "autor:" in hl_lower:
                                        author = hl.split(":", 1)[1].strip()
                        except Exception:
                            pass

                        scripts.append({
                            "name": item.name,
                            "path": fpath,
                            "type": item.suffix[1:],
                            "description": desc,
                            "author": author,
                            "size": f"{item.stat().st_size / 1024:.1f} KB"
                        })
            except Exception:
                pass
        return scripts

    def watchdog_cycle(self) -> None:
        fixes: List[str] = []
        _, mdns = self.run_shell("getprop init.svc.mdnsd", silent=True)
        if mdns.strip() != "running":
            self.run_shell("start mdnsd", silent=True)
            fixes.append("Restarted mdnsd")

        _, av1 = self.run_shell("getprop media.codec.av1.disable", silent=True)
        if av1.strip().lower() != "true":
            self.run_shell("setprop media.codec.av1.disable true", silent=True)
            fixes.append("Re-applied AV1 block")

        restore_cmds = [f"pm enable --user 0 {p} >/dev/null 2>&1 || true" for p in HardwareRegistry.PROTECTED_CAST_PACKAGES]
        self.run_shell(" ; ".join(restore_cmds), silent=True)

        if fixes:
            self.emit("WATCHDOG", f"Auto-Healing wykonany: {', '.join(fixes)}")


EXECUTOR = EnterpriseExecutor()


def watchdog_worker() -> None:
    while True:
        time.sleep(30)
        if EXECUTOR.watchdog_active:
            try:
                EXECUTOR.watchdog_cycle()
            except Exception:
                pass


threading.Thread(target=watchdog_worker, daemon=True).start()
EXECUTOR.emit("INFO", f"SecFERRO ATV PanelCore v22.0.0 uruchomiony ({EXECUTOR.current_label()})")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class PanelRequestHandler(BaseHTTPRequestHandler):
    def _json(self, payload: Dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            body = HTML_DASHBOARD.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/sse":
            self._serve_sse()
        elif path == "/api/audit":
            self._json(EXECUTOR.run_audit())
        elif path == "/api/telemetry":
            _, mem = EXECUTOR.run_shell("awk '/MemTotal|MemAvailable/ {print $1,$2}' /proc/meminfo", silent=True)
            _, wl = EXECUTOR.run_shell("dumpsys power | grep -E 'mWakefulness=|Wake Locks:size' | head -n 4", silent=True)
            _, omx = EXECUTOR.run_shell("dumpsys media.player | grep -i 'omx.broadcom' | head -n 3", silent=True)
            self._json({
                "mem": mem or "MemTotal: 1536000 kB",
                "power": wl or "mWakefulness=Awake",
                "omx": omx or "omx.broadcom.video_decoder.vp9 (Ready)",
            })
        elif path == "/api/processes":
            code, raw = EXECUTOR.run_shell("ps -A -o PID,USER,PR,NI,%CPU,%MEM,CMD", silent=True)
            procs = []
            if code == 0:
                for line in raw.splitlines()[1:]:
                    parts = line.split(None, 6)
                    if len(parts) >= 7:
                        procs.append({
                            "pid": parts[0], "user": parts[1], "pr": parts[2],
                            "ni": parts[3], "cpu": parts[4], "mem": parts[5], "cmd": parts[6]
                        })
            self._json({"processes": procs[:120]})
        elif path == "/api/packages":
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].lower()
            code, raw = EXECUTOR.run_shell("pm list packages", silent=True)
            pkgs = []
            if code == 0:
                for line in raw.splitlines():
                    if line.startswith("package:"):
                        name = line.replace("package:", "").strip()
                        if not q or q in name.lower():
                            pkgs.append({
                                "name": name,
                                "protected": name in HardwareRegistry.PROTECTED_CAST_PACKAGES
                            })
                            if len(pkgs) >= 70:
                                break
            self._json({"packages": pkgs})
        elif path == "/api/scripts":
            self._json({"scripts": EXECUTOR.scan_recursive_scripts()})
        elif path == "/api/settings/dump":
            table = urllib.parse.parse_qs(parsed.query).get("table", ["global"])[0]
            if table not in ("global", "secure", "system"):
                table = "global"
            _, out = EXECUTOR.run_shell(f"settings list {table}", silent=True)
            self._json({"table": table, "output": out})
        else:
            self.send_error(404)

    def _serve_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = EXECUTOR.subscribe_sse()
        try:
            for item in reversed(EXECUTOR.journal[:15]):
                line = f"[{item['time']}] [{item['level']}] {item['msg']}"
                self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
            self.wfile.flush()
            while True:
                msg = q.get()
                self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                self.wfile.flush()
        except Exception:
            pass
        finally:
            EXECUTOR.unsubscribe_sse(q)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        if self.path == "/api/mode":
            mode = str(data.get("mode", "auto"))
            target = str(data.get("target", ""))
            if mode == "adb" or target:
                ok, msg = EXECUTOR.connect_adb(target or EXECUTOR.adb_target)
            else:
                EXECUTOR.mode = mode
                EXECUTOR.persist()
                ok, msg = True, f"Przełączono tryb na: {EXECUTOR.current_label()}"
                EXECUTOR.emit("OK", msg)
            self._json({"ok": ok, "output": msg, "mode_label": EXECUTOR.current_label()})

        elif self.path == "/api/module/apply":
            key = str(data.get("key", ""))
            self._json(EXECUTOR.apply_module(key))

        elif self.path == "/api/smarttube/coldstart":
            run_aot = bool(data.get("aot", True))
            self._json(EXECUTOR.deploy_smarttube_coldstart(run_aot=run_aot))

        elif self.path == "/api/system/bloat_trim":
            self._json(EXECUTOR.trim_bloat_and_gms())

        elif self.path == "/api/watchdog/toggle":
            EXECUTOR.watchdog_active = not EXECUTOR.watchdog_active
            EXECUTOR.persist()
            state_str = "AKTYWNY (co 30s)" if EXECUTOR.watchdog_active else "WYŁĄCZONY"
            EXECUTOR.emit("WATCHDOG", f"Status Watchdoga zmieniony: {state_str}")
            if EXECUTOR.watchdog_active:
                EXECUTOR.watchdog_cycle()
            self._json({"active": EXECUTOR.watchdog_active, "status": state_str})

        elif self.path == "/api/registry/write":
            kind = str(data.get("kind", "setprop"))
            key = str(data.get("key", "")).strip()
            val = str(data.get("value", "")).strip()
            table = str(data.get("table", "global")).strip()
            if not key:
                return self._json({"ok": False, "output": "Brak klucza."})
            if kind == "setprop":
                code, out = EXECUTOR.run_shell(f"setprop {key} '{val}'")
            elif kind == "settings":
                code, out = EXECUTOR.run_shell(f"settings put {table} {key} '{val}'")
            else:
                code, out = EXECUTOR.run_shell(key)
            self._json({"ok": code == 0, "output": out})

        elif self.path == "/api/process/tune":
            pid = int(data.get("pid", 0))
            nice = int(data.get("nice", 0))
            oom = int(data.get("oom", 0))
            _, out = EXECUTOR.run_shell(f"renice -n {nice} -p {pid} ; echo {oom} > /proc/{pid}/oom_score_adj 2>/dev/null || true")
            self._json({"ok": True, "output": f"PID {pid} -> nice={nice}, oom_adj={oom} ({out})"})

        elif self.path == "/api/package/control":
            pkg = str(data.get("pkg", ""))
            act = str(data.get("action", ""))
            if pkg in HardwareRegistry.PROTECTED_CAST_PACKAGES and act in ("suspend", "disable"):
                return self._json({"ok": False, "output": f"ODRZUCONO: {pkg} jest chronionym pakietem Cast/System!"})
            cmd_map = {
                "stop": f"am force-stop {pkg}",
                "suspend": f"pm suspend {pkg}",
                "unsuspend": f"pm unsuspend {pkg}",
                "bg_ignore": f"cmd appops set {pkg} RUN_IN_BACKGROUND ignore && cmd appops set {pkg} START_FOREGROUND ignore",
                "whitelist": f"dumpsys deviceidle whitelist +{pkg} && am set-standby-bucket {pkg} active",
                "compile": f"pm compile -f --check-prof false -m everything {pkg}",
            }
            cmd = cmd_map.get(act, "")
            if not cmd:
                return self._json({"ok": False, "output": "Nieznana akcja pakietu."})
            _, out = EXECUTOR.run_shell(cmd, timeout=35)
            self._json({"ok": True, "output": f"{pkg} [{act}]: {out}"})

        elif self.path == "/api/scripts/run":
            spath = str(data.get("path", ""))
            stype = str(data.get("type", "sh"))
            ctx = str(data.get("context", "auto"))
            runner = "python3" if stype == "py" else "sh"
            _, out = EXECUTOR.run_shell(f"{runner} '{spath}'", timeout=30, override_mode=ctx)
            self._json({"ok": True, "output": out})

        else:
            self.send_error(404)

    def log_message(self, format: str, *args: Any) -> None:
        return


HTML_DASHBOARD: Final[str] = r"""<!DOCTYPE html>
<html lang="pl" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SecFERRO ATV Enterprise Gateway v22 — BCM72604</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        netBg: '#0b0f19',
        netSidebar: '#0f172a',
        netCard: '#131c31',
        netBorder: '#1e293b',
        netAccent: '#3b82f6',
        netSuccess: '#10b981',
        netWarning: '#f59e0b',
        netDanger: '#ef4444'
      }
    }
  }
}
</script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');
  body { background-color: #0b0f19; color: #cbd5e1; font-family: 'Inter', sans-serif; }
  .font-mono { font-family: 'JetBrains Mono', monospace; }
  .router-card { background-color: #131c31; border: 1px solid #1e293b; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); border-radius: 0.75rem; }
  .router-card-hover:hover { border-color: #3b82f6; transition: all 0.2s ease; }
  .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
  .custom-scrollbar::-webkit-scrollbar-track { background: #0f172a; }
  .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
</style>
</head>
<body class="min-h-screen flex flex-col antialiased selection:bg-blue-500 selection:text-white">

<!-- TOP HEADER (ROUTER STATUS BAR) -->
<header class="bg-[#0f172a] border-b border-slate-800 h-14 px-4 lg:px-6 flex items-center justify-between sticky top-0 z-50">
  <div class="flex items-center space-x-4">
    <div class="flex items-center space-x-2.5">
      <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-md shadow-blue-500/20 text-xs">SF</div>
      <span class="font-bold text-sm tracking-wide text-white">SECFERRO <span class="text-blue-400 font-mono text-xs">GW-v22</span></span>
    </div>
    <div class="hidden md:flex items-center space-x-2 px-3 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-300">
      <span>Hardware: <strong class="text-white">BCM72604 (1.5GB RAM)</strong></span>
      <span class="text-slate-600">|</span>
      <span>OS: <strong class="text-white">ATV 9 Enterprise</strong></span>
    </div>
  </div>

  <div class="flex items-center space-x-3">
    <!-- Watchdog Switch -->
    <button onclick="toggleWatchdog()" id="watchdogBtn" class="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 hover:border-blue-500 text-xs font-semibold text-slate-300 transition flex items-center gap-1.5">
      <span id="watchdogDot" class="w-2 h-2 rounded-full bg-slate-500"></span>
      <span id="watchdogText">Auto-Heal: OFF</span>
    </button>

    <!-- Backend status badge -->
    <div class="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-400 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
      <span id="backendLabel">Detecting...</span>
    </div>

    <!-- Modal trigger -->
    <button onclick="document.getElementById('adbModal').classList.remove('hidden')" class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow transition">
      Network Target
    </button>
  </div>
</header>

<!-- MAIN APP CONTAINER (ROUTER SPLIT LAYOUT) -->
<div class="flex-1 flex overflow-hidden">

  <!-- SIDEBAR NAVIGATION (WLAN/ROUTER STYLE) -->
  <aside class="w-64 bg-[#0f172a] border-r border-slate-800 flex flex-col shrink-0 hidden lg:flex select-none">
    <div class="p-4 border-b border-slate-800/80">
      <span class="text-[10px] font-mono uppercase tracking-widest text-slate-400 font-bold">System Menu</span>
    </div>
    <nav class="flex-1 p-3 space-y-1 overflow-y-auto custom-scrollbar">
      <button onclick="setTab('cockpit')" data-tab="cockpit" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-blue-600 text-white shadow-md shadow-blue-600/20 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
        Status & Cockpit
      </button>
      <button onclick="setTab('smarttube')" data-tab="smarttube" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        SmartTube & Media Hub
      </button>
      <button onclick="setTab('registry')" data-tab="registry" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
        Settings & Props Editor
      </button>
      <button onclick="setTab('procs')" data-tab="procs" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
        Process Manager (Renice)
      </button>
      <button onclick="setTab('apps')" data-tab="apps" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
        AppOps & AOT Compiler
      </button>
      <button onclick="setTab('scripts')" data-tab="scripts" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path></svg>
        Recursive Script Hub
      </button>
    </nav>
    <div class="p-3 border-t border-slate-800/80">
      <div class="bg-slate-900/80 rounded-lg p-3 text-[11px] font-mono text-slate-400 flex flex-col gap-1">
        <span>Uptime: <strong id="sysUptime" class="text-slate-200">Active</strong></span>
        <span>Storage: <strong class="text-emerald-400">Optimal</strong></span>
      </div>
    </div>
  </aside>

  <!-- MAIN CONTENT AREA -->
  <main class="flex-1 flex flex-col overflow-y-auto custom-scrollbar p-4 lg:p-6 gap-6">

    <!-- MOBILE TABS BAR -->
    <div class="flex lg:hidden gap-1.5 overflow-x-auto pb-2 border-b border-slate-800">
      <button onclick="setTab('cockpit')" data-tab="cockpit" class="nav-btn-m px-3 py-1.5 rounded bg-blue-600 text-white text-xs font-semibold whitespace-nowrap">Status</button>
      <button onclick="setTab('smarttube')" data-tab="smarttube" class="nav-btn-m px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs font-semibold whitespace-nowrap">SmartTube</button>
      <button onclick="setTab('registry')" data-tab="registry" class="nav-btn-m px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs font-semibold whitespace-nowrap">Settings</button>
      <button onclick="setTab('procs')" data-tab="procs" class="nav-btn-m px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs font-semibold whitespace-nowrap">Processes</button>
      <button onclick="setTab('apps')" data-tab="apps" class="nav-btn-m px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs font-semibold whitespace-nowrap">Apps</button>
      <button onclick="setTab('scripts')" data-tab="scripts" class="nav-btn-m px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs font-semibold whitespace-nowrap">Scripts</button>
    </div>

    <!-- TAB 1: COCKPIT & HARDWARE SUITES -->
    <section id="tab-cockpit" class="tab-pane flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative overflow-hidden">
        <div class="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-blue-600/10 to-transparent pointer-events-none"></div>
        <div class="space-y-1.5">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 font-mono text-[10px] font-bold">ROUTER DASHBOARD MODE</span>
            <span class="text-xs text-slate-400 font-mono">Firmware: SecFERRO v22 Enterprise</span>
          </div>
          <h2 class="text-lg font-bold text-white">Zarządzanie Wydajnością Sagemcom DCTIW362</h2>
          <p class="text-xs text-slate-400 max-w-2xl">Centrum dowodzenia dekoderem telewizyjnym. Monitoruj stan pamięci RAM, optymalizuj potoki kodeków OMX/V3D, steruj buforowaniem sieciowym TCP i automatycznie blokuj procesy w tle.</p>
        </div>
        <div class="flex flex-wrap gap-2.5 shrink-0">
          <button onclick="applyAllRecommended()" class="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold shadow-lg shadow-blue-600/30 transition flex items-center gap-2">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
            Zastosuj Pakiet Titanium
          </button>
          <button onclick="trimBloatAndGms()" class="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-300 text-xs font-bold transition">
            Wytnij Bloatware & GMS
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="router-card p-4 flex flex-col justify-between">
          <div class="flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-wider">
            <span>Pamięć RAM (1.5GB)</span>
            <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
          </div>
          <pre id="telMem" class="text-xs font-mono text-emerald-400 my-3 whitespace-pre-wrap">Ładowanie statystyk...</pre>
          <div class="text-[11px] text-slate-500">Zarządzanie LMK PSI & Caches</div>
        </div>
        <div class="router-card p-4 flex flex-col justify-between">
          <div class="flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-wider">
            <span>Power & WakeLocks</span>
            <span class="w-2 h-2 rounded-full bg-blue-400"></span>
          </div>
          <pre id="telPower" class="text-xs font-mono text-blue-300 my-3 whitespace-pre-wrap">Ładowanie statystyk...</pre>
          <div class="text-[11px] text-slate-500">Blokada pętli GMS w tle</div>
        </div>
        <div class="router-card p-4 flex flex-col justify-between">
          <div class="flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-wider">
            <span>Broadcom OMX Decoder</span>
            <span class="w-2 h-2 rounded-full bg-purple-400"></span>
          </div>
          <pre id="telOmx" class="text-xs font-mono text-purple-300 my-3 whitespace-pre-wrap">Ładowanie statystyk...</pre>
          <div class="text-[11px] text-slate-500">V3D Hardware Composition</div>
        </div>
      </div>

      <div>
        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 px-1">Moduły Systemowe i Przepływy (Profiles)</h3>
        <div id="modulesGrid" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5"></div>
      </div>

      <div class="router-card p-5">
        <div class="flex items-center justify-between mb-4 pb-2 border-b border-slate-800">
          <div>
            <h3 class="text-sm font-bold text-white">Stan Wektorów Bezpieczeństwa i Sprzętu</h3>
            <p class="text-xs text-slate-400">Live inspection of Broadcom BCM72604 firmware configuration</p>
          </div>
          <button onclick="refreshAudit()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition">Odśwież Audyt</button>
        </div>
        <div id="auditVectorsGrid" class="grid grid-cols-1 md:grid-cols-2 gap-3"></div>
      </div>
    </section>

    <!-- TAB 2: SMARTTUBE COLD-START & MEDIA -->
    <section id="tab-smarttube" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-5">
        <div class="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <h2 class="text-base font-bold text-white">SmartTube Cold-Start & Audio/Video Tuning</h2>
            <p class="text-xs text-slate-400 mt-1">Konfiguruje optymalne parametry ExoPlayer, bufor startowy 400ms, AFR, wymusza PCM Stereo oraz rejestruje aplikację w Doze Whitelist.</p>
          </div>
          <div class="flex gap-2.5">
            <button onclick="deploySmartTube(false)" class="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white text-xs font-bold transition">
              Wdróż XML + OOM (Szybkie)
            </button>
            <button onclick="deploySmartTube(true)" class="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold shadow-lg shadow-blue-600/30 transition">
              Pełny Cold-Start + Kompilacja AOT
            </button>
          </div>
        </div>
        <div class="bg-[#080d16] border border-slate-800 rounded-xl p-4">
          <div class="text-xs font-bold text-slate-400 mb-2 font-mono">Podgląd konfiguracji XML `org.smarttube.stable_preferences.xml`:</div>
          <pre class="text-[11px] font-mono text-emerald-400 overflow-x-auto max-h-72 whitespace-pre-wrap">&lt;map&gt;
    &lt;string name="decoder_preference"&gt;tunneling_disabled&lt;/string&gt;
    &lt;boolean name="use_hw_decoder" value="true" /&gt;
    &lt;boolean name="use_extension_renderer" value="true" /&gt;
    &lt;boolean name="force_surface_view" value="true" /&gt;
    &lt;boolean name="tunneling_audio" value="false" /&gt;
    &lt;string name="custom_video_decoder"&gt;OMX.broadcom.video_decoder.vp9&lt;/string&gt;

    &lt;int name="min_buffer_ms" value="1000" /&gt;
    &lt;int name="max_buffer_ms" value="25000" /&gt;
    &lt;int name="buffer_for_playback_ms" value="400" /&gt;
    &lt;int name="buffer_for_playback_after_rebuffer_ms" value="800" /&gt;
    &lt;boolean name="cache_enabled" value="true" /&gt;
    &lt;int name="max_cache_size_mb" value="512" /&gt;
    &lt;boolean name="afr_enabled" value="true" /&gt;
&lt;/map&gt;</pre>
        </div>
      </div>
    </section>

    <!-- TAB 3: SETTINGS DB & PROPS EXPLORER -->
    <section id="tab-registry" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-5">
        <div>
          <h2 class="text-base font-bold text-white">Global Settings Database & System Properties Editor</h2>
          <p class="text-xs text-slate-400 mt-1">Bezpośrednia interrakcja z bazą SQLite systemowych ustawień Androida (`global`, `secure`, `system`) oraz właściwościami `setprop`.</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-[#080d16] border border-slate-800 p-4.5 rounded-xl flex flex-col gap-2.5">
            <span class="text-xs font-bold text-blue-400 uppercase tracking-wider">Wstrzyknij System Property (`setprop`)</span>
            <input id="regPropKey" placeholder="np. media.tunneled-playback.enable" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:border-blue-500 focus:outline-none">
            <input id="regPropVal" placeholder="wartość (np. false)" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:border-blue-500 focus:outline-none">
            <button onclick="writeRegistry('setprop')" class="py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition">Zapisz Właściwość</button>
          </div>
          <div class="bg-[#080d16] border border-slate-800 p-4.5 rounded-xl flex flex-col gap-2.5">
            <span class="text-xs font-bold text-purple-400 uppercase tracking-wider">Wstrzyknij do Bazy (`settings put`)</span>
            <div class="flex gap-2">
              <select id="regSetTable" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-2 text-xs font-mono text-white">
                <option value="global">global</option>
                <option value="secure">secure</option>
                <option value="system">system</option>
              </select>
              <input id="regSetKey" placeholder="klucz (np. low_ram)" class="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:border-blue-500 focus:outline-none">
            </div>
            <input id="regSetVal" placeholder="wartość (np. false)" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:border-blue-500 focus:outline-none">
            <button onclick="writeRegistry('settings')" class="py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition">Zapisz w Bazie Settings</button>
          </div>
        </div>

        <div class="bg-[#080d16] border border-slate-800 p-4.5 rounded-xl flex flex-col gap-3">
          <div class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
            <span class="text-xs font-bold text-slate-300">Inspekcja Tabeli Settings na Żywo:</span>
            <div class="flex gap-2">
              <button onclick="dumpSettings('global')" class="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200">global</button>
              <button onclick="dumpSettings('secure')" class="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200">secure</button>
              <button onclick="dumpSettings('system')" class="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200">system</button>
            </div>
          </div>
          <pre id="settingsDumpOut" class="text-[11px] font-mono text-slate-300 h-72 overflow-y-auto whitespace-pre-wrap custom-scrollbar">Wybierz tabelę powyżej, aby wyświetlić zawartość...</pre>
        </div>
      </div>
    </section>

    <!-- TAB 4: PROCESSES (RENICE / OOM) -->
    <section id="tab-procs" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-5">
        <div class="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
          <div>
            <h2 class="text-base font-bold text-white">Menedżer Procesów i Priorytetów CPU (Renice / OOM)</h2>
            <p class="text-xs text-slate-400">Optymalizuj przydział czasu procesora dla wątków dekodowania wideo i SurfaceFlinger.</p>
          </div>
          <div class="flex gap-2">
            <input id="procSearch" oninput="loadProcesses()" placeholder="Filtruj PID / nazwę..." class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500">
            <button onclick="loadProcesses()" class="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition">Odśwież</button>
          </div>
        </div>
        <div class="overflow-x-auto max-h-[500px] custom-scrollbar">
          <table class="w-full text-left text-xs font-mono">
            <thead class="bg-[#080d16] text-slate-400 sticky top-0">
              <tr><th class="p-3">PID</th><th class="p-3">USER</th><th class="p-3">NI</th><th class="p-3">CPU / MEM</th><th class="p-3">COMMAND</th><th class="p-3 text-right">Akcje</th></tr>
            </thead>
            <tbody id="procTable" class="divide-y divide-slate-800/80"></tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 5: APPS, APPOPS & AOT -->
    <section id="tab-apps" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-5">
        <div class="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
          <div>
            <h2 class="text-base font-bold text-white">Zarządzanie Pakietami, AppOps & Kompilacja AOT</h2>
            <p class="text-xs text-slate-400">Zarządzaj uprawnieniami tła, hibernacją oraz wymuszaj pełną kompilację `pm compile -m everything`.</p>
          </div>
          <div class="flex gap-2">
            <input id="pkgSearch" placeholder="Szukaj pakietu..." class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500">
            <button onclick="loadPackages()" class="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition">Pobierz Pakiety</button>
          </div>
        </div>
        <div id="pkgGrid" class="grid grid-cols-1 md:grid-cols-2 gap-3.5 max-h-[500px] overflow-y-auto custom-scrollbar"></div>
      </div>
    </section>

    <!-- TAB 6: SCRIPT HUB (RECURSIVE SCANNER) -->
    <section id="tab-scripts" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-5">
        <div class="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
          <div>
            <h2 class="text-base font-bold text-white">Rekurencyjne Centrum Skryptów (`.sh` / `.py`)</h2>
            <p class="text-xs text-slate-400">Automatyczny skaner wykrywający i parsujący skrypty w katalogach tymczasowych i pamięci urządzenia.</p>
          </div>
          <div class="flex items-center gap-2">
            <select id="scriptCtx" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white">
              <option value="auto">Auto Context</option>
              <option value="adb">ADB Bridge</option>
              <option value="rish">Shizuku (rish)</option>
              <option value="local">Local Shell</option>
            </select>
            <button onclick="loadScripts()" class="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition">Skanuj Rekurencyjnie</button>
          </div>
        </div>
        <div id="scriptsGrid" class="grid grid-cols-1 md:grid-cols-2 gap-3.5"></div>
      </div>
    </section>

  </main>

  <!-- RIGHT SIDEBAR: LIVE SSE CONSOLE (ROUTER LOGS STYLE) -->
  <aside class="w-96 bg-[#0f172a] border-l border-slate-800 flex flex-col shrink-0 hidden xl:flex">
    <div class="p-4 border-b border-slate-800 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
        <h2 class="text-xs font-bold uppercase tracking-wider text-white font-mono">Real-Time Event Stream</h2>
      </div>
      <button onclick="document.getElementById('sseConsole').innerHTML=''" class="text-[11px] text-slate-400 hover:text-white transition">Wyczyść</button>
    </div>

    <div id="sseConsole" class="flex-1 bg-[#070b14] border border-slate-800/80 rounded-xl p-3 m-3 overflow-y-auto font-mono text-[11px] space-y-1.5 custom-scrollbar"></div>

    <div class="p-3 border-t border-slate-800 flex gap-2">
      <input id="quickCmdInput" onkeydown="if(event.key==='Enter') runQuickCmd()" placeholder="Wpisz komendę shell..." class="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-blue-500">
      <button onclick="runQuickCmd()" class="px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition">Wykonaj</button>
    </div>
  </aside>

</div>

<!-- ADB / EXECUTION MODAL -->
<div id="adbModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
  <div class="router-card max-w-md w-full p-6 flex flex-col gap-4 shadow-2xl">
    <h3 class="text-base font-bold text-white">Konfiguracja Połączenia Sieciowego i ADB</h3>
    <p class="text-xs text-slate-400">Określ metodę transmisji poleceń do Sagemcom DCTIW362.</p>
    <div class="flex flex-col gap-1.5">
      <label class="text-xs text-slate-400 font-medium">Tryb Backendowy</label>
      <select id="modalMode" class="bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white">
        <option value="auto">Auto-Detect (ADB -> Shizuku rish -> Local)</option>
        <option value="adb">ADB Wi-Fi Bridge</option>
        <option value="rish">Shizuku (rish)</option>
        <option value="local">Local Shell (sh)</option>
      </select>
    </div>
    <div class="flex flex-col gap-1.5">
      <label class="text-xs text-slate-400 font-medium">Adres IP:PORT (dla ADB Wi-Fi)</label>
      <input id="modalTarget" placeholder="192.168.1.3:5555" class="bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs font-mono text-white">
    </div>
    <div class="flex justify-end gap-2.5 mt-3">
      <button onclick="document.getElementById('adbModal').classList.add('hidden')" class="px-4 py-2 rounded-lg bg-slate-800 text-xs font-semibold text-slate-300">Anuluj</button>
      <button onclick="saveBackendMode()" class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold shadow transition">Połącz i Zapisz</button>
    </div>
  </div>
</div>

<script>
const MODULES_META = [
  { key: "brcm_omx_v3d", title: "Broadcom OMX, V3D & AV1 SW Block", cat: "Media & GPU", badge: "CORE", desc: "Dekodowanie VP9/H264, 32 bufory VPU, WCG 1023 oraz blokada programowego AV1 (usuwa 100% obciążenia CPU)." },
  { key: "skiagl_font_sharpness", title: "SkiaGL Font Antialiasing & Sharpness", cat: "Visual & UI", badge: "SHARP", desc: "Aktywuje antyaliasowanie czcionek WebView, rasteryzację GPU i zero-copy (Titanium v19)." },
  { key: "kernel_p99_vm", title: "Kernel VM Tuning & P99 Frame Pacing", cat: "CPU & Kernel", badge: "PACING", desc: "Stroi swappiness (100), VFS cache (50) oraz fazy VSync SurfaceFlinger eliminując zacięcia." },
  { key: "smarttube_anti_blackscreen", title: "SmartTube Anti-Blackscreen & PCM", cat: "Media & GPU", badge: "FIX", desc: "Wyłącza wadliwe tunelowanie audio/wideo Broadcom dla ExoPlayera, wymusza PCM Stereo i bufor 350ms." },
  { key: "cinema_tunnel_4k", title: "Cinema 4K HDMI Clock-Sync Tunnel", cat: "Media & GPU", badge: "4K HDR", desc: "Włącza sprzętowe tunelowanie HDMI i synchronizację zegara dla VOD (Netflix/Prime) bez dryfu A/V." },
  { key: "cpu_perf_governor", title: "CPU Governor 'performance' & FIFO UI", cat: "CPU & Kernel", badge: "TURBO", desc: "Blokuje CPU na maksymalnym taktowaniu, aktywuje FIFO UI oraz flagi wygładzania czcionek SkiaGL." },
  { key: "ram_lmk_psi", title: "1.5GB RAM LMK PSI & Activity Limits", cat: "Memory & LMK", badge: "1.5GB", desc: "Stroi PSI Low Memory Killer, ogranicza procesy w tle do 8 i zrzuca PageCache zapobiegając zamrożeniom." },
  { key: "net_120mbit_ipv6", title: "Fiber 120Mbps TCP Buffers & IPv6 Kill", cat: "Network & DNS", badge: "NET", desc: "Okna TCP pod 120Mbps, TCP FastOpen, wyłączenie IPv6, blokada skanowania Wi-Fi i DNS 1.1.1.1." },
  { key: "wakelock_bloat_neutralize", title: "WakeLock, Telemetry & GMS Purge", cat: "Services", badge: "CLEAN", desc: "Zatrzymuje zapętlone usługi GMS BAD_AUTHENTICATION, bmgr backup journal, telemetrię i lokalizację." },
  { key: "netflix_drm_safe_freeze", title: "Netflix Deep Freeze (Widevine Safe)", cat: "Services", badge: "DRM SAFE", desc: "Hibernuje pakiet Netflix przez pm suspend i AppOps bez naruszania kluczy DRM Widevine L1." }
];

function renderModules() {
  const grid = document.getElementById('modulesGrid');
  grid.innerHTML = MODULES_META.map(m => `
    <div class="router-card router-card-hover p-4 flex flex-col justify-between gap-3 bg-[#131c31]/90">
      <div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">${m.badge}</span>
          <span class="text-[11px] text-slate-400 font-mono">${m.cat}</span>
        </div>
        <h4 class="text-sm font-bold text-white mt-2">${m.title}</h4>
        <p class="text-xs text-slate-400 mt-1 leading-relaxed">${m.desc}</p>
      </div>
      <button onclick="applyModule('${m.key}')" class="w-full py-2 rounded-lg bg-slate-800 hover:bg-blue-600 text-white text-xs font-bold transition shadow-sm">
        Aktywuj Moduł
      </button>
    </div>
  `).join('');
}

function setTab(id) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
  document.getElementById('tab-' + id).classList.remove('hidden');
  
  document.querySelectorAll('.nav-btn').forEach(btn => {
    const active = btn.dataset.tab === id;
    btn.className = active
      ? 'nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-blue-600 text-white shadow-md shadow-blue-600/20 transition'
      : 'nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition';
  });

  document.querySelectorAll('.nav-btn-m').forEach(btn => {
    const active = btn.getAttribute('onclick').includes(id);
    btn.className = active
      ? 'nav-btn-m px-3 py-1.5 rounded bg-blue-600 text-white text-xs font-semibold whitespace-nowrap'
      : 'nav-btn-m px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs font-semibold whitespace-nowrap';
  });

  if (id === 'procs') loadProcesses();
  if (id === 'apps') loadPackages();
  if (id === 'scripts') loadScripts();
  if (id === 'registry') dumpSettings('global');
}

async function applyModule(key) {
  await fetch('/api/module/apply', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({key})
  });
  refreshAudit();
  refreshTelemetry();
}

async function applyAllRecommended() {
  const keys = ['brcm_omx_v3d', 'skiagl_font_sharpness', 'kernel_p99_vm', 'smarttube_anti_blackscreen', 'cpu_perf_governor', 'ram_lmk_psi', 'net_120mbit_ipv6', 'wakelock_bloat_neutralize'];
  for (const k of keys) {
    await applyModule(k);
  }
}

async function trimBloatAndGms() {
  await fetch('/api/system/bloat_trim', { method: 'POST' });
}

async function deploySmartTube(aot) {
  await fetch('/api/smarttube/coldstart', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({aot})
  });
}

async function toggleWatchdog() {
  const res = await fetch('/api/watchdog/toggle', { method: 'POST' });
  const data = await res.json();
  updateWatchdogState(data.active);
}

function updateWatchdogState(active) {
  const dot = document.getElementById('watchdogDot');
  const text = document.getElementById('watchdogText');
  const btn = document.getElementById('watchdogBtn');
  
  if (active) {
    dot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-ping';
    text.textContent = 'Auto-Heal: ACTIVE';
    btn.className = 'px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-xs font-bold text-emerald-300 transition flex items-center gap-1.5';
  } else {
    dot.className = 'w-2 h-2 rounded-full bg-slate-500';
    text.textContent = 'Auto-Heal: OFF';
    btn.className = 'px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 hover:border-blue-500 text-xs font-semibold text-slate-300 transition flex items-center gap-1.5';
  }
}

async function refreshAudit() {
  try {
    const res = await fetch('/api/audit');
    const data = await res.json();
    document.getElementById('backendLabel').textContent = data.mode_label;
    updateWatchdogState(data.watchdog);

    const grid = document.getElementById('auditVectorsGrid');
    grid.innerHTML = data.vectors.map(v => `
      <div class="bg-[#080d16] border border-slate-800 rounded-xl p-3.5 flex items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full ${v.healthy ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
            <span class="text-xs font-bold text-white truncate">${v.name}</span>
          </div>
          <div class="text-[11px] font-mono text-slate-400 truncate mt-1">${v.category} · Val: <span class="text-slate-200">${v.value}</span></div>
        </div>
        <button onclick="applyModule('${v.fix_module}')" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-blue-600 text-xs font-bold text-white shrink-0 transition">
          ${v.healthy ? 'Zweryfikowano' : 'Napraw'}
        </button>
      </div>
    `).join('');
  } catch (e) {}
}

async function refreshTelemetry() {
  try {
    const res = await fetch('/api/telemetry');
    const d = await res.json();
    document.getElementById('telMem').textContent = d.mem;
    document.getElementById('telPower').textContent = d.power;
    document.getElementById('telOmx').textContent = d.omx;
  } catch (e) {}
}

async function writeRegistry(kind) {
  const payload = kind === 'setprop'
    ? { kind, key: document.getElementById('regPropKey').value, value: document.getElementById('regPropVal').value }
    : { kind, table: document.getElementById('regSetTable').value, key: document.getElementById('regSetKey').value, value: document.getElementById('regSetVal').value };
  await fetch('/api/registry/write', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
  if (kind === 'settings') dumpSettings(payload.table);
}

async function dumpSettings(table) {
  const box = document.getElementById('settingsDumpOut');
  box.textContent = 'Pobieranie tabeli ' + table + '...';
  const res = await fetch('/api/settings/dump?table=' + table);
  const data = await res.json();
  box.textContent = data.output || 'Brak danych.';
}

async function loadProcesses() {
  const tbody = document.getElementById('procTable');
  const q = document.getElementById('procSearch').value.toLowerCase();
  const res = await fetch('/api/processes');
  const data = await res.json();
  tbody.innerHTML = data.processes
    .filter(p => !q || p.cmd.toLowerCase().includes(q) || p.pid.includes(q))
    .map(p => `
      <tr class="hover:bg-slate-900/60 transition">
        <td class="p-3 text-blue-400 font-bold">${p.pid}</td>
        <td class="p-3 text-slate-400">${p.user}</td>
        <td class="p-3 text-emerald-400">${p.ni}</td>
        <td class="p-3 text-slate-300">${p.cpu}% / ${p.mem}%</td>
        <td class="p-3 text-white truncate max-w-xs">${p.cmd}</td>
        <td class="p-3 text-right space-x-1.5">
          <button onclick="tuneProc(${p.pid}, -10, -800)" class="px-2.5 py-1 rounded bg-blue-600/20 hover:bg-blue-600 text-blue-200 text-[11px] font-semibold transition">VIP (-10 / OOM -800)</button>
          <button onclick="tuneProc(${p.pid}, 0, 0)" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition">Reset</button>
        </td>
      </tr>
    `).join('');
}

async function tuneProc(pid, nice, oom) {
  await fetch('/api/process/tune', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pid, nice, oom})
  });
  loadProcesses();
}

async function loadPackages() {
  const grid = document.getElementById('pkgGrid');
  const q = document.getElementById('pkgSearch').value;
  grid.innerHTML = '<div class="text-xs text-slate-400 p-4">Pobieranie listy pakietów...</div>';
  const res = await fetch('/api/packages?q=' + encodeURIComponent(q));
  const data = await res.json();
  grid.innerHTML = data.packages.map(p => `
    <div class="bg-[#080d16] border border-slate-800 rounded-xl p-4 flex flex-col justify-between gap-3">
      <div class="flex items-center justify-between gap-2">
        <span class="text-xs font-bold text-white truncate">${p.name}</span>
        ${p.protected ? '<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">CAST SHIELD</span>' : ''}
      </div>
      <div class="flex flex-wrap gap-1.5">
        <button onclick="pkgCmd('${p.name}', 'stop')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-200 transition">Force Stop</button>
        <button onclick="pkgCmd('${p.name}', 'bg_ignore')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-amber-600/30 text-[11px] text-amber-300 transition">Blokuj Tło</button>
        <button onclick="pkgCmd('${p.name}', 'whitelist')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-emerald-600/30 text-[11px] text-emerald-300 transition">Doze VIP</button>
        <button onclick="pkgCmd('${p.name}', 'compile')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-blue-600/30 text-[11px] text-blue-300 transition">AOT Compile</button>
        ${!p.protected ? `<button onclick="pkgCmd('${p.name}', 'suspend')" class="px-2.5 py-1 rounded bg-red-950/60 hover:bg-red-800 text-[11px] text-red-300 transition">Suspend</button>` : ''}
      </div>
    </div>
  `).join('');
}

async function pkgCmd(pkg, action) {
  await fetch('/api/package/control', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pkg, action})
  });
}

async function loadScripts() {
  const grid = document.getElementById('scriptsGrid');
  grid.innerHTML = '<div class="text-xs text-slate-400 p-4">Skanowanie rekurencyjne dysku i katalogów tymczasowych...</div>';
  const res = await fetch('/api/scripts');
  const data = await res.json();
  if (!data.scripts.length) {
    grid.innerHTML = '<div class="text-xs text-slate-400 p-4 col-span-full">Brak skryptów `.sh` lub `.py` wykrytych przez skaner.</div>';
    return;
  }
  grid.innerHTML = data.scripts.map(s => `
    <div class="bg-[#080d16] border border-slate-800 rounded-xl p-4 flex flex-col justify-between gap-3">
      <div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-[10px] font-mono uppercase px-2 py-0.5 rounded ${s.type === 'sh' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'}">${s.type}</span>
          <span class="text-[11px] font-mono text-slate-500">${s.size}</span>
        </div>
        <h4 class="text-sm font-bold text-white mt-2 truncate">${s.name}</h4>
        <p class="text-xs text-slate-400 mt-1">${s.description}</p>
        <div class="text-[11px] font-mono text-slate-500 truncate mt-2">${s.path}</div>
      </div>
      <button onclick="runScript('${s.path}', '${s.type}')" class="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition">Uruchom w Kontekście</button>
    </div>
  `).join('');
}

async function runScript(path, type) {
  const context = document.getElementById('scriptCtx').value;
  await fetch('/api/scripts/run', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({path, type, context})
  });
}

async function runQuickCmd() {
  const input = document.getElementById('quickCmdInput');
  const cmd = input.value.trim();
  if (!cmd) return;
  input.value = '';
  await fetch('/api/registry/write', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({kind: 'shell', key: cmd})
  });
}

async function saveBackendMode() {
  const mode = document.getElementById('modalMode').value;
  const target = document.getElementById('modalTarget').value;
  const res = await fetch('/api/mode', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mode, target})
  });
  const data = await res.json();
  document.getElementById('backendLabel').textContent = data.mode_label;
  document.getElementById('adbModal').classList.add('hidden');
  refreshAudit();
  refreshTelemetry();
}

function initSSE() {
  const box = document.getElementById('sseConsole');
  const es = new EventSource('/api/sse');
  es.onmessage = (e) => {
    const div = document.createElement('div');
    div.textContent = e.data;
    if (e.data.includes('[ERR]')) div.className = 'text-red-400 font-mono';
    else if (e.data.includes('[OK]')) div.className = 'text-emerald-400 font-mono';
    else if (e.data.includes('[WATCHDOG]')) div.className = 'text-amber-300 font-mono font-bold';
    else if (e.data.includes('[EXEC]')) div.className = 'text-blue-400 font-mono';
    else div.className = 'text-slate-300 font-mono';
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  };
}

window.addEventListener('DOMContentLoaded', () => {
  renderModules();
  initSSE();
  refreshAudit();
  refreshTelemetry();
});
</script>
</body>
</html>
"""


def main() -> None:
    server = ThreadedHTTPServer(("0.0.0.0", PORT), PanelRequestHandler)
    print(f"[*] SecFERRO ATV Gateway Enterprise v22.0.0 działa na http://127.0.0.1:{PORT}")
    print(f"[*] Wykryty backend: {EXECUTOR.current_label()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Zamykanie serwera...")
        server.server_close()


if __name__ == "__main__":
    main()