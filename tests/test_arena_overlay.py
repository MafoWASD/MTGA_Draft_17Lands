import tkinter
from unittest.mock import MagicMock, patch

import pytest

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
