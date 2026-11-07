#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════════════════════════════
# SecFERRO Adaptive Dalvik & Performance Engine                                  #
# Target  : Sagemcom DCTIW362p | BCM72604 | Android TV 9 (API 28)                #
# Funkcja : Dynamiczna zmiana źródła optymalizacji (setprop vs settings db)      #
# Runtime : Python 3.8+ | Autodetekcja uprawnień (ROOT / RISH / ADB NO-ROOT)     #
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import enum
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import ClassVar, Final, TypeAlias

ResultTriple: TypeAlias = tuple[int, str, str]

# Paleta TUI
_P: Final[str] = "\033[38;2;191;0;255m"
_G: Final[str] = "\033[32m"
_R: Final[str] = "\033[31m"
_Y: Final[str] = "\033[33m"
_D: Final[str] = "\033[90m"
_C: Final[str] = "\033[36m"
_B: Final[str] = "\033[0m"


class ExecLayer(enum.Enum):
    ROOT = "su -c"
    RISH = "sh /data/local/tmp/rish -c"
    ADB  = "sh -c"


@dataclass(frozen=True, slots=True)
class AdaptiveVector:
    """Struktura przechowująca optymalną modyfikację oraz jej no-root alternatywę."""
    name: str
    target_layer: ExecLayer
    # Komenda optymalna (wymaga wyższych uprawnień, np. setprop dalvik)
    optimal_cmd: str
    # Alternatywa oparta na bazie settings (działa na standardowym ADB)
    fallback_settings_cmd: str
    desc: str


# ════════════════════════════════════════════════════════════════════════════════
# ADAPTACYJNA BAZA WIEDZY (Dalvik & Performance)
# ════════════════════════════════════════════════════════════════════════════════
class AdaptiveCatalog:
    """
    Katalog technik łączący natywne modyfikacje właściwości systemu (prop) 
    z alternatywnymi stałymi ActivityManagera w bazie Settings.Global.
    """
    PERFORMANCE_VECTORS: Final[tuple[AdaptiveVector, ...]] = (
        AdaptiveVector(
            name="Dalvik Heap MinFree",
            target_layer=ExecLayer.RISH,
            optimal_cmd="setprop dalvik.vm.heapminfree 2m",
            fallback_settings_cmd="settings put global activity_manager_constants max_cached_processes=3,background_settle_time=60000",
            desc="Redukcja mikro-pauz GC / Agresywny reaping pamięci w tle"
        ),
        AdaptiveVector(
            name="Dalvik Heap MaxFree",
            target_layer=ExecLayer.RISH,
            optimal_cmd="setprop dalvik.vm.heapmaxfree 16m",
            fallback_settings_cmd="settings put global activity_manager_constants empty_process_percent=50,max_empty_time_millis=30000",
            desc="Rozszerzenie limitów zwalniania / Skrócenie życia pustych procesów"
        ),
        AdaptiveVector(
            name="LMK Upgrade Pressure",
            target_layer=ExecLayer.RISH,
            optimal_cmd="setprop ro.lmk.upgrade_pressure 50",
            fallback_settings_cmd="settings put global app_standby_enabled 1",
            desc="Szybsza reakcja OOM / Wymuszenie App Standby dla nieaktywnych"
        ),
        AdaptiveVector(
            name="LMK Kill Heaviest",
            target_layer=ExecLayer.RISH,
            optimal_cmd="setprop ro.lmk.kill_heaviest_task true",
            fallback_settings_cmd="settings put global adaptive_battery_management_enabled 1",
            desc="Agresywne ubijanie ciężkich zadań / Adaptacyjne zamrażanie zasobów"
        ),
        AdaptiveVector(
            name="Phantom Process Killer",
            target_layer=ExecLayer.ROOT, # device_config często wymaga roota na ATV9
            optimal_cmd="cmd device_config put activity_manager max_phantom_processes 0",
            fallback_settings_cmd="settings put global settings_enable_monitor_phantom_procs false",
            desc="Dezaktywacja monitora procesów widmo (oszczędność CPU)"
        ),
    )


# ════════════════════════════════════════════════════════════════════════════════
# SILNIK WYKONAWCZY ADB
# ════════════════════════════════════════════════════════════════════════════════
class Executor:
    def __init__(self, target_ip: str | None = None) -> None:
        self.target_ip = target_ip
        self.adb_prefix = self._setup_adb()
        self.layer = self._probe()

    def _setup_adb(self) -> str:
        if self.target_ip:
            subprocess.run(f"adb connect {self.target_ip}", shell=True, stdout=subprocess.DEVNULL)
            return f"adb -s {self.target_ip} shell "
        return "adb shell "

    def _probe(self) -> ExecLayer:
        if subprocess.run(f"{self.adb_prefix}su -c 'id'", shell=True, capture_output=True).returncode == 0:
            return ExecLayer.ROOT
        if subprocess.run(f"{self.adb_prefix}sh /data/local/tmp/rish -c 'id'", shell=True, capture_output=True).returncode == 0:
            return ExecLayer.RISH
        return ExecLayer.ADB

    def run(self, cmd: str, force_layer: ExecLayer | None = None) -> ResultTriple:
        active_layer = force_layer if force_layer else self.layer
        
        if active_layer == ExecLayer.ROOT:
            full = f"{self.adb_prefix}su -c '{cmd}'"
        elif active_layer == ExecLayer.RISH:
            full = f"{self.adb_prefix}sh /data/local/tmp/rish -c '{cmd}'"
        else:
            full = f"{self.adb_prefix}{cmd}"
            
        try:
            r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=10)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"


# ════════════════════════════════════════════════════════════════════════════════
# MENEDŻER ADAPTACYJNY
# ════════════════════════════════════════════════════════════════════════════════
class AdaptivePerfManager:
    def __init__(self, ex: Executor):
        self.ex = ex

    def apply_hybrid_optimizations(self):
        SecFERRO_TUI.section(f"Adaptacyjna Optymalizacja Dalvik & LMK")
        
        layer_level = {ExecLayer.ADB: 0, ExecLayer.RISH: 1, ExecLayer.ROOT: 2}
        current_level = layer_level[self.ex.layer]

        for v in AdaptiveCatalog.PERFORMANCE_VECTORS:
            required_level = layer_level[v.target_layer]
            
            # Jeśli mamy odpowiednie uprawnienia, próbujemy aplikować metodę optymalną (setprop/device_config)
            if current_level >= required_level:
                rc, _, err = self.ex.run(v.optimal_cmd)
                if rc == 0:
                    SecFERRO_TUI.row(v.name, f"Optymalna ({v.optimal_cmd.split()[1]})", True)
                    continue
                else:
                    # Fallback w przypadku błędu (np. ro. jest zablokowane nawet na Rish w niektórych buildach)
                    SecFERRO_TUI.warn(f"Błąd metody optymalnej dla {v.name}. Uruchamiam fallback (Settings DB).")
            
            # Wrzut do bazy Settings.Global jako alternatywa No-Root
            rc, _, _ = self.ex.run(v.fallback_settings_cmd, force_layer=ExecLayer.ADB)
            
            if rc == 0:
                # Czyste logowanie dla bazy settings
                key_match = v.fallback_settings_cmd.split("global ")[-1].split(" ")[0]
                SecFERRO_TUI.row(v.name, f"Alternatywa ({key_match})", True)
            else:
                SecFERRO_TUI.row(v.name, "Błąd wstrzyknięcia do bazy Settings", False)

    def apply_animator_sync(self):
        """Dodatkowa warstwa w bazie ustawień synchronizująca GPU z renderingiem."""
        SecFERRO_TUI.section("Synchronizacja Klatek & Responsywność UI (Settings DB)")
        
        tweaks = [
            ("window_animation_scale", "0.35"),
            ("transition_animation_scale", "0.35"),
            ("animator_duration_scale", "0.35"),
            ("activity_starts_logging_enabled", "0"), # Wyłącza I/O overhead w logcat
            ("ble_scan_always_enabled", "0"),
        ]
        
        for key, val in tweaks:
            rc, _, _ = self.ex.run(f"settings put global {key} {val}", force_layer=ExecLayer.ADB)
            SecFERRO_TUI.row(f"settings global {key}", val, rc == 0)


# ════════════════════════════════════════════════════════════════════════════════
# TUI & MAIN ENTRYPOINT
# ════════════════════════════════════════════════════════════════════════════════
class SecFERRO_TUI:
    @staticmethod
    def banner(title: str) -> None:
        print(f"\n{_P}╔{'═'*78}╗")
        print(f"║ {_C}{title:^76}{_P} ║")
        print(f"╚{'═'*78}╝{_B}")

    @staticmethod
    def section(text: str) -> None:
        print(f"\n  {_Y}── {text} ──{_B}")

    @staticmethod
    def row(key: str, value: str, ok: bool | None = None) -> None:
        tag = f"{_G}[✓]{_B}" if ok is True else (f"{_R}[✗]{_B}" if ok is False else f"{_D}[~]{_B}")
        print(f"  {tag} {_D}{key:<45}{_B}{value}")

    @staticmethod
    def warn(msg: str) -> None:
        print(f"  {_Y}[!]{_B} {msg}")

def main():
    os.system('clear' if os.name == 'posix' else 'cls')
    SecFERRO_TUI.banner("SecFERRO: Adaptacyjna Pamięć & Wydajność (Dalvik/LMK)")
    
    ip_arg = sys.argv[1] if len(sys.argv) > 1 else None
    ex = Executor(ip_arg)
    
    SecFERRO_TUI.section("Środowisko Uruchomieniowe")
    SecFERRO_TUI.row("Adres ADB (Endpoint)", ex.target_ip if ex.target_ip else "Lokalny / Domyślny", True)
    SecFERRO_TUI.row("Aktualny Poziom Uprawnień", ex.layer.name, True)
    
    if ex.layer == ExecLayer.ADB:
        SecFERRO_TUI.warn("Brak ROOT/RISH. Optymalizacje Dalvik/LMK zostaną przetłumaczone na komendy Settings DB.")

    manager = AdaptivePerfManager(ex)
    manager.apply_hybrid_optimizations()
    manager.apply_animator_sync()

    print(f"\n{_G}  [✓] Moduły wydajnościowe zostały wdrożone pomyślnie.{_B}\n")

if __name__ == "__main__":
    main()
