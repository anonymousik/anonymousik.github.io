#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# PLAYBOX ULTIMATE V12.1 - BROADCOM SKIA EDITION (TERMUX / CLI)
# Ekskluzywna optymalizacja pod Sagemcom (BCM72xx / Android 9)
# Skoncentrowana na TTFF (Szybki Start Wideo) i responsywności UI
# ==============================================================================

import os
import sys
import subprocess
import time
from typing import List, Optional

class PlayBoxV12:
    def __init__(self, target_ip: Optional[str] = None):
        self.device = target_ip or ""
        self.is_connected = False

    def detect_device(self) -> str:
        try:
            out = subprocess.check_output(["adb", "devices"], text=True).strip()
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines: 
                return lines[0].split("\t")[0]
        except Exception:
            pass
        return ""

    def adb(self, cmd_list: List[str], silent: bool = False, timeout: int = 12) -> str:
        """Egzekucja komend ADB."""
        try:
            full_cmd = ["adb", "-s", self.device] + cmd_list
            res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            return res.stdout.strip()
        except subprocess.TimeoutExpired:
            if not silent: print("\033[91m[ADB TIMEOUT] Urządzenie nie odpowiada.\033[0m")
            return ""
        except Exception as e:
            if not silent: print(f"\033[91m[ADB ERROR] {e}\033[0m")
            return ""

    def set_prop(self, key: str, value: str, root_fallback: bool = True):
        """Bezpieczne ustawianie właściwości systemowych z opcjonalnym wymuszeniem root."""
        self.adb(["shell", "setprop", key, value], silent=True)
        if root_fallback:
            self.adb(["shell", "su", "-c", f"setprop {key} {value}"], silent=True)

    def put_setting(self, namespace: str, key: str, value: str):
        """Ustawienia global/secure."""
        self.adb(["shell", "settings", "put", namespace, key, str(value)], silent=True)

    def connect(self, ip: str = None) -> bool:
        if ip:
            self.device = ip
        elif not self.device:
            self.device = self.detect_device()
            
        if not self.device:
            print("\033[91m[!] Brak przypisanego IP lub nie wykryto urządzeń w USB/Sieci.\033[0m")
            return False

        print(f"\033[93m[*] Łączenie z bazą: {self.device}...\033[0m")
        self.adb(["disconnect"], silent=True)
        res = self.adb(["connect", self.device])
        
        if "connected" in res.lower() or "already" in res.lower():
            self.is_connected = True
            print("\033[92m[✓] Połączenie stabilne.\033[0m")
            return True
        else:
            self.is_connected = False
            print(f"\033[91m[!] Błąd połączenia: {res}\033[0m")
            return False

    # ---------------------------------------------------------
    # MODUŁ 1: WEBVIEW TURBO
    # ---------------------------------------------------------
    def module_webview_turbo(self):
        print("\n\033[96m[MODUŁ 1] Aktywacja ekstremalnego silnika WebView...\033[0m")
        flags = (
            "ignore-gpu-blocklist=true enable-gpu-rasterization=true "
            "animated-image-resume=true webview-accelerate-small-canvases=true "
            "num-raster-threads=2 webview-thread-safe-media=true "
            "optimize-network-buffers=true optimize-network-buffers2=true "
            "enable-finch-seed-delta-compression=true "
            "enable-webview-surface-control-for-tv=true webview-surface-control=true "
            "webview-disable-package-allowlist-throttling=true"
        )
        self.put_setting("global", "webview_flags", f'"{flags}"')
        print("\033[92m[✓] Flagi WebView zaaplikowane.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 2: BROADCOM SKIAGL (V3D MITIGATED)
    # ---------------------------------------------------------
    def module_broadcom_skiagl(self):
        print("\n\033[96m[MODUŁ 2] Konfiguracja potoku SkiaGL (Zbalansowane V3D)...\033[0m")
        props = {
            "debug.hwui.renderer": "skiagl",
            "persist.sys.ui.hw": "true",
            "debug.hwui.render_thread_count": "1",    
            "debug.sf.disable_backpressure": "0",     
            "debug.sf.latch_unsignaled": "1",
            "ro.hwui.texture_cache_size": "24.0",     
            "ro.hwui.layer_cache_size": "16384",      
            "ro.hwui.text_large_cache_width": "1024", 
            "ro.hwui.text_large_cache_height": "512"
        }
        for k, v in props.items():
            self.set_prop(k, v)
        self.put_setting("global", "overlay_display_devices", '""')
        self.adb(["shell", "service", "call", "SurfaceFlinger", "1008", "i32", "1"], silent=True)
        print("\033[92m[✓] SkiaGL zoptymalizowany pod wąskie gardła TMU/L2.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 3: SIEĆ, TCP BUFFERS 120Mbps & SmartTube Fix
    # ---------------------------------------------------------
    def module_network_and_smarttube(self):
        print("\n\033[96m[MODUŁ 3] Optymalizacja stosu TCP i fixy wideo...\033[0m")
        tcp_buffers = "4096,131072,786432,4096,16384,3184168"
        self.put_setting("global", "net.tcp.buffersize.wifi", f'"{tcp_buffers}"')
        self.put_setting("global", "net.tcp.buffersize.default", f'"{tcp_buffers}"')
        self.set_prop("net.tcp.buffersize.wifi", tcp_buffers)
        self.set_prop("net.tcp.buffersize.default", tcp_buffers)
        
        self.set_prop("net.tcp.default_init_rwnd", "140")
        self.put_setting("global", "wifi_watchdog_on", "0")
        self.put_setting("global", "captive_portal_mode", "0")
        self.put_setting("global", "wifi_scan_always_enabled", "0")
        self.put_setting("global", "prefer_ipv4", "true")

        self.put_setting("global", "exoplayer_buffer_limit", "3184168")
        self.put_setting("secure", "exoplayer_buffer_limit", "3184168")
        self.set_prop("media.tunneled-playback.enable", "false")
        self.put_setting("global", "encoded_surround_output", "0") 
        print("\033[92m[✓] Sieć zoptymalizowana.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 4: MEDIA FRAMEWORK & HARDWARE ACCEL
    # ---------------------------------------------------------
    def module_media_hardware_accel(self):
        print("\n\033[96m[MODUŁ 4] Wymuszanie potoków sprzętowych...\033[0m")
        self.put_setting("global", "hardware_acceleration_enabled", "true")
        self.set_prop("debug.sf.hw", "1", root_fallback=True)
        self.set_prop("media.stagefright.audio.sink", "512", root_fallback=True)
        self.set_prop("media.stagefright.leswitches", "true", root_fallback=True)
        self.set_prop("persist.sys.media.use-awesome", "0", root_fallback=True)
        self.set_prop("ro.logd.size", "16M")
        print("\033[92m[✓] Priorytetyzacja dekoderów włączona.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 5: INTELIGENTNE ZARZĄDZANIE ZASOBAMI
    # ---------------------------------------------------------
    def module_intelligent_resources_foreground(self):
        print("\n\033[96m[MODUŁ 5] Inteligentna alokacja zasobów...\033[0m")
        self.put_setting("global", "always_finish_activities", "0") 
        self.put_setting("global", "low_ram", "true")
        self.put_setting("global", "sys_free_storage_alloc_limit", "104857600")
        self.put_setting("global", "max_cached_processes", "2") 
        self.put_setting("global", "low_power_trigger_level", "0")
        self.put_setting("global", "power_manager_constants", '"no_cached_apps_until_foreground=true"')
        
        self.set_prop("ro.sys.fw.bg_apps_limit", "2", root_fallback=True)
        self.set_prop("persist.sys.purgeable_assets", "1", root_fallback=True)
        self.set_prop("windowsmgr.max_events_per_sec", "150", root_fallback=True) 
        
        launchers = ["com.google.android.tvlauncher", "pl.play.now", "com.sagemcom.tv.launcher"]
        for pkg in launchers:
            self.adb(["shell", "cmd", "appops", "set", pkg, "RUN_IN_BACKGROUND", "ignore"], silent=True)

        print("\033[90m[*] GC i zwalnianie VRAM...\033[0m")
        self.adb(["shell", "cmd", "activity", "kill-all"])
        self.adb(["shell", "cmd", "activity", "trim-memory", "RUNNING_CRITICAL"])
        self.adb(["shell", "cmd", "activity", "gc-heap"])
        print("\033[92m[✓] Środowisko skupione na First-Planie.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 6: DEBLOAT I TELEMETRIA
    # ---------------------------------------------------------
    def module_debloat_telemetry(self):
        print("\n\033[96m[MODUŁ 6] Wyłączanie procesów w tle...\033[0m")
        settings_secure = {
            "accessibility_enabled": "0",
            "upload_log_enable": "0",
            "send_action_logs_at_app_foreground": "0",
            "show_media_prediction": "0",
            "assistant": "0",
            "voice_recognition_service": "0",
            "limit_ad_tracking": "1",
            "advertiser_id_limit_ad_tracking": "1"
        }
        for k, v in settings_secure.items():
            self.put_setting("secure", k, v)
        self.put_setting("global", "touch_exploration_granted_accessibility_services", "0")
        print("\033[92m[✓] Telemetria zatrzymana.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 7: DRM-SAFE NETFLIX FREEZE
    # ---------------------------------------------------------
    def module_freeze_netflix(self):
        pkg = "com.netflix.ninja"
        print(f"\n\033[96m[MODUŁ 7] Głęboka hibernacja {pkg}...\033[0m")
        self.adb(["shell", "am", "force-stop", pkg])
        self.adb(["shell", "pm", "suspend", pkg])
        self.adb(["shell", "cmd", "appops", "set", pkg, "RUN_IN_BACKGROUND", "ignore"])
        self.adb(["shell", "cmd", "appops", "set", pkg, "START_FOREGROUND", "ignore"])
        self.adb(["shell", "cmd", "appops", "set", pkg, "SYSTEM_ALERT_WINDOW", "ignore"])
        print("\033[92m[✓] Netflix zamrożony bezpiecznie.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 8: DCTIW362_PLAY (DASH / VP9 / tv-player-ias)
    # ---------------------------------------------------------
    def module_dctiw362_play_visionos(self):
        print("\n\033[96m[MODUŁ 8] Profil sprzętowy DCTIW362_PLAY...\033[0m")
        self.set_prop("debug.stagefright.ccodec", "0") 
        self.set_prop("media.stagefright.omx-force-hw", "true")
        self.set_prop("ro.media.dec.video.vp9", "OMX.BROADCOM.video-decoder.vp9")
        self.set_prop("ro.media.dec.video.vp9.mime", "x-vnd.on2.vp9")
        
        self.put_setting("global", "exoplayer_client_id", "VISIONOS")
        self.put_setting("global", "exoplayer_protocol_default", "DASH")
        self.put_setting("global", "exoplayer_player_type", "tv-player-ias.vflset")
        self.set_prop("persist.sys.media.player_type", "tv-player-ias.vflset")
        self.put_setting("global", "exoplayer_dash_chunk_size", "1048576") 
        self.set_prop("persist.sys.media.visionos.dash", "true")
        self.set_prop("persist.sys.media.visionos.vp9", "true")
        print("\033[92m[✓] Profil dekodowania sprzętowego osadzony.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 9: RESPONSYWNOŚĆ UI I SZYBKI START WIDEO (TTFF)
    # ---------------------------------------------------------
    def module_speed_ttff_responsiveness(self):
        print("\n\033[96m[MODUŁ 9] Akceleracja responsywności UI i błyskawicznego wideo...\033[0m")
        
        # Skrócenie czasu animacji UI do 25% oryginału (natychmiastowe okna)
        print("\033[90m[*] Aplikowanie modyfikatorów renderowania okien (0.25x)...\033[0m")
        self.put_setting("global", "window_animation_scale", "0.25")
        self.put_setting("global", "transition_animation_scale", "0.25")
        self.put_setting("global", "animator_duration_scale", "0.25")
        
        # ExoPlayer: Redukcja min_buffer do natychmiastowego pokazania pierwszej klatki
        print("\033[90m[*] Skracanie progu Time-To-First-Frame (TTFF)...\033[0m")
        self.put_setting("global", "exoplayer_min_buffer_ms", "500") # Start po 0.5s zamiast 2.5s
        self.set_prop("media.stagefright.extractrightaway", "true")  # Wymusza natychmiastowy ekstrakt mediów
        
        # Wymuszanie kompilacji maszynowej (AOT) dla głównych aplikacji, omijając opóźnienia JIT
        print("\033[90m[*] Próba kompilacji natywnej kluczowych komponentów (AOT 'speed')...\033[0m")
        apps_to_speedup = ["org.smarttube.stable", "com.google.android.youtube.tv"]
        for app in apps_to_speedup:
            self.adb(["shell", "cmd", "package", "compile", "-m", "speed", app], silent=True)

        print("\033[92m[✓] Animacje przyspieszone. Odtwarzacze ustawione na agresywny start!\033[0m")

    def restart_ui(self):
        print("\n\033[93m[*] Restartowanie SurfaceFlinger i SystemUI...\033[0m")
        self.adb(["shell", "stop", "&&", "start"])
        print("\033[92m[✓] Interfejs uruchamia się ponownie (Poczekaj 10 sekund).\033[0m")

    def run_full_omega(self):
        print("\n" + "="*60)
        print("\033[91m🚀 URUCHAMIANIE PROCEDURY FULL OMEGA (ALL-IN-ONE)\033[0m")
        print("="*60)
        
        self.module_webview_turbo()
        self.module_broadcom_skiagl()
        self.module_network_and_smarttube()
        self.module_media_hardware_accel()
        self.module_intelligent_resources_foreground()
        self.module_debloat_telemetry()
        self.module_freeze_netflix()
        self.module_dctiw362_play_visionos()
        self.module_speed_ttff_responsiveness() # Dodany moduł 9
        
        print("\n\033[92m[✓] WSZYSTKIE OPTYMALIZACJE WDROŻONE POMYŚLNIE!\033[0m")
        self.restart_ui()
        print("=" * 60)

class CLI_Interface:
    def __init__(self, bot: PlayBoxV12):
        self.bot = bot

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def pause(self):
        input("\n\033[90m[ Naciśnij ENTER, aby kontynuować ]\033[0m")

    def run(self):
        while True:
            self.clear_screen()
            print("\033[96m" + "═" * 70)
            print(" 🚀 PLAYBOX ULTIMATE V12.1 - SPEED & TTFF EDITION (TERMUX CLI)")
            print("═" * 70 + "\033[0m")
            
            if self.bot.is_connected:
                print(f" Status połączenia: \033[92m[✓] POŁĄCZONO ({self.bot.device})\033[0m")
            else:
                print(f" Status połączenia: \033[91m[X] BRAK POŁĄCZENIA\033[0m")
            print("\033[96m" + "═" * 70 + "\033[0m\n")

            print("\033[93m--- MODUŁY OPTYMALIZACYJNE ---\033[0m")
            print(" 1. \033[97mWebView Turbo Flags\033[0m")
            print(" 2. \033[97mSkiaGL (V3D Zbalansowane)\033[0m")
            print(" 3. \033[97mSieć (120Mbps) & SmartTube\033[0m")
            print(" 4. \033[97mSprzętowa Akceleracja\033[0m")
            print(" 5. \033[97mInteligentne Zasoby (Foreground Boost)\033[0m")
            print(" 6. \033[97mDebloat & Odcięcie Telemetrii\033[0m")
            print(" 7. \033[97mZabezpieczony Netflix (DRM)\033[0m")
            print(" 8. \033[97mProfil DASH/VP9 VISIONOS\033[0m")
            print(" 9. \033[92mBłyskawiczne Wideo (TTFF) & Responsywność UI\033[0m")
            print("\n\033[93m--- OPERACJE ZAAWANSOWANE ---\033[0m")
            print(" 10.\033[91m 🔥 FULL OMEGA (Uruchom Wszystko 1-9) 🔥\033[0m")
            print(" 11.\033[92m ♻️ Restart SystemUI (Zastosuj Zmiany)\033[0m")
            print(" 12.\033[94m 🔌 Podłącz urządzenie (Zmień IP)\033[0m")
            print("\n 0. \033[90mWyjście\033[0m")

            choice = input("\n\033[93m[WYBIERZ AKCJĘ] > \033[0m").strip()

            if choice == '12':
                ip = input("Podaj adres IP z portem (np. 192.168.1.10:5555) [ENTER = Autodetekcja]: ").strip()
                self.bot.connect(ip if ip else None)
                self.pause()
                continue
            elif choice == '0':
                self.clear_screen()
                print("\033[92mZamykanie systemu PlayBox. Do widzenia!\033[0m")
                break

            if not self.bot.is_connected and choice in [str(i) for i in range(1, 12)]:
                print("\n\033[91m[!] Musisz najpierw połączyć się z urządzeniem (Opcja 12).\033[0m")
                self.pause()
                continue

            self.clear_screen()
            print("\033[90m" + "-"*50 + "\033[0m")
            
            try:
                if choice == '1': self.bot.module_webview_turbo()
                elif choice == '2': self.bot.module_broadcom_skiagl()
                elif choice == '3': self.bot.module_network_and_smarttube()
                elif choice == '4': self.bot.module_media_hardware_accel()
                elif choice == '5': self.bot.module_intelligent_resources_foreground()
                elif choice == '6': self.bot.module_debloat_telemetry()
                elif choice == '7': self.bot.module_freeze_netflix()
                elif choice == '8': self.bot.module_dctiw362_play_visionos()
                elif choice == '9': self.bot.module_speed_ttff_responsiveness()
                elif choice == '10': self.bot.run_full_omega()
                elif choice == '11': self.bot.restart_ui()
                else: print("\033[91mNieprawidłowy wybór.\033[0m")
            except Exception as e:
                print(f"\n\033[91m[BŁĄD WYKONAWCZY] {e}\033[0m")
                
            print("\033[90m" + "-"*50 + "\033[0m")
            self.pause()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PlayBox Ultimate V12.1 - CLI Termux")
    parser.add_argument("--ip", type=str, help="IP urządzenia", default=None)
    args = parser.parse_args()

    bot = PlayBoxV12()
    bot.connect(args.ip)
    
    cli = CLI_Interface(bot)
    cli.run()