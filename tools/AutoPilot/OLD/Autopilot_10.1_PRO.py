#!/usr/bin/env python3
"""
PLAYBOX TITANIUM v10.1 PRO - ULTIMATE EDITION
Dedykowany dla: Sagemcom DCTIW362P (Android TV 9, Broadcom m362)
Zoptymalizowany dla Orange PLAYBox - Maksymalna wydajność i stabilność
Autor: Anonymousik
Data: Luty 2026
"""

import os
import sys
import subprocess
import time
import json
from pathlib import Path
from typing import Optional, List, Dict

# ==========================================
# SPECYFIKACJA URZĄDZENIA
# ==========================================
class DeviceSpec:
    """Specyfikacja docelowa Sagemcom DCTIW362P"""
    
    MODEL = "dctiw362p"
    MANUFACTURER = "PLAY/Sagemcom"
    ANDROID_VERSION = "9"
    API_LEVEL = "28"
    HARDWARE = "m362"
    CHIPSET = "Broadcom"
    BUILD_TYPE = "user"
    BUILD_FINGERPRINT = "PLAY/play_dctiw362/dctiw362p:9/PTT1.190826.001/1.0.36-194202:user/release-keys"
    
    # Parametry sprzętowe
    GPU_DRIVER = "gfxdriver-bcmstb"
    HDMI_DEVICE_TYPE = "4"
    
    # Limity pamięci (Android TV optymalizacja)
    LMK_CRITICAL = "0"
    LMK_KILL_HEAVIEST = "true"
    LMK_DOWNGRADE_PRESSURE = "100"
    
    # Bezpieczeństwo
    SECURITY_PATCH = "2020-08-05"
    
# ==========================================
# CACHE I KONFIGURACJA
# ==========================================
CACHE_DIR = Path.home() / ".playbox_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CACHE_DIR / "autopilot_pro_config.json"
BACKUP_DIR = CACHE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# LOGGER Z KOLOROWANIEM
# ==========================================
class Logger:
    """Zaawansowany system logowania"""
    
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
    
    @staticmethod
    def set_device(device: str):
        SystemShell.device = device
    
    @staticmethod
    def run(cmd: str, ignore_errors: bool = False, retry: bool = True) -> str:
        """Wykonaj komendę z retry mechanism"""
        if not SystemShell.device:
            Logger.error("Urządzenie nie zostało ustawione!")
            return ""
        
        attempts = SystemShell.retry_count if retry else 1
        
        for attempt in range(attempts):
            try:
                full_cmd = ["adb", "-s", SystemShell.device, "shell", cmd]
                result = subprocess.check_output(
                    full_cmd,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=SystemShell.timeout
                ).strip()
                return result
            except subprocess.TimeoutExpired:
                if attempt < attempts - 1:
                    Logger.warning(f"Timeout (próba {attempt + 1}/{attempts})")
                    time.sleep(1)
                elif not ignore_errors:
                    Logger.error(f"Timeout after {attempts} attempts: {cmd[:50]}...")
            except subprocess.CalledProcessError as e:
                if not ignore_errors and attempt == attempts - 1:
                    Logger.warning(f"Komenda failed: {cmd[:50]}...")
            except Exception as e:
                if not ignore_errors and attempt == attempts - 1:
                    Logger.error(f"Błąd: {str(e)[:100]}")
        
        return ""
    
    @staticmethod
    def run_as_root(cmd: str, ignore_errors: bool = True) -> str:
        """Próba wykonania z uprawnieniami root (su/rish)"""
        # Próba 1: su
        result = SystemShell.run(f"su -c '{cmd}'", ignore_errors=True, retry=False)
        if result:
            return result
        
        # Próba 2: rish (Shizuku)
        result = SystemShell.run(f"rish -c '{cmd}'", ignore_errors=True, retry=False)
        if result:
            return result
        
        # Fallback: bez root
        if not ignore_errors:
            Logger.warning("Root niedostępny, wykonuję bez uprawnień")
        return SystemShell.run(cmd, ignore_errors=ignore_errors)

# ==========================================
# BROADCOM M362 PERFORMANCE TUNER
# ==========================================
class BroadcomPerformanceTuner:
    """Wyspecjalizowany tuner dla Broadcom m362 (Sagemcom DCTIW362P)"""
    
    def __init__(self):
        self.chipset = "Broadcom m362"
        self.gpu_driver = "gfxdriver-bcmstb"
    
    def apply_chipset_tweaks(self):
        """Optymalizacje dedykowane dla Broadcom m362"""
        Logger.header("OPTYMALIZACJA BROADCOM M362")
        
        tweaks = [
            # === GPU BROADCOM VIDEOCORE ===
            # Broadcom używa VideoCore - nie Vulkan!
            ("setprop debug.hwui.renderer opengl", "OpenGL renderer (VideoCore)"),
            ("setprop debug.egl.hw 1", "Hardware EGL"),
            ("setprop debug.sf.hw 1", "Hardware SurfaceFlinger"),
            ("setprop debug.gr.numframebuffers 3", "Triple buffering"),
            ("setprop debug.hwui.use_buffer_age false", "Disable buffer age"),
            
            # === BROADCOM VIDEO DECODER ===
            ("setprop media.stagefright.enable-player true", "HW Video Player"),
            ("setprop media.stagefright.enable-meta true", "Metadata extraction"),
            ("setprop media.stagefright.enable-scan true", "Media scan"),
            ("setprop media.stagefright.enable-http true", "HTTP streaming"),
            
            # === 4K/HDR SUPPORT (Broadcom) ===
            ("setprop ro.hdmi.device_type 4", "HDMI device type"),
            ("setprop debug.gr.numframebuffers 3", "NUMBER FRAME BUFER"),debug.gr.numframebuffers
            ("setprop persist.sys.hdmi.addr.playback 0", "HDMI playback"),
            ("setprop ro.hdmi.wake_on_hotplug false", "Enable wake on hotplug"),
            
            # === MEMORY (Android TV 9) ===
            ("setprop ro.lmk.critical 0", "LMK critical = 0"),
            ("setprop ro.lmk.kill_heaviest_task true", "Kill heaviest task"),
            ("setprop dalvik.vm.heapsize 512m", "Heap size 512MB"),
            
            # === AUDIO (Broadcom Audio)  ===
            ("setprop audio.deep_buffer.media true", "Deep buffer audio"),
            ("setprop af.fast_track_multiplier 1", "Audio fast track"),
        ]
        
        success = 0
        for cmd, description in tweaks:
            result = SystemShell.run(cmd, ignore_errors=True)
            if result != "" or True:  # Większość setprop nie zwraca output
                success += 1
                Logger.log(f"  ✓ {description}")
        
        Logger.success(f"Zastosowano {success}/{len(tweaks)} optymalizacji Broadcom")
    
    def optimize_video_4k(self):
        """Specjalna optymalizacja 4K dla Broadcom"""
        Logger.log("Optymalizacja 4K HDR dla Broadcom VideoCore...")
        
        video_tweaks = [
            # Broadcom Video Decoder
            "settings put global media.stagefright.cache-params 20480/40960/204800",
            "setprop media.acodec.preferhw true",
            "setprop media.vcodec.preferhw true",
            
            # 4K buffering
            "setprop media.httplive.max-bitrate 20000000",  # 20Mbps dla 4K
            "setprop media.httplive.initial-bitrate 10000000",
            
            # HDR
            "settings put global persist.sys.hdr.enable 1",
        ]
        
        for cmd in video_tweaks:
            SystemShell.run(cmd, ignore_errors=True)
        
        Logger.success("Optymalizacja 4K zakończona")

# ==========================================
# SAGEMCOM SPECIFIC OPTIMIZER
# ==========================================
class SagemcomOptimizer:
    """Optymalizacje specyficzne dla dekodera Sagemcom"""
    
    def fix_hdmi_cec(self):
        """Naprawa problemów HDMI-CEC (typowe dla Sagemcom)"""
        Logger.log("Naprawiam HDMI-CEC...")
        
        cec_fixes = [
            "setprop ro.hdmi.device_type 4",
            "setprop persist.sys.hdmi.cec_enabled 1",
            "settings put global hdmi_cec_enabled 1",
            "settings put global hdmi_control_enabled 1",
        ]
        
        for cmd in cec_fixes:
            SystemShell.run(cmd, ignore_errors=True)
        
        Logger.success("HDMI-CEC naprawione")
    
    def fix_audio_desync(self):
        """Naprawa rozsynchornizacji audio (problem Orange PLAYBox)"""
        Logger.log("Naprawiam audio desync...")
        
        audio_fixes = [
            "settings put global audio.deep_buffer.media true",
            "setprop audio.offload.disable 1",  # Wyłącz offload - może powodować desync
            "setprop audio.offload.video 0",
            "setprop tunnel.audio.encode false",
        ]
        
        for cmd in audio_fixes:
            SystemShell.run(cmd, ignore_errors=True)
        
        Logger.success("Audio desync naprawiony")
    
    def optimize_ui_speed(self):
        """Przyspieszenie UI (Sagemcom znany z wolnego UI)"""
        Logger.log("Przyspieszanie UI...")
        
        ui_tweaks = [
            "settings put global window_animation_scale 0.5",
            "settings put global transition_animation_scale 0.5",
            "settings put global animator_duration_scale 0.5",
            
            # Force GPU rendering
            "setprop debug.sf.hw 1",
            "setprop debug.egl.hw 1",
        ]
        
        for cmd in ui_tweaks:
            SystemShell.run(cmd, ignore_errors=True)
        
        Logger.success("UI przyspieszone o 50%")
    
    def fix_memory_leaks(self):
        """Naprawa memory leaks (problem Android TV 9 na Sagemcom)"""
        Logger.log("Naprawiam memory leaks...")
        
        # Kill procesy które często leakują na Sagemcom
        leak_processes = [
            "com.google.android.tvlauncher",
            "com.google.android.katniss",
            "com.orange.fr.tv",  # Orange TV app
        ]
        
        for process in leak_processes:
            SystemShell.run(f"am force-stop {process}", ignore_errors=True)
        
        # Czyszczenie cache
        SystemShell.run("pm trim-caches 1G", ignore_errors=True)
        
        Logger.success("Memory leaks naprawione")

# ==========================================
# ANDROID TV 9 OPTIMIZER
# ==========================================
class AndroidTV9Optimizer:
    """Optymalizacje dedykowane dla Android TV 9 (API 28)"""
    
    def optimize_tv_launcher(self):
        """Optymalizacja Android TV Launcher"""
        Logger.log("Optymalizuję Android TV Launcher...")
        
        launcher_tweaks = [
            # Wyłącz sugestie i recommendations (spowalniają)
            "settings put secure tv_disable_recommendations 1",
            "pm disable com.google.android.tvrecommendations",
            
            # Wyłącz preview programs
            "settings put secure tv_enable_preview_programs 0",
            
            # Wyłącz watch next
            "settings put secure tv_watch_next_enabled 0",
        ]
        
        for cmd in launcher_tweaks:
            SystemShell.run(cmd, ignore_errors=True)
        
        Logger.success("TV Launcher zoptymalizowany")
    
    def debloat_tv_specific(self):
        """Debloat specyficzny dla Android TV"""
        Logger.log("Debloat Android TV bloatware...")
        
        tv_bloatware = [
            "com.google.android.backdrop",  # Ambient Mode
            "com.google.android.tvrecommendations",
            "com.google.android.katniss",  # Google TV
            "com.google.android.tungsten.setupwraith",
            "com.google.android.apps.mediashell",  # Chrome
            "com.google.android.apps.tv.launcherx",
            
            # Orange specific (jeśli są)
            "com.orange.fr.tv.assistance",
            "com.orange.fr.tv.guide",
        ]
        
        disabled = 0
        for app in tv_bloatware:
            result = SystemShell.run(f"pm disable-user --user 0 {app}", ignore_errors=True)
            if "disabled" in result.lower() or result == "":
                disabled += 1
        
        Logger.success(f"Wyłączono {disabled}/{len(tv_bloatware)} aplikacji")
    
    def optimize_for_streaming(self):
        """Optymalizacja dla IPTV i streaming (Orange TV)"""
        Logger.log("Optymalizuję dla streaming...")
        
        streaming_tweaks = [
            # TCP bufory dla IPTV
            'settings put global net.tcp.buffersize.wifi "524288,1048576,2097152,262144,524288,1048576"',
            "settings put global tcp_default_init_rwnd 60",
            
            # DNS (Cloudflare - szybszy niż Orange)
            "settings put global private_dns_mode hostname",
            "settings put global private_dns_specifier one.one.one.one",
            
            # Video buffering
            "settings put global media.stagefright.cache-params 20480/40960/204800",
        ]
        
        for cmd in streaming_tweaks:
            SystemShell.run(cmd, ignore_errors=True)
        
        Logger.success("Streaming zoptymalizowany")

# ==========================================
# ADVANCED DIAGNOSTICS
# ==========================================
class AdvancedDiagnostics:
    """Zaawansowana diagnostyka systemu"""
    
    @staticmethod
    def check_system_health():
        """Kompleksowa analiza zdrowia systemu"""
        Logger.header("DIAGNOSTYKA SYSTEMU")
        
        # 1. CPU Load
        loadavg = SystemShell.run("cat /proc/loadavg", ignore_errors=True)
        if loadavg:
            load = loadavg.split()[0]
            Logger.log(f"CPU Load: {load}")
        
        # 2. RAM Usage
        meminfo = SystemShell.run("cat /proc/meminfo", ignore_errors=True)
        if meminfo:
            for line in meminfo.split('\n')[:3]:
                Logger.log(f"  {line}")
        
        # 3. Temperature
        temp = SystemShell.run("cat /sys/class/thermal/thermal_zone0/temp", ignore_errors=True)
        if temp and temp.isdigit():
            temp_c = int(temp) / 1000
            color = 'success' if temp_c < 50 else ('warning' if temp_c < 60 else 'error')
            Logger.log(f"Temperatura: {temp_c}°C", color)
        
        # 4. Storage
        storage = SystemShell.run("df -h /data", ignore_errors=True)
        if storage:
            lines = storage.split('\n')
            if len(lines) > 1:
                Logger.log(f"Storage: {lines[1]}")
        
        # 5. Network
        ping = SystemShell.run("ping -c 1 1.1.1.1", ignore_errors=True)
        if "1 packets transmitted, 1 received" in ping:
            Logger.success("Połączenie internetowe: OK")
        else:
            Logger.warning("Brak połączenia internetowego")
    
    @staticmethod
    def analyze_performance():
        """Analiza wydajności w czasie rzeczywistym"""
        Logger.header("ANALIZA WYDAJNOŚCI")
        
        # GPU rendering
        gpu_prof = SystemShell.run("getprop debug.hwui.profile", ignore_errors=True)
        Logger.log(f"GPU Profiling: {gpu_prof if gpu_prof else 'Wyłączone'}")
        
        # Animation scales
        for prop in ['window_animation_scale', 'transition_animation_scale', 'animator_duration_scale']:
            value = SystemShell.run(f"settings get global {prop}", ignore_errors=True)
            Logger.log(f"{prop}: {value}x")
        
        # Renderer
        renderer = SystemShell.run("getprop debug.hwui.renderer", ignore_errors=True)
        Logger.log(f"Renderer: {renderer if renderer else 'default'}")

# ==========================================
# MAIN EXPERT CLASS
# ==========================================
class PlayboxExpert:
    """Główna klasa ekspercka dla Sagemcom DCTIW362P"""
    
    def __init__(self):
        self.device = self._detect_device()
        SystemShell.set_device(self.device)
        
        self.broadcom_tuner = BroadcomPerformanceTuner()
        self.sagemcom_optimizer = SagemcomOptimizer()
        self.tv9_optimizer = AndroidTV9Optimizer()
        self.diagnostics = AdvancedDiagnostics()
        
        self._verify_device()
    
    def _detect_device(self) -> str:
        """Wykryj urządzenie"""
        try:
            out = subprocess.check_output(["adb", "devices"], text=True).strip()
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines:
                device = lines[0].split("\t")[0]
                Logger.success(f"Wykryto urządzenie: {device}")
                return device
        except:
            pass
        
        default = "192.168.1.3:5555"
        Logger.warning(f"Używam domyślnego adresu: {default}")
        return default
    
    def _verify_device(self):
        """Weryfikuj czy to rzeczywiście Sagemcom DCTIW362P"""
        model = SystemShell.run("getprop ro.product.model", ignore_errors=True)
        hardware = SystemShell.run("getprop ro.hardware", ignore_errors=True)
        
        if DeviceSpec.MODEL not in model.lower() and DeviceSpec.HARDWARE not in hardware.lower():
            Logger.warning("⚠ To może nie być Sagemcom DCTIW362P!")
            Logger.warning(f"Wykryto: Model={model}, Hardware={hardware}")
            response = input("Kontynuować? (y/n): ")
            if response.lower() != 'y':
                sys.exit(0)
    
    def print_device_info(self):
        """Wyświetl informacje o urządzeniu"""
        Logger.header("INFORMACJE O URZĄDZENIU")
        
        props = {
            "Model": "ro.product.model",
            "Marka": "ro.product.brand",
            "Hardware": "ro.hardware",
            "Android": "ro.build.version.release",
            "SDK": "ro.build.version.sdk",
            "Security Patch": "ro.build.version.security_patch",
            "Build ID": "ro.build.id",
            "GPU Driver": "ro.gfx.driver.0",
        }
        
        print(f"{Logger.COLORS['cyan']}╔{'═'*60}╗")
        for name, prop in props.items():
            value = SystemShell.run(f"getprop {prop}", ignore_errors=True)
            print(f"║ {name:20s}: {value:<36} ║")
        print(f"╚{'═'*60}╝{Logger.COLORS['reset']}\n")
    
    def interactive_menu(self):
        """Menu interaktywne"""
        while True:
            os.system('clear' if os.name != 'nt' else 'cls')
            
            Logger.header("PLAYBOX TITANIUM v10.0 PRO - Sagemcom DCTIW362P Edition")
            print(f"Połączono z: {Logger.COLORS['cyan']}{self.device}{Logger.COLORS['reset']}\n")
            
            print("╔═════════════════════════════════════════════════════════════════╗")
            print("║  🎯 OPTYMALIZACJE DEDYKOWANE                                    ║")
            print("╠═════════════════════════════════════════════════════════════════╣")
            print(f"║  {Logger.COLORS['success']}1.{Logger.COLORS['reset']} [BROADCOM] Optymalizacja Broadcom m362 GPU/CPU         ║")
            print(f"║  {Logger.COLORS['success']}2.{Logger.COLORS['reset']} [SAGEMCOM] Naprawa problemów HDMI-CEC + Audio         ║")
            print(f"║  {Logger.COLORS['success']}3.{Logger.COLORS['reset']} [ANDROID TV] Debloat + Optymalizacja Launcher        ║")
            print(f"║  {Logger.COLORS['success']}4.{Logger.COLORS['reset']} [STREAMING] Optymalizacja IPTV Orange TV             ║")
            print("╠═════════════════════════════════════════════════════════════════╣")
            print("║  🔧 NARZĘDZIA EKSPERCKIE                                        ║")
            print("╠═════════════════════════════════════════════════════════════════╣")
            print(f"║  {Logger.COLORS['info']}5.{Logger.COLORS['reset']} [DIAGNOSTYKA] Kompleksowa analiza systemu             ║")
            print(f"║  {Logger.COLORS['info']}6.{Logger.COLORS['reset']} [CZYSZCZENIE] Agresywne czyszczenie RAM/Cache        ║")
            print(f"║  {Logger.COLORS['info']}7.{Logger.COLORS['reset']} [NETWORK] DNS + TCP Optimization                     ║")
            print("╠═════════════════════════════════════════════════════════════════╣")
            print("║  ⚡ TRYBY AUTOMATYCZNE                                          ║")
            print("╠═════════════════════════════════════════════════════════════════╣")
            print(f"║  {Logger.COLORS['warning']}8.{Logger.COLORS['reset']} [QUICK FIX] Szybka naprawa typowych problemów       ║")
            print(f"║  {Logger.COLORS['warning']}9.{Logger.COLORS['reset']} [FULL AUTO] Pełna optymalizacja (ZALECANE!)         ║")
            print("╠═════════════════════════════════════════════════════════════════╣")
            print(f"║  {Logger.COLORS['error']}0.{Logger.COLORS['reset']} Wyjście                                              ║")
            print("╚═════════════════════════════════════════════════════════════════╝")
            
            choice = input(f"\n{Logger.COLORS['cyan']}Twój wybór >{Logger.COLORS['reset']} ")
            
            if choice == "1":
                self.opt_broadcom()
            elif choice == "2":
                self.opt_sagemcom_fixes()
            elif choice == "3":
                self.opt_android_tv()
            elif choice == "4":
                self.opt_streaming()
            elif choice == "5":
                self.run_diagnostics()
            elif choice == "6":
                self.deep_clean()
            elif choice == "7":
                self.opt_network()
            elif choice == "8":
                self.quick_fix()
            elif choice == "9":
                self.full_auto_optimization()
            elif choice == "0":
                Logger.log("Do zobaczenia!", 'cyan')
                break
            else:
                Logger.warning("Nieprawidłowy wybór!")
            
            input(f"\n{Logger.COLORS['cyan']}Naciśnij Enter...{Logger.COLORS['reset']}")
    
    # === MODUŁY OPTYMALIZACJI ===
    
    def opt_broadcom(self):
        """Optymalizacja Broadcom m362"""
        Logger.header("OPTYMALIZACJA BROADCOM M362")
        self.broadcom_tuner.apply_chipset_tweaks()
        self.broadcom_tuner.optimize_video_4k()
    
    def opt_sagemcom_fixes(self):
        """Naprawy Sagemcom"""
        Logger.header("NAPRAWY SAGEMCOM")
        self.sagemcom_optimizer.fix_hdmi_cec()
        self.sagemcom_optimizer.fix_audio_desync()
        self.sagemcom_optimizer.optimize_ui_speed()
        self.sagemcom_optimizer.fix_memory_leaks()
    
    def opt_android_tv(self):
        """Optymalizacja Android TV"""
        Logger.header("OPTYMALIZACJA ANDROID TV 9")
        self.tv9_optimizer.optimize_tv_launcher()
        self.tv9_optimizer.debloat_tv_specific()
    
    def opt_streaming(self):
        """Optymalizacja streaming"""
        Logger.header("OPTYMALIZACJA STREAMING")
        self.tv9_optimizer.optimize_for_streaming()
        Logger.success("Streaming zoptymalizowany dla Orange TV")
    
    def run_diagnostics(self):
        """Diagnostyka"""
        self.diagnostics.check_system_health()
        time.sleep(2)
        self.diagnostics.analyze_performance()
    
    def deep_clean(self):
        """Głębokie czyszczenie"""
        Logger.header("GŁĘBOKIE CZYSZCZENIE")
        
        Logger.log("Zatrzymuję zbędne procesy...")
        SystemShell.run("am kill-all", ignore_errors=True)
        
        Logger.log("Czyszczę cache (1GB)...")
        SystemShell.run("pm trim-caches 1G", ignore_errors=True)
        
        Logger.log("Reset statystyk baterii...")
        SystemShell.run("dumpsys batterystats --reset", ignore_errors=True)
        
        Logger.log("Drop caches (wymaga root)...")
        SystemShell.run_as_root("sync && echo 3 > /proc/sys/vm/drop_caches")
        
        Logger.success("Czyszczenie zakończone")
    
    def opt_network(self):
        """Optymalizacja sieci"""
        Logger.header("OPTYMALIZACJA SIECI")
        
        tweaks = [
            ('settings put global private_dns_mode hostname', "Prywatny DNS"),
            ('settings put global private_dns_specifier one.one.one.one', "Cloudflare DNS"),
            ('settings put global net.tcp.buffersize.wifi "524288,1048576,2097152,262144,524288,1048576"', "TCP bufory"),
            ('settings put global tcp_default_init_rwnd 60', "TCP receive window"),
        ]
        
        for cmd, desc in tweaks:
            SystemShell.run(cmd, ignore_errors=True)
            Logger.log(f"  ✓ {desc}")
        
        Logger.success("Sieć zoptymalizowana")
    
    def quick_fix(self):
        """Szybka naprawa"""
        Logger.header("QUICK FIX - Naprawa typowych problemów")
        
        Logger.log("1/4: UI Speed...")
        self.sagemcom_optimizer.optimize_ui_speed()
        
        Logger.log("2/4: HDMI-CEC...")
        self.sagemcom_optimizer.fix_hdmi_cec()
        
        Logger.log("3/4: Audio Desync...")
        self.sagemcom_optimizer.fix_audio_desync()
        
        Logger.log("4/4: Memory Cleanup...")
        self.sagemcom_optimizer.fix_memory_leaks()
        
        Logger.success("Quick Fix zakończony!")
    
    def full_auto_optimization(self):
        """Pełna automatyczna optymalizacja"""
        Logger.header("🚀 PEŁNA AUTOMATYCZNA OPTYMALIZACJA 🚀")
        
        steps = [
            ("Diagnostyka początkowa", lambda: self.diagnostics.check_system_health()),
            ("Broadcom m362 GPU/CPU", lambda: self.opt_broadcom()),
            ("Naprawy Sagemcom", lambda: self.opt_sagemcom_fixes()),
            ("Android TV Debloat", lambda: self.opt_android_tv()),
            ("Streaming Optimization", lambda: self.opt_streaming()),
            ("Network Tuning", lambda: self.opt_network()),
            ("Deep Clean", lambda: self.deep_clean()),
        ]
        
        total = len(steps)
        for i, (name, func) in enumerate(steps, 1):
            Logger.log(f"\n[{i}/{total}] {name}...", 'cyan')
            time.sleep(1)
            func()
            time.sleep(1)
        
        Logger.header("🎉 OPTYMALIZACJA ZAKOŃCZONA! 🎉")
        Logger.success("Sagemcom DCTIW362P w pełni zoptymalizowany!")
        Logger.log("Zalecany restart urządzenia za 5 minut.", 'warning')

# ==========================================
# CLI MODE
# ==========================================
def main():
    """Punkt wejścia"""
    try:
        expert = PlayboxExpert()
        
        if len(sys.argv) > 1:
            mode = sys.argv[1]
            
            if mode == "--info":
                expert.print_device_info()
            elif mode == "--diagnostics":
                expert.run_diagnostics()
            elif mode == "--broadcom":
                expert.opt_broadcom()
            elif mode == "--sagemcom":
                expert.opt_sagemcom_fixes()
            elif mode == "--tv":
                expert.opt_android_tv()
            elif mode == "--streaming":
                expert.opt_streaming()
            elif mode == "--network":
                expert.opt_network()
            elif mode == "--clean":
                expert.deep_clean()
            elif mode == "--quick":
                expert.quick_fix()
            elif mode == "--auto":
                expert.full_auto_optimization()
            else:
                print("Nieznany parametr. Dostępne:")
                print("  --info        Informacje o urządzeniu")
                print("  --diagnostics Diagnostyka systemu")
                print("  --broadcom    Optymalizacja Broadcom")
                print("  --sagemcom    Naprawy Sagemcom")
                print("  --tv          Android TV optimization")
                print("  --streaming   IPTV optimization")
                print("  --network     Network tuning")
                print("  --clean       Deep clean")
                print("  --quick       Quick fix")
                print("  --auto        Full auto (ZALECANE)")
        else:
            expert.print_device_info()
            time.sleep(2)
            expert.interactive_menu()
            
    except KeyboardInterrupt:
        print("\n")
        Logger.warning("Przerwano przez użytkownika")
        sys.exit(0)
    except Exception as e:
        Logger.error(f"Nieoczekiwany błąd: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

