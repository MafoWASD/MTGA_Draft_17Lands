from unittest.mock import MagicMock

from src import constants
from src.advisor.schema import Recommendation
from src.arena_mod_bridge import ArenaModBridge


def _make_recommendation(card_name, contextual_score, base_win_rate):
    return Recommendation(
        card_name=card_name,
        base_win_rate=base_win_rate,
        contextual_score=contextual_score,
        z_score=0.0,
        cast_probability=1.0,
        wheel_chance=0.0,
        functional_cmc=2.0,
        reasoning=[],
    )


def _make_bridge():
    """Builds an ArenaModBridge without spinning up ArenaModClient's real
    background polling thread or touching the filesystem."""
    bridge = ArenaModBridge.__new__(ArenaModBridge)
    bridge._client = MagicMock()
    return bridge


def test_update_data_writes_scores_keyed_by_arena_id():
    bridge = _make_bridge()
    pack_cards = [
        {
            constants.DATA_FIELD_NAME: "Lightning Strike",
            constants.DATA_FIELD_ARENA_ID: "12345",
        },
        {
            constants.DATA_FIELD_NAME: "Giant Growth",
            constants.DATA_FIELD_ARENA_ID: "67890",
        },
    ]
    recommendations = [
        _make_recommendation("Lightning Strike", 84.6, 61.2),
        _make_recommendation("Giant Growth", 42.0, 50.5),
    ]

    bridge.update_data(pack_cards, recommendations)

    bridge._client.write_scores.assert_called_once_with(
        {
            12345: {"value": 85, "gihwr": 61.2},
            67890: {"value": 42, "gihwr": 50.5},
        }
    )


def test_update_data_skips_cards_without_a_recommendation():
    bridge = _make_bridge()
    pack_cards = [
        {
            constants.DATA_FIELD_NAME: "Unscored Card",
            constants.DATA_FIELD_ARENA_ID: "111",
        }
    ]

    bridge.update_data(pack_cards, recommendations=[])

    bridge._client.write_scores.assert_called_once_with({})


def test_update_data_skips_cards_missing_an_arena_id():
    bridge = _make_bridge()
    pack_cards = [{constants.DATA_FIELD_NAME: "No ID Card"}]
    recommendations = [_make_recommendation("No ID Card", 50.0, 55.0)]

    bridge.update_data(pack_cards, recommendations)

    bridge._client.write_scores.assert_called_once_with({})


def test_update_data_handles_empty_pack():
    bridge = _make_bridge()

    bridge.update_data([], [])

    bridge._client.write_scores.assert_called_once_with({})


def test_destroy_stops_the_client():
    bridge = _make_bridge()

    bridge.destroy()

    bridge._client.stop.assert_called_once()
