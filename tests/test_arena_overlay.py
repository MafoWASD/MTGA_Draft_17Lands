import tkinter
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src import constants
from src.overlay_layout import slot_rect_for_index
from src.ui.windows.arena_overlay import ArenaOverlay
from src.ui.styles import Theme


@pytest.fixture
def root():
    r = tkinter.Tk()
    Theme.apply(r, "Dark")
    yield r
    r.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_overlay_positions_itself_over_arena_rect(mock_ov, root):
    tracker = MagicMock()
    tracker.get_rect.return_value = (10, 20, 1930, 1100)

    overlay = ArenaOverlay(root, tracker=tracker)
    overlay.update_idletasks()

    assert overlay.winfo_exists()
    assert overlay.geometry().startswith("1920x1080+10+20")

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_overlay_hides_when_arena_not_found(mock_ov, root):
    tracker = MagicMock()
    tracker.get_rect.return_value = None

    overlay = ArenaOverlay(root, tracker=tracker)

    assert overlay.state() == "withdrawn"

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_overlay_reschedules_position_sync(mock_ov, root):
    tracker = MagicMock()
    tracker.get_rect.return_value = (0, 0, 100, 100)

    overlay = ArenaOverlay(root, tracker=tracker)

    assert overlay._poll_job is not None
    assert tracker.get_rect.call_count == 1

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_destroy_cancels_pending_poll(mock_ov, root):
    tracker = MagicMock()
    tracker.get_rect.return_value = (0, 0, 100, 100)

    overlay = ArenaOverlay(root, tracker=tracker)
    assert overlay._poll_job is not None

    overlay.destroy()

    assert overlay._poll_job is None


@patch("src.ui.windows.arena_overlay._get_win32_extended_style_api")
@patch("tkinter.Toplevel.overrideredirect")
def test_click_through_applies_layered_and_transparent_styles(mock_ov, mock_api, root):
    win32gui = MagicMock()
    win32con = MagicMock(GWL_EXSTYLE=1, WS_EX_LAYERED=0b01, WS_EX_TRANSPARENT=0b10)
    win32gui.GetWindowLong.return_value = 0b100
    mock_api.return_value = (win32gui, win32con)

    overlay = ArenaOverlay(root, tracker=MagicMock(get_rect=MagicMock(return_value=None)))

    win32gui.SetWindowLong.assert_called_once_with(
        overlay.winfo_id(), win32con.GWL_EXSTYLE, 0b111
    )

    overlay.destroy()


@patch("src.ui.windows.arena_overlay._get_win32_extended_style_api", return_value=None)
@patch("tkinter.Toplevel.overrideredirect")
def test_click_through_is_a_no_op_off_windows(mock_ov, mock_api, root):
    tracker = MagicMock(get_rect=MagicMock(return_value=None))

    overlay = ArenaOverlay(root, tracker=tracker)

    assert overlay.winfo_exists()

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_update_data_maps_each_card_to_its_slot_rect(mock_ov, root):
    arena_rect = (0, 0, 1920, 1080)
    tracker = MagicMock(get_rect=MagicMock(return_value=arena_rect))
    overlay = ArenaOverlay(root, tracker=tracker)

    pack_cards = [
        {constants.DATA_FIELD_NAME: "Card A"},
        {constants.DATA_FIELD_NAME: "Card B"},
    ]
    recommendations = [
        SimpleNamespace(card_name="Card A", contextual_score=88, is_elite=False),
        SimpleNamespace(card_name="Card B", contextual_score=42, is_elite=False),
    ]

    overlay.update_data(pack_cards, recommendations)

    assert len(overlay.slot_data) == 2
    for index, entry in enumerate(overlay.slot_data):
        assert entry["card"] == pack_cards[index]
        assert entry["slot"] == slot_rect_for_index(arena_rect, index, 2)
        assert entry["recommendation"] == recommendations[index]

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_update_data_handles_card_with_no_matching_recommendation(mock_ov, root):
    tracker = MagicMock(get_rect=MagicMock(return_value=(0, 0, 1920, 1080)))
    overlay = ArenaOverlay(root, tracker=tracker)

    pack_cards = [{constants.DATA_FIELD_NAME: "Unrated Card"}]

    overlay.update_data(pack_cards, [])

    assert overlay.slot_data[0]["recommendation"] is None

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_update_data_clears_slots_when_pack_is_empty(mock_ov, root):
    tracker = MagicMock(get_rect=MagicMock(return_value=(0, 0, 1920, 1080)))
    overlay = ArenaOverlay(root, tracker=tracker)

    overlay.update_data([], [])

    assert overlay.slot_data == []

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_update_data_clears_slots_when_arena_not_found(mock_ov, root):
    tracker = MagicMock(get_rect=MagicMock(return_value=None))
    overlay = ArenaOverlay(root, tracker=tracker)

    overlay.update_data(
        [{constants.DATA_FIELD_NAME: "Card A"}],
        [SimpleNamespace(card_name="Card A", contextual_score=88, is_elite=False)],
    )

    assert overlay.slot_data == []

    overlay.destroy()


def _rec(name, score, is_elite=False):
    return SimpleNamespace(card_name=name, contextual_score=score, is_elite=is_elite)


@patch("tkinter.Toplevel.overrideredirect")
def test_render_badges_draws_one_badge_per_rated_card(mock_ov, root):
    tracker = MagicMock(get_rect=MagicMock(return_value=(0, 0, 1920, 1080)))
    overlay = ArenaOverlay(root, tracker=tracker)

    pack_cards = [
        {constants.DATA_FIELD_NAME: "Card A"},
        {constants.DATA_FIELD_NAME: "Card B"},
    ]
    overlay.update_data(
        pack_cards, [_rec("Card A", 88), _rec("Card B", 42)]
    )

    # Each badge is a circle + a text label, both tagged "badge".
    assert len(overlay.canvas.find_withtag("badge")) == 4

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_render_badges_skips_cards_without_a_recommendation(mock_ov, root):
    tracker = MagicMock(get_rect=MagicMock(return_value=(0, 0, 1920, 1080)))
    overlay = ArenaOverlay(root, tracker=tracker)

    overlay.update_data([{constants.DATA_FIELD_NAME: "Unrated"}], [])

    assert overlay.canvas.find_withtag("badge") == ()

    overlay.destroy()


@patch("tkinter.Toplevel.overrideredirect")
def test_render_badges_clears_previous_badges_on_refresh(mock_ov, root):
    tracker = MagicMock(get_rect=MagicMock(return_value=(0, 0, 1920, 1080)))
    overlay = ArenaOverlay(root, tracker=tracker)

    overlay.update_data(
        [{constants.DATA_FIELD_NAME: "Card A"}], [_rec("Card A", 88)]
    )
    assert len(overlay.canvas.find_withtag("badge")) == 2

    overlay.update_data([], [])
    assert overlay.canvas.find_withtag("badge") == ()

    overlay.destroy()


@pytest.mark.parametrize(
    "recommendation,expected_colors",
    [
        (_rec("Bomb", 95, is_elite=True), ("#78350f", "#fde047")),
        (_rec("Strong", 80), ("#7f1d1d", "#fecaca")),
        (_rec("Good", 60), ("#0c4a6e", "#e0f2fe")),
        (_rec("Marginal", 20), ("#374151", "#d1d5db")),
    ],
)
def test_badge_colors_for_recommendation_tiers(recommendation, expected_colors):
    from src.ui.windows.arena_overlay import badge_colors_for_recommendation

    assert badge_colors_for_recommendation(recommendation) == expected_colors
