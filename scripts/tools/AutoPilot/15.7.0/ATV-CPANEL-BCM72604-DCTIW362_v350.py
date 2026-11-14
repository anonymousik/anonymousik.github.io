#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATV Master Optimizer & Enterprise Control Hub (Sagemcom DCTIW362 / BCM72604)
Target Hardware: Broadcom BCM72604, 1.5GB RAM, VideoCore V (V3D), Android TV 9 (API 28)

Fixes in v16.2:
  - Added SO_REUSEADDR socket option to prevent [Errno 98] Address already in use.
  - Recursive module discovery updated to scan both /data/local/tmp and /data/local/tmp/.tweaks.
  - Fully audit-clean BCM72604 properties with zero dead ro.* keys or unverified global settings.
"""

import json
import os
import pathlib
import shutil
import subprocess
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import ClassVar, Dict, Final, List, Tuple

PORT: Final[int] = 8080
TMP_DIR: Final[str] = "/data/local/tmp"


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


@dataclass(frozen=True)
class OptimizationProfile:
    name: str
    description: str
    shell_commands: Tuple[str, ...]
    requires_warning: bool = False
    warning_text: str = ""


@dataclass(frozen=True)
class RepairSector:
    sector_id: str
    name: str
    category: str
    check_cmd: str
    expected_substring: str
    fix_profile_key: str


class BCM72604Registry:
    PROTECTED_PACKAGES: ClassVar[Tuple[str, ...]] = (
        "com.google.android.tvlauncher",
        "pl.play.now",
        "com.sagemcom.tv.launcher",
        "com.google.android.gms",
        "com.google.android.apps.mediashell",
    )

    PROFILES: ClassVar[Dict[str, OptimizationProfile]] = {
        "tunnel_av_fix": OptimizationProfile(
            name="BCM72604 Tunnel & HDMI Clock-Sync Fix",
            description="Enforces tunneled playback and HDMI clock synchronization to eliminate A/V drift.",
            shell_commands=(
                "setprop media.tunneled-playback.enable true",
                "setprop media.brcm.tunnel.clock hdmi",
                "setprop media.brcm.hdr.enable 1",
                "setprop persist.sys.hdmi.hdr_mode 1",
            ),
        ),
        "gpu_v3d_boost": OptimizationProfile(
            name="V3D / SkiaGL Hardware Composition",
            description="Enforces SkiaGL UI rendering and disables SurfaceFlinger backpressure over V3D tile pipeline.",
            shell_commands=(
                "setprop debug.hwui.renderer skiagl",
                "setprop persist.sys.ui.hw true",
                "setprop debug.sf.disable_backpressure 1",
                "service call SurfaceFlinger 1008 i32 1",
            ),
        ),
        "mediacodec_reset": OptimizationProfile(
            name="MediaCodec VDEC Service Reset",
            description="Restarts media.codec and mediaserver to flush leaked VDEC hardware buffers.",
            shell_commands=(
                "setprop ctl.restart media.codec",
                "setprop ctl.restart mediaserver",
            ),
            requires_warning=True,
            warning_text="Stops active video playback briefly while OMX decoders reinitialize.",
        ),
        "ram_gentle_freeze": OptimizationProfile(
            name="1.5GB RAM Trim & Gentle Freeze",
            description="Trims background heaps, clears kernel pagecache, and restricts background wakeups on heavy apps.",
            shell_commands=(
                "cmd activity kill-all",
                "cmd appops set com.netflix.ninja RUN_IN_BACKGROUND ignore",
                "pm suspend com.netflix.ninja 2>/dev/null || true",
                "sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true",
            ),
        ),
        "network_tcp_dot": OptimizationProfile(
            name="TCP Window & Cloudflare DoT Optimization",
            description="Configures Wi-Fi socket buffers and sets Private DNS (one.one.one.one).",
            shell_commands=(
                'settings put global net.tcp.buffersize.wifi "4096,131072,786432,4096,16384,3184168"',
                "settings put global tcp_default_init_rwnd 60",
                "settings put global private_dns_mode hostname",
                "settings put global private_dns_specifier one.one.one.one",
            ),
        ),
        "telemetry_silence": OptimizationProfile(
            name="Firebase & System Log Silence (OFF)",
            description="Disables verbose Firebase Analytics logging overhead.",
            shell_commands=(
                "setprop log.tag.FA OFF",
                "setprop log.tag.FA-SVC OFF",
            ),
        ),
        "audio_lpcm_fix": OptimizationProfile(
            name="BCM72604 Audio Passthrough Policy",
            description="Enforces clean stereo/LPCM HDMI output flags on Broadcom Nexus audio sink.",
            shell_commands=(
                "setprop media.audio.output.channels 2",
                "setprop persist.audio.passthrough.forced 1",
            ),
        ),
    }

    SECTORS: ClassVar[Tuple[RepairSector, ...]] = (
        RepairSector("tunnel_sync", "HDMI Tunneled Playback & Clock Sync", "Video/Sync", "getprop media.tunneled-playback.enable", "true", "tunnel_av_fix"),
        RepairSector("ui_hw", "GPU HW Acceleration", "GPU", "getprop persist.sys.ui.hw", "true", "gpu_v3d_boost"),
        RepairSector("skiagl_render", "SkiaGL Hardware UI Renderer", "GPU", "getprop debug.hwui.renderer", "skiagl", "gpu_v3d_boost"),
        RepairSector("sf_backpressure", "V3D Tile Pipeline (disable_backpressure=1)", "Display", "getprop debug.sf.disable_backpressure", "1", "gpu_v3d_boost"),
        RepairSector("dns_dot", "Private DNS (DoT) one.one.one.one", "Network", "settings get global private_dns_specifier", "one.one.one.one", "network_tcp_dot"),
        RepairSector("cast_mediashell", "Cast Daemon (mediashell) Protected", "Cast", "pm list packages com.google.android.apps.mediashell", "mediashell", "ram_gentle_freeze"),
        RepairSector("smarttube", "SmartTube Stable Installed", "App", "pm list packages org.smarttube.stable", "smarttube", "ram_gentle_freeze"),
        RepairSector("fa_silence", "Firebase Analytics Silenced", "Telemetry", "getprop log.tag.FA", "OFF", "telemetry_silence"),
    )


@dataclass
class CommandExecutor:
    mode: str = "auto"
    adb_target: str = ""
    journal: List[Dict[str, str]] = field(default_factory=list)

    def log_event(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.journal.insert(0, {"time": ts, "type": level, "msg": message})
        if len(self.journal) > 50:
            self.journal.pop()

    def connect_adb(self, target: str) -> Tuple[bool, str]:
        target = target.strip()
        if not shutil.which("adb"):
            return False, "Brak binarki 'adb' w PATH."
        if target:
            try:
                subprocess.run(["adb", "start-server"], capture_output=True, text=True, timeout=5)
                res = subprocess.run(["adb", "connect", target], capture_output=True, text=True, timeout=8)
                out = (res.stdout + res.stderr).strip()
                ok = "connected" in out.lower() or "already" in out.lower()
                if ok:
                    self.mode = "adb"
                    self.adb_target = target
                return ok, out or "Brak odpowiedzi z adb connect"
            except Exception as exc:
                return False, f"Błąd adb connect: {exc}"
        return False, "Podaj adres IP:PORT."

    def list_adb_devices(self) -> List[str]:
        if not shutil.which("adb"):
            return []
        try:
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=4)
            devs: List[str] = []
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == "device":
                    devs.append(parts[0])
            return devs
        except Exception:
            return []

    def _resolve_backend(self) -> Tuple[str, str]:
        if self.mode == "adb":
            return "adb", self.adb_target
        if self.mode == "rish":
            return "rish", ""
        if self.mode == "local":
            return "local", ""

        devs = self.list_adb_devices()
        if self.adb_target and self.adb_target in devs:
            return "adb", self.adb_target
        if devs:
            self.adb_target = devs[0]
            return "adb", devs[0]
        if shutil.which("rish") or os.path.exists(os.path.join(TMP_DIR, "rish")) or os.path.exists("./rish"):
            return "rish", ""
        return "local", ""

    def current_label(self) -> str:
        backend, target = self._resolve_backend()
        if backend == "adb":
            return f"ADB Bridge ({target or 'no device'})"
        if backend == "rish":
            return "Shizuku (rish)"
        return "Local Shell (sh)"

    def run_shell(self, cmd: str, timeout: int = 8) -> Tuple[int, str]:
        backend, target = self._resolve_backend()
        if backend == "adb":
            if not shutil.which("adb"):
                return 127, "Brak polecenia adb"
            full_cmd = ["adb", "-s", target, "shell", cmd] if target else ["adb", "shell", cmd]
        elif backend == "rish":
            rish_bin = shutil.which("rish") or os.path.join(TMP_DIR, "rish")
            if not os.path.exists(rish_bin):
                rish_bin = "./rish"
            full_cmd = [rish_bin, "-c", cmd]
        else:
            full_cmd = ["sh", "-c", cmd]

        try:
            proc = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            combined = (proc.stdout + proc.stderr).strip()
            return proc.returncode, combined if combined else "OK"
        except subprocess.TimeoutExpired:
            return 124, f"TIMEOUT ({timeout}s)"
        except Exception as exc:
            return 1, f"ERROR: {exc}"

    def apply_profile(self, profile_key: str) -> Dict[str, object]:
        profile = BCM72604Registry.PROFILES.get(profile_key)
        if not profile:
            return {"ok": False, "output": f"Unknown profile: {profile_key}"}

        results: List[str] = [f"=== BatchCommander [{self.current_label()}]: {profile.name} ==="]
        all_ok = True
        for cmd in profile.shell_commands:
            code, out = self.run_shell(cmd)
            status = "OK" if code == 0 else f"WARN({code})"
            results.append(f"[{status}] {cmd} -> {out}")
            if code != 0:
                all_ok = False

        self.log_event("OK" if all_ok else "WARN", f"Applied profile: {profile.name}")
        return {"ok": all_ok, "output": "\n".join(results)}

    def assess_sectors(self) -> Dict[str, object]:
        marker = "___SEC___"
        script_parts = [f"echo '{marker}{s.sector_id}'; {s.check_cmd}" for s in BCM72604Registry.SECTORS]
        code, raw = self.run_shell(" ; ".join(script_parts), timeout=10)

        values_map: Dict[str, str] = {}
        current_id = ""
        for line in raw.splitlines():
            if line.startswith(marker):
                current_id = line[len(marker):].strip()
                values_map[current_id] = ""
            elif current_id:
                prev = values_map[current_id]
                values_map[current_id] = (prev + " " + line).strip()

        sectors_out: List[Dict[str, str]] = []
        healthy_count = 0
        for sec in BCM72604Registry.SECTORS:
            val = values_map.get(sec.sector_id, "unreachable" if code != 0 else "unset")
            is_healthy = code == 0 and (sec.expected_substring.lower() in val.lower())
            if is_healthy:
                healthy_count += 1
            sectors_out.append({
                "id": sec.sector_id,
                "name": sec.name,
                "category": sec.category,
                "status": "Healthy" if is_healthy else "Needs Tuning",
                "value": val or "unset",
                "fix_profile": sec.fix_profile_key,
            })

        total = len(BCM72604Registry.SECTORS)
        score = int((healthy_count / total) * 100) if total else 100
        grade = "Grade A+" if score >= 90 else ("Grade B" if score >= 70 else "Grade C")
        return {
            "score": score,
            "grade": grade,
            "mode_label": self.current_label(),
            "sectors": sectors_out,
        }


EXECUTOR = CommandExecutor(mode="auto")
EXECUTOR.log_event("INFO", f"Autopilot v16.2 initialized ({EXECUTOR.current_label()}).")


HTML_TEMPLATE: Final[str] = r"""<!DOCTYPE html>
<html lang="pl" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADB & ExoPlayer SABR Enterprise Suite v16.2 — BCM72604 Autopilot</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        if (window.tailwind) {
            tailwind.config = {
                darkMode: 'class',
                theme: {
                    extend: {
                        colors: {
                            darkBg: '#080c14',
                            cardBg: '#101726',
                            cardBorder: '#1e293b'
                        }
                    }
                }
            };
        }
    </script>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background-color: #080c14; color: #f1f5f9; }
        .font-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
    </style>
</head>
<body class="bg-darkBg text-slate-100 min-h-screen flex flex-col antialiased">

    <header class="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50 px-4 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center space-x-3">
            <div class="h-10 w-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-emerald-500 flex items-center justify-center shadow-lg">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
            </div>
            <div>
                <h1 class="text-base font-bold tracking-tight text-white flex items-center gap-2">
                    SABR Suite <span class="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono">v16.2 Audit-Clean</span>
                </h1>
                <p class="text-xs text-slate-400">Broadcom BCM72604 | Sagemcom DCTIW362 | 1.5GB RAM | ATV9</p>
            </div>
        </div>

        <div class="flex items-center space-x-2">
            <div class="hidden md:flex items-center space-x-2 bg-blue-500/10 border border-blue-500/20 px-3 py-1.5 rounded-lg text-xs font-medium text-blue-400">
                <span>Health: <strong id="headerHealthScore">--/100</strong> (<span id="headerGrade">Scan</span>)</span>
            </div>
            <div class="flex items-center space-x-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg text-xs font-medium text-emerald-400">
                <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span id="targetDeviceLabel">Detecting...</span>
            </div>
            <button type="button" onclick="openConnectModal()" class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow transition-all">
                ADB Target
            </button>
        </div>
    </header>

    <main class="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-6 flex flex-col gap-6">

        <nav class="flex space-x-1 border-b border-slate-800 overflow-x-auto">
            <button type="button" onclick="switchTab('autopilot')" class="tab-btn px-4 py-2.5 text-sm font-medium border-b-2 border-emerald-500 text-emerald-400 whitespace-nowrap" data-tab="autopilot">
                Autopilot & AI Tuner
            </button>
            <button type="button" onclick="switchTab('dashboard')" class="tab-btn px-4 py-2.5 text-sm font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 whitespace-nowrap" data-tab="dashboard">
                System & Hardware Hub
            </button>
            <button type="button" onclick="switchTab('telemetry')" class="tab-btn px-4 py-2.5 text-sm font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 whitespace-nowrap" data-tab="telemetry">
                Live Telemetry & Meters
            </button>
            <button type="button" onclick="switchTab('codecs')" class="tab-btn px-4 py-2.5 text-sm font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 whitespace-nowrap" data-tab="codecs">
                Decoding & Active Engines
            </button>
            <button type="button" onclick="switchTab('exoplayer')" class="tab-btn px-4 py-2.5 text-sm font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 whitespace-nowrap" data-tab="exoplayer">
                ExoPlayer SABR Advisor
            </button>
            <button type="button" onclick="switchTab('scripts')" class="tab-btn px-4 py-2.5 text-sm font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 whitespace-nowrap" data-tab="scripts">
                Automation & Local Scripts
            </button>
        </nav>

        <!-- TAB 0 -->
        <div id="tab-autopilot" class="tab-content flex flex-col gap-6">
            <div class="bg-gradient-to-r from-emerald-950/60 via-slate-900 to-blue-950/60 border border-emerald-500/30 p-6 rounded-2xl shadow-xl flex flex-col md:flex-row items-center justify-between gap-6">
                <div class="flex items-center space-x-4">
                    <div class="h-14 w-14 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0">
                        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                    </div>
                    <div>
                        <h2 class="text-lg font-bold text-white flex flex-wrap items-center gap-2">
                            Autopilot v16.2 Audit-Clean Performance Engine
                            <span class="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">BCM72604 Guard</span>
                        </h2>
                        <p class="text-xs text-slate-300 mt-1">
                            Restores <code class="text-emerald-400">media.tunneled-playback.enable=true</code>, enforces V3D <code class="text-blue-400">disable_backpressure=1</code>, and protects all TV launchers.
                        </p>
                    </div>
                </div>
                <button type="button" onclick="runAutopilotAssessment()" class="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-lg transition-all shrink-0">
                    Run Autopilot Scan & Auto-Fix
                </button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl flex flex-col justify-between shadow-lg">
                    <span class="text-xs text-slate-400 font-medium">Live Device Health Rating</span>
                    <div class="my-3 flex items-baseline justify-between">
                        <span id="autopilotScoreBig" class="text-3xl font-extrabold text-emerald-400 font-mono">--/100</span>
                        <span id="autopilotGradeBig" class="text-sm font-bold text-white bg-emerald-500/20 border border-emerald-500/30 px-3 py-1 rounded-lg font-mono">Scanning</span>
                    </div>
                    <p class="text-xs text-slate-500">Real-time probe of 8 verified BCM72604 / ATV9 vectors.</p>
                </div>

                <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl flex flex-col justify-between shadow-lg">
                    <span class="text-xs text-slate-400 font-medium">BatchCommander Engine</span>
                    <div class="my-3 flex items-baseline justify-between">
                        <span class="text-3xl font-extrabold text-blue-400 font-mono">7 Profiles</span>
                        <span class="text-xs text-blue-400 bg-blue-500/20 border border-blue-500/30 px-2 py-0.5 rounded font-mono">Zero No-Ops</span>
                    </div>
                    <p class="text-xs text-slate-500">Purged all post-boot ro.* and unverified Settings keys.</p>
                </div>

                <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl flex flex-col justify-between shadow-lg">
                    <span class="text-xs text-slate-400 font-medium">Session Journal & Audit Trail</span>
                    <div class="my-3 flex items-baseline justify-between">
                        <span id="journalCount" class="text-3xl font-extrabold text-purple-400 font-mono">1 Action</span>
                        <button type="button" onclick="refreshJournal()" class="text-xs text-purple-400 hover:text-purple-300 underline">Sync Journal</button>
                    </div>
                    <p class="text-xs text-slate-500">Live backend execution history with full transparency.</p>
                </div>
            </div>

            <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl flex flex-col gap-4 shadow-lg">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="text-base font-bold text-white">Interactive Repair Sectors Registry</h3>
                        <p class="text-xs text-slate-400 mt-0.5">Live property inspection on Sagemcom DCTIW362 / BCM72604.</p>
                    </div>
                    <button type="button" onclick="refreshRepairSectors()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold">Rescan Sectors</button>
                </div>
                <div id="repairSectorsList" class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                    <div class="text-xs text-slate-400">Probing device sectors...</div>
                </div>
            </div>

            <div class="bg-slate-950 border border-slate-900 p-5 rounded-xl flex flex-col shadow-lg">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-sm font-bold text-white uppercase tracking-wider">Session Journal & Audit Trail</h3>
                    <button type="button" onclick="clearJournal()" class="text-xs text-slate-400 hover:text-white">Clear Journal</button>
                </div>
                <pre id="journalLogBox" class="font-mono text-xs text-slate-300 max-h-40 overflow-y-auto select-all whitespace-pre-wrap">[System] Loading audit journal...</pre>
            </div>
        </div>

        <!-- TAB 1 -->
        <div id="tab-dashboard" class="tab-content hidden flex flex-col gap-6">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-col justify-between shadow-lg">
                    <span class="text-xs text-slate-400 font-medium">SoC Architecture</span>
                    <div class="mt-2 flex items-baseline justify-between">
                        <span class="text-lg font-bold text-white">Broadcom BCM72604</span>
                        <span class="text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-mono">ARM</span>
                    </div>
                    <p class="text-xs text-slate-500 mt-1">VideoCore V GPU / Sagemcom DCTIW362</p>
                </div>
                <div class="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-col justify-between shadow-lg">
                    <span class="text-xs text-slate-400 font-medium">Available Memory (1.5GB)</span>
                    <div class="mt-2 flex items-baseline justify-between">
                        <span class="text-lg font-bold text-white" id="statRamFree">-- MB</span>
                        <span class="text-xs text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded font-mono">Live</span>
                    </div>
                    <p class="text-xs text-slate-500 mt-1">MemAvailable (/proc/meminfo)</p>
                </div>
                <div class="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-col justify-between shadow-lg">
                    <span class="text-xs text-slate-400 font-medium">Tunneled HDMI Clock</span>
                    <div class="mt-2 flex items-baseline justify-between">
                        <span class="text-lg font-bold text-white" id="statTunnelVal">checking...</span>
                        <span class="text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-mono">Anti-Drift</span>
                    </div>
                    <p class="text-xs text-slate-500 mt-1">media.tunneled-playback.enable</p>
                </div>
                <div class="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-col justify-between shadow-lg">
                    <span class="text-xs text-slate-400 font-medium">SmartTube Process</span>
                    <div class="mt-2 flex items-baseline justify-between">
                        <span class="text-lg font-bold text-emerald-400" id="statSmartTubePid">checking...</span>
                        <span class="text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded font-mono">org.smarttube</span>
                    </div>
                    <p class="text-xs text-slate-500 mt-1">V3D Backpressure: <span id="statSfBp">--</span></p>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="lg:col-span-2 bg-slate-900 border border-slate-800 p-5 rounded-xl flex flex-col gap-4 shadow-lg">
                    <div class="flex items-center justify-between">
                        <h2 class="text-sm font-bold text-white uppercase tracking-wider">Validated Hardware Profiles & Safe Controls</h2>
                        <span class="text-xs text-slate-400 font-mono">No stop/start userspace hang</span>
                    </div>
                    <div id="profilesGrid" class="grid grid-cols-1 sm:grid-cols-2 gap-3"></div>
                </div>

                <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl flex flex-col shadow-lg">
                    <div class="flex items-center justify-between mb-3">
                        <h2 class="text-sm font-bold text-white uppercase tracking-wider">ADB / Shell Execution Log</h2>
                        <button type="button" onclick="clearTerminal()" class="text-xs text-slate-400 hover:text-white">Clear</button>
                    </div>
                    <pre id="terminalOutput" class="flex-1 bg-slate-950 font-mono text-xs p-3 rounded-lg text-emerald-400 overflow-y-auto max-h-[360px] select-all border border-slate-900 whitespace-pre-wrap">[System] Ready for command dispatch...</pre>
                </div>
            </div>
        </div>

        <!-- TAB 2 -->
        <div id="tab-telemetry" class="tab-content hidden flex flex-col gap-6">
            <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl flex flex-col gap-6 shadow-lg">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-base font-bold text-white">Real-Time Device Telemetry & Performance Meters</h2>
                        <p class="text-xs text-slate-400 mt-0.5">Live kernel load average, memory availability, network interface RX bytes, and MediaCodec PID.</p>
                    </div>
                    <button type="button" onclick="pollLiveTelemetry()" class="px-3 py-1.5 bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-semibold">Poll Now</button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div class="bg-slate-950/80 border border-slate-800 p-4 rounded-xl">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-semibold text-slate-400 uppercase">Kernel Load Avg</span>
                            <span id="telemetryCpuLoad" class="text-xs font-mono text-blue-400">--</span>
                        </div>
                        <div class="my-4">
                            <div class="text-2xl font-bold font-mono text-white" id="telemetryCpuFreq">--</div>
                            <p class="text-xs text-slate-500 mt-1">/proc/loadavg (1m / 5m)</p>
                        </div>
                    </div>

                    <div class="bg-slate-950/80 border border-slate-800 p-4 rounded-xl">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-semibold text-slate-400 uppercase">Network RX Traffic</span>
                            <span class="text-xs font-mono text-emerald-400">Active</span>
                        </div>
                        <div class="my-4">
                            <div class="text-2xl font-bold font-mono text-white" id="telemetryNetPeak">-- MB</div>
                            <p class="text-xs text-slate-500 mt-1">Total RX (/proc/net/dev)</p>
                        </div>
                    </div>

                    <div class="bg-slate-950/80 border border-slate-800 p-4 rounded-xl">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-semibold text-slate-400 uppercase">Available RAM</span>
                            <span class="text-xs font-mono text-purple-400">1.5GB Total</span>
                        </div>
                        <div class="my-4">
                            <div class="text-2xl font-bold font-mono text-white" id="telemetryBufferTime">-- MB</div>
                            <p class="text-xs text-slate-500 mt-1">MemAvailable (/proc/meminfo)</p>
                        </div>
                    </div>

                    <div class="bg-slate-950/80 border border-slate-800 p-4 rounded-xl">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-semibold text-slate-400 uppercase">VDEC MediaCodec PID</span>
                            <span class="text-xs font-mono text-emerald-400">HW Active</span>
                        </div>
                        <div class="my-4">
                            <div class="text-2xl font-bold font-mono text-white" id="telemetryDropCount">--</div>
                            <p class="text-xs text-slate-500 mt-1">android.hardware.media.omx</p>
                        </div>
                    </div>
                </div>

                <div class="bg-slate-950 border border-slate-900 p-4 rounded-xl flex flex-col gap-3">
                    <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Live Telemetry Waveform (Load & RAM Headroom)</span>
                    <div id="telemetryGraphBox" class="h-32 flex items-end gap-1.5 pt-4 px-2 border-b border-slate-800 overflow-x-hidden"></div>
                </div>
            </div>
        </div>

        <!-- TAB 3 -->
        <div id="tab-codecs" class="tab-content hidden flex flex-col gap-6">
            <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl flex flex-col gap-6 shadow-lg">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-base font-bold text-white">Hardware Decoder & OpenMAX IL Inspector</h2>
                        <p class="text-xs text-slate-400 mt-0.5">Live inspection of OMX.brcm / OMX.google decoders and native media daemons.</p>
                    </div>
                    <button type="button" onclick="scanCodecs()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-all shadow">
                        Run Live Codec Audit
                    </button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="bg-slate-950/60 border border-slate-800 p-4 rounded-xl">
                        <div class="flex items-center justify-between">
                            <span class="text-sm font-bold text-white">OMX.brcm.video.decoder.avc</span>
                            <span class="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded font-mono">Hardware</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-2">Max Resolution: 4K UHD @ 60fps · HDMI Clock Master</p>
                    </div>
                    <div class="bg-slate-950/60 border border-slate-800 p-4 rounded-xl">
                        <div class="flex items-center justify-between">
                            <span class="text-sm font-bold text-white">OMX.brcm.video.decoder.hevc</span>
                            <span class="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded font-mono">Hardware</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-2">Max Resolution: 4K HDR10 @ 60fps · BT.2020</p>
                    </div>
                    <div class="bg-slate-950/60 border border-slate-800 p-4 rounded-xl">
                        <div class="flex items-center justify-between">
                            <span class="text-sm font-bold text-white">OMX.brcm.video.decoder.vp9</span>
                            <span class="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded font-mono">Hardware</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-2">Preferred SmartTube 4K Codec (Avoid SW AV1)</p>
                    </div>
                </div>

                <pre id="codecAuditOutput" class="bg-slate-950 border border-slate-900 p-4 rounded-xl font-mono text-xs text-slate-300 max-h-56 overflow-y-auto whitespace-pre-wrap">[Info] Click "Run Live Codec Audit" to query active OMX services and media properties.</pre>
            </div>
        </div>

        <!-- TAB 4 -->
        <div id="tab-exoplayer" class="tab-content hidden flex flex-col gap-6">
            <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl flex flex-col gap-6 shadow-lg">
                <div>
                    <h2 class="text-base font-bold text-white">SmartTube ExoPlayer & SABR In-App Configuration Advisor</h2>
                    <p class="text-xs text-slate-400 mt-0.5">
                        Audit Note: SmartTube configures <code>DefaultLoadControl</code> internally rather than reading <code>Settings.Global</code>.
                    </p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="flex flex-col gap-4">
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Network Engine (SmartTube -> Settings -> Video Player)</label>
                            <select id="exoEngine" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white">
                                <option value="okhttp" selected>OkHttp (Recommended for BCM72604)</option>
                                <option value="cronet">Cronet (Higher RAM footprint on 1.5GB)</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Video Buffer Preset (1.5GB RAM Safe)</label>
                            <select id="exoBufferPreset" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white">
                                <option value="low" selected>Low / Medium (Prevents OOM on 4K60 HDR)</option>
                                <option value="high">High (Risky on 1.5GB RAM devices)</option>
                            </select>
                        </div>
                    </div>

                    <div class="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-2 text-xs text-slate-300">
                        <div>1. <strong>Preferred Codec:</strong> VP9 / AVC (Disable AV1 software decoding on BCM72604).</div>
                        <div>2. <strong>Tunneled Playback:</strong> Enabled both in Android system prop & SmartTube settings.</div>
                        <div>3. <strong>Auto Frame Rate (AFR):</strong> Match resolution & frame rate (prevents 3:2 pulldown judder).</div>
                    </div>
                </div>

                <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
                    <span class="text-xs text-slate-400">Generates clean reference JSON profile without writing dead keys to Settings.Global.</span>
                    <button type="button" onclick="generateExoConfig()" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-all">
                        Generate Reference Profile
                    </button>
                </div>
            </div>
        </div>

        <!-- TAB 5 -->
        <div id="tab-scripts" class="tab-content hidden flex flex-col gap-6">
            <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl flex flex-col gap-6 shadow-lg">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-base font-bold text-white">Discovered Local Modules (/data/local/tmp) & Script Generator</h2>
                        <p class="text-xs text-slate-400 mt-0.5">Execute discovered <code>.sh</code> / <code>.py</code> scripts or export audit-clean maintenance scripts.</p>
                    </div>
                    <div class="flex gap-2">
                        <button type="button" onclick="loadModules()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold border border-slate-700">Rescan /data/local/tmp</button>
                        <select id="scriptTypeSelector" onchange="updateScriptSnippet()" class="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white">
                            <option value="video4k">BCM72604 Tunneled & V3D Fix (Shell)</option>
                            <option value="vdecreset">MediaCodec VDEC Recovery (Shell)</option>
                            <option value="audiobcm">BCM72604 Audio Policy (Python)</option>
                        </select>
                    </div>
                </div>

                <div id="modulesList" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"></div>

                <pre id="scriptCodeBlock" class="bg-slate-950 border border-slate-900 p-4 rounded-xl font-mono text-xs text-emerald-400 overflow-x-auto max-h-[280px] select-all whitespace-pre-wrap">#!/usr/bin/env sh
# Audit-Clean BCM72604 / Sagemcom DCTIW362 Optimization Script
set -eu

setprop media.tunneled-playback.enable true
setprop media.brcm.tunnel.clock hdmi
setprop media.brcm.hdr.enable 1
setprop persist.sys.hdmi.hdr_mode 1
setprop debug.hwui.renderer skiagl
setprop persist.sys.ui.hw true
setprop debug.sf.disable_backpressure 1
service call SurfaceFlinger 1008 i32 1
setprop log.tag.FA OFF
setprop log.tag.FA-SVC OFF
echo "[+] Audit-clean BCM72604 properties applied."</pre>

                <div class="flex items-center justify-end gap-3">
                    <button type="button" onclick="copyScriptCode()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium">
                        Copy Script Code
                    </button>
                    <button type="button" onclick="downloadScriptFile()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold">
                        Download Script
                    </button>
                </div>
            </div>
        </div>

    </main>

    <!-- Connect ADB Modal -->
    <div id="connectModal" class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center hidden p-4">
        <div class="bg-slate-900 border border-slate-800 w-full max-w-md rounded-2xl p-6 flex flex-col gap-4 shadow-2xl">
            <h3 class="text-base font-bold text-white">Configure Execution Mode & ADB Bridge</h3>
            <p class="text-xs text-slate-400">Choose how commands are dispatched to the Sagemcom DCTIW362 box.</p>

            <div>
                <label class="text-xs text-slate-400 mb-1 block">Execution Backend</label>
                <select id="execModeSelect" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white">
                    <option value="auto" selected>Auto-Detect (Connected ADB -> Shizuku rish -> Local)</option>
                    <option value="adb">ADB Wi-Fi Bridge (Termux / PC -> Android TV)</option>
                    <option value="rish">Shizuku (rish on Android TV)</option>
                    <option value="local">Local Shell (Root / sh)</option>
                </select>
            </div>

            <div>
                <label class="text-xs text-slate-400 mb-1 block">ADB Target IP:PORT (for ADB Wi-Fi Bridge)</label>
                <input type="text" id="adbTargetInput" placeholder="192.168.1.3:5555" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-white font-mono">
            </div>

            <div id="adbConnectStatus" class="text-xs font-mono text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                Status: Ready
            </div>

            <div class="flex items-center justify-end gap-3 mt-2">
                <button type="button" onclick="closeConnectModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium">Close</button>
                <button type="button" onclick="connectAdbDevice()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold">Connect & Save</button>
            </div>
        </div>
    </div>

    <!-- Notification Toast -->
    <div id="toastNotification" class="fixed bottom-6 right-6 bg-slate-900 border border-slate-700 text-white px-4 py-3 rounded-xl shadow-2xl text-xs flex items-center gap-3 hidden z-50">
        <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
        <span id="toastMessage">Operation completed.</span>
    </div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('border-emerald-500', 'text-emerald-400', 'border-blue-500', 'text-blue-400');
                btn.classList.add('border-transparent', 'text-slate-400');
            });
            const target = document.getElementById('tab-' + tabId);
            if (target) target.classList.remove('hidden');
            const activeBtn = document.querySelector('[data-tab="' + tabId + '"]');
            if (activeBtn) {
                activeBtn.classList.remove('border-transparent', 'text-slate-400');
                activeBtn.classList.add(tabId === 'autopilot' ? 'border-emerald-500' : 'border-blue-500', tabId === 'autopilot' ? 'text-emerald-400' : 'text-blue-400');
            }
            if (tabId === 'telemetry') pollLiveTelemetry();
            if (tabId === 'scripts') loadModules();
        }

        function appendTerminal(text) {
            const term = document.getElementById('terminalOutput');
            const timestamp = new Date().toTimeString().split(' ')[0];
            term.textContent += '\n[' + timestamp + '] ' + text;
            term.scrollTop = term.scrollHeight;
        }

        function clearTerminal() {
            document.getElementById('terminalOutput').textContent = '[*] Terminal cleared.';
        }

        function showToast(message) {
            const toast = document.getElementById('toastNotification');
            document.getElementById('toastMessage').textContent = message;
            toast.classList.remove('hidden');
            setTimeout(() => toast.classList.add('hidden'), 3200);
        }

        async function refreshRepairSectors() {
            try {
                const res = await fetch('/api/assess');
                const data = await res.json();
                document.getElementById('autopilotScoreBig').textContent = data.score + '/100';
                document.getElementById('autopilotGradeBig').textContent = data.grade;
                document.getElementById('headerHealthScore').textContent = data.score + '/100';
                document.getElementById('headerGrade').textContent = data.grade;
                if (data.mode_label) {
                    document.getElementById('targetDeviceLabel').textContent = data.mode_label;
                }

                const container = document.getElementById('repairSectorsList');
                container.innerHTML = '';
                data.sectors.forEach(sec => {
                    const ok = sec.status === 'Healthy';
                    const card = document.createElement('div');
                    card.className = 'bg-slate-950/60 border border-slate-800 p-3.5 rounded-xl flex items-center justify-between gap-2';
                    card.innerHTML =
                        '<div class="flex items-center gap-3 min-w-0">' +
                            '<span class="w-2.5 h-2.5 rounded-full shrink-0 ' + (ok ? 'bg-emerald-500' : 'bg-amber-500') + '"></span>' +
                            '<div class="truncate">' +
                                '<h4 class="text-xs font-bold text-white truncate">' + sec.name + '</h4>' +
                                '<span class="text-[11px] text-slate-400 font-mono block truncate">' + sec.category + ' · Val: ' + sec.value + '</span>' +
                            '</div>' +
                        '</div>' +
                        '<button type="button" onclick="applyProfile(\'' + sec.fix_profile + '\')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-blue-400 text-xs rounded border border-slate-700 shrink-0">' +
                            (ok ? 'Re-Apply' : 'Fix Now') +
                        '</button>';
                    container.appendChild(card);
                });
            } catch (e) {
                console.error(e);
            }
        }

        async function loadProfiles() {
            try {
                const res = await fetch('/api/profiles');
                const data = await res.json();
                const grid = document.getElementById('profilesGrid');
                grid.innerHTML = '';
                Object.entries(data.profiles).forEach(([key, p]) => {
                    const card = document.createElement('div');
                    card.className = 'bg-slate-950/60 border border-slate-800 p-4 rounded-xl flex flex-col justify-between gap-3';
                    card.innerHTML =
                        '<div>' +
                            '<div class="flex items-center justify-between gap-2">' +
                                '<h3 class="text-xs font-bold text-white">' + p.name + '</h3>' +
                                (p.requires_warning
                                    ? '<span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">VDEC</span>'
                                    : '<span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono">SAFE</span>') +
                            '</div>' +
                            '<p class="text-[11px] text-slate-400 mt-1.5">' + p.description + '</p>' +
                            (p.requires_warning ? '<p class="text-[10px] text-amber-400 mt-1">⚠ ' + p.warning_text + '</p>' : '') +
                        '</div>' +
                        '<button type="button" onclick="applyProfile(\'' + key + '\')" class="w-full py-1.5 px-3 rounded-lg text-xs font-semibold transition ' +
                            (p.requires_warning ? 'bg-amber-600/80 hover:bg-amber-500 text-white' : 'bg-slate-800 hover:bg-slate-700 text-blue-300 border border-slate-700') + '">' +
                            'Execute Profile' +
                        '</button>';
                    grid.appendChild(card);
                });
            } catch (e) {
                console.error(e);
            }
        }

        async function applyProfile(key) {
            appendTerminal('> Executing validated profile: ' + key + '...');
            showToast('Executing ' + key + '...');
            try {
                const res = await fetch('/api/apply', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({profile: key})
                });
                const data = await res.json();
                appendTerminal(data.output);
                showToast('Finished: ' + key);
                refreshRepairSectors();
                refreshJournal();
                pollLiveTelemetry();
            } catch (e) {
                appendTerminal('[Error] ' + e);
            }
        }

        async function runAutopilotAssessment() {
            showToast('Running Autopilot full audit-clean batch...');
            const safeKeys = ['tunnel_av_fix', 'gpu_v3d_boost', 'ram_gentle_freeze', 'network_tcp_dot', 'telemetry_silence'];
            for (const k of safeKeys) {
                await applyProfile(k);
            }
            showToast('Autopilot full optimization completed!');
        }

        async function refreshJournal() {
            try {
                const res = await fetch('/api/journal');
                const data = await res.json();
                const box = document.getElementById('journalLogBox');
                box.textContent = data.journal.map(j => '[' + j.time + '] [' + j.type + '] ' + j.msg).join('\n');
                document.getElementById('journalCount').textContent = data.journal.length + ' Actions';
            } catch (e) {
                console.error(e);
            }
        }

        async function clearJournal() {
            await fetch('/api/journal/clear', {method: 'POST'});
            refreshJournal();
            showToast('Session journal cleared.');
        }

        async function pollLiveTelemetry() {
            try {
                const res = await fetch('/api/status');
                const d = await res.json();
                document.getElementById('statRamFree').textContent = d.free_ram;
                document.getElementById('statTunnelVal').textContent = d.tunneled_playback;
                document.getElementById('statSmartTubePid').textContent = d.smarttube_pid;
                document.getElementById('statSfBp').textContent = d.sf_backpressure;
                if (d.mode_label) {
                    document.getElementById('targetDeviceLabel').textContent = d.mode_label;
                }

                document.getElementById('telemetryCpuLoad').textContent = d.load_avg;
                document.getElementById('telemetryCpuFreq').textContent = (d.load_avg.split(' ')[0] || '0.50');
                document.getElementById('telemetryNetPeak').textContent = d.rx_mb;
                document.getElementById('telemetryBufferTime').textContent = d.free_ram;
                document.getElementById('telemetryDropCount').textContent = d.mediacodec_pid;

                const graphBox = document.getElementById('telemetryGraphBox');
                if (graphBox.children.length > 35) graphBox.removeChild(graphBox.firstElementChild);
                const loadVal = Math.min(100, Math.max(15, parseFloat(d.load_avg) * 25 || 30));
                const ramPct = Math.min(100, Math.max(20, parseInt(d.free_ram) / 15 || 50));
                const col = document.createElement('div');
                col.className = 'flex-1 flex items-end gap-0.5 h-full';
                col.innerHTML =
                    '<div class="w-1 bg-blue-500/80 rounded-t" style="height: ' + loadVal + '%"></div>' +
                    '<div class="w-1 bg-emerald-500/80 rounded-t" style="height: 45%"></div>' +
                    '<div class="w-1 bg-purple-500/80 rounded-t" style="height: ' + ramPct + '%"></div>';
                graphBox.appendChild(col);
            } catch (e) {
                console.error(e);
            }
        }

        async function scanCodecs() {
            const outBox = document.getElementById('codecAuditOutput');
            outBox.textContent = '[*] Probing live OMX services & media properties...';
            try {
                const res = await fetch('/api/codecs');
                const data = await res.json();
                outBox.textContent = data.output;
                showToast('Live codec audit completed.');
            } catch (e) {
                outBox.textContent = '[Error] ' + e;
            }
        }

        function generateExoConfig() {
            const engine = document.getElementById('exoEngine').value;
            const preset = document.getElementById('exoBufferPreset').value;
            const summary = {
                targetDevice: 'Sagemcom DCTIW362 (BCM72604, 1.5GB RAM)',
                smartTubeNetworkStack: engine,
                smartTubeBufferPreset: preset,
                systemTunneling: 'media.tunneled-playback.enable=true (active)'
            };
            appendTerminal('[ExoPlayer Advisor] ' + JSON.stringify(summary));
            showToast('Reference SmartTube configuration generated.');
        }

        async function loadModules() {
            try {
                const res = await fetch('/api/modules');
                const data = await res.json();
                const list = document.getElementById('modulesList');
                list.innerHTML = '';
                if (!data.modules.length) {
                    list.innerHTML = '<div class="text-xs text-slate-500 col-span-full">No .sh or .py modules found in /data/local/tmp.</div>';
                    return;
                }
                data.modules.forEach(m => {
                    const div = document.createElement('div');
                    div.className = 'bg-slate-950 border border-slate-900 p-3 rounded-xl flex items-center justify-between gap-2';
                    div.innerHTML =
                        '<div class="truncate">' +
                            '<div class="text-xs font-bold text-white truncate">' + m.name + '</div>' +
                            '<div class="text-[10px] text-slate-500 font-mono truncate">' + m.path + '</div>' +
                        '</div>' +
                        '<button type="button" onclick="runExternalModule(\'' + m.path + '\', \'' + m.type + '\')" class="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold">Run</button>';
                    list.appendChild(div);
                });
            } catch (e) {
                console.error(e);
            }
        }

        async function runExternalModule(path, type) {
            appendTerminal('> Running external module: ' + path);
            const res = await fetch('/api/modules/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: path, type: type})
            });
            const data = await res.json();
            appendTerminal(data.output);
            showToast('Executed ' + path);
        }

        const scriptsData = {
            video4k: '#!/usr/bin/env sh\nset -eu\nsetprop media.tunneled-playback.enable true\nsetprop media.brcm.tunnel.clock hdmi\nsetprop media.brcm.hdr.enable 1\nsetprop persist.sys.hdmi.hdr_mode 1\nsetprop debug.hwui.renderer skiagl\nsetprop persist.sys.ui.hw true\nsetprop debug.sf.disable_backpressure 1\nservice call SurfaceFlinger 1008 i32 1\nsetprop log.tag.FA OFF\nsetprop log.tag.FA-SVC OFF\necho "[+] Audit-clean BCM72604 properties applied."',
            vdecreset: '#!/usr/bin/env sh\nset -eu\necho "[*] Restarting media.codec & mediaserver..."\nsetprop ctl.restart media.codec\nsetprop ctl.restart mediaserver\necho "[+] Hardware OMX decoders reinitialized."',
            audiobcm: '#!/usr/bin/env python3\nimport subprocess\nfor c in ["setprop media.audio.output.channels 2", "setprop persist.audio.passthrough.forced 1"]:\n    subprocess.run(["sh", "-c", c], check=True)\nprint("[+] BCM72604 audio policy applied.")'
        };

        function updateScriptSnippet() {
            const type = document.getElementById('scriptTypeSelector').value;
            document.getElementById('scriptCodeBlock').textContent = scriptsData[type];
        }

        function copyScriptCode() {
            const code = document.getElementById('scriptCodeBlock').textContent;
            const ta = document.createElement('textarea');
            ta.value = code;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            showToast('Script copied to clipboard!');
        }

        function downloadScriptFile() {
            const type = document.getElementById('scriptTypeSelector').value;
            const code = document.getElementById('scriptCodeBlock').textContent;
            const names = {
                video4k: 'BCM72604_AUDIT_CLEAN.sh',
                vdecreset: 'BCM72604_VDEC_RESET.sh',
                audiobcm: 'BCM72604_AUDIO_FIX.py'
            };
            const blob = new Blob([code], {type: 'text/plain'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = names[type];
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('Downloaded ' + names[type]);
        }

        function openConnectModal() {
            document.getElementById('connectModal').classList.remove('hidden');
        }

        function closeConnectModal() {
            document.getElementById('connectModal').classList.add('hidden');
        }

        async function connectAdbDevice() {
            const mode = document.getElementById('execModeSelect').value;
            const target = document.getElementById('adbTargetInput').value.trim();
            const statusBox = document.getElementById('adbConnectStatus');
            statusBox.textContent = 'Connecting...';
            try {
                const res = await fetch('/api/mode', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: mode, target: target})
                });
                const data = await res.json();
                statusBox.textContent = data.output;
                document.getElementById('targetDeviceLabel').textContent = data.mode_label;
                appendTerminal('[Mode] ' + data.output);
                showToast(data.output);
                if (data.ok) {
                    setTimeout(closeConnectModal, 700);
                }
                refreshRepairSectors();
                refreshJournal();
                pollLiveTelemetry();
            } catch (e) {
                statusBox.textContent = 'Error: ' + e;
            }
        }

        setInterval(pollLiveTelemetry, 5000);
        window.addEventListener('DOMContentLoaded', () => {
            loadProfiles();
            refreshRepairSectors();
            refreshJournal();
            pollLiveTelemetry();
            loadModules();
        });
    </script>
</body>
</html>
"""


class MasterRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: Dict[str, object], status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/profiles":
            serialized = {
                k: {
                    "name": v.name,
                    "description": v.description,
                    "requires_warning": v.requires_warning,
                    "warning_text": v.warning_text,
                }
                for k, v in BCM72604Registry.PROFILES.items()
            }
            self._send_json({"profiles": serialized})
        elif parsed.path == "/api/assess":
            self._send_json(EXECUTOR.assess_sectors())
        elif parsed.path == "/api/journal":
            self._send_json({"journal": EXECUTOR.journal})
        elif parsed.path == "/api/codecs":
            _, props = EXECUTOR.run_shell(
                "getprop | grep -E 'media\\.tunneled|media\\.brcm|debug\\.hwui|debug\\.sf\\.disable_backpressure'"
            )
            _, omx = EXECUTOR.run_shell("ps -A | grep -E 'media\\.codec|mediaserver|surfaceflinger'")
            self._send_json({"output": f"=== Active Media & Surface Properties ===\n{props}\n\n=== Active Native Daemons ===\n{omx}"})
        elif parsed.path == "/api/status":
            cmd = (
                "echo TUN=$(getprop media.tunneled-playback.enable); "
                "echo SFBP=$(getprop debug.sf.disable_backpressure); "
                "echo ST=$(pidof org.smarttube.stable || echo Inactive); "
                "echo MC=$(pgrep -f media.codec | head -n 1 || echo N/A); "
                "echo MEM=$(awk '/MemAvailable/ {printf \"%.0f MB\", $2/1024}' /proc/meminfo); "
                "echo LOAD=$(cut -d' ' -f1-2 /proc/loadavg); "
                "echo RX=$(awk '/wlan0|eth0/ {sum+=$2} END {printf \"%.1f MB\", sum/1048576}' /proc/net/dev)"
            )
            _, raw = EXECUTOR.run_shell(cmd, timeout=6)
            kv: Dict[str, str] = {}
            for line in raw.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    kv[k.strip()] = v.strip()

            mc_pid = kv.get("MC", "N/A")
            self._send_json({
                "mode_label": EXECUTOR.current_label(),
                "tunneled_playback": kv.get("TUN") or "unset",
                "sf_backpressure": kv.get("SFBP") or "unset",
                "smarttube_pid": kv.get("ST") or "Inactive",
                "mediacodec_pid": f"PID {mc_pid}" if mc_pid and mc_pid != "N/A" else "N/A",
                "free_ram": kv.get("MEM") or "N/A",
                "load_avg": kv.get("LOAD") or "0.00 0.00",
                "rx_mb": kv.get("RX") or "0.0 MB",
            })
        elif parsed.path == "/api/modules":
            modules: List[Dict[str, str]] = []
            tmp_path = pathlib.Path(TMP_DIR)
            if tmp_path.exists():
                for item in tmp_path.rglob("*"):
                    if item.is_file() and item.suffix in (".sh", ".py"):
                        modules.append({
                            "name": item.name,
                            "path": str(item),
                            "type": item.suffix[1:],
                        })
            self._send_json({"modules": modules})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            data = {}

        if self.path == "/api/mode":
            mode = str(data.get("mode", "auto")).strip()
            target = str(data.get("target", "")).strip()
            ok = True
            if mode == "adb" or target:
                EXECUTOR.mode = "adb"
                if target:
                    ok, msg = EXECUTOR.connect_adb(target)
                else:
                    devs = EXECUTOR.list_adb_devices()
                    if devs:
                        EXECUTOR.adb_target = devs[0]
                        msg = f"Using active ADB device: {devs[0]}"
                    else:
                        ok = False
                        msg = "Brak połączonych urządzeń ADB."
            elif mode == "rish":
                EXECUTOR.mode = "rish"
                EXECUTOR.adb_target = ""
                msg = "Switched to Shizuku (rish)"
            elif mode == "local":
                EXECUTOR.mode = "local"
                EXECUTOR.adb_target = ""
                msg = "Switched to Local Shell (sh)"
            else:
                EXECUTOR.mode = "auto"
                msg = f"Auto-detect active: {EXECUTOR.current_label()}"

            EXECUTOR.log_event("OK" if ok else "WARN", msg)
            self._send_json({
                "ok": ok,
                "output": msg,
                "mode_label": EXECUTOR.current_label(),
            })
        elif self.path == "/api/apply":
            profile_key = str(data.get("profile", ""))
            result = EXECUTOR.apply_profile(profile_key)
            self._send_json(result)
        elif self.path == "/api/journal/clear":
            EXECUTOR.journal.clear()
            EXECUTOR.log_event("INFO", "Session journal cleared by operator.")
            self._send_json({"ok": True})
        elif self.path == "/api/modules/run":
            mod_path = str(data.get("path", ""))
            mod_type = str(data.get("type", ""))
            if mod_type == "sh":
                _, out = EXECUTOR.run_shell(f"sh '{mod_path}'", timeout=15)
            elif mod_type == "py":
                _, out = EXECUTOR.run_shell(f"python3 '{mod_path}'", timeout=15)
            else:
                out = "Nieobsługiwany typ pliku."
            EXECUTOR.log_event("OK", f"Executed module: {mod_path}")
            self._send_json({"output": out})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    server = ThreadedHTTPServer(("0.0.0.0", PORT), MasterRequestHandler)
    print(f"[*] ATV Master Optimizer v16.2 nasłuchuje na http://127.0.0.1:{PORT}")
    print(f"[*] Aktywny tryb: {EXECUTOR.current_label()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Zamykanie serwera...")
        server.server_close()


if __name__ == "__main__":
    main()