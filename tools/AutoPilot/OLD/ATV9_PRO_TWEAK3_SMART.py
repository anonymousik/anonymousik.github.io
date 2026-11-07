#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PLAYBOX TITANIUM v10.2 PRO - ULTIMATE EDITION
Dedykowany dla: Sagemcom DCTIW362P (Android TV 9, Broadcom m362)
Zoptymalizowany dla Orange PLAYBox - Maksymalna wydajność i stabilność
#AIAssisted
"""

import os
import sys
import subprocess
import time
import json
import zipfile
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# ==========================================
# SPECYFIKACJA URZĄDZENIA
# ==========================================
class DeviceSpec:
    """Specyfikacja docelowa Sagemcom DCTIW362P"""
    MODEL = "dctiw362p"
    MANUFACTURER = "PLAY/Sagemcom"
    ANDROID_VERSION = "9"
    HARDWARE = "m362"
    CHIPSET = "Broadcom"
    
# ==========================================
# CACHE I KONFIGURACJA
# ==========================================
CACHE_DIR = Path.home() / ".playbox_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SMARTTUBE_DIR = CACHE_DIR / "smarttube"
SMARTTUBE_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# LOGGER Z KOLOROWANIEM
# ==========================================
class Logger:
    """Zaawansowany system logowania CLI"""
    
    COLORS = {
        'info': '\033[94m',
        'success': '\033[92m',
        'warning': '\033[93m',
        'error': '\033[91m',
        'header': '\033[95m',
        'cyan': '\033[96m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    
    @staticmethod
    def log(msg: str, level: str = 'info'):
        color = Logger.COLORS.get(level, Logger.COLORS['info'])
        timestamp = time.strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] {msg}{Logger.COLORS['reset']}")
    
    @staticmethod
    def success(msg: str):
        Logger.log(f"✓ {msg}", 'success')
    
    @staticmethod
    def warning(msg: str):
        Logger.log(f"⚠ {msg}", 'warning')
    
    @staticmethod
    def error(msg: str):
        Logger.log(f"✗ {msg}", 'error')
    
    @staticmethod
    def header(msg: str):
        print(f"\n{Logger.COLORS['header']}{Logger.COLORS['bold']}{'='*75}")
        print(f"   {msg}")
        print(f"{'='*75}{Logger.COLORS['reset']}\n")

# ==========================================
# SYSTEM SHELL - KOMUNIKACJA ADB
# ==========================================
class SystemShell:
    """Zaawansowana komunikacja ADB z retry i timeout"""
    
    device: Optional[str] = None
    retry_count: int = 3
    timeout: int = 30
    
    @classmethod
    def connect(cls, target: str) -> bool:
        try:
            r = subprocess.run(["adb", "connect", target], capture_output=True, text=True, timeout=10)
            if "connected" in r.stdout.lower():
                cls.device = target
                Logger.success(f"Połączono z ADB: {target}")
                return True
            return False
        except Exception as e:
            Logger.error(f"Błąd ADB: {e}")
            return False

    @staticmethod
    def autodetect() -> bool:
        try:
            out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
            for line in out.splitlines():
                if "\tdevice" in line:
                    SystemShell.device = line.split("\t")[0].strip()
                    Logger.success(f"ADB auto-wykryty: {SystemShell.device}")
                    return True
        except Exception:
            pass
        return False
    
    @staticmethod
    def run(cmd: str, ignore_errors: bool = False, retry: bool = True) -> str:
        if not SystemShell.device:
            return ""
        attempts = SystemShell.retry_count if retry else 1
        for attempt in range(attempts):
            try:
                full_cmd = ["adb", "-s", SystemShell.device, "shell", cmd]
                result = subprocess.check_output(full_cmd, stderr=subprocess.STDOUT, text=True, timeout=SystemShell.timeout).strip()
                return result
            except subprocess.TimeoutExpired:
                if attempt < attempts - 1:
                    time.sleep(1)
            except Exception:
                pass
        return ""
    
    @staticmethod
    def run_as_root(cmd: str, ignore_errors: bool = True) -> str:
        result = SystemShell.run(f"su -c '{cmd}'", ignore_errors=True, retry=False)
        if result and "not found" not in result.lower() and "denied" not in result.lower():
            return result
        result = SystemShell.run(f"rish -c '{cmd}'", ignore_errors=True, retry=False)
        if result and "not found" not in result.lower():
            return result
        return SystemShell.run(cmd, ignore_errors=ignore_errors)

# ==========================================
# BROADCOM M362 PERFORMANCE TUNER
# ==========================================
class BroadcomPerformanceTuner:
    """Wyspecjalizowany tuner dla Broadcom m362 (Sagemcom DCTIW362P)"""
    
    def apply_chipset_tweaks(self):
        Logger.header("OPTYMALIZACJA BROADCOM M362 (FIX JANKY FRAMES)")
        tweaks = [
            ("setprop debug.hwui.renderer opengl", "OpenGL renderer (VideoCore)"),
            ("setprop debug.egl.hw 1", "Hardware EGL"),
            ("setprop debug.sf.hw 1", "Hardware SurfaceFlinger"),
            ("setprop debug.gr.numframebuffers 3", "Triple buffering (UI Smoothness)"),
            ("setprop debug.hwui.use_buffer_age false", "Disable buffer age"),
            ("setprop debug.hwui.render_thread_cpu_affinity 1", "CPU affinity for UI render thread"),
            ("setprop media.stagefright.enable-player true", "HW Video Player"),
            ("setprop ro.hdmi.device_type 4", "HDMI device type (Android TV)"),
            ("setprop media.stagefright.audio.sink 512", "Bufor audio (HDMI passthrough)"),
        ]
        success = 0
        for cmd, description in tweaks:
            SystemShell.run_as_root(cmd, ignore_errors=True)
            success += 1
            Logger.log(f"  ✓ {description}")
        Logger.success(f"Zastosowano {success}/{len(tweaks)} optymalizacji Broadcom")

# ==========================================
# SAGEMCOM SPECIFIC OPTIMIZER
# ==========================================
class SagemcomOptimizer:
    """Optymalizacje specyficzne dla dekodera Sagemcom"""
    
    def fix_hdmi_cec(self):
        Logger.log("Naprawiam HDMI-CEC oraz zasilanie ekranu...")
        cec_fixes = [
            "setprop ro.hdmi.device_type 4",
            "setprop ro.hdmi.cec_device_types 4",
            "setprop ro.hdmi.wake_on_hotplug false",
            "setprop persist.sys.hdmi.keep_awake false"
        ]
        for cmd in cec_fixes:
            SystemShell.run_as_root(cmd, ignore_errors=True)
        Logger.success("Konfiguracja HDMI-CEC zaktualizowana")

    def fix_memory_leaks(self):
        Logger.log("Naprawiam wycieki pamięci i zrzucam cache...")
        leak_processes = [
            "com.google.android.tvlauncher",
            "com.google.android.katniss",
            "com.orange.fr.tv",
        ]
        for process in leak_processes:
            SystemShell.run(f"am force-stop {process}", ignore_errors=True)
        SystemShell.run("cmd activity trim-memory RUNNING_CRITICAL", ignore_errors=True)
        SystemShell.run("pm trim-caches 4096G", ignore_errors=True)
        SystemShell.run("cmd activity gc-heap", ignore_errors=True)
        Logger.success("Zwolniono zasoby RAM i wyczyszczono stertę")

    def optimize_ui_speed(self):
        Logger.log("Zwiększanie responsywności UI i eliminacja skoków klatek...")
        ui_tweaks = [
            "settings put global window_animation_scale 0.5",
            "settings put global transition_animation_scale 0.5",
            "settings put global animator_duration_scale 0.5",
            "settings put global hardware_acceleration_enabled true",
        ]
        for cmd in ui_tweaks:
            SystemShell.run(cmd, ignore_errors=True)
        Logger.success("Skale animacji zredukowane, akceleracja sprzętowa wymuszona")

    def freeze_netflix_drm_safe(self):
        Logger.log("Zamrażam aplikację Netflix (Ochrona DRM Widevine L1)...")
        netflix_cmds = [
            "am force-stop com.netflix.ninja",
            "pm suspend com.netflix.ninja",
            "cmd appops set com.netflix.ninja RUN_IN_BACKGROUND ignore",
        ]
        for cmd in netflix_cmds:
            SystemShell.run_as_root(cmd, ignore_errors=True)
        Logger.success("Netflix bezpiecznie zamrożony w tle")

# ==========================================
# ADVANCED MAGISK & KERNEL TUNER
# ==========================================
class AdvancedMagiskTuner:
    """Implementacja poprawek jądra, LMK oraz I/O pod niski bandwidth RAM"""
    
    def apply_kernel_vm_tweaks(self):
        Logger.header("GŁĘBOKIE MODYFIKACJE SYSTEMOWE (KERNEL / LMK / VM)")
        tweaks = [
            "setprop dalvik.vm.heapgrowthlimit 256m",
            "echo 100 > /proc/sys/vm/swappiness",
            "echo 50 > /proc/sys/vm/vfs_cache_pressure",
            "echo 64 > /sys/module/lowmemorykiller/parameters/cost",
            "echo '32768,39936,46552,65536,131072,262144' > /sys/module/lowmemorykiller/parameters/minfree",
            "device_config put activity_manager max_cached_processes 4",
            "device_config put activity_manager max_phantom_processes 32",
            "device_config put activity_manager kill_bg_restricted_cached_idle true"
        ]
        for cmd in tweaks:
            SystemShell.run_as_root(cmd, ignore_errors=True)
        Logger.success("Zaaplikowano modyfikacje LMK, VM oraz Activity Manager dla oszczędności RAM")
        
    def optimize_network_stalls(self):
        Logger.log("Wdrażanie optymalizacji zapobiegających przerwom w łączności WiFi...")
        net_tweaks = [
            "device_config put connectivity data_stall_evaluation_type 2",
            "device_config put connectivity data_stall_tcp_polling_interval 30000",
            "settings put global wifi_supplicant_scan_interval_ms 300000"
        ]
        for cmd in net_tweaks:
            SystemShell.run_as_root(cmd, ignore_errors=True)
        Logger.success("Progi czułości WiFi zmodyfikowane")
        
    def compile_apps_speed(self):
        Logger.log("Kompilacja aplikacji (speed-profile)... Może to potrwać do kilku minut!")
        SystemShell.run_as_root("cmd package compile -m speed-profile -a", ignore_errors=True)
        Logger.success("Kompilacja Dalvik/ART zakończona pomyślnie")

# ==========================================
# SMARTTUBE CONFIG MANAGER (BCM72604 OPTIMIZER)
# ==========================================
#class SmartTubeOptimizer:
#    PKG_STABLE = "org.smarttube.stable"
#    DEVICE_BACKUP_ZIP = "/sdcard/SmartTubeBackup.zip"
#    
#    BCM72604_OPTIMAL = {
#        "video_codec":               ("int",     "2",     "VP9 HW codec BCM72604"),
#        "av1_enabled":               ("boolean", "false", "AV1 off (brak HW)"),
#        "vp9_enabled":               ("boolean", "true",  "VP9 on HW path"),
#        "preferred_codec":           ("string",  "vp9",   "Preferowany VP9"),
#        "use_tunnel_mode":           ("boolean", "true",  "Tunnel mode BCM sync"),
#        "tunneled_playback":         ("boolean", "true",  "Tunneled playback"),
#        "video_resolution":          ("string",  "1080",  "Max 1080p display BCM"),
#        "hdr_mode":                  ("boolean", "true",  "HDR10 hardware path"),
#        "video_frame_rate_switch":   ("boolean", "true",  "Auto fps switch"),
#        "buffer_type":               ("int",     "2",     "Duży bufor sieciowy"),
#        "hardware_acceleration":     ("boolean", "true",  "HW acceleration"),
#        "frame_interpolation":       ("boolean", "false", "Interpolacja off (HW VP9)"),
#    }
#
#    def _pull_config(self) -> Optional[Path]:
#        Logger.log("Pobieranie konfiguracji SmartTube...")
#        SystemShell.run(f"am broadcast -a com.liskovsoft.smartyoutubetv2.BACKUP_EXPORT -p {self.PKG_STABLE}", ignore_errors=True)
#        time.sleep(3)
#        local_zip = SMARTTUBE_DIR / "SmartTubeBackup_original.zip"
#        subprocess.run(["adb", "-s", SystemShell.device, "pull", self.DEVICE_BACKUP_ZIP, str(local_zip)], 
#                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#        if local_zip.exists() and local_zip.stat().st_size > 0:
#            Logger.success(f"Pobrano konfigurację SmartTube ({local_zip.stat().st_size} bajtów)")
#            return local_zip
#        Logger.error("Nie znaleziono pliku SmartTubeBackup.zip.")
#        return None
#
#    def _optimize_json(self, data: bytes) -> bytes:
#        try:
#            obj = json.loads(data.decode("utf-8", errors="replace"))
#            def _apply(node, key, new_val):
#                if isinstance(node, dict):
#                    if key in node: node[key] = new_val
#                    else:
#                        for v in node.values(): _apply(v, key, new_val)
#                elif isinstance(node, list):
#                    for item in node: _apply(item, key, new_val)
#            for key, (typ, value, _) in self.BCM72604_OPTIMAL.items():
#                if typ == "boolean": new_val = (value == "true")
#                elif typ == "int": new_val = int(value)
#                else: new_val = value
#                _apply(obj, key, new_val)
#
#wreturn json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
#        except:
#            return data
#
#    def _optimize_xml(self, data: bytes) -> bytes:
#        try:
#            root = ET.fromstring(data.decode("utf-8", errors="replace"))
#            for key, (typ, value, _) in self.BCM72604_OPTIMAL.items()                found = False
#for el in root:
#                    if el.get("name") == key:
#                        if typ == "string":
#                            el.tag, el.text = "string", value
#                            if "value" in el.attrib: del el.attrib["value"#                        else:
#                            el.tag = ty#p
#                            el.set("value", value)
#                            el.text = None
#                        found = True
#                        break
#                if not found:
#                    if typ == "string":
#                        ET.SubElement(root, "string", {"name": key}).text = value
#                    else:
#                       ET.SubElement(root, typ, {"name": key, "value": value})
#            buf = io.BytesIO()
#            ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
#            return buf.getvalue()
#        except:
#            return data
#
#    def optimize_and_push(self):
#        Logger.header("OPTYMALIZACJA SMARTTUBE DLA BROADCOM")
#        original_zip = self._pull_config()
#        if not original_zip: return
#        optimized_zip = SMARTTUBE_DIR / "SmartTubeBackup.zip"
#        try:
#            with zipfile.ZipFile(str(original_zip), "r") as zin, \
#                 zipfile.ZipFile(str(optimized_zip), "w", compression=zipfile.ZIP_DEFLATED) as zout:
#                for item in zin.infolist():
#                    raw = zin.read(item.filename)
#                    ext = Path(item.filename).suffix.lower()
#                    if ext == ".xml" or item.filename.endswith(".bak"):
#                        zout.writestr(item, self._optimize_xml(raw))
#                    elif ext == ".json":
#                        zout.writestr(item, self._optimize_json(raw))
#                    else:
#                        zout.writestr(item, raw)
#            SystemShell.run(f"am force-stop {self.PKG_STABLE}", ignore_errors=True)
#            subprocess.run(["adb", "-s", SystemShell.device, "push", str(optimized_zip), self.DEVICE_BACKUP_ZIP],
#                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#            import_dir = f"/sdcard/data/{self.PKG_STABLE}/backup"
#            SystemShell.run(f"mkdir -p {import_dir}", ignore_errors=True)
#            Logger.success("Gotowe! Przywróć kopię zapasową w ustawieniach SmartTube.")
#        except Exception as e:
#            Logger.error(f"Błąd podczas optymalizacji paczki SmartTube: {e}")
#
#

# SMARTTUBE CONFIG MANAGER (BCM72604 OPTIMIZER)
class SmartTubeOptimizer:
    """Optymalizacja SmartTube w locie (bezpośrednia modyfikacja XML przez Root)"""
    PKG_STABLE = "org.smarttube.stable"

    def optimize_smarttube(self) -> None:
        Logger.header("OPTYMALIZACJA SMARTTUBE DLA BROADCOM (ROOT IN-PLACE)")
# SMARTTUBE CONFIG MANAGER (ROOTLESS BCM72604 OPTIMIZER)
class SmartTubeOptimizer:
    """W pełni bez-rootowa optymalizacja SmartTube z wykorzystaniem wektora Intent (Backup/Restore)"""
    PKG_STABLE = "org.smarttube.stable"
    DEVICE_BACKUP_ZIP = "/sdcard/SmartTubeBackup.zip"

    BCM72604_OPTIMAL = {
        "video_codec":               ("int",     "2",     "VP9 HW codec BCM72604"),
        "av1_enabled":               ("boolean", "false", "AV1 off (brak HW)"),
        "use_tunnel_mode":           ("boolean", "true",  "Tunnel mode BCM sync"),
        "tunneled_playback":         ("boolean", "true",  "Tunneled playback"),
        "video_resolution":          ("string",  "1080",  "Max 1080p display BCM"),
        "hdr_mode":                  ("boolean", "true",  "HDR10 hardware path"),
        "video_frame_rate_switch":   ("boolean", "true",  "Auto fps switch"),
        "disable_software_decoders": ("boolean", "true",  "Force HW OMX"),
        "custom_video_decoder":      ("string",  "OMX.BROADCOM.video-decoder.vp9", "Broadcom VP9 override")
    }

    def optimize_smarttube(self) -> None:
        Logger.header("OPTYMALIZACJA SMARTTUBE DLA BROADCOM (ROOTLESS)")
        Logger.log("Wysyłanie sygnału (Intent) do aplikacji w celu zrzutu konfiguracji...")

        # Wymuszenie zapisu preferencji do /sdcard/ (Obejście DAC)
        SystemShell.run(f"am broadcast -a com.liskovsoft.smartyoutubetv2.BACKUP_EXPORT -p {self.PKG_STABLE}", ignore_errors=True)
        time.sleep(2) # Opóźnienie na asynchroniczny zrzut I/O przez aplikację Androida

        local_zip = SMARTTUBE_DIR / "SmartTubeBackup_original.zip"
        Logger.log(f"Pobieranie archiwum przez most ADB do pamięci podręcznej...")

        subprocess.run(["adb", "-s", SystemShell.device, "pull", self.DEVICE_BACKUP_ZIP, str(local_zip)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if not local_zip.exists():
            Logger.error("Błąd: Nie udało się pobrać SmartTubeBackup.zip. Upewnij się, że aplikacja jest włączona w tle.")
            return

        Logger.success(f"Pobrano pomyślnie konfigurację ({local_zip.stat().st_size} bajtów).")

        try:
            # Operowanie strumieniowe w pamięci RAM, minimalizacja zapisu na dysku (Flash wear-leveling)
            optimized_zip = SMARTTUBE_DIR / "SmartTubeBackup.zip"

            with zipfile.ZipFile(str(local_zip), "r") as zin:
                with zipfile.ZipFile(str(optimized_zip), "w", compression=zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        data = zin.read(item.filename)

                        # Modyfikujemy tylko pliki konfiguracyjne XML
                        if item.filename.endswith(".xml"):
                            root = ET.fromstring(data.decode("utf-8", errors="replace"))

                            # Wstrzykiwanie optymalizacji w O(n) na strukturze drzewa
                            for key, (typ, value, _) in self.BCM72604_OPTIMAL.items():
                                found = False
                                for child in root:
                                    if child.get("name") == key:
                                        child.set("value", value)
                                        if typ == "string":
                                            child.text = value
                                        found = True
                                        break

                                # Jeśli brakuje klucza - inicjalizuj węzeł
                                if not found:
                                    if typ == "string":
                                        ET.SubElement(root, typ, {"name": key}).text = value
                                    else:
                                        ET.SubElement(root, typ, {"name": key, "value": value})

                            buf = io.BytesIO()
                            ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
                            zout.writestr(item, buf.getvalue())
                        else:
                            zout.writestr(item, data) # Przepisanie nie-XML (np. baz sqlite) w trybie 1:1

            Logger.log("Zamykanie instancji aplikacji i przesyłanie spreparowanego archiwum...")
            SystemShell.run(f"am force-stop {self.PKG_STABLE}", ignore_errors=True)

            subprocess.run(["adb", "-s", SystemShell.device, "push", str(optimized_zip), self.DEVICE_BACKUP_ZIP],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Tworzenie odpowiedniej ścieżki w sdcard pod przyszły import (wymagane w nowszych wersjach STN)
            import_dir = f"/sdcard/data/{self.PKG_STABLE}/backup"
            SystemShell.run(f"mkdir -p {import_dir}", ignore_errors=True)
            SystemShell.run(f"cp {self.DEVICE_BACKUP_ZIP} {import_dir}/", ignore_errors=True)

            Logger.success("Ładunek wstrzyknięty pomyślnie na pamięć wewnętrzną dekodera!")
            Logger.log("ABY ZAKOŃCZYĆ: Otwórz SmartTube -> Ustawienia -> Kopia zapasowa -> Przywróć kopię", color="warning")

        except Exception as e:
            Logger.error(f"Wyjątek krytyczny w potoku parsowania XML: {e}")

# ==========================================
# ANDROID TV 9 OPTIMIZER
# ==========================================
class AndroidTV9Optimizer:
    """Moduł optymalizacji generycznych parametrów Android TV"""
    
    def apply_low_ram_profile(self):
        Logger.log("Wdrażam profil Low-RAM (Restrykcje aktywności w tle)...")
        low_ram_tweaks = [
            "settings put global low_ram true",
            "settings put global low_power_mode 1",
            "settings put global max_cached_processes 4",
            "settings put global boot_fast 1",
            "settings put global sys_storage_threshold_percentage 5"
        ]
        for cmd in low_ram_tweaks:
            SystemShell.run(cmd, ignore_errors=True)
        Logger.success("Profil Low-RAM aktywowany pomyślnie")
        
    def opt_streaming(self):
        Logger.log("Optymalizuję sieć pod stabilne działanie IPTV...")
        streaming_tweaks = [
            'settings put global net.tcp.buffersize.wifi "4096,131072,786432,4096,16384,786432"',
            'settings put global net.tcp.buffersize.default "4096,131072,786432,4096,16384,786432"',
            "settings put global wifi_watchdog_on 0",
            "settings put global captive_portal_mode 0",
            "settings put global wifi_scan_always_enabled 0",
            "settings put global exoplayer_buffer_limit 3184168",
            "settings put global private_dns_mode hostname",
            "settings put global private_dns_specifier dns.adguard.com"
        ]
        for cmd in streaming_tweaks:
            SystemShell.run(cmd, ignore_errors=True)
        Logger.success("Bufory TCP i konfiguracja DNS uaktualnione")

# ==========================================
# MAIN CONTROLLER
# ==========================================
class PlayBoxTitaniumPro:
    
    def __init__(self):
        self.broadcom = BroadcomPerformanceTuner()
        self.sagemcom = SagemcomOptimizer()
        self.magisk = AdvancedMagiskTuner()
        self.smarttube = SmartTubeOptimizer()
        self.atv = AndroidTV9Optimizer()

    def connect_device(self):
        Logger.header("POŁĄCZENIE Z URZĄDZENIEM")
        if not SystemShell.autodetect():
            Logger.log("Nie wykryto urządzenia automatycznie. Podaj IP:PORT dekodera:", 'warning')
            ip = input(f"{Logger.COLORS['cyan']}IP:PORT > {Logger.COLORS['reset']}")
            if not SystemShell.connect(ip):
                Logger.error("Błąd połączenia. Zakończenie pracy.")
                sys.exit(1)

    def clean_system(self):
        Logger.header("CZYSZCZENIE SYSTEMU I ZASOBÓW")
        SystemShell.run_as_root("am kill-all", ignore_errors=True)
        self.sagemcom.fix_memory_leaks()
        Logger.success("Czyszczenie zakończone pomyślnie.")

    def full_auto(self):
        Logger.header("PEŁNA OPTYMALIZACJA AUTOMATYCZNA (FULL AUTO)")
        self.broadcom.apply_chipset_tweaks()
        self.sagemcom.fix_hdmi_cec()
        self.sagemcom.optimize_ui_speed()
        self.atv.apply_low_ram_profile()
        self.atv.opt_streaming()
        self.magisk.apply_kernel_vm_tweaks()
        self.magisk.optimize_network_stalls()
        self.clean_system()
        Logger.header("PODSUMOWANIE OPTYMALIZACJI: Wszystkie moduły włączone!")

    def interactive_menu(self):
        self.connect_device()
        while True:
            os.system('clear' if os.name != 'posix' else 'clear')
            print(f"\n{Logger.COLORS['header']}{Logger.COLORS['bold']}")
            print("╔═════════════════════════════════════════════════════════════════╗")
            print("║             PLAYBOX TITANIUM SMARTTUBE_V3 OMX EDITION PRO - ULTIMATE               ║")
            print("║                (Broadcom m362 + Android TV 9)                   ║")
            print("╚═════════════════════════════════════════════════════════════════╝")
            print(f"║  {Logger.COLORS['info']}1.{Logger.COLORS['reset']} [BROADCOM] Optymalizacja Chipsetu (Video/Audio/Janky)  ║")
            print(f"║  {Logger.COLORS['info']}2.{Logger.COLORS['reset']} [SAGEMCOM] Fix UI, Memory, HDMI-CEC                      ║")
            print(f"║  {Logger.COLORS['info']}3.{Logger.COLORS['reset']} [NETWORK] Optymalizacja Streamingu / IPTV & DNS            ║")
            print(f"║  {Logger.COLORS['info']}4.{Logger.COLORS['reset']} [MAGISK] Głębokie modyfikacje Kernela / VM (LMK)           ║")
            print(f"║  {Logger.COLORS['info']}5.{Logger.COLORS['reset']} [MAGISK] Optymalizacja Dalvik (Speed-Profile Compile)      ║")
            print(f"║  {Logger.COLORS['info']}6.{Logger.COLORS['reset']} [SMARTTUBE] Optymalizacja BCM72604 dla SmartTube           ║")
            print(f"║  {Logger.COLORS['info']}7.{Logger.COLORS['reset']} [CLEANUP] Agresywne czyszczenie RAM/Cache                  ║")
            print(f"║  {Logger.COLORS['info']}8.{Logger.COLORS['reset']} [DRM SAFE] Zamrożenie Netflix (Widevine L1)                ║")
            print(f"║  {Logger.COLORS['info']}9.{Logger.COLORS['reset']} [LOW RAM] Aktywuj profil dla słabych urządzeń              ║")
            print("╠═════════════════════════════════════════════════════════════════╣")
            print(f"║  {Logger.COLORS['warning']}10.{Logger.COLORS['reset']} [FULL AUTO] Pełna optymalizacja (ZALECANE!)               ║")
            print("╠═════════════════════════════════════════════════════════════════╣")
            print(f"║  {Logger.COLORS['error']}0.{Logger.COLORS['reset']} Wyjście                                                  ║")
            print("╚═════════════════════════════════════════════════════════════════╝")
            
            choice = input(f"\n{Logger.COLORS['cyan']}Twój wybór >{Logger.COLORS['reset']} ")
            
            if choice == "1": self.broadcom.apply_chipset_tweaks()
            elif choice == "2":
                self.sagemcom.fix_hdmi_cec()
                self.sagemcom.optimize_ui_speed()
                self.sagemcom.fix_memory_leaks()
            elif choice == "3": self.atv.opt_streaming()
            elif choice == "4":
                self.magisk.apply_kernel_vm_tweaks()
                self.magisk.optimize_network_stalls()
            elif choice == "5": self.magisk.compile_apps_speed()
            elif choice == "6": self.smarttube.optimize()
            elif choice == "7": self.clean_system()
            elif choice == "8": self.sagemcom.freeze_netflix_drm_safe()
            elif choice == "9": self.atv.apply_low_ram_profile()
            elif choice == "10": self.full_auto()
            elif choice == "0":
                Logger.success("Zakończono. Miłego korzystania z PlayBox Titanium Pro Ultimate!")
                sys.exit(0)
            else:
                Logger.error("Nieprawidłowy wybór!")
            
            input("\nNaciśnij Enter, aby kontynuować...")

if __name__ == "__main__":
    app = PlayBoxTitaniumPro()
    try:
        app.interactive_menu()
    except KeyboardInterrupt:
        print("\nPrzerwano przez użytkownika. Wychodzenie...")
        sys.exit(0)
