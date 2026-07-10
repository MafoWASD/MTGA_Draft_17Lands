"""
src/overlay_layout.py
Maps MTG Arena's draft pack card layout to on-screen slot rectangles.
"""

from typing import List, Tuple

Rect = Tuple[int, int, int, int]  # (left, top, right, bottom) in screen pixels

# Percentage offsets, relative to the Arena window's client rect, bounding the
# horizontal band where pack cards are laid out during a draft pick. These are
# eyeballed against Arena's draft screen and will need calibration against a
# real Arena window (see ArenaOverlay's debug outline from Task 2).
PACK_AREA_LEFT_PCT = 0.06
PACK_AREA_RIGHT_PCT = 0.94
PACK_AREA_TOP_PCT = 0.30
PACK_AREA_BOTTOM_PCT = 0.72

CARD_ASPECT_RATIO = 5.0 / 7.0  # width / height, standard MTG card proportions
CARD_GAP_PCT = 0.01  # gap between adjacent cards, as a fraction of Arena's width


def slot_rect_for_index(arena_rect: Rect, index: int, pack_size: int) -> Rect:
    """Returns the on-screen rect for the card at `index` within a pack of `pack_size` cards.

    `index` is 0-based, left to right. Coordinates are absolute screen pixels,
    in the same space as `arena_rect`.
    """
    if pack_size <= 0:
        raise ValueError("pack_size must be positive")
    if not (0 <= index < pack_size):
        raise ValueError(f"index {index} out of range for pack_size {pack_size}")

    left, top, right, bottom = arena_rect
    width = right - left
    height = bottom - top

    area_left = left + width * PACK_AREA_LEFT_PCT
    area_top = top + height * PACK_AREA_TOP_PCT
    area_width = width * (PACK_AREA_RIGHT_PCT - PACK_AREA_LEFT_PCT)
    area_height = height * (PACK_AREA_BOTTOM_PCT - PACK_AREA_TOP_PCT)

    gap = width * CARD_GAP_PCT
    slot_width = (area_width - gap * (pack_size - 1)) / pack_size
    slot_height = min(area_height, slot_width / CARD_ASPECT_RATIO)

    slot_left = area_left + index * (slot_width + gap)
    slot_top = area_top + (area_height - slot_height) / 2

    return (
        round(slot_left),
        round(slot_top),
        round(slot_left + slot_width),
        round(slot_top + slot_height),
    )


def all_slot_rects(arena_rect: Rect, pack_size: int) -> List[Rect]:
    """Returns slot rects for every card in a pack, in pack order."""
    return [slot_rect_for_index(arena_rect, i, pack_size) for i in range(pack_size)]
