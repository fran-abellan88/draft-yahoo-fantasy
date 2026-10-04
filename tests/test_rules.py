"""Tests for my own pick rules: parsing, the filter on candidates, and what the service shows for them."""

from typing import Any, Dict, List

import pytest

from fantasy_draft.data import load_players
from fantasy_draft.rules import PickRule, parse_rules, restrict, rule_states
from fantasy_draft.service import DraftService, RequestError, parse_rule

MINE = [2, 27, 30, 55, 58, 83, 86, 111]
KNOWN = {"a", "b", "c", "d"}


@pytest.fixture(scope="module")
def service() -> DraftService:
    return DraftService(load_players())


def _rule(kind: str, players: List[str], first: int = 1, last: Any = None, **extra: Any) -> Dict[str, Any]:
    return {"id": "x", "kind": kind, "players": players, "from": first, "to": last, **extra}


def _ask(service: DraftService, rules: List[Dict[str, Any]], picks: Any = ()) -> Dict[str, Any]:
    return service.analyze({"categories": service.keys, "picks": list(picks), "method": "uncapped", "gamesAdjusted": True, "rules": rules})


def test_ranges_count_my_picks_and_a_missing_end_runs_to_my_last() -> None:
    rules = parse_rules([_rule("avoid", ["a"], 1, 3), _rule("only", ["b"], 2, 2), _rule("avoid", ["c"], 6)], KNOWN, MINE)
    assert [sorted(rule.picks) for rule in rules] == [[2, 27, 30], [27], [83, 86, 111]]


def test_a_switched_off_rule_is_checked_but_not_used() -> None:
    assert parse_rules([_rule("avoid", ["a"], enabled=False)], KNOWN, MINE) == []
    with pytest.raises(ValueError, match="unknown players"):
        parse_rules([_rule("avoid", ["zzz"], enabled=False)], KNOWN, MINE)


@pytest.mark.parametrize(
    "bad,message",
    [
        (_rule("never", ["a"]), "kind"),
        (_rule("avoid", []), "players"),
        (_rule("avoid", ["a"], 0), "from"),
        (_rule("avoid", ["a"], 9), "from"),
        (_rule("avoid", ["a"], True), "from"),
        (_rule("avoid", ["a"], 3, 2), "before"),
        (_rule("avoid", ["a"], 1, 99), "to"),
        (_rule("avoid", ["a"], enabled="yes"), "enabled"),
    ],
)
def test_a_rule_that_makes_no_sense_is_refused(bad: Dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_rules([bad], KNOWN, MINE)


def test_only_keeps_the_listed_players_and_avoid_removes_them() -> None:
    only = PickRule("o", "only", frozenset({"a", "b"}), frozenset({2}))
    avoid = PickRule("v", "avoid", frozenset({"a"}), frozenset({2, 27}))
    assert restrict([only], 2, ["a", "b", "c"]) == {"a", "b"}
    assert restrict([only], 27, ["a", "b", "c"]) is None
    assert restrict([only, avoid], 2, ["a", "b", "c"]) == {"b"}
    assert restrict([avoid], 27, ["a", "c"]) == {"c"}
    assert restrict([only], 2, ["c"]) == set()  # nobody left: the caller drops the rule for this pick


def test_rule_states_say_when_a_rule_is_spent_or_could_not_be_met() -> None:
    only = PickRule("o", "only", frozenset({"a", "b"}), frozenset({2}))
    avoid = PickRule("v", "avoid", frozenset({"c"}), frozenset({27, 30}))
    assert rule_states([only, avoid], set(), 2, set()) == {"o": "active", "v": "active"}
    assert rule_states([only, avoid], set(), 27, set()) == {"o": "moot", "v": "active"}  # the pick is past
    assert rule_states([only, avoid], {"c"}, 2, set()) == {"o": "active", "v": "moot"}  # everyone he bans is gone
    assert rule_states([only], {"a", "b"}, 2, {2}) == {"o": "moot"}
    assert rule_states([only], {"a"}, 2, {2}) == {"o": "unmet"}


def test_a_rule_names_the_pick_and_the_plan_follows_it(service: DraftService) -> None:
    free = _ask(service, [])
    first = free["plans"][0]["steps"][0]["id"]
    other = free["alternatives"][0]["id"]
    ruled = _ask(service, [_rule("avoid", [first], 1, 1)])
    assert ruled["plans"][0]["steps"][0]["id"] != first
    only = _ask(service, [_rule("only", [other], 1, 1)])
    assert only["plans"][0]["steps"][0]["id"] == other
    assert only["recommendation"]["id"] == other
    assert [entry["state"] for entry in only["rules"]] == ["active"]
    assert only["rulesImpact"]["cost"] >= 0
    assert only["rulesImpact"]["without"] == first


def test_an_avoided_player_is_still_planned_where_the_rule_does_not_reach(service: DraftService) -> None:
    ruled = _ask(service, [_rule("avoid", ["nikola-jokic"], 1, 1)])
    assert "nikola-jokic" not in [step["id"] for step in ruled["plans"][0]["steps"][:1]]
    row = next(row for row in ruled["pool"] if row["id"] == "nikola-jokic")
    assert row["blocked"] is True
    assert all(not row["blocked"] for row in _ask(service, [])["pool"])


def test_an_only_rule_nobody_can_meet_is_dropped_and_reported(service: DraftService) -> None:
    first = service.players.sort_values("xrank")["player_id"].tolist()[0]
    held = _ask(service, [_rule("only", [first], 1, 1)])
    assert held["plans"][0]["steps"][0]["id"] == first
    # He is logged as someone else's pick 1: the rule has nobody left to allow, so my pick 2 is chosen freely
    gone = _ask(service, [_rule("only", [first], 1, 1)], picks=[{"kind": "player", "id": first}])
    assert gone["plans"] and gone["plans"][0]["steps"][0]["id"] != first
    assert gone["rules"][0]["state"] == "moot"


def test_rules_never_change_what_the_other_teams_would_pick(service: DraftService) -> None:
    rule = parse_rule(None)
    free = service._planner_choice(3, [], service.keys, rule, "uncapped", True)
    banned = PickRule("v", "avoid", frozenset({free or ""}), frozenset(range(1, 200)))
    assert service._planner_choice(3, [], service.keys, rule, "uncapped", True, [banned]) == free


def test_the_request_is_refused_when_a_rule_is_wrong(service: DraftService) -> None:
    with pytest.raises(RequestError, match="rule 1"):
        _ask(service, [_rule("avoid", ["nobody-by-that-name"])])


def test_no_rules_means_no_rules_block_and_no_cost(service: DraftService) -> None:
    answer = _ask(service, [])
    assert answer["rules"] == [] and answer["rulesImpact"] is None
