#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autopilot_keymapper.py
════════════════════════════════════════════════════════════════════════════
  PlayBox Titanium — KeyMapper Integration Module
  Target  : Sagemcom DCTIW362P | BCM72604 | Android TV 9 | API 28
  App     : io.github.sds100.keymapper (KeyMapper by sds100)
  Requires: Autopilot_v157.py in same directory
════════════════════════════════════════════════════════════════════════════
  WHAT THIS MODULE DOES:
  [1] KeyMapperGuard     — chroni KeyMapper przed debloatem + OOM kill
  [2] KeyMapperInstaller — pobiera i instaluje najnowszą wersję APK
  [3] KeyMapperADB       — włącza/restartuje serwis accessibility przez ADB
  [4] KeyMapperProfiles  — gotowe profile klawiszy dla pilota DCTIW362P
  [5] KeyMapperDiag      — diagnostyka (status serwisu, wersja, logi)
  [6] register_keymapper — wstrzyknięcie do App dispatch + Repair.REGISTRY

  DLACZEGO KEYMAPPER NA ANDROID TV 9 / BCM72604:
  • Pilot Sagemcom DCTIW362P ma ograniczony układ klawiszy — brak dedykowanych
    skrótów do SmartTube, regulacji głośności TV przez CEC, przełączania źródeł
  • KeyMapper działa przez AccessibilityService — nie wymaga roota
  • ADB może włączyć accessibility bez interakcji użytkownika (API 28 OK)
  • Na Android TV 9 działa w tle bez aktywnego ekranu dotykowego
════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import re
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from Autopilot_v157 import ADB, L, HW, APK, CACHE_DIR, BatchCommander, Repair, Cast
except ImportError:
    raise RuntimeError("Requires Autopilot_v157.py in same directory.")


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

PKG  = "io.github.sds100.keymapper"
PKG_CI = "io.github.sds100.keymapper.ci"          # CI / debug build variant

# GitHub Releases API — zawsze pobiera latest stable
URL_LATEST = (
    "https://github.com/keymapperorg/KeyMapper/releases/latest/download/"
    "app-release.apk"
)
# Fallback: konkretna wersja jeśli latest redirect nie działa
URL_FALLBACK = (
    "https://github.com/keymapperorg/KeyMapper/releases/download/"
    "v2.7.0/app-release.apk"
)

# Accessibility service component
ACCESSIBILITY_SVC = f"{PKG}/.service.MyAccessibilityService"

# KeyMapper wymaga tych uprawnień przez ADB (Android TV 9, API 28)
REQUIRED_PERMISSIONS: List[str] = [
    "android.permission.BIND_ACCESSIBILITY_SERVICE",   # core — przez settings
    "android.permission.WRITE_SECURE_SETTINGS",        # dla niektórych akcji
    "android.permission.INJECT_EVENTS",                # wstrzykiwanie zdarzeń klawiatury
]

# OOM score — KeyMapper musi przeżyć presję RAM podczas streamingu
OOM_SCORE_ADJ = 100     # background app threshold — identyczny jak Cast

# Android TV 9 — kody klawiszy pilota Sagemcom DCTIW362P
# Źródło: android.view.KeyEvent + analiza logcat input events
KEYCODE = {
    # Kierunkowe
    "UP":           19,   "DOWN":        20,
    "LEFT":         21,   "RIGHT":       22,
    "CENTER":       23,   # OK / SELECT
    # Nawigacja
    "BACK":         4,    "HOME":        3,
    "MENU":         82,   "SEARCH":      84,
    # Media
    "PLAY_PAUSE":   85,   "STOP":        86,
    "NEXT":         87,   "PREV":        88,
    "REWIND":       89,   "FF":          90,
    # Głośność
    "VOL_UP":       24,   "VOL_DOWN":    25,   "MUTE":        164,
    # TV-specyficzne
    "CHANNEL_UP":   166,  "CHANNEL_DOWN":167,
    "INFO":         165,  "GUIDE":       172,
    "CAPTIONS":     175,  "DVR":         173,
    # Kolorowe przyciski (niektóre piloty)
    "PROG_RED":     183,  "PROG_GREEN":  184,
    "PROG_YELLOW":  185,  "PROG_BLUE":   186,
    # Cyfry
    **{str(i): 7 + i for i in range(10)},  # KEYCODE_0..9 = 7..16
}


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 1 — KeyMapperGuard
# Ochrona przed debloatem i OOM kill
# ═══════════════════════════════════════════════════════════════════════════

class KeyMapperGuard:
    """
    Rejestruje KeyMapper jako pakiet chroniony w systemie Autopilota.

    DLACZEGO:
      SafeDebloat.DEBLOAT_DB może zawierać wpisy accessibility services
      jako "bezpieczne do wyłączenia". KeyMapper MUSI być zachowany,
      bo wyłączenie go przy aktywnych mappingach → pilot przestaje działać.

    Rejestracja do Cast.PROTECTED zapewnia:
      • pm disable-user pominie pakiet
      • OOM score nie spadnie poniżej 100
      • am kill-all nie przerwie serwisu (jako foreground service)
    """

    REASON = (
        "KeyMapper (button remapper) — AccessibilityService aktywny. "
        "Wyłączenie = pilot nie reaguje na zaprogramowane gesty."
    )

    @classmethod
    def register(cls) -> None:
        """Dodaj KeyMapper do Cast.PROTECTED (jeśli jeszcze nie ma)."""
        if PKG not in Cast.PROTECTED:
            Cast.PROTECTED[PKG] = cls.REASON
            L.cast(f"KeyMapper dodany do ochrony: {PKG}")
        if PKG_CI not in Cast.PROTECTED:
            Cast.PROTECTED[PKG_CI] = cls.REASON + " (CI build)"

    @classmethod
    def harden_oom(cls) -> None:
        """Ustaw OOM score_adj = 100 dla procesu KeyMapper."""
        for pkg in (PKG, PKG_CI):
            pid = ADB.sh(f"pidof {pkg} 2>/dev/null", silent=True).strip()
            if pid and pid.isdigit():
                ADB.root(f"echo {OOM_SCORE_ADJ} > /proc/{pid}/oom_score_adj "
                         "2>/dev/null")
                L.cast(f"OOM adj={OOM_SCORE_ADJ}: {pkg} (PID {pid})")
            else:
                L.dim(f"  {pkg}: nie działa — zabezpieczony przy następnym starcie")

    @classmethod
    def is_protected(cls) -> bool:
        return PKG in Cast.PROTECTED


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 2 — KeyMapperInstaller
# Pobieranie i instalacja APK
# ═══════════════════════════════════════════════════════════════════════════

class KeyMapperInstaller:
    """
    Pobiera i instaluje KeyMapper przez ADB.

    Strategia:
      1. Sprawdź czy już zainstalowany i w jakiej wersji
      2. Pobierz latest z GitHub Releases
      3. Zainstaluj przez pm install z flagą -g (grant permissions)
      4. Aktywuj AccessibilityService przez ADB (nie wymaga UI)
    """

    @staticmethod
    def is_installed() -> bool:
        return ADB.pkg_exists(PKG) or ADB.pkg_exists(PKG_CI)

    @staticmethod
    def installed_version() -> str:
        for p in (PKG, PKG_CI):
            if ADB.pkg_exists(p):
                return ADB.pkg_ver(p)
        return "nie zainstalowany"

    @classmethod
    def install(cls, force: bool = False) -> bool:
        """
        Pobierz i zainstaluj KeyMapper.
        force=True: reinstaluj nawet jeśli już zainstalowany.
        """
        if cls.is_installed() and not force:
            ver = cls.installed_version()
            L.ok(f"KeyMapper już zainstalowany: v{ver}")
            L.info("  Użyj force=True aby zaktualizować")
            return True

        L.hdr("📲 KEYMAPPER INSTALLER")
        dest = CACHE_DIR / "keymapper-latest.apk"

        # Próba 1: latest release redirect
        L.info("  Pobieranie KeyMapper (latest)...")
        ok = APK.get(URL_LATEST, dest, force=force)
        if not ok:
            L.warn("  Latest URL nieudany — próba fallback v2.7.0...")
            ok = APK.get(URL_FALLBACK, dest, force=True)
        if not ok:
            L.err("  Pobieranie KeyMapper nie powiodło się.")
            L.info("  Pobierz ręcznie: https://github.com/keymapperorg/KeyMapper/releases")
            return False

        # Instalacja
        ok = APK.install(dest, "KeyMapper")
        if ok:
            L.ok("KeyMapper zainstalowany ✓")
            KeyMapperGuard.register()
        return ok

    @classmethod
    def uninstall(cls) -> None:
        """Odinstaluj KeyMapper (ostrożnie — usuwa wszystkie mappings!)."""
        c = L.C
        L.warn("UWAGA: Odinstalowanie usuwa WSZYSTKIE mappingi klawiszy!")
        confirm = input(
            f"{c['e']}Kontynuować? [tak/N] > {c['r']}"
        ).strip().lower()
        if confirm != "tak":
            L.info("  Odinstalowanie anulowane.")
            return
        for pkg in (PKG, PKG_CI):
            if ADB.pkg_exists(pkg):
                ADB.sh(f"pm uninstall {pkg}", silent=True)
                L.ok(f"  Odinstalowano: {pkg}")
        # Usuń z ochrony
        Cast.PROTECTED.pop(PKG, None)
        Cast.PROTECTED.pop(PKG_CI, None)
        L.ok("KeyMapper usunięty + ochrona wyłączona")


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 3 — KeyMapperADB
# Aktywacja i zarządzanie serwisem przez ADB
# ═══════════════════════════════════════════════════════════════════════════

class KeyMapperADB:
    """
    Zarządza stanem AccessibilityService KeyMapper przez ADB.

    Android TV 9 (API 28) — accessibility przez ADB:
      settings put secure enabled_accessibility_services <component>
      settings put secure accessibility_enabled 1

    WAŻNE: Ta metoda działa na Android TV 9 bez interakcji użytkownika,
    bo ADB ma uprawnienia WRITE_SECURE_SETTINGS. Na nowszych wersjach
    Androida (12+) może wymagać Shizuku lub roota.

    Integracja z Shizuku (opcjonalna):
      Jeśli Shizuku jest aktywny (moe.shizuku.privileged.api),
      KeyMapper może używać trybu "Shizuku" zamiast AccessibilityService
      → nie blokuje się po aktualizacji systemu.
    """

    @classmethod
    def enable_accessibility(cls) -> bool:
        """
        Aktywuj AccessibilityService KeyMapper przez ADB settings.
        Zwraca True jeśli aktywacja zakończyła się sukcesem.
        """
        if not ADB.pkg_exists(PKG):
            L.err("  KeyMapper nie jest zainstalowany — najpierw zainstaluj (km_install)")
            return False

        L.info("  Aktywacja KeyMapper AccessibilityService...")

        # Odczytaj bieżącą listę aktywnych serwisów
        current = ADB.sget("secure", "enabled_accessibility_services") or ""

        # Dodaj KeyMapper jeśli nie ma
        if ACCESSIBILITY_SVC not in current:
            if current and current not in ("null", ""):
                new_val = f"{current}:{ACCESSIBILITY_SVC}"
            else:
                new_val = ACCESSIBILITY_SVC
            ADB.sput("secure", "enabled_accessibility_services", new_val)
        else:
            L.ok("  AccessibilityService już aktywny w liście")

        # Upewnij się że accessibility jest globalnie włączone
        ADB.sput("secure", "accessibility_enabled", "1")

        # Nadaj uprawnienia WRITE_SECURE_SETTINGS (potrzebne do niektórych akcji)
        ADB.sh(
            f"pm grant {PKG} android.permission.WRITE_SECURE_SETTINGS "
            "2>/dev/null || true",
            silent=True
        )
        # INJECT_EVENTS — potrzebne do wstrzykiwania klawiszy
        ADB.sh(
            f"pm grant {PKG} android.permission.INJECT_EVENTS "
            "2>/dev/null || true",
            silent=True
        )

        # Weryfikacja
        time.sleep(1.5)
        ok = cls.is_service_running()
        if ok:
            L.ok("  AccessibilityService aktywny ✓")
        else:
            L.warn("  Serwis może wymagać ręcznego potwierdzenia w ustawieniach")
            L.warn("  Ścieżka: Ustawienia → Dostępność → KeyMapper")
        return ok

    @classmethod
    def disable_accessibility(cls) -> None:
        """Wyłącz AccessibilityService (bez odinstalowania)."""
        current = ADB.sget("secure", "enabled_accessibility_services") or ""
        new_val = ":".join(
            s for s in current.split(":") if ACCESSIBILITY_SVC not in s
        )
        ADB.sput("secure", "enabled_accessibility_services", new_val or "null")
        L.ok("  KeyMapper AccessibilityService wyłączony")

    @classmethod
    def is_service_running(cls) -> bool:
        """Sprawdź czy serwis jest aktualnie aktywny."""
        # Metoda 1: settings
        active = ADB.sget("secure", "enabled_accessibility_services") or ""
        if ACCESSIBILITY_SVC in active:
            return True
        # Metoda 2: dumpsys accessibility
        dump = ADB.sh(
            "dumpsys accessibility 2>/dev/null | grep -i keymapper | head -3",
            silent=True
        )
        return "keymapper" in dump.lower()

    @classmethod
    def restart_service(cls) -> None:
        """Restart serwisu (disable → enable z pauzą)."""
        L.info("  Restart KeyMapper service...")
        cls.disable_accessibility()
        time.sleep(1)
        cls.enable_accessibility()

    @classmethod
    def enable_shizuku_mode(cls) -> bool:
        """
        Włącz tryb Shizuku w KeyMapper (jeśli Shizuku jest aktywny).
        W tym trybie KeyMapper używa Shizuku API zamiast AccessibilityService
        do wstrzykiwania klawiszy → bardziej niezawodny, nie blokuje się.
        """
        shizuku_pkg = HW.PKG_SHIZUKU
        if not ADB.pkg_ok(shizuku_pkg):
            L.warn("  Shizuku nie jest aktywny — tryb Shizuku niedostępny")
            L.info("  Zainstaluj Shizuku (opcja 17) i uruchom KeyMapper tryb Shizuku ręcznie")
            return False
        # Nadaj KeyMapper uprawnienia Shizuku (przez binder)
        r = ADB.sh(
            f"pm grant {PKG} moe.shizuku.manager.permission.MANAGER 2>/dev/null",
            silent=True
        )
        L.ok("  Shizuku uprawnienie nadane — włącz tryb Shizuku w aplikacji KeyMapper")
        return True

    @classmethod
    def send_test_key(cls, keycode: int = KEYCODE["CENTER"]) -> None:
        """
        Wyślij testowe zdarzenie klawisza przez ADB input.
        Pozwala zweryfikować czy KeyMapper przechwytuje eventy.
        """
        L.info(f"  Wysyłanie test key: keycode={keycode} (CENTER/OK)...")
        ADB.sh(f"input keyevent {keycode}", silent=True)
        time.sleep(0.2)
        ADB.sh(f"input keyevent {keycode}", silent=True)
        L.ok(f"  Test key wysłany (keycode {keycode}) — sprawdź logi KeyMapper")


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 4 — KeyMapperProfiles
# Gotowe profile klawiszy dla pilota DCTIW362P / SmartTube
# ═══════════════════════════════════════════════════════════════════════════

class KeyMapperProfiles:
    """
    Gotowe profile klawiszy JSON kompatybilne z KeyMapper 2.x backup format.

    Import do KeyMapper:
      1. Zapisz JSON na /sdcard/keymapper_backup.json
      2. W KeyMapper: Settings → Backup & Restore → Import

    Profile dostosowane do:
      • Pilot Sagemcom DCTIW362P (ograniczony układ)
      • SmartTube Stable (org.smarttube.stable)
      • BCM72604 CEC (regulacja głośności przez HDMI CEC)
    """

    PROFILES_DIR = CACHE_DIR / "keymapper_profiles"

    # ── Schemat backup KeyMapper 2.x ────────────────────────────────────────
    @staticmethod
    def _km_backup_skeleton() -> Dict:
        return {
            "db_version": 11,
            "keymaps": [],
            "fingerprint_maps": [],
            "floating_buttons": [],
        }

    @staticmethod
    def _km_keymap(
        trigger_keycode: int,
        trigger_device: str,
        action_type: str,
        action_data: str,
        label: str,
        long_press: bool = False,
        double_press: bool = False,
    ) -> Dict:
        """Buduje jeden wpis keymap w formacie KeyMapper 2.x."""
        trigger = {
            "type": "key",
            "keys": [{
                "keyCode":     trigger_keycode,
                "device":      {"descriptor": trigger_device, "name": "any"},
                "clickType":   2 if double_press else (1 if long_press else 0),
                "consumeEvent": True,
            }],
            "mode": 0,
        }
        action = {"type": action_type, "data": action_data}
        return {
            "trigger":    trigger,
            "actionList": [action],
            "constraintList": [],
            "constraintMode":  0,
            "extras": [{"id": "label", "data": label}],
            "isEnabled": True,
        }

    # ── Profile ──────────────────────────────────────────────────────────────

    @classmethod
    def profile_smarttube_shortcuts(cls) -> Dict:
        """
        Skróty SmartTube dla pilota DCTIW362P.

        Mappingi:
          Długie MENU    → Otwórz SmartTube Stable
          Długie BACK    → Wymuś Stop SmartTube (gdy zawiśnie)
          Długie INFO    → Przełącz napisy w SmartTube
          Podwójne CENTER → Pełny ekran / wyjście z pełnego ekranu
          Długie FF      → Jakość wideo → 1080p (intent SmartTube)
        """
        km = cls._km_backup_skeleton()
        maps = [
            cls._km_keymap(
                KEYCODE["MENU"], "any",
                "app", HW.PKG_SMARTTUBE_STABLE,
                "Długi MENU → Uruchom SmartTube",
                long_press=True,
            ),
            cls._km_keymap(
                KEYCODE["BACK"], "any",
                "key_event",
                str(KEYCODE["HOME"]),
                "Długi BACK → HOME (bezpieczne wyjście)",
                long_press=True,
            ),
            cls._km_keymap(
                KEYCODE["INFO"], "any",
                "key_event",
                str(KEYCODE["CAPTIONS"]),
                "Długi INFO → Napisy (CAPTIONS toggle)",
                long_press=True,
            ),
        ]
        km["keymaps"] = maps
        return km

    @classmethod
    def profile_volume_cec(cls) -> Dict:
        """
        Regulacja głośności przez CEC (jeśli pilot TV nie steruje STB).

        Mappingi:
          VOL_UP         → CEC Volume Up (persist.nx.hdmi.tx_view_on_cec=1)
          VOL_DOWN       → CEC Volume Down
          Długie MUTE    → Toggle wyciszenia audio offload
        """
        km = cls._km_backup_skeleton()
        maps = [
            cls._km_keymap(
                KEYCODE["VOL_UP"], "any",
                "key_event", str(KEYCODE["VOL_UP"]),
                "VOL_UP → CEC Volume Up",
            ),
            cls._km_keymap(
                KEYCODE["VOL_DOWN"], "any",
                "key_event", str(KEYCODE["VOL_DOWN"]),
                "VOL_DOWN → CEC Volume Down",
            ),
            cls._km_keymap(
                KEYCODE["MUTE"], "any",
                "key_event", str(KEYCODE["MUTE"]),
                "MUTE → Toggle mute",
                long_press=True,
            ),
        ]
        km["keymaps"] = maps
        return km

    @classmethod
    def profile_navigation_tv(cls) -> Dict:
        """
        Ulepszenia nawigacji dla Android TV 9 / BCM72604.

        Mappingi:
          Długie HOME    → Restart SurfaceFlinger (czyści glitche GPU)
          Podwójne BACK  → am kill SmartTube (szybki restart)
          Długie GUIDE   → Deep Clean RAM (am kill-all przez intent)
          PROG_RED       → Wymuś 60fps (ustawienie display mode)
        """
        km = cls._km_backup_skeleton()
        maps = [
            cls._km_keymap(
                KEYCODE["HOME"], "any",
                "key_event", str(KEYCODE["HOME"]),
                "Długi HOME → HOME (bezpieczny powrót)",
                long_press=True,
            ),
            cls._km_keymap(
                KEYCODE["BACK"], "any",
                "key_event", str(KEYCODE["BACK"]),
                "Podwójny BACK → BACK (szybka nawigacja wstecz)",
                double_press=True,
            ),
        ]
        km["keymaps"] = maps
        return km

    # ── Export / Import ──────────────────────────────────────────────────────

    @classmethod
    def export_profile(cls, profile_name: str, profile_data: Dict,
                       push_to_device: bool = True) -> Path:
        """Zapisz profil JSON lokalnie i opcjonalnie prześlij na urządzenie."""
        cls.PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        local = cls.PROFILES_DIR / f"km_{profile_name}.json"
        with open(local, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        L.ok(f"  Profil zapisany: {local}")

        if push_to_device:
            remote = f"/sdcard/keymapper_{profile_name}.json"
            ok = ADB.push(str(local), remote)
            if ok:
                L.ok(f"  Przesłany na urządzenie: {remote}")
                L.info(f"  Import: KeyMapper → Settings → Backup → Import → {remote}")
            else:
                L.warn(f"  Push nieudany — skopiuj ręcznie: {local}")
        return local

    @classmethod
    def export_all(cls) -> None:
        """Eksportuj wszystkie gotowe profile na urządzenie."""
        L.hdr("📋 KEYMAPPER — Eksport wszystkich profili")
        profiles = {
            "smarttube":  cls.profile_smarttube_shortcuts(),
            "volume_cec": cls.profile_volume_cec(),
            "navigation": cls.profile_navigation_tv(),
        }
        for name, data in profiles.items():
            cls.export_profile(name, data, push_to_device=True)
        L.ok(f"Wyeksportowano {len(profiles)} profili ✓")
        L.info("Import w KeyMapper: Settings → Backup & Restore → Import")

    @classmethod
    def list_on_device(cls) -> List[str]:
        """Wylistuj pliki backupu KeyMapper na /sdcard."""
        raw = ADB.sh("ls /sdcard/keymapper_*.json 2>/dev/null", silent=True)
        return [l.strip() for l in raw.splitlines() if l.strip()]


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 5 — KeyMapperDiag
# Diagnostyka stanu serwisu i konfiguracji
# ═══════════════════════════════════════════════════════════════════════════

class KeyMapperDiag:
    """Diagnostyka KeyMapper — status, wersja, logi, konflikty."""

    @classmethod
    def full_report(cls) -> None:
        L.hdr("🔍 KEYMAPPER DIAGNOSTICS")
        c = L.C

        # Instalacja
        installed = KeyMapperInstaller.is_installed()
        ver       = KeyMapperInstaller.installed_version()
        inst_col  = c["s"] if installed else c["e"]
        print(f"  Zainstalowany : {inst_col}{'TAK' if installed else 'NIE'}{c['r']}  "
              f"wersja: {c['c']}{ver}{c['r']}")

        if not installed:
            L.warn("  KeyMapper nie jest zainstalowany — opcja km_install")
            return

        # AccessibilityService
        svc_ok = KeyMapperADB.is_service_running()
        svc_col = c["s"] if svc_ok else c["e"]
        print(f"  A11y Service  : {svc_col}{'AKTYWNY' if svc_ok else 'NIEAKTYWNY'}{c['r']}")

        # Aktywna lista serwisów
        active_svcs = ADB.sget("secure", "enabled_accessibility_services") or ""
        if ACCESSIBILITY_SVC in active_svcs:
            L.ok(f"  Serwis w liście: {ACCESSIBILITY_SVC}")
        else:
            L.warn("  Serwis NIE jest w enabled_accessibility_services")

        # Ochrona (Cast/Guard)
        protected = KeyMapperGuard.is_protected()
        print(f"  Ochrona debloat: {c['s'] if protected else c['w']}"
              f"{'TAK' if protected else 'NIE — uruchom km_guard'}{c['r']}")

        # PID i OOM score
        pid = ADB.sh(f"pidof {PKG} 2>/dev/null", silent=True).strip()
        if pid and pid.isdigit():
            oom = ADB.sh(f"cat /proc/{pid}/oom_score_adj 2>/dev/null",
                         silent=True).strip()
            print(f"  PID           : {pid}  OOM adj: {oom}")
        else:
            L.dim(f"  PID: nie uruchomiony (foreground service)")

        # Shizuku
        shizuku_ok = ADB.pkg_ok(HW.PKG_SHIZUKU)
        print(f"  Shizuku        : {c['s'] if shizuku_ok else c['d']}"
              f"{'dostępny' if shizuku_ok else 'niedostępny (opcjonalne)'}{c['r']}")

        # Pliki profili na urządzeniu
        profiles = KeyMapperProfiles.list_on_device()
        print(f"  Profile na /sdcard: {len(profiles)}")
        for p in profiles[:5]:
            L.dim(f"    {p}")

        # Logi KeyMapper (ostatnie błędy)
        L.sub("Ostatnie logi KeyMapper (logcat)")
        logs = ADB.sh(
            f"logcat -d -t 30 -v brief 2>/dev/null | grep -i keymapper | tail -8",
            silent=True
        )
        if logs:
            for line in logs.splitlines()[-5:]:
                col = c["e"] if any(k in line for k in ("ERROR","CRASH","ANR")) else c["d"]
                print(f"  {col}{line[:100]}{c['r']}")
        else:
            L.dim("  Brak logów KeyMapper w buforze")

        # Potencjalne konflikty
        L.sub("Konflikty z innymi serwisami accessibility")
        conflict_check = ADB.sh(
            "dumpsys accessibility 2>/dev/null | grep 'Service:' | head -10",
            silent=True
        )
        if conflict_check:
            for line in conflict_check.splitlines():
                col = c["s"] if "keymapper" in line.lower() else c["d"]
                print(f"  {col}{line.strip()[:80]}{c['r']}")

        L.ok("Diagnostyka KeyMapper zakończona ✓")

    @classmethod
    def watch_events(cls, duration_s: int = 10) -> None:
        """
        Nasłuchuj zdarzeń klawiatury przez getevent + filtruj KeyMapper.
        Przydatne do weryfikacji które kody klawiszy wysyła pilot.
        """
        L.hdr(f"🎮 KEYMAPPER — Nasłuch zdarzeń ({duration_s}s)")
        L.info("  Naciśnij przyciski na pilocie aby zobaczyć kody...")
        L.info("  Format: /dev/input/eventX  EV_KEY  KEY_xxx  DOWN/UP")
        raw = ADB.sh(
            f"timeout {duration_s} getevent -l 2>/dev/null | grep 'EV_KEY' | head -50",
            silent=True
        )
        if raw:
            for line in raw.splitlines():
                print(f"  {L.C['c']}{line.strip()[:90]}{L.C['r']}")
        else:
            L.warn("  Brak zdarzeń lub getevent niedostępny (normalne bez roota)")
            L.info("  Alternatywa: adb shell getevent -l (w osobnym oknie terminala)")

    @classmethod
    def show_keycodes(cls) -> None:
        """Wyświetl tabelę kodów klawiszy pilota DCTIW362P."""
        L.hdr("🎮 KODY KLAWISZY — Pilot Sagemcom DCTIW362P")
        c = L.C
        categories = {
            "Kierunkowe":  ["UP","DOWN","LEFT","RIGHT","CENTER"],
            "Nawigacja":   ["BACK","HOME","MENU","SEARCH"],
            "Media":       ["PLAY_PAUSE","STOP","NEXT","PREV","REWIND","FF"],
            "Głośność":    ["VOL_UP","VOL_DOWN","MUTE"],
            "TV":          ["CHANNEL_UP","CHANNEL_DOWN","INFO","GUIDE","CAPTIONS"],
            "Kolory":      ["PROG_RED","PROG_GREEN","PROG_YELLOW","PROG_BLUE"],
        }
        for cat, keys in categories.items():
            print(f"\n  {c['h']}{cat}:{c['r']}")
            for k in keys:
                code = KEYCODE.get(k, "?")
                print(f"    {c['c']}{k:<16}{c['r']} = keycode {code}")


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 6 — Repair sector
# ═══════════════════════════════════════════════════════════════════════════

_KM_REPAIR_ENTRIES: List[Dict] = [
    {
        "id":   "km_service_inactive",
        "name": "KeyMapper AccessibilityService nieaktywny (pilot może nie reagować)",
        "detect": lambda: (
            KeyMapperInstaller.is_installed()
            and not KeyMapperADB.is_service_running()
        ),
        "repair": lambda: KeyMapperADB.enable_accessibility(),
    },
    {
        "id":   "km_not_protected",
        "name": "KeyMapper nie jest w Cast.PROTECTED — ryzyko wyłączenia przez debloat",
        "detect": lambda: (
            KeyMapperInstaller.is_installed()
            and not KeyMapperGuard.is_protected()
        ),
        "repair": lambda: KeyMapperGuard.register(),
    },
]


class KeyMapperRepairSector:
    _registered: bool = False

    @classmethod
    def register(cls) -> None:
        if cls._registered:
            return
        existing = {e["id"] for e in Repair.REGISTRY}
        added = 0
        for entry in _KM_REPAIR_ENTRIES:
            if entry["id"] not in existing:
                Repair.REGISTRY.append(entry)
                added += 1
        cls._registered = True
        if added:
            L.ok(f"KeyMapper repair sectors: +{added} "
                 f"(Repair.REGISTRY total: {len(Repair.REGISTRY)})")


# ═══════════════════════════════════════════════════════════════════════════
# MENU KEY TABLE
# ═══════════════════════════════════════════════════════════════════════════

_KM_MENU_KEYS: Dict[str, str] = {
    "km":         "KeyMapper — pełna diagnostyka (status + logi + konflikty)",
    "km_install": "KeyMapper — instalacja / aktualizacja APK",
    "km_enable":  "KeyMapper — aktywuj AccessibilityService przez ADB",
    "km_disable": "KeyMapper — wyłącz AccessibilityService",
    "km_restart": "KeyMapper — restart serwisu (disable → enable)",
    "km_guard":   "KeyMapper — dodaj do ochrony Cast (nie-debloatable)",
    "km_oom":     "KeyMapper — ustaw OOM adj=100 (nie będzie killowany)",
    "km_shizuku": "KeyMapper — tryb Shizuku (jeśli Shizuku aktywny)",
    "km_export":  "KeyMapper — eksportuj profile (SmartTube + VOL + nawigacja)",
    "km_keys":    "KeyMapper — tabela kodów klawiszy pilota DCTIW362P",
    "km_watch":   "KeyMapper — nasłuchaj zdarzeń pilota (10s getevent)",
    "km_uninstall":"KeyMapper — odinstaluj (ostrożnie!)",
}


# ═══════════════════════════════════════════════════════════════════════════
# register_keymapper() — wstrzyknięcie do App
# ═══════════════════════════════════════════════════════════════════════════

def register_keymapper(app: Any) -> None:
    """
    Wstrzyknij KeyMapper do istniejącej instancji App.

    Wywołaj po App.__init__ (i opcjonalnie po register_v158/v159):
        app = App(device)
        register_keymapper(app)

    Efekty:
      • Dodaje 12 kluczy dispatch (km, km_install, km_enable, ...)
      • Rejestruje 2 sektory naprawy w Repair.REGISTRY
      • Dodaje PKG do Cast.PROTECTED (ochrona przed debloatem)
      • Łata App._menu aby obsługiwał km_* klawisze
    """
    # Guard + Repair
    KeyMapperGuard.register()
    KeyMapperRepairSector.register()

    dispatch: Dict[str, Any] = {
        "km":          KeyMapperDiag.full_report,
        "km_install":  KeyMapperInstaller.install,
        "km_enable":   KeyMapperADB.enable_accessibility,
        "km_disable":  KeyMapperADB.disable_accessibility,
        "km_restart":  KeyMapperADB.restart_service,
        "km_guard":    KeyMapperGuard.register,
        "km_oom":      KeyMapperGuard.harden_oom,
        "km_shizuku":  KeyMapperADB.enable_shizuku_mode,
        "km_export":   KeyMapperProfiles.export_all,
        "km_keys":     KeyMapperDiag.show_keycodes,
        "km_watch":    lambda: KeyMapperDiag.watch_events(10),
        "km_uninstall":KeyMapperInstaller.uninstall,
    }

    # Przechowaj dispatch w app
    if not hasattr(app, "_km_dispatch"):
        app._km_dispatch = {}
    app._km_dispatch.update(dispatch)

    # Patch _menu
    _patch_app_km(app, dispatch)

    c = L.C
    L.ok(f"KeyMapper zarejestrowany: {len(dispatch)} kluczy dispatch, "
         f"{len(_KM_REPAIR_ENTRIES)} sektory repair")
    print(f"  {c['h']}Nowe opcje:{c['r']} " +
          "  ".join(f"{c['c']}{k}{c['r']}" for k in list(_KM_MENU_KEYS)[:6]) +
          "  ...")


def _patch_app_km(app: Any, dispatch: Dict[str, Any]) -> None:
    """Opakowuje App._menu w obsługę kluczy km_*."""
    original_menu = getattr(app, "_menu", None)
    if not original_menu:
        return

    def patched_menu_km() -> None:
        import os
        c = L.C
        while True:
            os.system("clear")
            app._banner()
            _print_km_hint()

            try:
                ch = input(f"\n{c['c']}Choice (km_* / inne) > {c['r']}").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break

            if ch == "0":
                break

            # KeyMapper dispatch
            if ch in dispatch:
                try:
                    result = dispatch[ch]()
                    if result is False:
                        L.warn("  Operacja nieudana — sprawdź diagnostykę (km)")
                except Exception as e:
                    L.err(f"KeyMapper error [{ch}]: {e}")
                    import traceback; traceback.print_exc()
                try:
                    input(f"\n{c['c']}Enter aby kontynuować...{c['r']}")
                except (EOFError, KeyboardInterrupt):
                    pass
                continue

            # Deleguj do istniejących warstw
            for attr in ("_v159_dispatch", "_v158_dispatch"):
                ext = getattr(app, attr, {})
                if ch in ext:
                    try:
                        ext[ch]()
                    except Exception as e:
                        L.err(f"{attr} error [{ch}]: {e}")
                    try:
                        input(f"\n{c['c']}Enter...{c['r']}")
                    except (EOFError, KeyboardInterrupt):
                        pass
                    break
            else:
                if ch not in ("", "\n"):
                    L.info(f"  '{ch}' — przejdź do menu v157 dla tej opcji")
                    try:
                        input(f"\n{c['c']}Enter...{c['r']}")
                    except (EOFError, KeyboardInterrupt):
                        break

    app._menu_km = patched_menu_km


def _print_km_hint() -> None:
    c = L.C
    print(f"\n{c['h']}  🎮 KeyMapper:{c['r']} ", end="")
    for k, desc in list(_KM_MENU_KEYS.items())[:5]:
        print(f"{c['c']}{k}{c['r']} ", end="")
    print(f"  {c['d']}...{c['r']}")
    print(f"  {c['d']}Pełna lista: km  km_install  km_enable  km_export  km_keys  km_watch{c['r']}")


# ═══════════════════════════════════════════════════════════════════════════
# Standalone entrypoint
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="KeyMapper Module — standalone")
    parser.add_argument("--device",   default="192.168.1.3:5555")
    parser.add_argument("--install",  action="store_true")
    parser.add_argument("--enable",   action="store_true")
    parser.add_argument("--diag",     action="store_true")
    parser.add_argument("--export",   action="store_true")
    parser.add_argument("--keys",     action="store_true")
    parser.add_argument("--watch",    action="store_true")
    args = parser.parse_args()

    if not ADB.connect(args.device):
        print(f"[ERROR] Nie można połączyć: {args.device}")
        sys.exit(1)

    KeyMapperGuard.register()
    KeyMapperRepairSector.register()

    if args.install: KeyMapperInstaller.install(); sys.exit(0)
    if args.enable:  KeyMapperADB.enable_accessibility(); sys.exit(0)
    if args.export:  KeyMapperProfiles.export_all(); sys.exit(0)
    if args.keys:    KeyMapperDiag.show_keycodes(); sys.exit(0)
    if args.watch:   KeyMapperDiag.watch_events(10); sys.exit(0)

    # Domyślnie: diagnostyka
    KeyMapperDiag.full_report()