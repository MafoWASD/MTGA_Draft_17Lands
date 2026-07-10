"""
src/overlay_layout.py
Maps MTG Arena's draft pack card grid layout to on-screen slot rectangles.
"""

from typing import List, Tuple

Rect = Tuple[int, int, int, int]  # (left, top, right, bottom) in screen pixels

# Percentage offsets, relative to the Arena window's client rect, calibrated
# from a real Pack 1 Pick 1 screenshot (14 cards, wrapped 5-5-4 into rows of
# up to MAX_COLUMNS_PER_ROW). Arena lays pack cards out in a fixed-size grid
# that wraps to new rows — it does NOT stretch every card into a single row.
GRID_LEFT_PCT = 0.144
GRID_TOP_PCT = 0.178
COLUMN_PITCH_PCT = 0.102  # horizontal distance between successive card left-edges
ROW_PITCH_PCT = 0.246  # vertical distance between successive card top-edges
CARD_WIDTH_PCT = 0.088  # fixed card width, independent of pack_size

CARD_ASPECT_RATIO = 5.0 / 7.0  # width / height, standard MTG card proportions
MAX_COLUMNS_PER_ROW = 5


def slot_rect_for_index(arena_rect: Rect, index: int, pack_size: int) -> Rect:
    """Returns the on-screen rect for the card at `index` within a pack of `pack_size` cards.

    `index` is 0-based. Cards wrap into rows of up to MAX_COLUMNS_PER_ROW,
    left to right then top to bottom, matching Arena's draft pack grid.
    Coordinates are absolute screen pixels, in the same space as `arena_rect`.
    """
    if pack_size <= 0:
        raise ValueError("pack_size must be positive")
    if not (0 <= index < pack_size):
        raise ValueError(f"index {index} out of range for pack_size {pack_size}")

    left, top, right, bottom = arena_rect
    width = right - left
    height = bottom - top

    columns = min(pack_size, MAX_COLUMNS_PER_ROW)
    row, col = divmod(index, columns)

    card_width = width * CARD_WIDTH_PCT
    card_height = card_width / CARD_ASPECT_RATIO

    slot_left = left + width * GRID_LEFT_PCT + col * width * COLUMN_PITCH_PCT
    slot_top = top + height * GRID_TOP_PCT + row * height * ROW_PITCH_PCT

    return (
        round(slot_left),
        round(slot_top),
        round(slot_left + card_width),
        round(slot_top + card_height),
    )


def all_slot_rects(arena_rect: Rect, pack_size: int) -> List[Rect]:
    """Returns slot rects for every card in a pack, in pack order."""
    return [slot_rect_for_index(arena_rect, i, pack_size) for i in range(pack_size)]
