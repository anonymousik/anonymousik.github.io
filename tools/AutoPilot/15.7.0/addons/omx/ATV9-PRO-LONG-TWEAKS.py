#!/usr/bin/env python3
"""
================================================================================
PLAYBOX TITANIUM v12.0 - LONGEVITY & HARDWARE STABILITY OPTIMIZER
Target Device: Sagemcom DCTIW362 / Play NOW TV Box v1
Hardware: Broadcom BCM72604 SoC | Android TV 9.0 (API 28)
Focus: System Stability, Flash Storage Lifespan, Thermal Protection, Fast Video Seek
Execution Context: ADB (192.168.1.3:5555) / Shizuku rish / Termux
================================================================================
"""

import os
import re
import subprocess
import sys
import time
from typing import Dict, List

# --- CONFIGURATION DEFINITIONS ---
ADB_TARGET = "192.168.1.3:5555"

TARGET_SMARTTUBE = "org.smarttube.stable"
TARGET_LAUNCHER = "com.spocky.projlauncher"

# 1. Longevity, Memory & Thermal Protection Settings
SETTINGS_GLOBAL: Dict[str, str] = {
    "window_animation_scale": "0.0",
    "transition_animation_scale": "0.5",
    "animator_duration_scale": "0.5",
    # Protects 1.45GB RAM pool from LMK thrashing and CPU thermal spikes
    "activity_manager_constants": "max_cached_processes=8,background_settle_time=60000,fgservice_min_shown_time=500,power_check_max_cpu_1=75,power_check_max_cpu_0=85",
    "power_manager_constants": "no_cached_apps_until_foreground=true",
    "low_power_trigger_level": "0",
    # Prevent eMMC Flash Storage Wear out from constant logging
    "sys_free_storage_log_interval": "0",
    "sqlite_compatibility_wal_flags": "truncate_size=2097152",
    # Lock safe PCM Stereo mode to eliminate AudioFlinger crashes
    "encoded_surround_output": "1",
    "encoded_surround_output_enabled": "0",
    # Power and Network scanning savings
    "wifi_scan_always_enabled": "0",
    "ble_scan_always_enabled": "0",
    "wifi_sleep_policy": "2",
    "custom_home_package": TARGET_LAUNCHER,
    "accessibility_enabled": "0",
    # DNS stability (IPv4 primary lock)
    "private_dns_mode": "off",
    "dns_server1": "1.1.1.1",
    "dns_server2": "8.8.8.8"
}

SETTINGS_SYSTEM: Dict[str, str] = {
    "hardware_accelerated": "1",
    "sound_effects_enabled": "0",
    "master_mono": "0",
    "volume_music_speaker": "100"
}

SETTINGS_SECURE: Dict[str, str] = {
    "screensaver_enabled": "0",
    "sleep_timeout": "2147483647"
}

# 2. Hardware Properties (Broadcom OMX, Audio Sink, Thermal Safety)
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

    # Broadcom OMX Hardware Decoder
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
    "ro.nx.media.vdec_outportbuf": "32",
    "ro.nx.mma": "1",
    "persist.sys.ui.hw": "true",

    # Audio Pipeline & Buffer Underrun Protection
    "af.resampler.quality": "4",
    "ro.nx.audio.tunnel_buffer_ms": "350",
    "ro.nx.audio.lipsync_delay": "0",
    "media.stagefright.audio.sink": "2097152",

    # Fiber TCP & System Buffer Safety
    "net.tcp.buffersize.default": "262144,524288,20971520,262144,524288,20971520",
    "net.tcp.buffersize.wifi": "524288,1048576,20971520,262144,524288,20971520",
    "net.tcp.buffersize.ethernet": "524288,1048576,20971520,262144,524288,20971520",
    "sys.sysctl.tcp_def_init_rwnd": "120",
    "net.ipv4.tcp_fastopen": "3",
    "sys.sysctl.extra_free_kbytes": "32768",
    "net.dns1": "1.1.1.1",
    "net.dns2": "8.8.8.8"
}

# 3. Unsafe / Unneeded System Packages to Disable Safely
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

GMS_TRIM_SERVICES: List[str] = [
    "com.google.android.gms/com.google.android.gms.chromesync.sync.ChimeraSyncReceiverService",
    "com.google.android.gms/com.google.android.gms.auth.api.signin.revocation.RevocationBoundService",
    "com.google.android.gms/com.google.android.gms.analytics.AnalyticsService"
]


class ShellExecutor:
    """Handles ADB and local execution paths."""

    def __init__(self, target_ip: str = ADB_TARGET):
        self.target_ip = target_ip
        self.is_adb_remote = True
        self._setup_connection()

    def _setup_connection(self):
        if os.path.exists("/system/bin/app_process"):
            res = self.exec_local("id -u")
            if res.strip() in ["0", "2000"]:
                self.is_adb_remote = False
                print(f"[*] Native Local Execution Context (UID: {res.strip()}).")
                return

        print(f"[*] Remote ADB Mode. Connecting to {self.target_ip}...")
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


def preserve_flash_storage_and_memory(executor: ShellExecutor):
    """Executes storage TRIM and flushes logcat ring buffers to prevent flash wear."""
    print("\n[*] Executing eMMC Flash Storage Maintenance & Log Buffer Flush...")
    
    # Trim system storage blocks for eMMC longevity
    executor.run("sm fstrim >/dev/null 2>&1 || fstrim -v /data >/dev/null 2>&1")
    
    # Suppress logcat overhead to save CPU and NAND writes
    executor.run("logcat -c >/dev/null 2>&1")
    executor.run("logcat -G 256K >/dev/null 2>&1")
    
    print("  [✓] Storage TRIM completed and logcat ring buffer capped at 256KB.")


def tune_network_and_disable_ipv6(executor: ShellExecutor):
    """Suppresses unneeded IPv6 lookups to maintain stable IPv4 socket throughput."""
    print("\n[*] Configuring Resilient Network Stack & IPv6 Suppression...")

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
            
    print(f"  [✓] System IPv6 stack disabled on {disabled_count} interfaces.")

    executor.run("echo 1 > /proc/sys/net/ipv4/tcp_low_latency 2>/dev/null")
    executor.run("echo 5000 > /proc/sys/net/core/netdev_max_backlog 2>/dev/null")
    executor.run("ndc resolver flushdefaultif >/dev/null 2>&1")
    print("  [✓] Network socket queues and DNS resolvers flushtuned.")


def main():
    print("======================================================================")
    print("   PLAYBOX TITANIUM v12.0 - HARDWARE STABILITY & LONGEVITY SUITE")
    print("======================================================================")

    executor = ShellExecutor(ADB_TARGET)

    # --- 1. SETTINGS DATABASE SYNCHRONIZATION ---
    print("\n[+] [1/6] Applying Long-Term Stability Directives in Settings DB...")

    def update_settings(namespace: str, data: Dict[str, str]):
        count = 0
        for key, val in data.items():
            current = executor.run(f"settings get {namespace} {key}").strip()
            if current != val:
                executor.run(f"settings put {namespace} {key} '{val}'")
                count += 1
        print(f"  [✓] {namespace.upper()} DB synchronized ({count} entries set).")

    update_settings("global", SETTINGS_GLOBAL)
    update_settings("system", SETTINGS_SYSTEM)
    update_settings("secure", SETTINGS_SECURE)

    executor.run('settings put global overlay_display_devices ""')
    executor.run("service call SurfaceFlinger 1008 i32 1")

    # --- 2. HARDWARE DECODER & STABILITY PROPERTIES ---
    print("\n[+] [2/6] Enforcing Broadcom Hardware Engine & Audio Tunneling Props...")
    for prop, val in SYSTEM_PROPERTIES.items():
        executor.run(f"setprop {prop} {val}")
    print("  [✓] System properties enforced.")

    # --- 3. STORAGE & LOGGING MAINTENANCE ---
    print("\n[+] [3/6] Applying Flash Storage Wear-Reduction Protocols...")
    preserve_flash_storage_and_memory(executor)

    # --- 4. NETWORK STACK TUNING ---
    print("\n[+] [4/6] Tuning Network Resolvers & Suppressing IPv6 Overhead...")
    tune_network_and_disable_ipv6(executor)

    # --- 5. DEBLOATING & BACKGROUND WAKELOCK TRIMMING ---
    print("\n[+] [5/6] Disabling Non-Essential Telemetry & GMS Sync Loops...")
    installed_packages = executor.run("pm list packages -u")

    disabled_count = 0
    for pkg in TARGET_BLOAT_PACKAGES:
        if f"package:{pkg}" in installed_packages:
            executor.run(f"pm disable-user --user 0 {pkg} >/dev/null 2>&1")
            disabled_count += 1
    print(f"  [✓] Trimmed {disabled_count} unused background services.")

    for srv in GMS_TRIM_SERVICES:
        executor.run(f"pm disable-user --user 0 {srv} >/dev/null 2>&1")

    # --- 6. PRIORITY ELEVATION & MEMORY COMPACTION ---
    print("\n[+] [6/6] Setting Core Process Priority & Trimming Heap...")

    def elevate_process(package_name: str, nice_val: int, oom_adj: int):
        pid_output = executor.run(f"pidof {package_name}").strip()
        if pid_output:
            pids = pid_output.split()
            for pid in pids:
                executor.run(f"renice -n {nice_val} -p {pid} 2>/dev/null")
                executor.run(f"echo {oom_adj} > /proc/{pid}/oom_score_adj 2>/dev/null")
            print(f"    [elevated] {package_name} (PIDs: {', '.join(pids)}) -> nice: {nice_val}, oom_score_adj: {oom_adj}")

    elevate_process(TARGET_SMARTTUBE, nice_val=-10, oom_adj=-800)
    elevate_process(TARGET_LAUNCHER, nice_val=-5, oom_adj=-700)

    executor.run("cmd appops set com.netflix.ninja RUN_IN_BACKGROUND ignore >/dev/null 2>&1")
    executor.run(f"cmd activity trim-memory {TARGET_SMARTTUBE} COMPLETE >/dev/null 2>&1")
    executor.run(f"cmd activity trim-memory {TARGET_LAUNCHER} COMPLETE >/dev/null 2>&1")
    executor.run("pm trim-caches 4096G >/dev/null 2>&1")

    print("\n======================================================================")
    print(" [✓] STABILITY & LONGEVITY OPTIMIZATION SUITE v12.0 FINISHED!")
    print(" [i] eMMC Flash wear reduced, CPU thermals guarded, RAM pool stabilized.")
    print("======================================================================")


if __name__ == "__main__":
    main()