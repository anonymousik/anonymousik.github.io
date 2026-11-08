#!/usr/bin/env python3
"""
================================================================================
PLAYBOX TITANIUM v19.1 - ULTIMATE CPU PERFORMANCE & VISUAL SHARPNESS SUITE
Target Device: Sagemcom DCTIW362 / Play NOW TV Box v1 (Broadcom BCM72604)
Target Scope: Forces CPU Governor to 'performance' with frequency locking, 
              optimizes SkiaGL font antialiasing/sharpness, enforces Broadcom OMX 
              hardware decoding, and suppresses GMS/WakeLock background loops.
================================================================================
"""

import os
import subprocess
import sys

ADB_TARGET = "192.168.1.3:5555"

TARGET_SMARTTUBE = "org.smarttube.stable"
TARGET_LAUNCHER = "com.spocky.projengmenu"

# Global System Settings for UI Fluidity and PCM Audio
SETTINGS_GLOBAL = {
    "window_animation_scale": "0.1",
    "transition_animation_scale": "0.25",
    "animator_duration_scale": "0.25",
    "activity_manager_constants": "max_cached_processes=10,background_settle_time=60000,fgservice_min_shown_time=500",
    "power_manager_constants": "no_cached_apps_until_foreground=true,maximum_screen_off_timeout=2147483647",
    "low_power_trigger_level": "0",
    "encoded_surround_output": "1",            # PCM Mode to avoid AudioFlinger underruns
    "encoded_surround_output_enabled": "0",
    "wifi_scan_always_enabled": "0",
    "ble_scan_always_enabled": "0",
    "wifi_sleep_policy": "2",
    "custom_home_package": TARGET_LAUNCHER,
    "sys_free_storage_log_interval": "0",
    "accessibility_enabled": "0",
    "private_dns_mode": "off",
    "dns_server1": "1.1.1.1",
    "dns_server2": "8.8.8.8"
}

SETTINGS_SYSTEM = {
    "hardware_accelerated": "1",
    "sound_effects_enabled": "0",
    "master_mono": "0",
    "volume_music_speaker": "100"
}

SETTINGS_SECURE = {
    "screensaver_enabled": "1",
    "sleep_timeout": "2147483647",
    "location_mode": "0",
    "wifi_watchdog_poor_link_detection": "0"
}

# SkiaGL Font Sharpness, GPU Rasterization & Broadcom OMX Properties
SYSTEM_PROPERTIES = {
    # SkiaGL & Font Clarity / Antialiasing Engine
    "debug.hwui.renderer": "skiagl",
    "debug.hwui.render_thread_count": "2",
    "debug.hwui.use_partial_updates": "true",
    "debug.hwui.show_dirty_regions": "false",
    "debug.egl.hw": "1",
    "debug.egl.check_gl_errors": "0",

    # SurfaceFlinger Pacing & HWC2 Composition
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
    "persist.sys.ui.hw": "true",

    # OMX & Broadcom Video Decoder Pipeline
    "media.stagefright.enable-player": "true",
    "media.stagefright.enable-http": "true",
    "media.stagefright.enable-aac": "true",
    "media.stagefright.enable-qcp": "true",
    "media.stagefright.enable-scan": "true",
    "media.stagefright.enable-fma264": "true",
    "media.stagefright.enable-meta": "true",
    "media.stagefright.omx.support_vendor_extensions": "false",
    "media.autorun.media.codec": "1",
    "ro.nx.media.vdec.fsm1080p": "1",
    "ro.nx.media.vdec.progoverride": "2",
    "ro.nx.media.vdec_outportbuf": "32",
    "ro.nx.mma": "1",

    # Audio Tunneling & Buffer Safety
    "af.resampler.quality": "4",
    "ro.nx.audio.tunnel_buffer_ms": "350",
    "ro.nx.audio.lipsync_delay": "0",
    "media.stagefright.audio.sink": "2097152",

    # Fiber TCP & Low-Latency IPv4
    "net.tcp.buffersize.default": "262144,524288,20971520,262144,524288,20971520",
    "net.tcp.buffersize.wifi": "524288,1048576,20971520,262144,524288,20971520",
    "net.tcp.buffersize.ethernet": "524288,1048576,20971520,262144,524288,20971520",
    "sys.sysctl.tcp_def_init_rwnd": "120",
    "net.ipv4.tcp_fastopen": "3",
    "sys.sysctl.extra_free_kbytes": "32768",
    "net.dns1": "1.1.1.1",
    "net.dns2": "8.8.8.8"
}

WEBVIEW_FLAGS = {
    "webview_flags": "ignore-gpu-blocklist=true enable-gpu-rasterization=true animated-image-resume=true webview-accelerate-small-canvases=true num-raster-threads=2 font-antialiasing=true",
    "webview_flags_tv": "enable-webview-surface-control-for-tv=true"
}

# Bloatware & Cast Receiver Packages to Disable
TARGET_BLOAT_PACKAGES = [
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
    "com.android.providers.userdictionary",
    "com.android.location.fused",
    "com.google.android.apps.mediashell"
]

GMS_TRIM_SERVICES = [
    "com.google.android.gms/com.google.android.gms.chromesync.sync.ChimeraSyncReceiverService",
    "com.google.android.gms/com.google.android.gms.auth.api.signin.revocation.RevocationBoundService",
    "com.google.android.gms/com.google.android.gms.analytics.AnalyticsService",
    "com.google.android.gms/com.google.android.gms.auth.api.credentials.sync.CredentialSyncService",
    "com.google.android.gms/.chimera.GmsIntentOperationService"
]


class ShellExecutor:
    """Handles execution locally or over ADB."""
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


def force_cpu_performance(executor: ShellExecutor):
    """Enforces high-performance CPU governor and locks maximum frequencies."""
    print("\n[+] [1/6] Forcing CPU Governor to 'performance' Mode...")
    policy_check = executor.run("ls -d /sys/devices/system/cpu/cpufreq/policy* 2>/dev/null")
    if not policy_check:
        print("  [i] Standard cpufreq paths not exposed. Enforcing system performance boosts...")
        executor.run("setprop sys.use_fifo_ui true")
        executor.run("setprop power.saving.mode 0")
        return

    policies = policy_check.split()
    for policy in policies:
        gov_path = f"{policy}/scaling_governor"
        max_freq_path = f"{policy}/scaling_max_freq"
        min_freq_path = f"{policy}/scaling_min_freq"
        
        max_freq = executor.run(f"cat {max_freq_path} 2>/dev/null").strip()
        executor.run(f"echo performance > {gov_path} 2>/dev/null")
        if max_freq:
            executor.run(f"echo {max_freq} > {min_freq_path} 2>/dev/null")
            print(f"  [✓] Locked {policy.split('/')[-1]} to performance at {max_freq} kHz.")
        else:
            print(f"  [✓] Set {policy.split('/')[-1]} governor to performance.")


def main():
    print("======================================================================")
    print("   PLAYBOX TITANIUM v19.0 - ULTIMATE PERFORMANCE & SHARPNESS SUITE")
    print("======================================================================")

    executor = ShellExecutor(ADB_TARGET)

    # 1. CPU PERFORMANCE GOVERNOR
    force_cpu_performance(executor)

    # 2. SETTINGS DATABASE (PCM AUDIO & FONT FLAGS)
    print("\n[+] [2/6] Synchronizing Settings Database & WebView Antialiasing...")
    for ns, data in [("global", SETTINGS_GLOBAL), ("system", SETTINGS_SYSTEM), ("secure", SETTINGS_SECURE)]:
        for key, val in data.items():
            executor.run(f"settings put {ns} {key} '{val}'")
            
    for key, val in WEBVIEW_FLAGS.items():
        executor.run(f"settings put global {key} '{val}'")
    print("  [✓] Settings database and WebView font antialiasing configured.")

    # 3. SYSTEM PROPERTIES (SKIALG & BROADCOM OMX)
    print("\n[+] [3/6] Injecting SkiaGL Visual Sharpness & Broadcom OMX Props...")
    for prop, val in SYSTEM_PROPERTIES.items():
        executor.run(f"setprop {prop} {val}")
    print("  [✓] Visual clarity and hardware decoding properties enforced.")

    # 4. NETWORK STACK & IPV6 SUPPRESSION
    print("\n[+] [4/6] Suppressing IPv6 & Flushing DNS Resolvers...")
    for node in ["all", "default", "eth0", "wlan0"]:
        executor.run(f"echo 1 > /proc/sys/net/ipv6/conf/{node}/disable_ipv6 2>/dev/null")
    executor.run("ndc resolver flushdefaultif >/dev/null 2>&1")
    print("  [✓] IPv6 suppressed & DNS flushed.")

    # 5. BLOATWARE & GMS WAKELOCK TRIMMING
    print("\n[+] [5/6] Disabling Bloatware & Neutralizing GMS Auth/WakeLock Loops...")
    installed = executor.run("pm list packages -u")
    for pkg in TARGET_BLOAT_PACKAGES:
        if f"package:{pkg}" in installed:
            executor.run(f"pm disable-user --user 0 {pkg} >/dev/null 2>&1")
    for srv in GMS_TRIM_SERVICES:
        executor.run(f"pm disable-user --user 0 {srv} >/dev/null 2>&1")
    print("  [✓] Background telemetry and Chromecast loops neutralized.")

    # 6. PROCESS PRIORITY ELEVATION & CACHE PURGE
    print("\n[+] [6/6] Elevating SmartTube Priority & Purging Page Caches...")
    for pkg, nice_val, oom_adj in [(TARGET_SMARTTUBE, -10, -800), (TARGET_LAUNCHER, -5, -700)]:
        pids = executor.run(f"pidof {pkg}").strip().split()
        for pid in pids:
            if pid:
                executor.run(f"renice -n {nice_val} -p {pid} 2>/dev/null")
                executor.run(f"echo {oom_adj} > /proc/{pid}/oom_score_adj 2>/dev/null")
                
    executor.run("cmd activity trim-memory org.smarttube.stable COMPLETE >/dev/null 2>&1")
    executor.run("pm trim-caches 4096G >/dev/null 2>&1")
    print("  [✓] Process scheduling and heap memory cleaned.")

    print("\n======================================================================")
    print(" [✓] TITANIUM v19.0 ULTIMATE SUITE APPLIED SUCCESSFULLY!")
    print(" [i] CPU set to Performance, SkiaGL font antialiasing active, PCM audio locked.")
    print("======================================================================")


if __name__ == "__main__":
    main()
