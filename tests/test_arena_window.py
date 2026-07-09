import sys
from unittest.mock import MagicMock, patch

from src.arena_window import ArenaWindowTracker


def _mock_win32gui(visible_windows):
    """Builds a MagicMock standing in for win32gui.

    visible_windows: list of (hwnd, title, is_visible) tuples used by EnumWindows.
    """
    win32gui = MagicMock()

    def enum_windows(callback, extra):
        for hwnd, _title, _visible in visible_windows:
            callback(hwnd, extra)

    win32gui.EnumWindows.side_effect = enum_windows
    win32gui.IsWindowVisible.side_effect = lambda hwnd: next(
        v for h, _, v in visible_windows if h == hwnd
    )
    win32gui.GetWindowText.side_effect = lambda hwnd: next(
        t for h, t, _ in visible_windows if h == hwnd
    )
    win32gui.IsWindow.return_value = True
    win32gui.IsIconic.return_value = False
    win32gui.error = Exception
    return win32gui


@patch("src.arena_window._get_win32gui")
def test_find_window_matches_arena_title(mock_get_win32gui):
    win32gui = _mock_win32gui([(42, "MTGA", True)])
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.find_window() == 42


@patch("src.arena_window._get_win32gui")
def test_find_window_ignores_non_matching_or_hidden_windows(mock_get_win32gui):
    win32gui = _mock_win32gui(
        [(1, "Notepad", True), (2, "MTGA", False), (3, "Some Other App", True)]
    )
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.find_window() is None


@patch("src.arena_window._get_win32gui")
def test_find_window_caches_handle_while_valid(mock_get_win32gui):
    win32gui = _mock_win32gui([(7, "MTGA", True)])
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()
    tracker.find_window()
    tracker.find_window()

    win32gui.EnumWindows.assert_called_once()


@patch("src.arena_window._get_win32gui")
def test_get_rect_returns_window_rect(mock_get_win32gui):
    win32gui = _mock_win32gui([(42, "MTGA", True)])
    win32gui.GetWindowRect.return_value = (10, 20, 1930, 1100)
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.get_rect() == (10, 20, 1930, 1100)


@patch("src.arena_window._get_win32gui")
def test_get_rect_returns_none_when_minimized(mock_get_win32gui):
    win32gui = _mock_win32gui([(42, "MTGA", True)])
    win32gui.IsIconic.return_value = True
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.get_rect() is None


@patch("src.arena_window._get_win32gui")
def test_get_rect_returns_none_when_window_not_found(mock_get_win32gui):
    win32gui = _mock_win32gui([])
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.get_rect() is None


@patch("src.arena_window._get_win32gui")
def test_get_rect_handles_invalidated_handle(mock_get_win32gui):
    win32gui = _mock_win32gui([(42, "MTGA", True)])
    win32gui.GetWindowRect.side_effect = win32gui.error("window closed")
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.get_rect() is None
    assert tracker._hwnd is None


@patch("src.arena_window._get_win32gui")
def test_is_foreground_true_when_arena_is_active(mock_get_win32gui):
    win32gui = _mock_win32gui([(42, "MTGA", True)])
    win32gui.GetForegroundWindow.return_value = 42
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.is_foreground() is True


@patch("src.arena_window._get_win32gui")
def test_is_foreground_false_when_another_window_is_active(mock_get_win32gui):
    win32gui = _mock_win32gui([(42, "MTGA", True)])
    win32gui.GetForegroundWindow.return_value = 99
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.is_foreground() is False


@patch("src.arena_window._get_win32gui")
def test_is_foreground_false_when_arena_not_found(mock_get_win32gui):
    win32gui = _mock_win32gui([])
    mock_get_win32gui.return_value = win32gui

    tracker = ArenaWindowTracker()

    assert tracker.is_foreground() is False


def test_no_win32gui_available_returns_none_gracefully():
    """On a real non-Windows platform (no mocking), the tracker should no-op cleanly."""
    with patch("src.arena_window._get_win32gui", return_value=None):
        tracker = ArenaWindowTracker()

        assert tracker.find_window() is None
        assert tracker.get_rect() is None
        assert tracker.is_foreground() is False
