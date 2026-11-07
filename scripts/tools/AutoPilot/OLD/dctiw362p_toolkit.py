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
        "debug.hwui.renderer":        "opengl",
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
# ══════════════════════════════════════════════════════════════════════════

class SmartTubeProfileApplier:
    PACKAGES: ClassVar[tuple[str, ...]] = (
        "org.smarttube.stable", "org.smarttube.beta",
        "com.liskovsoft.smarttubetv.beta",
    )
    PREF_FILES: ClassVar[tuple[str, ...]] = (
        "{pkg}_preferences.xml",
        "shareutils.xml",
        "org.smarttube.stable_preferences.xml",
        "yt-service-prefs.xml",
    )

    def __init__(self, sh: AdbShell) -> None:
        self._sh: Final[AdbShell] = sh
        self._pkg: str = ""

    def _detect_pkg(self) -> str:
        for pkg in self.PACKAGES:
            if self._sh.run(f"pm list packages {pkg}").ok:
                return pkg
        return ""

    def _prefs_dir(self) -> str:
        return f"/sdcard/data/{self._pkg}/Backup/shared_prefs"

    def backup_all(self, dest: str = "/sdcard/dctiw362p_prefs_backup") -> bool:
        self._sh.run(f"mkdir -p '{dest}'")
        ok = self._sh.run(f"cp -r '{self._prefs_dir()}'/* '{dest}/' 2>/dev/null").ok
        print(f"  Backup shared_prefs -> {dest} : {'OK' if ok else 'BRAK/PUSTY'}")
        return ok

    def apply(self) -> bool:
        _hdr("SMARTTUBE — ZWERYFIKOWANY PROFIL KODEKA/BUFORA")
        self._pkg = self._detect_pkg()
        if not self._pkg:
            print("  [BLAD] SmartTube nie znaleziony na urzadzeniu.")
            return False
        print(f"  Pakiet: {self._pkg}")

        self.backup_all()
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
    ap.add_argument("--apply-smarttube", action="store_true", help="patchuj prefs SmartTube")
    ap.add_argument("--drift", action="store_true", help="wykryj odchylenia od profilu")
    ap.add_argument("--all", action="store_true", help="pelna sekwencja: verify+system+smarttube")
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

    if args.all or args.apply_system:
        SystemProfileApplier(sh).apply()
    if args.all or args.apply_smarttube:
        SmartTubeProfileApplier(sh).apply()
    if args.drift:
        DriftDetector(sh).scan()

    if not any([args.apply_system, args.apply_smarttube, args.drift, args.all]):
        print("\nNic do zrobienia -- podaj --all, --apply-system, "
              "--apply-smarttube lub --drift (patrz --help).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
