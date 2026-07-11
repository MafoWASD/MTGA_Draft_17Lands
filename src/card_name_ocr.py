"""
src/card_name_ocr.py
Reads a card's name off the live Arena screen via OCR, for cases where the
draft log's pack-card order doesn't match Arena's on-screen grid position.
"""

import difflib
import os
import sys
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageGrab, ImageOps

from src.logger import create_logger

logger = create_logger()

Rect = Tuple[int, int, int, int]  # (left, top, right, bottom) in screen pixels

# The card name sits in a thin banner right at the top of the card art, not
# the full card. Cropping tightly to it (rather than the whole card) avoids
# reading art/borders bleeding into the OCR pass, which hurts recognition
# more than it helps — shrunk from an earlier, looser 0.16 after real
# captures showed noise from below the name banner.
NAME_REGION_TOP_PCT = 0.015
NAME_REGION_HEIGHT_PCT = 0.11

# Calibrated against real captured text: a clean-ish read still scores ~0.85
# (e.g. "Ant-Man's Arm � 2" vs "Ant-Man's Army"), so there's headroom to
# accept noisier reads before risking cross-matching between the ~14 mostly
# dissimilar card names in a pack.
FUZZY_MATCH_CUTOFF = 0.4

# Reads this short are rejected before scoring at all — difflib's ratio can
# cross even FUZZY_MATCH_CUTOFF by chance on a couple of stray characters
# (real example: OCR read "oe" and it scored 0.5 against "Forest").
MIN_TEXT_LENGTH_FOR_MATCH = 4

# The Windows Tesseract installer doesn't add itself to PATH by default, so
# pytesseract's bare "tesseract" command often can't find it even when it's
# installed. Fall back to the installer's default locations.
COMMON_TESSERACT_PATHS = [
    os.path.join(
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        "Tesseract-OCR",
        "tesseract.exe",
    ),
    os.path.join(
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        "Tesseract-OCR",
        "tesseract.exe",
    ),
]

_tesseract_available: Optional[bool] = None
_path_configured = False


def _configure_tesseract_path(pytesseract):
    """Points pytesseract at a known install location if the bare command isn't found."""
    try:
        pytesseract.get_tesseract_version()
        return  # already resolvable via PATH
    except Exception as e:
        logger.debug(
            "Bare 'tesseract' command not resolvable (%s: %s); "
            "checking common install locations.",
            type(e).__name__,
            e,
        )

    for path in COMMON_TESSERACT_PATHS:
        if os.path.isfile(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.debug("Configured Tesseract binary path: %s", path)
            return

    logger.debug(
        "No Tesseract binary found at any common install location: %s",
        COMMON_TESSERACT_PATHS,
    )


def _get_pytesseract():
    """Lazily imports pytesseract, returning None if it's not installed."""
    global _path_configured
    try:
        import pytesseract
    except ImportError:
        return None

    if not _path_configured:
        _configure_tesseract_path(pytesseract)
        _path_configured = True

    return pytesseract


def is_ocr_available() -> bool:
    """Returns True if both pytesseract and the Tesseract binary are usable.

    Caches the result (it can't change mid-session) so callers can check
    this cheaply on every pack refresh.
    """
    global _tesseract_available
    if _tesseract_available is not None:
        return _tesseract_available

    pytesseract = _get_pytesseract()
    if pytesseract is None:
        _tesseract_available = False
        return False

    try:
        version = pytesseract.get_tesseract_version()
        logger.info("Tesseract OCR binary found (version %s).", version)
        _tesseract_available = True
    except Exception as e:
        logger.debug(
            "Tesseract OCR binary not found; card-name OCR disabled. "
            "Command in use: %r. Reason: %s: %s",
            getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract"),
            type(e).__name__,
            e,
        )
        _tesseract_available = False

    return _tesseract_available


def name_region_for_slot(slot_rect: Rect) -> Rect:
    """Returns the crop region for a card's name banner within its slot rect."""
    left, top, right, bottom = slot_rect
    height = bottom - top

    region_top = top + round(height * NAME_REGION_TOP_PCT)
    region_bottom = region_top + round(height * NAME_REGION_HEIGHT_PCT)

    return (left, region_top, right, region_bottom)


def capture_region(rect: Rect) -> Image.Image:
    """Grabs a screenshot of the given absolute screen rect.

    all_screens=True is required on Windows for correct multi-monitor
    capture — without it, ImageGrab only captures the primary display, so
    a rect on a secondary monitor silently grabs whatever's on the primary
    monitor at those coordinates instead (e.g. a different window entirely).
    This is only a fallback for when capture_window() isn't usable — it's
    still vulnerable to other windows overlapping Arena at those coordinates.
    """
    return ImageGrab.grab(bbox=rect, all_screens=True)


# Asks the target window to render its actual current content (rather than
# a generic WM_PRINT fallback), which is required for hardware-accelerated
# apps like Arena (Unity/DirectX) — added in Windows 8.1.
PW_RENDERFULLCONTENT = 2


def _get_win32_capture_api():
    """Lazily imports the win32 capture APIs, returning None on non-Windows platforms."""
    if sys.platform != "win32":
        return None
    import ctypes

    import win32gui
    import win32ui

    return win32gui, win32ui, ctypes


def capture_window(hwnd: int) -> Optional[Image.Image]:
    """Captures a window's content directly via PrintWindow.

    Unlike a screen-region grab, this reads the window's own rendered
    content regardless of what else is on screen — immune to other windows
    overlapping Arena and to multi-monitor coordinate mixups, since it
    operates on the window handle rather than screen coordinates. Returns
    None if window capture isn't supported here (caller should fall back to
    capture_region).
    """
    api = _get_win32_capture_api()
    if api is None:
        return None
    win32gui, win32ui, ctypes = api

    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return None

        window_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(window_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)

        result = ctypes.windll.user32.PrintWindow(
            hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
        )

        bmp_info = bitmap.GetInfo()
        bmp_bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_bits,
            "raw",
            "BGRX",
            0,
            1,
        )

        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)

        if not result:
            logger.debug("PrintWindow reported failure for hwnd %s.", hwnd)
            return None

        return image
    except Exception:
        logger.debug("Window capture via PrintWindow failed.", exc_info=True)
        return None


def recognize_text(image: Image.Image) -> str:
    """Runs OCR on an image and returns the cleaned-up recognized text."""
    pytesseract = _get_pytesseract()
    if pytesseract is None:
        return ""

    # Grayscale + contrast stretch + upscale noticeably improves accuracy on
    # small title text — card name banners vary a lot in color (each card
    # color has its own frame/background), so autocontrast matters more than
    # a fixed threshold would: it adapts per-image instead of assuming a
    # fixed dark-on-light or light-on-dark polarity. 3x (not 2x) because
    # Tesseract's accuracy on small captured game text scales with how large
    # the text ends up, well past what 2x gave it to work with.
    prepared = image.convert("L")
    prepared = ImageOps.autocontrast(prepared)
    prepared = prepared.resize(
        (prepared.width * 3, prepared.height * 3), Image.LANCZOS
    )

    try:
        # --psm 6 (uniform block of text) rather than 7 (a single line):
        # a card name that wraps to two lines makes psm 7's single-line
        # assumption fail outright instead of just reading it noisily.
        text = pytesseract.image_to_string(prepared, config="--psm 6")
    except Exception:
        logger.debug("OCR recognition failed", exc_info=True)
        return ""

    # Collapse a name that wrapped across lines (psm 6 preserves the
    # linebreak) into one space-separated line for matching.
    return " ".join(text.split())


def match_card_name(
    recognized_text: str, candidate_names: List[str]
) -> Optional[str]:
    """Fuzzy-matches OCR'd text against known candidate card names.

    Very short reads (a couple of stray characters) are rejected outright:
    difflib's ratio can cross even a loose cutoff by chance on short strings
    (e.g. "oe" scores 0.5 against "Forest") — that's noise, not a name.
    """
    if not recognized_text or not candidate_names:
        return None
    if len(recognized_text.strip()) < MIN_TEXT_LENGTH_FOR_MATCH:
        return None

    matches = difflib.get_close_matches(
        recognized_text, candidate_names, n=1, cutoff=FUZZY_MATCH_CUTOFF
    )
    return matches[0] if matches else None


def identify_cards_in_pack(
    hwnd: Optional[int],
    arena_rect: Rect,
    slots: List[Rect],
    candidate_names: List[str],
) -> Dict[int, str]:
    """Identifies which candidate card is shown at each slot, in one pass.

    Captures the Arena window once via capture_window (immune to occluding
    windows and multi-monitor coordinate issues) and crops each slot's name
    region out of that single capture, falling back to a per-slot screen
    grab only if window capture isn't usable. Returns a dict of slot index
    -> matched card name, omitting slots OCR couldn't confidently read.
    """
    if not is_ocr_available():
        return {}

    window_image = capture_window(hwnd) if hwnd is not None else None
    origin_x, origin_y, _, _ = arena_rect

    remaining_names = list(candidate_names)
    resolved: Dict[int, str] = {}

    for index, slot in enumerate(slots):
        region = name_region_for_slot(slot)
        if window_image is not None:
            crop_box = (
                region[0] - origin_x,
                region[1] - origin_y,
                region[2] - origin_x,
                region[3] - origin_y,
            )
            image = window_image.crop(crop_box)
        else:
            image = capture_region(region)

        recognized_text = recognize_text(image)
        matched = match_card_name(recognized_text, remaining_names)
        logger.debug(
            "OCR slot %s: raw text %r -> matched %r", slot, recognized_text, matched
        )
        if matched is not None:
            resolved[index] = matched
            remaining_names.remove(matched)

    return resolved
