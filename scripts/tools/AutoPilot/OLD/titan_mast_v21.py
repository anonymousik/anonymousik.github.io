#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM MASTER ORCHESTRATOR v20.0 (UNIFIED RISH EDITION)          ║
║  Target  : Sagemcom DCTIW362P | BCM72604 | Android TV 9 | API 28            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UNIFIED: Scalone techniki rish z v15.7.1, v15.7.2, v19.1                  ║
║  STRATEGY CHAIN: S1 Shell-Bypass > S2 Silent-Grant > S3 Direct              ║
║  FIX: KeyError 'h' w L.C — uzupełniony pełny słownik kolorów               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

VERSION  = "20.0"
DRY_RUN  = False  # True = symuluj bez wykonywania

# ==============================================================================
# [1] LOGGER — pełny słownik kolorów (fix KeyError 'h' z v19.1)
# ==============================================================================
class L:
    C: Dict[str, str] = {
        "s": "\033[92m",   # zielony    — ok
        "w": "\033[93m",   # żółty      — warn
        "e": "\033[91m",   # czerwony   — err
        "c": "\033[96m",   # cyan       — info
        "h": "\033[95m",   # magenta    — header / rish label
        "d": "\033[2m",    # dim        — secondary text
        "b": "\033[1m",    # bold
        "r": "\033[0m",    # reset
    }

    @staticmethod
    def ok(m: str)   -> None: print(f"  {L.C['s']}[✓]{L.C['r']} {m}")
    @staticmethod
    def info(m: str) -> None: print(f"  {L.C['c']}[i]{L.C['r']} {m}")
    @staticmethod
    def warn(m: str) -> None: print(f"  {L.C['w']}[!]{L.C['r']} {m}")
    @staticmethod
    def err(m: str)  -> None: print(f"  {L.C['e']}[✘]{L.C['r']} {m}")
    @staticmethod
    def dry(m: str)  -> None: print(f"  {L.C['d']}[DRY] {m}{L.C['r']}")
    @staticmethod
    def step(n: int, m: str) -> None:
        print(f"  {L.C['h']}[{n}]{L.C['r']} {m}")
    @staticmethod
    def hdr(m: str) -> None:
        bar = "═" * (len(m) + 8)
        print(f"\n{L.C['h']}{L.C['b']}╔{bar}╗\n║    {m.upper()}    ║\n╚{bar}╝{L.C['r']}\n")


# ==============================================================================
# [2] REMOTE TRANSPORT — ADB wrapper z pełną obsługą błędów
# ==============================================================================
class RemoteTransport:
    dev: str = ""

    @classmethod
    def connect(cls, target: str) -> bool:
        cls.dev = target if ":" in target else f"{target}:5555"
        L.info(f"Nawiązywanie połączenia ADB z {cls.dev}...")
        if DRY_RUN:
            L.dry(f"adb connect {cls.dev}")
            return True
        try:
            r = subprocess.run(
                ["adb", "connect", cls.dev],
                capture_output=True, text=True, timeout=10
            )
            out = r.stdout.lower()
            if "connected" in out and "failed" not in out and "unable" not in out:
                L.ok(f"Most ADB aktywny: {cls.dev}")
                return True
            L.err(f"Odmowa połączenia: {r.stdout.strip()}")
            return False
        except FileNotFoundError:
            L.err("Brak binarki 'adb' w PATH. Zainstaluj android-tools.")
            return False
        except Exception as exc:
            L.err(f"Błąd transportu: {exc}")
            return False

    @classmethod
    def sh(cls, cmd: str, timeout: int = 20) -> str:
        if DRY_RUN:
            L.dry(f"adb shell: {cmd[:90]}")
            return "DRY_RUN_OK"
        try:
            return subprocess.check_output(
                ["adb", "-s", cls.dev, "shell", cmd],
                stderr=subprocess.STDOUT, text=True, timeout=timeout
            ).strip()
        except subprocess.CalledProcessError as exc:
            return exc.output.strip() if exc.output else ""
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except Exception as exc:
            return f"ERROR:{exc}"

    @classmethod
    def push(cls, local_path: str, remote_path: str) -> bool:
        if DRY_RUN:
            L.dry(f"adb push {local_path} -> {remote_path}")
            return True
        try:
            r = subprocess.run(
                ["adb", "-s", cls.dev, "push", local_path, remote_path],
                capture_output=True, text=True, timeout=60
            )
            return r.returncode == 0
        except Exception as exc:
            L.err(f"Push error: {exc}")
            return False


# alias dla kompatybilności z poprzednimi modułami (v15.7.x)
ADB = RemoteTransport


# ==============================================================================
# [3] SHIZUKU LIFECYCLE MANAGER
# ==============================================================================
class ShizukuLifecycle:
    """
    Zarządza cyklem życia serwera Shizuku.
    Ścieżka start.sh potwierdzona dla Shizuku >= 13 na PlayBOX:
      /storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh
    """
    START_SH    = "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh"
    SERVER_PROC = "shizuku_server"

    @classmethod
    def is_running(cls) -> bool:
        out = RemoteTransport.sh("ps -A 2>/dev/null | grep shizuku_server")
        return cls.SERVER_PROC in out

    @classmethod
    def ensure_running(cls) -> bool:
        if cls.is_running():
            L.ok("Serwer Shizuku aktywny.")
            return True

        L.warn("Serwer Shizuku nie wykryty — próba uruchomienia...")

        # Metoda 1: start.sh (Shizuku >= 13, standardowa ścieżka)
        RemoteTransport.sh(f"sh {cls.START_SH}")
        time.sleep(3)
        if cls.is_running():
            L.ok("Shizuku uruchomiony przez start.sh.")
            return True

        # Metoda 2: am broadcast (starsze wersje Shizuku lub po restarcie ADB)
        RemoteTransport.sh(
            "am broadcast -a moe.shizuku.server.intent.action.REQUEST_BINDER "
            "-n moe.shizuku.privileged.api/moe.shizuku.server.ShizukuService"
        )
        time.sleep(2)
        if cls.is_running():
            L.ok("Shizuku uruchomiony przez broadcast.")
            return True

        L.err("Nie można uruchomić serwera Shizuku.")
        L.info("Uruchom aplikację Shizuku ręcznie i naciśnij 'Start' raz z GUI.")
        return False


# ==============================================================================
# [4] PRIVILEGE ENGINE — WIELOSTRATEGYJNA ESKALACJA RISH
# ==============================================================================
class PrivilegeEngine:
    """
    Wielostrategyjna eskalacja uprawnień przez Shizuku rish.

    Łańcuch strategii (w kolejności priorytetu):
    ──────────────────────────────────────────────────────────────────────
    S1  Shell-Bypass  RISH_APPLICATION_ID=com.android.shell
                      com.android.shell jest zawsze w pre-authorized list
                      Shizuku → brak okienka GUI, natychmiastowe uprawnienia.
                      Wrapper generowany przez base64|decode (bezpieczny dla
                      znaków specjalnych w Termux — bez problemów z escape).

    S2  Silent-Grant  ShizukuShellLoader --request-permission com.termux
                      Wstrzyknięcie com.termux do bazy danych Shizuku IPC
                      bez interakcji GUI. Flush bazy: sleep(2.0).
                      Następnie wrapper z RISH_APPLICATION_ID=com.termux.

    S3  Direct        app_process na każdą komendę (najwolniejszy fallback).
                      Nowa JVM per wywołanie — ok. 800ms overhead/cmd.
                      Działa jeśli Shizuku binder jest dostępny bez DEX.
    ──────────────────────────────────────────────────────────────────────
    """

    DEX_PATH  = "/data/local/tmp/rish_shizuku.dex"
    BIN_PATH  = "/data/local/tmp/rish"
    _SHELL_PKG  = "com.android.shell"   # S1: zawsze pre-autoryzowany
    _TERMUX_PKG = "com.termux"           # S2: silent-grant target
    _active_strategy: int = 0

    # ──────────────────────────────────────────────────────────────────
    # Punkt wejścia
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def init(cls) -> bool:
        L.hdr("Privilege Engine — Inicjalizacja Rish")

        if not ShizukuLifecycle.ensure_running():
            return False
        if not cls._verify_dex():
            return False

        L.step(1, "Próba S1: Shell-Bypass (com.android.shell context)...")
        if cls._strategy_shell_bypass():
            cls._active_strategy = 1
            L.ok("Aktywna strategia: S1 Shell-Bypass (brak GUI, pełne uprawnienia)")
            return True

        L.step(2, "Próba S2: Silent-Grant (com.termux IPC injection)...")
        if cls._strategy_silent_grant():
            cls._active_strategy = 2
            L.ok("Aktywna strategia: S2 Silent-Grant (com.termux autoryzowany)")
            return True

        L.step(3, "Próba S3: Direct app_process (fallback, ~800ms/cmd)...")
        if cls._strategy_direct_test():
            cls._active_strategy = 3
            L.warn("Aktywna strategia: S3 Direct (wydajność zmniejszona)")
            return True

        L.err("Wszystkie strategie rish zawiodły.")
        return False

    # ──────────────────────────────────────────────────────────────────
    # Publiczne API
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def rish(cls, cmd: str, timeout: int = 20) -> str:
        if DRY_RUN:
            L.dry(f"rish({cls.strategy_name()}): {cmd[:90]}")
            return "DRY_RUN_OK"
        dispatch = {1: cls._exec_s1, 2: cls._exec_s2, 3: cls._exec_s3}
        fn = dispatch.get(cls._active_strategy)
        if fn is None:
            L.err("Privilege Engine nie zainicjalizowany!")
            return "NOT_INITIALIZED"
        return fn(cmd, timeout)

    @classmethod
    def strategy_name(cls) -> str:
        return {1: "S1-ShellBypass", 2: "S2-SilentGrant",
                3: "S3-Direct", 0: "NONE"}[cls._active_strategy]

    # ──────────────────────────────────────────────────────────────────
    # S1: Shell-Bypass
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def _strategy_shell_bypass(cls) -> bool:
        cls._deploy_wrapper(cls._SHELL_PKG)
        out = cls._exec_s1("id")
        if "uid=" in out:
            L.ok(f"S1 test: {out[:60]}")
            return True
        L.warn(f"S1 nieudany: {out[:60]}")
        return False

    @classmethod
    def _exec_s1(cls, cmd: str, timeout: int = 20) -> str:
        return RemoteTransport.sh(f"{cls.BIN_PATH} -c '{cls._esc(cmd)}'", timeout)

    # ──────────────────────────────────────────────────────────────────
    # S2: Silent-Grant
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def _strategy_silent_grant(cls) -> bool:
        """
        Wstrzyknięcie com.termux do bazy Shizuku IPC przez --request-permission.
        ShizukuShellLoader bezpośrednio modyfikuje plik XML uprawnień Shizuku
        (/data/system/packages.xml lub prywatny store Shizuku) bez GUI.
        """
        grant_cmd = (
            f"app_process -Djava.class.path={cls.DEX_PATH} /system/bin "
            f"rikka.shizuku.shell.ShizukuShellLoader "
            f"--request-permission {cls._TERMUX_PKG}"
        )
        RemoteTransport.sh(grant_cmd, timeout=10)
        L.info("Czekam na flush bazy Shizuku IPC (2s)...")
        time.sleep(2.0)

        cls._deploy_wrapper(cls._TERMUX_PKG)
        out = cls._exec_s2("id")
        if "uid=" in out:
            L.ok(f"S2 test: {out[:60]}")
            return True
        L.warn(f"S2 nieudany: {out[:60]}")
        return False

    @classmethod
    def _exec_s2(cls, cmd: str, timeout: int = 20) -> str:
        return RemoteTransport.sh(f"{cls.BIN_PATH} -c '{cls._esc(cmd)}'", timeout)

    # ──────────────────────────────────────────────────────────────────
    # S3: Direct app_process (fallback, bez wrappera)
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def _strategy_direct_test(cls) -> bool:
        out = cls._exec_s3("id")
        if "uid=" in out:
            L.ok(f"S3 test: {out[:60]}")
            return True
        return False

    @classmethod
    def _exec_s3(cls, cmd: str, timeout: int = 20) -> str:
        """
        Bezpośrednie wywołanie przez app_process. Każde wywołanie startuje
        nową JVM (~800ms overhead). Używane tylko gdy wrapper nie działa.
        """
        direct = (
            f"app_process -Djava.class.path={cls.DEX_PATH} /system/bin "
            f"--nice-name=rish rikka.shizuku.shell.ShizukuShellLoader "
            f"-c '{cls._esc(cmd)}'"
        )
        return RemoteTransport.sh(direct, timeout)

    # ──────────────────────────────────────────────────────────────────
    # Generowanie wrappera przez base64 (bezpieczne w Termux)
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def _deploy_wrapper(cls, app_id: str) -> None:
        """
        Generuje /data/local/tmp/rish przez base64|base64 -d zamiast printf/echo.
        Technika: enkodujemy skrypt do base64 po stronie hosta → dekodujemy
        na urządzeniu. Eliminuje wszystkie problemy z escape'owaniem znaków
        specjalnych ($, \", \\, backtick) w Termux→ADB→shell pipeline.
        """
        script = (
            "#!/system/bin/sh\n"
            f"export RISH_APPLICATION_ID={app_id}\n"
            f"DEX={cls.DEX_PATH}\n"
            'if [ "$1" = "-c" ]; then\n'
            '  shift; CMD="$*"\n'
            '  exec /system/bin/app_process'
            ' -Djava.class.path="$DEX" /system/bin'
            ' --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader'
            ' -c "$CMD"\n'
            "else\n"
            '  exec /system/bin/app_process'
            ' -Djava.class.path="$DEX" /system/bin'
            ' --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader'
            ' "$@"\n'
            "fi\n"
        )
        b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
        # Android busybox base64 obsługuje -d; standardowy base64 też
        deploy_cmd = (
            f"echo '{b64}' | base64 -d > {cls.BIN_PATH} "
            f"&& chmod 755 {cls.BIN_PATH}"
        )
        out = RemoteTransport.sh(deploy_cmd)
        if "error" not in out.lower():
            L.ok(f"Wrapper wdrożony (ctx={app_id}): {cls.BIN_PATH}")
        else:
            L.warn(f"Deploy wrapper: {out[:60]}")

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def _verify_dex(cls) -> bool:
        if DRY_RUN:
            return True
        out = RemoteTransport.sh(f"ls -la {cls.DEX_PATH} 2>/dev/null")
        if cls.DEX_PATH in out:
            L.ok(f"DEX zweryfikowany: {cls.DEX_PATH}")
            return True
        L.err(f"Brak: {cls.DEX_PATH}")
        L.info(f"Wgraj: adb push rish_shizuku.dex {cls.DEX_PATH}")
        return False

    @staticmethod
    def _esc(cmd: str) -> str:
        """Escape apostrofów dla single-quoted shell argument."""
        return cmd.replace("'", "'\\''")


# ==============================================================================
# [5] BCM72604 HARDWARE OPTIMIZER
# ==============================================================================
class BCM72604Optimizer:
    """
    Tweaki setprop specyficzne dla BCM72604 (ARM Cortex-A15 + VideoCore IV).
    Źródła: VC4-AG100-R, ARM Cortex-A15 TRM §A2.6.2, BCM72604 datasheet.

    UWAGA: setprop przez rish (nie przez ADB shell) — omija SELinux deny
    na ro.* i persist.* dla procesu shell uid=2000.
    """

    # (prop, wartość, opis z uzasadnieniem sprzętowym)
    PROPS: List[Tuple[str, str, str]] = [
        # VC4: brak Vulkan na BCM72604 — Skia GL jest właściwym backendem
        ("debug.hwui.renderer",
         "skiagl",
         "VC4: Skia GL renderer (Vulkan nieobsługiwany na BCM72604)"),
        ("debug.renderengine.backend",
         "skiaglthreaded",
         "VC4: wielowątkowy Skia GL RenderEngine"),

        # A15 TRM §A2.6.2: SDIV/UDIV dostępne w natywnym ISA Cortex-A15
        ("dalvik.vm.isa.arm.features",
         "default,idiv",
         "A15: sprzętowy integer divide (SDIV/UDIV w A15 ISA)"),

        # SurfaceFlinger: redukuje DequeueBufferDuration (anomalia 14.2ms)
        ("debug.sf.disable_backpressure",
         "1",
         "SF: wyłącz back-pressure (fix 14.2ms DequeueBufferDuration)"),
        ("debug.sf.latch_unsignaled",
         "1",
         "SF: pobierz niesygnalizowane bufory (triple-buffering bypass)"),

        # A15: wymusza pełny takt 1.4GHz
        ("persist.sys.powermode",
         "1",
         "A15: tryb pełnej mocy (1.4GHz max)"),

        # HW kompozycja — potwierdzona wartość PlayBOX
        ("persist.sys.ui.hw",
         "true",
         "HWUI: wymuś akcelerację sprzętową UI"),

        # HDMI keep-awake — zapobiega resync HDMI po CEC wakeup
        ("persist.sys.hdmi.keep_awake",
         "true",
         "HDMI: zapobiegaj resync po CEC wakeup"),

        # LMK: filecache 90MB (2GB RAM, vm.swappiness=0, brak ZRAM/swap)
        # ro.lmk.use_minfree_levels=false → sysfs minfree ignorowane
        ("ro.lmk.filecache_min_kb",
         "92160",
         "LMK: filecache min 90MB (BCM72604 2GB, brak swap)"),

        # Dalvik heap — potwierdzone wartości PlayBOX
        ("dalvik.vm.heapminfree",
         "2m",
         "Dalvik: heapminfree 2MB"),
        ("dalvik.vm.heapmaxfree",
         "16m",
         "Dalvik: heapmaxfree 16MB"),

        # Telemetria — wyłącz zbędne wakelocki
        ("persist.sys.send_action_app_error",
         "0",
         "Telemetria: wyłączona"),
    ]

    @classmethod
    def apply_all(cls) -> Dict[str, bool]:
        L.hdr("BCM72604 Hardware Optimizer")
        results: Dict[str, bool] = {}
        for prop, val, desc in cls.PROPS:
            out = PrivilegeEngine.rish(f"setprop {prop} {val}")
            ok = not any(kw in out.lower() for kw in ("error", "failed", "denied"))
            results[prop] = ok
            (L.ok if ok else L.warn)(f"{prop} = {val}   [{desc}]")
        return results


# ==============================================================================
# [6] NETWORK OPTIMIZER — TCP stack dla 4K streaming
# ==============================================================================
class NetworkOptimizer:
    """
    Optymalizacja stosu TCP dla strumieniowania 4K (PlayBOX/PlayNow WiFi 5GHz).
    Wartości buforów: min/default/max dla Tx i Rx.
    """

    @classmethod
    def apply(cls) -> None:
        L.hdr("Network Optimizer — TCP 4K Stack")
        tweaks: List[Tuple[str, str]] = [
            # 512KB/1MB/2MB Tx, 256KB/512KB/1MB Rx
            (
                "settings put global net.tcp.buffersize.wifi "
                "'524288,1048576,2097152,262144,524288,1048576'",
                "TCP WiFi bufory: 512K/1M/2M Tx │ 256K/512K/1M Rx"
            ),
            # Initial RWND 60 segmentów ≈ 90KB przy MTU 1500
            (
                "settings put global tcp_default_init_rwnd 60",
                "TCP initial RWND: 60 segmentów (~90KB)"
            ),
            # Watchdog timeout: anti-crash guard
            (
                "settings put global sys.watchdog.timeout 60000",
                "Watchdog: 60s timeout (anti-crash guard)"
            ),
            # DNS: Cloudflare — one.one.one.one (nie dns.cloudflare.com)
            (
                "ndc resolver setnetdns 100 '' 1.1.1.1 1.0.0.1",
                "DNS: Cloudflare 1.1.1.1 + 1.0.0.1 (one.one.one.one)"
            ),
            # Captive portal — Google HTTPS check
            (
                "settings put global captive_portal_https_url "
                "https://connectivitycheck.gstatic.com/generate_204",
                "Captive portal: Google HTTPS check"
            ),
        ]
        for cmd, desc in tweaks:
            out = PrivilegeEngine.rish(cmd)
            ok = "exception" not in out.lower()
            (L.ok if ok else L.warn)(desc + (f"  [{out[:30]}]" if not ok else ""))


# ==============================================================================
# [7] MEMORY OPTIMIZER
# ==============================================================================
class MemoryOptimizer:
    """
    Zarządzanie pamięcią BCM72604 (2GB RAM, vm.swappiness=0, brak ZRAM/swap).
    ro.lmk.use_minfree_levels=false → sysfs LMK minfree ignorowane.
    """

    @classmethod
    def drop_caches(cls, level: int = 3) -> None:
        """
        Zwalnia pamięć podręczną VFS.
        1 = pagecache, 2 = dentries+inodes, 3 = all
        """
        L.info(f"Drop VFS caches (poziom {level})...")
        PrivilegeEngine.rish(f"sync && echo {level} > /proc/sys/vm/drop_caches")
        L.ok("Pamięć VFS zwolniona.")

    @classmethod
    def kill_background(cls) -> None:
        L.info("Terminowanie procesów w tle (am kill-all)...")
        PrivilegeEngine.rish("am kill-all")
        L.ok("Procesy tła zakończone.")

    @classmethod
    def trim_caches(cls, size: str = "2G") -> None:
        L.info(f"Trim package caches ({size})...")
        PrivilegeEngine.rish(f"pm trim-caches {size}")
        L.ok("Cache pakietów przycięty.")

    @classmethod
    def full_gc(cls) -> None:
        """Pełna sekwencja GC: kill-all → trim → sync → drop."""
        L.hdr("Memory Full GC")
        cls.kill_background()
        cls.trim_caches()
        cls.drop_caches(3)
        L.ok("Pełny GC zakończony.")

    @classmethod
    def get_meminfo(cls) -> Dict[str, int]:
        out = RemoteTransport.sh("cat /proc/meminfo 2>/dev/null")
        info: Dict[str, int] = {}
        for line in out.splitlines():
            m = re.match(r"(\w+):\s+(\d+)", line)
            if m:
                info[m.group(1)] = int(m.group(2))
        return info


# ==============================================================================
# [8] UI OPTIMIZER — HWUI + SurfaceFlinger
# ==============================================================================
class UIOptimizer:
    """
    Optymalizacje UI przez settings provider (rish).
    Skupia się na SmartTube PlaybackActivity (wysokie jitter na BCM72604).
    """

    @classmethod
    def apply(cls) -> None:
        L.hdr("UI Optimizer — HWUI + SurfaceFlinger")
        tweaks: List[Tuple[str, str]] = [
            # Redukuje jitter SmartTube przez cache warstw
            ("settings put global surface_flinger enable_layer_caching true",
             "SF: cache warstw aktywny (fix SmartTube jitter)"),
            # Latencja SysUI
            ("settings put global sysui_latency_reboot_count 0",
             "SysUI: latency count reset"),
            # HW accel
            ("settings put system hardware_acceleration_enabled 1",
             "HW accel: wymuszony"),
            # Animacje UI 0.5x (kompromis płynność/latencja)
            ("settings put global window_animation_scale 0.5",
             "Animacje okien: 0.5x"),
            ("settings put global transition_animation_scale 0.5",
             "Animacje przejść: 0.5x"),
            ("settings put global animator_duration_scale 0.5",
             "Animacje obiektów: 0.5x"),
        ]
        for cmd, desc in tweaks:
            out = PrivilegeEngine.rish(cmd)
            ok = "exception" not in out.lower()
            (L.ok if ok else L.warn)(desc)


# ==============================================================================
# [9] PRIVACY HARDENER
# ==============================================================================
class PrivacyHardener:
    @classmethod
    def apply(cls) -> None:
        L.hdr("Privacy Hardener")
        tweaks: List[Tuple[str, str]] = [
            ("settings put global send_action_app_error 0",
             "Telemetria crash: wyłączona"),
            ("settings put secure limit_ad_tracking 1",
             "Śledzenie reklam: wyłączone"),
            ("settings put global auto_time_zone 0",
             "Auto-timezone: wyłączony"),
            # UsageStats wakelocki — wyłącz jeśli możliwe
            ("pm disable-user --user 0 com.android.providers.usagestats "
             "2>/dev/null || true",
             "UsageStats provider: wyłączony"),
        ]
        for cmd, desc in tweaks:
            out = PrivilegeEngine.rish(cmd)
            ok = "exception" not in out.lower()
            (L.ok if ok else L.warn)(desc)


# ==============================================================================
# [10] DIAGNOSTIC ENGINE
# ==============================================================================
class DiagnosticEngine:
    @classmethod
    def run_full(cls) -> None:
        L.hdr("Pełna Diagnostyka Systemu")
        cls._device_info()
        cls._rish_status()
        cls._memory_report()
        cls._thermal_report()
        cls._shizuku_health()

    @classmethod
    def _device_info(cls) -> None:
        L.info("=== Informacje o urządzeniu ===")
        for prop, label in [
            ("ro.product.model",         "Model"),
            ("ro.build.version.release", "Android"),
            ("ro.build.id",              "Build ID"),
            ("ro.board.platform",        "Platform"),
        ]:
            val = RemoteTransport.sh(f"getprop {prop}")
            print(f"    {L.C['d']}{label}:{L.C['r']} {val}")

    @classmethod
    def _rish_status(cls) -> None:
        L.info("=== Status Rish / Shizuku ===")
        result = PrivilegeEngine.rish("id && getprop ro.build.id")
        for line in result.splitlines():
            print(f"    {line}")
        strat = PrivilegeEngine.strategy_name()
        print(f"    {L.C['h']}Strategia: {strat}{L.C['r']}")
        shizuku_ok = ShizukuLifecycle.is_running()
        print(f"    {L.C['h']}Shizuku server: "
              f"{'aktywny' if shizuku_ok else 'nieaktywny'}{L.C['r']}")

    @classmethod
    def _memory_report(cls) -> None:
        L.info("=== Pamięć RAM ===")
        mem = MemoryOptimizer.get_meminfo()
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        used  = total - avail
        pct   = used / total * 100 if total else 0
        color = L.C['s'] if pct < 70 else L.C['w'] if pct < 85 else L.C['e']
        print(f"    Całkowita: {total // 1024} MB")
        print(f"    Dostępna:  {avail // 1024} MB")
        print(f"    Użyta:     {color}{used // 1024} MB ({pct:.1f}%){L.C['r']}")

    @classmethod
    def _thermal_report(cls) -> None:
        L.info("=== Termika BCM72604 ===")
        for zone in range(6):
            raw = RemoteTransport.sh(
                f"cat /sys/class/thermal/thermal_zone{zone}/temp 2>/dev/null"
            )
            if raw.isdigit():
                temp = int(raw) / 1000
                color = (L.C['s'] if temp < 70 else
                         L.C['w'] if temp < 85 else L.C['e'])
                name_raw = RemoteTransport.sh(
                    f"cat /sys/class/thermal/thermal_zone{zone}/type 2>/dev/null"
                )
                print(f"    Zone {zone} ({name_raw}): {color}{temp:.1f}°C{L.C['r']}")

    @classmethod
    def _shizuku_health(cls) -> None:
        L.info("=== Shizuku / DEX Health ===")
        # DEX size
        dex_info = RemoteTransport.sh(
            f"ls -la {PrivilegeEngine.DEX_PATH} 2>/dev/null"
        )
        print(f"    DEX: {dex_info if dex_info else 'BRAK'}")
        # Wrapper
        bin_info = RemoteTransport.sh(
            f"ls -la {PrivilegeEngine.BIN_PATH} 2>/dev/null"
        )
        print(f"    Wrapper: {bin_info if bin_info else 'BRAK'}")
        # Shizuku PID
        pid_info = RemoteTransport.sh("ps -A 2>/dev/null | grep shizuku")
        print(f"    Shizuku: {pid_info if pid_info else 'NIEAKTYWNY'}")


# ==============================================================================
# [11] FULL OPTIMIZATION SUITE
# ==============================================================================
class FullOptimizationSuite:
    """Orkiestruje wszystkie moduły w pełną sekwencję optymalizacji."""

    @classmethod
    def run(cls, skip_privacy: bool = False) -> None:
        L.hdr(f"Titanium v{VERSION} — Pełna Optymalizacja")
        t0 = time.time()

        BCM72604Optimizer.apply_all()
        NetworkOptimizer.apply()
        UIOptimizer.apply()
        if not skip_privacy:
            PrivacyHardener.apply()
        MemoryOptimizer.full_gc()

        elapsed = time.time() - t0
        L.ok(f"Optymalizacja zakończona w {elapsed:.1f}s")


# ==============================================================================
# [12] INTERACTIVE MENU
# ==============================================================================
class MasterUI:
    MENU: List[Tuple[str, str]] = [
        ("1", "Pełna Optymalizacja (BCM72604 + Sieć + UI + GC)"),
        ("2", "Quick GC (Kill-All + Drop Caches)"),
        ("3", "Hardware Props (setprop BCM72604)"),
        ("4", "Sieć (TCP 4K bufory + DNS)"),
        ("5", "Privacy Hardener"),
        ("6", "UI Optimizer (HWUI + SF)"),
        ("7", "Pełna Diagnostyka"),
        ("8", "Status Rish (uprawnienia + strategia)"),
        ("9", "Podgląd RAM"),
        ("d", "Przełącz DRY_RUN"),
        ("r", "Reinicjuj Privilege Engine"),
        ("q", "Wyjście"),
    ]

    @classmethod
    def show(cls) -> None:
        global DRY_RUN
        while True:
            subprocess.run(["clear"])
            dry_tag = f" {L.C['w']}[DRY_RUN]{L.C['r']}" if DRY_RUN else ""
            print(
                f"\n{L.C['h']}{L.C['b']}"
                f"╔══════════════════════════════════════════════════════════╗\n"
                f"║  TITANIUM MASTER v{VERSION}  │  {RemoteTransport.dev:<25}    ║\n"
                f"║  Rish: {PrivilegeEngine.strategy_name():<20}  "
                f"Shizuku: {'OK' if ShizukuLifecycle.is_running() else 'OFF'}     ║\n"
                f"╚══════════════════════════════════════════════════════════╝"
                f"{L.C['r']}{dry_tag}\n"
            )
            for key, label in cls.MENU:
                if key == 'q':
                    color = L.C['e']
                elif key in ('d', 'r'):
                    color = L.C['w']
                else:
                    color = L.C['c']
                print(f"  {color}[{key}]{L.C['r']} {label}")

            choice = input(f"\n  {L.C['w']}Wybór ❯ {L.C['r']}").strip().lower()

            if   choice == '1': FullOptimizationSuite.run()
            elif choice == '2': MemoryOptimizer.full_gc()
            elif choice == '3': BCM72604Optimizer.apply_all()
            elif choice == '4': NetworkOptimizer.apply()
            elif choice == '5': PrivacyHardener.apply()
            elif choice == '6': UIOptimizer.apply()
            elif choice == '7': DiagnosticEngine.run_full()
            elif choice == '8':
                out = PrivilegeEngine.rish("id")
                L.info(f"Wynik rish: {out}")
                L.info(f"Strategia:  {PrivilegeEngine.strategy_name()}")
            elif choice == '9':
                mem = MemoryOptimizer.get_meminfo()
                L.info(f"RAM Total:     {mem.get('MemTotal', 0) // 1024} MB")
                L.info(f"RAM Available: {mem.get('MemAvailable', 0) // 1024} MB")
                L.info(f"RAM Cached:    {mem.get('Cached', 0) // 1024} MB")
            elif choice == 'd':
                DRY_RUN = not DRY_RUN
                L.info(f"DRY_RUN: {'ON' if DRY_RUN else 'OFF'}")
            elif choice == 'r':
                PrivilegeEngine._active_strategy = 0
                if not PrivilegeEngine.init():
                    L.err("Reinicjalizacja nieudana.")
            elif choice == 'q':
                sys.exit(0)
            else:
                L.warn("Nieznana opcja.")

            input(f"\n  {L.C['d']}Naciśnij Enter, aby kontynuować...{L.C['r']}")


# ==============================================================================
# [13] ENTRY POINT
# ==============================================================================
def main() -> None:
    global DRY_RUN

    parser = argparse.ArgumentParser(
        description=f"PlayBox Titanium v{VERSION} — Master Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Przykłady:\n"
            "  python3 titanium_v20.py --device 192.168.1.100\n"
            "  python3 titanium_v20.py --device 192.168.1.100 --auto\n"
            "  python3 titanium_v20.py --device 192.168.1.100 --diag\n"
            "  python3 titanium_v20.py --device 192.168.1.100 --gc\n"
            "  python3 titanium_v20.py --device 192.168.1.100 --dry-run --auto\n"
        )
    )
    parser.add_argument("--device",      required=True,        help="IP urządzenia TV (np. 192.168.1.100)")
    parser.add_argument("--dry-run",     action="store_true",  help="Symuluj bez wykonywania komend")
    parser.add_argument("--auto",        action="store_true",  help="Pełna optymalizacja bez menu")
    parser.add_argument("--diag",        action="store_true",  help="Tylko diagnostyka")
    parser.add_argument("--gc",          action="store_true",  help="Tylko Quick GC")
    parser.add_argument("--no-privacy",  action="store_true",  help="Pomiń Privacy Hardener")
    args = parser.parse_args()

    if args.dry_run:
        DRY_RUN = True
        L.warn("Tryb DRY_RUN aktywny — komendy nie będą wykonywane na urządzeniu.")

    if not RemoteTransport.connect(args.device):
        sys.exit(1)

    if not PrivilegeEngine.init():
        L.err("Inicjalizacja Privilege Engine nieudana.")
        L.info("Sprawdź: Shizuku uruchomiony na TV, DEX wgrany, ADB podłączone.")
        sys.exit(1)

    if args.diag:
        DiagnosticEngine.run_full()
    elif args.gc:
        MemoryOptimizer.full_gc()
    elif args.auto:
        FullOptimizationSuite.run(skip_privacy=args.no_privacy)
    else:
        MasterUI.show()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n")
        L.warn("Przerwano przez użytkownika.")
        sys.exit(0)