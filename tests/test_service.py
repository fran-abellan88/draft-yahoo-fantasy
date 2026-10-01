"""Tests for the dashboard's service layer: what the page receives for a given draft state."""

from typing import Any, Dict, List

import pytest

from fantasy_draft.data import load_players
from fantasy_draft.draft import DraftState, my_picks
from fantasy_draft.service import DraftService, RequestError, parse_rule

ALL = ["fg_pct", "ft_pct", "3ptm", "pts", "reb", "ast", "st", "blk", "to"]


@pytest.fixture(scope="module")
def service() -> DraftService:
    return DraftService(load_players())


def _ids_by_xrank(service: DraftService) -> List[str]:
    return service.players.sort_values("xrank")["player_id"].tolist()


def _ask(service: DraftService, picks: List[str], **extra: Any) -> Dict[str, Any]:
    return service.analyze({"categories": ALL, "picks": picks, **extra})


def test_pool_payload_describes_the_league_and_every_player(service: DraftService) -> None:
    payload = service.pool_payload()
    assert payload["league"] == {"teams": 14, "slot": 2, "rounds": 8, "rosterSize": 13}
    assert payload["myPicks"][:8] == [2, 27, 30, 55, 58, 83, 86, 111]
    assert [c["key"] for c in payload["categories"]] == ALL
    assert next(c for c in payload["categories"] if c["key"] == "to")["lowerIsBetter"] is True
    assert len(payload["players"]) == 150
    jokic = next(p for p in payload["players"] if p["id"] == "nikola-jokic")
    assert jokic["positions"] == ["C"] and jokic["xrank"] == 1
    assert jokic["lastSeason"]["gp"] == 65
    haliburton = next(p for p in payload["players"] if p["id"] == "tyrese-haliburton")
    assert haliburton["lastSeason"] is None


def test_the_payload_is_json_safe(service: DraftService) -> None:
    import json

    json.dumps(service.pool_payload(), allow_nan=False)
    json.dumps(_ask(service, []), allow_nan=False)


def test_opening_state(service: DraftService) -> None:
    result = _ask(service, [])
    assert result["clock"]["pick"] == 1 and not result["clock"]["isMine"]
    assert result["clock"]["nextMyPick"] == 2 and result["clock"]["picksUntilMine"] == 1
    assert [row["rank"] for row in result["pool"]] == list(range(1, 151))
    assert result["recommendation"]["pick"] == 2
    assert 1 <= len(result["plans"]) <= 5
    assert result["plans"][0]["steps"][0]["pick"] == 2
    assert result["profile"]["roster"] is None and result["profile"]["plan"] is not None
    assert not result["horizonDone"]


def test_when_it_is_my_turn_every_remaining_player_is_available(service: DraftService) -> None:
    first = _ids_by_xrank(service)[0]
    result = _ask(service, [first])
    assert result["clock"]["pick"] == 2 and result["clock"]["isMine"]
    assert all(row["availability"] == 1.0 for row in result["pool"])
    assert first not in {row["id"] for row in result["pool"]}
    assert result["recommendation"]["pick"] == 2
    assert result["recommendation"]["id"] != first


def test_my_picks_are_identified_by_the_snake_order(service: DraftService) -> None:
    ids = _ids_by_xrank(service)
    result = _ask(service, ids[:3])  # pick 1 other, pick 2 mine, pick 3 other
    assert result["roster"] == [{"id": ids[1], "pick": 2}]
    assert [entry["mine"] for entry in result["log"]] == [False, True, False]
    assert result["profile"]["roster"] is not None


def test_plans_never_contain_a_drafted_player(service: DraftService) -> None:
    ids = _ids_by_xrank(service)
    drafted = set(ids[:14])
    result = _ask(service, ids[:14])
    for plan in result["plans"]:
        assert not drafted & {step["id"] for step in plan["steps"]}


def test_unticking_a_category_changes_the_scores(service: DraftService) -> None:
    all_scores = {row["id"]: row["score"] for row in _ask(service, [])["pool"]}
    without = service.analyze({"categories": [c for c in ALL if c != "to"], "picks": []})
    assert {row["id"]: row["score"] for row in without["pool"]} != all_scores
    assert "to" not in without["pool"][0]["categoryScores"]
    assert set(without["profile"]["plan"]) == set(ALL) - {"to"}


def test_flags_reach_the_page(service: DraftService) -> None:
    rows = {row["id"]: row for row in _ask(service, [])["pool"]}
    assert rows["tyrese-haliburton"]["flags"]["noLastSeason"]
    assert rows["walker-kessler"]["flags"]["smallSample"]
    assert rows["joel-embiid"]["flags"]["lowGames"]
    assert rows["tyrese-haliburton"]["lastSeasonScore"] is None


def test_the_window_rule_gives_a_different_answer_shape(service: DraftService) -> None:
    result = _ask(service, [], rule={"type": "window", "slack": 3})
    probabilities = {step["availability"] for plan in result["plans"] for step in plan["steps"]}
    assert probabilities <= {0.0, 1.0}


def test_after_my_last_planned_pick_there_is_no_recommendation(service: DraftService) -> None:
    ids = _ids_by_xrank(service)[:111]  # picks 1..111, so the eighth-round pick is made
    result = _ask(service, ids)
    assert result["horizonDone"] and result["recommendation"] is None and result["plans"] == []
    assert result["clock"]["nextMyPick"] == 114
    assert all(row["availability"] is None for row in result["pool"])


def test_the_clock_knows_when_the_draft_is_over(service: DraftService) -> None:
    clock = service._clock(DraftState(taken=frozenset(str(i) for i in range(182))))
    assert clock["draftComplete"]


def test_snake_direction_flips_each_round(service: DraftService) -> None:
    assert service._clock(DraftState(taken=frozenset(str(i) for i in range(13))))["reversed"] is False  # pick 14
    clock = service._clock(DraftState(taken=frozenset(str(i) for i in range(14))))  # pick 15, round 2
    assert clock["reversed"] is True and clock["slotOnClock"] == 14 and clock["round"] == 2


@pytest.mark.parametrize(
    "request_body, message",
    [
        ({"categories": [], "picks": []}, "at least one"),
        ({"categories": ["dunks"], "picks": []}, "Unknown categories"),
        ({"categories": ["pts", "pts"], "picks": []}, "twice"),
        ({"categories": "pts", "picks": []}, "at least one"),
        ({"categories": ALL, "picks": ["nobody"]}, "Unknown players"),
        ({"categories": ALL, "picks": ["nikola-jokic", "nikola-jokic"]}, "picked twice"),
        ({"categories": ALL, "picks": "nikola-jokic"}, "list of player ids"),
        ({"categories": ALL, "picks": [], "rule": {"type": "magic"}}, "Unknown availability rule"),
        ({"categories": ALL, "picks": [], "rule": {"type": "window", "slack": -1}}, "slack"),
        ({"categories": ALL, "picks": [], "rule": {"type": "probability", "threshold": "high"}}, "threshold"),
        ({"categories": ALL, "picks": [], "topK": 100000}, "topK"),
    ],
)
def test_bad_requests_are_rejected_with_a_readable_message(service: DraftService, request_body: Dict[str, Any], message: str) -> None:
    with pytest.raises(RequestError, match=message):
        service.analyze(request_body)


def test_rule_defaults_and_bounds() -> None:
    assert parse_rule(None).threshold == 0.5
    assert parse_rule({"type": "window"}).slack == 3.0
    with pytest.raises(RequestError):
        parse_rule({"type": "probability", "baseSd": True})


def test_my_picks_helper_agrees_with_the_service(service: DraftService) -> None:
    assert service.pool_payload()["myPicks"] == my_picks(2, 13)


def test_games_adjustment_lowers_scores_of_players_projected_to_miss_games(service: DraftService) -> None:
    plain = {row["id"]: row["score"] for row in _ask(service, [])["pool"]}
    adjusted = {row["id"]: row["score"] for row in _ask(service, [], gamesAdjusted=True)["pool"]}
    gp = service.players.set_index("player_id")["gp"]
    for pid, score in plain.items():
        expected = score * min(gp[pid], 82) / 82
        assert adjusted[pid] == pytest.approx(expected, abs=0.1), pid
    assert any(adjusted[pid] < plain[pid] - 5 for pid in plain)


@pytest.mark.parametrize("value", ["yes", 1, None])
def test_games_adjustment_must_be_a_boolean(service: DraftService, value: Any) -> None:
    with pytest.raises(RequestError, match="gamesAdjusted"):
        _ask(service, [], gamesAdjusted=value)


def test_uncapped_method_ranks_differently_from_capped_and_can_exceed_100(service: DraftService) -> None:
    capped = {row["id"]: row["score"] for row in _ask(service, [])["pool"]}
    uncapped = {row["id"]: row["score"] for row in _ask(service, [], method="uncapped")["pool"]}
    assert max(capped.values()) <= 100 and capped != uncapped
    assert uncapped["nikola-jokic"] > capped["nikola-jokic"]  # nothing is clamped away for the best player


def test_method_plans_use_the_chosen_scale(service: DraftService) -> None:
    capped = _ask(service, [])["plans"][0]["totalScore"]
    uncapped = _ask(service, [], method="uncapped")["plans"][0]["totalScore"]
    assert uncapped != capped


@pytest.mark.parametrize("value", ["rank", 1, None])
def test_method_must_be_a_known_one(service: DraftService, value: Any) -> None:
    with pytest.raises(RequestError, match="method"):
        _ask(service, [], method=value)
