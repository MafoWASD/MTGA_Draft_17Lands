"""Locates and tracks the MTG Arena game window on Windows."""

import sys
from typing import Optional, Tuple

from src.logger import create_logger

logger = create_logger()

ARENA_WINDOW_TITLES = ("MTGA", "MTG Arena")


def _get_win32gui():
    """Lazily imports win32gui, returning None on non-Windows platforms."""
    if sys.platform != "win32":
        return None
    import win32gui

    return win32gui


class ArenaWindowTracker:
    """Finds the MTG Arena window and reports its screen position/size.

    No-ops (returns None/False) on non-Windows platforms, since pywin32's
    win32gui is only installable there.
    """

    def __init__(self, window_titles: Tuple[str, ...] = ARENA_WINDOW_TITLES):
        self.window_titles = window_titles
        self._hwnd: Optional[int] = None

    def find_window(self) -> Optional[int]:
        """Returns the cached Arena window handle, re-scanning if it's stale."""
        win32gui = _get_win32gui()
        if win32gui is None:
            return None

        if self._hwnd is not None and win32gui.IsWindow(self._hwnd):
            return self._hwnd

        found = []

        def _enum_handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(
                hwnd
            ) in self.window_titles:
                found.append(hwnd)

        win32gui.EnumWindows(_enum_handler, None)
        self._hwnd = found[0] if found else None
        return self._hwnd

    def get_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (left, top, right, bottom) for the Arena window.

        Returns None if the window can't be found or is minimized.
        """
        win32gui = _get_win32gui()
        hwnd = self.find_window()
        if win32gui is None or hwnd is None:
            return None

        if win32gui.IsIconic(hwnd):
            return None

        try:
            return win32gui.GetWindowRect(hwnd)
        except win32gui.error:
            logger.debug("Arena window handle %s became invalid", hwnd)
            self._hwnd = None
            return None

    def is_foreground(self) -> bool:
        """Returns True if the Arena window is currently the foreground window."""
        win32gui = _get_win32gui()
        hwnd = self.find_window()
        if win32gui is None or hwnd is None:
            return False

        return win32gui.GetForegroundWindow() == hwnd
