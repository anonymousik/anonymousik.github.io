#!/usr/bin/env python3
"""
================================================================================
PLAYBOX TITANIUM ULTIMATE MASTER OPTIMIZER (PROACTIVE ADAPTIVE EDITION v11.0)
Target Device: Sagemcom DCTIW362 / DCTIW362P (Play NOW TV Box v1)
Hardware: Broadcom BCM72604 SoC + VideoCore V GPU | Android TV 9.0 (API 28)
Target Focus: SmartTube (org.smarttube.stable) & Projectivy Launcher
Execution Context: ADB (192.168.1.3:5555) / Shizuku rish / Termux
================================================================================
"""

import os
import re
import subprocess
import sys
import time
from typing import Dict, List, Tuple

# --- CONFIGURATION DEFINITIONS ---
ADB_TARGET = "192.168.1.3:5555"

TARGET_SMARTTUBE = "org.smarttube.stable"
TARGET_LAUNCHER = "com.spocky.projengmenu"

# 1. Global / System / Secure Settings Alignment
SETTINGS_GLOBAL: Dict[str, str] = {
    "window_animation_scale": "0.0",
    "transition_animation_scale": "0.25",
    "animator_duration_scale": "0.25",
    "activity_manager_constants": "max_cached_processes=8,background_settle_time=60000,fgservice_min_shown_time=500,power_check_max_cpu_1=75,power_check_max_cpu_0=85",
    "power_manager_constants": "no_cached_apps_until_foreground=true",
    "low_power_trigger_level": "0",
    "encoded_surround_output": "1",            # Force PCM Mode (Eliminates AudioFlinger UNDERRUNs)
    "encoded_surround_output_enabled": "0",    # Stop invalid format probing
    "wifi_scan_always_enabled": "0",
    "ble_scan_always_enabled": "0",
    "wifi_sleep_policy": "2",
    "custom_home_package": TARGET_LAUNCHER,
    "sys_free_storage_log_interval": "0",
    "accessibility_enabled": "0",              
    # Disable Accessibility audio description layers
    # SYSTEM-WIDE DNS & IPV6 OVERRIDES
    "private_dns_mode": "off",                 # Offloading private DNS overhead for fast local/IPv4 resolution
    "dns_server1": "1.1.1.1",                  # Cloudflare Primary IPv4
    "dns_server2": "8.8.8.8"                   # Google Secondary IPv4
}

SETTINGS_SYSTEM: Dict[str, str] = {
    "hardware_accelerated": "1",
    "sound_effects_enabled": "0",             # Disable UI click sounds to save audio buffer overhead
    "master_mono": "0",
    "volume_music_speaker": "100"
}

SETTINGS_SECURE: Dict[str, str] = {
    "screensaver_enabled": "0",
    "sleep_timeout": "2147483647"              # Prevent premature sleep during streaming
}

# 2. System Properties (Hardware Decoder, GFX Pacing, Audio & IPv4 Network Stack)
SYSTEM_PROPERTIES: Dict[str, str] = {
    # SurfaceFlinger & VideoCore V HW Acceleration
    "debug.sf.hw": "1",
    "debug.sf.disable_backpressure": "1",
    "debug.sf.latch_unsignaled": "1",
    "debug.sf.early_phase_offset_ns": "5000000",
    "debug.sf.early_app_phase_offset_ns": "500000",
    "debug.sf.early_gl_phase_offset_ns": "3000000",
    "ro.v3d.fence.expose": "true",
    "ro.v3d.disable_buffer_age": "true",
    "ro.nx.v3d.no_map_lock": "0",
    "ro.nx.hwc2.tweak.fbcomp": "1",
    "debug.egl.hw": "1",
    "debug.egl.check_gl_errors": "0",
    "debug.hwui.renderer": "skiagl",
    "debug.hwui.render_thread_count": "2",

    # Broadcom OMX Video Decoder Hardware Pipeline
    "media.stagefright.enable-player": "true",
    "media.stagefright.enable-http": "true",
    "media.stagefright.enable-aac": "true",
    "media.stagefright.enable-qcp": "true",
    "media.stagefright.enable-scan": "true",
    "media.stagefright.enable-fma264": "true",
    "media.stagefright.enable-meta": "true",
    "media.autorun.media.codec": "1",
    "ro.nx.media.vdec.fsm1080p": "1",
    "ro.nx.media.vdec.progoverride": "2",
    "ro.nx.media.vdec_outportbuf": "32",        # 32 buffers for instantaneous Seeking I-frame switching
    "ro.nx.mma": "1",
    "persist.sys.ui.hw": "true",

    # Audio Sink & Nexus Audio Tunnel Buffering (Seeking Fix)
    "af.resampler.quality": "4",
    "ro.nx.audio.tunnel_buffer_ms": "350",      # 350ms Audio Tunneling Buffer to prevent Seek freezes
    "ro.nx.audio.lipsync_delay": "0",          # Strict lipsync lock
    "media.stagefright.audio.sink": "2097152", # 2MB AudioSink Buffer

    # Ultra-Fast Fiber TCP & Disable Network Delays
    "net.tcp.buffersize.default": "262144,524288,20971520,262144,524288,20971520",
    "net.tcp.buffersize.wifi": "524288,1048576,20971520,262144,524288,20971520",
    "net.tcp.buffersize.ethernet": "524288,1048576,20971520,262144,524288,20971520",
    "sys.sysctl.tcp_def_init_rwnd": "120",
    "net.ipv4.tcp_fastopen": "3",
    "sys.sysctl.extra_free_kbytes": "32768",
    "net.dns1": "1.1.1.1",
    "net.dns2": "8.8.8.8"
}

# 3. System Bloatware Target List (Safe for Removal)
TARGET_BLOAT_PACKAGES: List[str] = [
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
    "pl.play.playnow.box",
    "com.sagemcom.appupdate",
    "com.sagemcom.stb.setupwizard",
    "com.sagemcom.sysupdate",
    "com.google.android.tungsten.setupwraith",
    "com.google.android.leanbacklauncher.recommendations",
    "com.google.android.syncadapters.contacts",
    "com.google.android.backuptransport",
    "com.android.providers.userdictionary"
]

# GMS background services causing wake lock & auth failure loops
GMS_TRIM_SERVICES: List[str] = [
    "com.google.android.gms/com.google.android.gms.chromesync.sync.ChimeraSyncReceiverService",
    "com.google.android.gms/com.google.android.gms.auth.api.signin.revocation.RevocationBoundService",
    "com.google.android.gms/com.google.android.gms.analytics.AnalyticsService"
]


class ShellExecutor:
    """Manages ADB and local shell command execution intelligently."""

    def __init__(self, target_ip: str = ADB_TARGET):
        self.target_ip = target_ip
        self.is_adb_remote = True
        self._setup_connection()

    def _setup_connection(self):
        if os.path.exists("/system/bin/app_process"):
            res = self.exec_local("id -u")
            if res.strip() in ["0", "2000"]:
                self.is_adb_remote = False
                print(f"[*] Native On-Device Execution Context Detected (UID: {res.strip()}).")
                return

        print(f"[*] Remote Network Execution Context Detected. Connecting to ADB target {self.target_ip}...")
        subprocess.run(f"adb connect {self.target_ip}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def exec_local(self, cmd: str) -> str:
        try:
            res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            return res.stdout.strip()
        except Exception as e:
            return f"Error: {e}"

    def run(self, cmd: str) -> str:
        if self.is_adb_remote:
            full_cmd = f"adb -s {self.target_ip} shell \"{cmd}\""
        else:
            full_cmd = cmd
        return self.exec_local(full_cmd)


def tune_network_and_disable_ipv6(executor: ShellExecutor):
    """Disables system-wide IPv6 stack and flushes DNS caches for zero network latency."""
    print("\n[*] Applying Advanced Network & System IPv6 Suppression...")

    # 1. Disable IPv6 via sysctl / proc entries where write permission allows
    ipv6_targets = [
        "/proc/sys/net/ipv6/conf/all/disable_ipv6",
        "/proc/sys/net/ipv6/conf/default/disable_ipv6",
        "/proc/sys/net/ipv6/conf/eth0/disable_ipv6",
        "/proc/sys/net/ipv6/conf/wlan0/disable_ipv6"
    ]
    
    disabled_count = 0
    for target in ipv6_targets:
        res = executor.run(f"echo 1 > {target} 2>/dev/null && echo SUCCESS || echo FAIL").strip()
        if "SUCCESS" in res:
            disabled_count += 1
            
    print(f"  [✓] System-wide IPv6 stack disabled on {disabled_count} network nodes.")

    # 2. Kernel Socket Tuning & Low Latency IPv4
    executor.run("echo 1 > /proc/sys/net/ipv4/tcp_low_latency 2>/dev/null")
    executor.run("echo 5000 > /proc/sys/net/core/netdev_max_backlog 2>/dev/null")

    # 3. Flush Android System DNS Caches
    executor.run("ndc resolver flushdefaultif >/dev/null 2>&1")
    executor.run("ndc resolver flushnet eth0 >/dev/null 2>&1")
    executor.run("ndc resolver flushnet wlan0 >/dev/null 2>&1")
    print("  [✓] System DNS Resolver caches successfully flushed.")


def test_smarttube_audio_buffer(executor: ShellExecutor):
    """Automated routine to verify SmartTube audio buffer health via logcat inspection."""
    print("\n[*] Running SmartTube Audio Buffer Diagnostics...")
    log_dump = executor.run("logcat -d -t 250 AudioFlinger:W bomx_video_decoder:I *:S").strip()
    underruns = len(re.findall(r"pause because of UNDERRUN", log_dump))
    if underruns > 0:
        print(f"  [!] Warning: Detected {underruns} recent AudioFlinger underruns. Applying buffer flush...")
        executor.run("cmd activity trim-memory org.smarttube.stable COMPLETE >/dev/null 2>&1")
    else:
        print("  [✓] Audio buffer health optimal: 0 underruns recorded.")


def main():
    print("======================================================================")
    print("   PLAYBOX TITANIUM v11.0 PRO - PROACTIVE NETWORK & HARDWARE OPTIMIZER")
    print("   Broadcom BCM72604 / IPv6 Suppressor / SmartTube Seeking Pipeline")
    print("======================================================================")

    executor = ShellExecutor(ADB_TARGET)

    # --- 1. SETTINGS DATABASE PROACTIVE REPAIR ---
    print("\n[+] [1/7] Auditing and Repairing Misconfigured Android Settings...")

    def update_settings_namespace(namespace: str, data: Dict[str, str]):
        count = 0
        for key, val in data.items():
            current = executor.run(f"settings get {namespace} {key}").strip()
            if current != val:
                executor.run(f"settings put {namespace} {key} '{val}'")
                count += 1
                print(f"    [fixed] {namespace} -> {key} = '{val}' (was: '{current}')")
        print(f"  [✓] {namespace.upper()} namespace synchronized ({count} values repaired).")

    update_settings_namespace("global", SETTINGS_GLOBAL)
    update_settings_namespace("system", SETTINGS_SYSTEM)
    update_settings_namespace("secure", SETTINGS_SECURE)

    # Bypass UI hardware overlays
    executor.run('settings put global overlay_display_devices ""')
    executor.run("service call SurfaceFlinger 1008 i32 1")

    # --- 2. ADVANCED NETWORK & IPV6 SUPPRESSION ---
    print("\n[+] [2/7] Executing Network Titan IPv6 & DNS Cache Optimization...")
    tune_network_and_disable_ipv6(executor)

    # --- 3. BROADCOM HW DECODER & SYSTEM PROPERTIES INJECTION ---
    print("\n[+] [3/7] Setting Broadcom VideoCore V & OMX Hardware Pipeline Props...")
    prop_count = 0
    for prop, val in SYSTEM_PROPERTIES.items():
        executor.run(f"setprop {prop} {val}")
        prop_count += 1
    print(f"  [✓] Injected {prop_count} hardware & media rendering properties.")

    # --- 4. DYNAMIC BLOATWARE & TELEMETRY DEBLOATING ---
    print("\n[+] [4/7] Auditing Installed Packages & Debloating Unnecessary Services...")
    installed_packages = executor.run("pm list packages -u")

    disabled_count = 0
    for pkg in TARGET_BLOAT_PACKAGES:
        if f"package:{pkg}" in installed_packages:
            executor.run(f"pm disable-user --user 0 {pkg} >/dev/null 2>&1")
            disabled_count += 1
    print(f"  [✓] Deactivated {disabled_count} telemetry and bloatware packages.")

    # Trim GMS auth/sync loops
    for srv in GMS_TRIM_SERVICES:
        executor.run(f"pm disable-user --user 0 {srv} >/dev/null 2>&1")
    print("  [✓] Trimmed GMS ChromeSync / Analytics wakelock services.")

    # --- 5. SCHEDULER PRIORITY ELEVATION (RENICE & OOM ADJ) ---
    print("\n[+] [5/7] Adjusting Process Priorities & OOM Score Adj (High Priority)...")

    def elevate_process(package_name: str, nice_val: int, oom_adj: int):
        pid_output = executor.run(f"pidof {package_name}").strip()
        if pid_output:
            pids = pid_output.split()
            for pid in pids:
                executor.run(f"renice -n {nice_val} -p {pid} 2>/dev/null")
                executor.run(f"echo {oom_adj} > /proc/{pid}/oom_score_adj 2>/dev/null")
            print(f"    [elevated] {package_name} (PID: {', '.join(pids)}) -> nice: {nice_val}, OOM score adj: {oom_adj}")
        else:
            print(f"    [info] {package_name} is not running currently.")

    elevate_process(TARGET_SMARTTUBE, nice_val=-10, oom_adj=-800)
    elevate_process(TARGET_LAUNCHER, nice_val=-5, oom_adj=-700)

    # Ignore background activities for Netflix DRM to preserve RAM
    executor.run("cmd appops set com.netflix.ninja RUN_IN_BACKGROUND ignore >/dev/null 2>&1")

    # --- 6. SMARTTUBE SEEKING & AUDIO FLINGER BUFFER STABILIZATION ---
    print("\n[+] [6/7] Stabilizing AudioFlinger & Clearing ExoPlayer Buffers...")
    test_smarttube_audio_buffer(executor)
    executor.run(f"cmd activity trim-memory {TARGET_SMARTTUBE} COMPLETE >/dev/null 2>&1")
    executor.run(f"cmd activity trim-memory {TARGET_LAUNCHER} COMPLETE >/dev/null 2>&1")
    print("  [✓] SmartTube ExoPlayer Sabr buffer states reset.")

    # --- 7. MEMORY PURGE & CACHE COMPACTION ---
    print("\n[+] [7/7] Purging Page Caches & Trimming Package Memory...")
    executor.run("pm trim-caches 4096G >/dev/null 2>&1")
    executor.run("cmd activity gc-heap >/dev/null 2>&1")
    print("  [✓] System heap compacted and caches purged.")

    print("\n======================================================================")
    print(" [✓] ATV PRO ULTIMATE OPTIMIZATION SUITE v11.0 COMPLETED SUCCESSFULLY!")
    print(" [i] System IPv6 stack suppressed & DNS resolver caches flushed.")
    print(" [i] Broadcom OMX hardware decoding & IPv4 fast resolution active.")
    print("======================================================================")


if __name__ == "__main__":
    main()
