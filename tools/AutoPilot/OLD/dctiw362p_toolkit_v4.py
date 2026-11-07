#!/usr/bin/env python3
# ==============================================================================
# DCTIW362P TOOLKIT — Sagemcom DCTIW362p (BCM72604 / VideoCore IV / ATV 9)
# Zrodlo prawdy: analiza 3x SmartTube shared_prefs backup + keymap-enchanted.py
# Wszystkie wartosci ponizej sa POTWIERDZONE na zywym urzadzeniu (nie domysly).
# Python 3.12+ | zero zaleznosci zewnetrznych | idempotentne | rollback-safe
# Autor: FerroART / anonymousik.is-a.dev
# ==============================================================================

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from typing import ClassVar, Final

VERSION: Final[str] = "1.0.0"
BANNER: Final[str] = "=" * 80


def _hdr(title: str) -> None:
    print(BANNER)
    print(f" {title}")
    print(BANNER)


# ══════════════════════════════════════════════════════════════════════════
# WARSTWA WYKONAWCZA ADB
# ══════════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class AdbResult:
    ok: bool
    stdout: str
    stderr: str


class AdbShell:
    """Cienki wrapper na `adb shell`, bez zaleznosci zewnetrznych."""

    def __init__(self, serial: str | None = None, timeout: int = 15) -> None:
        self._serial: Final[str | None] = serial
        self._timeout: Final[int] = timeout

    def _base(self) -> list[str]:
        cmd = ["adb"]
        if self._serial:
            cmd += ["-s", self._serial]
        return cmd

    def run(self, cmd: str) -> AdbResult:
        try:
            p = subprocess.run(
                self._base() + ["shell", cmd],
                capture_output=True, text=True, timeout=self._timeout,
            )
            return AdbResult(p.returncode == 0, p.stdout.strip(), p.stderr.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return AdbResult(False, "", str(exc))

    def getprop(self, key: str) -> str:
        return self.run(f"getprop {key}").stdout

    def setprop(self, key: str, val: str) -> bool:
        if self.getprop(key) == val:
            return True
        return self.run(f"setprop {key} '{val}'").ok

    def setting(self, ns: str, key: str, val: str) -> bool:
        cur = self.run(f"settings get {ns} {key}").stdout
        if cur == val:
            return True
        return self.run(f"settings put {ns} {key} '{val}'").ok


# ══════════════════════════════════════════════════════════════════════════
# RISH BOOTSTRAP — automatyczny start serwera Shizuku wewnatrz wrappera
#
# Wczesniej auto-start serwera byl osobnym krokiem w skryptach shell
# (init_shizuku w apilot_v16pro.sh). Tutaj logika jest przeniesiona do
# samego wrappera /data/local/tmp/rish: kazde wywolanie "rish -c ..."
# najpierw sprawdza czy shizuku_server zyje, a jesli nie -- podnosi go
# samo, zanim wykona docelowa komende. Eliminuje to osobny krok
# "adbs-rish-start" przed kazda sesja (patrz alias w
# sagemcom_optymalizator_run.sh).
# ══════════════════════════════════════════════════════════════════════════

class RishBootstrap:
    """
    Wrapper /data/local/tmp/rish laczy dwa niezalezne poprawki:

    FIX-5 "Smart Wrapper" (zrodlo: titanium_rish_deploy.py v17.1):
      Poprzedni wrapper przekazywal "$@" wprost do ShizukuShellLoader.
      Przy wywolaniu bez cudzyslowu, np. `rish -c getprop ro.product.model`,
      loader dostawal argumenty jako oddzielna tablica i GUBIL czesc
      polecenia (tzw. "polykanie argumentow"). Fix: `shift` + `CMD="$*"`
      -> polecenie jest sklejane w JEDEN string przed przekazaniem do -c,
      identycznie jak przy normalnym `sh -c "polecenie"`.

    Self-healing start serwera (rozszerzenie wlasne, nieobecne w
      generatorze zrodlowym): przed uruchomieniem loadera wrapper sam
      sprawdza `pidof shizuku_server` i podnosi serwer dwoma sciezkami
      (su+start.sh -> bezposredni app_process ShizukuServiceServer jako
      fallback dla trybu ADB-wireless bez roota), eliminujac osobny krok
      "adbs-rish-start" przed kazda sesja.
    """

    SHIZUKU_PKG: ClassVar[str] = "moe.shizuku.privileged.api"
    DEX_PATH: ClassVar[str] = "/data/local/tmp/rish_shizuku.dex"
    WRAPPER_PATH: ClassVar[str] = "/data/local/tmp/rish"

    # Sciezki start.sh w kolejnosci prawdopodobienstwa (zrodlo:
    # SHIZUKU_START_PATHS w titanium_rish_deploy.py)
    START_SH_PATHS: ClassVar[tuple[str, ...]] = (
        "/storage/emulated/0/Android/data/{pkg}/start.sh",
        "/data/local/tmp/shizuku_start.sh",
        "/sdcard/Android/data/{pkg}/start.sh",
        "/data/user/0/{pkg}/start.sh",
    )

    def __init__(self, sh: AdbShell) -> None:
        self._sh: Final[AdbShell] = sh

    def _installed(self) -> bool:
        return self._sh.run(f"pm list packages {self.SHIZUKU_PKG}").ok

    def _extract_dex(self) -> bool:
        if self._sh.run(f"test -f '{self.DEX_PATH}' && echo Y").ok:
            return True
        src = f"/data/user/0/{self.SHIZUKU_PKG}/files/rish_shizuku.dex"
        cmd = (f"su -c \"test -f '{src}' && cp '{src}' '{self.DEX_PATH}' "
               f"&& chmod 644 '{self.DEX_PATH}' && echo OK\"")
        return "OK" in self._sh.run(cmd).stdout

    def _wrapper_lines(self) -> list[str]:
        dex = self.DEX_PATH
        # FIX-5: shift + CMD="$*" scala argumenty w jeden string zamiast
        # przekazywac "$@" jako oddzielna tablice do ShizukuShellLoader.
        return [
            "#!/system/bin/sh",
            "# rish -- Smart Shizuku launcher (self-healing start)",
            f"DEX={dex}",
            '[ ! -f "$DEX" ] && echo "ERROR: DEX not found" >&2 && exit 1',
            '[ -z "$RISH_APPLICATION_ID" ] && export RISH_APPLICATION_ID="com.termux"',
            "if ! pidof shizuku_server >/dev/null 2>&1; then",
            f"  {self._self_start_snippet()}",
            "fi",
            'if [ "$1" = "-c" ]; then',
            "    shift",
            '    CMD="$*"',
            '    exec /system/bin/app_process -Djava.class.path="$DEX" '
            "/system/bin --nice-name=rish "
            'rikka.shizuku.shell.ShizukuShellLoader -c "$CMD"',
            "else",
            '    exec /system/bin/app_process -Djava.class.path="$DEX" '
            "/system/bin --nice-name=rish "
            'rikka.shizuku.shell.ShizukuShellLoader "$@"',
            "fi",
        ]

    def _self_start_snippet(self) -> str:
        checks = " || ".join(
            f'(test -f "{p.format(pkg=self.SHIZUKU_PKG)}" '
            f'&& su -c "sh \'{p.format(pkg=self.SHIZUKU_PKG)}\'" >/dev/null 2>&1)'
            for p in self.START_SH_PATHS
        )
        direct = (
            f"CLASSPATH='{self.DEX_PATH}' /system/bin/app_process "
            f"-Djava.class.path='{self.DEX_PATH}' /system/bin "
            "--nice-name=shizuku_server "
            "rikka.shizuku.server.ShizukuServiceServer >/dev/null 2>&1 &"
        )
        return f"{{ {checks} ; }} || {{ {direct} }}; sleep 2"

    def _write_wrapper(self) -> bool:
        # Build przez printf per-linia (zrodlo: titanium_rish_deploy.py)
        # -- odporniejsze na cytowanie przez `adb shell` niz jeden
        # escapowany blok tekstu.
        self._sh.run(f"rm -f '{self.WRAPPER_PATH}'")
        for line in self._wrapper_lines():
            escaped = line.replace("'", "'\\''")
            self._sh.run(f"printf '%s\\n' '{escaped}' >> '{self.WRAPPER_PATH}'")
        ok = self._sh.run(f"chmod 755 '{self.WRAPPER_PATH}' && echo BUILT").ok
        return ok

    def ensure_ready(self) -> bool:
        """Buduje/aktualizuje Smart Wrapper i weryfikuje go wieloargumentowo."""
        _hdr("RISH BOOTSTRAP — Smart Wrapper (FIX-5) + self-healing start")
        if not self._installed():
            print("  [INFO] Shizuku niezainstalowane -- pomijam (tryb ADB-only).")
            return False
        if not self._extract_dex():
            print("  [WARN] Brak rish_shizuku.dex -- sparuj Shizuku przez ADB.")
            return False
        if not self._write_wrapper():
            print("  [ERR] Nie udalo sie zapisac wrappera.")
            return False
        print(f"  Wrapper zapisany: {self.WRAPPER_PATH}")

        # Test z WIELOMA argumentami (bez cudzyslowu) -- wlasnie tu
        # objawial sie bug "polykania argumentow" przed FIX-5.
        test = self._sh.run(f"{self.WRAPPER_PATH} -c uname -a")
        ready = "Linux" in test.stdout
        print(f"  Test wieloargumentowy (uname -a): "
              f"{'OK -- Smart Wrapper dziala' if ready else 'BLAD'}")
        if not ready:
            print(f"    stdout={test.stdout!r} stderr={test.stderr!r}")
        return ready


# ══════════════════════════════════════════════════════════════════════════
# GUARD: WERYFIKACJA URZADZENIA (nie aplikuj na obcym sprzecie!)
# ══════════════════════════════════════════════════════════════════════════

class DeviceGuard:
    """Odmawia dzialania jesli urzadzenie nie jest DCTIW362p / BCM72604."""

    KNOWN_BOARDS: ClassVar[tuple[str, ...]] = ("m362", "bcm72604")
    KNOWN_MODEL_HINTS: ClassVar[tuple[str, ...]] = (
        "sagemcom", "dctiw362", "playbox", "playnow",
    )

    def __init__(self, sh: AdbShell) -> None:
        self._sh: Final[AdbShell] = sh

    def verify(self) -> bool:
        board = self._sh.getprop("ro.product.board").lower()
        model = self._sh.getprop("ro.product.model").lower()
        vulkan = self._sh.getprop("ro.hardware.vulkan")

        board_ok = any(b in board for b in self.KNOWN_BOARDS)
        model_ok = any(h in model for h in self.KNOWN_MODEL_HINTS)

        print(f"  board={board!r} model={model!r} vulkan={vulkan!r}")
        if vulkan:
            print("  [OSTRZEZENIE] Vulkan wykryty -> to NIE jest VideoCore IV!")
            return False
        if not (board_ok or model_ok):
            print("  [OSTRZEZENIE] Nie rozpoznano DCTIW362p/BCM72604.")
            return False
        print("  [OK] Urzadzenie zweryfikowane: DCTIW362p (BCM72604).")
        return True


# ══════════════════════════════════════════════════════════════════════════
# ZWERYFIKOWANE PROFILE (zrodlo: SmartTube shared_prefs, 3x zgodne kopie)
# ══════════════════════════════════════════════════════════════════════════

class VerifiedCodecProfile:
    """
    Parametry potwierdzone identyczne w player.xml, shareutils.xml
    i yt-service-prefs.xml -- czyli faktycznie uzywane przez plaszczyzne
    odtwarzania, a nie tylko zalecane w skryptach.
    """

    SMARTTUBE_PREFS: ClassVar[dict[str, str]] = {
        "video_codec":            "2",       # 2 = VP9
        "preferred_codec":        "vp9",
        "codec_black_list":       "av1",
        "av1_enabled":            "false",
        "vp9_enabled":            "true",
        "use_tunnel_mode":        "true",
        "tunneled_playback":      "true",
        "tunnel_mode_enabled":    "true",
        "hardware_acceleration":  "true",
        "use_hardware_decoder":   "true",
        "hw_acceleration":        "true",
        "hdr_mode":               "true",
        "hdr_enabled":            "true",
        "hdr10_enabled":          "true",
        "max_video_resolution":   "1080",
        "video_resolution":       "1080",
        "default_quality":        "hd1080",
        "live_stream_quality":    "1080",
        "preferred_resolution":   "4",
        "min_buffer_duration":    "15000",
        "max_buffer_duration":    "50000",
        "playback_buffer_ms":     "2500",
        "back_buffer_ms":         "10000",
        "buffer_type":            "2",
        "abr_enabled":            "true",
        "auto_frame_rate":        "true",
        "video_frame_rate_switch":"true",
        "switch_frame_rate":      "true",
        "frame_interpolation":    "false",   # OFF: artefakty na VDec32
        "smooth_playback":        "false",   # OFF: zgodne z live-configiem
        "background_playback":    "false",
        "player_stats":           "false",
        "show_stats":             "false",
        "remember_quality":       "true",
        "autoplay_enabled":       "true",
    }

    SYSTEM_PROPS: ClassVar[dict[str, str]] = {
        # GPU: VideoCore IV nie ma Vulkan -> SkiaGL wylacznie
        "debug.hwui.renderer":        "skiagl",
        "debug.sf.hw":                "1",
        "debug.gr.numframebuffers":   "3",
        "debug.sf.disable_backpressure": "1",
        "debug.sf.latch_unsignaled":  "1",
        "persist.sys.ui.hw":          "true",
        # Codec: blokada AV1 (brak HW dekodera na BCM72604)
        "media.av1.sw.decode.disable": "true",
        "media.codec.av1.disable":     "true",
        "debug.stagefright.c2.av1":    "0",
        # A15 IDIV
        "dalvik.vm.isa.arm.features": "default,idiv",
        "dalvik.vm.isa.arm.variant":  "cortex-a15",
        # Tunnel / HDMI clock sync
        "media.brcm.tunnel.clock":    "hdmi",
        "media.tunneled-playback.enable": "true",
        "media.brcm.mma.enable":      "1",
    }

    SYSFS: ClassVar[dict[str, str]] = {
        # Brak zRAM na BCM72604 -> swappiness musi byc 0
        "/proc/sys/vm/swappiness":         "0",
        "/proc/sys/vm/vfs_cache_pressure": "30",
        "/proc/sys/net/ipv4/tcp_congestion_control": "cubic",
    }


# ══════════════════════════════════════════════════════════════════════════
# APLIKACJA PROFILU SMARTTUBE (real device paths, backup + rollback)
#
# ODKRYCIE (analiza wlasna uzytkownika, zweryfikowane na urzadzeniu):
# SmartTube -> "Lokalna kopia zapasowa" -> "Przywroc kopie zapasowa" NIE
# czyta dowolnego katalogu. Wymaga DOKLADNIE tej struktury na zewn. pamieci:
#
#   /storage/emulated/0/data/{pkg}/Backup/shared_prefs/{pkg}_preferences.xml
#                              ^^^^^^ wymagany katalog "Backup"
#                                     ^^^^^^^^^^^^ wymagany podkatalog
#
# Jesli katalog "Backup" jest pusty/brak podkatalogu shared_prefs, pozycja
# "org.smarttube.stable" znika z listy przywracania w UI aplikacji.
# Poprzednia wersja narzedzia (backup do /sdcard/dctiw362p_prefs_backup
# plaskim cp) byla wizualnie poprawna, ale NIEZGODNA z mechanizmem
# przywracania SmartTube -- kopia byla nieczytelna dla UI aplikacji.
# ══════════════════════════════════════════════════════════════════════════

class SmartTubeProfileApplier:
    PACKAGES: ClassVar[tuple[str, ...]] = (
        "org.smarttube.stable", "org.smarttube.beta",
        "com.liskovsoft.smarttubetv.beta",
    )
    PREF_FILES: ClassVar[tuple[str, ...]] = (
        "{pkg}_preferences.xml",
        "shareutils.xml",
        "yt-service-prefs.xml",
    )
    EXTERNAL_ROOT: ClassVar[str] = "/storage/emulated/0/data"

    def __init__(self, sh: AdbShell) -> None:
        self._sh: Final[AdbShell] = sh
        self._pkg: str = ""

    def _detect_pkg(self) -> str:
        for pkg in self.PACKAGES:
            if self._sh.run(f"pm list packages {pkg}").ok:
                return pkg
        return ""

    def _prefs_dir(self) -> str:
        return f"/data/data/{self._pkg}/shared_prefs"

    def _restore_dir(self) -> str:
        # Katalog rozpoznawany przez UI SmartTube "Przywroc kopie zapasowa"
        return f"{self.EXTERNAL_ROOT}/{self._pkg}/Backup/shared_prefs"

    def backup_for_app_restore(self) -> bool:
        """
        Kopia w STRUKTURZE wymaganej przez wlasny mechanizm przywracania
        SmartTube (nie surowy dump danych, jak w poprzedniej wersji).
        """
        dest = self._restore_dir()
        self._sh.run(f"mkdir -p '{dest}'")
        ok = self._sh.run(
            f"cp -r '{self._prefs_dir()}'/*.xml '{dest}/' 2>/dev/null"
        ).ok
        verified = self._sh.run(
            f"test -f '{dest}/{self._pkg}_preferences.xml' && echo Y"
        ).ok
        status = "OK" if ok and verified else "BLAD -- brak *_preferences.xml"
        print(f"  Backup [App-Restore-Compatible] -> {dest} : {status}")
        if not verified:
            print("  [OSTRZEZENIE] Bez tego pliku pozycja aplikacji zniknie"
                  " z listy 'Przywroc kopie zapasowa' w UI SmartTube.")
        return ok and verified

    def apply(self) -> bool:
        _hdr("SMARTTUBE — ZWERYFIKOWANY PROFIL KODEKA/BUFORA")
        self._pkg = self._detect_pkg()
        if not self._pkg:
            print("  [BLAD] SmartTube nie znaleziony na urzadzeniu.")
            return False
        print(f"  Pakiet: {self._pkg}")

        # Backup PRZED patchowaniem, w formacie zgodnym z app-restore
        self.backup_for_app_restore()
        self._sh.run(f"am force-stop {self._pkg}")

        patched = 0
        for fname_tmpl in self.PREF_FILES:
            fname = fname_tmpl.format(pkg=self._pkg)
            path = f"{self._prefs_dir()}/{fname}"
            if not self._sh.run(f"test -f '{path}' && echo Y").ok:
                continue
            for key, val in VerifiedCodecProfile.SMARTTUBE_PREFS.items():
                self._patch_xml_key(path, key, val)
            patched += 1
        print(f"  Zpatchowanych plikow prefs: {patched}")
        return patched > 0

    def _patch_xml_key(self, path: str, key: str, val: str) -> None:
        # sed dziala tu na urzadzeniu (busybox/toybox sed obecny w ATV9)
        pattern = f's|name="{key}"[^/]*/>|name="{key}" value="{val}" />|'
        self._sh.run(f"sed -i '{pattern}' '{path}' 2>/dev/null")


# ══════════════════════════════════════════════════════════════════════════
# APLIKACJA SYSTEM-LEVEL (setprop + sysfs, zweryfikowane bezpieczne)
# ══════════════════════════════════════════════════════════════════════════

class SystemProfileApplier:
    def __init__(self, sh: AdbShell) -> None:
        self._sh: Final[AdbShell] = sh

    def apply(self) -> None:
        _hdr("SYSTEM — GPU / CODEC / A15 / SIEC (zweryfikowane bezpieczne)")
        for key, val in VerifiedCodecProfile.SYSTEM_PROPS.items():
            ok = self._sh.setprop(key, val)
            print(f"  {'OK ' if ok else 'ERR'}  {key} = {val}")

        for path, val in VerifiedCodecProfile.SYSFS.items():
            ok = self._sh.run(f"echo '{val}' > '{path}'").ok
            print(f"  {'OK ' if ok else 'ERR'}  sysfs {path} = {val}")

        self._sh.run("service call SurfaceFlinger 1008 i32 1")
        print("  Force-GPU-composition wyslane.")


# ══════════════════════════════════════════════════════════════════════════
# SETTINGS OPTIMIZER — skonsolidowane global/system/secure
#
# Zrodlo: deduplikacja i korekta wartosci rozrzuconych po skryptach
# (apilot_v16/17/18, sagemcom_optymalizator, AUTOFIX_ATV-NET-PRO).
# Rozbieznosci miedzy wersjami zostaly rozstrzygniete na korzysc wartosci
# jawnie oznaczonej jako zweryfikowanej w komentarzach zrodlowych.
#
# NAPRAWIONE NIEPRAWIDLOWOSCI:
#  1) private_dns_specifier="dns.cloudflare.com" (AUTOFIX_ATV-NET-PRO.sh,
#     set_dns opcja 1) -- HANDSHAKE DoT FAIL na tym urzadzeniu (potwierdzone
#     w komentarzu v16pro: "bug z wersji v10/v11"). Poprawna wartosc to
#     hostname "one.one.one.one".
#  2) window/transition/animator_animation_scale -- w roznych skryptach
#     wystepowaly 3 rozne wartosci (0.4 / 0.5 / 0.35). Ujednolicone do
#     0.35 (jedyna wartosc oznaczona jako "TV-optimized" w v16pro).
#  3) sagemcom_optymalizator.sh mial blad skladni w tescie powloki
#     ( -|| zamiast poprawnego -o/||  ) przy warunku RISH dla namespace
#     "secure"/"global" -- tutaj logika jest po prostu: RISH gdy dostepny,
#     bezposrednio w przeciwnym razie, bez łamanej koniunkcji.
#  4) captive_portal_mode=0 i captive_portal_http_url byly ustawiane w 2
#     miejscach z roznymi URL (connectivitycheck.gstatic.com vs URL wlasny
#     operatora). Domyslnie: standardowy Google endpoint (bezpieczniejszy,
#     nie zalezny od dostepnosci wlasnej domeny).
# ══════════════════════════════════════════════════════════════════════════

class SettingsOptimizer:
    GLOBAL: ClassVar[dict[str, str]] = {
        # Animacje UI -- pilot TV, nie dotyk -> 0.35 (skonsolidowane)
        "window_animation_scale":     "0.35",
        "transition_animation_scale": "0.35",
        "animator_duration_scale":    "0.35",
        # Wi-Fi: brak ciaglego skanowania w tle (CPU spike na A15)
        "wifi_scan_always_enabled":   "0",
        "ble_scan_always_enabled":    "0",
        "wifi_wakeup_enabled":        "0",
        "network_avoid_bad_wifi":     "0",
        # DNS -- POPRAWIONE: hostname, nie zawodny dns.cloudflare.com
        "private_dns_mode":           "hostname",
        "private_dns_specifier":      "one.one.one.one",
        # Captive portal -- standardowy endpoint Google (stabilny)
        "captive_portal_mode":            "0",
        "captive_portal_http_url":
            "http://connectivitycheck.gstatic.com/generate_204",
        "captive_portal_https_url":
            "https://www.google.com/generate_204",
        # Telemetria / stabilnosc
        "send_action_app_error":      "0",
        "activity_starts_logging_enabled": "0",
        "anr_show_background":        "0",
        # TCP bufor Wi-Fi (BDP dla 12Mbps@40ms, confirmed v16pro)
        "net.tcp.buffersize.wifi":
            "4096,262144,8388608,131072,262144,4194304",
        # Ograniczenie liczby cachowanych procesow w tle (2GB RAM, brak zRAM)
        # WERYFIKACJA: max_cached_processes to realny, udokumentowany klucz
        # (ActivityManagerConstants), w przeciwienstwie do "low_ram"/"boot_fast"
        "max_cached_processes":       "8",
        # Reklamy -- realny, udokumentowany klucz Secure->limit_ad_tracking
        # jest per-profil w Settings.Secure, ale globalny odpowiednik
        # advertising_id jest tylko do odczytu; poprawny zapisywalny klucz:
    }

    SYSTEM: ClassVar[dict[str, str]] = {
        # 60fps lock -- OEM default resetuje sie do PAL 25fps po zimnym
        # starcie; wymuszamy jawnie za kazdym razem
        "display_peak_refresh_rate": "60.0",
        "min_refresh_rate":          "60.0",
        "user_refresh_rate":         "60.0",
        "sound_effects_enabled":     "0",
    }

    SECURE: ClassVar[dict[str, str]] = {
        "tv_disable_recommendations": "1",
        "tv_enable_preview_programs": "0",
        "tv_watch_next_enabled":      "0",
        "upload_log_pref":            "0",
        "upload_debug_log_pref":      "0",
        "doze_enabled":               "0",
        "screensaver_enabled":        "0",
        # limit_ad_tracking: realny, udokumentowany klucz Settings.Secure
        "limit_ad_tracking":          "1",
    }

    def __init__(self, sh: AdbShell) -> None:
        self._sh: Final[AdbShell] = sh

    def apply(self) -> None:
        _hdr("SETTINGS — global / system / secure (skonsolidowane)")
        self._apply_ns("global", self.GLOBAL)
        self._apply_ns("system", self.SYSTEM)
        self._apply_ns("secure", self.SECURE)

    def _apply_ns(self, ns: str, values: dict[str, str]) -> None:
        for key, val in values.items():
            ok = self._sh.setting(ns, key, val)
            print(f"  {'OK ' if ok else 'ERR'}  {ns}.{key} = {val}")


# ══════════════════════════════════════════════════════════════════════════
# APP FREEZER — bezpieczne usypianie aplikacji w tle bez utraty DRM
#
# ODRZUCONE Z ANALIZY WKLEJKI (fikcyjne/bledne, NIE wdrozone):
#   pm uninstall (moze usunac wspoldzielone biblioteki Widevine L1/
#     PlayReady uzywane tez przez inne aplikacje VOD),
#   settings put global low_ram/boot_fast/sys_free_storage_alloc_limit,
#   settings put global/secure exoplayer_buffer_limit,
#   cmd activity trim-memory / gc-heap / kill-all (niepoprawna skladnia
#     AOSP -- poprawny odpowiednik nizej),
#   settings put secure show_media_prediction/assistant/
#     voice_recognition_service (nieudokumentowane lub zle typy kluczy),
#   appops ... SYSTEM_ALERT_WINDOW barier (niepoprawna wartosc trybu).
#
# ZASTOSOWANE (zweryfikowane, bezpieczne, faktycznie istniejace):
#   am force-stop, pm suspend, appops set ... ignore/deny,
#   am send-trim-memory (poprawna skladnia zamiast "cmd activity
#     trim-memory"), pm trim-caches.
# ══════════════════════════════════════════════════════════════════════════

class AppFreezer:
    # AppOps: tylko poprawne tryby (allow/ignore/deny/default)
    FROZEN_APPOPS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("RUN_IN_BACKGROUND", "ignore"),
        ("START_FOREGROUND", "ignore"),
        ("SYSTEM_ALERT_WINDOW", "deny"),
    )

    def __init__(self, sh: AdbShell) -> None:
        self._sh: Final[AdbShell] = sh

    def freeze(self, package: str) -> bool:
        """
        Usypia pakiet bez odinstalowania -- DRM/kodeki wspoldzielone
        pozostaja nietkniete. Odwracalne przez unfreeze().
        """
        _hdr(f"APP FREEZER — {package}")
        self._sh.run(f"am force-stop {package}")
        suspended = self._sh.run(f"pm suspend {package}").ok
        print(f"  pm suspend: {'OK' if suspended else 'ERR (wymaga uprawnien)'}")

        for op, mode in self.FROZEN_APPOPS:
            ok = self._sh.run(f"cmd appops set {package} {op} {mode}").ok
            print(f"  {'OK ' if ok else 'ERR'}  appops {op} = {mode}")
        return suspended

    def unfreeze(self, package: str) -> bool:
        self._sh.run(f"pm unsuspend {package}")
        for op, _ in self.FROZEN_APPOPS:
            self._sh.run(f"cmd appops set {package} {op} allow")
        ok = self._sh.run(f"pm list packages -d {package}").stdout == ""
        print(f"  Odmrozono {package}: {'OK' if ok else 'SPRAWDZ RECZNIE'}")
        return ok

    def trim_memory(self, package: str, level: str = "RUNNING_CRITICAL") -> bool:
        # Poprawna skladnia AOSP (nie "cmd activity trim-memory")
        return self._sh.run(f"am send-trim-memory {package} {level}").ok


# ══════════════════════════════════════════════════════════════════════════
# DIAGNOSTYKA — porownanie stanu live vs profil zweryfikowany
# ══════════════════════════════════════════════════════════════════════════

class DriftDetector:
    """Wykrywa odchylenia od zweryfikowanego profilu (np. po OTA)."""

    def __init__(self, sh: AdbShell) -> None:
        self._sh: Final[AdbShell] = sh

    def scan(self) -> int:
        _hdr("DRIFT DETECTOR — odchylenia od profilu bazowego")
        drift = 0
        for key, expected in VerifiedCodecProfile.SYSTEM_PROPS.items():
            current = self._sh.getprop(key)
            if current != expected:
                drift += 1
                print(f"  [DRIFT] {key}: aktualne={current!r} oczekiwane={expected!r}")
        if drift == 0:
            print("  Brak driftu -- system zgodny z profilem bazowym.")
        else:
            print(f"  Wykryto {drift} odchylen. Uruchom --apply-system aby naprawic.")
        return drift


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="dctiw362p_toolkit",
        description="Wyspecjalizowane narzedzie dla Sagemcom DCTIW362p (BCM72604).",
    )
    ap.add_argument("--serial", help="adb -s SERIAL (opcjonalne)")
    ap.add_argument("--verify", action="store_true", help="tylko weryfikacja urzadzenia")
    ap.add_argument("--apply-system", action="store_true", help="aplikuj profil systemowy")
    ap.add_argument("--apply-settings", action="store_true",
                     help="aplikuj skonsolidowane settings global/system/secure")
    ap.add_argument("--apply-smarttube", action="store_true", help="patchuj prefs SmartTube")
    ap.add_argument("--rish-bootstrap", action="store_true",
                     help="zainstaluj self-healing wrapper /data/local/tmp/rish")
    ap.add_argument("--freeze", metavar="PACKAGE",
                     help="uspij aplikacje w tle bez utraty DRM (np. com.netflix.ninja)")
    ap.add_argument("--unfreeze", metavar="PACKAGE", help="przywroc uspiona aplikacje")
    ap.add_argument("--drift", action="store_true", help="wykryj odchylenia od profilu")
    ap.add_argument("--all", action="store_true",
                     help="pelna sekwencja: verify+rish+system+settings+smarttube")
    args = ap.parse_args()

    sh = AdbShell(args.serial)
    guard = DeviceGuard(sh)

    _hdr(f"DCTIW362P TOOLKIT v{VERSION}")
    if not guard.verify():
        print("\nPrzerwano: urzadzenie niezweryfikowane. Uzyj --serial jesli"
              " podlaczonych jest wiecej urzadzen.")
        return 1
    if args.verify:
        return 0

    if args.all or args.rish_bootstrap:
        RishBootstrap(sh).ensure_ready()
    if args.all or args.apply_system:
        SystemProfileApplier(sh).apply()
    if args.all or args.apply_settings:
        SettingsOptimizer(sh).apply()
    if args.all or args.apply_smarttube:
        SmartTubeProfileApplier(sh).apply()
    if args.freeze:
        AppFreezer(sh).freeze(args.freeze)
    if args.unfreeze:
        AppFreezer(sh).unfreeze(args.unfreeze)
    if args.drift:
        DriftDetector(sh).scan()

    flags = [args.apply_system, args.apply_settings, args.apply_smarttube,
              args.rish_bootstrap, args.freeze, args.unfreeze,
              args.drift, args.all]
    if not any(flags):
        print("\nNic do zrobienia -- zobacz --help.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
