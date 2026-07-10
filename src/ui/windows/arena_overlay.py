"""
src/ui/windows/arena_overlay.py
Transparent overlay window kept in sync with the MTG Arena game window.
"""

import sys
import tkinter

import ttkbootstrap as tb

from src import constants
from src.arena_window import ArenaWindowTracker
from src.overlay_layout import DEFAULT_LAYOUT_MODE, slot_rect_for_index
from src.logger import create_logger

logger = create_logger()

POLL_INTERVAL_MS = 250

# Windows-only colorkey: pixels of this exact color are made fully invisible
# and click-through by wm "-transparentcolor", instead of dimming the whole
# window uniformly with -alpha. Chosen to not collide with any badge color.
TRANSPARENT_COLOR_KEY = "#010101"

BADGE_RADIUS = 18
BADGE_FONT = ("Segoe UI", 11, "bold")

# Tier colors mirror the elite_bomb/high_fit row-highlight palette already
# used in src/ui/components.py, extended with the missing tiers.
BADGE_COLORS_BOMB = ("#78350f", "#fde047")  # flame, for is_elite cards
BADGE_COLORS_STRONG = ("#7f1d1d", "#fecaca")  # red
BADGE_COLORS_GOOD = ("#0c4a6e", "#e0f2fe")  # blue, matches high_fit
BADGE_COLORS_MARGINAL = ("#374151", "#d1d5db")  # grey

BADGE_TIER_STRONG_THRESHOLD = 75
BADGE_TIER_GOOD_THRESHOLD = 50

GIHWR_BADGE_WIDTH = 46
GIHWR_BADGE_HEIGHT = 20
GIHWR_BADGE_MARGIN = 4
GIHWR_BADGE_COLOR_BG = "#166534"  # green
GIHWR_BADGE_COLOR_FG = "#dcfce7"
GIHWR_BADGE_FONT = ("Segoe UI", 9, "bold")
GIHWR_ARROW = "↑"


def badge_colors_for_recommendation(recommendation):
    """Returns (background, foreground) hex colors for a card's VALUE badge."""
    if recommendation.is_elite:
        return BADGE_COLORS_BOMB
    if recommendation.contextual_score >= BADGE_TIER_STRONG_THRESHOLD:
        return BADGE_COLORS_STRONG
    if recommendation.contextual_score >= BADGE_TIER_GOOD_THRESHOLD:
        return BADGE_COLORS_GOOD
    return BADGE_COLORS_MARGINAL


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

    def __init__(self, parent, configuration=None, tracker=None):
        super().__init__(title="Arena Overlay", topmost=True)
        self.parent = parent
        self.configuration = configuration
        self.tracker = tracker or ArenaWindowTracker()
        self._poll_job = None

        self.overrideredirect(True)

        self.slot_data = []
        self._last_rect = None

        self.canvas = tkinter.Canvas(
            self, bg=TRANSPARENT_COLOR_KEY, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        if sys.platform == "win32":
            try:
                # Some systems quantize the raw hex slightly; read back Tk's
                # actually-resolved canvas color so the colorkey match is
                # exact, not just nominal.
                self.attributes("-transparentcolor", self.canvas.cget("bg"))
            except Exception:
                pass
        else:
            # -transparentcolor is Windows-only; fall back to uniform dimming
            # elsewhere so the overlay is still usable for local development.
            try:
                self.attributes("-alpha", 0.85)
            except Exception:
                pass

        self.withdraw()
        self.update_idletasks()
        self._enable_click_through()
        self._sync_position()

    def update_data(self, pack_cards, recommendations):
        """Maps the current pack's cards to their on-screen slot rects and redraws badges."""
        rect = self.tracker.get_rect()
        if rect is None or not pack_cards:
            self.slot_data = []
            self._last_rect = None
            self._render_badges()
            return

        rec_by_name = {r.card_name: r for r in (recommendations or [])}
        pack_size = len(pack_cards)
        layout_mode = getattr(
            getattr(self.configuration, "settings", None),
            "pack_layout_mode",
            DEFAULT_LAYOUT_MODE,
        )

        self._last_rect = rect
        self.slot_data = [
            {
                "card": card,
                "slot": slot_rect_for_index(rect, index, pack_size, layout_mode),
                "recommendation": rec_by_name.get(
                    card.get(constants.DATA_FIELD_NAME)
                ),
            }
            for index, card in enumerate(pack_cards)
        ]
        self._render_badges()

    def _render_badges(self):
        """Draws VALUE and GIHWR badges for each pack card that has a recommendation."""
        self.canvas.delete("badge")
        if not self.slot_data or self._last_rect is None:
            return

        origin_x, origin_y, _, _ = self._last_rect
        for entry in self.slot_data:
            recommendation = entry["recommendation"]
            if recommendation is None:
                continue

            left, top, right, _bottom = entry["slot"]
            cx = (left + right) / 2 - origin_x
            cy = top - origin_y

            bg, fg = badge_colors_for_recommendation(recommendation)
            self.canvas.create_oval(
                cx - BADGE_RADIUS,
                cy,
                cx + BADGE_RADIUS,
                cy + 2 * BADGE_RADIUS,
                fill=bg,
                outline=fg,
                width=2,
                tags="badge",
            )
            self.canvas.create_text(
                cx,
                cy + BADGE_RADIUS,
                text=str(round(recommendation.contextual_score)),
                fill=fg,
                font=BADGE_FONT,
                tags="badge",
            )

            self._render_gihwr_badge(recommendation, left - origin_x, top - origin_y)

    def _render_gihwr_badge(self, recommendation, slot_left, slot_top):
        """Draws the green GIHWR% badge in the top-left corner of a card slot."""
        if recommendation.base_win_rate <= 0:
            return

        badge_left = slot_left + GIHWR_BADGE_MARGIN
        badge_top = slot_top + GIHWR_BADGE_MARGIN
        self.canvas.create_rectangle(
            badge_left,
            badge_top,
            badge_left + GIHWR_BADGE_WIDTH,
            badge_top + GIHWR_BADGE_HEIGHT,
            fill=GIHWR_BADGE_COLOR_BG,
            outline=GIHWR_BADGE_COLOR_FG,
            width=1,
            tags="badge",
        )
        self.canvas.create_text(
            badge_left + GIHWR_BADGE_WIDTH / 2,
            badge_top + GIHWR_BADGE_HEIGHT / 2,
            text=f"{GIHWR_ARROW} {recommendation.base_win_rate:.0f}%",
            fill=GIHWR_BADGE_COLOR_FG,
            font=GIHWR_BADGE_FONT,
            tags="badge",
        )

    def _enable_click_through(self):
        api = _get_win32_extended_style_api()
        if api is None:
            return

        win32gui, win32con = api
        # winfo_id() returns Tk's inner content-window handle. The actual
        # top-level HWND that Windows uses for mouse hit-testing is its
        # parent; setting the extended styles on the wrong handle leaves
        # clicks blocked even though the style bits appear to be set.
        hwnd = win32gui.GetParent(self.winfo_id())
        styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            styles | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT,
        )
        win32gui.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_FRAMECHANGED,
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
