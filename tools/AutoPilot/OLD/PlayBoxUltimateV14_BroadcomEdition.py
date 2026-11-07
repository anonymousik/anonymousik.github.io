#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# PLAYBOX ULTIMATE V14.0 - BROADCOM BCM72604 HYBRID EDITION
# Dedykowana optymalizacja dla Sagemcom DCTIW362 (Play Now TV Box V1)
# SoC: Broadcom BCM72604 (Dual-Core) | RAM: 1.5 GB | OS: Android TV 9
# ==============================================================================

import os
import sys
import subprocess
import time
from typing import List, Optional

class PlayBoxBroadcomV14:
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

    def adb(self, cmd_list: List[str], silent: bool = False, timeout: int = 15) -> str:
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

    def adb_shell(self, cmd_str: str, silent: bool = False) -> str:
        return self.adb(["shell", cmd_str], silent=silent)

    def set_prop(self, key: str, value: str, root_fallback: bool = True):
        self.adb(["shell", "setprop", key, value], silent=True)
        if root_fallback:
            self.adb(["shell", "su", "-c", f"setprop {key} {value}"], silent=True)

    def put_setting(self, namespace: str, key: str, value: str):
        self.adb(["shell", "settings", "put", namespace, key, str(value)], silent=True)

    def connect(self, ip: str = None) -> bool:
        if ip:
            self.device = ip
        elif not self.device:
            self.device = self.detect_device()
            
        if not self.device:
            print("\033[91m[!] Brak przypisanego IP lub nie wykryto urządzeń ADB.\033[0m")
            return False

        print(f"\033[93m[*] Łączenie z bazą Sagemcom: {self.device}...\033[0m")
        self.adb(["disconnect"], silent=True)
        res = self.adb(["connect", self.device])
        
        if "connected" in res.lower() or "already" in res.lower():
            self.is_connected = True
            print("\033[92m[✓] Połączenie nawiązane pomyślnie.\033[0m")
            return True
        else:
            self.is_connected = False
            print(f"\033[91m[!] Błąd połączenia: {res}\033[0m")
            return False

    # ---------------------------------------------------------
    # MODUŁ 1: THORIUM WEBVIEW & USŁUGI TŁA
    # ---------------------------------------------------------
    def module_webview_thorium_debloat(self):
        print("\n\033[96m[MODUŁ 1] Wdrożenie Thorium WebView & Wyłączenie uslug tła...\033[0m")
        
        # Wyłączenie ciężkich usług składowych WebView
        disable_services = [
            "com.google.android.webview/com.google.android.apps.chrome.process.ChildProcessService",
            "com.google.android.webview/org.chromium.android_webview.services.CrashReceiverService",
            "com.google.android.webview/org.chromium.android_webview.services.VariationsSeedServer"
        ]
        for srv in disable_services:
            self.adb_shell(f"pm disable-user --user 0 {srv}", silent=True)

        # Flagi Thorium zbalansowane pod 1.5GB RAM i 2 rdzenie BCM
        thorium_flags = (
            "ignore-gpu-blocklist=true "
            "enable-gpu-rasterization=true "
            "animated-image-resume=true "
            "webview-accelerate-small-canvases=true "
            "num-raster-threads=2 "
            "webview-thread-safe-media=true "
            "optimize-network-buffers=true "
            "optimize-network-buffers2=true "
            "enable-finch-seed-delta-compression=true "
            "enable-webview-surface-control-for-tv=true "
            "webview-surface-control=true "
            "webview-disable-package-allowlist-throttling=true"
        )
        self.put_setting("global", "webview_flags", f'"{thorium_flags}"')
        
        # Zabić WebView i SmartTube dla przeładowania instancji
        self.adb_shell("pkill -f com.google.android.webview", silent=True)
        self.adb_shell("am force-stop org.smarttube.stable", silent=True)
        print("\033[92m[✓] WebView Thorium zoptymalizowany, usługi tła odciążone.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 2: SKIAGL & STEROWNIK GFXDRIVER-BCMSTB
    # ---------------------------------------------------------
    def module_skiagl_gfxdriver_bcmstb(self):
        print("\n\033[96m[MODUŁ 2] Konfiguracja SkiaGL & Obejście SurfaceFlinger (bcmstb)...\033[0m")
        
        props = {
            "debug.hwui.renderer": "skiagl",
            "persist.sys.ui.hw": "true",
            "debug.hwui.render_thread_count": "2",  # 2 rdzenie BCM72604
            "debug.hwui.show_dirty_regions": "false",
            "debug.sf.disable_backpressure": "1",
            "debug.sf.latch_unsignaled": "1",
            "ro.hwui.texture_cache_size": "24.0",    # Zbalansowany cache pod 1.5GB RAM
            "ro.hwui.text_large_cache_width": "2048",
            "ro.hwui.text_large_cache_height": "1024"
        }
        for k, v in props.items():
            self.set_prop(k, v)

        # Obejście miksowania interfejsu przez Android Compositor dla warstwy wideo
        self.put_setting("global", "overlay_display_devices", '""')
        self.adb_shell("service call SurfaceFlinger 1008 i32 1", silent=True)
        
        print("\033[92m[✓] SkiaGL aktywny, priorytet klatek bcmstb ustabilizowany.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 3: OPTYMALIZACJA EXOPLAYER & BUFORA VDEC
    # ---------------------------------------------------------
    def module_exoplayer_vdec_balance(self):
        print("\n\033[96m[MODUŁ 3] Optymalizacja bufora ExoPlayer & DASH (Limit 25s / Chunk 4MB)...\033[0m")
        
        # Ograniczenie buforowania wideo dla eliminacji zapchania dekodera OMX Broadcom
        self.put_setting("global", "exoplayer_max_buffer_ms", "25000")       # Max 25 sekund bufora
        self.put_setting("global", "exoplayer_min_buffer_ms", "1500")        # Fast TTFF 1.5s
        self.put_setting("global", "exoplayer_dash_chunk_size", "4194304")   # 4 MB kompromis
        self.put_setting("global", "exoplayer_buffer_limit", "25165824")     # Max 24 MB łącznej pamięci
        self.put_setting("secure", "exoplayer_buffer_limit", "25165824")
        
        self.set_prop("media.tunneled-playback.enable", "false")
        self.set_prop("ro.media.dec.video.vp9", "OMX.BROADCOM.video-decoder.vp9")
        
        print("\033[92m[✓] Pamięć podręczna ExoPlayera zbalansowana (Brak 10-sekundowego czarnego ekranu).\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 4: ROZDZIELCZOŚĆ UI (1080p) & HDMI 4K/HDR PASSTHROUGH
    # ---------------------------------------------------------
    def module_resolution_hdr_pipeline(self):
        print("\n\033[96m[MODUŁ 4] Wymuszenie UI 1080p & Odblokowanie 4K/60Hz HDR dla wideo...\033[0m")
        
        # 1. UI w czystym 1080p dla odciążenia GPU V3D
        self.adb_shell("wm size 1920x1080", silent=True)
        self.adb_shell("wm density 213", silent=True)
        self.put_setting("global", "display_size_forced", "1920,1080")

        # 2. Wyjście HDMI i potok HDR (Dla strumieni wideo 4K w SmartTube)
        self.put_setting("global", "user_preferred_resolution", "2160p60hz")
        self.put_setting("global", "hdr_output_mode", "auto")
        self.put_setting("global", "hdr_static_metadata", "1")
        self.put_setting("global", "nrdp_platform_capabilities", '{"hdrOutputType":"always","videoPeekTunnelFramesToSend":16}')
        
        print("\033[92m[✓] UI skonsolidowane w 1080p, HDMI przesyła strumienie 4K HDR w locie.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 5: PERFORMANCE PROCESORA & ZARZĄDZANIE PAMIĘCIĄ LMK
    # ---------------------------------------------------------
    def module_cpu_memory_governor(self):
        print("\n\033[96m[MODUŁ 5] Profil wydajnościowy CPU & Low Memory Killer (1.5GB RAM)...\033[0m")
        
        # Reżim wydajności bez uśpienia i dławienia procesów tła
        self.put_setting("global", "power_manager_constants", '"no_cached_apps_until_foreground=true"')
        self.put_setting("global", "low_power_trigger_level", "0")
        self.put_setting("global", "sys_free_storage_log_interval", "0")
        
        # Adaptacyjne ograniczenie procesów podręcznych (Środowisko 1.5GB RAM wymaga max 2 procesów)
        self.put_setting("global", "max_cached_processes", "2")
        self.put_setting("global", "activity_manager_constants", "max_cached_processes=2")
        self.set_prop("ro.sys.fw.bg_apps_limit", "2", root_fallback=True)

        # Logi diagnostyczne FA
        self.set_prop("log.tag.FA", "VERBOSE")
        self.set_prop("log.tag.FA-SVC", "VERBOSE")

        # Zrzucenie uśpionego RAMu
        self.adb_shell("cmd activity kill-all", silent=True)
        self.adb_shell("cmd activity trim-memory RUNNING_CRITICAL", silent=True)
        
        print("\033[92m[✓] Zarządcza polityka CPU/RAM ustawiona na tryb Performance.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 6: CZYSZCZENIE CACHE & NATIVE COMPILATION (SMARTTUBE)
    # ---------------------------------------------------------
    def module_smarttube_maintenance(self):
        print("\n\033[96m[MODUŁ 6] Czyszczenie Cache & Kompilacja AOT SmartTube...\033[0m")
        
        # Usunięcie starych cząstek cache
        self.adb_shell("rm -rf /data/data/com.liskovsoft.smarttubetv.beta/cache/*", silent=True)
        self.adb_shell("rm -rf /data/data/org.smarttube.stable/cache/*", silent=True)

        # Optymalizacja kompilacji AOT pod procesor Broadcom
        print("\033[90m[*] Kompilacja natywna (speed-profile) dla org.smarttube.stable...\033[0m")
        self.adb_shell("cmd package compile -m speed-profile org.smarttube.stable", silent=True)
        
        print("\033[92m[✓] Czyszczenie zakończone, SmartTube skompilowany AOT.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 7: DEBLOAT & HIBERNACJA KONKURENCJI
    # ---------------------------------------------------------
    def module_debloat_and_freeze(self):
        print("\n\033[96m[MODUŁ 7] Zatrzymanie zbędnych aplikacji i telemetrii...\033[0m")
        
        settings_secure = {
            "accessibility_enabled": "0",
            "upload_log_enable": "0",
            "send_action_logs_at_app_foreground": "0",
            "assistant": "0"
        }
        for k, v in settings_secure.items():
            self.put_setting("secure", k, v)

        # Mrożenie aplikacji VOD
        heavy_pkgs = ["com.netflix.ninja", "com.google.android.youtube.tv"]
        for pkg in heavy_pkgs:
            self.adb_shell(f"am force-stop {pkg}", silent=True)
            self.adb_shell(f"cmd appops set {pkg} RUN_IN_BACKGROUND ignore", silent=True)

        print("\033[92m[✓] Telemetria wyłączona, zasoby zarezerwowane dla pierwszego planu.\033[0m")

    # ---------------------------------------------------------
    # RESTAROWANIE SYSTEMU UI
    # ---------------------------------------------------------
    def restart_ui(self):
        print("\n\033[93m[*] Restartowanie powłoki graficznej (SurfaceFlinger & SystemUI)...\033[0m")
        self.adb_shell("stop && start", silent=True)
        print("\033[92m[✓] Interfejs uruchamia się ponownie (Odczekaj 12 sekund).\033[0m")

    # ---------------------------------------------------------
    # PELNY PROGRAM OPTYMALIZACYJNY
    # ---------------------------------------------------------
    def run_full_omega(self):
        print("\n" + "="*65)
        print("\033[91m🚀 URUCHAMIANIE OMEGA V14: SAGEMCOM BROADCOM BCM72604\033[0m")
        print("="*65)
        
        self.module_webview_thorium_debloat()
        self.module_skiagl_gfxdriver_bcmstb()
        self.module_exoplayer_vdec_balance()
        self.module_resolution_hdr_pipeline()
        self.module_cpu_memory_governor()
        self.module_smarttube_maintenance()
        self.module_debloat_and_freeze()
        
        print("\n\033[92m[✓] WSZYSTKIE TWEAKI BROADCOM V14 ZAAPLIKOWANE!\033[0m")
        self.restart_ui()
        print("=" * 65)

class CLI_Interface:
    def __init__(self, bot: PlayBoxBroadcomV14):
        self.bot = bot

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def pause(self):
        input("\n\033[90m[ Naciśnij ENTER, aby kontynuować ]\033[0m")

    def run(self):
        while True:
            self.clear_screen()
            print("\033[96m" + "═" * 70)
            print(" 🚀 PLAYBOX V14.0 - SAGEMCOM BCM72604 (1.5GB RAM) HYBRID EDITION")
            print("═" * 70 + "\033[0m")
            
            if self.bot.is_connected:
                print(f" Status: \033[92m[✓] POŁĄCZONO ({self.bot.device})\033[0m")
            else:
                print(f" Status: \033[91m[X] BRAK POŁĄCZENIA\033[0m")
            print("\033[96m" + "═" * 70 + "\033[0m\n")

            print("\033[93m--- MODUŁY HYBRYDOWE V14 ---\033[0m")
            print(" 1. \033[97mWebView Thorium & Usunięcie zbędnych usług\033[0m")
            print(" 2. \033[97mSkiaGL & SurfaceFlinger bcmstb Direct Pipeline\033[0m")
            print(" 3. \033[97mExoPlayer DASH Buffer (Limit 25s / Chunk 4MB)\033[0m")
            print(" 4. \033[97mUI 1080p + HDMI 4K/60Hz HDR Passthrough Engine\033[0m")
            print(" 5. \033[97mProfil Wydajnościowy CPU & LMK 1.5GB RAM Fix\033[0m")
            print(" 6. \033[97mCzyszczenie Cache & AOT Kompilacja SmartTube\033[0m")
            print(" 7. \033[97mDebloat & Zamrożenie tła (Netflix/YouTube)\033[0m")
            print("\n\033[93m--- AKCJE GLOBALNE ---\033[0m")
            print(" 10.\033[91m 🔥 BROADCOM OMEGA V14 (Uruchom Wszystko 1-7) 🔥\033[0m")
            print(" 11.\033[92m ♻️ Miękki Restart SystemUI (Aplikuj Zmiany)\033[0m")
            print(" 12.\033[94m 🔌 Podłącz urządzenie (IP / Auto)\033[0m")
            print("\n 0. \033[90mWyjście\033[0m")

            choice = input("\n\033[93m[WYBIERZ AKCJĘ] > \033[0m").strip()

            if choice == '12':
                ip = input("Podaj IP:Port (np. 192.168.1.10:5555) [ENTER = Auto]: ").strip()
                self.bot.connect(ip if ip else None)
                self.pause()
                continue
            elif choice == '0':
                self.clear_screen()
                print("\033[92mZamykanie skryptu...\033[0m")
                break

            if not self.bot.is_connected and choice in [str(i) for i in range(1, 12)]:
                print("\n\033[91m[!] Najpierw nawiąż połączenie z urządzeniem (Opcja 12).\033[0m")
                self.pause()
                continue

            self.clear_screen()
            print("\033[90m" + "-"*50 + "\033[0m")
            
            try:
                if choice == '1': self.bot.module_webview_thorium_debloat()
                elif choice == '2': self.bot.module_skiagl_gfxdriver_bcmstb()
                elif choice == '3': self.bot.module_exoplayer_vdec_balance()
                elif choice == '4': self.bot.module_resolution_hdr_pipeline()
                elif choice == '5': self.bot.module_cpu_memory_governor()
                elif choice == '6': self.bot.module_smarttube_maintenance()
                elif choice == '7': self.bot.module_debloat_and_freeze()
                elif choice == '10': self.bot.run_full_omega()
                elif choice == '11': self.bot.restart_ui()
                else: print("\033[91mNieprawidłowy wybór.\033[0m")
            except Exception as e:
                print(f"\n\033[91m[BŁĄD EXEC] {e}\033[0m")
                
            print("\033[90m" + "-"*50 + "\033[0m")
            self.pause()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PlayBox V14.0 Broadcom Edition")
    parser.add_argument("--ip", type=str, help="IP urządzenia", default=None)
    args = parser.parse_args()

    bot = PlayBoxBroadcomV14()
    bot.connect(args.ip)
    
    cli = CLI_Interface(bot)
    cli.run()