"""
src/ui/windows/arena_overlay.py
Transparent overlay window kept in sync with the MTG Arena game window.
"""

import sys

import ttkbootstrap as tb

from src import constants
from src.arena_window import ArenaWindowTracker
from src.overlay_layout import slot_rect_for_index
from src.logger import create_logger

logger = create_logger()

POLL_INTERVAL_MS = 250


def _get_win32_extended_style_api():
    """Lazily imports win32gui/win32con, returning None on non-Windows platforms."""
    if sys.platform != "win32":
        return None
    import win32con
    import win32gui

    return win32gui, win32con


class ArenaOverlay(tb.Toplevel):
    """A borderless, always-on-top, click-through window tracking Arena's screen rect.

    Hides itself whenever Arena can't be found or is minimized. Click-through
    is real OS-level pass-through (WS_EX_TRANSPARENT), not just a Tk affordance,
    so clicks always reach the Arena window underneath.
    """

    def __init__(self, parent, tracker=None):
        super().__init__(title="Arena Overlay", topmost=True)
        self.parent = parent
        self.tracker = tracker or ArenaWindowTracker()
        self._poll_job = None

        self.overrideredirect(True)
        try:
            self.attributes("-alpha", 0.85)
        except Exception:
            pass

        self.slot_data = []

        self.withdraw()
        self.update_idletasks()
        self._enable_click_through()
        self._sync_position()

    def update_data(self, pack_cards, recommendations):
        """Maps the current pack's cards to their on-screen slot rects.

        Stores a list of {"card", "slot", "recommendation"} entries for the
        renderer to consume; rendering itself is added in a later task.
        """
        rect = self.tracker.get_rect()
        if rect is None or not pack_cards:
            self.slot_data = []
            return

        rec_by_name = {r.card_name: r for r in (recommendations or [])}
        pack_size = len(pack_cards)

        self.slot_data = [
            {
                "card": card,
                "slot": slot_rect_for_index(rect, index, pack_size),
                "recommendation": rec_by_name.get(
                    card.get(constants.DATA_FIELD_NAME)
                ),
            }
            for index, card in enumerate(pack_cards)
        ]

    def _enable_click_through(self):
        api = _get_win32_extended_style_api()
        if api is None:
            return

        win32gui, win32con = api
        hwnd = self.winfo_id()
        styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            styles | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT,
        )

    def _sync_position(self):
        rect = self.tracker.get_rect()
        if rect is None:
            self.withdraw()
        else:
            left, top, right, bottom = rect
            self.geometry(f"{right - left}x{bottom - top}+{left}+{top}")
            self.deiconify()

        self._poll_job = self.after(POLL_INTERVAL_MS, self._sync_position)

    def destroy(self):
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        super().destroy()
