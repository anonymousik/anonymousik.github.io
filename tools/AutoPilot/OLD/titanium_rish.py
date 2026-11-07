#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  PLAYBOX TITANIUM BRAIN v17.1 — Intelligent Master Controller               ║
║  Target : Sagemcom DCTIW362P | BCM72604 | Android TV 9 | API 28            ║
║  Author : anonymousik / FerroART                                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  FIXES W v17.1:                                                              ║
║  [C] ShizukuOrchestrator — Wdrożono Heurystyczny Smart-Wrapper dla rish    ║
║      (Naprawia ignorowanie argumentów po -c, np. rish -c uname -a działa)  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import argparse, asyncio, hashlib, json, os, re, statistics, subprocess, sys, threading, time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

VERSION     = "17.1"
CACHE_DIR   = Path.home() / ".playbox_cache" / "brain_v17"
LOG_FILE    = CACHE_DIR / "brain.log"
JOURNAL_F   = CACHE_DIR / "journal.json"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_C = {
    "s": "\033[92m", "w": "\033[93m", "e": "\033[91m",
    "i": "\033[94m", "h": "\033[95m", "c": "\033[96m",
    "d": "\033[2m",  "b": "\033[1m",  "r": "\033[0m",
}
def C(k: str) -> str: return _C.get(k, "")

class HW:
    SOC             = "BCM72604"
    CPU_CORES       = 2
    ISA_FEATURES    = "default,idiv"
    RAM_TOTAL_MB    = 1425
    PKG_SMARTTUBE   = "org.smarttube.stable"
    PKG_SHIZUKU     = "moe.shizuku.privileged.api"
    RISH_DEX        = "/data/local/tmp/rish_shizuku.dex"
    RISH_BIN        = "/data/local/tmp/rish"
    SHIZUKU_START   = f"/data/user/0/{PKG_SHIZUKU}/start.sh"
    ADB_PORT        = 5555

class L:
    _buf: List[str] = []
    _lock = threading.Lock()

    @classmethod
    def _w(cls, msg: str, lvl: str) -> None:
        ts   = time.strftime("%H:%M:%S")
        line = f"[{ts}][{lvl}] {msg}"
        print(f"{_C.get(lvl,'')}{line}{_C['r']}")
        with cls._lock:
            cls._buf.append(line)

    @classmethod
    def ok(cls, m: str)   -> None: cls._w(f"[OK]  {m}", "s")
    @classmethod
    def info(cls, m: str) -> None: cls._w(f"[..] {m}", "i")
    @classmethod
    def warn(cls, m: str) -> None: cls._w(f"[!!] {m}", "w")
    @classmethod
    def err(cls, m: str)  -> None: cls._w(f"[XX] {m}", "e")
    @classmethod
    def fix(cls, m: str)  -> None: cls._w(f"[>>] {m}", "w")
    @classmethod
    def dim(cls, m: str)  -> None: cls._w(f"     {m}", "d")
    @classmethod
    def hdr(cls, m: str)  -> None:
        sep = "=" * 68
        print(f"\n{_C['h']}{_C['b']}{sep}\n  {m}\n{sep}{_C['r']}\n")
    @classmethod
    def row(cls, label: str, val: str, w: int = 28) -> None:
        print(f"  {_C['i']}{label:<{w}}{_C['r']} {val}")

class ADB:
    dev:  Optional[str] = None
    rish: bool          = False
    _TO = 35
    _RETRY = 2

    @classmethod
    def connect(cls, target: str) -> bool:
        try:
            r = subprocess.run(["adb", "connect", target], capture_output=True, text=True, timeout=12)
            if "connected" in r.stdout.lower():
                cls.dev = target
                return True
            return False
        except Exception:
            return False

    @classmethod
    def sh(cls, cmd: str, silent: bool = False, timeout: int = 0) -> str:
        if not cls.dev: return ""
        try:
            return subprocess.check_output(
                ["adb", "-s", cls.dev, "shell", cmd], stderr=subprocess.STDOUT, text=True, timeout=timeout or cls._TO
            ).strip()
        except Exception as e:
            return ""

    @classmethod
    def root(cls, cmd: str) -> str:
        for prefix in (f"su -c \"{cmd}\"", f"{HW.RISH_BIN} -c \"{cmd}\""):
            r = cls.sh(prefix, silent=True)
            if r and "not found" not in r and "permission denied" not in r.lower():
                return r
        return cls.sh(cmd)

    @classmethod
    def batch(cls, cmds: List[str]) -> str:
        return cls.sh("; ".join(f"({c})" for c in cmds), silent=True)

@dataclass
class ShizukuStatus:
    installed:    bool  = False
    server_pid:   str   = ""
    dex_present:  bool  = False
    rish_built:   bool  = False
    rish_tested:  bool  = False
    permissions:  List[str] = field(default_factory=list)

class ShizukuOrchestrator:
    @classmethod
    def status(cls) -> ShizukuStatus:
        st = ShizukuStatus()
        batch = ADB.batch([
            f"pm list packages 2>/dev/null | grep -c {HW.PKG_SHIZUKU}",
            "pidof shizuku_server 2>/dev/null",
            f"test -f {HW.RISH_DEX} && echo YES || echo NO",
            f"test -x {HW.RISH_BIN} && echo YES || echo NO",
            f"{HW.RISH_BIN} -c 'echo RISH_OK' 2>/dev/null",
        ])
        lines = [l.strip() for l in batch.splitlines()]
        def _l(i): return lines[i] if i < len(lines) else ""

        st.installed   = _l(0) == "1"
        st.server_pid  = _l(1)
        st.dex_present = _l(2) == "YES"
        st.rish_built  = _l(3) == "YES"
        st.rish_tested = "RISH_OK" in _l(4)

        if st.rish_tested: ADB.rish = True
        return st

    @classmethod
    def ensure_dex(cls) -> bool:
        if ADB.sh(f"test -f {HW.RISH_DEX} && echo OK", silent=True).strip() == "OK": return True
        src = f"/data/user/0/{HW.PKG_SHIZUKU}/files/rish_shizuku.dex"
        if "OK" in (ADB.root(f"test -f '{src}' && cp '{src}' {HW.RISH_DEX} && chmod 644 {HW.RISH_DEX} && echo OK") or ""): return True
        apk = ADB.sh(f"pm path {HW.PKG_SHIZUKU} 2>/dev/null | cut -d: -f2", silent=True).strip()
        if apk and "OK" in (ADB.root(f"unzip -p '{apk}' assets/rish_shizuku.dex > {HW.RISH_DEX} 2>/dev/null && echo OK") or ""): return True
        return False

    @classmethod
    def build_rish(cls) -> bool:
        # === HEURYSTYCZNY SMART WRAPPER DLA RISH ===
        # Rozwiązuje problem połykania argumentów (np. rish -c uname -a)
        rish_content = (
            "#!/system/bin/sh\\n"
            f"BASEDIR=/data/local/tmp\\n"
            "DEX=$BASEDIR/rish_shizuku.dex\\n"
            "[ ! -f \"$DEX\" ] && echo \"ERROR: $DEX missing\" && exit 1\\n"
            "[ -z \"$RISH_APPLICATION_ID\" ] && export RISH_APPLICATION_ID=com.termux\\n"
            "if [ \"$1\" = \"-c\" ]; then\\n"
            "  shift\\n"
            "  CMD=\"$*\"\\n"
            "  exec /system/bin/app_process -Djava.class.path=\"$DEX\" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader -c \"$CMD\"\\n"
            "else\\n"
            "  exec /system/bin/app_process -Djava.class.path=\"$DEX\" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader \"$@\"\\n"
            "fi\\n"
        )
        out = ADB.sh(f"printf '{rish_content}' > {HW.RISH_BIN} && chmod 755 {HW.RISH_BIN} && echo BUILT", silent=True)
        if "BUILT" in (out or ""):
            L.ok(f"  rish Smart-Wrapper built: {HW.RISH_BIN}")
            return True
        return False

    @classmethod
    def start_server(cls) -> str:
        pid = ADB.sh("pidof shizuku_server 2>/dev/null", silent=True).strip()
        if pid: return pid
        if "OK" in (ADB.root(f"test -f '{HW.SHIZUKU_START}' && echo OK") or ""):
            ADB.root(f"sh '{HW.SHIZUKU_START}' &")
            time.sleep(2.5)
            pid = ADB.sh("pidof shizuku_server 2>/dev/null", silent=True).strip()
            if pid: return pid
        if ADB.sh(f"test -f {HW.RISH_DEX} && echo OK", silent=True).strip() == "OK":
            cmd = f"CLASSPATH={HW.RISH_DEX} /system/bin/app_process -Djava.class.path={HW.RISH_DEX} /system/bin --nice-name=shizuku_server rikka.shizuku.server.ShizukuServiceServer &"
            ADB.root(cmd)
            time.sleep(3)
            return ADB.sh("pidof shizuku_server 2>/dev/null", silent=True).strip()
        return ""

    @classmethod
    def full_setup(cls) -> ShizukuStatus:
        L.hdr("SHIZUKU ORCHESTRATOR v17.1 (SMART WRAPPER)")
        st = cls.status()
        if not st.installed: return st
        if not st.dex_present: st.dex_present = cls.ensure_dex()
        if st.dex_present: st.rish_built = cls.build_rish() # Zawsze odbudowujemy dla pewności że mamy Smart Wrappera
        if not st.server_pid: st.server_pid = cls.start_server()
        if st.rish_built and st.server_pid:
            test = ADB.sh(f"{HW.RISH_BIN} -c 'uname -a' 2>/dev/null", silent=True)
            if "Linux" in test:
                st.rish_tested = True
                ADB.rish = True
                L.ok(f"  rish operational ✓ Heuristic fix active. Response: {test[:30]}...")
            else:
                L.warn("  rish test failed")
        return st

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--device":
        device = sys.argv[2]
        if ":" not in device: device += ":5555"
        if ADB.connect(device):
            ShizukuOrchestrator.full_setup()
    else:
        print("Usage: python titanium_brain.py --device IP")

