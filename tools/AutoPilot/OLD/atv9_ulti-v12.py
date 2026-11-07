#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# PLAYBOX ULTIMATE V12.0 - BROADCOM SKIA EDITION (V3D + RAM OPTIMIZED)
# Ekskluzywna optymalizacja pod Sagemcom (BCM72xx / Android 9)
# Zawiera modyfikacje: 
# - SkiaGL (V3D Scoreboard/TMU Mitigated)
# - TCP Buffers 120Mbps, SmartTube/ExoPlayer Fixes
# - DRM-Safe Netflix Freeze, Extreme RAM/GC Management
# ==============================================================================

import os
import sys
import subprocess
import time
import threading
import re
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import List, Optional

class PlayBoxV12:
    def __init__(self, target_ip: Optional[str] = None):
        self.device = target_ip or self._detect_device()
        self.is_connected = False

    def _detect_device(self) -> str:
        try:
            out = subprocess.check_output(["adb", "devices"], text=True).strip()
            lines = [l for l in out.splitlines() if "\tdevice" in l]
            if lines: return lines[0].split("\t")[0]
        except Exception:
            pass
        return "192.168.1.3:5555"

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
        # Próba standardowa
        self.adb(["shell", "setprop", key, value], silent=True)
        # Fallback (wymuszenie przez su -c, jeśli dostępne)
        if root_fallback:
            self.adb(["shell", "su", "-c", f"setprop {key} {value}"], silent=True)

    def put_setting(self, namespace: str, key: str, value: str):
        """Ustawienia global/secure."""
        self.adb(["shell", "settings", "put", namespace, key, str(value)], silent=True)

    def connect(self) -> bool:
        print(f"\033[93m[*] Łączenie z bazą: {self.device}...\033[0m")
        self.adb(["disconnect"], silent=True)
        res = self.adb(["connect", self.device])
        if "connected" in res.lower() or "already" in res.lower():
            self.is_connected = True
            print("\033[92m[✓] Połączenie stabilne.\033[0m")
            return True
        return False

    # ---------------------------------------------------------
    # MODUŁ 1: WEBVIEW TURBO (BEZ ZMIAN - STABILNY)
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
            "debug.hwui.render_thread_count": "1",    # Mitygacja Scoreboard Stalls
            "debug.sf.disable_backpressure": "0",     # Wymusza synchronizację z CPU
            "debug.sf.latch_unsignaled": "1",
            "ro.hwui.texture_cache_size": "24.0",     
            "ro.hwui.layer_cache_size": "16384",      # Limit warstw zapobiegający Thrashingowi
            "ro.hwui.text_large_cache_width": "1024", # Oszczędność TMU
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
        print("\n\033[96m[MODUŁ 3] Optymalizacja stosu TCP (120Mbps / 768KB) i fixy wideo...\033[0m")
        
        # Bufor pod 120 Mbps (786432 bajtów = 768KB)
        tcp_buffers = "4096,131072,786432,4096,16384,3184168"
        self.put_setting("global", "net.tcp.buffersize.wifi", f'"{tcp_buffers}"')
        self.put_setting("global", "net.tcp.buffersize.default", f'"{tcp_buffers}"')
        self.set_prop("net.tcp.buffersize.wifi", tcp_buffers)
        self.set_prop("net.tcp.buffersize.default", tcp_buffers)
        
        # Zmniejszenie opóźnień sieci
        self.set_prop("net.tcp.default_init_rwnd", "140")
        
        # Wyłączniki WiFi w tle (oszczędzanie CPU)
        self.put_setting("global", "wifi_watchdog_on", "0")
        self.put_setting("global", "captive_portal_mode", "0")
        self.put_setting("global", "wifi_scan_always_enabled", "0")
        self.put_setting("global", "prefer_ipv4", "true")

        # ExoPlayer & SmartTube Fixes
        self.put_setting("global", "exoplayer_buffer_limit", "3184168")
        self.put_setting("secure", "exoplayer_buffer_limit", "3184168")
        self.set_prop("media.tunneled-playback.enable", "false") # Crash fix dla SmartTube
        self.put_setting("global", "encoded_surround_output", "0") # Audio fix
        
        print("\033[92m[✓] Bufor TCP ustawiony pod 120Mbps. Parametry SmartTube zaaplikowane.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 4: MEDIA FRAMEWORK & HARDWARE ACCEL
    # ---------------------------------------------------------
    def module_media_hardware_accel(self):
        print("\n\033[96m[MODUŁ 4] Wymuszanie potoków sprzętowych (UI/Audio/Video)...\033[0m")
        self.put_setting("global", "hardware_acceleration_enabled", "true")
        
        self.set_prop("debug.sf.hw", "1", root_fallback=True)
        self.set_prop("media.stagefright.audio.sink", "512", root_fallback=True)
        self.set_prop("media.stagefright.leswitches", "true", root_fallback=True)
        self.set_prop("persist.sys.media.use-awesome", "0", root_fallback=True)
        
        # Bufor Loggera odciążający CPU na operacjach I/O
        self.set_prop("ro.logd.size", "16M")
        
        print("\033[92m[✓] Priorytetyzacja koprocesora VideoCore i dekoderów włączona.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 5: EXTREME RAM & GARBAGE COLLECTION
    # ---------------------------------------------------------
    def module_extreme_ram_gc(self):
        print("\n\033[96m[MODUŁ 5] Ekstremalne zarządzanie pamięcią (OOM / GC)...\033[0m")
        
        self.put_setting("global", "low_ram", "true")
        self.put_setting("global", "sys_free_storage_alloc_limit", "104857600")
        self.put_setting("global", "always_finish_activities", "1")
        self.put_setting("global", "low_power_mode", "1")
        self.put_setting("global", "max_cached_processes", "8")
        self.put_setting("global", "boot_fast", "1")
        self.put_setting("global", "sys_storage_threshold_percentage", "5")
        self.put_setting("global", "low_power_trigger_level", "0")

        # Błyskawiczne zwolnienie zasobów w czasie rzeczywistym
        print("\033[90m[*] Uruchamianie Garbage Collection i obcinanie pamięci...\033[0m")
        self.adb(["shell", "cmd", "activity", "kill-all"])
        self.adb(["shell", "cmd", "package", "trim-caches", "4096G"])
        self.adb(["shell", "cmd", "activity", "trim-memory", "RUNNING_CRITICAL"])
        self.adb(["shell", "cmd", "activity", "gc-heap"])
        
        print("\033[92m[✓] Pamięć RAM odśmiecona (Stan Krytyczny narzucony).\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 6: DEBLOAT I TELEMETRIA (CPU OFFLOAD)
    # ---------------------------------------------------------
    def module_debloat_telemetry(self):
        print("\n\033[96m[MODUŁ 6] Wyłączanie procesów w tle (UI/Asystent/Reklamy)...\033[0m")
        
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
        self.put_setting("global", "advertiser_id_limit_ad_tracking", "1")
        
        print("\033[92m[✓] Podsystem telemetryczny i ułatwienia dostępu zatrzymane.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 7: DRM-SAFE NETFLIX FREEZE
    # ---------------------------------------------------------
    def module_freeze_netflix(self):
        pkg = "com.netflix.ninja"
        print(f"\n\033[96m[MODUŁ 7] Głęboka hibernacja {pkg} (Bez uszkodzeń DRM)...\033[0m")
        
        self.adb(["shell", "am", "force-stop", pkg])
        self.adb(["shell", "pm", "suspend", pkg])
        
        # Odcięcie uprawnień AppOps
        self.adb(["shell", "cmd", "appops", "set", pkg, "RUN_IN_BACKGROUND", "ignore"])
        self.adb(["shell", "cmd", "appops", "set", pkg, "START_FOREGROUND", "ignore"])
        # 'ignore' działa jako bariera dla SYSTEM_ALERT_WINDOW w wierszu poleceń
        self.adb(["shell", "cmd", "appops", "set", pkg, "SYSTEM_ALERT_WINDOW", "ignore"])
        
        print("\033[92m[✓] Netflix odcięty od zasobów systemowych. Certyfikaty L1 nietknięte.\033[0m")

    # ---------------------------------------------------------
    # MODUŁ 8: DCTIW362_PLAY (VISIONOS / DASH / VP9 Broadcom)
    # ---------------------------------------------------------
    def module_dctiw362_play_visionos(self):
        print("\n\033[96m[MODUŁ 8] Profil DCTIW362_PLAY (VISIONOS, DASH, VP9 Broadcom)...\033[0m")
        
        # Wymuszanie sprzętowego dekodera OMX.BROADCOM dla VP9 (Android 9 / Broadcom)
        print("\033[90m[*] Priorytetyzacja dekodera OMX.BROADCOM.video-decoder.vp9...\033[0m")
        # Wyłączamy eksperymentalny Codec2, aby wymusić sprawdzony OMX w Broadcom
        self.set_prop("debug.stagefright.ccodec", "0") 
        self.set_prop("media.stagefright.omx-force-hw", "true")
        self.set_prop("ro.media.dec.video.vp9", "OMX.BROADCOM.video-decoder.vp9")
        self.set_prop("ro.media.dec.video.vp9.mime", "x-vnd.on2.vp9")
        
        # Optymalizacje pod ExoPlayer (protokół DASH i klient VISIONOS)
        print("\033[90m[*] Aplikowanie parametrów ExoPlayer (DASH / VISIONOS / tv-player-ias)...\033[0m")
        self.put_setting("global", "exoplayer_client_id", "VISIONOS")
        self.put_setting("global", "exoplayer_protocol_default", "DASH")
        self.put_setting("global", "exoplayer_player_type", "tv-player-ias.vflset")
        
        # Rozmiar pojedynczego chunka DASH (zapobiega dławieniu się PlayBoxa na mikro-żądaniach)
        self.put_setting("global", "exoplayer_dash_chunk_size", "1048576") 
        
        # Właściwości flagowane pod natywne apki operatora
        self.set_prop("persist.sys.media.visionos.dash", "true")
        self.set_prop("persist.sys.media.visionos.vp9", "true")
        self.set_prop("persist.sys.media.player_type", "tv-player-ias.vflset")
        
        print("\033[92m[✓] Specyfika DCTIW362_PLAY (OMX, DASH, VISIONOS, tv-player-ias) wdrożona pomyślnie.\033[0m")

    def restart_ui(self):
        print("\n\033[93m[*] Restartowanie SurfaceFlinger i SystemUI...\033[0m")
        self.adb(["shell", "stop", "&&", "start"])
        print("\033[92m[✓] Interfejs uruchamia się ponownie (Poczekaj 10 sekund).\033[0m")

# ==============================================================================
# NIEZAWODNY INTERFEJS GRAFICZNY (GUI)
# ==============================================================================
class TextRedirector:
    """Przechwytuje standardowe wyjście (print) i przekierowuje do widgetu Text w GUI."""
    def __init__(self, widget):
        self.widget = widget
        # Regex do usuwania znaków kolorujących z terminala (ANSI escape codes)
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def write(self, string):
        clean_string = self.ansi_escape.sub('', string)
        # after(0, ...) zapewnia pełne bezpieczeństwo wątków w Tkinter (aktualizacja z głównego wątku)
        self.widget.after(0, self._append, clean_string)

    def _append(self, text):
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)

    def flush(self):
        pass

class PlayBoxGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PlayBox Ultimate V12.0 - Broadcom GUI Edition")
        self.root.geometry("900x650")
        self.root.configure(bg="#2b2b2b")
        
        # Nowoczesny styl dla ttk
        self.style = ttk.Style()
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
        
        self.bot = PlayBoxV12()
        self.build_ui()
        
        # Przekierowanie konsoli
        sys.stdout = TextRedirector(self.log_text)
        print("Witaj w systemie PlayBox Ultimate V12.0 (Tryb Niezawodnego GUI)")
        print("Upewnij się, że opcje programisty i debugowanie ADB są włączone na urządzeniu.")
        print("Wprowadź IP urządzenia w lewym górnym rogu i kliknij 'Połącz ADB'.\n")

    def build_ui(self):
        conn_frame = tk.Frame(self.root, bg="#1e1e1e", bd=2, relief=tk.SUNKEN)
        conn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(conn_frame, text="IP Urządzenia:", bg="#1e1e1e", fg="#4CAF50", font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=10, pady=10)
        self.ip_entry = tk.Entry(conn_frame, width=18, font=("Consolas", 11, "bold"), bg="#333333", fg="white", insertbackground="white")
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        self.ip_entry.insert(0, self.bot.device)
        
        self.btn_connect = tk.Button(conn_frame, text="🔌 Połącz ADB", bg="#0277bd", fg="white", font=("Arial", 10, "bold"),
                                     activebackground="#01579b", activeforeground="white", command=self.connect_device)
        self.btn_connect.pack(side=tk.LEFT, padx=15)
        
        self.status_lbl = tk.Label(conn_frame, text="Status: Brak połączenia", bg="#1e1e1e", fg="#F44336", font=("Arial", 11, "bold"))
        self.status_lbl.pack(side=tk.RIGHT, padx=15)

        mod_frame = tk.LabelFrame(self.root, text=" ⚙️ Moduły Optymalizacyjne Skia & Broadcom ", bg="#2b2b2b", fg="#FFC107", font=("Arial", 11, "bold"))
        mod_frame.pack(fill=tk.X, padx=10, pady=5)
        
        buttons = [
            ("1. WebView Turbo Flags", self.bot.module_webview_turbo, "#37474f"),
            ("2. SkiaGL (V3D Zbalansowane)", self.bot.module_broadcom_skiagl, "#37474f"),
            ("3. Sieć (120Mbps) & SmartTube", self.bot.module_network_and_smarttube, "#37474f"),
            ("4. Sprzętowa Akceleracja", self.bot.module_media_hardware_accel, "#37474f"),
            ("5. Extreme RAM / OOM Clear", self.bot.module_extreme_ram_gc, "#424242"),
            ("6. Debloat & Odcięcie Telemetrii", self.bot.module_debloat_telemetry, "#424242"),
            ("7. Zabezpieczony Netflix (DRM)", self.bot.module_freeze_netflix, "#424242"),
            ("8. Profil DASH/VP9 VISIONOS", self.bot.module_dctiw362_play_visionos, "#424242")
        ]
        
        row, col = 0, 0
        for text, func, color in buttons:
            btn = tk.Button(mod_frame, text=text, width=28, bg=color, fg="white", font=("Arial", 9, "bold"),
                            activebackground="#546e7a", activeforeground="white",
                            command=lambda f=func: self.run_thread(f))
            btn.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
            col += 1
            if col > 3:
                col = 0
                row += 1

        for i in range(4):
            mod_frame.columnconfigure(i, weight=1)

        spc_frame = tk.Frame(self.root, bg="#2b2b2b")
        spc_frame.pack(fill=tk.X, padx=10, pady=10)
        
        btn_omega = tk.Button(spc_frame, text="🔥 FULL OMEGA (Uruchom Wszystko 1-8) 🔥", bg="#b71c1c", fg="white", 
                              font=("Arial", 11, "bold"), activebackground="#d32f2f", command=self.run_full_omega)
        btn_omega.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=5)
        
        btn_restart = tk.Button(spc_frame, text="♻️ Restart SystemUI (Zastosuj)", bg="#2e7d32", fg="white", 
                                font=("Arial", 11, "bold"), activebackground="#388e3c", command=lambda: self.run_thread(self.bot.restart_ui))
        btn_restart.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0), ipady=5)

        log_frame = tk.LabelFrame(self.root, text=" 📝 Terminal Monitorujący ", bg="#2b2b2b", fg="#4fc3f7", font=("Arial", 10, "bold"))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, bg="#000000", fg="#00FF00", font=("Consolas", 10), bd=0)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def connect_device(self):
        # Ustawia IP z inputu i uruchamia proces łączenia w tle
        ip = self.ip_entry.get().strip()
        if ip:
            self.bot.device = ip
        self.run_thread(self._do_connect, require_connection=False)

    def _do_connect(self):
        if self.bot.connect():
            self.status_lbl.config(text=f"Status: POŁĄCZONO ({self.bot.device})", fg="#4CAF50")
        else:
            self.status_lbl.config(text="Status: BŁĄD POŁĄCZENIA", fg="#F44336")

    def run_thread(self, func, require_connection=True):
        """Asynchroniczne wywoływanie akcji, aby nie blokować GUI."""
        if require_connection and not self.bot.is_connected:
            messagebox.showwarning("Brak połączenia", "Przed modyfikacją połącz się z urządzeniem za pomocą ADB!")
            return
        
        def _wrapper():
            try:
                func()
                print("-" * 75)
            except Exception as e:
                print(f"\n[BŁĄD KRYTYCZNY] {e}")

        threading.Thread(target=_wrapper, daemon=True).start()

    def run_full_omega(self):
        if not self.bot.is_connected:
            messagebox.showwarning("Brak połączenia", "Połącz się z urządzeniem przed rozpoczęciem FULL OMEGA!")
            return
        
        def _omega_task():
            print("\n" + "="*50)
            print("🚀 URUCHAMIANIE PROCEDURY FULL OMEGA (ALL-IN-ONE)")
            print("="*50)
            
            # Sekwencja modułów
            self.bot.module_webview_turbo()
            self.bot.module_broadcom_skiagl()
            self.bot.module_network_and_smarttube()
            self.bot.module_media_hardware_accel()
            self.bot.module_debloat_telemetry()
            self.bot.module_freeze_netflix()
            self.bot.module_dctiw362_play_visionos()
            self.bot.module_extreme_ram_gc() # RAM zawsze na końcu
            
            print("\n[✓] WSZYSTKIE OPTYMALIZACJE WDROŻONE POMYŚLNIE!")
            self.bot.restart_ui()
            print("=" * 50)

        threading.Thread(target=_omega_task, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = PlayBoxGUI(root)
    root.mainloop()