import pytest

from src.overlay_layout import (
    PACK_AREA_BOTTOM_PCT,
    PACK_AREA_LEFT_PCT,
    PACK_AREA_RIGHT_PCT,
    PACK_AREA_TOP_PCT,
    all_slot_rects,
    slot_rect_for_index,
)

ARENA_RECT = (0, 0, 1920, 1080)


def test_first_slot_starts_at_pack_area_left_edge():
    left, _, _, _ = slot_rect_for_index(ARENA_RECT, 0, 4)

    expected_area_left = round(1920 * PACK_AREA_LEFT_PCT)
    assert left == expected_area_left


def test_slots_are_ordered_left_to_right_without_overlap():
    rects = all_slot_rects(ARENA_RECT, 8)

    for previous, current in zip(rects, rects[1:]):
        assert previous[2] <= current[0]


def test_last_slot_does_not_exceed_pack_area_right_edge():
    rects = all_slot_rects(ARENA_RECT, 5)

    expected_area_right = round(1920 * PACK_AREA_RIGHT_PCT)
    assert rects[-1][2] <= expected_area_right


def test_slots_stay_within_vertical_pack_area():
    rects = all_slot_rects(ARENA_RECT, 3)

    expected_top = round(1080 * PACK_AREA_TOP_PCT)
    expected_bottom = round(1080 * PACK_AREA_BOTTOM_PCT)

    for _, top, _, bottom in rects:
        assert top >= expected_top - 1
        assert bottom <= expected_bottom + 1


def test_slot_dimensions_are_positive_for_typical_pack_sizes():
    for pack_size in (1, 2, 3, 8, 15):
        for rect in all_slot_rects(ARENA_RECT, pack_size):
            left, top, right, bottom = rect
            assert right > left
            assert bottom > top


def test_single_card_slot_height_is_clamped_to_pack_area_height():
    left, top, right, bottom = slot_rect_for_index(ARENA_RECT, 0, 1)

    area_height = 1080 * (PACK_AREA_BOTTOM_PCT - PACK_AREA_TOP_PCT)
    assert (bottom - top) <= round(area_height) + 1


def test_all_slot_rects_matches_slot_rect_for_index_per_card():
    pack_size = 6
    rects = all_slot_rects(ARENA_RECT, pack_size)

    for index, rect in enumerate(rects):
        assert rect == slot_rect_for_index(ARENA_RECT, index, pack_size)


def test_rejects_out_of_range_index():
    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, 4, 4)

    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, -1, 4)


def test_rejects_non_positive_pack_size():
    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, 0, 0)


def test_mapping_shifts_with_arena_window_offset():
    """Moving the whole Arena window should shift slots by the same offset."""
    base_rects = all_slot_rects(ARENA_RECT, 4)

    offset_rect = (100, 50, 100 + 1920, 50 + 1080)
    offset_rects = all_slot_rects(offset_rect, 4)

    for (bl, bt, br, bb), (ol, ot, orr, ob) in zip(base_rects, offset_rects):
        assert ol == bl + 100
        assert ot == bt + 50
        assert orr == br + 100
        assert ob == bb + 50
