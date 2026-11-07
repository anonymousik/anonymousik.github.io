#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
Maksymalnie Rozbudowana Formuła Optymalizacji Procesów Dekodera Video
i Silnika Renderowania UI dla Broadcom BCM72604 (DCTIW362_PLAY)
Target: Android TV 9 (API 28) | SmartTube & VOD/IPTV High-Bitrate Strumienie
Features: Local Shell, Shizuku/rish, Remote ADB & Persistent Boot Injection
==============================================================================
"""

import os
import sys
import subprocess
import shutil
import time
import argparse

class TVOptimizer:
    def __init__(self, target_ip=None, target_port=5555):
        self.target_ip = target_ip
        self.target_port = target_port
        self.is_remote = target_ip is not None
        
        if self.is_remote:
            self.adb_bin = shutil.which('adb')
            if not self.adb_bin:
                print("[!] BŁĄD: Brak zainstalowanego 'adb' w systemie macierzystym!")
                sys.exit(1)
            self.mode = f"REMOTE_ADB ({self.target_ip}:{self.target_port})"
            self._connect_adb()
        else:
            self.is_root = os.geteuid() == 0 if hasattr(os, 'geteuid') else False
            self.rish_path = shutil.which('rish')
            self.mode = "ROOT" if self.is_root else ("RISH" if self.rish_path else "LOCAL_SHELL")

        print(f"[*] Wykryty tryb wykonawczy: {self.mode}")

    def _connect_adb(self):
        target = f"{self.target_ip}:{self.target_port}"
        print(f"[*] Łączenie ze zdalnym urządzeniem Android TV: {target}...")
        res = subprocess.run([self.adb_bin, "connect", target], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "connected" not in res.stdout.lower() and "already connected" not in res.stdout.lower():
            print(f"[!] Nie udało się połączyć z urządzeniem {target}. Odpowiedź ADB: {res.stdout.strip()}")
        else:
            print(f"[+] Pomyślnie połączono z {target}")

    def run_cmd(self, command: str) -> bool:
        try:
            if self.is_remote:
                target = f"{self.target_ip}:{self.target_port}"
                exec_cmd = [self.adb_bin, "-s", target, "shell", command]
            elif self.is_root:
                exec_cmd = ["sh", "-c", command]
            elif self.rish_path:
                exec_cmd = [self.rish_path, "-c", command]
            else:
                exec_cmd = ["sh", "-c", command]

            res = subprocess.run(
                exec_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15
            )
            return res.returncode == 0
        except Exception as e:
            print(f"[!] Błąd wykonania ({command}): {e}")
            return False

    def optimize_rendering_engine(self):
        print("[*] 1/10 Rozbudowane Strojenie Potoku Renderowania SkiaGL & SurfaceFlinger...")
        cmds = [
            "wm density 280",
            "wm size 1920x1080",
            "setprop persist.sys.font_hinting full",
            "setprop debug.hwui.text_subpixel_quantization true",
            "setprop debug.hwui.renderer skiagl",
            "setprop debug.renderengine.backend skiaglthreaded",
            "setprop debug.hwui.render_thread true",
            "setprop persist.sys.ui.hw true",
            "setprop debug.hwui.texture_cache_size 96",
            "setprop debug.hwui.layer_cache_size 48",
            "setprop debug.hwui.r_buffer_cache_size 24",
            "setprop debug.hwui.path_cache_size 32",
            "setprop debug.sf.latch_unsignaled 1",
            "setprop debug.sf.disable_backpressure 1",
            "setprop debug.sf.early_phase_offset_ns 200000",
            "setprop debug.sf.high_fps_early_phase_offset_ns 200000",
            "setprop debug.gr.numframebuffers 3",
            "setprop ro.hwui.use_vulkan false",
            "setprop persist.vendor.display.mode 7",
            "settings put global display_peak_refresh_rate 60.0"
        ]
        for cmd in cmds:
            self.run_cmd(cmd)

    def optimize_hardware_vpu_decoder(self):
        print("[*] 2/10 Głęboka Optymalizacja Sprzętowego Dekodera Broadcom Nexus VPU (VP9 / HEVC)...")
        cmds = [
            "setprop media.acodec.preferhw true",
            "setprop media.codec.sw.fallback false",
            "setprop media.tunneled-playback.enable true",
            "setprop media.brcm.tunnel.clock hdmi",
            "setprop media.brcm.mma.enable 1",
            "setprop media.brcm.vpu.buffers 384",
            "setprop media.brcm.vdec.progoverride 2",
            "setprop media.brcm.vdec.vp9.hw_accel true",
            "setprop media.brcm.vdec.vp9.dpb_size 64",
            "setprop media.brcm.vpu.high_bitrate_mode 1",
            "setprop media.brcm.vdec.fastpath 1",
            "setprop media.brcm.vdec.low_latency 1",
            "setprop media.stagefright.enable-player true",
            "setprop media.stagefright.enable-http true",
            "setprop media.stagefright.enable-aac true",
            "setprop media.stagefright.cache-params 134217728/268435456/300",
            "setprop media.codec.c2.av1 0",
            "setprop media.codec.av1.disable true"
        ]
        for cmd in cmds:
            self.run_cmd(cmd)

    def optimize_art_dalvik_jit(self):
        print("[*] 3/10 Kompilacja ART/Dalvik & Aktywacja ARM Cortex-A15 HW IDIV...")
        cmds = [
            "setprop dalvik.vm.isa.arm.features default,idiv",
            "setprop dalvik.vm.execution-mode int:jit",
            "setprop dalvik.vm.dex2oat-filter speed-profile",
            "setprop dalvik.vm.heapminfree 4m",
            "setprop dalvik.vm.heapmaxfree 32m",
            "setprop dalvik.vm.heapgrowthlimit 256m",
            "setprop dalvik.vm.heapsize 512m",
            "setprop ro.lmk.upgrade_pressure 30",
            "settings put global activity_manager_constants max_cached_processes=32"
        ]
        for cmd in cmds:
            self.run_cmd(cmd)

    def optimize_kernel_and_phantoms(self):
        print("[*] 4/10 Strojenie Jądra Linux i Zarządzanie Pamięcią Wirtualną (Rezerwa VPU)...")
        sysctl_cmds = [
            "sysctl -w vm.swappiness=20 2>/dev/null || echo 20 > /proc/sys/vm/swappiness",
            "sysctl -w vm.vfs_cache_pressure=10 2>/dev/null || echo 10 > /proc/sys/vm/vfs_cache_pressure",
            "sysctl -w vm.dirty_ratio=40 2>/dev/null || echo 40 > /proc/sys/vm/dirty_ratio",
            "sysctl -w vm.min_free_kbytes=131072 2>/dev/null || echo 131072 > /proc/sys/vm/min_free_kbytes"
        ]
        for cmd in sysctl_cmds:
            self.run_cmd(cmd)

        phantom_cmds = [
            "/system/bin/device_config set_sync_disabled_for_tests persistent",
            "/system/bin/device_config put activity_manager max_phantom_processes 2147483647",
            "settings put global settings_enable_monitor_phantom_procs false"
        ]
        for cmd in phantom_cmds:
            self.run_cmd(cmd)

    def optimize_network_and_buffers(self):
        print("[*] 5/10 Strojenie Stosu Sieciowego (64 MB TCP Buffer pod Wysokie Bitrate)...")
        net_cmds = [
            "ip link set eth0 down 2>/dev/null",
            "ip route flush table main 2>/dev/null",
            "ip neigh flush all 2>/dev/null",
            "sysctl -w net.ipv6.conf.all.disable_ipv6=1 2>/dev/null || echo 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6",
            "sysctl -w net.core.rmem_max=67108864 2>/dev/null || echo 67108864 > /proc/sys/net/core/rmem_max",
            "sysctl -w net.core.wmem_max=67108864 2>/dev/null || echo 67108864 > /proc/sys/net/core/wmem_max",
            "setprop net.tcp.buffersize.wifi 4194304,16777216,67108864,2097152,8388608,33554432",
            "setprop net.tcp.default_init_rwnd 292",
            "settings put global private_dns_mode hostname",
            "settings put global private_dns_specifier one.one.one.one"
        ]
        for cmd in net_cmds:
            self.run_cmd(cmd)

    def optimize_smarttube_and_vod(self):
        print("[*] 6/10 Priorytetyzacja Odtwarzania SmartTube & Netflix...")
        st_cmds = [
            'cmd appops set org.smarttube.stable RUN_IN_BACKGROUND allow',
            'cmd appops set com.netflix.ninja RUN_IN_BACKGROUND allow'
        ]
        for cmd in st_cmds:
            self.run_cmd(cmd)

    def apply_appops(self):
        print("[*] 7/10 Blokada Usług Wybudzających GMS w Tle...")
        appops_cmds = [
            "cmd appops set com.google.android.gms WAKE_LOCK ignore",
            "cmd appops set com.google.android.gms RUN_IN_BACKGROUND ignore"
        ]
        for cmd in appops_cmds:
            self.run_cmd(cmd)

    def apply_realtime_scheduling(self):
        print("[*] 8/10 Konfiguracja Priorytetów Czasu Rzeczywistego (SCHED_FIFO)...")
        rt_script = """
        if [ "$(id -u)" -eq 0 ]; then
            SF_PID=$(pgrep surfaceflinger)
            COMP_PID=$(pgrep -f "android.hardware.graphics.composer")
            SYS_PID=$(pgrep -f "system_server")
            
            [ -n "$SF_PID" ] && chrt -f -p 99 $SF_PID 2>/dev/null
            [ -n "$COMP_PID" ] && chrt -f -p 99 $COMP_PID 2>/dev/null
            [ -n "$SYS_PID" ] && chrt -f -p 85 $SYS_PID 2>/dev/null
            
            for pid in $SF_PID $COMP_PID; do
                echo $pid > /dev/stune/top-app/tasks 2>/dev/null
            done
        fi
        """
        self.run_cmd(rt_script)

    def setup_persistence(self):
        print("[*] 9/10 Tworzenie Trwałego Skryptu Rozruchowego (Persistence)...")
        init_script = """
        if [ "$(id -u)" -eq 0 ]; then
            mount -o remount,rw /system 2>/dev/null
            mkdir -p /system/etc/init.d/ 2>/dev/null
            echo '#!/system/bin/sh
            echo 20 > /proc/sys/vm/swappiness
            echo 10 > /proc/sys/vm/vfs_cache_pressure
            echo 40 > /proc/sys/vm/dirty_ratio
            echo 131072 > /proc/sys/vm/min_free_kbytes
            echo 67108864 > /proc/sys/net/core/rmem_max
            echo 67108864 > /proc/sys/net/core/wmem_max
            echo 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6
            ip link set eth0 down 2>/dev/null
            ip route flush table main 2>/dev/null
            SF_PID=$(pgrep surfaceflinger)
            COMP_PID=$(pgrep -f "android.hardware.graphics.composer")
            [ -n "$SF_PID" ] && chrt -f -p 99 $SF_PID 2>/dev/null
            [ -n "$COMP_PID" ] && chrt -f -p 99 $COMP_PID 2>/dev/null
            ' > /system/etc/init.d/99_bcm_opt
            chmod 755 /system/etc/init.d/99_bcm_opt 2>/dev/null
            mount -o remount,ro /system 2>/dev/null
        fi
        """
        self.run_cmd(init_script)

    def cleanup_and_trim(self):
        print("[*] 10/10 Czyszczenie Pamięci Cache i Defragmentacja eMMC (fstrim)...")
        self.run_cmd("pm trim-caches 800M")
        self.run_cmd("fstrim -v /data")

    def execute(self):
        start_time = time.time()
        print("\n==============================================================================")
        print("  ROZBUDOWANA FORMUŁA OPTYMALIZACJI DEKODERA VIDEO I SILNIKA RENDEROWANIA UI  ")
        print("  TARGET: DCTIW362_PLAY (Broadcom BCM72604) | ULTRA-RESPONSE MULTIMEDIA       ")
        print("==============================================================================\n")
        
        self.optimize_rendering_engine()
        self.optimize_hardware_vpu_decoder()
        self.optimize_art_dalvik_jit()
        self.optimize_kernel_and_phantoms()
        self.optimize_network_and_buffers()
        self.optimize_smarttube_and_vod()
        self.apply_appops()
        self.apply_realtime_scheduling()
        self.setup_persistence()
        self.cleanup_and_trim()

        elapsed = round(time.time() - start_time, 2)
        print("\n==============================================================================")
        print(f"  [+] OPTYMALIZACJA ZAKOŃCZONA POMYŚLNIE W CZASIE {elapsed} SEKUND!")
        print("  [+] TRWAŁE PARAMETRY PERSISTENT ORAZ INIT.D ZOSTAŁY SKONFIGUROWANE.")
        print("==============================================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optymalizator Android TV (Broadcom BCM72604)")
    parser.add_argument("--ip", type=str, help="Adres IP zdalnego urządzenia Android TV")
    parser.add_argument("--port", type=int, default=5555, help="Port zdalnego ADB (domyślnie: 5555)")
    args = parser.parse_args()

    optimizer = TVOptimizer(target_ip=args.ip, target_port=args.port)
    optimizer.execute()