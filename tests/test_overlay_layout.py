import pytest

from src import constants
from src.overlay_layout import (
    CARD_ASPECT_RATIO,
    DEFAULT_LAYOUT_MODE,
    GRID_5_COLUMN,
    GRID_8_COLUMN,
    LAYOUT_PROFILES,
    all_slot_rects,
    slot_rect_for_index,
)

ARENA_RECT = (0, 0, 1920, 1080)


def test_default_layout_mode_is_five_column():
    assert DEFAULT_LAYOUT_MODE == constants.PACK_LAYOUT_MODE_5_COLUMN
    assert LAYOUT_PROFILES[DEFAULT_LAYOUT_MODE] is GRID_5_COLUMN


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_first_slot_starts_at_grid_top_left_corner(layout_mode):
    profile = LAYOUT_PROFILES[layout_mode]
    left, top, _, _ = slot_rect_for_index(ARENA_RECT, 0, 15, layout_mode)

    assert left == round(1920 * profile.grid_left_pct)
    assert top == round(1080 * profile.grid_top_pct)


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_card_size_is_fixed_regardless_of_pack_size(layout_mode):
    """Unlike a stretch-to-fill layout, card size must not shrink as pack_size grows."""
    small_pack_rect = slot_rect_for_index(ARENA_RECT, 0, 3, layout_mode)
    large_pack_rect = slot_rect_for_index(ARENA_RECT, 0, 15, layout_mode)

    small_width = small_pack_rect[2] - small_pack_rect[0]
    large_width = large_pack_rect[2] - large_pack_rect[0]
    assert small_width == large_width


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_row_wraps_after_max_columns_per_row(layout_mode):
    """A full pack must put the card after the last column at the start of row 2."""
    profile = LAYOUT_PROFILES[layout_mode]
    columns = profile.max_columns_per_row
    pack_size = columns + 3  # guarantees a second, partial row

    first_row_last = slot_rect_for_index(ARENA_RECT, columns - 1, pack_size, layout_mode)
    second_row_first = slot_rect_for_index(ARENA_RECT, columns, pack_size, layout_mode)

    # Second row starts back at the grid's left edge...
    assert second_row_first[0] == round(1920 * profile.grid_left_pct)
    # ...one row pitch below the first row.
    assert second_row_first[1] == round(
        1080 * (profile.grid_top_pct + profile.row_pitch_pct)
    )
    # And it's strictly below the last card of the first row.
    assert second_row_first[1] > first_row_last[1]


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_small_pack_stays_in_a_single_row(layout_mode):
    """A pack with fewer cards than max_columns_per_row must not wrap."""
    rects = all_slot_rects(ARENA_RECT, 3, layout_mode)

    tops = {rect[1] for rect in rects}
    assert len(tops) == 1


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_columns_are_evenly_spaced_by_column_pitch(layout_mode):
    profile = LAYOUT_PROFILES[layout_mode]
    rects = all_slot_rects(ARENA_RECT, profile.max_columns_per_row, layout_mode)

    for previous, current in zip(rects, rects[1:]):
        # Allow a 1px rounding fuzz: each slot rounds its absolute position,
        # not the pitch in isolation, so consecutive diffs can be off-by-one.
        assert current[0] - previous[0] == pytest.approx(
            1920 * profile.column_pitch_pct, abs=1
        )


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_rows_are_evenly_spaced_by_row_pitch(layout_mode):
    profile = LAYOUT_PROFILES[layout_mode]
    columns = profile.max_columns_per_row
    pack_size = columns * 3

    rects = all_slot_rects(ARENA_RECT, pack_size, layout_mode)

    row1_top = rects[0][1]
    row2_top = rects[columns][1]
    row3_top = rects[2 * columns][1]

    assert row2_top - row1_top == pytest.approx(1080 * profile.row_pitch_pct, abs=1)
    assert row3_top - row2_top == pytest.approx(1080 * profile.row_pitch_pct, abs=1)


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_card_aspect_ratio_matches_standard_mtg_proportions(layout_mode):
    left, top, right, bottom = slot_rect_for_index(ARENA_RECT, 0, 5, layout_mode)

    width = right - left
    height = bottom - top
    assert width / height == pytest.approx(CARD_ASPECT_RATIO, rel=0.01)


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_slot_dimensions_are_positive_for_typical_pack_sizes(layout_mode):
    for pack_size in (1, 2, 3, 8, 14, 15):
        for rect in all_slot_rects(ARENA_RECT, pack_size, layout_mode):
            left, top, right, bottom = rect
            assert right > left
            assert bottom > top


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_all_slot_rects_matches_slot_rect_for_index_per_card(layout_mode):
    pack_size = 15
    rects = all_slot_rects(ARENA_RECT, pack_size, layout_mode)

    for index, rect in enumerate(rects):
        assert rect == slot_rect_for_index(ARENA_RECT, index, pack_size, layout_mode)


@pytest.mark.parametrize("layout_mode", list(LAYOUT_PROFILES))
def test_mapping_shifts_with_arena_window_offset(layout_mode):
    """Moving the whole Arena window should shift slots by the same offset."""
    base_rects = all_slot_rects(ARENA_RECT, 15, layout_mode)

    offset_rect = (100, 50, 100 + 1920, 50 + 1080)
    offset_rects = all_slot_rects(offset_rect, 15, layout_mode)

    for (bl, bt, br, bb), (ol, ot, orr, ob) in zip(base_rects, offset_rects):
        assert ol == bl + 100
        assert ot == bt + 50
        assert orr == br + 100
        assert ob == bb + 50


def test_rejects_out_of_range_index():
    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, 14, 14)

    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, -1, 14)


def test_rejects_non_positive_pack_size():
    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, 0, 0)


def test_rejects_unknown_layout_mode():
    with pytest.raises(ValueError):
        slot_rect_for_index(ARENA_RECT, 0, 14, layout_mode="not_a_real_mode")


def test_five_and_eight_column_profiles_place_cards_differently():
    """Sanity check the two profiles are actually distinct, not accidental duplicates."""
    five_col_rect = slot_rect_for_index(
        ARENA_RECT, 5, 15, constants.PACK_LAYOUT_MODE_5_COLUMN
    )
    eight_col_rect = slot_rect_for_index(
        ARENA_RECT, 5, 15, constants.PACK_LAYOUT_MODE_8_COLUMN
    )

    assert five_col_rect != eight_col_rect
