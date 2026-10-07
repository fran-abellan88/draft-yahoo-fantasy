"""My adjustments: parsing, what they do to scores and plans, and the commentator notes file."""

from typing import Any, Dict, List

import pytest

from fantasy_draft.adjustments import Adjustment, apply_adjustments, parse_adjustments
from fantasy_draft.data import load_players
from fantasy_draft.notes import KINDS, NOTES_PATH, load_notes
from fantasy_draft.service import DraftService, RequestError, parse_rule

KNOWN = {"a", "b", "c"}


@pytest.fixture(scope="module")
def service() -> DraftService:
    return DraftService(load_players())


def _entry(player: str = "a", **extra: Any) -> Dict[str, Any]:
    return {"id": "x", "player": player, "games": 40, "offset": 0, **extra}


def _ask(service: DraftService, adjustments: List[Dict[str, Any]], picks: Any = (), **extra: Any) -> Dict[str, Any]:
    request = {"categories": service.keys, "picks": list(picks), "method": "uncapped", "gamesAdjusted": True, "adjustments": adjustments}
    return service.analyze({**request, **extra})


def test_enabled_adjustments_are_returned_and_switched_off_ones_are_only_checked() -> None:
    parsed = parse_adjustments([_entry("a"), _entry("b", games=None, offset=-2.5), _entry("c", enabled=False)], KNOWN)
    assert parsed == [Adjustment("a", 40.0, 0.0), Adjustment("b", None, -2.5)]
    with pytest.raises(ValueError, match="unknown player"):
        parse_adjustments([_entry("zzz", enabled=False)], KNOWN)


@pytest.mark.parametrize(
    "bad,message",
    [
        (_entry(games=83), "games"),
        (_entry(games=-1), "games"),
        (_entry(games=True), "games"),
        (_entry(offset=31), "offset"),
        (_entry(offset="3"), "offset"),
        (_entry(games=None, offset=0), "give expected games"),
        (_entry(note="x" * 301), "note"),
        (_entry(enabled="yes"), "enabled"),
        ("text", "object"),
    ],
)
def test_an_adjustment_that_makes_no_sense_is_refused(bad: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_adjustments([bad], KNOWN)


def test_two_enabled_adjustments_for_one_player_are_refused() -> None:
    with pytest.raises(ValueError, match="already has"):
        parse_adjustments([_entry("a"), _entry("a", games=30)], KNOWN)
    assert parse_adjustments([_entry("a"), _entry("a", games=30, enabled=False)], KNOWN) == [Adjustment("a", 40.0, 0.0)]


def test_applying_adjustments_changes_a_copy_and_not_the_pool(service: DraftService) -> None:
    before = service.players.copy()
    adjusted = apply_adjustments(service.players, [Adjustment("nikola-jokic", 30.0, 2.0)])
    row = adjusted["player_id"] == "nikola-jokic"
    assert adjusted.loc[row, "gp"].iloc[0] == 30 and adjusted.loc[row, "score_offset"].iloc[0] == 2.0
    assert adjusted.loc[~row, "score_offset"].eq(0).all()
    assert service.players.equals(before) and "score_offset" not in service.players.columns


def test_an_offset_moves_the_score_by_exactly_those_points(service: DraftService) -> None:
    plain = {row["id"]: row for row in _ask(service, [])["pool"]}
    moved = {row["id"]: row for row in _ask(service, [{"id": "o", "player": "jalen-duren", "offset": -4.0}])["pool"]}
    assert moved["jalen-duren"]["score"] == pytest.approx(plain["jalen-duren"]["score"] - 4.0, abs=0.1)
    assert moved["jalen-duren"]["adjusted"] == {"games": None, "offset": -4.0}
    assert moved["nikola-jokic"]["score"] == plain["nikola-jokic"]["score"] and moved["nikola-jokic"]["adjusted"] is None


def test_expected_games_count_only_while_games_are_counted(service: DraftService) -> None:
    entry = [{"id": "g", "player": "nikola-jokic", "games": 20}]
    plain = {row["id"]: row["score"] for row in _ask(service, [])["pool"]}
    counted = {row["id"]: row["score"] for row in _ask(service, entry)["pool"]}
    ignored = {row["id"]: row["score"] for row in _ask(service, entry, gamesAdjusted=False)["pool"]}
    assert counted["nikola-jokic"] < plain["nikola-jokic"] - 20, "20 games of 70 is a heavy discount"
    plain_off = {row["id"]: row["score"] for row in _ask(service, [], gamesAdjusted=False)["pool"]}
    assert ignored["nikola-jokic"] == plain_off["nikola-jokic"]


def test_the_plan_follows_the_adjustment(service: DraftService) -> None:
    free = _ask(service, [])
    assert free["plans"][0]["steps"][0]["id"] == "nikola-jokic"
    hurt = _ask(service, [{"id": "h", "player": "nikola-jokic", "games": 20, "offset": -5}])
    assert hurt["plans"][0]["steps"][0]["id"] != "nikola-jokic"


def test_the_other_teams_are_planned_without_my_adjustments(service: DraftService) -> None:
    hurt = [{"id": "h", "player": "nikola-jokic", "games": 20, "offset": -10}]
    assert service._for_request({"adjustments": hurt}) is not service
    mine = service._for_request({"adjustments": hurt})
    rule = {"type": "probability"}
    plain = service._for_request({})
    for slot in (1, 3):  # rivals take the same pick whether or not I adjusted anyone
        assert mine._planner_choice(slot, [], service.keys, parse_rule(rule), "uncapped", True) == plain._planner_choice(
            slot, [], service.keys, parse_rule(rule), "uncapped", True
        )
    assert mine._planner_choice(1, [], service.keys, parse_rule(rule), "uncapped", True) == "nikola-jokic"


def test_variants_are_cached_and_bounded(service: DraftService) -> None:
    first = service._for_request({"adjustments": [{"id": "1", "player": "jalen-duren", "offset": 1}]})
    again = service._for_request({"adjustments": [{"id": "2", "player": "jalen-duren", "offset": 1}]})
    assert first is again, "the same adjustments, whatever their ids, are one variant"
    for offset in range(1, 20):
        service._for_request({"adjustments": [{"id": "n", "player": "jalen-duren", "offset": float(offset)}]})
    assert len(service._variants) <= 12


def test_a_wrong_adjustment_in_a_request_is_a_request_error(service: DraftService) -> None:
    with pytest.raises(RequestError, match="adjustment 1"):
        _ask(service, [{"id": "x", "player": "nobody", "offset": 1}])


def test_the_notes_file_matches_the_pool_and_every_row_has_a_source() -> None:
    notes = load_notes(load_players())
    assert len(notes) >= 30
    assert all(note["kind"] in KINDS and note["note"] and note["source"] for note in notes)
    suggested = [note for note in notes if "games" in note or "offset" in note]
    assert all(0 <= note.get("games", 0) <= 82 and -30 <= note.get("offset", 0) <= 30 for note in suggested)
    assert NOTES_PATH.exists()


def test_a_note_for_a_player_not_in_the_pool_is_refused(tmp_path: Any) -> None:
    path = tmp_path / "notes.csv"
    path.write_text("player,kind,note,source,games,offset\nNobody Atall,injury,out,somewhere,,\n")
    with pytest.raises(ValueError, match="not in the player pool"):
        load_notes(load_players(), path)
    path.write_text("player,kind,note,source,games,offset\nNikola Jokic,gossip,out,somewhere,,\n")
    with pytest.raises(ValueError, match="kind must be"):
        load_notes(load_players(), path)


def test_the_notes_mark_the_players_to_leave_alone_and_they_are_all_in_the_pool() -> None:
    notes = load_notes(load_players())
    flagged = sorted({note["player"] for note in notes if note.get("exclude")})
    assert flagged == [
        "brandon-ingram", "coby-white", "jimmy-butler-iii", "kon-knueppel", "kristaps-porzingis", "nic-claxton", "tobias-harris"
    ]
    assert all(note["kind"] == "injury" for note in notes if note.get("exclude"))


def test_a_notes_file_without_the_exclude_column_still_loads(tmp_path: Any) -> None:
    path = tmp_path / "notes.csv"
    path.write_text("player,kind,note,source,games,offset\nNikola Jokic,injury,out,somewhere,,\n")
    assert load_notes(load_players(), path) == [{"player": "nikola-jokic", "kind": "injury", "note": "out", "source": "somewhere"}]
