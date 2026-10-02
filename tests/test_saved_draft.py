"""Tests for the saved draft file: atomic writes, versions, limits and an unusable file."""

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from fantasy_draft.saved_draft import MAX_BYTES, MAX_PICKS, Conflict, SavedDraft, SavedDraftError


@pytest.fixture()
def saved(tmp_path: Path) -> SavedDraft:
    return SavedDraft(tmp_path / "saved_draft.json")


STATE: Dict[str, Any] = {"version": 2, "picks": [{"kind": "player", "id": "a"}], "history": [], "categories": ["pts"]}


def test_with_no_file_there_is_no_draft_and_version_zero(saved: SavedDraft) -> None:
    assert saved.load() == (0, None, None)


def test_a_save_stores_the_state_and_raises_the_version_by_one(saved: SavedDraft) -> None:
    assert saved.save(STATE, 0) == 1
    assert saved.save({**STATE, "picks": []}, 1) == 2
    assert saved.load() == (2, {**STATE, "picks": []}, None)


def test_a_save_based_on_an_older_version_is_refused_and_leaves_the_file_alone(saved: SavedDraft) -> None:
    saved.save(STATE, 0)
    with pytest.raises(Conflict) as refused:
        saved.save({**STATE, "picks": []}, 0)
    assert refused.value.current == 1
    assert saved.load()[1] == STATE


TOO_BIG = [{"picks": [{}] * (MAX_PICKS + 1)}, {"history": "x" * MAX_BYTES}]


@pytest.mark.parametrize("state", ["x", [], {"picks": "no"}, {"unknown": 1}, *TOO_BIG])
def test_a_state_of_the_wrong_shape_or_size_is_refused(saved: SavedDraft, state: Any) -> None:
    with pytest.raises(SavedDraftError):
        saved.save(state, 0)
    assert not saved.path.exists()


@pytest.mark.parametrize("base", [None, "0", 0.5, True])
def test_the_base_version_must_be_a_whole_number(saved: SavedDraft, base: Any) -> None:
    with pytest.raises(SavedDraftError):
        saved.save(STATE, base)


def test_the_file_is_replaced_atomically_and_leaves_no_temporary_file(saved: SavedDraft) -> None:
    saved.save(STATE, 0)
    saved.save(STATE, 1)
    assert [path.name for path in saved.path.parent.iterdir()] == ["saved_draft.json"]


def test_a_failed_write_keeps_the_previous_draft(saved: SavedDraft, monkeypatch: pytest.MonkeyPatch) -> None:
    saved.save(STATE, 0)

    def fail(source: Any, target: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("fantasy_draft.saved_draft.os.replace", fail)
    with pytest.raises(OSError):
        saved.save({**STATE, "picks": []}, 1)
    monkeypatch.undo()
    assert saved.load()[1] == STATE
    assert not [path for path in saved.path.parent.iterdir() if path.suffix == ".tmp"], "the temporary file is removed"


UNUSABLE = [b"not json", b"[]", b'{"version": 1}', b'{"version": "1", "state": {}}', b'{"version": 1, "state": {"x": 1}}']


@pytest.mark.parametrize("contents", UNUSABLE)
def test_an_unusable_file_is_reported_and_set_aside_on_the_next_save_not_overwritten(saved: SavedDraft, contents: bytes) -> None:
    saved.path.write_bytes(contents)
    version, state, problem = saved.load()
    assert (version, state) == (0, None) and problem and "set aside" in problem
    assert saved.path.read_bytes() == contents, "reading does not touch it"
    assert saved.save(STATE, 0) == 1
    assert saved.path.with_suffix(".unreadable.json").read_bytes() == contents, "the old content is kept"
    assert json.loads(saved.path.read_text())["version"] == 1


def test_a_save_that_empties_a_draft_with_picks_keeps_the_old_file(saved: SavedDraft) -> None:
    saved.save(STATE, 0)
    saved.save({**STATE, "picks": []}, 1)
    previous = json.loads(saved.path.with_suffix(".previous.json").read_text())
    assert previous["state"]["picks"] == STATE["picks"] and previous["version"] == 1
    assert saved.load()[1]["picks"] == []


def test_ordinary_saves_leave_no_previous_file(saved: SavedDraft) -> None:
    saved.save({**STATE, "picks": []}, 0)  # empty into nothing
    saved.save(STATE, 1)  # filling an empty draft
    saved.save({**STATE, "history": [{"type": "log", "count": 1}]}, 2)  # editing one with picks
    assert not saved.path.with_suffix(".previous.json").exists()
