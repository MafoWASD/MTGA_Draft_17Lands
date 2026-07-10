"""
src/card_name_ocr.py
Reads a card's name off the live Arena screen via OCR, for cases where the
draft log's pack-card order doesn't match Arena's on-screen grid position.
"""

import difflib
import os
from typing import List, Optional, Tuple

from PIL import Image, ImageGrab

from src.logger import create_logger

logger = create_logger()

Rect = Tuple[int, int, int, int]  # (left, top, right, bottom) in screen pixels

# The card name sits in a banner near the top of the card art, not the full
# card. Cropping tightly to it (rather than OCR'ing the whole card) avoids
# reading art/rules text and keeps recognition fast.
NAME_REGION_TOP_PCT = 0.02
NAME_REGION_HEIGHT_PCT = 0.16

FUZZY_MATCH_CUTOFF = 0.5

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
    """Grabs a screenshot of the given absolute screen rect."""
    return ImageGrab.grab(bbox=rect)


def recognize_text(image: Image.Image) -> str:
    """Runs OCR on an image and returns the cleaned-up recognized text."""
    pytesseract = _get_pytesseract()
    if pytesseract is None:
        return ""

    # Upscaling + grayscale noticeably improves accuracy on small title text.
    prepared = image.convert("L")
    prepared = prepared.resize((prepared.width * 2, prepared.height * 2))

    try:
        text = pytesseract.image_to_string(prepared, config="--psm 7")
    except Exception:
        logger.debug("OCR recognition failed", exc_info=True)
        return ""

    return text.strip()


def match_card_name(
    recognized_text: str, candidate_names: List[str]
) -> Optional[str]:
    """Fuzzy-matches OCR'd text against known candidate card names."""
    if not recognized_text or not candidate_names:
        return None

    matches = difflib.get_close_matches(
        recognized_text, candidate_names, n=1, cutoff=FUZZY_MATCH_CUTOFF
    )
    return matches[0] if matches else None


def identify_card_at_slot(
    slot_rect: Rect, candidate_names: List[str]
) -> Optional[str]:
    """Captures, OCRs, and fuzzy-matches the card name shown at a slot.

    Returns the best-matching name from `candidate_names`, or None if OCR is
    unavailable or nothing matched closely enough.
    """
    if not is_ocr_available():
        return None

    region = name_region_for_slot(slot_rect)
    image = capture_region(region)
    recognized_text = recognize_text(image)
    matched = match_card_name(recognized_text, candidate_names)
    logger.debug(
        "OCR slot %s (crop %s): raw text %r -> matched %r",
        slot_rect,
        region,
        recognized_text,
        matched,
    )
    return matched
