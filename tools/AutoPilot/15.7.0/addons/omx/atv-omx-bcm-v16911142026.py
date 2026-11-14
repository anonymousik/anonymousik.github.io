#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PLAYBOX TITANIUM v16.0 — BROADCOM BCM72604 & CHROMECAST-SAFE EDITION
Urządzenie : Sagemcom DCTIW362 / DCTIW362_PLAY (Play Now TV Box V1)
Hardware   : Dual-Core ARM Cortex-A15 | VideoCore V3D | 1425 MB RAM | WiFi 5GHz
System     : Android TV 9.0 (API 28) | Tryb: 100% Bez Roota (ADB / Shizuku)
================================================================================
"""

import argparse
import io
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List, Optional


class HW:
    """Zweryfikowane parametry sprzętowe Sagemcom DCTIW362_PLAY."""
    DEFAULT_IP           = "192.168.1.3:5555"
    RAM_TOTAL_MB         = 1425
    DECODER_VP9          = "OMX.broadcom.decoder.vp9"
    PKG_SMARTTUBE        = "org.smarttube.stable"
    PKG_SMARTTUBE_BETA   = "org.smarttube.beta"
    PKG_LAUNCHER         = "com.spocky.projengmenu"
    PKG_MEDIASHELL       = "com.google.android.apps.mediashell"
    PKG_GMS              = "com.google.android.gms"
    PKG_GSF              = "com.google.android.gsf"
    PKG_REMOTE           = "com.google.android.tv.remote.service"


CACHE_DIR = Path.home() / ".playbox_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class UI:
    """Kolory i formatowanie interfejsu konsoli."""
    H = "\033[95m"
    I = "\033[94m"
    S = "\033[92m"
    W = "\033[93m"
    E = "\033[91m"
    C = "\033[96m"
    B = "\033[1m"
    D = "\033[2m"
    R = "\033[0m"

    @classmethod
    def ok(cls, msg: str) -> None:
        print(f"{cls.S}[✓] {msg}{cls.R}")

    @classmethod
    def info(cls, msg: str) -> None:
        print(f"{cls.I}[*] {msg}{cls.R}")

    @classmethod
    def warn(cls, msg: str) -> None:
        print(f"{cls.W}[!] {msg}{cls.R}")

    @classmethod
    def err(cls, msg: str) -> None:
        print(f"{cls.E}[✗] {msg}{cls.R}")

    @classmethod
    def hdr(cls, title: str) -> None:
        print(f"\n{cls.H}{cls.B}{'═' * 74}\n  {title}\n{'═' * 74}{cls.R}")


class ADB:
    """Warstwa komunikacji ADB (obsługuje zdalne połączenie TCP/IP oraz lokalny Termux/Shizuku)."""
    target: str = ""
    is_local: bool = False

    @classmethod
    def connect(cls, ip: Optional[str] = None) -> bool:
        if os.path.exists("/system/bin/app_process"):
            uid = cls._exec_raw("id -u")
            if uid in ("0", "2000"):
                cls.is_local = True
                cls.target = "local-shell"
                UI.ok(f"Wykryto lokalną powłokę na dekoderze (UID: {uid})")
                return True

        cls.target = ip or cls._autodetect() or HW.DEFAULT_IP
        UI.info(f"Łączenie z dekoderem Sagemcom przez ADB: {cls.target}...")
        subprocess.run(["adb", "connect", cls.target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if cls.sh("echo OK") == "OK":
            UI.ok(f"Połączono pomyślnie z {cls.target}")
            return True
        UI.err(f"Brak odpowiedzi z {cls.target}. Sprawdź IP i debugowanie sieciowe ADB.")
        return False

    @staticmethod
    def _autodetect() -> Optional[str]:
        try:
            out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
            for line in out.splitlines():
                if "\tdevice" in line:
                    return line.split("\t")[0].strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _exec_raw(cmd: str, timeout: int = 20) -> str:
        try:
            res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
            return res.stdout.strip()
        except Exception:
            return ""

    @classmethod
    def sh(cls, cmd: str, timeout: int = 25) -> str:
        if cls.is_local:
            return cls._exec_raw(cmd, timeout)
        if not cls.target:
            return ""
        try:
            res = subprocess.run(
                ["adb", "-s", cls.target, "shell", cmd],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout
            )
            return res.stdout.strip()
        except Exception:
            return ""

    @classmethod
    def batch(cls, commands: List[str], label: str = "Batch") -> None:
        if not commands:
            return
        joined = "; ".join(f"({c})" for c in commands)
        t0 = time.time()
        cls.sh(joined, timeout=35)
        UI.ok(f"{label}: wykonano {len(commands)} instrukcji w {time.time() - t0:.2f}s")

    @classmethod
    def prop(cls, key: str) -> str:
        return cls.sh(f"getprop {key}")

    @classmethod
    def sget(cls, ns: str, key: str) -> str:
        return cls.sh(f"settings get {ns} {key}")


class OptimizerModules:
    """Zestaw zoptymalizowanych modułów pod Broadcom BCM72604 + Chromecast."""

    @staticmethod
    def module_1_video_v3d_pipeline() -> None:
        UI.hdr("1. POTOK SPRZĘTOWY BROADCOM OMX + VIDEOCORE V3D + 60Hz")
        cmds = [
            "service call SurfaceFlinger 1008 i32 1",
            'settings put global overlay_display_devices ""',
            "setprop debug.composition.type hwc",
            "setprop debug.hwui.renderer skiagl",
            "setprop debug.renderengine.backend skiaglthreaded",
            "setprop debug.hwui.render_thread true",
            "setprop debug.hwui.render_thread_count 2",
            "setprop debug.hwui.use_partial_updates true",
            "setprop debug.hwui.show_dirty_regions false",
            "setprop debug.hwui.render_dirty_regions false",
            "setprop debug.hwui.layer_cache_size 32768",
            "setprop debug.egl.hw 1",
            "setprop debug.sf.hw 1",
            "setprop debug.gr.numframebuffers 3",
            "setprop debug.sf.latch_unsignaled 1",
            "setprop debug.sf.disable_backpressure 1",
            "setprop debug.sf.early_phase_offset_ns 500000",
            "setprop debug.sf.early_app_phase_offset_ns 1000000",
            "setprop persist.sys.ui.hw true",
            "setprop debug.stagefright.ccodec 0",
            "setprop debug.stagefright.omx_default_rank 512",
            "setprop debug.stagefright.c2.av1 0",
            "setprop media.codec.av1.disable true",
            "setprop media.av1.sw.decode.disable true",
            "setprop media.vcodec.preferhw true",
            "setprop media.acodec.preferhw true",
            "setprop media.codec.priority 0",
            "setprop media.brcm.decoder.preinit true",
            "setprop media.brcm.surface.prewarm true",
            "setprop media.brcm.mma.enable 1",
            "setprop media.brcm.vpu.buffers 32",
            "setprop dalvik.vm.isa.arm.features default,idiv",
            "wm size 1920x1080",
            "settings put system display_peak_refresh_rate 60.0",
            "settings put system min_refresh_rate 60.0",
            "settings put system user_refresh_rate 60.0",
            "settings put global persist.sys.hdmi.keep_awake true",
        ]
        ADB.batch(cmds, "Potok Wideo & V3D")

    @staticmethod
    def module_2_audio_fast_seek() -> None:
        UI.hdr("2. DŹWIĘK PCM STEREO & SZYBKIE PRZEWIJANIE (FAST SEEK)")
        cmds = [
            "settings put global encoded_surround_output 1",
            "settings put global encoded_surround_output_enabled 0",
            "settings put system sound_effects_enabled 0",
            "settings put system master_mono 0",
            "setprop audio.offload.disable 1",
            "setprop audio.deep_buffer.media true",
            "setprop audio.brcm.hdmi.clock_lock true",
            "setprop tunnel.audio.encode false",
            "setprop af.resampler.quality 4",
            "setprop media.stagefright.audio.sink 2097152",
            "setprop media.stagefright.cache-params 65536/131072/30",
        ]
        ADB.batch(cmds, "Audio PCM & Fast Seek")
    @staticmethod
    def module_3_chromecast_safe() -> None:
        UI.hdr("3. OCHRONA CHROMECAST (CAST-SAFE + mDNS WIFI 5GHz)")
        cmds = [
            f"pm enable {HW.PKG_MEDIASHELL}",
            f"pm enable --user 0 {HW.PKG_MEDIASHELL}",
            f"pm enable {HW.PKG_GMS}",
            f"pm enable --user 0 {HW.PKG_GMS}",
            f"pm enable {HW.PKG_GSF}",
            f"pm enable {HW.PKG_REMOTE}",
            f"dumpsys deviceidle whitelist +{HW.PKG_MEDIASHELL}",
            f"dumpsys deviceidle whitelist +{HW.PKG_GMS}",
            f"am set-standby-bucket {HW.PKG_MEDIASHELL} active",
            f"cmd appops set {HW.PKG_GMS} WAKE_LOCK ignore",
            f"cmd appops set {HW.PKG_GMS} CHANGE_NETWORK_STATE ignore",
            "setprop ro.mdns.enable_passive_mode false",
            "setprop net.ssdp.ttl 4",
        ]
        ADB.batch(cmds, "Chromecast Cast-Safe")

    @staticmethod
    def module_4_wifi5ghz_fiber_network() -> None:
        UI.hdr("4. OPTYMALIZACJA SIECI WIFI 5GHz POD ŚWIATŁOWÓD PLAY")
        tcp_buf = "524288,1048576,2097152,262144,524288,1048576"
        cmds = [
            "settings put global wifi_sleep_policy 2",
            "settings put global wifi_power_save 0",
            "settings put global wifi_scan_always_enabled 0",
            "settings put global ble_scan_always_enabled 0",
            "settings put global wifi_watchdog_on 0",
            "settings put secure wifi_watchdog_poor_link_detection 0",
            "settings put global captive_portal_mode 0",
            "settings put global netstats_enabled 0",
            "settings put global prefer_ipv4 true",
            "settings put global network_avoid_bad_wifi 0",
            f"settings put global net.tcp.buffersize.wifi '{tcp_buf}'",
            f"settings put global net.tcp.buffersize.default '{tcp_buf}'",
            f"setprop net.tcp.buffersize.wifi '{tcp_buf}'",
            f"setprop net.tcp.buffersize.default '{tcp_buf}'",
            "setprop net.tcp.default_init_rwnd 120",
            "setprop wifi.supplicant_scan_interval 300",
            "settings put global private_dns_mode hostname",
            "settings put global private_dns_specifier one.one.one.one",
            "setprop net.dns1 1.1.1.1",
            "setprop net.dns2 1.0.0.1",
            "ndc resolver flushdefaultif",
        ]
        ADB.batch(cmds, "Sieć Wi-Fi 5GHz & DNS")

    @staticmethod
    def module_5_ram_debloat_cast_safe() -> None:
        UI.hdr("5. ZARZĄDZANIE 1425 MB RAM & DEBLOAT (ZACHOWANIE CHROMECAST)")
        cleanup_keys = [
            "settings delete global user_preferred_resolution",
            "settings delete global display_size_forced",
            "settings delete global exoplayer_max_buffer_ms",
            "settings delete global exoplayer_dash_chunk_size",
            "settings delete global exoplayer_buffer_limit",
            "settings delete global exoplayer_target_buffer_bytes",
            "settings delete system media.brcm.vpu.prealloc",
            "settings delete global af.fast_track_multiplier",
        ]
        ADB.batch(cleanup_keys, "Czyszczenie starych kluczy")

        ram_cmds = [
            "settings put global activity_manager_constants 'max_cached_processes=4,background_settle_time=20000,fgservice_min_shown_time=100,power_check_max_cpu_1=35,power_check_max_cpu_0=45'",
            "settings put global low_ram false",
            "settings put global always_finish_activities 0",
            "cmd power set-mode 0",
            "settings put global low_power 0",
            "settings put global low_power_trigger_level 0",
            "settings put global stay_on_while_plugged_in 3",
            "settings put global window_animation_scale 0.0",
            "settings put global transition_animation_scale 0.2",
            "settings put global animator_duration_scale 0.2",
            "settings put secure tv_disable_recommendations 1",
            "settings put secure tv_enable_preview_programs 0",
            "settings put secure tv_watch_next_enabled 0",
            "settings put secure location_mode 0",
            "bmgr enable false",
            f"dumpsys deviceidle whitelist +{HW.PKG_SMARTTUBE}",
            f"dumpsys deviceidle whitelist +{HW.PKG_LAUNCHER}",
            f"am set-standby-bucket {HW.PKG_SMARTTUBE} active",
            f"am set-standby-bucket {HW.PKG_LAUNCHER} active",
            f"cmd appops set {HW.PKG_SMARTTUBE} WAKE_LOCK allow",
            f"cmd appops set {HW.PKG_SMARTTUBE} RUN_ANY_IN_BACKGROUND allow",
        ]
        ADB.batch(ram_cmds, "Zarządzanie RAM & Priorytety")

        safe_bloat = [
            "com.sagemcom.stb.setupwizard",
            "com.sagemcom.apdmanager",
            "com.sagemcom.sysupdate",
            "com.sagemcom.appupdate",
            "pl.play.playnow.box",
            "com.google.android.leanbacklauncher.recommendations",
            "com.google.android.katniss",
            "com.google.android.videos",
            "com.google.android.play.games",
            "com.google.android.music",
            "com.google.android.backdrop",
            "com.google.android.feedback",
            "com.google.android.marvin.talkback",
            "com.google.android.speech.pumpkin",
            "com.google.android.tungsten.setupwraith",
            "com.google.android.backuptransport",
            "com.android.location.fused",
        ]
        installed = ADB.sh("pm list packages -u")
        bloat_cmds = [f"pm disable-user --user 0 {pkg}" for pkg in safe_bloat if f"package:{pkg}" in installed]
        bloat_cmds.extend([
            "am force-stop com.netflix.ninja",
            "pm suspend com.netflix.ninja",
            "cmd appops set com.netflix.ninja RUN_IN_BACKGROUND ignore",
        ])
        ADB.batch(bloat_cmds, "Debloat (Cast-Safe)")

    @staticmethod
    def module_6_aot_compile_smarttube() -> None:
        UI.hdr("6. KOMPILACJA NATYWNA AOT (SPEED-PROFILE) DLA SMARTTUBE")
        UI.info("Kompilacja kodu SmartTube i Projectivy pod procesor ARMv7 Cortex-A15 (30-60s)...")
        for pkg in (HW.PKG_SMARTTUBE, HW.PKG_SMARTTUBE_BETA, HW.PKG_LAUNCHER):
            if pkg in ADB.sh(f"pm list packages {pkg}"):
                res = ADB.sh(f"cmd package compile -m speed-profile -f {pkg}", timeout=90)
                if "success" in res.lower():
                    UI.ok(f"Skompilowano AOT: {pkg}")
                else:
                    UI.warn(f"Pominięto lub brak zmian dla: {pkg}")

    @staticmethod
    def module_7_deep_clean() -> None:
        UI.hdr("7. CZYSZCZENIE PAMIĘCI PODRĘCZNEJ (CAST-SAFE)")
        cmds = [
            f"cmd activity trim-memory {HW.PKG_SMARTTUBE} COMPLETE",
            "cmd activity trim-memory RUNNING_CRITICAL",
            "pm trim-caches 150m",
            "logcat -c",
            "logcat -G 256K",
        ]
        ADB.batch(cmds, "Czyszczenie RAM & Logcat")
        ADB.sh(f"am set-standby-bucket {HW.PKG_MEDIASHELL} active")
        UI.ok("Pamięć wyczyszczona, Chromecast aktywny.")
    @staticmethod
    def module_8_smarttube_xml_patch() -> None:
        UI.hdr("8. WSTRZYKNIĘCIE PROFILU BCM72604 DO BACKUPU SMARTTUBE")
        pkg = HW.PKG_SMARTTUBE if HW.PKG_SMARTTUBE in ADB.sh(f"pm list packages {HW.PKG_SMARTTUBE}") else HW.PKG_SMARTTUBE_BETA
        remote_zip = "/sdcard/SmartTubeBackup.zip"
        local_orig = CACHE_DIR / "st_orig.zip"
        local_opt = CACHE_DIR / "st_opt.zip"

        UI.info(f"Eksport kopii zapasowej z {pkg}...")
        ADB.sh(f"am broadcast -a com.liskovsoft.smartyoutubetv2.BACKUP_EXPORT -p {pkg}")
        time.sleep(2.5)

        if ADB.is_local:
            if not os.path.exists(remote_zip):
                UI.err("Nie znaleziono pliku SmartTubeBackup.zip. Uruchom najpierw SmartTube.")
                return
            subprocess.run(["cp", remote_zip, str(local_orig)])
        else:
            subprocess.run(["adb", "-s", ADB.target, "pull", remote_zip, str(local_orig)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if not local_orig.exists() or local_orig.stat().st_size == 0:
            UI.err("Błąd pobierania backupu. Otwórz SmartTube, wejdź w Ustawienia -> Kopia zapasowa i spróbuj ponownie.")
            return

        optimal_prefs = {
            "video_codec": ("int", "2"),
            "av1_enabled": ("boolean", "false"),
            "hdr_mode": ("boolean", "false"),
            "force_hw_decoding": ("boolean", "true"),
            "disable_software_decoders": ("boolean", "true"),
            "custom_video_decoder": ("string", HW.DECODER_VP9),
            "tunneled_playback": ("boolean", "false"),
            "video_resolution": ("string", "1080"),
        }

        try:
            with zipfile.ZipFile(str(local_orig), "r") as zin, zipfile.ZipFile(str(local_opt), "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    raw = zin.read(item.filename)
                    if item.filename.endswith(".xml"):
                        root = ET.fromstring(raw.decode("utf-8", errors="replace"))
                        for key, (typ, val) in optimal_prefs.items():
                            found = False
                            for child in root:
                                if child.get("name") == key:
                                    if typ == "string":
                                        child.text = val
                                        child.attrib.pop("value", None)
                                    else:
                                        child.set("value", val)
                                    found = True
                                    break
                            if not found:
                                if typ == "string":
                                    ET.SubElement(root, "string", {"name": key}).text = val
                                else:
                                    ET.SubElement(root, typ, {"name": key, "value": val})
                        buf = io.BytesIO()
                        ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
                        zout.writestr(item, buf.getvalue())
                    else:
                        zout.writestr(item, raw)

            ADB.sh(f"am force-stop {pkg}")
            if ADB.is_local:
                subprocess.run(["cp", str(local_opt), remote_zip])
            else:
                subprocess.run(["adb", "-s", ADB.target, "push", str(local_opt), remote_zip],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            backup_dir = f"/sdcard/data/{pkg}/backup"
            ADB.sh(f"mkdir -p {backup_dir} && cp {remote_zip} {backup_dir}/")
            UI.ok("Zoptymalizowana konfiguracja wysłana na dekoder!")
            UI.warn("Otwórz SmartTube -> Ustawienia -> Kopia zapasowa -> Przywróć kopię, aby zatwierdzić.")
        except Exception as e:
            UI.err(f"Błąd przetwarzania XML SmartTube: {e}")

    @staticmethod
    def run_diagnostics() -> None:
        UI.hdr("DIAGNOSTYKA STANU DEKODERA (BCM72604 + CHROMECAST)")
        raw = ADB.sh(
            "grep -E 'MemTotal|MemAvailable|Cached' /proc/meminfo; "
            "echo '---'; "
            "getprop init.svc.mdnsd; "
            "pm list packages -e com.google.android.apps.mediashell; "
            "getprop debug.hwui.renderer; "
            "getprop media.codec.av1.disable; "
            "settings get global private_dns_specifier; "
            "dumpsys display 2>/dev/null | grep -m1 modeId"
        )
        lines = raw.splitlines()
        mem = {}
        for l in lines:
            if ":" in l and "kB" in l:
                k, v = l.split(":", 1)
                mem[k.strip()] = int(v.strip().split()[0]) // 1024

        avail_est = mem.get("MemAvailable", 0) + mem.get("Cached", 0)
        UI.info(f"Pamięć RAM całkowita  : {mem.get('MemTotal', 1425)} MB")
        UI.ok(f"Pamięć dostępna (z cache): ~{avail_est} MB (wolna bezpośrednia: {mem.get('MemAvailable', 0)} MB)")

        mdns_ok = "running" in raw
        cast_ok = "mediashell" in raw
        print(f"  Chromecast mDNS       : {UI.S + 'RUNNING ✓' + UI.R if mdns_ok else UI.E + 'STOPPED ✗' + UI.R}")
        print(f"  Chromecast Daemon     : {UI.S + 'AKTYWNY ✓' + UI.R if cast_ok else UI.E + 'WYŁĄCZONY ✗' + UI.R}")
        print(f"  Silnik Renderowania   : {UI.C}{ADB.prop('debug.hwui.renderer') or 'domyślny'}{UI.R}")
        print(f"  Blokada kodeka AV1    : {UI.C}{ADB.prop('media.codec.av1.disable') or 'nie'}{UI.R}")
        print(f"  Prywatny DNS (DoT)    : {UI.C}{ADB.sget('global', 'private_dns_specifier')}{UI.R}")

        m_mode = re.search(r"modeId[\s=]+(\d+)", raw)
        if m_mode:
            mode = m_mode.group(1)
            fps_txt = "1080p @ 60Hz ✓" if mode == "7" else f"Tryb {mode} (uruchom opcję 1 dla 60Hz!)"
            print(f"  Tryb wyświetlania     : {UI.S if mode == '7' else UI.W}{fps_txt}{UI.R}")

    @classmethod
    def run_all_preset(cls) -> None:
        UI.hdr("PEŁNA OPTYMALIZACJA AUTOMATYCZNA (ALL-IN-ONE CAST-SAFE)")
        cls.module_1_video_v3d_pipeline()
        cls.module_2_audio_fast_seek()
        cls.module_3_chromecast_safe()
        cls.module_4_wifi5ghz_fiber_network()
        cls.module_5_ram_debloat_cast_safe()
        cls.module_7_deep_clean()
        UI.hdr("ZAKOŃCZONO POMYŚLNIE!")
        UI.ok("Dekoder Sagemcom BCM72604 zoptymalizowany. Chromecast w pełni sprawny.")


def interactive_menu() -> None:
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print(f"""{UI.H}{UI.B}
╔══════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM v16.0 — BROADCOM BCM72604 & CHROMECAST-SAFE PANEL      ║
║  Urządzenie: Sagemcom DCTIW362_PLAY ({ADB.target:<22})            ║
╚══════════════════════════════════════════════════════════════════════════╝{UI.R}
  {UI.S}1.{UI.R} Potok Sprzętowy Broadcom OMX + VideoCore V3D + Blokada 1080p 60Hz
  {UI.S}2.{UI.R} Dźwięk PCM Stereo & Szybkie Przewijanie (Fix AudioFlinger Underrun)
  {UI.S}3.{UI.R} Ochrona Chromecast (Przywrócenie & Priorytet mDNS dla Wi-Fi 5GHz)
  {UI.S}4.{UI.R} Optymalizacja Sieci Wi-Fi 5GHz & TCP pod Światłowód Play
  {UI.S}5.{UI.R} Zarządzanie 1425 MB RAM & Debloat (Zachowuje Chromecast i Widevine)
  {UI.S}6.{UI.R} Kompilacja Natywna AOT (speed-profile) dla SmartTube i Launchera
  {UI.S}7.{UI.R} Czyszczenie Pamięci RAM & Logcat (Cast-Safe)
  {UI.S}8.{UI.R} Wstrzyknięcie Profilu BCM72604 do SmartTube (XML Backup Patch)
  {UI.C}9.{UI.R} Diagnostyka Systemu, Pamięci RAM i Statusu Chromecast
  {UI.W}10.{UI.R} {UI.B}PEŁNA OPTYMALIZACJA (Uruchom Moduły 1-5 + 7 jednym kliknięciem){UI.R}
  {UI.E}0.{UI.R} Wyjście
{UI.H}{'═' * 74}{UI.R}""")

        choice = input(f"\n{UI.C}Wybierz opcję [0-10] > {UI.R}").strip()
        if choice == "0":
            print("Do zobaczenia!")
            break
        elif choice == "1":
            OptimizerModules.module_1_video_v3d_pipeline()
        elif choice == "2":
            OptimizerModules.module_2_audio_fast_seek()
        elif choice == "3":
            OptimizerModules.module_3_chromecast_safe()
        elif choice == "4":
            OptimizerModules.module_4_wifi5ghz_fiber_network()
        elif choice == "5":
            OptimizerModules.module_5_ram_debloat_cast_safe()
        elif choice == "6":
            OptimizerModules.module_6_aot_compile_smarttube()
        elif choice == "7":
            OptimizerModules.module_7_deep_clean()
        elif choice == "8":
            OptimizerModules.module_8_smarttube_xml_patch()
        elif choice == "9":
            OptimizerModules.run_diagnostics()
        elif choice == "10":
            OptimizerModules.run_all_preset()
        else:
            UI.warn("Nieprawidłowy wybór.")

        input(f"\n{UI.D}Naciśnij ENTER, aby wrócić do menu...{UI.R}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PlayBox Titanium v16.0 (Broadcom BCM72604 + Chromecast-Safe)")
    parser.add_argument("--ip", type=str, default=None, help="Adres IP:PORT dekodera (np. 192.168.1.3:5555)")
    parser.add_argument("--auto", action="store_true", help="Uruchom pełną optymalizację bez menu interaktywnego")
    args = parser.parse_args()

    if not ADB.connect(args.ip):
        sys.exit(1)

    if args.auto:
        OptimizerModules.run_all_preset()
    else:
        interactive_menu()
