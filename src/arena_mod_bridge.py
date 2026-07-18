"""
src/arena_mod_bridge.py
Bridges live pack/recommendation data to the Arena Pack Overlay Mod
(bepinex_mod/), which renders VALUE score badges natively inside Arena's
own UI. Replaces an earlier Tkinter overlay window + OCR-based screen
reading (src/card_name_ocr.py, src/ui/windows/arena_overlay.py,
src/arena_window.py, src/overlay_layout.py) — position resolution AND
rendering both now happen inside the mod itself, reading the game's own
draft data (Wotc.Mtga.Wrapper.Draft.DraftPackHolder.LayoutCards) instead of
guessing from the draft log's arbitrary card order or screen-scraping.
"""

from typing import List

from src import constants
from src.arena_mod_client import ArenaModClient
from src.logger import create_logger

logger = create_logger()


class ArenaModBridge:
    """Owns the connection to the mod and pushes VALUE/GIHWR scores to it.

    No Tkinter window: badge rendering happens inside Arena's own process
    (bepinex_mod/src/BadgeRenderPatch.cs). This class only computes and
    sends the numbers.
    """

    def __init__(self):
        self._client = ArenaModClient()

    def update_data(self, pack_cards: List[dict], recommendations) -> None:
        rec_by_name = {r.card_name: r for r in (recommendations or [])}

        scores = {}
        for card in pack_cards or []:
            arena_id = card.get(constants.DATA_FIELD_ARENA_ID)
            if not arena_id:
                continue
            try:
                grp_id = int(arena_id)
            except (TypeError, ValueError):
                continue

            recommendation = rec_by_name.get(card.get(constants.DATA_FIELD_NAME))
            if recommendation is None:
                continue

            scores[grp_id] = {
                "value": round(recommendation.contextual_score),
                "gihwr": recommendation.base_win_rate,
            }

        self._client.write_scores(scores)

    def destroy(self) -> None:
        self._client.stop()
