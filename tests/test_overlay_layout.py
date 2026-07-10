import pytest

from src.overlay_layout import (
    CARD_ASPECT_RATIO,
    COLUMN_PITCH_PCT,
    GRID_LEFT_PCT,
    GRID_TOP_PCT,
    MAX_COLUMNS_PER_ROW,
    ROW_PITCH_PCT,
    all_slot_rects,
    slot_rect_for_index,
)

ARENA_RECT = (0, 0, 1920, 1080)


def test_first_slot_starts_at_grid_top_left_corner():
    left, top, _, _ = slot_rect_for_index(ARENA_RECT, 0, 14)

    assert left == round(1920 * GRID_LEFT_PCT)
    assert top == round(1080 * GRID_TOP_PCT)


def test_card_size_is_fixed_regardless_of_pack_size():
    """Unlike a stretch-to-fill layout, card size must not shrink as pack_size grows."""
    small_pack_rect = slot_rect_for_index(ARENA_RECT, 0, 3)
    large_pack_rect = slot_rect_for_index(ARENA_RECT, 0, 14)

    small_width = small_pack_rect[2] - small_pack_rect[0]
    large_width = large_pack_rect[2] - large_pack_rect[0]
    assert small_width == large_width


def test_row_wraps_after_max_columns_per_row():
    """A 14-card pack (5-5-4) must put index 5 at the start of row 2, not row 1 col 6."""
    first_row_last = slot_rect_for_index(ARENA_RECT, MAX_COLUMNS_PER_ROW - 1, 14)
    second_row_first = slot_rect_for_index(ARENA_RECT, MAX_COLUMNS_PER_ROW, 14)

    # Second row starts back at the grid's left edge...
    assert second_row_first[0] == round(1920 * GRID_LEFT_PCT)
    # ...one row pitch below the first row.
    assert second_row_first[1] == round(1080 * (GRID_TOP_PCT + ROW_PITCH_PCT))
    # And it's strictly below the last card of the first row.
    assert second_row_first[1] > first_row_last[1]


def test_small_pack_stays_in_a_single_row():
    """A pack with fewer cards than MAX_COLUMNS_PER_ROW must not wrap."""
    rects = all_slot_rects(ARENA_RECT, 3)

    tops = {rect[1] for rect in rects}
    assert len(tops) == 1


def test_columns_are_evenly_spaced_by_column_pitch():
    rects = all_slot_rects(ARENA_RECT, 5)

    for previous, current in zip(rects, rects[1:]):
        assert current[0] - previous[0] == round(1920 * COLUMN_PITCH_PCT)


def test_rows_are_evenly_spaced_by_row_pitch():
    rects = all_slot_rects(ARENA_RECT, 14)

    row1_top = rects[0][1]
    row2_top = rects[MAX_COLUMNS_PER_ROW][1]
    row3_top = rects[2 * MAX_COLUMNS_PER_ROW][1]

    assert row2_top - row1_top == round(1080 * ROW_PITCH_PCT)
    assert row3_top - row2_top == round(1080 * ROW_PITCH_PCT)


def test_card_aspect_ratio_matches_standard_mtg_proportions():
    left, top, right, bottom = slot_rect_for_index(ARENA_RECT, 0, 5)

    width = right - left
    height = bottom - top
    assert width / height == pytest.approx(CARD_ASPECT_RATIO, rel=0.01)


def test_slot_dimensions_are_positive_for_typical_pack_sizes():
    for pack_size in (1, 2, 3, 8, 14, 15):
        for rect in all_slot_rects(ARENA_RECT, pack_size):
            left, top, right, bottom = rect
            assert right > left
            assert bottom > top


def test_all_slot_rects_matches_slot_rect_for_index_per_card():
    pack_size = 14
    rects = all_slot_rects(ARENA_RECT, pack_size)

    for index, rect in enumerate(rects):
        assert rect == slot_rect_for_index(ARENA_RECT, index, pack_size)


def test_rejects_out_of_range_index():
    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, 14, 14)

    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, -1, 14)


def test_rejects_non_positive_pack_size():
    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, 0, 0)


def test_mapping_shifts_with_arena_window_offset():
    """Moving the whole Arena window should shift slots by the same offset."""
    base_rects = all_slot_rects(ARENA_RECT, 14)

    offset_rect = (100, 50, 100 + 1920, 50 + 1080)
    offset_rects = all_slot_rects(offset_rect, 14)

    for (bl, bt, br, bb), (ol, ot, orr, ob) in zip(base_rects, offset_rects):
        assert ol == bl + 100
        assert ot == bt + 50
        assert orr == br + 100
        assert ob == bb + 50
