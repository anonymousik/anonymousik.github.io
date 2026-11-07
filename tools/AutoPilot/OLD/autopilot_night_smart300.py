# ════════════════════════════════════════════════════════════════════════════════
# SecFERRO_SmartTubeEnhancer_v9.5.1                                             #
# Module : SmartTube Remote Keymap + Phone Clipboard Bridge                     #
# Target : Sagemcom DCTIW362p | Android TV 9 | SmartTube v15+                  #
#                                                                                #
# TECHNICAL BASIS — SmartTube PlayerData preference schema:                     #
#   player_button_{action}       = str(keycode)   → short press                 #
#   player_button_{action}_long  = str(keycode)   → long press (≥800 ms)        #
#   Source: RemoteButtonsData.java, PlayerSettingsPresenter.java                 #
#   Backup path: /data/data/{PKG}/shared_prefs/{PKG}_preferences.xml            #
#                                                                                #
# REMOTE KEYCODES — Sagemcom DCTIW362p (Android TV standard):                  #
#   PAGE_UP         = 92   KEYCODE_PAGE_UP                                      #
#   PAGE_DOWN       = 93   KEYCODE_PAGE_DOWN                                    #
#   MIC             = 231  KEYCODE_VOICE_ASSIST                                 #
#   PLAY_PAUSE      = 85   KEYCODE_MEDIA_PLAY_PAUSE                             #
#   REC             = 130  KEYCODE_MEDIA_RECORD                                 #
#   PROGRAM         = 172  KEYCODE_GUIDE                                        #
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import ClassVar, Final

# Re-use existing SecFERRO infrastructure (single-file concat target)
# from secferro_core import SecFERRO_ShellExecutor, SecFERRO_TUI, ResultTriple


# ════════════════════════════════════════════════════════════════════════════════
# KEY BINDING DESCRIPTOR
# ════════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class KeyBinding:
    """
    Bidirectional SmartTube remote key descriptor.

    keycode     : Android KeyEvent keycode integer
    action      : SmartTube short-press action identifier
    long_action : SmartTube long-press action identifier (empty = disabled)
    description : human-readable summary for TUI diagnostics
    """
    keycode:     int
    action:      str
    long_action: str = ""
    description: str = ""


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE ACTION CATALOG
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeCatalog:
    """
    SmartTube v15+ player action identifiers and remote key bindings.

    Action IDs source: PlayerButtonData.java — SmartTube GitHub (yuliskov).
    Preference schema: player_button_{action} = str(keycode)
                       player_button_{action}_long = str(keycode)

    Existing bindings preserved:
      PAGE_UP (92)   short → like    (factory default)
      PAGE_DOWN (93) short → dislike (factory default)
    """

    PACKAGES: Final[tuple[str, ...]] = (
        "org.smarttube.stable",
        "org.smarttube.beta",
        "com.liskovsoft.smarttubetv.beta",
        "com.liskovsoft.smarttubetv.next",
    )

    # ── Action identifier literals (SmartTube PlayerButtonData enum values) ─
    ACT_LIKE              = "like"
    ACT_DISLIKE           = "dislike"
    ACT_ADD_TO_QUEUE      = "add_to_queue"
    ACT_REMOVE_QUEUE      = "remove_from_queue"
    ACT_OPEN_QUEUE        = "open_queue"
    ACT_OPEN_COMMENTS     = "open_comments"
    ACT_OPEN_WATCH_LATER  = "open_watch_later"
    ACT_SAVE_WATCH_LATER  = "save_to_watch_later"
    ACT_COPY_LINK         = "copy_link"
    ACT_COPY_LINK_TIME    = "copy_link_with_time"
    ACT_PLAY_PAUSE        = "play_pause"

    BINDINGS: Final[tuple[KeyBinding, ...]] = (
        # PAGE_UP (92): like (existing) / hold → add to queue (NEW)
        KeyBinding(
            92, ACT_LIKE, ACT_ADD_TO_QUEUE,
            "PAGE_UP  short=like          | hold=add to queue",
        ),
        # PAGE_DOWN (93): dislike (existing) / hold → remove from queue (NEW)
        KeyBinding(
            93, ACT_DISLIKE, ACT_REMOVE_QUEUE,
            "PAGE_DOWN short=dislike       | hold=remove from queue",
        ),
        # MIC (231): open comments section
        KeyBinding(
            231, ACT_OPEN_COMMENTS, "",
            "MIC      short=open comments",
        ),
        # PLAY_PAUSE (85): play/pause (existing) / hold → open playback queue
        KeyBinding(
            85, ACT_PLAY_PAUSE, ACT_OPEN_QUEUE,
            "PLAY_PAUSE short=play/pause   | hold=open queue",
        ),
        # REC (130): open Watch Later / hold → save to Watch Later
        KeyBinding(
            130, ACT_OPEN_WATCH_LATER, ACT_SAVE_WATCH_LATER,
            "REC      short=open Watch Later | hold=save to Watch Later",
        ),
        # PROGRAM/GUIDE (172): copy link / hold → copy link + timestamp
        KeyBinding(
            172, ACT_COPY_LINK, ACT_COPY_LINK_TIME,
            "PROGRAM  short=copy link      | hold=copy link+timestamp",
        ),
    )

    # Preference key template (SmartTube PlayerSettingsPresenter schema)
    PREF_KEY_SHORT : Final[str] = "player_button_{action}"
    PREF_KEY_LONG  : Final[str] = "player_button_{action}_long"

    # SmartTube preferences XML filename pattern
    PREF_FILENAME_TMPL: Final[str] = "{pkg}_preferences.xml"
    PREFS_DIR:          Final[str] = "/data/data/{pkg}/shared_prefs"
    FILES_DIR:          Final[str] = "/data/data/{pkg}/files"
    PLAYER_DATA_JSON:   Final[str] = "player_data.json"


# ════════════════════════════════════════════════════════════════════════════════
# SMARTTUBE KEY MAPPER
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeKeyMapper:
    """
    Injects SmartTube remote key bindings via shared_prefs XML and
    player_data.json (dual-format for SmartTube v14 compat and v15+ schema).

    Primary path  : /data/data/{pkg}/shared_prefs/{pkg}_preferences.xml
    Secondary path: /data/data/{pkg}/files/player_data.json
    Both require rish/root write access.
    """

    def __init__(self, sh: "SecFERRO_ShellExecutor") -> None:
        self._sh: Final["SecFERRO_ShellExecutor"] = sh
        self._pkg: str = ""

    # ── Package detection ──────────────────────────────────────────────────

    def _detect_pkg(self) -> str:
        for pkg in SmartTubeCatalog.PACKAGES:
            rc, _, _ = self._sh.run(f"pm list packages {pkg} 2>/dev/null")
            if rc == 0:
                return pkg
        return ""

    def _resolve_pkg(self) -> bool:
        if not self._pkg:
            self._pkg = self._detect_pkg()
        if not self._pkg:
            SecFERRO_TUI.error("SmartTube package not found")
            return False
        return True

    # ── XML preference manipulation ────────────────────────────────────────

    def _prefs_path(self) -> str:
        name = SmartTubeCatalog.PREF_FILENAME_TMPL.format(pkg=self._pkg)
        return f"{SmartTubeCatalog.PREFS_DIR.format(pkg=self._pkg)}/{name}"

    def _pull_prefs_xml(self, local: str) -> bool:
        _, out, _ = self._sh.run(
            f"cat '{self._prefs_path()}' 2>/dev/null"
        )
        if not out or "<map" not in out:
            return False
        with open(local, "w", encoding="utf-8") as f:
            f.write(out)
        return True

    def _build_new_entries(self) -> list[tuple[str, str]]:
        """Returns (pref_key, keycode_str) pairs for all bindings."""
        entries: list[tuple[str, str]] = []
        for b in SmartTubeCatalog.BINDINGS:
            kc = str(b.keycode)
            if b.action:
                key = SmartTubeCatalog.PREF_KEY_SHORT.format(action=b.action)
                entries.append((key, kc))
            if b.long_action:
                key = SmartTubeCatalog.PREF_KEY_LONG.format(action=b.long_action)
                entries.append((key, kc))
        return entries

    def _patch_xml_tree(self, tree: ET.ElementTree) -> int:
        root = tree.getroot()
        entries = self._build_new_entries()
        patched = 0
        for pref_key, kc_str in entries:
            existing = root.find(f"string[@name='{pref_key}']")
            if existing is not None:
                existing.text = kc_str
            else:
                elem = ET.SubElement(root, "string")
                elem.set("name", pref_key)
                elem.text = kc_str
            patched += 1
        return patched

    def _push_patched_xml(self, local: str) -> bool:
        with open(local, "r", encoding="utf-8") as f:
            content = f.read()
        escaped = content.replace("'", "'\\''")
        rc, _, _ = self._sh.run(
            f"echo '{escaped}' > '{self._prefs_path()}' 2>/dev/null"
        )
        return rc == 0

    # ── JSON player_data fallback ──────────────────────────────────────────

    def _json_path(self) -> str:
        return (f"{SmartTubeCatalog.FILES_DIR.format(pkg=self._pkg)}"
                f"/{SmartTubeCatalog.PLAYER_DATA_JSON}")

    def _patch_player_data_json(self) -> bool:
        _, raw, _ = self._sh.run(f"cat '{self._json_path()}' 2>/dev/null")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {}
        km = data.setdefault("keyMapping", {})
        for b in SmartTubeCatalog.BINDINGS:
            entry: dict[str, str] = {}
            if b.action:
                entry["action"] = b.action
            if b.long_action:
                entry["longAction"] = b.long_action
            km[str(b.keycode)] = entry
        payload = json.dumps(data, indent=2)
        escaped = payload.replace("'", "'\\''")
        rc, _, _ = self._sh.run(
            f"echo '{escaped}' > '{self._json_path()}' 2>/dev/null"
        )
        return rc == 0

    # ── Verification ───────────────────────────────────────────────────────

    def _verify_binding(self, b: KeyBinding) -> bool:
        """Confirms the short-press action pref was written."""
        key = SmartTubeCatalog.PREF_KEY_SHORT.format(action=b.action)
        _, out, _ = self._sh.run(
            f"grep -c 'name=\"{key}\"' '{self._prefs_path()}' 2>/dev/null"
        )
        return out.strip() == "1"

    # ── Main apply ─────────────────────────────────────────────────────────

    def apply(self) -> bool:
        SecFERRO_TUI.banner("SmartTube Key Mapper — Remote Control Enhancement")
        if not self._resolve_pkg():
            return False
        SecFERRO_TUI.row("package", self._pkg, True)

        # 1. Backup existing prefs
        backup_path = "/sdcard/smarttube_prefs_backup.xml"
        self._sh.run(f"cp '{self._prefs_path()}' '{backup_path}' 2>/dev/null")
        SecFERRO_TUI.row("backup saved", backup_path, True)

        # 2. Pull → patch XML → push
        local_tmp = "/data/local/tmp/st_prefs_patched.xml"
        xml_ok = False
        if self._pull_prefs_xml(local_tmp):
            try:
                tree = ET.parse(local_tmp)
                count = self._patch_xml_tree(tree)
                tree.write(local_tmp, encoding="unicode", xml_declaration=True)
                xml_ok = self._push_patched_xml(local_tmp)
                SecFERRO_TUI.row("XML prefs patched", f"{count} entries", xml_ok)
            except ET.ParseError as exc:
                SecFERRO_TUI.warn(f"XML parse error: {exc} → falling back to JSON")

        # 3. JSON fallback (player_data.json)
        json_ok = self._patch_player_data_json()
        SecFERRO_TUI.row("player_data.json", "patched", json_ok)

        # 4. Verify + print binding table
        SecFERRO_TUI.section("Key binding verification")
        for b in SmartTubeCatalog.BINDINGS:
            ok = self._verify_binding(b)
            SecFERRO_TUI.row(b.description, f"KC={b.keycode}", ok)

        # 5. Restart SmartTube to reload prefs
        self._sh.run(f"am force-stop {self._pkg}")
        time.sleep(1)
        SecFERRO_TUI.row("SmartTube restarted", "prefs reloaded", True)
        return xml_ok or json_ok


# ════════════════════════════════════════════════════════════════════════════════
# PHONE CLIPBOARD BRIDGE
# ════════════════════════════════════════════════════════════════════════════════

class PhoneClipboardBridge:
    """
    Extracts the current SmartTube video URL (± timestamp) and routes it to
    the user's phone clipboard via a priority-ordered transport chain:

      1. KDE Connect CLI  (kdeconnect-cli --share-text)
      2. ADB direct       (service call clipboard on paired phone ADB-WiFi)
      3. TV clipboard     (service call clipboard on TV — Android TV Remote app)

    URL extraction: dumpsys activity intent URI → videoId= pattern.
    Timestamp: dumpsys media_session playback position (seconds).
    """

    _YT_BASE:    Final[str] = "https://youtu.be/{video_id}"
    _YT_TS_TMPL: Final[str] = "https://youtu.be/{video_id}?t={seconds}"
    _VIDEO_RE:   Final[re.Pattern[str]] = re.compile(
        r"videoId=([a-zA-Z0-9_\-]{11})"
    )
    _TIME_RE:    Final[re.Pattern[str]] = re.compile(
        r"position=(\d+)"
    )

    def __init__(self, sh: "SecFERRO_ShellExecutor") -> None:
        self._sh: Final["SecFERRO_ShellExecutor"] = sh

    # ── URL extraction ─────────────────────────────────────────────────────

    def _extract_video_id(self) -> str:
        _, out, _ = self._sh.run(
            "dumpsys activity activities 2>/dev/null | grep -E 'videoId=' | head -3"
        )
        m = self._VIDEO_RE.search(out)
        if m:
            return m.group(1)
        # Fallback: window title / media session
        _, out2, _ = self._sh.run(
            "dumpsys media_session 2>/dev/null | grep -E 'videoId=' | head -1"
        )
        m2 = self._VIDEO_RE.search(out2)
        return m2.group(1) if m2 else ""

    def _extract_playback_secs(self) -> int:
        _, out, _ = self._sh.run(
            "dumpsys media_session 2>/dev/null | grep -E 'position=' | head -1"
        )
        m = self._TIME_RE.search(out)
        # MediaSession position is in milliseconds → convert to seconds
        return int(m.group(1)) // 1000 if m else 0

    def _build_url(self, with_timestamp: bool) -> str:
        vid = self._extract_video_id()
        if not vid:
            return ""
        if with_timestamp:
            secs = self._extract_playback_secs()
            return self._YT_TS_TMPL.format(video_id=vid, seconds=secs)
        return self._YT_BASE.format(video_id=vid)

    # ── Transport: KDE Connect ─────────────────────────────────────────────

    def _find_kdeconnect_device(self) -> str:
        """Returns first reachable KDE Connect device ID (phone)."""
        _, out, _ = self._sh.run(
            "kdeconnect-cli --list-devices --id-only 2>/dev/null | head -1"
        )
        return out.strip()

    def _send_via_kdeconnect(self, url: str) -> bool:
        dev_id = self._find_kdeconnect_device()
        if not dev_id:
            return False
        rc, _, _ = self._sh.run(
            f"kdeconnect-cli -d '{dev_id}' --share-text '{url}' 2>/dev/null"
        )
        return rc == 0

    # ── Transport: TV clipboard (Android TV Remote app readable) ───────────

    def _copy_to_tv_clipboard(self, url: str) -> bool:
        # Android 9 (API 28): service call clipboard 2 = setPrimaryClip
        rc, _, _ = self._sh.run(
            f"service call clipboard 2 i32 1 s16 'com.android.shell' "
            f"s16 '{url}' 2>/dev/null"
        )
        return rc == 0

    # ── Transport: ADB broadcast to paired phone ───────────────────────────

    def _send_via_adb_phone(self, url: str) -> bool:
        """
        Attempts clipboard injection on an ADB-paired phone at known LAN IPs.
        Requires ADB WiFi debugging enabled on the phone.
        """
        _, devices, _ = self._sh.run("adb devices 2>/dev/null")
        for line in devices.splitlines():
            if "\tdevice" not in line:
                continue
            serial = line.split("\t")[0].strip()
            # Skip the current TV device (ends in :5555 typically)
            if serial.endswith(":5555") or "192.168.1.3" in serial:
                continue
            rc, _, _ = self._sh.run(
                f"adb -s {serial} shell "
                f"\"service call clipboard 2 i32 1 s16 'shell' "
                f"s16 '{url}' 2>/dev/null\""
            )
            if rc == 0:
                SecFERRO_TUI.row("phone ADB target", serial, True)
                return True
        return False

    # ── Notification overlay fallback ─────────────────────────────────────

    def _show_url_overlay(self, url: str) -> None:
        """Shows URL as a long Toast on the TV screen as last-resort fallback."""
        self._sh.run(
            f"am start -a android.intent.action.VIEW "
            f"-d '{url}' "
            f"--activity-clear-task 2>/dev/null"
        )
        # Alternative: send a system notification
        self._sh.run(
            f"am broadcast -a 'android.intent.action.SEND' "
            f"--es android.intent.extra.TEXT '{url}' "
            f"--et android.intent.extra.SUBJECT 'SmartTube Link' 2>/dev/null"
        )

    # ── Main send ──────────────────────────────────────────────────────────

    def send(self, with_timestamp: bool = False) -> bool:
        SecFERRO_TUI.banner(
            "Phone Clipboard Bridge"
            + (" [+timestamp]" if with_timestamp else "")
        )
        url = self._build_url(with_timestamp)
        if not url:
            SecFERRO_TUI.error("Cannot extract current video ID from SmartTube")
            return False
        SecFERRO_TUI.row("URL", url, True)

        # Priority chain
        if self._send_via_kdeconnect(url):
            SecFERRO_TUI.row("transport", "KDE Connect", True)
            return True
        SecFERRO_TUI.warn("KDE Connect unavailable — trying ADB direct")

        if self._send_via_adb_phone(url):
            SecFERRO_TUI.row("transport", "ADB direct (phone)", True)
            return True
        SecFERRO_TUI.warn("ADB direct unavailable — fallback to TV clipboard")

        tv_ok = self._copy_to_tv_clipboard(url)
        SecFERRO_TUI.row("transport", "TV clipboard (use Remote app)", tv_ok)
        self._show_url_overlay(url)
        return tv_ok


# ════════════════════════════════════════════════════════════════════════════════
# KEYCODE PROBE — identifies actual keycodes sent by the Sagemcom remote
# ════════════════════════════════════════════════════════════════════════════════

class RemoteKeyProbe:
    """
    Captures raw KeyEvent keycodes from the Sagemcom DCTIW362p remote by
    reading the Android input event stream.  Run before mapping to verify
    that remote button → keycode assumptions are correct for this firmware.

    Usage:
        probe = RemoteKeyProbe(sh)
        probe.capture(duration_secs=15)
    """

    _INPUT_CMD: Final[str] = (
        "getevent -lt /dev/input/event0 2>/dev/null | "
        "grep -E 'EV_KEY' | head -20"
    )

    def __init__(self, sh: "SecFERRO_ShellExecutor") -> None:
        self._sh: Final["SecFERRO_ShellExecutor"] = sh

    def _discover_input_dev(self) -> str:
        """Returns the input device path for the IR/RC receiver."""
        _, out, _ = self._sh.run(
            "getevent -i 2>/dev/null | grep -B5 -E 'rc|remote|ir|key' "
            "| grep 'add device' | awk '{print $3}' | head -1"
        )
        return out.strip() or "/dev/input/event0"

    def capture(self, duration_secs: int = 10) -> dict[str, int]:
        """
        Reads key events for `duration_secs` seconds.
        Returns {button_name_hint: keycode} from observed events.
        """
        SecFERRO_TUI.banner("Remote Keycode Probe — Press buttons now")
        dev = self._discover_input_dev()
        SecFERRO_TUI.row("input device", dev, True)
        SecFERRO_TUI.warn(
            f"Press each remote button within {duration_secs}s: "
            "PAGE_UP, PAGE_DOWN, MIC, PLAY_PAUSE, REC, PROGRAM"
        )
        cmd = (
            f"timeout {duration_secs} getevent -lt {dev} 2>/dev/null "
            f"| grep EV_KEY"
        )
        _, raw, _ = self._sh.run(cmd)
        keycodes: dict[str, int] = {}
        kc_re = re.compile(r"KEY_(\w+)\s+(DOWN|UP)")
        for line in raw.splitlines():
            m = kc_re.search(line)
            if m and m.group(2) == "DOWN":
                key_name = m.group(1)
                # Resolve to integer via Android keycode table (limited subset)
                kc_int = self._resolve_keycode(key_name)
                if kc_int:
                    keycodes[key_name] = kc_int
                    SecFERRO_TUI.row(f"  captured KEY_{key_name}", str(kc_int), True)
        return keycodes

    def _resolve_keycode(self, linux_key_name: str) -> int:
        """Maps Linux input key names to Android KEYCODE integers."""
        mapping: dict[str, int] = {
            "CHANNELUP":    92,   # KEYCODE_PAGE_UP
            "CHANNELDOWN":  93,   # KEYCODE_PAGE_DOWN
            "PAGEUP":       92,
            "PAGEDOWN":     93,
            "MICMUTE":      231,  # KEYCODE_VOICE_ASSIST
            "SEARCH":       84,
            "PLAYPAUSE":    85,   # KEYCODE_MEDIA_PLAY_PAUSE
            "RECORD":       130,  # KEYCODE_MEDIA_RECORD
            "EPG":          172,  # KEYCODE_GUIDE
            "PROGRAM":      172,
            "TV":           172,
        }
        return mapping.get(linux_key_name.upper(), 0)


# ════════════════════════════════════════════════════════════════════════════════
# INTEGRATION — SmartTubeEnhancer facade (PerformanceTuner extension point)
# ════════════════════════════════════════════════════════════════════════════════

class SmartTubeEnhancer:
    """
    Facade integrating SmartTubeKeyMapper + PhoneClipboardBridge into the
    SecFERRO PerformanceTuner pipeline.

    Integration in PerformanceTuner:
        def _apply_smarttube_enhancement(self) -> None:
            SmartTubeEnhancer(self._sh).apply_all()
    """

    def __init__(self, sh: "SecFERRO_ShellExecutor") -> None:
        self._sh:       Final["SecFERRO_ShellExecutor"] = sh
        self._mapper:   Final[SmartTubeKeyMapper]       = SmartTubeKeyMapper(sh)
        self._clipboard: Final[PhoneClipboardBridge]    = PhoneClipboardBridge(sh)
        self._probe:    Final[RemoteKeyProbe]           = RemoteKeyProbe(sh)

    def apply_keymaps(self) -> bool:
        return self._mapper.apply()

    def probe_remote(self, duration: int = 10) -> dict[str, int]:
        return self._probe.capture(duration_secs=duration)

    def share_url(self, with_timestamp: bool = False) -> bool:
        return self._clipboard.send(with_timestamp=with_timestamp)

    def print_keybinding_reference(self) -> None:
        SecFERRO_TUI.banner("SmartTube Remote Key Reference — Sagemcom DCTIW362p")
        rows: tuple[tuple[str, str, str], ...] = (
            ("PAGE_UP (KC 92)",   "short",  "👍 Like"),
            ("PAGE_UP (KC 92)",   "hold",   "➕ Add to Queue"),
            ("PAGE_DOWN (KC 93)", "short",  "👎 Dislike"),
            ("PAGE_DOWN (KC 93)", "hold",   "➖ Remove from Queue"),
            ("MIC (KC 231)",      "short",  "💬 Open Comments"),
            ("PLAY_PAUSE (KC 85)","short",  "⏯  Play / Pause"),
            ("PLAY_PAUSE (KC 85)","hold",   "📋 Open Playback Queue"),
            ("REC (KC 130)",      "short",  "📁 Open Watch Later"),
            ("REC (KC 130)",      "hold",   "🔖 Save to Watch Later"),
            ("PROGRAM (KC 172)",  "short",  "🔗 Copy Link"),
            ("PROGRAM (KC 172)",  "hold",   "🔗+⏱ Copy Link + Timestamp"),
        )
        for button, press_type, action in rows:
            SecFERRO_TUI.row(f"{button:<22} [{press_type:<5}]", action, None)

    def apply_all(self) -> None:
        SecFERRO_TUI.banner("SmartTube Enhancer — Full Apply")
        self.print_keybinding_reference()
        km_ok = self.apply_keymaps()
        SecFERRO_TUI.row("key mapping applied", str(km_ok), km_ok)
        SecFERRO_TUI.section("Phone Clipboard Bridge — KDE Connect availability")
        dev = self._clipboard._find_kdeconnect_device()
        SecFERRO_TUI.row("KDE Connect device", dev or "not found", bool(dev))
        if not dev:
            SecFERRO_TUI.warn(
                "Install KDE Connect on phone + TV for full clipboard sharing. "
                "Fallback: TV clipboard + Android TV Remote app."
            )


# ════════════════════════════════════════════════════════════════════════════════
# INTEGRATION PATCH for PerformanceTuner (add to existing class body)
# ════════════════════════════════════════════════════════════════════════════════

# Patch _apply_smarttube_enhancement into PerformanceTuner:
#
# def _apply_smarttube_enhancement(self) -> None:
#     SecFERRO_TUI.banner("SmartTube Remote Enhancement — v9.5.1")
#     enhancer = SmartTubeEnhancer(self._sh)
#     enhancer.apply_all()
#
# And in run_full_optimization(), add:
#     self._apply_smarttube_enhancement()
#
# And in dispatch dict (main()):
#     "--smarttube":    tuner._apply_smarttube_enhancement,
#     "--probe-remote": lambda: SmartTubeEnhancer(tuner._sh).probe_remote(15),
#     "--share-url":    lambda: SmartTubeEnhancer(tuner._sh).share_url(False),
#     "--share-url-ts": lambda: SmartTubeEnhancer(tuner._sh).share_url(True),