from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.card_name_ocr import (
    NAME_REGION_HEIGHT_PCT,
    NAME_REGION_TOP_PCT,
    capture_region,
    identify_card_at_slot,
    is_ocr_available,
    match_card_name,
    name_region_for_slot,
    recognize_text,
)
import src.card_name_ocr as card_name_ocr


@pytest.fixture(autouse=True)
def reset_ocr_availability_cache():
    """is_ocr_available() caches its result globally; keep tests independent."""
    card_name_ocr._tesseract_available = None
    yield
    card_name_ocr._tesseract_available = None


def test_name_region_for_slot_is_a_thin_band_near_the_top():
    slot = (100, 200, 300, 480)  # 200x280 card

    left, top, right, bottom = name_region_for_slot(slot)

    assert left == 100
    assert right == 300
    assert top == 200 + round(280 * NAME_REGION_TOP_PCT)
    assert bottom == top + round(280 * NAME_REGION_HEIGHT_PCT)
    assert bottom < 480  # stays within the card, doesn't cover the art


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

    mock_image_grab.grab.assert_called_once_with(bbox=rect)


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


def test_match_card_name_returns_none_when_nothing_close_enough():
    candidates = ["Hawkeye, Master Marksman", "Web Up"]

    assert match_card_name("completely unrelated garbage text", candidates) is None


def test_match_card_name_returns_none_for_empty_input():
    assert match_card_name("", ["Web Up"]) is None
    assert match_card_name("Web Up", []) is None


@patch("src.card_name_ocr.is_ocr_available", return_value=False)
def test_identify_card_at_slot_returns_none_when_ocr_unavailable(mock_available):
    result = identify_card_at_slot((0, 0, 200, 280), ["Web Up"])

    assert result is None


@patch("src.card_name_ocr.match_card_name")
@patch("src.card_name_ocr.recognize_text")
@patch("src.card_name_ocr.capture_region")
@patch("src.card_name_ocr.is_ocr_available", return_value=True)
def test_identify_card_at_slot_wires_capture_recognize_and_match(
    mock_available, mock_capture, mock_recognize, mock_match
):
    mock_capture.return_value = "fake-image"
    mock_recognize.return_value = "Web Up"
    mock_match.return_value = "Web Up"

    result = identify_card_at_slot((0, 0, 200, 280), ["Web Up", "Hawkeye"])

    mock_capture.assert_called_once_with(name_region_for_slot((0, 0, 200, 280)))
    mock_recognize.assert_called_once_with("fake-image")
    mock_match.assert_called_once_with("Web Up", ["Web Up", "Hawkeye"])
    assert result == "Web Up"
