from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.card_name_ocr import (
    NAME_REGION_HEIGHT_PCT,
    NAME_REGION_TOP_PCT,
    capture_region,
    identify_cards_in_pack,
    is_ocr_available,
    match_card_name,
    name_region_for_slot,
    recognize_text,
)
import src.card_name_ocr as card_name_ocr


@pytest.fixture(autouse=True)
def reset_ocr_availability_cache():
    """is_ocr_available() and the resolved binary path cache globally; keep tests independent."""
    card_name_ocr._tesseract_available = None
    card_name_ocr._path_configured = False
    yield
    card_name_ocr._tesseract_available = None
    card_name_ocr._path_configured = False


def test_name_region_for_slot_is_a_thin_band_near_the_top():
    slot = (100, 200, 300, 480)  # 200x280 card

    left, top, right, bottom = name_region_for_slot(slot)

    assert left == 100
    assert right == 300
    assert top == 200 + round(280 * NAME_REGION_TOP_PCT)
    assert bottom == top + round(280 * NAME_REGION_HEIGHT_PCT)
    assert bottom < 480  # stays within the card, doesn't cover the art


def test_configure_tesseract_path_skips_when_already_on_path():
    pytesseract = MagicMock()
    pytesseract.get_tesseract_version.return_value = "5.3.0"

    card_name_ocr._configure_tesseract_path(pytesseract)

    pytesseract.get_tesseract_version.assert_called_once()


@patch("src.card_name_ocr.os.path.isfile")
def test_configure_tesseract_path_falls_back_to_common_install_location(mock_isfile):
    pytesseract = MagicMock()
    pytesseract.get_tesseract_version.side_effect = Exception("not on PATH")
    expected_path = card_name_ocr.COMMON_TESSERACT_PATHS[0]
    mock_isfile.side_effect = lambda p: p == expected_path

    card_name_ocr._configure_tesseract_path(pytesseract)

    assert pytesseract.pytesseract.tesseract_cmd == expected_path


@patch("src.card_name_ocr.os.path.isfile", return_value=False)
def test_configure_tesseract_path_gives_up_when_no_common_location_exists(mock_isfile):
    pytesseract = MagicMock()
    pytesseract.get_tesseract_version.side_effect = Exception("not on PATH")

    card_name_ocr._configure_tesseract_path(pytesseract)

    assert pytesseract.pytesseract.tesseract_cmd not in card_name_ocr.COMMON_TESSERACT_PATHS


@patch("src.card_name_ocr._configure_tesseract_path")
def test_get_pytesseract_configures_path_only_once(mock_configure):
    card_name_ocr._get_pytesseract()
    card_name_ocr._get_pytesseract()

    mock_configure.assert_called_once()


@patch("src.card_name_ocr._get_pytesseract", return_value=None)
def test_is_ocr_available_false_when_pytesseract_not_installed(mock_get):
    assert is_ocr_available() is False


@patch("src.card_name_ocr._get_pytesseract")
def test_is_ocr_available_false_when_tesseract_binary_missing(mock_get):
    pytesseract = MagicMock()
    pytesseract.get_tesseract_version.side_effect = Exception("not found")
    mock_get.return_value = pytesseract

    assert is_ocr_available() is False


@patch("src.card_name_ocr._get_pytesseract")
def test_is_ocr_available_true_when_tesseract_responds(mock_get):
    pytesseract = MagicMock()
    pytesseract.get_tesseract_version.return_value = "5.3.0"
    mock_get.return_value = pytesseract

    assert is_ocr_available() is True


@patch("src.card_name_ocr._get_pytesseract")
def test_is_ocr_available_caches_result(mock_get):
    pytesseract = MagicMock()
    pytesseract.get_tesseract_version.return_value = "5.3.0"
    mock_get.return_value = pytesseract

    is_ocr_available()
    is_ocr_available()

    mock_get.assert_called_once()


@patch("src.card_name_ocr.ImageGrab")
def test_capture_region_grabs_the_given_rect(mock_image_grab):
    rect = (10, 20, 300, 60)

    capture_region(rect)

    # all_screens=True is required for secondary-monitor rects to capture
    # correctly on Windows.
    mock_image_grab.grab.assert_called_once_with(bbox=rect, all_screens=True)


@patch("src.card_name_ocr._get_pytesseract", return_value=None)
def test_recognize_text_returns_empty_string_without_pytesseract(mock_get):
    image = Image.new("RGB", (100, 30))

    assert recognize_text(image) == ""


@patch("src.card_name_ocr._get_pytesseract")
def test_recognize_text_strips_and_returns_ocr_output(mock_get):
    pytesseract = MagicMock()
    pytesseract.image_to_string.return_value = "  Hawkeye, Master Marksman  \n"
    mock_get.return_value = pytesseract

    image = Image.new("RGB", (100, 30))

    assert recognize_text(image) == "Hawkeye, Master Marksman"


@patch("src.card_name_ocr._get_pytesseract")
def test_recognize_text_returns_empty_string_on_ocr_failure(mock_get):
    pytesseract = MagicMock()
    pytesseract.image_to_string.side_effect = Exception("ocr engine crashed")
    mock_get.return_value = pytesseract

    image = Image.new("RGB", (100, 30))

    assert recognize_text(image) == ""


def test_match_card_name_finds_close_match_despite_ocr_noise():
    candidates = ["Hawkeye, Master Marksman", "Web Up", "Giant-Sized Flying Ant"]

    assert (
        match_card_name("Hawkeye, Master Marksrnan", candidates)
        == "Hawkeye, Master Marksman"
    )


def test_match_card_name_tolerates_heavier_real_world_ocr_noise():
    """Calibrated against a real capture: 'Ant-Man's Arm � 2' still had to
    match "Ant-Man's Army" despite the garbled trailing character and cost."""
    candidates = ["Ant-Man's Army", "Web Up", "Giant-Sized Flying Ant"]

    assert (
        match_card_name("Ant-Man's Arm � 2", candidates) == "Ant-Man's Army"
    )


def test_match_card_name_returns_none_when_nothing_close_enough():
    candidates = ["Hawkeye, Master Marksman", "Web Up"]

    assert match_card_name("completely unrelated garbage text", candidates) is None


def test_match_card_name_returns_none_for_empty_input():
    assert match_card_name("", ["Web Up"]) is None
    assert match_card_name("Web Up", []) is None


def test_match_card_name_rejects_short_reads_even_if_ratio_would_pass():
    """Real false positive: OCR read 'oe' off a near-blank slot and it
    scored 0.5 against 'Forest' — well above FUZZY_MATCH_CUTOFF (0.4)."""
    assert match_card_name("oe", ["Forest", "Web Up"]) is None


def test_match_card_name_rejects_single_character_reads():
    candidates = ["Web Up", "Take Up the Shield"]

    assert match_card_name("a", candidates) is None
    assert match_card_name("7", candidates) is None


@patch("src.card_name_ocr._get_win32_capture_api", return_value=None)
def test_capture_window_returns_none_when_api_unavailable(mock_api):
    assert card_name_ocr.capture_window(123) is None


@patch("src.card_name_ocr._get_win32_capture_api")
def test_capture_window_returns_none_for_a_zero_size_window(mock_api):
    win32gui, win32ui, ctypes = MagicMock(), MagicMock(), MagicMock()
    win32gui.GetWindowRect.return_value = (100, 100, 100, 100)  # 0x0
    mock_api.return_value = (win32gui, win32ui, ctypes)

    assert card_name_ocr.capture_window(123) is None


@patch("src.card_name_ocr._get_win32_capture_api")
def test_capture_window_returns_none_when_printwindow_reports_failure(mock_api):
    win32gui, win32ui, ctypes = MagicMock(), MagicMock(), MagicMock()
    win32gui.GetWindowRect.return_value = (0, 0, 200, 280)
    ctypes.windll.user32.PrintWindow.return_value = 0  # failure

    bitmap = win32ui.CreateBitmap.return_value
    bitmap.GetInfo.return_value = {"bmWidth": 200, "bmHeight": 280}
    bitmap.GetBitmapBits.return_value = b"\x00" * (200 * 280 * 4)
    mock_api.return_value = (win32gui, win32ui, ctypes)

    assert card_name_ocr.capture_window(123) is None


@patch("src.card_name_ocr._get_win32_capture_api")
def test_capture_window_returns_image_on_success(mock_api):
    win32gui, win32ui, ctypes = MagicMock(), MagicMock(), MagicMock()
    win32gui.GetWindowRect.return_value = (0, 0, 200, 280)
    ctypes.windll.user32.PrintWindow.return_value = 1  # success

    bitmap = win32ui.CreateBitmap.return_value
    bitmap.GetInfo.return_value = {"bmWidth": 200, "bmHeight": 280}
    bitmap.GetBitmapBits.return_value = b"\x00" * (200 * 280 * 4)
    mock_api.return_value = (win32gui, win32ui, ctypes)

    image = card_name_ocr.capture_window(123)

    assert image is not None
    assert image.size == (200, 280)


@patch("src.card_name_ocr._get_win32_capture_api")
def test_capture_window_returns_none_on_unexpected_error(mock_api):
    win32gui, win32ui, ctypes = MagicMock(), MagicMock(), MagicMock()
    win32gui.GetWindowRect.side_effect = Exception("window closed mid-capture")
    mock_api.return_value = (win32gui, win32ui, ctypes)

    assert card_name_ocr.capture_window(123) is None


@patch("src.card_name_ocr.is_ocr_available", return_value=False)
def test_identify_cards_in_pack_returns_empty_when_ocr_unavailable(mock_available):
    result = identify_cards_in_pack(123, (0, 0, 1920, 1080), [(0, 0, 200, 280)], ["Web Up"])

    assert result == {}


@patch("src.card_name_ocr.match_card_name")
@patch("src.card_name_ocr.recognize_text")
@patch("src.card_name_ocr.capture_window")
@patch("src.card_name_ocr.is_ocr_available", return_value=True)
def test_identify_cards_in_pack_crops_slots_from_one_window_capture(
    mock_available, mock_capture_window, mock_recognize, mock_match
):
    window_image = MagicMock()
    mock_capture_window.return_value = window_image
    mock_recognize.side_effect = ["Web Up text", "Hawkeye text"]
    mock_match.side_effect = ["Web Up", "Hawkeye"]

    arena_rect = (100, 50, 100 + 1920, 50 + 1080)
    slots = [(200, 150, 400, 430), (500, 150, 700, 430)]

    result = identify_cards_in_pack(999, arena_rect, slots, ["Web Up", "Hawkeye"])

    mock_capture_window.assert_called_once_with(999)
    assert window_image.crop.call_count == 2
    assert result == {0: "Web Up", 1: "Hawkeye"}


@patch("src.card_name_ocr.match_card_name")
@patch("src.card_name_ocr.recognize_text")
@patch("src.card_name_ocr.capture_region")
@patch("src.card_name_ocr.capture_window", return_value=None)
@patch("src.card_name_ocr.is_ocr_available", return_value=True)
def test_identify_cards_in_pack_falls_back_to_screen_capture(
    mock_available, mock_capture_window, mock_capture_region, mock_recognize, mock_match
):
    mock_recognize.return_value = "Web Up text"
    mock_match.return_value = "Web Up"

    arena_rect = (0, 0, 1920, 1080)
    slots = [(200, 150, 400, 430)]

    result = identify_cards_in_pack(999, arena_rect, slots, ["Web Up"])

    mock_capture_region.assert_called_once_with(name_region_for_slot(slots[0]))
    assert result == {0: "Web Up"}


@patch("src.card_name_ocr.match_card_name", return_value=None)
@patch("src.card_name_ocr.recognize_text", return_value="")
@patch("src.card_name_ocr.capture_window")
@patch("src.card_name_ocr.is_ocr_available", return_value=True)
def test_identify_cards_in_pack_omits_unresolved_slots(
    mock_available, mock_capture_window, mock_recognize, mock_match
):
    result = identify_cards_in_pack(
        999, (0, 0, 1920, 1080), [(200, 150, 400, 430)], ["Web Up"]
    )

    assert result == {}


@patch("src.card_name_ocr.match_card_name")
@patch("src.card_name_ocr.recognize_text", return_value="text")
@patch("src.card_name_ocr.capture_window")
@patch("src.card_name_ocr.is_ocr_available", return_value=True)
def test_identify_cards_in_pack_does_not_match_the_same_card_twice(
    mock_available, mock_capture_window, mock_recognize, mock_match
):
    # Both slots happen to read the same (mis-recognized) text; only the
    # first slot should claim "Web Up" — the second must not double-claim it.
    mock_match.side_effect = ["Web Up", None]

    result = identify_cards_in_pack(
        999,
        (0, 0, 1920, 1080),
        [(200, 150, 400, 430), (500, 150, 700, 430)],
        ["Web Up"],
    )

    assert result == {0: "Web Up"}
    # Second call's candidate list must have already excluded "Web Up".
    assert mock_match.call_args_list[1].args[1] == []
