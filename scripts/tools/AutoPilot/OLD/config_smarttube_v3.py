#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smarttube_config.py
================================================================
  PlayBox Titanium -- SmartTube Config Manager
  Eksport / Optymalizacja / Import konfiguracji SmartTube

  Uzywa natywnej sciezki backupu SmartTube:
    /storage/emulated/0/data/   (dostepne bez root przez ADB)

  Uzycie:
    python3 smarttube_config.py --device 192.168.1.3:5555
    python3 smarttube_config.py --dry-run
    python3 smarttube_config.py --export-only
    python3 smarttube_config.py --restore ./backup/20240101/
================================================================
"""
from __future__ import annotations

import argparse
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
_R  = "\033[0m";  _G  = "\033[92m";  _Y  = "\033[93m"
_B  = "\033[94m"; _E  = "\033[91m";  _H  = "\033[95m"
_C  = "\033[96m"; _D  = "\033[2m";   _BO = "\033[1m"

def ok(m):   print(_G  + "  [OK] " + str(m) + _R)
def warn(m): print(_Y  + "  [!!] " + str(m) + _R)
def err(m):  print(_E  + "  [XX] " + str(m) + _R)
def info(m): print(_B  + "  [ ] " + str(m) + _R)
def fix(m):  print(_Y  + "  [>>] " + str(m) + _R)
def hdr(m):  print("\n" + _H + _BO + "=" * 62 + "\n  " + str(m) + "\n" + "=" * 62 + _R)
def sub(m):  print("\n" + _C + "  -- " + str(m) + " --" + _R)
def step(n, t, m): print(_BO + _B + "\n  [" + str(n) + "/" + str(t) + "] " + m + _R)


# ================================================================
# Stale
# ================================================================

PKG_STABLE = "org.smarttube.stable"
PKG_BETA   = "org.smarttube.beta"
PKG_LEGACY = "com.liskovsoft.smarttubetv"

# Natywna sciezka backupu SmartTube (bez root)
DEVICE_BACKUP_BASE = "/storage/emulated/0/data"

# Katalog lokalny
LOCAL_DIR = Path.home() / ".playbox_cache" / "smarttube_configs"

# Timeout uruchomienia SmartTube (sekundy)
LAUNCH_TIMEOUT = 20


# ================================================================
# ADB wrapper
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
    def autodetect(cls) -> bool:
        try:
            out = subprocess.check_output(
                ["adb", "devices"], text=True, timeout=5
            )
            for line in out.splitlines():
                if "\tdevice" in line:
                    cls.dev = line.split("\t")[0].strip()
                    ok("ADB auto-wykryty: " + cls.dev)
                    return True
        except Exception:
            pass
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
    def keyevent(cls, code: int) -> None:
        """Wysyla event klawisza przez ADB."""
        cls.sh("input keyevent " + str(code), silent=True)

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
    def pull_dir(cls, remote_dir: str, local_dir: str) -> bool:
        """Sciagnij caly katalog."""
        try:
            subprocess.check_call(
                ["adb", "-s", cls.dev, "pull", remote_dir + "/.", local_dir],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=120
            )
            return True
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
    def push_dir(cls, local_dir: str, remote_dir: str) -> bool:
        """Wyslij caly katalog."""
        try:
            subprocess.check_call(
                ["adb", "-s", cls.dev, "push", local_dir + "/.", remote_dir],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=120
            )
            return True
        except Exception:
            return False

    @classmethod
    def pkg_exists(cls, pkg: str) -> bool:
        return pkg in cls.sh("pm list packages " + pkg, silent=True)

    @classmethod
    def pkg_running(cls, pkg: str) -> bool:
        out = cls.sh("pidof " + pkg + " 2>/dev/null", silent=True)
        return bool(out and out.strip().split()[0].isdigit())

    @classmethod
    def ls(cls, path: str) -> List[str]:
        out = cls.sh("ls " + path + " 2>/dev/null", silent=True)
        if not out or "No such" in out or "Permission" in out:
            return []
        return [f.strip() for f in out.splitlines() if f.strip()]

    @classmethod
    def exists(cls, path: str) -> bool:
        out = cls.sh("test -e " + path + " && echo yes", silent=True)
        return "yes" in out

    @classmethod
    def mkdir(cls, path: str) -> None:
        cls.sh("mkdir -p " + path, silent=True)


# ================================================================
# Wykrycie pakietu SmartTube
# ================================================================

def detect_pkg() -> Optional[str]:
    for pkg in (PKG_STABLE, PKG_BETA, PKG_LEGACY):
        if _ADB.pkg_exists(pkg):
            return pkg
    return None


# ================================================================
# Natywna sciezka backupu SmartTube
# ================================================================

class SmartTubeBackupPath:
    """
    SmartTube zapisuje backup w:
      /storage/emulated/0/data/<pkg>/        -- nowe wersje
      /storage/emulated/0/data/              -- starsze wersje (bezposrednio)
    """

    @classmethod
    def find_backup_dir(cls, pkg: str) -> Optional[str]:
        candidates = [
            DEVICE_BACKUP_BASE + "/" + pkg,
            DEVICE_BACKUP_BASE + "/" + pkg.replace(".", "_"),
            DEVICE_BACKUP_BASE,
            "/sdcard/data/" + pkg,
            "/sdcard/data",
            "/sdcard/SmartTube",
            "/storage/emulated/0/SmartTube",
            "/storage/emulated/0/Android/data/" + pkg + "/files",
        ]

        for path in candidates:
            files = _ADB.ls(path)
            xml_or_json = [f for f in files
                           if f.endswith(".xml") or f.endswith(".json")
                           or f.endswith(".bak")]
            if xml_or_json:
                ok("Znaleziono pliki konfiguracji w: " + path)
                info("Pliki: " + ", ".join(xml_or_json[:6]))
                return path

        return None

    @classmethod
    def list_config_files(cls, backup_dir: str) -> List[str]:
        files = _ADB.ls(backup_dir)
        return [f for f in files
                if f.endswith(".xml") or f.endswith(".json") or f.endswith(".bak")]


# ================================================================
# Trigger natywnego backupu/importu SmartTube z użyciem UI (Logcat Analiza)
# ================================================================

class SmartTubeBackupTrigger:
    """
    Uruchamia i wymusza backup/import konfiguracji SmartTube.
    Zamiast losowych wywołań, używa precyzyjnej analizy UI na podstawie logów:
    - Activity: com.liskovsoft.smartyoutubetv2.tv.ui.dialogs.AppDialogActivity
    - Klawisze: KEYCODE_DPAD_DOWN (20), KEYCODE_DPAD_CENTER (23)
    """

    @classmethod
    def trigger_ui_action(cls, pkg: str, action_name: str) -> bool:
        """
        Symuluje otworzenie menu dialogowego konfiguracji i kliknięcie potwierdzenia.
        Wymaga, by użytkownik miał chociaż raz wcześniej wygenerowany config
        lub znajdował się na ekranie Ustawień kopii zapasowej.
        """
        info("Symulacja akcji UI: " + action_name + " poprzez ADB...")
        
        # Otwarcie aktywnosci dialogowej (wymagany flag NEW_TASK 0x10000000 z logow)
        cmp = pkg + "/com.liskovsoft.smartyoutubetv2.tv.ui.dialogs.AppDialogActivity"
        _ADB.sh("am start -n " + cmp + " -f 0x10000000", silent=True)
        time.sleep(2.0) # Czas na wyrenderowanie okna
        
        # Sekwencja potwierdzona w logach: IR klawisz 108 -> ADB KEYCODE_DPAD_DOWN (20)
        _ADB.keyevent(20)
        time.sleep(0.5)
        
        # Sekwencja potwierdzona w logach: IR klawisz 353 -> ADB KEYCODE_DPAD_CENTER (23)
        _ADB.keyevent(23)
        time.sleep(1.0)
        
        return True

    @classmethod
    def launch_and_wait(cls, pkg: str, backup_dir_base: str,
                        timeout_s: int = LAUNCH_TIMEOUT) -> Optional[str]:
        """
        Uruchom SmartTube i wymuś eksport używając symulacji UI.
        """
        _ADB.sh("am force-stop " + pkg, silent=True)
        time.sleep(1)

        # Uruchom podstawowo aplikacje
        _ADB.sh("monkey -p " + pkg + " -c android.intent.category.LAUNCHER 1 2>/dev/null", silent=True)
        time.sleep(3)

        info("Próba automatycznego wyzwolenia dialogu eksportu...")
        cls.trigger_ui_action(pkg, "Eksport")

        # Czekaj az pojawi sie katalog z plikami
        for i in range(timeout_s):
            time.sleep(1)
            print("  " + str(i + 1) + "/" + str(timeout_s) + "s...", end="\r")

            backup_dir = SmartTubeBackupPath.find_backup_dir(pkg)
            if backup_dir:
                print()
                ok("Backup wygenerowany po " + str(i + 1) + "s: " + backup_dir)
                time.sleep(2)  # Daj czas na dokonczenie zapisu
                return backup_dir

        print()
        return None


# ================================================================
# KROK 1 -- Eksport
# ================================================================

class ConfigExporter:

    @classmethod
    def export(cls, pkg: str, local_dir: Path) -> Tuple[Dict[str, Path], str]:
        hdr("KROK 1 -- Eksport konfiguracji SmartTube")
        local_dir.mkdir(parents=True, exist_ok=True)

        backup_dir = SmartTubeBackupPath.find_backup_dir(pkg)

        if not backup_dir:
            warn("Nie znaleziono istniejacego backupu")
            info("Próbuję wywołać eksport przez automatyzację UI z logów...")
            backup_dir = SmartTubeBackupTrigger.launch_and_wait(pkg, DEVICE_BACKUP_BASE)

            if not backup_dir:
                warn("Automatyczny eksport zawiódł.")
                info("Sprawdzam znane lokalizacje backupu...")
                backup_dir = SmartTubeBackupPath.find_backup_dir(pkg)

        if not backup_dir:
            err("Nie mozna znalezc plikow konfiguracji SmartTube")
            _print_manual_export_hint(pkg)
            return {}, ""

        # Zatrzymaj SmartTube przed kopiowaniem
        _ADB.sh("am force-stop " + pkg, silent=True)
        time.sleep(1)

        config_files = SmartTubeBackupPath.list_config_files(backup_dir)
        if not config_files:
            err("Brak plikow konfiguracyjnych w: " + backup_dir)
            return {}, backup_dir

        info("Pliki do eksportu (" + str(len(config_files)) + "):")
        for f in config_files:
            size = _ADB.sh("stat -c %s " + backup_dir + "/" + f + " 2>/dev/null", silent=True)
            size_s = (" [" + size + " B]") if size and size.isdigit() else ""
            print("    " + _C + f + _R + _D + size_s + _R)

        exported: Dict[str, Path] = {}
        dir_pull_ok = _ADB.pull_dir(backup_dir, str(local_dir))
        
        if dir_pull_ok:
            for f in config_files:
                local_p = local_dir / f
                if local_p.exists():
                    ok("  " + f + " [" + str(local_p.stat().st_size) + " B]")
                    exported[f] = local_p
        else:
            for f in config_files:
                remote = backup_dir + "/" + f
                local_p = local_dir / f
                if _ADB.pull(remote, str(local_p)):
                    ok("  " + f)
                    exported[f] = local_p
                else:
                    warn("  Pull nieudany: " + f)

        if not exported:
            err("Eksport nieudany")
        else:
            ok("Wyeksportowano " + str(len(exported)) + " plikow do: " + str(local_dir))

        return exported, backup_dir


def _print_manual_export_hint(pkg: str) -> None:
    print()
    warn("Wskazowki recznego eksportu:")
    print("  " + _Y + "  1. Uruchom SmartTube na urzadzeniu" + _R)
    print("  " + _Y + "  2. Wejdz w: Ustawienia -> Kopia zapasowa i przywracanie" + _R)
    print("  " + _Y + "  3. Wybierz 'Eksportuj ustawienia' lub zaakceptuj monit z aktualizacją" + _R)
    print("  " + _Y + "  4. SmartTube zapisze plik w /storage/emulated/0/data/" + _R)
    print("  " + _Y + "  5. Uruchom ponownie: python3 smarttube_config.py" + _R)


# ================================================================
# Baza optymalnych ustawien dla BCM72604
# ================================================================

BCM72604_OPTIMAL: Dict[str, Tuple[str, str, str]] = {
    "video_codec":               ("int",     "2",     "VP9 -- jedyny HW codec BCM72604"),
    "av1_enabled":               ("boolean", "false", "AV1 off -- brak HW, 100% CPU A15"),
    "vp9_enabled":               ("boolean", "true",  "VP9 on -- VDec32 HW path"),
    "preferred_codec":           ("string",  "vp9",   "Preferowany VP9"),
    "codec_black_list":          ("string",  "av1",   "AV1 na czarnej liscie"),
    "use_tunnel_mode":           ("boolean", "true",  "Tunnel -- hardware clock sync BCM"),
    "tunnel_mode_enabled":       ("boolean", "true",  "Tunnel mode enabled"),
    "tunneled_playback":         ("boolean", "true",  "Tunneled playback"),
    "video_resolution":          ("string",  "1080",  "Max 1080p -- display BCM72604"),
    "preferred_resolution":      ("int",     "4",     "1080p index"),
    "max_video_resolution":      ("string",  "1080",  "Max 1080p"),
    "default_quality":           ("string",  "hd1080","Domyslnie HD 1080p"),
    "hdr_mode":                  ("boolean", "true",  "HDR10 -- VDec32->Nexus->HDMI"),
    "hdr_enabled":               ("boolean", "true",  "HDR enabled"),
    "hdr10_enabled":             ("boolean", "true",  "HDR10 enabled"),
    "video_frame_rate_switch":   ("boolean", "true",  "Auto fps switch"),
    "auto_frame_rate":           ("boolean", "true",  "Automatyczna czestotliwosc"),
    "frame_rate_switching":      ("boolean", "true",  "Przelaczanie fps"),
    "switch_frame_rate":         ("boolean", "true",  "Przelacz fps do tresci"),
    "player_data_source":        ("int",     "0",     "ExoPlayer"),
    "buffer_type":               ("int",     "2",     "Duzy bufor"),
    "min_buffer_duration":       ("string",  "15000", "Min bufor 15s"),
    "max_buffer_duration":       ("string",  "50000", "Max bufor 50s"),
    "playback_buffer_ms":        ("string",  "2500",  "Bufor startu 2.5s"),
    "back_buffer_ms":            ("string",  "10000", "Bufor cofania 10s"),
    "hardware_acceleration":     ("boolean", "true",  "HW acceleration"),
    "hw_acceleration":           ("boolean", "true",  "HW acceleration"),
    "use_hardware_decoder":      ("boolean", "true",  "HW dekoder"),
    "background_play_mode":      ("int",     "0",     "Brak odtwarzania w tle"),
    "background_playback":       ("boolean", "false", "Background off"),
    "player_stats":              ("boolean", "false", "Stats overlay off"),
    "show_stats":                ("boolean", "false", "Statystyki off"),
    "debug_view":                ("boolean", "false", "Debug view off"),
    "audio_delay_ms":            ("int",     "0",     "Brak opoznienia audio"),
    "frame_interpolation":       ("boolean", "false", "Interpolacja off (VP9 HW)"),
    "smooth_playback":           ("boolean", "false", "Smooth off"),
    "speed_buttons":             ("boolean", "true",  "Przyciski szybkosci"),
    "default_speed":             ("float",   "1.0",   "Szybkosc 1.0x"),
    "suggestions_enabled":       ("boolean", "false", "Sugestie off"),
    "feed_enabled":              ("boolean", "false", "Feed off"),
    "autoplay_enabled":          ("boolean", "true",  "Autoplay on"),
    "remember_quality":          ("boolean", "true",  "Pamietaj jakosc"),
    "abr_enabled":               ("boolean", "true",  "ABR on"),
    "subtitles_font_size":       ("int",     "16",    "Rozmiar napisow TV"),
    "live_stream_quality":       ("string",  "1080",  "Live 1080p"),
}

# ================================================================
# KROK 2 -- Optymalizacja (XML + JSON)
# ================================================================

class ConfigOptimizer:

    def __init__(self, file_path: Path, dry_run: bool = False):
        self.path     = file_path
        self.dry_run  = dry_run
        self.changes: List[Tuple[str, str, str]] = []
        self.tree:    Optional[ET.ElementTree] = None
        self.root_el: Optional[ET.Element]    = None
        self._json_data: Optional[dict] = None
        self._is_json = file_path.suffix.lower() == ".json"
        self._is_xml  = file_path.suffix.lower() in (".xml", ".bak")

    def load(self) -> bool:
        if self._is_json:
            return self._load_json()
        return self._load_xml()

    def _load_xml(self) -> bool:
        try:
            self.tree    = ET.parse(str(self.path))
            self.root_el = self.tree.getroot()
            return True
        except ET.ParseError as e:
            try:
                content = self.path.read_text(encoding="utf-8", errors="replace")
                content = content.replace('<?xml version=\'1.0\' encoding=\'utf-8\' standalone=\'yes\' ?>', '')
                content = '<?xml version="1.0" encoding="utf-8"?>' + content
                self.root_el = ET.fromstring(content)
                self.tree    = ET.ElementTree(self.root_el)
                return True
            except Exception:
                err("  Blad parsowania XML: " + str(e))
                return False
        except Exception as e:
            err("  Blad odczytu XML: " + str(e))
            return False

    def _load_json(self) -> bool:
        import json
        try:
            with open(str(self.path), encoding="utf-8") as f:
                self._json_data = json.load(f)
            return True
        except Exception as e:
            err("  Blad parsowania JSON: " + str(e))
            return False

    def _xml_set(self, key: str, typ: str, value: str) -> bool:
        if self.root_el is None:
            return False
        for el in self.root_el:
            if el.get("name") == key:
                old = el.text if el.tag == "string" else el.get("value", "")
                if str(old) == str(value) and el.tag == typ:
                    return False
                if typ == "string":
                    el.tag = "string"
                    el.text = value
                    if "value" in el.attrib:
                        del el.attrib["value"]
                else:
                    el.tag = typ
                    el.set("value", value)
                    el.text = None
                self.changes.append((key, str(old), value))
                return True
        if typ == "string":
            ne = ET.SubElement(self.root_el, "string", {"name": key})
            ne.text = value
        else:
            ET.SubElement(self.root_el, typ, {"name": key, "value": value})
        self.changes.append((key, "<brak>", value))
        return True

    def _apply_xml(self) -> int:
        changed = 0
        for key, (typ, value, desc) in BCM72604_OPTIMAL.items():
            if self._xml_set(key, typ, value):
                changed += 1
                fix("  [XML] " + key + " = " + value + _D + "  (" + desc + ")" + _R)
        if self.root_el is not None:
            for el in self.root_el:
                name = el.get("name", "")
                val  = el.text if el.tag == "string" else el.get("value", "")
                if val and val in ["2160", "4k", "4K", "UHD", "2160p", "5", "6", "7"]:
                    if any(kw in name.lower() for kw in ("resolution", "quality")):
                        old = val
                        if el.tag == "string":
                            el.text = "1080"
                        else:
                            el.set("value", "4")
                        self.changes.append((name, old, "1080"))
                        fix("  [RES] " + name + " = 4K->1080p")
                        changed += 1
                if "av1" in name.lower() and val not in ("false", "0", ""):
                    old = val
                    if el.tag == "boolean":
                        el.set("value", "false")
                    elif el.tag == "string":
                        el.text = "false"
                    elif el.tag == "int":
                        el.set("value", "0")
                    self.changes.append((name, old, "disabled"))
                    fix("  [AV1] " + name + " -> disabled")
                    changed += 1
        return changed

    def _json_set(self, key: str, typ: str, value: str) -> bool:
        if self._json_data is None:
            return False

        if typ == "boolean":
            new_val = (value == "true")
        elif typ == "int":
            try:
                new_val = int(value)
            except ValueError:
                new_val = value
        elif typ == "float":
            try:
                new_val = float(value)
            except ValueError:
                new_val = value
        else:
            new_val = value

        changed = self._json_set_recursive(self._json_data, key, new_val)
        if changed:
            self.changes.append((key, "?", str(value)))
        return changed

    def _json_set_recursive(self, obj, key: str, value) -> bool:
        if isinstance(obj, dict):
            if key in obj:
                if obj[key] != value:
                    obj[key] = value
                    return True
                return False
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    if self._json_set_recursive(v, key, value):
                        return True
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    if item.get("name") == key or item.get("key") == key:
                        old = item.get("value", item.get("val"))
                        if old != value:
                            if "value" in item:
                                item["value"] = value
                            elif "val" in item:
                                item["val"] = value
                            return True
                        return False
                    if self._json_set_recursive(item, key, value):
                        return True
        return False

    def _apply_json(self) -> int:
        changed = 0
        for key, (typ, value, desc) in BCM72604_OPTIMAL.items():
            if self._json_set(key, typ, value):
                changed += 1
                fix("  [JSON] " + key + " = " + value + _D + "  (" + desc + ")" + _R)
        return changed

    def apply_optimizations(self) -> int:
        if self._is_json:
            return self._apply_json()
        return self._apply_xml()

    def save(self, output_path: Optional[Path] = None) -> bool:
        if self.dry_run:
            info("  [DRY RUN] Nie zapisano")
            return True
        target = output_path or self.path
        if self._is_json:
            return self._save_json(target)
        return self._save_xml(target)

    def _save_xml(self, target: Path) -> bool:
        try:
            _indent_xml(self.root_el)
            self.tree.write(str(target), encoding="utf-8", xml_declaration=True)
            ok("  Zapisano XML: " + target.name + " (" + str(target.stat().st_size) + " B)")
            return True
        except Exception as e:
            err("  Blad zapisu XML: " + str(e))
            return False

    def _save_json(self, target: Path) -> bool:
        import json
        try:
            with open(str(target), "w", encoding="utf-8") as f:
                json.dump(self._json_data, f, indent=2, ensure_ascii=False)
            ok("  Zapisano JSON: " + target.name + " (" + str(target.stat().st_size) + " B)")
            return True
        except Exception as e:
            err("  Blad zapisu JSON: " + str(e))
            return False

    def print_summary(self) -> None:
        if not self.changes:
            ok("  Brak zmian -- " + self.path.name + " juz optymalny")
            return
        print("\n  " + _BO + "Zmiany w " + self.path.name + " (" + str(len(self.changes)) + "):" + _R)
        print("  " + _D + "-" * 56 + _R)
        for key, old, new in self.changes:
            ks  = (key[:32] + "..") if len(key) > 34 else key.ljust(34)
            old_s = str(old)[:10].ljust(10)
            print("  " + _C + ks + _R + " " + _D + old_s + _R + " -> " + _G + str(new)[:14] + _R)


# ================================================================
# KROK 3 -- Import (push do natywnej sciezki backupu i UI Automation)
# ================================================================

class ConfigImporter:
    """
    Importuje zoptymalizowana konfiguracje z powrotem do SmartTube.
    Wymusza załadowanie przez automatyzację interfejsu (zgodnie z logami).
    """

    @classmethod
    def import_configs(cls, pkg: str, files: Dict[str, Path], backup_dir: str, dry_run: bool = False) -> bool:
        hdr("KROK 3 -- Import konfiguracji do SmartTube")

        if dry_run:
            info("[DRY RUN] Import pominieto")
            return True

        if not files:
            err("Brak plikow do importu")
            return False

        info("Zatrzymywanie SmartTube przed nadpisaniem plików...")
        _ADB.sh("am force-stop " + pkg, silent=True)
        time.sleep(1.5)

        _ADB.mkdir(backup_dir)

        # 1. Wgranie plików konfiguracyjnych 
        ok_count = 0
        for fname, local_path in files.items():
            remote = backup_dir + "/" + fname
            info("Push: " + fname + " -> " + remote)
            if _ADB.push(str(local_path), remote):
                ok("  " + fname + " [" + str(local_path.stat().st_size) + " B]")
                ok_count += 1
            else:
                alt = "/sdcard/data/" + fname
                if _ADB.push(str(local_path), alt):
                    ok("  " + fname + " -> " + alt + " (fallback)")
                    ok_count += 1
                else:
                    warn("  Push nieudany: " + fname)

        if ok_count == 0:
            err("Import nieudany -- brak pushnionych plikow")
            return False

        ok("Pushnieto " + str(ok_count) + "/" + str(len(files)) + " plikow")

        # 2. Procedura UI ładująca ustawienia (zgodna z analizą Logcat)
        info("Wywoływanie procesu załadowania kopii przez automatyzację UI...")
        
        # Otwieramy najpierw aplikację
        _ADB.sh("monkey -p " + pkg + " -c android.intent.category.LAUNCHER 1 2>/dev/null", silent=True)
        time.sleep(3)
        
        # Wywołujemy sekwencję UI
        SmartTubeBackupTrigger.trigger_ui_action(pkg, "Import")
        
        # Zgodnie z logami, SmartTube wykona System.exit(0) po poprawnym restaurowaniu
        time.sleep(3)
        if not _ADB.pkg_running(pkg):
            ok("Proces SmartTube został poprawnie ubity przez aplikację (System.exit(0)) po restaurowaniu danych.")
        else:
            warn("Proces SmartTube nadal działa. Restoring mógł nie zainicjować restartu.")
            
        # 3. Uruchamiamy SmartTube ponownie z nowymi ustawieniami
        info("Uruchamianie SmartTube z nową, zoptymalizowaną konfiguracją...")
        _ADB.sh("monkey -p " + pkg + " -c android.intent.category.LAUNCHER 1 2>/dev/null", silent=True)
        time.sleep(2)

        print()
        info("Weryfikacja w SmartTube:")
        print("  " + _B + "  Ustawienia -> Odtwarzacz -> Kodek wideo -> VP9" + _R)
        print("  " + _B + "  Ustawienia -> Odtwarzacz -> Tryb tunelowy -> WL" + _R)
        print("  " + _B + "  Ustawienia -> Jakosc -> Max rozdzielczosc -> 1080p" + _R)

        return True


# ================================================================
# Pomocnicze
# ================================================================

def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    indent = "\n" + "    " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        last = None
        for child in elem:
            _indent_xml(child, level + 1)
            last = child
        if last is not None and (not last.tail or not last.tail.strip()):
            last.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def print_file_summary(file_path: Path) -> None:
    KEYS = [
        "video_codec", "use_tunnel_mode", "hdr_mode",
        "video_resolution", "preferred_resolution",
        "video_frame_rate_switch", "auto_frame_rate",
        "hardware_acceleration", "av1_enabled", "vp9_enabled",
        "buffer_type", "min_buffer_duration",
        "background_play_mode", "player_stats",
    ]
    found = {}

    if file_path.suffix.lower() == ".json":
        import json
        try:
            with open(str(file_path), encoding="utf-8") as f:
                data = json.load(f)
            def _find_in_json(obj, keys):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k in keys:
                            found[k] = ("json", str(v))
                        elif isinstance(v, (dict, list)):
                            _find_in_json(v, keys)
                elif isinstance(obj, list):
                    for item in obj:
                        _find_in_json(item, keys)
            _find_in_json(data, set(KEYS))
        except Exception:
            return
    else:
        try:
            tree = ET.parse(str(file_path))
            root = tree.getroot()
            for el in root:
                name = el.get("name", "")
                if name in KEYS:
                    val = el.text if el.tag == "string" else el.get("value", "?")
                    found[name] = (el.tag, val)
        except Exception:
            return

    if not found:
        return

    print("  " + _BO + file_path.name + ":" + _R)
    for key in KEYS:
        if key in found:
            typ, val = found[key]
            opt = BCM72604_OPTIMAL.get(key, (None, None, None))[1]
            col = _G if (opt and str(val) == str(opt)) else (_E if opt else _B)
            print("  " + _C + key[:35].ljust(35) + _R +
                  " = " + col + str(val) + _R + _D + " [" + typ + "]" + _R)
    print()


# ================================================================
# Glowny menedzer
# ================================================================

class SmartTubeConfigManager:

    @classmethod
    def run_full(cls, device: Optional[str] = None, dry_run: bool = False,
                 export_only: bool = False, restore_dir: Optional[str] = None) -> bool:

        hdr("SmartTube Config Manager -- BCM72604 Optimizer")
        info("Tryb: " + ("DRY RUN" if dry_run else "RESTORE" if restore_dir else "EXPORT ONLY" if export_only else "PELNY"))

        if device:
            if not _ADB.connect(device):
                return False
        else:
            if not _ADB.autodetect():
                err("Brak polaczenia ADB -- podaj --device IP:PORT")
                return False

        pkg = detect_pkg()
        if not pkg:
            err("SmartTube nie zainstalowane")
            return False
        ok("Pakiet: " + pkg)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_dir = LOCAL_DIR / ts
        work_dir.mkdir(parents=True, exist_ok=True)
        info("Katalog roboczy: " + str(work_dir))

        if restore_dir:
            return cls._do_restore(pkg, Path(restore_dir), DEVICE_BACKUP_BASE + "/" + pkg, dry_run)

        # ---- KROK 1: EKSPORT ---
        step(1, 3, "Eksport konfiguracji z urzadzenia")
        exported, backup_dir = ConfigExporter.export(pkg, work_dir / "original")
        if not exported:
            return False

        sub("Stan PRZED optymalizacja")
        for _, fp in exported.items():
            print_file_summary(fp)

        if export_only:
            ok("Eksport zakonczone")
            info("Pliki: " + str(work_dir / "original"))
            return True

        # ---- KROK 2: OPTYMALIZACJA ---
        step(2, 3, "Optymalizacja dla BCM72604")
        opt_dir = work_dir / "optimized"
        opt_dir.mkdir(exist_ok=True)

        optimized_files: Dict[str, Path] = {}
        total_changes = 0

        for fname, orig_path in exported.items():
            info("Optymalizuje: " + fname + "...")
            opt_path = opt_dir / fname
            shutil.copy2(str(orig_path), str(opt_path))

            optimizer = ConfigOptimizer(opt_path, dry_run=dry_run)
            if not optimizer.load():
                warn("  Pominieto: " + fname)
                optimized_files[fname] = opt_path
                continue

            n = optimizer.apply_optimizations()
            optimizer.print_summary()
            total_changes += n

            if optimizer.save():
                optimized_files[fname] = opt_path

        print()
        ok("Laczna liczba zmian: " + str(total_changes))

        sub("Stan PO optymalizacji")
        for _, fp in optimized_files.items():
            print_file_summary(fp)

        # ---- KROK 3: IMPORT ---
        step(3, 3, "Import zoptymalizowanej konfiguracji")

        if not dry_run:
            try:
                ans = input("\n  " + _Y + "Importowac zoptymalizowana konfiguracje? [T/n] > " + _R).strip().lower()
                proceed = ans in ("", "t", "y", "tak", "yes")
            except (EOFError, KeyboardInterrupt):
                proceed = False

            if proceed:
                if ConfigImporter.import_configs(pkg, optimized_files, backup_dir, dry_run):
                    hdr("Gotowe!")
                    ok("Konfiguracja SmartTube zoptymalizowana dla BCM72604")
                    ok("VP9 HW + Tunnel Mode + HDR10 + 1080p + AV1 zablokowany")
                    info("Backup oryginalu: " + str(work_dir / "original"))
                    info("Rollback: --restore " + str(work_dir / "original"))
                    return True
                else:
                    return False
            else:
                info("Import anulowany")
                info("Recznie: --restore " + str(opt_dir))
        else:
            info("[DRY RUN] Import pominieto")

        return True

    @classmethod
    def _do_restore(cls, pkg: str, restore_dir: Path, backup_dir: str, dry_run: bool) -> bool:
        hdr("RESTORE -- Przywracanie konfiguracji")
        if not restore_dir.exists():
            err("Katalog nie istnieje: " + str(restore_dir))
            return False
        files_list = list(restore_dir.glob("*.xml")) + list(restore_dir.glob("*.json")) + list(restore_dir.glob("*.bak"))
        if not files_list:
            err("Brak plikow w: " + str(restore_dir))
            return False
        restore_files = {f.name: f for f in files_list}
        info("Pliki do przywrocenia: " + ", ".join(restore_files.keys()))
        return ConfigImporter.import_configs(pkg, restore_files, backup_dir, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SmartTube Config Manager -- BCM72604 Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "PRZYKLADY:\n"
            "  python3 smarttube_config.py --device 192.168.1.3:5555\n"
            "  python3 smarttube_config.py --dry-run\n"
            "  python3 smarttube_config.py --export-only\n"
            "  python3 smarttube_config.py --restore ~/.playbox_cache/smarttube_configs/20240101/original\n"
            "  python3 smarttube_config.py --show ./prefs.xml\n"
        )
    )
    parser.add_argument("--device",      default=None, help="ADB device IP:PORT")
    parser.add_argument("--dry-run",     action="store_true", help="Pokaz zmiany bez zapisu i importu")
    parser.add_argument("--export-only", action="store_true", help="Tylko eksportuj")
    parser.add_argument("--restore",     default=None, metavar="KATALOG", help="Przywroc z katalogu backup")
    parser.add_argument("--show",        default=None, metavar="PLIK", help="Pokaz zawartosc pliku XML/JSON")
    args = parser.parse_args()

    if args.show:
        p = Path(args.show)
        if not p.exists():
            err("Plik nie istnieje: " + args.show)
            sys.exit(1)
        hdr("Zawartosc: " + p.name)
        print_file_summary(p)
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
