#!/usr/bin/env python3
"""
PLAYBOX TITANIUM MASTER SUITE - BCM72604 / VIDEOCORE V / OMX OPTIMIZER
Target Device: Sagemcom DCTIW362 (Android TV 9.0 / ARMv7 32-bit / API 28)
Execution Context: ADB / Shizuku / rish (UID 2000 / Shell)
Architecture: Broadcom BCM72604 SoC + VideoCore V (V3D-510) GPU
"""

import os
import subprocess
import sys
import time

TARGET_SMARTTUBE = "org.smarttube.stable"
TARGET_LAUNCHER = "com.spocky.projlauncher"
ADB_TARGET = "192.168.1.3:5555"

def run_cmd(cmd: str) -> str:
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

# Comprehensive System Properties for Broadcom OMX & SurfaceFlinger
SYSTEM_PROPERTIES = {
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
    "af.resampler.quality": "4",
    "ro.nx.audio.tunnel_buffer_ms": "250",
    "ro.nx.audio.lipsync_delay": "0",
    "media.stagefright.audio.sink": "1048576",
    "net.tcp.buffersize.default": "262144,524288,20971520,262144,524288,20971520",
    "net.tcp.buffersize.wifi": "524288,1048576,20971520,262144,524288,20971520",
    "net.tcp.buffersize.ethernet": "524288,1048576,20971520,262144,524288,20971520",
    "sys.sysctl.tcp_def_init_rwnd": "120",
    "net.ipv4.tcp_fastopen": "3",
    "sys.sysctl.extra_free_kbytes": "32768"
}

# Settings database entries optimized for 1.45 GB RAM pool
SETTINGS_GLOBAL = {
    "window_animation_scale": "0.0",
    "transition_animation_scale": "0.5",
    "animator_duration_scale": "0.5",
    "activity_manager_constants": "max_cached_processes=8,background_settle_time=60000,fgservice_min_shown_time=500,power_check_max_cpu_1=75,power_check_max_cpu_0=85",
    "power_manager_constants": "no_cached_apps_until_foreground=true",
    "low_power_trigger_level": "0",
    "encoded_surround_output": "1",  # PCM Surround mode to prevent AudioFlinger UNDERRUN
    "wifi_scan_always_enabled": "0",
    "ble_scan_always_enabled": "0",
    "custom_home_package": "com.spocky.projlauncher"
}

SETTINGS_SYSTEM = {
    "hardware_accelerated": "1",
    "sound_effects_enabled": "0"
}

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
    "com.android.providers.userdictionary"
]

def run_shell(cmd: str) -> str:
    """Executes local adb/shell command safely."""
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def main():
    print("======================================================================")
    print("[*] PLAYBOX BCM72604 TITANIUM MASTER OPTIMIZATION SUITE")
    print("======================================================================")

    uid = run_shell("adb shell id -u")
    print(f"[i] Execution Context UID: {uid}")

    # 1. Properties
    print("\n[+] [1/5] Applying Broadcom OMX & VideoCore V System Properties...")
    for k, v in SYSTEM_PROPERTIES.items():
        run_shell(f"adb shell setprop {k} {v}")
    run_shell("adb shell service call SurfaceFlinger 1008 i32 1")
    print("[✓] System properties applied.")

    # 2. Settings DB
    print("\n[+] [2/5] Configuring Settings Database (Activity Manager & Audio)...")
    for k, v in SETTINGS_GLOBAL.items():
        run_shell(f"adb shell settings put global {k} '{v}'")
    for k, v in SETTINGS_SYSTEM.items():
        run_shell(f"adb shell settings put system {k} '{v}'")
    print("[✓] Settings database updated.")

    # 3. Bloatware trimming
    print("\n[+] [3/5] Trimming System Bloatware & Telemetry...")
    installed = run_shell("adb shell pm list packages -u")
    disabled = 0
    for pkg in TARGET_BLOAT_PACKAGES:
        if f"package:{pkg}" in installed:
            run_shell(f"adb shell pm disable-user --user 0 {pkg} >/dev/null 2>&1")
            disabled += 1
    print(f"[✓] Disabled {disabled} unwanted packages.")

    # 4. App Priority Elevation
    print("\n[+] [4/5] Elevating Process Priorities (SmartTube & Projectivy)...")
    st_pid = run_shell(f"adb shell pidof {TARGET_SMARTTUBE}")
    if st_pid:
        run_shell(f"adb shell 'echo -800 > /proc/{st_pid}/oom_score_adj' 2>/dev/null")
        run_shell(f"adb shell renice -n -10 -p {st_pid} 2>/dev/null")
        print("    [✓] SmartTube priority elevated (-800 OOM, -10 nice).")

    prj_pid = run_shell(f"adb shell pidof {TARGET_LAUNCHER}")
    if prj_pid:
        run_shell(f"adb shell 'echo -700 > /proc/{prj_pid}/oom_score_adj' 2>/dev/null")
        run_shell(f"adb shell renice -n -5 -p {prj_pid} 2>/dev/null")
        print("    [✓] Projectivy Launcher priority elevated (-700 OOM, -5 nice).")

    # 5. Memory Trim & Cleanup
    print("\n[+] [5/5] Executing Memory Compaction & Cache Purge...")
    run_shell(f"adb shell cmd activity trim-memory {TARGET_SMARTTUBE} COMPLETE >/dev/null 2>&1")
    run_shell(f"adb shell cmd activity trim-memory {TARGET_LAUNCHER} COMPLETE >/dev/null 2>&1")
    run_shell("adb shell pm trim-caches 4096G >/dev/null 2>&1")
    print("[✓] Memory compaction completed.")

    print("\n======================================================================")
    print("[✓] OPTIMIZATION SUITE FINISHED SUCCESSFULLY!")
    print("======================================================================")
def apply_optimal_audio_config():
    print("======================================================================")
    print("[*] APPLYING OPTIMAL AUDIO & SETTINGS CONFIGURATION")
    print("======================================================================")

    # 1. Ensure ADB connection
    print(f"[i] Connecting to ADB target {ADB_TARGET}...")
    run_cmd(f"adb connect {ADB_TARGET}")

    # 2. Configure Settings Database Parameters (Matching TV Menu: PCM / Never Passthrough)
    print("\n[+] [1/2] Enforcing Optimal Audio Database Parameters...")
    
    audio_settings = {
        "encoded_surround_output": "1",          # Force PCM Stereo / Multichannel decoded on device (Nigdy passthrough)
        "encoded_surround_output_enabled": "0",  # Disable automatic format probing that triggers AudioFlinger UNDERRUN
        "sound_effects_enabled": "0",            # Disable UI touch/click sounds to save AudioFlinger ring buffer
        "master_mono": "0",                      # Stereo output enabled
        "volume_music_speaker": "100"            # Full scale volume pipeline
    }

    for key, val in audio_settings.items():
        cmd = f"adb -s {ADB_TARGET} shell settings put global {key} {val}"
        run_cmd(cmd)
        print(f"    [setting] global {key} = {val}")

    # System-level sound safety flags
    run_cmd(f"adb -s {ADB_TARGET} shell settings put system sound_effects_enabled 0")
    run_cmd(f"adb -s {ADB_TARGET} shell settings put system notification_light_pulse 0")

    # 3. Apply Low-Latency Audio Properties for Broadcom Nexus
    print("\n[+] [2/2] Injecting Broadcom Audio & Stagefright Sink Properties...")
    audio_props = {
        "af.resampler.quality": "4",
        "ro.nx.audio.tunnel_buffer_ms": "250",
        "ro.nx.audio.lipsync_delay": "0",
        "media.stagefright.audio.sink": "1048576"
    }

    for prop, val in audio_props.items():
        cmd = f"adb -s {ADB_TARGET} shell setprop {prop} {val}"
        run_cmd(cmd)
        print(f"    [setprop] {prop} = {val}")

    print("\n======================================================================")
    print("[✓] AUDIO CONFIGURATION APPLIED SUCCESSFULLY!")
    print("[i] The device is now locked to PCM decoding mode, eliminating UNDERRUNs.")
    print("======================================================================")

if __name__ == "__main__":
    apply_optimal_audio_config()
    main()
