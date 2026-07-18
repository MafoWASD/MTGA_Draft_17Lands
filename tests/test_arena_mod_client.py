import json
import os
import tempfile
import time

import pytest

import src.arena_mod_client as arena_mod_client
from src.arena_mod_client import ArenaModClient


@pytest.fixture
def temp_data_paths(monkeypatch):
    """Points the module's file-based IPC at an isolated temp directory,
    sidestepping pytest's own tmp_path fixture (broken in this environment -
    see other test files' PermissionError on pytest-of-<user>)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        data_dir = os.path.join(tmp_dir, "ArenaPackOverlayMod")
        data_file = os.path.join(data_dir, "pack_layout.json")
        scores_file = os.path.join(data_dir, "scores.json")
        monkeypatch.setattr(arena_mod_client, "DATA_DIR", data_dir)
        monkeypatch.setattr(arena_mod_client, "DATA_FILE", data_file)
        monkeypatch.setattr(arena_mod_client, "SCORES_FILE", scores_file)
        yield data_dir, data_file, scores_file


def _write_pack_layout(path, slots, with_bom=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = json.dumps({"schema_version": 1, "slots": slots})
    encoding = "utf-8-sig" if with_bom else "utf-8"
    with open(path, "w", encoding=encoding) as f:
        f.write(payload)


def test_is_connected_false_when_no_file_exists(temp_data_paths):
    client = ArenaModClient()
    client.stop()

    client._poll_once()

    assert client.is_connected() is False
    assert client.latest_slots() == {}


def test_poll_once_reads_a_fresh_pack_layout_file(temp_data_paths):
    _data_dir, data_file, _scores_file = temp_data_paths
    _write_pack_layout(
        data_file,
        [{"index": 0, "grp_id": 98453}, {"index": 1, "grp_id": 98326}],
    )

    client = ArenaModClient()
    client.stop()
    client._poll_once()

    assert client.is_connected() is True
    assert client.latest_slots() == {0: 98453, 1: 98326}


def test_poll_once_handles_dotnet_bom_encoding(temp_data_paths):
    """.NET's File.WriteAllText(..., Encoding.UTF8) writes a BOM - the real
    failure mode this project hit against the live mod (plain utf-8
    decoding leaves the BOM character in the string and json.loads chokes
    on it)."""
    _data_dir, data_file, _scores_file = temp_data_paths
    _write_pack_layout(data_file, [{"index": 0, "grp_id": 111}], with_bom=True)

    client = ArenaModClient()
    client.stop()
    client._poll_once()

    assert client.latest_slots() == {0: 111}


def test_poll_once_ignores_a_torn_write(temp_data_paths):
    _data_dir, data_file, _scores_file = temp_data_paths
    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        f.write('{"schema_version": 1, "slots": [{"index": 0')  # truncated

    client = ArenaModClient()
    client.stop()
    client._poll_once()

    assert client.is_connected() is False
    assert client.latest_slots() == {}


def test_is_connected_goes_stale_after_the_timeout(temp_data_paths, monkeypatch):
    _data_dir, data_file, _scores_file = temp_data_paths
    _write_pack_layout(data_file, [{"index": 0, "grp_id": 1}])
    monkeypatch.setattr(arena_mod_client, "STALE_AFTER_SEC", 0.05)

    client = ArenaModClient()
    client.stop()
    client._poll_once()
    assert client.is_connected() is True

    time.sleep(0.1)
    assert client.is_connected() is False


def test_write_scores_produces_a_file_the_mod_style_reader_can_parse(temp_data_paths):
    _data_dir, _data_file, scores_file = temp_data_paths
    client = ArenaModClient()
    client.stop()

    client.write_scores({98453: {"value": 85, "gihwr": 62.3}, 98326: {"value": 40, "gihwr": 51.0}})

    with open(scores_file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    assert payload == {
        "98453": {"value": 85, "gihwr": 62.3},
        "98326": {"value": 40, "gihwr": 51.0},
    }
