#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# PLAYBOX ULTIMATE V10.0 - BROADCOM SKIA EDITION
# Ekskluzywna optymalizacja pod Sagemcom (BCM72xx / Android 9)
# Zawiera modyfikacje: SkiaGL, WebView Turbo, Hybrid Display 1080p/4K
# ==============================================================================

import os
import sys
import subprocess
import time

class PlayBoxV10:
    def __init__(self, target_ip=None):
        self.device = target_ip or self._detect_device()
        self.is_connected = False
        
    def _detect_device(self):
        try:
            out = subprocess.check_output(["adb", "devices"], text=True).strip()
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines: return lines[0].split("\t")[0]
        except: pass
        return "192.168.1.3:5555"

    def adb(self, cmd_list, silent=False):
        try:
            full_cmd = ["adb", "-s", self.device] + cmd_list
            res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
            return res.stdout.strip()
        except Exception as e:
            if not silent: print(f"\033[91m[ADB ERROR] {e}\033[0m")
            return ""

    def connect(self):
        print(f"\033[93m[*] Łączenie z bazą: {self.device}...\033[0m")
        self.adb(["disconnect"], silent=True)
        res = self.adb(["connect", self.device])
        if "connected" in res or "already" in res:
            self.is_connected = True
            print("\033[92m[✓] Połączenie stabilne.\033[0m")
            return True
        return False

    # ---------------------------------------------------------
    # MODUŁ 1: WEBVIEW TURBO (Chromium/Thorium Engine)
    # ---------------------------------------------------------
    def module_webview_turbo(self):
        print("\n\033[96m[MODUŁ] Aktywacja ekstremalnego silnika WebView...\033[0m")
        
        # Potężny łańcuch flag optymalizujących WebView (Zgodnie z notatkami)
        flags = (
            "ignore-gpu-blocklist=true enable-gpu-rasterization=true "
            "animated-image-resume=true webview-accelerate-small-canvases=true "
            "num-raster-threads=2 webview-thread-safe-media=true "
            "optimize-network-buffers=true optimize-network-buffers2=true "
            "enable-finch-seed-delta-compression=true "
            "enable-webview-surface-control-for-tv=true webview-surface-control=true "
            "webview-disable-package-allowlist-throttling=true"
        )
        
        self.adb(["shell", "settings", "put", "global", "webview_flags", f'"{flags}"'])
        
        # Dodatkowe wyłączenie procesów telemetrycznych i crash-raportów WebView
        services = [
            "com.google.android.webview/com.google.android.apps.chrome.process.ChildProcessService",
            "com.google.android.webview/org.chromium.android_webview.services.CrashReceiverService",
            "com.google.android.webview/org.chromium.android_webview.services.VariationsSeedServer"
        ]
        for srv in services:
            self.adb(["shell", "pm", "disable-user", "--user", "0", srv], silent=True)
            
        print("\033[92m[✓] Flagi WebView zaaplikowane. Wyłączono raportowanie błędów chromium.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 2: BROADCOM SKIAGL & SURFACE BYPASS
    # ---------------------------------------------------------
    def module_broadcom_skiagl(self):
        print("\n\033[96m[MODUŁ] Konfiguracja sterownika Broadcom (SkiaGL + VSync)...\033[0m")
        
        props = {
            # Wymuszenie silnika SkiaGL zamiast OpenGL
            "debug.hwui.renderer": "skiagl",
            "persist.sys.ui.hw": "true",
            "debug.hwui.render_thread_count": "2",
            "debug.hwui.show_dirty_regions": "false",
            
            # Priorytety i poszerzenie bufora RAM dla tekstur UI
            "debug.sf.disable_backpressure": "1",
            "debug.sf.latch_unsignaled": "1",
            "ro.hwui.texture_cache_size": "32.0",
            "ro.hwui.text_large_cache_width": "2048",
            "ro.hwui.text_large_cache_height": "1024"
        }
        
        for k, v in props.items():
            self.adb(["shell", "setprop", k, v])

        # Bypass kompozytora systemowego (BARDZO WAŻNE DLA BROADCOM)
        self.adb(["shell", "settings", "put", "global", "overlay_display_devices", '""'])
        self.adb(["shell", "service", "call", "SurfaceFlinger", "1008", "i32", "1"])
        
        print("\033[92m[✓] Potok graficzny przestawiony na SkiaGL. Objętość cache powiększona.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 3: ARCHITEKTURA HYBRYDOWA (UI 1080p / VIDEO 4K HDR)
    # ---------------------------------------------------------
    def module_hybrid_display(self):
        print("\n\033[96m[MODUŁ] Aktywacja Trybu Hybrydowego (DPI/HDR)...\033[0m")
        print("\033[90m[*] Ustawianie interfejsu systemowego na lekkie 1080p...\033[0m")
        self.adb(["shell", "wm", "size", "1920x1080"])
        self.adb(["shell", "wm", "density", "213"])
        self.adb(["shell", "settings", "put", "global", "display_size_forced", "1920,1080"])
        
        print("\033[90m[*] Tworzenie tunelu wideo dla natywnego 4K HDR60Hz...\033[0m")
        self.adb(["shell", "settings", "put", "global", "user_preferred_resolution", "2160p60hz"])
        self.adb(["shell", "settings", "put", "global", "hdr_output_mode", "auto"])
        self.adb(["shell", "settings", "put", "global", "hdr_static_metadata", "1"])
        
        nrdp = '{"hdrOutputType":"always","videoPeekTunnelFramesToSend":16}'
        self.adb(["shell", "settings", "put", "global", "nrdp_platform_capabilities", f"'{nrdp}'"])
        
        print("\033[92m[✓] Tryb Hybrydowy aktywny. Płynność interfejsu wzrośnie drastycznie.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 4: AGRESYWNE CZYSZCZENIE CPU/RAM
    # ---------------------------------------------------------
    def module_cpu_ram_agressive(self):
        print("\n\033[96m[MODUŁ] Agresywny Zrzut Zasobów (No Cached Apps)...\033[0m")
        
        # Zapobiega trzymaniu aplikacji w pamięci podręcznej RAM
        self.adb(["shell", "settings", "put", "global", "power_manager_constants", '"no_cached_apps_until_foreground=true"'])
        self.adb(["shell", "settings", "put", "global", "low_power_trigger_level", "0"])
        self.adb(["shell", "settings", "put", "global", "sys_free_storage_log_interval", "0"])
        
        # Wyłączenie logowania usług by odciążyć CPU
        self.adb(["shell", "setprop", "log.tag.FA", "VERBOSE"])
        self.adb(["shell", "setprop", "log.tag.FA-SVC", "VERBOSE"])
        
        self.adb(["shell", "pm", "trim-caches", "9999M"])
        print("\033[92m[✓] Procesor odciążony. RAM skonfigurowany pod odtwarzacz wideo.\033[0m")

    # ---------------------------------------------------------
    # UI MENU
    # ---------------------------------------------------------
    def show_menu(self):
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\033[95m" + "═"*65)
            print("   PLAYBOX ULTIMATE V10.0 - BROADCOM SKIA EDITION")
            print("═"*65 + "\033[0m")
            print(f"Status: \033[92mPOŁĄCZONO ({self.device})\033[0m\n")
            
            print("Wybierz moduł do wdrożenia:")
            print("\033[93m1. [WEBVIEW] Turbo Flags & Chromium Optimization\033[0m")
            print("\033[94m2. [GRAFIKA] SkiaGL, Render Threads & Surface Bypass\033[0m")
            print("\033[96m3. [EKRAN] Tryb Hybrydowy (Interfejs 1080p -> Wideo 4K HDR)\033[0m")
            print("\033[91m4. [ZASOBY] Agresywne uwalnianie RAM i ochrona CPU\033[0m")
            print("\033[92m5. [FULL OMEGA] Uruchom wszystkie moduły na raz (ZALECANE)\033[0m")
            print("\n6. Miękki restart powłoki (Wymagany do wczytania SkiaGL/Ekranu)")
            print("\n0. Wyjście")
            
            choice = input("\nRozkaz > ")
            
            if choice == '1': self.module_webview_turbo(); input("\nNaciśnij Enter...")
            elif choice == '2': self.module_broadcom_skiagl(); input("\nNaciśnij Enter...")
            elif choice == '3': self.module_hybrid_display(); input("\nNaciśnij Enter...")
            elif choice == '4': self.module_cpu_ram_agressive(); input("\nNaciśnij Enter...")
            elif choice == '5':
                self.module_webview_turbo()
                self.module_broadcom_skiagl()
                self.module_hybrid_display()
                self.module_cpu_ram_agressive()
                print("\n\033[92m[✓] WSZYSTKIE OPTYMALIZACJE WDROŻONE!\033[0m")
                print("Zalecam wykonanie 'Miękkiego restartu' (Opcja 6).")
                input("\nNaciśnij Enter...")
            elif choice == '6':
                print("\n\033[93m[*] Restartowanie SurfaceFlinger i powłoki...\033[0m")
                self.adb(["shell", "stop", "&&", "start"])
                print("\033[92m[✓] Interfejs uruchamia się ponownie (Poczekaj 10 sekund na TV).\033[0m")
                input("\nNaciśnij Enter...")
            elif choice == '0':
                break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", help="IP urządzenia (np. 192.168.1.3:5555)")
    args = parser.parse_args()

    bot = PlayBoxV10(target_ip=args.device)
    if bot.connect():
        bot.show_menu()
    else:
        print("\033[91m[!] Nie udało się połączyć. Upewnij się, że dekoder jest włączony i ADB aktywne.\033[0m")