"""
src/arena_mod_client.py
Client for the optional Arena Pack Overlay Mod (BepInEx companion, see
bepinex_mod/). When installed, the mod reads the current draft pack's
slot-index -> Arena card ID (grpId) mapping directly out of the game's own
data (Wotc.Mtga.Wrapper.Draft.DraftPackHolder.LayoutCards) and writes it to
a JSON file in the OS temp directory on every pack layout - a more reliable
alternative to guessing from the draft log's arbitrary card order or
screen-scraping via OCR.

A loopback TCP socket was tried first and rejected: the mod's listener
reported itself successfully bound, but never appeared in the OS's own
connection table for Arena's process (verified via PowerShell
Get-NetTCPConnection against the real PID), and no firewall rule fixed it -
likely some sandboxing/security layer around Arena's process. A file has no
such surface: same OS temp directory, same Windows user account, ordinary
file I/O on both sides.
"""

import json
import os
import tempfile
import threading
import time
from typing import Dict, Optional

from src.logger import create_logger

logger = create_logger()

DATA_DIR = os.path.join(tempfile.gettempdir(), "ArenaPackOverlayMod")
DATA_FILE = os.path.join(DATA_DIR, "pack_layout.json")
SCORES_FILE = os.path.join(DATA_DIR, "scores.json")

# How often to poll the file for changes. Matches the Arena overlay's own
# poll cadence (ArenaOverlay.POLL_INTERVAL_MS) rather than the mod's own
# write frequency, since we only care about picking up the latest state
# whenever the overlay itself next checks.
POLL_INTERVAL_SEC = 0.25

# If the file hasn't been updated in this long, treat the mod as not
# running (crashed, Arena closed, mod uninstalled) rather than trusting
# stale data - mirrors the dynamic-availability reasoning in the project
# plan: unlike OCR's static is_ocr_available() cache, the mod's presence
# can change at any point during a session.
STALE_AFTER_SEC = 5.0


class ArenaModClient:
    """Polls the mod's pack-layout file in a background thread.

    is_connected() reflects whether a *fresh* (non-stale) file was found on
    the last poll, not just whether the file exists - a leftover file from
    a previous Arena session must not be mistaken for a live connection.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._latest_slots: Dict[int, int] = {}
        self._last_fresh_at: Optional[float] = None
        self._last_mtime: Optional[float] = None
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def is_connected(self) -> bool:
        with self._lock:
            if self._last_fresh_at is None:
                return False
            return (time.monotonic() - self._last_fresh_at) < STALE_AFTER_SEC

    def latest_slots(self) -> Dict[int, int]:
        """Returns the most recently read slot index -> grpId mapping."""
        with self._lock:
            return dict(self._latest_slots)

    def write_scores(self, scores: Dict[int, dict]) -> None:
        """Writes {grpId: {"value": int, "gihwr": float}} for the mod to
        pick up on its next pack layout. Atomic (write to a temp file, then
        rename) so the mod never reads a half-written file mid-poll."""
        payload = {str(grp_id): data for grp_id, data in scores.items()}
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp_path = SCORES_FILE + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp_path, SCORES_FILE)
        except OSError as e:
            logger.warning("Failed to write Arena mod scores file: %s", e)

    def stop(self):
        self._stop = True

    def _run(self):
        while not self._stop:
            self._poll_once()
            time.sleep(POLL_INTERVAL_SEC)

    def _poll_once(self):
        try:
            mtime = os.path.getmtime(DATA_FILE)
        except OSError:
            return  # file doesn't exist yet - mod not installed/running

        with self._lock:
            already_seen = mtime == self._last_mtime
        if already_seen:
            with self._lock:
                self._last_fresh_at = time.monotonic()
            return

        try:
            # utf-8-sig: .NET's File.WriteAllText(..., Encoding.UTF8) writes
            # a BOM by default, which plain utf-8 decoding leaves in the
            # string and breaks json.loads on the first byte.
            with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
                payload = json.load(f)
        except (OSError, ValueError):
            # Torn read (mid-write on the mod's side) - try again next poll.
            return

        slots = payload.get("slots")
        if not isinstance(slots, list):
            return

        parsed = {}
        for entry in slots:
            try:
                parsed[int(entry["index"])] = int(entry["grp_id"])
            except (KeyError, TypeError, ValueError):
                continue

        with self._lock:
            self._latest_slots = parsed
            self._last_mtime = mtime
            self._last_fresh_at = time.monotonic()
        logger.debug("Arena mod pack layout: %s", parsed)
