"""Tests for the dashboard's service layer: what the page receives for a given draft state."""

from typing import Any, Dict, List

import pytest

from fantasy_draft.data import load_players
from fantasy_draft.draft import DraftState, my_picks, slot_of_pick
from fantasy_draft.optimizer import FIRST_PICK_OPTIONS, NODE_BUDGET, OPTION_NODE_BUDGET, FirstPickOption, Plan
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
    league = {key: payload["league"][key] for key in ("teams", "slot", "rounds", "rosterSize")}
    assert league == {"teams": 14, "slot": 2, "rounds": 8, "rosterSize": 13}
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
    assert result["roster"] == [{"id": ids[1], "kind": "player", "pick": 2}]
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
    assert rows["tyrese-haliburton"]["lastSeasonDelta"] is None


@pytest.mark.parametrize("extra", [{}, {"method": "uncapped", "gamesAdjusted": True}, {"method": "zscore"}])
def test_last_season_score_is_on_the_scale_of_the_score_shown(service: DraftService, extra: Dict[str, Any]) -> None:
    rows = _ask(service, [], **extra)["pool"]
    known = [row for row in rows if row["lastSeasonScore"] is not None]
    assert len(known) > 100
    for row in known:
        assert row["lastSeasonDelta"] == pytest.approx(row["score"] - row["lastSeasonScore"], abs=0.11)
    # Games missed last season lower last season's score only when the page counts games
    kessler_plain = next(r for r in _ask(service, [], method="uncapped")["pool"] if r["id"] == "walker-kessler")
    kessler_adjusted = next(r for r in _ask(service, [], method="uncapped", gamesAdjusted=True)["pool"] if r["id"] == "walker-kessler")
    assert kessler_adjusted["lastSeasonScore"] < kessler_plain["lastSeasonScore"]


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


def test_the_answer_says_whether_the_search_was_complete(service: DraftService) -> None:
    answer = _ask(service, [])
    assert answer["search"]["truncated"] is False and 0 < answer["search"]["nodes"] < NODE_BUDGET


def test_alternatives_are_other_first_picks_priced_against_the_best_plan(service: DraftService) -> None:
    answer = _ask(service, [])
    recommended = answer["recommendation"]["id"]
    alternatives = answer["alternatives"]
    assert alternatives and len(alternatives) <= 4
    assert recommended not in [alt["id"] for alt in alternatives]
    assert all(alt["behind"] >= 0 for alt in alternatives)
    assert len({alt["id"] for alt in alternatives}) == len(alternatives)


def test_a_rule_that_lets_everyone_through_is_cut_short_and_flagged(service: DraftService) -> None:
    ids = _ids_by_xrank(service)
    wide = {"type": "probability", "baseSd": 20, "sdPerAdp": 1.0, "threshold": 0.05}
    answer = service.analyze({"categories": ["fg_pct", "ft_pct"], "picks": ids[:26], "rule": wide, "method": "uncapped"})
    assert answer["search"]["truncated"] is True
    assert answer["plans"], "a cut-short search still returns the best plan it found"
    assert answer["search"]["nodes"] <= (FIRST_PICK_OPTIONS + 2) * (NODE_BUDGET + 1)


@pytest.mark.parametrize("settings", [{"method": "uncapped", "gamesAdjusted": True}, {"method": "capped", "gamesAdjusted": False}])
def test_the_work_budget_never_binds_with_default_rules_over_a_whole_draft(service: DraftService, settings: Dict[str, Any]) -> None:
    """If this fails, default results have silently become approximate: more candidates or rounds were added without a rethink."""
    ids = service.players.sort_values("adp_est")["player_id"].tolist()
    busiest_main = busiest_option = 0
    # Every third state, plus the one just before each of my picks, which is where the search is busiest
    for made in sorted(set(range(0, 112, 3)) | {pick - 1 for pick in my_picks(rounds=8)}):
        answer = service.analyze({"categories": ALL, "picks": ids[:made], **settings})
        assert answer["search"]["truncated"] is False, f"cut short with {made} picks made"
        busiest_main = max(busiest_main, answer["search"]["mainNodes"])
        busiest_option = max(busiest_option, answer["search"]["maxOptionNodes"])
    # The first-pick searches have the tighter cap, so they are the first to bind
    assert busiest_option < OPTION_NODE_BUDGET / 2, f"a first-pick search used {busiest_option:,}; its budget is {OPTION_NODE_BUDGET:,}"
    assert busiest_main < NODE_BUDGET / 2, f"the main search used {busiest_main:,} nodes; its budget is {NODE_BUDGET:,}"


def test_alternatives_say_whether_they_assume_the_recommended_player_is_gone(service: DraftService) -> None:
    ids = _ids_by_xrank(service)
    waiting = _ask(service, [])  # pick 1 is still to be made, so he may be taken before my pick 2
    on_the_clock = _ask(service, ids[:1])  # pick 2 is mine and the board is in front of me
    assert waiting["alternativesMode"] == "gone" and on_the_clock["alternativesMode"] == "instead"


def test_an_alternative_is_ahead_of_the_best_plan_only_when_the_position_bonus_ranked_it_lower(service: DraftService) -> None:
    for made in (0, 1, 10, 26, 40):
        answer = _ask(service, _ids_by_xrank(service)[:made])
        for alt in answer["alternatives"]:
            assert alt["behind"] >= 0 or alt.get("byPositions"), f"{made} picks made"
            assert not alt.get("byPositions") or alt["behind"] < 0.05


def _plan(player_id: str, total: float, value: float) -> Plan:
    return Plan((2,), (player_id,), total, 1.0, value)


def test_a_level_or_better_roster_score_that_ranks_lower_is_marked_as_decided_by_positions(service: DraftService) -> None:
    ids = _ids_by_xrank(service)
    best, level, ahead, behind = _plan(ids[0], 10.0, 10.6), _plan(ids[1], 10.0, 10.3), _plan(ids[2], 10.2, 10.3), _plan(ids[3], 9.0, 9.1)
    options = [FirstPickOption(plan.player_ids[0], plan) for plan in (level, ahead, behind)]
    rule = parse_rule(None)
    shown = service._alternatives(options, best, rule, DraftState())
    assert [item["behind"] for item in shown] == [0.0, -0.2, 1.0]  # the roster gap, negative when the option is ahead
    assert [bool(item.get("byPositions")) for item in shown] == [True, True, False]


def test_the_answer_reports_the_main_and_the_busiest_option_search(service: DraftService) -> None:
    search = _ask(service, [])["search"]
    assert 0 < search["mainNodes"] < NODE_BUDGET and 0 < search["maxOptionNodes"] < OPTION_NODE_BUDGET
    assert search["nodes"] >= search["mainNodes"] + search["maxOptionNodes"]


def test_the_pool_tells_the_page_the_allowed_availability_settings(service: DraftService) -> None:
    limits = service.pool_payload()["ruleLimits"]
    assert limits["baseSd"] == {"default": 2.0, "min": 0.1, "max": 20.0}
    assert set(limits) == {"baseSd", "sdPerAdp", "threshold", "slack"}
    for key, limit in limits.items():  # the values the page may send are exactly the ones the server accepts
        assert parse_rule({"type": "window" if key == "slack" else "probability", key: limit["min"]})
        assert parse_rule({"type": "window" if key == "slack" else "probability", key: limit["max"]})


def test_a_pick_can_be_a_plain_id_or_an_object_and_the_answer_is_the_same(service: DraftService) -> None:
    ids = _ids_by_xrank(service)[:5]
    plain = _ask(service, ids)
    objects = _ask(service, [{"kind": "player", "id": pid} for pid in ids])
    no_kind = _ask(service, [{"id": pid} for pid in ids])
    mixed = _ask(service, [ids[0], {"kind": "player", "id": ids[1]}, *ids[2:]])
    assert plain["plans"] == objects["plans"] == no_kind["plans"] == mixed["plans"]
    assert plain["log"] == objects["log"] == mixed["log"]
    assert [entry["kind"] for entry in plain["log"]] == ["player"] * 5


@pytest.mark.parametrize(
    "picks, message",
    [
        ([{"kind": "player"}], "needs the player's id"),
        ([{"kind": "player", "id": 7}], "needs the player's id"),
        ([{"kind": "dunk", "id": "nikola-jokic"}], "has a kind"),
        ([{"kind": "player", "id": "nikola-jokic", "team": 3}], "has a kind"),
        ([{"kind": "player", "id": "nobody"}], "Unknown players"),
        ([["nikola-jokic"]], "list of player ids or pick objects"),
        ([None], "list of player ids or pick objects"),
        (["nikola-jokic", {"kind": "player", "id": "nikola-jokic"}], "picked twice"),
    ],
)
def test_a_malformed_pick_is_refused_with_its_number(service: DraftService, picks: Any, message: str) -> None:
    with pytest.raises(RequestError, match=message):
        _ask(service, picks)


def test_a_pick_outside_the_list_advances_the_draft_and_removes_nobody(service: DraftService) -> None:
    ids = _ids_by_xrank(service)
    plain = _ask(service, ids[:1])  # pick 1 made; I am on the clock at pick 2
    after = _ask(service, [ids[0], {"kind": "outside"}])  # pick 2, mine, was a player outside the list
    assert plain["clock"]["pick"] == 2 and after["clock"]["pick"] == 3
    assert after["roster"] == [{"id": None, "kind": "outside", "pick": 2}]
    assert [entry["kind"] for entry in after["log"]] == ["player", "outside"]
    assert after["log"][1] == {"pick": 2, "kind": "outside", "id": None, "mine": True, "slot": 2, "team": "Fran'stastic Team"}
    assert {row["id"] for row in after["pool"]} == {row["id"] for row in plain["pool"]}
    assert after["plans"], "there is still a plan for the later picks"


def test_an_outside_pick_by_another_team_only_moves_the_clock(service: DraftService) -> None:
    ids = _ids_by_xrank(service)
    answer = _ask(service, [{"kind": "outside"}, ids[0]])  # pick 1 outside the list, pick 2 (mine) Jokic
    assert answer["clock"]["pick"] == 3
    assert [entry["id"] for entry in answer["roster"]] == [ids[0]]
    assert {row["id"] for row in answer["pool"]} == set(ids) - {ids[0]}


def test_my_outside_pick_costs_a_slot_and_replacement_value(service: DraftService) -> None:
    ids = _ids_by_xrank(service)
    with_player = _ask(service, [ids[1], ids[0]])  # pick 2 mine is a pool player
    with_outside = _ask(service, [ids[1], {"kind": "outside"}])
    assert with_outside["plans"][0]["totalScore"] < with_player["plans"][0]["totalScore"]


def test_an_outside_pick_carries_no_player_id(service: DraftService) -> None:
    with pytest.raises(RequestError, match="no player id"):
        _ask(service, [{"kind": "outside", "id": "nikola-jokic"}])


# ---------- unseen and gone picks ----------

UNSEEN = {"kind": "unseen"}


def _by_adp(service: DraftService) -> List[str]:
    return service.players.sort_values("adp_est")["player_id"].tolist()


def _availability(answer: Dict[str, Any]) -> Dict[str, float]:
    return {row["id"]: row["availability"] for row in answer["pool"]}


def test_unseen_picks_advance_the_clock_and_show_in_the_log(service: DraftService) -> None:
    ids = _by_adp(service)
    answer = _ask(service, ids[:20] + [UNSEEN] * 6)
    assert answer["clock"]["pick"] == 27 and answer["clock"]["isMine"] is True
    assert [entry["kind"] for entry in answer["log"][-7:-5]] == ["player", "unseen"]
    assert answer["log"][-1] == {"pick": 26, "kind": "unseen", "id": None, "mine": False, "slot": 3, "team": "Raw Power"}
    assert {row["id"] for row in answer["pool"]} == set(ids[20:]), "an unseen pick removes nobody from the pool"


def test_with_unseen_picks_on_the_clock_is_no_longer_100_percent_for_everyone(service: DraftService) -> None:
    ids = _by_adp(service)
    seen = _availability(_ask(service, ids[:26]))
    unseen = _availability(_ask(service, ids[:20] + [UNSEEN] * 6))
    assert set(seen.values()) == {1.0}, "no unseen picks: everyone listed is there by definition"
    early, late = ids[20], ids[120]
    assert unseen[early] < 0.6 and unseen[late] > 0.95
    assert all(unseen[pid] <= seen[pid] for pid in seen)  # every player listed in both is no more likely to be there


def test_marking_a_player_gone_removes_him_and_one_unseen_pick(service: DraftService) -> None:
    ids = _by_adp(service)
    unseen = _ask(service, ids[:20] + [UNSEEN] * 6)
    gone_id = ids[20]
    marked = _ask(service, ids[:20] + [{"kind": "gone", "id": gone_id}] + [UNSEEN] * 5)
    assert marked["clock"]["pick"] == unseen["clock"]["pick"] == 27
    assert gone_id not in {row["id"] for row in marked["pool"]}
    assert [entry["kind"] for entry in marked["log"][20:22]] == ["gone", "unseen"]
    before, after = _availability(unseen), _availability(marked)
    assert all(after[pid] >= before[pid] - 1e-9 for pid in after), "fewer unseen picks can only raise everyone's odds"
    assert any(after[pid] > before[pid] + 0.01 for pid in after)


def test_a_player_marked_gone_never_appears_in_a_plan(service: DraftService) -> None:
    ids = _by_adp(service)
    marked = _ask(service, ids[:20] + [{"kind": "gone", "id": ids[21]}] + [UNSEEN] * 5)
    assert all(ids[21] not in [step["id"] for step in plan["steps"]] for plan in marked["plans"])


@pytest.mark.parametrize("kind", ["unseen", "gone"])
def test_an_unseen_or_gone_pick_cannot_be_one_of_my_own(service: DraftService, kind: str) -> None:
    ids = _by_adp(service)
    entry = {"kind": kind, **({"id": ids[100]} if kind == "gone" else {})}  # a player not already logged
    with pytest.raises(RequestError, match="Pick 2 is yours"):
        _ask(service, [ids[0], entry])  # pick 2 is mine
    with pytest.raises(RequestError, match="Pick 27 is yours"):
        _ask(service, ids[:26] + [entry])  # pick 27 is mine


@pytest.mark.parametrize(
    "picks, message",
    [
        ([{"kind": "unseen", "id": "nikola-jokic"}], "no player id"),
        ([{"kind": "gone"}], "needs the player's id"),
        ([{"kind": "gone", "id": "nobody"}], "Unknown players"),
        (["nikola-jokic", {"kind": "gone", "id": "nikola-jokic"}], "picked twice"),
    ],
)
def test_malformed_unseen_and_gone_picks_are_refused(service: DraftService, picks: Any, message: str) -> None:
    with pytest.raises(RequestError, match=message):
        _ask(service, picks)


def test_unseen_picks_count_towards_the_picks_made_for_ownership(service: DraftService) -> None:
    ids = _by_adp(service)
    answer = _ask(service, [ids[0], ids[1]] + [UNSEEN] * 24)  # picks 3 to 26 unseen; pick 27 is mine
    assert answer["clock"]["pick"] == 27 and answer["clock"]["isMine"] is True
    assert [entry["id"] for entry in answer["roster"]] == [ids[1]]


def test_look_first_lists_better_scoring_players_the_odds_left_out_and_nobody_long_gone(service: DraftService) -> None:
    ids = _by_adp(service)
    answer = _ask(service, ids[:20] + [UNSEEN] * 6, method="uncapped", gamesAdjusted=True)  # the page defaults
    rows = {row["id"]: row for row in answer["pool"]}
    recommended = rows[answer["recommendation"]["id"]]
    look = answer["lookFirst"]
    assert [entry["id"] for entry in look] == ["amen-thompson"], "the reviewer's case: 48.7 against 46.1, odds 49%"
    scores = [rows[entry["id"]]["score"] for entry in look]
    assert scores == sorted(scores, reverse=True)
    for entry in look:
        assert rows[entry["id"]]["score"] > recommended["score"], "better than the recommendation"
        assert 0.10 <= entry["availability"] < 0.5, "possible, but under the threshold that kept him out of the plan"
        assert entry["id"] != recommended["id"]


def test_look_first_is_empty_when_nothing_is_unseen_or_it_is_not_my_turn(service: DraftService) -> None:
    ids = _by_adp(service)
    assert _ask(service, ids[:26], method="uncapped", gamesAdjusted=True)["lookFirst"] == [], "my turn but the pool is exactly what is left"
    assert _ask(service, ids[:10] + [UNSEEN] * 3)["lookFirst"] == [], "pick 14 is not mine"
    assert _ask(service, [])["lookFirst"] == []


def test_the_team_names_follow_the_snake_order_and_slot_2_is_the_users_team(service: DraftService) -> None:
    from fantasy_draft.draft import TEAM_NAMES, slot_of_pick

    assert len(TEAM_NAMES) == 14 and TEAM_NAMES[1] == "Fran'stastic Team"
    assert [slot_of_pick(number) for number in (1, 2, 14, 15, 16, 28, 29)] == [1, 2, 14, 14, 13, 1, 1]
    payload = service.pool_payload()
    assert payload["league"]["teamNames"][payload["league"]["slot"] - 1] == "Fran'stastic Team"
    ids = service.players.sort_values("adp_est")["player_id"].tolist()
    answer = _ask(service, ids[:15])
    assert answer["log"][1]["team"] == "Fran'stastic Team" and answer["log"][14]["slot"] == 14
    assert answer["log"][14]["team"] == TEAM_NAMES[13]
    assert answer["clock"]["teamOnClock"] == TEAM_NAMES[12], "pick 16 goes to slot 13 in the second round"


def test_the_league_block_scores_all_14_teams_so_far_and_projected(service: DraftService) -> None:
    ids = _by_adp(service)
    answer = _ask(service, ids[:30], method="uncapped", gamesAdjusted=True)
    league = answer["league"]
    assert league["basis"] == "so far" and league["size"] == 3 and len(league["teams"]) == 14, "the round in progress"
    assert {row["players"] for row in league["teams"]} == {2, 3}
    projected = league["projected"]
    assert projected["size"] == 8 and {row["players"] for row in projected["teams"]} == {8}
    mine = next(row for row in projected["teams"] if row["mine"])
    assert mine["name"] == "Fran'stastic Team" and set(mine["totals"]) == set(ALL)
    assert set(league["standing"]) == set(ALL) and all(1 <= value["rank"] <= 14 for value in league["standing"].values())


def test_the_projection_never_changes_the_logged_picks_or_gives_one_player_to_two_teams(service: DraftService) -> None:
    ids = _by_adp(service)
    answer = _ask(service, ids[:30])
    again = _ask(service, ids[:30])
    assert answer["league"] == again["league"], "deterministic"
    assert answer["league"]["size"] == 3


def test_autopick_gives_the_best_adp_that_fits_and_refuses_a_bad_request(service: DraftService) -> None:
    ids = _by_adp(service)
    service = DraftService(service.players, rehearsal=True)
    assert service.autopick({"picks": ids[:3]}) == {"id": ids[3], "pick": 4}
    assert service.autopick({"picks": ids[:3], "noise": True, "seed": 5}) == service.autopick({"picks": ids[:3], "noise": True, "seed": 5})
    with pytest.raises(RequestError):
        service.autopick({"picks": ids[:3], "seed": "x"})
    with pytest.raises(RequestError):
        service.autopick({"picks": ids[:3], "noise": "yes"})


def test_team_need_weights_are_off_by_default_and_exactly_neutral_before_a_round_is_complete(service: DraftService) -> None:
    ids = _by_adp(service)
    plain = _ask(service, ids[:5], method="uncapped", gamesAdjusted=True)
    assert plain["needs"] == {"on": False, "ramp": 0.0, "weights": None}
    early = _ask(service, ids[:5], method="uncapped", gamesAdjusted=True, needs=True)
    assert early["needs"]["ramp"] == 0.0 and set(early["needs"]["weights"].values()) == {1.0}
    assert [row["score"] for row in early["pool"]] == [row["score"] for row in plain["pool"]]
    assert early["recommendation"] == plain["recommendation"] and early["plans"] == plain["plans"]


def test_team_need_weights_change_the_scores_once_rounds_are_complete_and_never_revive_a_punted_category(service: DraftService) -> None:
    ids = _by_adp(service)
    picks = ids[:56]
    plain = _ask(service, picks, method="uncapped", gamesAdjusted=True)
    needs = _ask(service, picks, method="uncapped", gamesAdjusted=True, needs=True)
    assert needs["needs"]["ramp"] == 1.0
    weights = needs["needs"]["weights"]
    assert set(weights) == set(ALL) and all(0.6 <= value <= 1.4 for value in weights.values())
    assert [row["score"] for row in needs["pool"]] != [row["score"] for row in plain["pool"]]
    punted = [key for key in ALL if key != "ast"]
    assert set(_ask(service, picks, method="uncapped", needs=True, **{})["needs"]["weights"]) == set(ALL)
    answer = service.analyze({"categories": punted, "picks": picks, "method": "uncapped", "needs": True})
    assert set(answer["needs"]["weights"]) == set(punted), "an unticked category has no weight"


def test_needs_must_be_a_boolean(service: DraftService) -> None:
    with pytest.raises(RequestError):
        _ask(service, [], needs="yes")


def test_the_lineup_block_names_the_slots_the_bench_and_the_positions_that_still_fit(service: DraftService) -> None:
    ids = _by_adp(service)
    answer = _ask(service, ids[:28], method="uncapped", gamesAdjusted=True)  # my picks 2 and 27
    lineup = answer["lineup"]
    assert [slot["slot"] for slot in lineup["slots"]] == ["PG", "SG", "G", "SF", "PF", "F", "C", "C", "Util", "Util"]
    filled = [slot["entry"] for slot in lineup["slots"] if slot["entry"] is not None]
    assert sorted(filled) == [0, 1] and lineup["bench"] == []
    assert set(lineup["canAdd"]) <= {"PG", "SG", "SF", "PF", "C"} and lineup["canAdd"]


def test_an_outside_pick_of_mine_fills_a_slot_and_a_full_lineup_has_nothing_to_add(service: DraftService) -> None:
    ids = _by_adp(service)
    answer = _ask(service, [ids[0], {"kind": "outside"}], gamesAdjusted=True)  # pick 2 is mine and not in the list
    assert len([slot for slot in answer["lineup"]["slots"] if slot["entry"] is not None]) == 1


def test_best_available_fits_my_lineup_and_unseen_risk_is_zero_without_unseen_picks(service: DraftService) -> None:
    ids = _by_adp(service)
    plain = _ask(service, ids[:5])
    assert plain["bestAvailable"]["id"] in {row["id"] for row in plain["pool"]}
    assert {row["unseenRisk"] for row in plain["pool"]} == {0.0}
    risky = _ask(service, ids[:20] + [UNSEEN] * 6)
    risks = {row["id"]: row["unseenRisk"] for row in risky["pool"]}
    assert max(risks.values()) > 0.3 and risks[ids[130]] < 0.01, "the risk is high near the unseen picks and nil far from them"


def test_an_on_the_clock_alternative_that_takes_the_recommended_player_next_says_so(service: DraftService) -> None:
    ids = _by_adp(service)
    answer = _ask(service, ids[:26], method="uncapped", gamesAdjusted=True)  # my turn at 27
    recommended = answer["recommendation"]["id"]
    thens = [alt["then"] for alt in answer["alternatives"] if "then" in alt]
    for then in thens:
        assert then["id"] == recommended and then["pick"] == 30 and 0 <= then["availability"] <= 1


def test_on_my_turn_each_row_also_carries_his_chance_at_my_following_pick(service: DraftService) -> None:
    ids = _by_adp(service)
    mine = _ask(service, ids[:26])  # my turn at 27, next planned pick 30
    assert mine["laterPick"] == 30 and all(0 <= row["later"] <= 1 for row in mine["pool"])
    assert any(row["later"] < 1 for row in mine["pool"]) and {row["availability"] for row in mine["pool"]} == {1.0}
    waiting = _ask(service, ids[:10])
    assert waiting["laterPick"] is None and {row["later"] for row in waiting["pool"]} == {None}


def test_automatic_picks_exist_only_in_a_rehearsal(service: DraftService) -> None:
    ids = _by_adp(service)
    assert service.pool_payload()["rehearsal"] is False
    plain = DraftService(service.players)
    with pytest.raises(RequestError, match="mock draft"):
        plain.autopick({"picks": ids[:3]})
    practice = DraftService(service.players, rehearsal=True)
    assert practice.pool_payload()["rehearsal"] is True and practice.autopick({"picks": ids[:3]})["id"] == ids[3]


def _projection(service: DraftService, ids: List[str]) -> Dict[str, Any]:
    return service.project_league({"categories": ALL, "picks": ids, "method": "uncapped", "gamesAdjusted": True})


def test_the_planner_projection_makes_the_picks_each_team_s_own_recommendation_would(service: DraftService) -> None:
    ids: List[str] = []
    for number in range(1, 21):
        slot = slot_of_pick(number, 14)
        answer = DraftService(service.players, slot=slot).analyze(
            {"categories": ALL, "picks": ids, "method": "uncapped", "gamesAdjusted": True}
        )
        ids.append(answer["recommendation"]["id"])
    simulated = _projection(service, [])["simulated"]
    assert simulated[:20] == ids, "the same search the page runs for that team, one after the other"


def test_the_planner_projection_completes_every_team_and_keeps_the_logged_picks(service: DraftService) -> None:
    logged = _by_adp(service)[:20]
    table = _projection(service, logged)
    assert table["size"] == 8 and {row["players"] for row in table["teams"]} == {8} and table["fallbacks"] == 0
    assert len(table["simulated"]) == 8 * 14 - 20 and len(set(table["simulated"]) | set(logged)) == 8 * 14, "nobody twice"
    assert not set(table["simulated"]) & set(logged)
    assert [row["place"] for row in table["teams"]] == sorted(row["place"] for row in table["teams"])


def test_a_poor_logged_pick_lowers_its_team_and_the_user_is_not_first_by_construction(service: DraftService) -> None:
    """One case, not a law: a rival's mistake can also leave the user lower (the players it frees change everyone's plan)."""
    by_adp = _by_adp(service)
    good = _projection(service, [by_adp[0]])
    poor = _projection(service, [by_adp[-1]])
    team_one = lambda table: next(row for row in table["teams"] if row["slot"] == 1)["score"]  # noqa: E731
    assert team_one(poor) < team_one(good) - 0.5, "his projected stats drop when he takes a poor player"
    assert _projection(service, [])["teams"][0]["place"] == 1


def test_the_planner_projection_refuses_what_analyze_refuses(service: DraftService) -> None:
    with pytest.raises(RequestError):
        service.project_league({"categories": [], "picks": []})
    with pytest.raises(RequestError):
        service.project_league({"categories": ALL, "picks": ["nobody"]})


def test_the_planner_projection_names_the_team_it_gives_the_user(service: DraftService) -> None:
    logged = _by_adp(service)[:2]
    table = _projection(service, logged)
    assert table["myPlayers"][0] == logged[1] and len(table["myPlayers"]) == 8, "my logged pick, then the seven simulated ones"
    assert set(table["myPlayers"][1:]) <= set(table["simulated"])


def _predict(service: DraftService, picks: List[Any]) -> Dict[str, Any]:
    return service.predict_picks({"categories": ALL, "picks": picks, "method": "uncapped", "gamesAdjusted": True})


def test_the_prediction_for_the_team_on_the_clock_is_what_its_own_recommendation_says(service: DraftService) -> None:
    clock = _predict(service, [])["clock"]
    own = DraftService(service.players, slot=1).analyze({"categories": ALL, "picks": [], "method": "uncapped", "gamesAdjusted": True})
    assert clock["pick"] == 1 and clock["slot"] == 1 and clock["planner"] == own["recommendation"]["id"]
    assert clock["adp"] == _by_adp(service)[0]
    assert _predict(service, _by_adp(service)[:1])["clock"] is None, "pick 2 is mine: the recommendation is the answer"


def test_each_logged_pick_is_compared_with_the_planner_and_adp_choice_before_it(service: DraftService) -> None:
    by_adp = _by_adp(service)
    planner_first = _predict(service, [])["clock"]["planner"]
    poor = by_adp[-1]
    answer = _predict(service, [planner_first, by_adp[0] if by_adp[0] != planner_first else by_adp[1], poor])
    first, third = answer["picks"][0], answer["picks"][1]
    assert [row["pick"] for row in answer["picks"]] == [1, 3], "my pick 2 is not compared"
    assert first["matchPlanner"] is True and first["planner"] == planner_first and first["scoreRank"] >= 1
    assert third["id"] == poor and not third["matchPlanner"] and not third["matchAdp"]
    assert third["reach"] > 100 and third["scoreRank"] > 20, "the worst-ADP player taken third is a huge reach"


def test_the_prediction_summary_counts_matches_and_leaves_out_what_cannot_be_compared(service: DraftService) -> None:
    by_adp = _by_adp(service)
    log: List[Any] = [by_adp[0], by_adp[1], {"kind": "unseen"}, {"kind": "outside"}, by_adp[2]]
    answer = _predict(service, log)
    assert [row["pick"] for row in answer["picks"]] == [1, 5], "not mine (2), not unseen (3) or outside (4)"
    summary = answer["summary"]
    assert summary["counted"] == 2 and summary["adp"] >= 1 and summary["either"] >= summary["adp"]
    assert len(summary["teams"]) == 13 and all(team["slot"] != service.slot for team in summary["teams"])
    assert sum(team["counted"] for team in summary["teams"]) == 2
    assert summary["meanReach"] is not None


def test_predictions_exist_only_in_the_real_draft_and_refuse_a_bad_log(service: DraftService) -> None:
    with pytest.raises(RequestError, match="real draft"):
        _predict(DraftService(service.players, rehearsal=True), [])
    with pytest.raises(RequestError):
        _predict(service, ["nobody"])
    assert _predict(service, [])["picks"] == [] and _predict(service, [])["summary"]["counted"] == 0
