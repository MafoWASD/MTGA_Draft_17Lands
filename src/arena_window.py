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
        self._logged_not_found = False

    def find_window(self) -> Optional[int]:
        """Returns the cached Arena window handle, re-scanning if it's stale."""
        win32gui = _get_win32gui()
        if win32gui is None:
            return None

        if self._hwnd is not None and win32gui.IsWindow(self._hwnd):
            return self._hwnd

        found = []
        visible_titles = []

        def _enum_handler(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            visible_titles.append(title)
            if title in self.window_titles:
                found.append(hwnd)

        win32gui.EnumWindows(_enum_handler, None)
        self._hwnd = found[0] if found else None

        if self._hwnd is not None:
            if self._logged_not_found:
                logger.info("Arena window found (title match).")
            self._logged_not_found = False
        elif not self._logged_not_found:
            # Log once per not-found streak (not every 250ms poll) so the
            # user can see what window titles ARE visible if "MTGA"/"MTG
            # Arena" isn't matching their actual client window.
            logger.debug(
                "Arena window not found among visible windows: %s",
                visible_titles,
            )
            self._logged_not_found = True

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
