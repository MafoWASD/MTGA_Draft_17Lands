"""
src/overlay_layout.py
Maps MTG Arena's draft pack card grid layout to on-screen slot rectangles.

Arena's pack grid can appear in more than one arrangement (the client has a
view toggle that changes how many cards fit per row), so callers pick a
calibration profile via `layout_mode` instead of assuming a single layout.
"""

from typing import Dict, List, NamedTuple, Tuple

from src import constants

Rect = Tuple[int, int, int, int]  # (left, top, right, bottom) in screen pixels

CARD_ASPECT_RATIO = 5.0 / 7.0  # width / height, standard MTG card proportions


class GridProfile(NamedTuple):
    grid_left_pct: float
    grid_top_pct: float
    column_pitch_pct: float  # horizontal distance between successive card left-edges
    row_pitch_pct: float  # vertical distance between successive card top-edges
    card_width_pct: float  # fixed card width, independent of pack_size
    max_columns_per_row: int


# Calibrated from a real Pack 1 Pick 1 screenshot (14 cards, wrapped 5-5-4).
GRID_5_COLUMN = GridProfile(
    grid_left_pct=0.144,
    grid_top_pct=0.178,
    column_pitch_pct=0.102,
    row_pitch_pct=0.246,
    card_width_pct=0.088,
    max_columns_per_row=5,
)

# Calibrated from a real Pack 3 Pick 1 screenshot taken in Arena's other pack
# view (toggled via the button next to the top-right icons), 15 cards wrapped
# 8-7.
GRID_8_COLUMN = GridProfile(
    grid_left_pct=0.169,
    grid_top_pct=0.170,
    column_pitch_pct=0.082,
    row_pitch_pct=0.182,
    card_width_pct=0.069,
    max_columns_per_row=8,
)

DEFAULT_LAYOUT_MODE = constants.PACK_LAYOUT_MODE_5_COLUMN

LAYOUT_PROFILES: Dict[str, GridProfile] = {
    constants.PACK_LAYOUT_MODE_5_COLUMN: GRID_5_COLUMN,
    constants.PACK_LAYOUT_MODE_8_COLUMN: GRID_8_COLUMN,
}


def slot_rect_for_index(
    arena_rect: Rect,
    index: int,
    pack_size: int,
    layout_mode: str = DEFAULT_LAYOUT_MODE,
) -> Rect:
    """Returns the on-screen rect for the card at `index` within a pack of `pack_size` cards.

    `index` is 0-based. Cards wrap into rows of up to the profile's
    `max_columns_per_row`, left to right then top to bottom, matching
    Arena's draft pack grid for the given `layout_mode`. Coordinates are
    absolute screen pixels, in the same space as `arena_rect`.
    """
    if pack_size <= 0:
        raise ValueError("pack_size must be positive")
    if not (0 <= index < pack_size):
        raise ValueError(f"index {index} out of range for pack_size {pack_size}")
    if layout_mode not in LAYOUT_PROFILES:
        raise ValueError(f"Unknown layout_mode: {layout_mode!r}")

    profile = LAYOUT_PROFILES[layout_mode]

    left, top, right, bottom = arena_rect
    width = right - left
    height = bottom - top

    columns = min(pack_size, profile.max_columns_per_row)
    row, col = divmod(index, columns)

    card_width = width * profile.card_width_pct
    card_height = card_width / CARD_ASPECT_RATIO

    slot_left = left + width * profile.grid_left_pct + col * width * profile.column_pitch_pct
    slot_top = top + height * profile.grid_top_pct + row * height * profile.row_pitch_pct

    return (
        round(slot_left),
        round(slot_top),
        round(slot_left + card_width),
        round(slot_top + card_height),
    )


def all_slot_rects(
    arena_rect: Rect, pack_size: int, layout_mode: str = DEFAULT_LAYOUT_MODE
) -> List[Rect]:
    """Returns slot rects for every card in a pack, in pack order."""
    return [
        slot_rect_for_index(arena_rect, i, pack_size, layout_mode)
        for i in range(pack_size)
    ]
