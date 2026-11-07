#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smarttube_config.py
================================================================
  PlayBox Titanium -- SmartTube Config Manager
  Eksport / Optymalizacja / Import konfiguracji SmartTube
  Target: Sagemcom DCTIW362P | BCM72604 | Android TV 9 | API 28

  Uzycie:
    python3 smarttube_config.py --device 192.168.1.3:5555
    python3 smarttube_config.py --export-only
    python3 smarttube_config.py --dry-run
    python3 smarttube_config.py --restore ./backup/

  Integracja z Autopilot_v157:
    from smarttube_config import SmartTubeConfigManager
    SmartTubeConfigManager.run_full(device="192.168.1.3:5555")
================================================================
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ================================================================
# Kolory (ASCII only -- Termux safe)
# ================================================================
_R  = "\033[0m"
_G  = "\033[92m"
_Y  = "\033[93m"
_B  = "\033[94m"
_E  = "\033[91m"
_H  = "\033[95m"
_C  = "\033[96m"
_D  = "\033[2m"
_BO = "\033[1m"

def ok(m):   print(_G  + "  [OK] " + str(m) + _R)
def warn(m): print(_Y  + "  [!!] " + str(m) + _R)
def err(m):  print(_E  + "  [XX] " + str(m) + _R)
def info(m): print(_B  + "  [ ] " + str(m) + _R)
def fix(m):  print(_Y  + "  [>>] " + str(m) + _R)
def hdr(m):  print("\n" + _H + _BO + "=" * 62 + "\n  " + str(m) + "\n" + "=" * 62 + _R)
def sub(m):  print("\n" + _C + "  -- " + str(m) + " --" + _R)


# ================================================================
# Stale
# ================================================================

PKG_STABLE  = "org.smarttube.stable"
PKG_BETA    = "org.smarttube.beta"
PKG_LEGACY  = "com.liskovsoft.smarttubetv"

# Katalog roboczy na urzadzeniu
DEVICE_TMP  = "/sdcard/smarttube_cfg_backup"

# Katalog lokalny (na komputerze / Termux)
LOCAL_DIR   = Path.home() / ".playbox_cache" / "smarttube_configs"


# ================================================================
# ADB wrapper (standalone -- bez zaleznosci od Autopilot_v157)
# ================================================================

class _ADB:
    dev: Optional[str] = None
    _TO = 30

    @classmethod
    def connect(cls, target: str) -> bool:
        try:
            r = subprocess.run(
                ["adb", "connect", target],
                capture_output=True, text=True, timeout=10
            )
            if "connected" in r.stdout.lower():
                cls.dev = target
                ok("ADB: " + target)
                return True
            err("ADB connect failed: " + r.stdout.strip())
            return False
        except FileNotFoundError:
            err("'adb' nie znalezione -- zainstaluj Android Platform Tools")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            err("ADB timeout: " + target)
            return False

    @classmethod
    def sh(cls, cmd: str, silent: bool = False) -> str:
        if not cls.dev:
            return ""
        try:
            return subprocess.check_output(
                ["adb", "-s", cls.dev, "shell", cmd],
                stderr=subprocess.STDOUT, text=True, timeout=cls._TO
            ).strip()
        except subprocess.TimeoutExpired:
            if not silent:
                warn("Timeout: " + cmd[:60])
            return ""
        except subprocess.CalledProcessError as e:
            return (e.output or "").strip()
        except Exception as e:
            if not silent:
                err(str(e))
            return ""

    @classmethod
    def root(cls, cmd: str) -> str:
        for prefix in ('su -c "' + cmd + '"', 'rish -c "' + cmd + '"'):
            r = cls.sh(prefix, silent=True)
            if r and "not found" not in r and "permission denied" not in r.lower():
                return r
        return cls.sh(cmd)

    @classmethod
    def pull(cls, remote: str, local: str) -> bool:
        try:
            subprocess.check_call(
                ["adb", "-s", cls.dev, "pull", remote, local],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=60
            )
            return Path(local).exists()
        except Exception:
            return False

    @classmethod
    def push(cls, local: str, remote: str) -> bool:
        try:
            subprocess.check_call(
                ["adb", "-s", cls.dev, "push", local, remote],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=60
            )
            return True
        except Exception:
            return False

    @classmethod
    def prop(cls, key: str) -> str:
        return cls.sh("getprop " + key, silent=True)

    @classmethod
    def pkg_exists(cls, pkg: str) -> bool:
        return pkg in cls.sh("pm list packages " + pkg, silent=True)

    @classmethod
    def pkg_running(cls, pkg: str) -> bool:
        out = cls.sh("pidof " + pkg + " 2>/dev/null", silent=True)
        return bool(out and out.strip().isdigit())


# ================================================================
# Odkrycie pakietu SmartTube
# ================================================================

def detect_smarttube_pkg() -> Optional[str]:
    for pkg in (PKG_STABLE, PKG_BETA, PKG_LEGACY):
        if _ADB.pkg_exists(pkg):
            return pkg
    return None


# ================================================================
# KROK 1 -- Eksport konfiguracji z urzadzenia
# ================================================================

class ConfigExporter:
    """
    Eksportuje SharedPreferences XML SmartTube z urzadzenia.

    Metody (w kolejnosci priorytetu):
      1. su (root) -- bezposredni dostep do /data/data/PKG/shared_prefs/
      2. run-as    -- dziala tylko na debuggable buildach
      3. backup    -- adb backup + rozpakowanie (fallback)
    """

    @classmethod
    def _prep_device_dir(cls) -> bool:
        _ADB.sh("mkdir -p " + DEVICE_TMP, silent=True)
        return True

    @classmethod
    def _list_prefs_files(cls, pkg: str) -> List[str]:
        """Zwraca liste plikow .xml w shared_prefs aplikacji."""
        prefs_dir = "/data/data/" + pkg + "/shared_prefs"
        out = _ADB.root("ls " + prefs_dir + " 2>/dev/null")
        if not out or "No such" in out:
            # Sprobuj przez run-as
            out = _ADB.sh("run-as " + pkg + " ls shared_prefs 2>/dev/null", silent=True)
        if not out:
            return []
        return [f.strip() for f in out.splitlines() if f.strip().endswith(".xml")]

    @classmethod
    def _copy_via_root(cls, pkg: str, filename: str) -> bool:
        """Kopiuj plik prefs na /sdcard/ przez su."""
        src  = "/data/data/" + pkg + "/shared_prefs/" + filename
        dest = DEVICE_TMP + "/" + filename
        out  = _ADB.root("cp " + src + " " + dest + " && echo ok")
        if "ok" in (out or ""):
            # Nadaj prawa do odczytu
            _ADB.root("chmod 644 " + dest + " 2>/dev/null")
            return True
        return False

    @classmethod
    def _copy_via_runas(cls, pkg: str, filename: str) -> bool:
        """Kopiuj plik prefs przez run-as (debuggable build)."""
        src  = "shared_prefs/" + filename
        dest = DEVICE_TMP + "/" + filename
        out  = _ADB.sh(
            "run-as " + pkg + " cat " + src + " > " + dest + " 2>/dev/null && echo ok",
            silent=True
        )
        return "ok" in (out or "")

    @classmethod
    def export(cls, pkg: str, local_dir: Path) -> Dict[str, Path]:
        """
        Glowna metoda eksportu.
        Zwraca slownik {nazwa_pliku: sciezka_lokalna}.
        """
        hdr("KROK 1 -- Eksport konfiguracji SmartTube")
        info("Pakiet: " + pkg)
        local_dir.mkdir(parents=True, exist_ok=True)
        cls._prep_device_dir()

        # Lista plikow prefs
        prefs_files = cls._list_prefs_files(pkg)
        if not prefs_files:
            warn("Nie znaleziono plikow SharedPreferences")
            warn("SmartTube moze nie byc uruchomiony ani skonfigurowany")
            return {}

        info("Znalezione pliki preferences (" + str(len(prefs_files)) + "):")
        for f in prefs_files:
            print("    " + _C + f + _R)

        exported: Dict[str, Path] = {}

        for fname in prefs_files:
            info("Eksportuje: " + fname + "...")

            # Metoda 1: root (su)
            success = cls._copy_via_root(pkg, fname)
            method  = "su (root)"

            # Metoda 2: run-as
            if not success:
                success = cls._copy_via_runas(pkg, fname)
                method  = "run-as"

            if not success:
                warn("  Nie mozna wyeksportowac: " + fname + " (brak root/run-as)")
                continue

            # Sciagnij na lokalny dysk
            remote  = DEVICE_TMP + "/" + fname
            local_p = local_dir / fname

            if _ADB.pull(remote, str(local_p)):
                ok("  " + fname + " [" + method + "] -> " + str(local_p))
                exported[fname] = local_p
            else:
                warn("  Nie mozna pobrac: " + fname)

        if not exported:
            err("Eksport nieudany -- brak plikow")
        else:
            ok("Wyeksportowano " + str(len(exported)) + "/" + str(len(prefs_files)) + " plikow")

        return exported


# ================================================================
# Baza optymalnych ustawien dla BCM72604
# ================================================================

# Format:
#   klucz_preferences: (typ, optymalna_wartosc, opis)
#
# Typy: "string" | "boolean" | "int" | "long" | "float"
#
# Klucze bazuja na kodzie zrodlowym SmartTube (github.com/yuliskov/SmartTube)
# oraz analizie zachowania aplikacji na BCM72604.

BCM72604_OPTIMAL: Dict[str, Tuple[str, str, str]] = {

    # ---- Kodek wideo ------------------------------------------------
    # BCM72604: VP9 HW (VDec32), brak AV1 HW, H264 SW fallback
    # video_codec: 0=Auto, 1=AVC/H264, 2=VP9, 3=AV1
    "video_codec":                  ("int",     "2",     "VP9 -- jedyny HW codec na BCM72604"),
    "av1_enabled":                  ("boolean", "false", "AV1 wylaczony -- brak HW dekodera (100% CPU A15)"),
    "vp9_enabled":                  ("boolean", "true",  "VP9 wlaczony -- VDec32 HW path"),
    "preferred_codec":              ("string",  "vp9",   "Preferowany kodek VP9"),
    "codec_black_list":             ("string",  "av1",   "AV1 na czarnej liscie"),

    # ---- Tryb tunelowy (BCM HDMI tunnel, hardware clock sync) --------
    # KRYTYCZNE: eliminuje A/V drift na BCM7362 HDMI ARC
    "use_tunnel_mode":              ("boolean", "true",  "Tunnel mode -- hardware clock sync"),
    "tunnel_mode_enabled":          ("boolean", "true",  "Tunnel mode enabled"),
    "tunneled_playback":            ("boolean", "true",  "Tunneled playback"),

    # ---- Jakosc wideo -----------------------------------------------
    # Potwierdzony display: 1920x1080@60fps
    "video_resolution":             ("string",  "1080",  "Max 1080p -- potwierdzona rozdzielczosc"),
    "preferred_resolution":         ("int",     "4",     "1080p (index 4 w SmartTube)"),
    "max_video_resolution":         ("string",  "1080",  "Max rozdzielczosc 1080p"),
    "default_quality":              ("string",  "hd1080","Domyslna jakosc HD 1080p"),

    # ---- HDR (BCM72604: HDR10 przez VDec32->Nexus->HDMI InfoFrame) ---
    "hdr_mode":                     ("boolean", "true",  "HDR10 wlaczony -- VDec32 HW path"),
    "hdr_enabled":                  ("boolean", "true",  "HDR enabled"),
    "hdr10_enabled":                ("boolean", "true",  "HDR10 enabled"),

    # ---- Czestotliwosc odswiezania ----------------------------------
    # Auto-rate matching: 24fps film -> display 24Hz mode
    "video_frame_rate_switch":      ("boolean", "true",  "Auto frame rate switching"),
    "auto_frame_rate":              ("boolean", "true",  "Automatyczna czestotliwosc"),
    "frame_rate_switching":         ("boolean", "true",  "Przelaczanie fps"),
    "switch_frame_rate":            ("boolean", "true",  "Przelacz fps do tresci"),

    # ---- Bufor (dla VP9 1080p: 8-12 Mbps) ---------------------------
    # 15-50s bufor zapobiega rebuffering na WiFi
    "player_data_source":           ("int",     "0",     "ExoPlayer (nie MediaPlayer)"),
    "buffer_type":                  ("int",     "2",     "Duzy bufor (extended)"),
    "min_buffer_duration":          ("string",  "15000", "Min bufor 15s"),
    "max_buffer_duration":          ("string",  "50000", "Max bufor 50s"),
    "playback_buffer_ms":           ("string",  "2500",  "Bufor przed startem 2.5s"),
    "back_buffer_ms":               ("string",  "10000", "Bufor cofania 10s"),

    # ---- Odtwarzanie w tle ------------------------------------------
    # Wylaczone -- oszczedza CPU na dual-core A15
    "background_play_mode":         ("int",     "0",     "Brak odtwarzania w tle (0=off)"),
    "background_playback":          ("boolean", "false", "Background playback wylaczony"),

    # ---- Statystyki / overlaye (CPU overhead) ------------------------
    "player_stats":                 ("boolean", "false", "Stats overlay wylaczony"),
    "show_stats":                   ("boolean", "false", "Nie pokazuj statystyk"),
    "debug_view":                   ("boolean", "false", "Debug view wylaczony"),

    # ---- Akceleracja sprzetowa --------------------------------------
    "hardware_acceleration":        ("boolean", "true",  "Hardware acceleration wlaczona"),
    "hw_acceleration":              ("boolean", "true",  "HW acceleration"),
    "use_hardware_decoder":         ("boolean", "true",  "Uzywaj HW dekodera"),

    # ---- Format audio -----------------------------------------------
    # BCM7362 HDMI ARC: audio offload wylaczony (drift fix w Autopilot)
    "audio_format":                 ("int",     "0",     "Domyslny format audio"),
    "audio_delay_ms":               ("int",     "0",     "Brak opoznienia audio (HDMI clock locked)"),

    # ---- Interpolacja klatek ----------------------------------------
    # Wylaczona -- nie dziala poprawnie na VP9 VDec32
    "frame_interpolation":          ("boolean", "false", "Interpolacja klatek wylaczona"),
    "smooth_playback":              ("boolean", "false", "Smooth playback off (VP9 HW path)"),

    # ---- Szybkosc odtwarzania ---------------------------------------
    "speed_buttons":                ("boolean", "true",  "Przyciski szybkosci"),
    "default_speed":                ("float",   "1.0",   "Domyslna szybkosc 1.0x"),

    # ---- UI / Launcher ----------------------------------------------
    # Rekomendacje wylaczone -- CPU polling na A15
    "suggestions_enabled":          ("boolean", "false", "Sugestie wylaczone (CPU)"),
    "feed_enabled":                 ("boolean", "false", "Feed wylaczony"),
    "autoplay_enabled":             ("boolean", "true",  "Autoplay wlaczony"),

    # ---- Jakosc domyslna dla kazdego wideo --------------------------
    "force_default_quality":        ("boolean", "false", "Nie wymuszaj domyslnej jakosci"),
    "remember_quality":             ("boolean", "true",  "Pamietaj wybrana jakosc"),

    # ---- ABR (Adaptive Bitrate) ------------------------------------
    # Wyzszy prog -- mniej przelaczen przy buforze WiFi
    "abr_enabled":                  ("boolean", "true",  "ABR wlaczony"),

    # ---- Napisy -----------------------------------------------------
    "subtitles_font_size":          ("int",     "16",    "Rozmiar napisow (TV 10-foot)"),
    "subtitles_enabled":            ("boolean", "false", "Napisy domyslnie wylaczone"),

    # ---- Live / IPTV ------------------------------------------------
    "live_stream_quality":          ("string",  "1080",  "Live stream 1080p"),
    "live_hide_end_screen":         ("boolean", "true",  "Ukryj ekran koncowy w live"),
}

# ================================================================
# Mapowanie indeksow jakosci SmartTube
# (rozne wersje uzywaja roznych kluczy/wartosci)
# ================================================================

RESOLUTION_ALIASES: Dict[str, List[str]] = {
    "1080": ["hd1080", "1080p", "1080", "FHD", "4"],
    "720":  ["hd720",  "720p",  "720",  "HD",  "3"],
    "4k":   ["4k", "2160", "2160p", "UHD", "6"],
}

CODEC_ALIASES: Dict[str, List[str]] = {
    "vp9": ["vp9", "VP9", "2", "webm"],
    "av1": ["av1", "AV1", "3"],
    "avc": ["avc", "AVC", "h264", "H264", "1"],
}


# ================================================================
# KROK 2 -- Optymalizacja XML
# ================================================================

class ConfigOptimizer:
    """
    Parsuje i modyfikuje SharedPreferences XML SmartTube.
    Stosuje optymalne ustawienia dla BCM72604.
    """

    def __init__(self, xml_path: Path, dry_run: bool = False):
        self.path    = xml_path
        self.dry_run = dry_run
        self.changes: List[Tuple[str, str, str, str]] = []  # (klucz, stara, nowa, opis)
        self.tree: Optional[ET.ElementTree] = None
        self.root_el: Optional[ET.Element]  = None

    # ---- Parsowanie -------------------------------------------------

    def load(self) -> bool:
        try:
            self.tree    = ET.parse(str(self.path))
            self.root_el = self.tree.getroot()
            if self.root_el.tag != "map":
                warn("  Nieoczekiwany root tag: " + self.root_el.tag)
            return True
        except ET.ParseError as e:
            err("  Blad parsowania XML: " + str(e))
            return False
        except Exception as e:
            err("  Blad odczytu: " + str(e))
            return False

    # ---- Odczyt wartosci -----------------------------------------------

    def _get_value(self, key: str) -> Optional[Tuple[str, str]]:
        """Zwraca (typ_elementu, wartosc) lub None jesli brak klucza."""
        if self.root_el is None:
            return None
        for el in self.root_el:
            if el.get("name") == key:
                tag = el.tag
                if tag == "string":
                    return ("string", el.text or "")
                elif tag in ("boolean", "int", "long", "float"):
                    return (tag, el.get("value", ""))
                elif tag == "set":
                    items = [s.text or "" for s in el.findall("string")]
                    return ("set", ",".join(items))
        return None

    # ---- Ustawienie wartosci ------------------------------------------

    def _set_value(self, key: str, typ: str, value: str) -> bool:
        """
        Ustaw wartosc elementu. Tworzy element jesli nie istnieje.
        Zwraca True jesli cos sie zmienilo.
        """
        if self.root_el is None:
            return False

        # Szukaj istniejacego elementu
        for el in self.root_el:
            if el.get("name") == key:
                old_val = el.text if el.tag == "string" else el.get("value", "")
                old_typ = el.tag
                new_val = value

                if old_val == new_val and old_typ == typ:
                    return False  # brak zmiany

                # Zastosuj zmiane
                if typ == "string":
                    el.tag  = "string"
                    el.text = value
                    if "value" in el.attrib:
                        del el.attrib["value"]
                else:
                    el.tag = typ
                    el.set("value", value)
                    el.text = None

                self.changes.append((key, str(old_val), value, typ))
                return True

        # Nie znaleziono -- stworz nowy element
        if typ == "string":
            new_el = ET.SubElement(self.root_el, "string", {"name": key})
            new_el.text = value
        else:
            new_el = ET.SubElement(self.root_el, typ, {"name": key, "value": value})

        self.changes.append((key, "<brak>", value, typ))
        return True

    # ---- Zastosowanie optymalnych ustawien ----------------------------

    def apply_bcm72604_optimizations(self) -> int:
        """
        Stosuje optymalne ustawienia BCM72604.
        Zwraca liczbe zmienionych kluczy.
        """
        changed = 0

        for key, (typ, value, desc) in BCM72604_OPTIMAL.items():
            if self._set_value(key, typ, value):
                changed += 1
                fix("  [ZMIANA] " + key + " = " + value + _D + "  (" + desc + ")" + _R)
            # Nie loguj brakow zmian dla czystosci wyjscia

        return changed

    def apply_resolution_aliases(self) -> int:
        """
        Dodatkowa normalizacja: wszystkie aliasy rozdzielczosci 1080p.
        """
        if self.root_el is None:
            return 0
        changed = 0

        for el in self.root_el:
            name = el.get("name", "")
            val  = el.text if el.tag == "string" else el.get("value", "")

            # Sprawdz czy to pole zwiazane z rozdzielczoscia
            if any(kw in name.lower() for kw in
                   ("resolution", "quality", "format", "bitrate_key")):
                # Czy wartosc to alias 4K lub wyzszy?
                if val and val in ["2160", "4k", "4K", "UHD", "2160p", "5", "6", "7"]:
                    old = val
                    if el.tag == "string":
                        el.text = "1080"
                    else:
                        el.set("value", "4")
                    self.changes.append((name, old, "1080/4", "resolution alias"))
                    fix("  [RES]    " + name + " = 4K->1080p (BCM72604 max display)")
                    changed += 1

            # Sprawdz czy to AV1 gdziekolwiek
            if "av1" in name.lower() or (val and "av1" in str(val).lower()):
                if val not in ("false", "0", ""):
                    old = val
                    if el.tag == "boolean":
                        el.set("value", "false")
                    elif el.tag in ("int", "string"):
                        if el.tag == "string":
                            el.text = "false"
                        else:
                            el.set("value", "0")
                    self.changes.append((name, old, "disabled", "AV1 blocked"))
                    fix("  [AV1]    " + name + " -> disabled (no HW decoder)")
                    changed += 1

        return changed

    # ---- Zapis -------------------------------------------------------

    def save(self, output_path: Optional[Path] = None) -> bool:
        """Zapisz zmodyfikowany XML."""
        if self.dry_run:
            info("  [DRY RUN] Plik nie zostal zapisany")
            return True

        target = output_path or self.path
        try:
            # Ladne formatowanie
            _indent_xml(self.root_el)
            self.tree.write(
                str(target),
                encoding="utf-8",
                xml_declaration=True
            )
            ok("  Zapisano: " + str(target))
            return True
        except Exception as e:
            err("  Blad zapisu XML: " + str(e))
            return False

    # ---- Raport zmian ------------------------------------------------

    def print_summary(self) -> None:
        if not self.changes:
            ok("  Brak zmian -- plik juz optymalny")
            return

        print("\n  " + _BO + "Zmiany w " + self.path.name + " (" + str(len(self.changes)) + "):" + _R)
        print("  " + _D + "-" * 58 + _R)
        print("  " + _B + "Klucz" + " " * 30 + "Przed      -> Po" + _R)
        print("  " + _D + "-" * 58 + _R)

        for key, old, new, desc in self.changes:
            key_s = (key[:33] + "..") if len(key) > 35 else key.ljust(35)
            old_s = (str(old)[:8] + "..") if len(str(old)) > 10 else str(old).ljust(10)
            new_s = str(new)[:10]
            print("  " + _C + key_s + _R + " "
                  + _D + old_s + _R + " -> "
                  + _G + new_s + _R)


# ================================================================
# KROK 3 -- Import zmodyfikowanej konfiguracji
# ================================================================

class ConfigImporter:
    """
    Importuje zmodyfikowany XML z powrotem do SmartTube.

    Kroki:
      1. Zatrzymaj SmartTube (am force-stop)
      2. Push pliku na /sdcard/
      3. Skopiuj do /data/data/PKG/shared_prefs/ przez su
      4. Napraw uprawnienia
      5. Uruchom SmartTube
      6. Weryfikacja
    """

    @classmethod
    def _stop_app(cls, pkg: str) -> None:
        info("Zatrzymywanie SmartTube...")
        _ADB.sh("am force-stop " + pkg, silent=True)
        time.sleep(1.5)
        if not _ADB.pkg_running(pkg):
            ok("  SmartTube zatrzymany")
        else:
            warn("  SmartTube moze nadal dzialac")

    @classmethod
    def _start_app(cls, pkg: str) -> bool:
        info("Uruchamianie SmartTube...")
        _ADB.sh(
            "monkey -p " + pkg + " -c android.intent.category.LAUNCHER 1 2>/dev/null",
            silent=True
        )
        time.sleep(3)
        if _ADB.pkg_running(pkg):
            ok("  SmartTube uruchomiony")
            return True
        warn("  Nie mozna uruchomic automatycznie -- uruchom recznie")
        return False

    @classmethod
    def _install_prefs(cls, pkg: str, local_file: Path, fname: str) -> bool:
        """Skopiuj plik prefs do app data directory."""
        remote_tmp  = DEVICE_TMP + "/" + fname
        prefs_dir   = "/data/data/" + pkg + "/shared_prefs"
        remote_dest = prefs_dir + "/" + fname

        # Push na /sdcard/
        if not _ADB.push(str(local_file), remote_tmp):
            err("  Nie mozna wyslac pliku na urzadzenie")
            return False
        ok("  Wyslano: " + remote_tmp)

        # Kopiuj do app data przez su
        cp_out = _ADB.root("cp " + remote_tmp + " " + remote_dest + " && echo ok")
        if "ok" not in (cp_out or ""):
            err("  Nie mozna skopiowac do " + prefs_dir + " (brak root?)")
            return False
        ok("  Skopiowano do: " + remote_dest)

        # Napraw uprawnienia (owner: aplikacja)
        uid_out = _ADB.root(
            "stat -c %u /data/data/" + pkg + " 2>/dev/null || "
            "ls -nd /data/data/" + pkg + " 2>/dev/null | awk '{print $3}'"
        )
        uid = uid_out.strip().split()[0] if uid_out.strip() else ""
        if uid and uid.isdigit():
            _ADB.root("chown " + uid + ":" + uid + " " + remote_dest + " 2>/dev/null")
        _ADB.root("chmod 660 " + remote_dest + " 2>/dev/null")
        ok("  Uprawnienia naprawione")

        return True

    @classmethod
    def import_configs(cls, pkg: str,
                       files: Dict[str, Path],
                       dry_run: bool = False) -> bool:
        """
        Glowna metoda importu.
        files: {nazwa_pliku: sciezka_lokalna_zmodyfikowanego}
        """
        hdr("KROK 3 -- Import konfiguracji do SmartTube")

        if dry_run:
            info("[DRY RUN] Import pominieto")
            return True

        if not files:
            err("Brak plikow do importu")
            return False

        cls._stop_app(pkg)

        success_count = 0
        for fname, local_path in files.items():
            info("Importuje: " + fname + "...")
            if cls._install_prefs(pkg, local_path, fname):
                success_count += 1

        # Wyczysc /sdcard/ temp
        _ADB.sh("rm -rf " + DEVICE_TMP, silent=True)
        info("Wyczyszczono katalog tymczasowy na urzadzeniu")

        if success_count > 0:
            ok("Zaimportowano " + str(success_count) + "/" + str(len(files)) + " plikow")
            cls._start_app(pkg)
            return True
        else:
            err("Import nieudany -- uruchom SmartTube recznie")
            return False


# ================================================================
# Pomocnicze -- ladne formatowanie XML
# ================================================================

def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    """Dodaje wciecia do XML dla czytelnosci."""
    indent = "\n" + "    " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


# ================================================================
# KROK 2b -- Raport przed/po
# ================================================================

def print_xml_summary(xml_path: Path) -> None:
    """Wyswietl kluczowe ustawienia z pliku XML."""
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
    except Exception:
        return

    INTERESTING_KEYS = [
        "video_codec", "use_tunnel_mode", "hdr_mode",
        "video_resolution", "preferred_resolution", "max_video_resolution",
        "video_frame_rate_switch", "auto_frame_rate",
        "background_play_mode", "background_playback",
        "hardware_acceleration", "av1_enabled", "vp9_enabled",
        "buffer_type", "min_buffer_duration", "max_buffer_duration",
        "frame_interpolation", "player_stats",
    ]

    found = {}
    for el in root:
        name = el.get("name", "")
        if name in INTERESTING_KEYS:
            val = el.text if el.tag == "string" else el.get("value", "?")
            found[name] = (el.tag, val)

    if not found:
        info("  Nie znaleziono interesujacych kluczy w " + xml_path.name)
        return

    print("  " + _BO + "Stan kluczowych ustawien (" + xml_path.name + "):" + _R)
    print("  " + _D + "-" * 52 + _R)
    for key in INTERESTING_KEYS:
        if key in found:
            typ, val = found[key]

            # Koloruj: zielony = ok, czerwony = nieoptymalne
            optimal_val = BCM72604_OPTIMAL.get(key, (None, None, None))[1]
            if optimal_val and str(val) == str(optimal_val):
                col = _G
            elif optimal_val:
                col = _E
            else:
                col = _B

            key_s = key[:35].ljust(35)
            print("  " + _C + key_s + _R + " = " + col + str(val) + _R
                  + _D + "  [" + typ + "]" + _R)


# ================================================================
# Glowny menedzer
# ================================================================

class SmartTubeConfigManager:
    """
    Orchestruje caly proces:
      1. Eksport XML z urzadzenia
      2. Backup oryginalu
      3. Optymalizacja XML
      4. Raport zmian
      5. Import do urzadzenia
    """

    @classmethod
    def run_full(cls,
                 device:      Optional[str] = None,
                 dry_run:     bool          = False,
                 export_only: bool          = False,
                 restore_dir: Optional[str] = None) -> bool:

        hdr("SmartTube Config Manager -- BCM72604 Optimizer")
        print("  Tryb: " + ("DRY RUN" if dry_run else
                             "RESTORE" if restore_dir else
                             "EXPORT ONLY" if export_only else
                             "PELNY (eksport + optymalizacja + import)"))
        print()

        # Polaczenie ADB
        if device:
            if not _ADB.connect(device):
                return False
        elif not _ADB.dev:
            # Wykryj automatycznie
            try:
                out = subprocess.check_output(
                    ["adb", "devices"], text=True, timeout=5
                )
                for line in out.splitlines():
                    if "\tdevice" in line:
                        _ADB.dev = line.split("\t")[0].strip()
                        ok("ADB auto-wykryty: " + _ADB.dev)
                        break
            except Exception:
                pass
            if not _ADB.dev:
                err("Brak polaczenia ADB -- podaj --device IP:PORT")
                return False

        # Wykryj pakiet SmartTube
        pkg = detect_smarttube_pkg()
        if not pkg:
            err("SmartTube nie jest zainstalowany")
            err("Sprobuj: Autopilot_v157.py opcja 16 (APK install)")
            return False
        ok("Wykryto pakiet: " + pkg)

        # Katalog roboczy z timestampem
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_dir  = LOCAL_DIR / ts
        work_dir.mkdir(parents=True, exist_ok=True)
        info("Katalog roboczy: " + str(work_dir))

        # ---- TRYB RESTORE -----------------------------------------------
        if restore_dir:
            return cls._do_restore(pkg, Path(restore_dir), dry_run)

        # ---- EKSPORT ----------------------------------------------------
        sub("Eksport oryginalnych plikow")
        exported = ConfigExporter.export(pkg, work_dir / "original")

        if not exported:
            err("Eksport nieudany -- nie mozna kontynuowac")
            return False

        # Pokaz stan przed
        print()
        sub("Stan konfiguracji PRZED optymalizacja")
        for fname, fpath in exported.items():
            print_xml_summary(fpath)

        if export_only:
            ok("Eksport zakonczone (--export-only)")
            info("Pliki: " + str(work_dir / "original"))
            return True

        # ---- OPTYMALIZACJA ----------------------------------------------
        sub("Optymalizacja dla BCM72604")
        optimized_dir = work_dir / "optimized"
        optimized_dir.mkdir(exist_ok=True)

        optimized_files: Dict[str, Path] = {}
        total_changes = 0

        for fname, orig_path in exported.items():
            info("Optymalizuje: " + fname + "...")

            # Kopiuj oryginalu do katalogu optimized
            opt_path = optimized_dir / fname
            shutil.copy2(str(orig_path), str(opt_path))

            # Zoptymalizuj
            optimizer = ConfigOptimizer(opt_path, dry_run=dry_run)
            if not optimizer.load():
                warn("  Pominieto " + fname + " (blad parsowania)")
                continue

            n1 = optimizer.apply_bcm72604_optimizations()
            n2 = optimizer.apply_resolution_aliases()
            changed = n1 + n2

            optimizer.print_summary()

            if changed > 0:
                if optimizer.save():
                    optimized_files[fname] = opt_path
                    total_changes += changed
                    ok("  " + fname + ": " + str(changed) + " zmian")
            else:
                ok("  " + fname + ": juz optymalny")
                optimized_files[fname] = opt_path

        print()
        ok("Laczna liczba zmian: " + str(total_changes))

        # Pokaz stan po
        sub("Stan konfiguracji PO optymalizacji")
        for fname, fpath in optimized_files.items():
            print_xml_summary(fpath)

        if not optimized_files:
            warn("Brak plikow do importu")
            return True

        # ---- IMPORT -----------------------------------------------------
        if not dry_run:
            proceed = True
            try:
                ans = input(
                    "\n  " + _Y + "Importowac zoptymalizowana konfiguracje? [T/n] > " + _R
                ).strip().lower()
                proceed = (ans in ("", "t", "y", "tak", "yes"))
            except (EOFError, KeyboardInterrupt):
                proceed = False

            if proceed:
                success = ConfigImporter.import_configs(pkg, optimized_files, dry_run)
                if success:
                    hdr("Gotowe!")
                    ok("Konfiguracja SmartTube zoptymalizowana dla BCM72604")
                    ok("VP9 HW + Tunnel Mode + HDR10 + 1080p + AV1 wylaczony")
                    info("Backup oryginalu: " + str(work_dir / "original"))
                    info("Zoptymalizowane: " + str(optimized_dir))
                    info("Rollback: python3 smarttube_config.py --restore " + str(work_dir / "original"))
                    return True
                else:
                    err("Import nieudany")
                    info("Mozesz ponowic: --restore " + str(optimized_dir))
                    return False
            else:
                info("Import anulowany przez uzytkownika")
                info("Zoptymalizowane pliki: " + str(optimized_dir))
                info("Reczny import: python3 smarttube_config.py --restore " + str(optimized_dir))
                return True
        else:
            info("[DRY RUN] Import pominieto")
            return True

    @classmethod
    def _do_restore(cls, pkg: str, restore_dir: Path, dry_run: bool) -> bool:
        """Przywroc konfiguracje z katalogu backupu."""
        hdr("RESTORE -- Przywracanie konfiguracji")

        if not restore_dir.exists():
            err("Katalog restore nie istnieje: " + str(restore_dir))
            return False

        xml_files = list(restore_dir.glob("*.xml"))
        if not xml_files:
            err("Brak plikow XML w: " + str(restore_dir))
            return False

        restore_files: Dict[str, Path] = {f.name: f for f in xml_files}
        info("Pliki do przywrocenia (" + str(len(restore_files)) + "):")
        for fname in restore_files:
            print("    " + _C + fname + _R)

        return ConfigImporter.import_configs(pkg, restore_files, dry_run)


# ================================================================
# CLI
# ================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SmartTube Config Manager -- BCM72604 Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "PRZYKLADY:\n"
            "  python3 smarttube_config.py --device 192.168.1.3:5555\n"
            "  python3 smarttube_config.py --export-only\n"
            "  python3 smarttube_config.py --dry-run\n"
            "  python3 smarttube_config.py --restore ~/.playbox_cache/smarttube_configs/20240101_120000/original\n"
        )
    )
    parser.add_argument(
        "--device",  default=None,
        help="ADB device IP:PORT (np. 192.168.1.3:5555)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Pokaz zmiany bez zapisu i importu"
    )
    parser.add_argument(
        "--export-only", action="store_true",
        help="Tylko eksportuj XML bez optymalizacji"
    )
    parser.add_argument(
        "--restore", default=None, metavar="KATALOG",
        help="Przywroc konfiguracje z katalogu backup"
    )
    parser.add_argument(
        "--show", default=None, metavar="PLIK.XML",
        help="Pokaz zawartosc pliku XML (bez polaczenia ADB)"
    )
    args = parser.parse_args()

    # Tryb pokazywania lokalnego pliku
    if args.show:
        p = Path(args.show)
        if not p.exists():
            err("Plik nie istnieje: " + args.show)
            sys.exit(1)
        hdr("Zawartosc: " + p.name)
        print_xml_summary(p)
        sys.exit(0)

    success = SmartTubeConfigManager.run_full(
        device      = args.device,
        dry_run     = args.dry_run,
        export_only = args.export_only,
        restore_dir = args.restore,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()