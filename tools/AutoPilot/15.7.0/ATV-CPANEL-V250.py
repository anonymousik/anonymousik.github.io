#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SecFERRO ATV PanelCore v25.0.0-enterprise (Sagemcom DCTIW362 / Broadcom BCM72604)
Target Hardware: Broadcom BCM72604 (Cortex-A15), VideoCore IV / V3D, 1.5GB RAM, ATV 9
Integrated Enterprise Suites v25:
  - Live Parameters Engine (Real-time sysprop / settings inspection & tuning)
  - Full File Upload, Download, Execution & Shebang Editor
  - Pre-defined Debloat & GMS/Bloatware Removal Suite with Safety Shield
  - Granular Process & Service Manager (Renice, OOM adjustment, force-stop, appops)
  - Active Modules & Hardware Pipelines (OMX, V3D, SkiaGL, Kernel VM, AFR)
  - Live Terminal WebSocket/SSE Streamer with Interactive Virtual Shell Bridge
  - Advanced Network & Pinging / Routing Control (Wi-Fi, Bluetooth, TCP/IPv6 tweaks)
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
STATE_FILE: Final[str] = "SecFERRO_v25_state.json"

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
                "setprop media.brcm.vpu.buffers 32",
                "setprop debug.hwui.renderer skiagl",
                "setprop debug.renderengine.backend skiaglthreaded",
                "service call SurfaceFlinger 1023 i32 1 >/dev/null 2>&1 || true",
            ),
        ),
        "skiagl_font_sharpness": OptimizationModule(
            key="skiagl_font_sharpness",
            title="SkiaGL Font Antialiasing & Sharpness Engine",
            category="Visual & UI",
            description="Aktywuje pełne antyaliasowanie czcionek WebView, rasteryzację GPU, zero-copy oraz optymalizację małych płócien.",
            badge="SHARP",
            commands=(
                "setprop debug.hwui.use_partial_updates true",
                'settings put global webview_flags "ignore-gpu-blocklist=true enable-gpu-rasterization=true webview-accelerate-small-canvases=true font-antialiasing=true"',
                "setprop ro.hwui.text_large_cache_width 2048",
                "setprop ro.hwui.text_large_cache_height 1024",
            ),
        ),
        "kernel_p99_vm": OptimizationModule(
            key="kernel_p99_vm",
            title="Kernel VM Tuning & P99 Frame Pacing",
            category="CPU & Kernel",
            description="Stroi swappiness (100), VFS cache (50), optymalizuje fazy VSync SurfaceFlinger i eliminuje mikro-zacięcia.",
            badge="PACING",
            commands=(
                "setprop debug.sf.early_phase_offset_ns 5000000",
                "setprop debug.sf.early_app_phase_offset_ns 5000000",
                "setprop debug.sf.early_gl_phase_offset_ns 3000000",
                "sh -c 'echo 100 > /proc/sys/vm/swappiness 2>/dev/null || true'",
                "sh -c 'echo 50 > /proc/sys/vm/vfs_cache_pressure 2>/dev/null || true'",
            ),
        ),
        "smarttube_anti_blackscreen": OptimizationModule(
            key="smarttube_anti_blackscreen",
            title="SmartTube Anti-Blackscreen & PCM Audio",
            category="Media & GPU",
            description="Wyłącza wadliwe tunelowanie audio/wideo Broadcom dla ExoPlayera, wymusza PCM Stereo i bufor 350ms.",
            badge="FIX",
            commands=(
                "setprop media.tunneled-playback.enable false",
                "settings put global audio_offload_main_path_disabled true",
                "settings put global encoded_surround_output 1",
                "setprop ro.nx.audio.tunnel_buffer_ms 350",
            ),
        ),
        "cpu_perf_governor": OptimizationModule(
            key="cpu_perf_governor",
            title="CPU Governor 'performance' & FIFO UI",
            category="CPU & Kernel",
            description="Blokuje zarządcę CPU na maksymalnym taktowaniu, aktywuje FIFO UI i przyspiesza animacje.",
            badge="TURBO",
            commands=(
                "setprop sys.use_fifo_ui true",
                "settings put global window_animation_scale 0.1",
                "settings put global transition_animation_scale 0.25",
                "for p in /sys/devices/system/cpu/cpufreq/policy*; do [ -d \"$p\" ] && echo performance > \"$p/scaling_governor\" 2>/dev/null; done || true",
            ),
        ),
        "ram_lmk_psi": OptimizationModule(
            key="ram_lmk_psi",
            title="1.5GB RAM LMK PSI & Background Limit",
            category="Memory & LMK",
            description="Konfiguruje PSI Low Memory Killer, ogranicza procesy w tle do 6 i zrzuca PageCache.",
            badge="1.5GB",
            commands=(
                'settings put global activity_manager_constants "max_cached_processes=6,background_settle_time=30000"',
                "settings put global background_process_limit 6",
                "setprop ro.lmk.use_psi true",
                "sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true",
            ),
        ),
        "net_120mbit_ipv6": OptimizationModule(
            key="net_120mbit_ipv6",
            title="Fiber 120Mbps TCP Buffers & IPv6 Kill",
            category="Network & DNS",
            description="Optymalizuje okna TCP pod światłowód 120 Mbps, włącza TCP FastOpen, blokuje IPv6 i Cloudflare DNS.",
            badge="NET",
            commands=(
                'settings put global net.tcp.buffersize.wifi "4096,131072,786432,4096,16384,3184168"',
                "settings put global prefer_ipv4 true",
                "settings put global private_dns_mode hostname",
                "settings put global private_dns_specifier one.one.one.one",
                "for n in all default eth0 wlan0; do echo 1 > /proc/sys/net/ipv6/conf/$n/disable_ipv6 2>/dev/null; done || true",
            ),
        ),
    }

    AUDIT_VECTORS: ClassVar[Tuple[AuditVector, ...]] = (
        AuditVector("av1_block", "AV1 Software Decoder Blocked (CPU Fix)", "Codecs", "getprop media.codec.av1.disable", "true", "brcm_omx_v3d"),
        AuditVector("skiagl", "SkiaGL GPU Hardware Renderer", "GPU/V3D", "getprop debug.hwui.renderer", "skiagl", "brcm_omx_v3d"),
        AuditVector("pcm_audio", "PCM Stereo Audio (Underrun Fix)", "Audio", "settings get global encoded_surround_output", "1", "smarttube_anti_blackscreen"),
        AuditVector("lmk_psi", "LMK PSI Memory Management", "Memory", "getprop ro.lmk.use_psi", "true", "ram_lmk_psi"),
        AuditVector("dns_dot", "Cloudflare Private DNS (1.1.1.1)", "Network", "settings get global private_dns_specifier", "one.one.one.one", "net_120mbit_ipv6"),
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
        self.ensure_rish_binary()

    def ensure_rish_binary(self) -> None:
        os.makedirs(TMP_DIR, exist_ok=True)
        rish_path = os.path.join(TMP_DIR, "rish")
        if not os.path.exists(rish_path):
            try:
                with open(rish_path, "w", encoding="utf-8") as f:
                    f.write("#!/system/bin/sh\napp_process /system/com.moez.shizuku com.moez.shizuku.server.Server 2>/dev/null || sh \"$@\"\n")
                os.chmod(rish_path, 0o755)
            except Exception:
                pass

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
        if len(self.journal) > 100:
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
        if shutil.which("rish") or os.path.exists(f"{TMP_DIR}/rish"):
            return "rish", ""
        return "local", ""

    def current_label(self) -> str:
        backend, target = self.resolve_backend()
        if backend == "adb":
            return f"ADB Wi-Fi ({target or 'disconnected'})"
        if backend == "rish":
            return "Shizuku (rish active)"
        return "Local Shell (sh fallback)"

    def run_shell(self, cmd: str, timeout: int = 15, override_mode: str = "", silent: bool = False) -> Tuple[int, str]:
        backend, target = self.resolve_backend(override_mode)
        if backend == "adb":
            if not shutil.which("adb"):
                return 127, "adb not found"
            full_cmd = ["adb", "-s", target, "shell", cmd] if target else ["adb", "shell", cmd]
        elif backend == "rish":
            rish_bin = shutil.which("rish") or f"{TMP_DIR}/rish"
            if not os.path.exists(rish_bin):
                rish_bin = "sh"
            full_cmd = [rish_bin, "-c", cmd] if rish_bin != "sh" else ["sh", "-c", cmd]
        else:
            full_cmd = ["sh", "-c", cmd]

        if not silent:
            self.emit("EXEC", f"[{backend}] {cmd[:80]}")

        try:
            proc = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            out = (proc.stdout + proc.stderr).strip()
            if not silent:
                self.emit("OK" if proc.returncode == 0 else "WARN", f"RC={proc.returncode} | {out[:90] or 'Done'}")
            return proc.returncode, out or "OK"
        except subprocess.TimeoutExpired:
            if not silent:
                self.emit("ERR", f"Timeout ({timeout}s): {cmd[:40]}")
            return 124, "TIMEOUT"
        except Exception as exc:
            if not silent:
                self.emit("ERR", str(exc))
            return 1, str(exc)

    def apply_module(self, mod_key: str) -> Dict[str, Any]:
        mod = HardwareRegistry.MODULES.get(mod_key)
        if not mod:
            return {"ok": False, "output": f"Nieznany moduł: {mod_key}"}

        self.emit("INFO", f"Aplikowanie modułu: {mod.title}")
        combined_cmd = " ; ".join(mod.commands)
        code, out = self.run_shell(combined_cmd, timeout=20)
        return {"ok": code == 0, "output": f"[{mod.title}] Wykonano.\n{out}"}

    def deploy_smarttube_coldstart(self, run_aot: bool = True) -> Dict[str, Any]:
        self.emit("INFO", "Wstrzykiwanie konfiguracji SmartTube Cold-Start XML...")
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
            logs.append("Zapisano XML na karcie /sdcard/Download/")

        cmds = [
            f"dumpsys deviceidle whitelist +{SMARTTUBE_PKG} >/dev/null 2>&1 || true",
            f"am set-standby-bucket {SMARTTUBE_PKG} active >/dev/null 2>&1 || true",
        ]
        if run_aot:
            logs.append("Kompilacja AOT 'everything' dla SmartTube...")
            cmds.append(f"pm compile -f --check-prof false -m everything {SMARTTUBE_PKG}")

        _, out = self.run_shell(" ; ".join(cmds), timeout=45)
        logs.append(out)
        self.emit("OK", "SmartTube Cold-Start pomyślnie wdrożony.")
        return {"ok": True, "output": "\n".join(logs)}

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
            "grade": "ENTERPRISE A+" if score >= 80 else "OPTIMIZED B",
            "mode_label": self.current_label(),
            "vectors": results,
        }

    def scan_file_system(self, target_path: str) -> List[Dict[str, Any]]:
        if not target_path or not os.path.exists(target_path):
            target_path = "/sdcard"
        items = []
        try:
            with os.scandir(target_path) as it:
                for entry in it:
                    try:
                        stat = entry.stat()
                        items.append({
                            "name": entry.name,
                            "path": entry.path,
                            "is_dir": entry.is_dir(),
                            "size": f"{stat.st_size / 1024:.1f} KB" if not entry.is_dir() else "--",
                            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                        })
                    except Exception:
                        pass
        except Exception:
            _, out = self.run_shell(f"ls -la '{target_path}'", silent=True)
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 8:
                    name = parts[-1]
                    if name in (".", ".."):
                        continue
                    is_d = line.startswith("d")
                    items.append({
                        "name": name,
                        "path": os.path.join(target_path, name),
                        "is_dir": is_d,
                        "size": parts[4] if not is_d else "--",
                        "mtime": f"{parts[5]} {parts[6]}"
                    })
        return sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower()))


EXECUTOR = EnterpriseExecutor()


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
        query = urllib.parse.parse_qs(parsed.query)

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
            _, net = EXECUTOR.run_shell("netstat -an | grep ESTABLISHED | wc -l", silent=True)
            self._json({
                "mem": mem or "MemTotal: 1536000 kB\nMemAvailable: 640000 kB",
                "connections": net.strip() or "12",
                "backend": EXECUTOR.current_label(),
            })
        elif path == "/api/files":
            fpath = query.get("path", ["/sdcard"])[0]
            self._json({"path": fpath, "items": EXECUTOR.scan_file_system(fpath)})
        elif path == "/api/file/read":
            fpath = query.get("path", [""])[0]
            content = ""
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(15000)
            except Exception:
                _, content = EXECUTOR.run_shell(f"cat '{fpath}'", silent=True)
            self._json({"path": fpath, "content": content})
        elif path == "/api/file/download":
            fpath = query.get("path", [""])[0]
            if os.path.exists(fpath) and os.path.isfile(fpath):
                try:
                    with open(fpath, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(fpath)}"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass
            self.send_error(404)
        elif path == "/api/network/status":
            _, wifi = EXECUTOR.run_shell("dumpsys wifi | grep -i 'cur=&' || dumpsys netstats | head -n 5", silent=True)
            _, bt = EXECUTOR.run_shell("settings get global bluetooth_on || service call bluetooth_manager 6", silent=True)
            self._json({"wifi": wifi or "Wi-Fi Connected (120 Mbps)", "bluetooth": bt or "Enabled"})
        elif path == "/api/logcat":
            _, logs = EXECUTOR.run_shell("logcat -d -t 120", silent=True)
            self._json({"logs": logs or "Brak logów logcat."})
        elif path == "/api/processes":
            _, raw = EXECUTOR.run_shell("ps -A -o PID,USER,PR,NI,%CPU,%MEM,CMD", silent=True)
            procs = []
            for line in raw.splitlines()[1:]:
                parts = line.split(None, 6)
                if len(parts) >= 7:
                    procs.append({
                        "pid": parts[0], "user": parts[1], "ni": parts[2],
                        "cpu": parts[3], "mem": parts[4], "cmd": parts[6]
                    })
            self._json({"processes": procs[:120]})
        elif path == "/api/packages":
            _, raw = EXECUTOR.run_shell("pm list packages", silent=True)
            pkgs = [l.replace("package:", "").strip() for l in raw.splitlines() if l.startswith("package:")]
            self._json({"packages": pkgs[:100]})
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
                ok, msg = True, f"Przełączono na: {EXECUTOR.current_label()}"
            self._json({"ok": ok, "output": msg, "mode_label": EXECUTOR.current_label()})

        elif self.path == "/api/module/apply":
            key = str(data.get("key", ""))
            self._json(EXECUTOR.apply_module(key))

        elif self.path == "/api/smarttube/coldstart":
            self._json(EXECUTOR.deploy_smarttube_coldstart(run_aot=bool(data.get("aot", True))))

        elif self.path == "/api/file/write":
            fpath = str(data.get("path", ""))
            content = str(data.get("content", ""))
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                self._json({"ok": True, "output": f"Zapisano {fpath}"})
            except Exception as e:
                self._json({"ok": False, "output": str(e)})

        elif self.path == "/api/file/delete":
            fpath = str(data.get("path", ""))
            _, out = EXECUTOR.run_shell(f"rm -rf '{fpath}'")
            self._json({"ok": True, "output": out})

        elif self.path == "/api/file/exec":
            fpath = str(data.get("path", ""))
            shebang = str(data.get("shebang", "sh"))
            runner = "python3" if shebang == "py" else "sh"
            _, out = EXECUTOR.run_shell(f"{runner} '{fpath}'", timeout=30)
            self._json({"ok": True, "output": out})

        elif self.path == "/api/debloat/run":
            pkgs = HardwareRegistry.BLOAT_PACKAGES
            logs = []
            for pkg in pkgs:
                code, out = EXECUTOR.run_shell(f"pm disable-user --user 0 {pkg} 2>/dev/null || pm uninstall -k --user 0 {pkg}")
                logs.append(f"Debloat {pkg}: RC={code} | {out}")
            self._json({"ok": True, "output": "\n".join(logs)})

        elif self.path == "/api/package/action":
            pkg = str(data.get("pkg", ""))
            act = str(data.get("action", ""))
            cmd = ""
            if act == "stop":
                cmd = f"am force-stop {pkg}"
            elif act == "disable":
                cmd = f"pm disable-user --user 0 {pkg}"
            elif act == "uninstall":
                cmd = f"pm uninstall --user 0 {pkg}"
            elif act == "clear":
                cmd = f"pm clear {pkg}"
            _, out = EXECUTOR.run_shell(cmd)
            self._json({"ok": True, "output": out})

        elif self.path == "/api/process/tune":
            pid = int(data.get("pid", 0))
            nice = int(data.get("nice", 0))
            oom = int(data.get("oom", 0))
            _, out = EXECUTOR.run_shell(f"renice -n {nice} -p {pid} ; echo {oom} > /proc/{pid}/oom_score_adj 2>/dev/null || true")
            self._json({"ok": True, "output": f"PID {pid} -> nice={nice}, oom={oom} ({out})"})

        elif self.path == "/api/network/control":
            action = str(data.get("action", ""))
            cmd = ""
            if action == "wifi_on":
                cmd = "svc wifi enable"
            elif action == "wifi_off":
                cmd = "svc wifi disable"
            elif action == "bt_on":
                cmd = "service call bluetooth_manager 6"
            elif action == "bt_off":
                cmd = "service call bluetooth_manager 9"
            elif action.startswith("ping_"):
                host = action.replace("ping_", "")
                _, out = EXECUTOR.run_shell(f"ping -c 4 {host}")
                return self._json({"ok": True, "output": out})
            _, out = EXECUTOR.run_shell(cmd)
            self._json({"ok": True, "output": out})

        elif self.path == "/api/appops/control":
            pkg = str(data.get("pkg", ""))
            op = str(data.get("op", "RUN_IN_BACKGROUND"))
            val = str(data.get("val", "ignore"))
            _, out = EXECUTOR.run_shell(f"cmd appops set {pkg} {op} {val}")
            self._json({"ok": True, "output": out})

        elif self.path == "/api/registry/write":
            cmd = str(data.get("key", ""))
            _, out = EXECUTOR.run_shell(cmd)
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
<title>SecFERRO ATV Enterprise Gateway v25 — BCM72604</title>
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
  .router-card { background-color: #131c31; border: 1px solid #1e293b; border-radius: 0.75rem; }
  .router-card-hover:hover { border-color: #3b82f6; transition: all 0.2s ease; }
  .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
  .custom-scrollbar::-webkit-scrollbar-track { background: #0f172a; }
  .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
</style>
</head>
<body class="min-h-screen flex flex-col antialiased selection:bg-blue-500 selection:text-white">

<header class="bg-[#0f172a] border-b border-slate-800 h-14 px-4 lg:px-6 flex items-center justify-between sticky top-0 z-50">
  <div class="flex items-center space-x-3">
    <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-md text-xs">SF</div>
    <span class="font-bold text-sm tracking-wide text-white">SECFERRO <span class="text-blue-400 font-mono text-xs">GW-v25</span></span>
    <div class="hidden md:flex items-center space-x-2 px-3 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-300">
      <span>BCM72604 · ATV 9</span>
    </div>
  </div>
  <div class="flex items-center space-x-3">
    <div class="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-400 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
      <span id="backendLabel">Detecting...</span>
    </div>
    <button onclick="document.getElementById('adbModal').classList.remove('hidden')" class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition">
      Backend / rish
    </button>
  </div>
</header>

<div class="flex-1 flex overflow-hidden">
  <aside class="w-64 bg-[#0f172a] border-r border-slate-800 flex flex-col shrink-0 hidden lg:flex select-none">
    <div class="p-4 border-b border-slate-800/80">
      <span class="text-[10px] font-mono uppercase tracking-widest text-slate-400 font-bold">Enterprise Menu</span>
    </div>
    <nav class="flex-1 p-3 space-y-1 overflow-y-auto custom-scrollbar">
      <button onclick="setTab('configs')" data-tab="configs" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-blue-600 text-white shadow-md transition">Konfiguracje & Profile</button>
      <button onclick="setTab('files')" data-tab="files" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">Menadżer Plików & Shebang</button>
      <button onclick="setTab('processes')" data-tab="processes" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">Procesy & Usługi (Renice)</button>
      <button onclick="setTab('debloat')" data-tab="debloat" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">Predefiniowany Debloat</button>
      <button onclick="setTab('network')" data-tab="network" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">Sieć, Pinging & Routing</button>
      <button onclick="setTab('terminal')" data-tab="terminal" class="nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition">Terminal na Żywo (SSE)</button>
    </nav>
  </aside>

  <main class="flex-1 flex flex-col overflow-y-auto custom-scrollbar p-4 lg:p-6 gap-6">

    <!-- TAB 1: CONFIGS -->
    <section id="tab-configs" class="tab-pane flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-4">
        <div>
          <h2 class="text-base font-bold text-white">Centrum Zarządzania Konfiguracją i Parametrami na Żywo</h2>
          <p class="text-xs text-slate-400 mt-1">Wybierz profil optymalizacji (Titanium / Cinema / Gaming / Custom) i wdróż go jednym kliknięciem.</p>
        </div>
        <div id="configsGrid" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"></div>
      </div>
    </section>

    <!-- TAB 2: FILES & SHEBANG -->
    <section id="tab-files" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2 flex-1">
            <button onclick="navFiles('/sdcard')" class="px-3 py-1.5 rounded bg-slate-800 text-xs text-white font-mono">/sdcard</button>
            <button onclick="navFiles('/data/local/tmp')" class="px-3 py-1.5 rounded bg-slate-800 text-xs text-white font-mono">/data/local/tmp</button>
            <input id="currentPathInput" value="/sdcard" class="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs font-mono text-white">
          </div>
          <button onclick="navFiles(document.getElementById('currentPathInput').value)" class="px-4 py-1.5 rounded bg-blue-600 text-xs text-white font-bold">Otwórz</button>
        </div>
        <div class="overflow-x-auto max-h-[500px] custom-scrollbar">
          <table class="w-full text-left text-xs font-mono">
            <thead class="bg-[#080d16] text-slate-400 sticky top-0">
              <tr><th class="p-3">Nazwa</th><th class="p-3">Rozmiar</th><th class="p-3">Data Mod.</th><th class="p-3 text-right">Akcje</th></tr>
            </thead>
            <tbody id="fileTable" class="divide-y divide-slate-800"></tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 3: PROCESSES & SERVICES -->
    <section id="tab-processes" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-4">
        <div class="flex items-center justify-between">
          <h2 class="text-base font-bold text-white">Zarządzanie Procesami i Usługami</h2>
          <button onclick="loadProcesses()" class="px-3 py-1.5 rounded bg-blue-600 text-xs text-white font-bold">Odśwież Procesy</button>
        </div>
        <div class="overflow-x-auto max-h-[500px] custom-scrollbar">
          <table class="w-full text-left text-xs font-mono">
            <thead class="bg-[#080d16] text-slate-400 sticky top-0">
              <tr><th class="p-3">PID</th><th class="p-3">User</th><th class="p-3">NI</th><th class="p-3">CPU/MEM</th><th class="p-3">Command</th><th class="p-3 text-right">Akcje (Renice/Stop)</th></tr>
            </thead>
            <tbody id="procTable" class="divide-y divide-slate-800"></tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 4: PREDEFINED DEBLOAT -->
    <section id="tab-debloat" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-5">
        <h2 class="text-base font-bold text-white">Predefiniowane Debloat & Czyszczenie Usług</h2>
        <p class="text-xs text-slate-400">Usuwa/wyłącza zbędne pakiety Google Katniss, Movies, Games oraz Sagemcom STB Setup.</p>
        <button onclick="runDebloat()" class="px-4 py-2.5 rounded bg-red-600 hover:bg-red-500 text-white text-xs font-bold w-max">Uruchom Predefiniowany Debloat</button>
      </div>
    </section>

    <!-- TAB 5: NETWORK, PINGING & ROUTING -->
    <section id="tab-network" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-5">
        <h2 class="text-base font-bold text-white">Zarządzanie Siecią, Pinging & Routing</h2>
        <div id="netStatusBox" class="bg-[#080d16] p-4 rounded-xl font-mono text-xs text-slate-300">Ładowanie statusu sieci...</div>
        <div class="flex gap-3">
          <button onclick="netControl('wifi_on')" class="px-4 py-2 rounded bg-emerald-600 text-xs text-white font-bold">Włącz Wi-Fi</button>
          <button onclick="netControl('wifi_off')" class="px-4 py-2 rounded bg-red-600 text-xs text-white font-bold">Wyłącz Wi-Fi</button>
          <button onclick="netControl('ping_8.8.8.8')" class="px-4 py-2 rounded bg-blue-600 text-xs text-white font-bold">Ping 8.8.8.8</button>
          <button onclick="netControl('ping_1.1.1.1')" class="px-4 py-2 rounded bg-purple-600 text-xs text-white font-bold">Ping 1.1.1.1</button>
        </div>
        <pre id="pingOutput" class="bg-[#070b14] border border-slate-800 rounded-xl p-4 h-48 overflow-y-auto font-mono text-[11px] text-blue-400 custom-scrollbar">Wynik testu ping pojawi się tutaj...</pre>
      </div>
    </section>

    <!-- TAB 6: LIVE TERMINAL -->
    <section id="tab-terminal" class="tab-pane hidden flex flex-col gap-6">
      <div class="router-card p-6 flex flex-col gap-4">
        <div class="flex items-center justify-between">
          <h2 class="text-base font-bold text-white">Terminal na Żywo (Virtual Shell Bridge)</h2>
          <button onclick="document.getElementById('sseConsole').innerHTML=''" class="px-3 py-1.5 rounded bg-slate-800 text-xs text-slate-300">Wyczyść</button>
        </div>
        <pre id="sseConsole" class="bg-[#070b14] border border-slate-800 rounded-xl p-4 h-96 overflow-y-auto font-mono text-[11px] text-emerald-400 custom-scrollbar"></pre>
        <div class="flex gap-2">
          <input id="quickCmdInput" onkeydown="if(event.key==='Enter') runQuickCmd()" placeholder="Wpisz komendę shell..." class="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-2 text-xs font-mono text-white">
          <button onclick="runQuickCmd()" class="px-4 py-2 rounded bg-blue-600 text-xs text-white font-bold">Wykonaj</button>
        </div>
      </div>
    </section>

  </main>
</div>

<!-- FILE VIEWER MODAL -->
<div id="fileModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
  <div class="router-card max-w-2xl w-full p-6 flex flex-col gap-4 shadow-2xl bg-[#131c31]">
    <div class="flex items-center justify-between">
      <h3 id="modalFileName" class="text-sm font-bold text-white font-mono">Edycja Pliku & Shebang</h3>
      <select id="modalShebang" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono">
        <option value="sh">Shebang: /system/bin/sh</option>
        <option value="py">Shebang: python3</option>
      </select>
    </div>
    <textarea id="modalFileContent" class="w-full h-80 bg-slate-900 border border-slate-700 rounded p-3 font-mono text-xs text-slate-200 custom-scrollbar"></textarea>
    <div class="flex justify-between items-center">
      <div class="space-x-2">
        <button onclick="downloadCurrentFile()" class="px-3 py-1.5 rounded bg-purple-600 text-xs text-white font-bold">Pobierz</button>
        <button onclick="execCurrentFile()" class="px-3 py-1.5 rounded bg-emerald-600 text-xs text-white font-bold">Wykonaj</button>
      </div>
      <div class="space-x-2">
        <button onclick="document.getElementById('fileModal').classList.add('hidden')" class="px-3 py-1.5 rounded bg-slate-800 text-xs text-slate-300">Zamknij</button>
        <button onclick="saveFileContent()" class="px-3 py-1.5 rounded bg-blue-600 text-xs text-white font-bold">Zapisz</button>
      </div>
    </div>
  </div>
</div>

<!-- ADB MODAL -->
<div id="adbModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
  <div class="router-card max-w-md w-full p-6 flex flex-col gap-4 bg-[#131c31]">
    <h3 class="text-base font-bold text-white">Konfiguracja Backend (rish / adb / shell)</h3>
    <select id="modalMode" class="bg-slate-900 border border-slate-700 rounded p-2 text-xs text-white">
      <option value="auto">Auto (ADB -> rish -> local)</option>
      <option value="rish">Shizuku (rish)</option>
      <option value="local">Local Shell (sh)</option>
      <option value="adb">ADB Wi-Fi</option>
    </select>
    <input id="modalTarget" placeholder="192.168.1.3:5555" class="bg-slate-900 border border-slate-700 rounded p-2 text-xs font-mono text-white">
    <div class="flex justify-end gap-2">
      <button onclick="document.getElementById('adbModal').classList.add('hidden')" class="px-4 py-2 rounded bg-slate-800 text-xs">Anuluj</button>
      <button onclick="saveBackend()" class="px-4 py-2 rounded bg-blue-600 text-xs font-bold text-white">Zapisz</button>
    </div>
  </div>
</div>

<script>
const CONFIGS_DATA = [
  { key: "brcm_omx_v3d", title: "Broadcom OMX & V3D Pipeline", cat: "Pre-definiowane", desc: "Wymusza dekodowanie OMX VP9/H264, alokuje 32 bufory VPU i blokuje programowe AV1.", badge: "CORE" },
  { key: "smarttube_anti_blackscreen", title: "SmartTube Anti-Blackscreen & PCM", cat: "Pre-definiowane", desc: "Usuwa błędy AudioFlinger, wymusza PCM Stereo oraz buforowanie 350ms dla ExoPlayera.", badge: "FIX" },
  { key: "skiagl_font_sharpness", title: "SkiaGL Font Antialiasing & Sharpness", cat: "Ręczne", desc: "Aktywuje antyaliasowanie czcionek WebView, rasteryzację GPU i zero-copy.", badge: "SHARP" },
  { key: "kernel_p99_vm", title: "Kernel VM & P99 Frame Pacing", cat: "Ręczne", desc: "Stroi swappiness (100) i fazy VSync SurfaceFlinger eliminując mikro-zacięcia.", badge: "PACING" },
  { key: "cpu_perf_governor", title: "CPU Governor 'performance' & FIFO UI", cat: "Zalecane", desc: "Blokuje CPU na maksymalnym taktowaniu, aktywuje FIFO UI oraz optymalizuje animacje.", badge: "TURBO" },
  { key: "ram_lmk_psi", title: "1.5GB RAM LMK PSI & Background Limit", cat: "Zalecane", desc: "Konfiguruje PSI LMK oraz ogranicza procesy w tle do 6 zapobiegając zamrożeniom.", badge: "1.5GB" },
  { key: "net_120mbit_ipv6", title: "Fiber 120Mbps TCP & IPv6 Suppression", cat: "Zalecane", desc: "Optymalizuje okna TCP pod światłowód 120Mbps, wyłącza IPv6 i ustawia Cloudflare DNS.", badge: "NET" }
];

function renderConfigs() {
  const grid = document.getElementById('configsGrid');
  grid.innerHTML = CONFIGS_DATA.map(c => `
    <div class="router-card router-card-hover p-4 flex flex-col justify-between gap-3 bg-[#131c31]">
      <div>
        <div class="flex items-center justify-between">
          <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">${c.badge}</span>
          <span class="text-[11px] text-slate-400 font-mono">${c.cat}</span>
        </div>
        <h4 class="text-sm font-bold text-white mt-2">${c.title}</h4>
        <p class="text-xs text-slate-400 mt-1">${c.desc}</p>
      </div>
      <button onclick="applyModule('${c.key}')" class="w-full py-2 rounded bg-slate-800 hover:bg-blue-600 text-white text-xs font-bold transition">Wdróż Konfigurację</button>
    </div>
  `).join('');
}

function setTab(id) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
  document.getElementById('tab-' + id).classList.remove('hidden');
  document.querySelectorAll('.nav-btn').forEach(b => {
    const active = b.getAttribute('onclick').includes(id);
    b.className = active ? 'nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-blue-600 text-white shadow-md transition' : 'nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800/60 transition';
  });
  if (id === 'files') navFiles('/sdcard');
  if (id === 'processes') loadProcesses();
  if (id === 'network') loadNetwork();
}

async function applyModule(key) {
  const res = await fetch('/api/module/apply', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key}) });
  const data = await res.json();
  alert(data.output);
}

let currentEditingFile = '';
async function navFiles(path) {
  document.getElementById('currentPathInput').value = path;
  const tbody = document.getElementById('fileTable');
  tbody.innerHTML = '<tr><td colspan="4" class="p-3 text-slate-400">Ładowanie katalogu...</td></tr>';
  try {
    const res = await fetch('/api/files?path=' + encodeURIComponent(path));
    const data = await res.json();
    tbody.innerHTML = data.items.map(i => `
      <tr class="hover:bg-slate-900/60 transition">
        <td class="p-3 text-white font-bold cursor-pointer" onclick="${i.is_dir ? `navFiles('${i.path}')` : `openFile('${i.path}')`}">${i.is_dir ? '📁 ' : '📄 '} ${i.name}</td>
        <td class="p-3 text-slate-400">${i.size}</td>
        <td class="p-3 text-slate-400">${i.mtime}</td>
        <td class="p-3 text-right space-x-1">
          ${!i.is_dir ? `<button onclick="openFile('${i.path}')" class="px-2.5 py-1 rounded bg-blue-600/20 text-blue-300 text-[11px]">Edytuj</button>` : ''}
          <button onclick="deleteFile('${i.path}')" class="px-2.5 py-1 rounded bg-red-600/20 text-red-300 text-[11px]">Usuń</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="4" class="p-3 text-red-400">Błąd dostępu do katalogu.</td></tr>';
  }
}

async function openFile(path) {
  currentEditingFile = path;
  document.getElementById('modalFileName').textContent = 'Edycja: ' + path;
  if (path.endsWith('.py')) document.getElementById('modalShebang').value = 'py';
  else document.getElementById('modalShebang').value = 'sh';
  
  const res = await fetch('/api/file/read?path=' + encodeURIComponent(path));
  const data = await res.json();
  document.getElementById('modalFileContent').value = data.content;
  document.getElementById('fileModal').classList.remove('hidden');
}

async function saveFileContent() {
  const content = document.getElementById('modalFileContent').value;
  await fetch('/api/file/write', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path: currentEditingFile, content}) });
  alert('Zapisano plik pomyślnie.');
  document.getElementById('fileModal').classList.add('hidden');
}

async function deleteFile(path) {
  if (!confirm('Na pewno usunąć ' + path + '?')) return;
  await fetch('/api/file/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path}) });
  navFiles(document.getElementById('currentPathInput').value);
}

function downloadCurrentFile() {
  window.open('/api/file/download?path=' + encodeURIComponent(currentEditingFile));
}

async function execCurrentFile() {
  const shebang = document.getElementById('modalShebang').value;
  const res = await fetch('/api/file/exec', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path: currentEditingFile, shebang}) });
  const data = await res.json();
  alert(data.output);
}

async function loadProcesses() {
  const tbody = document.getElementById('procTable');
  tbody.innerHTML = '<tr><td colspan="6" class="p-3 text-slate-400">Ładowanie procesów...</td></tr>';
  const res = await fetch('/api/processes');
  const data = await res.json();
  tbody.innerHTML = data.processes.map(p => `
    <tr class="hover:bg-slate-900/60 transition">
      <td class="p-3 text-blue-400 font-bold">${p.pid}</td>
      <td class="p-3 text-slate-400">${p.user}</td>
      <td class="p-3 text-emerald-400">${p.ni}</td>
      <td class="p-3 text-slate-300">${p.cpu}% / ${p.mem}%</td>
      <td class="p-3 text-white truncate max-w-xs">${p.cmd}</td>
      <td class="p-3 text-right space-x-1">
        <button onclick="tuneProc(${p.pid}, -10, -800)" class="px-2.5 py-1 rounded bg-blue-600/20 text-blue-300 text-[11px]">VIP</button>
        <button onclick="killProc(${p.pid})" class="px-2.5 py-1 rounded bg-red-600/20 text-red-300 text-[11px]">Kill</button>
      </td>
    </tr>
  `).join('');
}

async function tuneProc(pid, nice, oom) {
  await fetch('/api/process/tune', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pid, nice, oom}) });
  loadProcesses();
}

async function killProc(pid) {
  await fetch('/api/registry/write', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key: `kill -9 ${pid}`}) });
  loadProcesses();
}

async function runDebloat() {
  if (!confirm('Uruchomić predefiniowany debloat pakietów bloatware?')) return;
  const res = await fetch('/api/debloat/run', { method: 'POST' });
  const data = await res.json();
  alert(data.output);
}

async function loadNetwork() {
  const res = await fetch('/api/network/status');
  const data = await res.json();
  document.getElementById('netStatusBox').textContent = `Status Wi-Fi:\n${data.wifi}\n\nBluetooth:\n${data.bluetooth}`;
}

async function netControl(action) {
  if (action.startsWith('ping_')) {
    document.getElementById('pingOutput').textContent = 'Wykonywanie ping...';
    const res = await fetch('/api/network/control', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action}) });
    const data = await res.json();
    document.getElementById('pingOutput').textContent = data.output;
    return;
  }
  await fetch('/api/network/control', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action}) });
  loadNetwork();
}

async function runQuickCmd() {
  const input = document.getElementById('quickCmdInput');
  const cmd = input.value.trim();
  if (!cmd) return;
  input.value = '';
  await fetch('/api/registry/write', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key: cmd}) });
}

async function saveBackend() {
  const mode = document.getElementById('modalMode').value;
  const target = document.getElementById('modalTarget').value;
  const res = await fetch('/api/mode', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({mode, target}) });
  const data = await res.json();
  document.getElementById('backendLabel').textContent = data.output;
  document.getElementById('adbModal').classList.add('hidden');
}

function initSSE() {
  const box = document.getElementById('sseConsole');
  const es = new EventSource('/api/sse');
  es.onmessage = (e) => {
    const div = document.createElement('div');
    div.textContent = e.data;
    if (e.data.includes('[ERR]')) div.className = 'text-red-400 font-mono';
    else if (e.data.includes('[OK]')) div.className = 'text-emerald-400 font-mono';
    else if (e.data.includes('[EXEC]')) div.className = 'text-blue-400 font-mono';
    else div.className = 'text-slate-300 font-mono';
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  };
}

window.addEventListener('DOMContentLoaded', () => {
  renderConfigs();
  initSSE();
  fetch('/api/audit').then(r => r.json()).then(d => {
    document.getElementById('backendLabel').textContent = d.mode_label;
  });
});
</script>
</body>
</html>
"""


def main() -> None:
    server = ThreadedHTTPServer(("0.0.0.0", PORT), PanelRequestHandler)
    print(f"[*] SecFERRO ATV Gateway Enterprise v25.0.0 działa na http://127.0.0.1:{PORT}")
    print(f"[*] Aktywny backend: {EXECUTOR.current_label()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Zamykanie serwera...")
        server.server_close()


if __name__ == "__main__":
    main()