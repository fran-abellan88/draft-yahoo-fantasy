"""Tests for the draft optimizer, including an exhaustive cross-check on small pools."""

import itertools
from typing import Dict, List

import numpy as np
import pandas as pd
import pytest

from fantasy_draft.availability import AdpWindow, AvailabilityRule, NormalAdpModel
from fantasy_draft.categories import categories_in
from fantasy_draft.data import load_players
from fantasy_draft.draft import DraftState, my_picks
from fantasy_draft.lineup import all_can_start
from fantasy_draft.optimizer import FIRST_PICK_OPTIONS, NODE_BUDGET, Recommendation, pick_frequency, plan_picks, recommend, team_profile
from fantasy_draft.scoring import compute_bounds, composite_score

ROUNDS = 3  # my picks are then 2, 27 and 30


def _pool(seed: int = 0, size: int = 14) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    position_choices = [["PG"], ["SG"], ["PG", "SG"], ["SF"], ["PF"], ["SF", "PF"], ["C"], ["PF", "C"]]
    return pd.DataFrame(
        {
            "player_id": [f"p{i}" for i in range(size)],
            "player": [f"p{i}" for i in range(size)],
            "pos_list": [position_choices[i] for i in rng.integers(0, len(position_choices), size)],
            "adp_est": np.sort(rng.uniform(1.0, 45.0, size)),
            "pts": rng.uniform(5.0, 30.0, size),
        }
    )


def _brute_force(
    pool: pd.DataFrame, rule: AvailabilityRule, state: DraftState, bounds: dict, rounds: int = ROUNDS, lineup_rule: bool = True
) -> List[float]:
    """Best total score of every distinct valid team, found by trying every assignment."""
    scores = dict(zip(pool["player_id"], composite_score(pool, ["pts"], bounds)))
    positions = dict(zip(pool["player_id"], pool["pos_list"]))
    picks = [p for p in my_picks(rounds=rounds) if p >= state.next_pick]
    gone = set(state.taken) | set(state.mine)
    remaining = pool[~pool["player_id"].isin(gone)]
    adp = remaining["adp_est"].to_numpy()
    eligible: List[List[str]] = []
    for pick in picks:
        probabilities = rule.probability(adp, pick, state.picks_made)
        ids = remaining["player_id"].to_numpy()[probabilities >= rule.threshold]
        eligible.append(list(ids))
    base = sum(scores[p] for p in state.mine)
    best_per_team = {}
    for combo in itertools.product(*eligible):
        if len(set(combo)) < len(combo):
            continue
        roster = [positions[p] for p in list(state.mine) + list(combo)]
        if lineup_rule and not all_can_start(roster):
            continue
        team = frozenset(combo)
        best_per_team[team] = base + sum(scores[p] for p in combo)
    return sorted(best_per_team.values(), reverse=True)


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("rule", [NormalAdpModel(), AdpWindow(slack=4.0)], ids=["normal", "window"])
def test_matches_brute_force(seed: int, rule: AvailabilityRule) -> None:
    pool = _pool(seed)
    bounds = compute_bounds(pool, ["pts"])
    state = DraftState()
    expected = _brute_force(pool, rule, state, bounds)
    assert expected, "the synthetic pool should allow at least one valid team"
    plans = recommend(pool, state, ["pts"], bounds, rule, rounds=ROUNDS, top_k=10, max_candidates=len(pool))
    assert [plan.total_score for plan in plans] == pytest.approx(expected[:10])


@pytest.mark.parametrize("rule", [NormalAdpModel(), AdpWindow(slack=4.0)], ids=["normal", "window"])
def test_matches_brute_force_after_round_one(rule: AvailabilityRule) -> None:
    pool = _pool(seed=3, size=36)
    bounds = compute_bounds(pool, ["pts"])
    # Round 1 is over: I took p13 at pick 2 and the other thirteen picks removed p0..p12
    state = DraftState(taken=frozenset(f"p{i}" for i in range(13)), mine=("p13",))
    assert state.next_pick == 15
    expected = _brute_force(pool, rule, state, bounds)
    assert expected
    plans = recommend(pool, state, ["pts"], bounds, rule, rounds=ROUNDS, top_k=10, max_candidates=len(pool))
    assert [plan.total_score for plan in plans] == pytest.approx(expected[:10])
    assert all(plan.pick_numbers == (27, 30) for plan in plans)


def test_lineup_rule_binds_and_the_search_respects_it() -> None:
    """Six picks and a pool of centers: the best-scoring teams would need five starting centers."""
    centers = [["C"]] * 6
    others = [["PG"], ["SG"], ["SF"], ["PF"]]
    pool = pd.DataFrame(
        {
            "player_id": [f"p{i}" for i in range(10)],
            "player": [f"p{i}" for i in range(10)],
            "pos_list": centers + others,
            "adp_est": [200.0] * 10,  # everyone lasts until every one of my picks
            "pts": [30.0, 29.0, 28.0, 27.0, 26.0, 25.0, 12.0, 11.0, 10.0, 9.0],  # centers score best
        }
    )
    bounds = compute_bounds(pool, ["pts"])
    rule = AdpWindow(slack=0.0)
    constrained = _brute_force(pool, rule, DraftState(), bounds, rounds=6)
    unconstrained = _brute_force(pool, rule, DraftState(), bounds, rounds=6, lineup_rule=False)
    assert unconstrained[0] > constrained[0] + 1e-9, "the lineup rule must change the answer for this test to mean anything"

    plans = recommend(pool, DraftState(), ["pts"], bounds, rule, rounds=6, top_k=10, max_candidates=10)
    assert [plan.total_score for plan in plans] == pytest.approx(constrained[:10])
    for plan in plans:
        assert sum(1 for pid in plan.player_ids if int(pid[1:]) < 6) <= 4  # at most four centers can start


def test_inconsistent_draft_state_is_rejected() -> None:
    pool = _pool(seed=3)
    # Five picks are done, so pick 2 has passed and I must own exactly one of them
    state = DraftState(taken=frozenset({"p0", "p1", "p2", "p3", "p6"}), mine=())
    with pytest.raises(ValueError, match="should own"):
        recommend(pool, state, ["pts"], compute_bounds(pool, ["pts"]), NormalAdpModel(), rounds=ROUNDS)


def test_taken_players_never_appear_in_a_plan() -> None:
    pool = _pool(seed=2)
    bounds = compute_bounds(pool, ["pts"])
    state = DraftState(taken=frozenset({"p0"}))  # pick 1 is done, so my pick 2 is next
    plans = recommend(pool, state, ["pts"], bounds, AdpWindow(slack=40.0), rounds=ROUNDS, top_k=20, max_candidates=len(pool))
    assert plans
    assert all("p0" not in plan.player_ids for plan in plans)


def test_unknown_player_in_state_is_rejected() -> None:
    pool = _pool()
    with pytest.raises(ValueError, match="Unknown"):
        recommend(pool, DraftState(taken=frozenset({"nobody"})), ["pts"], compute_bounds(pool, ["pts"]), NormalAdpModel())


def test_player_cannot_be_mine_and_taken() -> None:
    pool = _pool()
    state = DraftState(taken=frozenset({"p1"}), mine=("p1",))
    with pytest.raises(ValueError, match="both"):
        recommend(pool, state, ["pts"], compute_bounds(pool, ["pts"]), NormalAdpModel())


def test_no_remaining_picks_returns_nothing() -> None:
    pool = _pool()
    # Thirteen picks are done including my only pick of the first round, so nothing of mine remains
    done = DraftState(taken=frozenset(f"p{i}" for i in range(1, 13)), mine=("p0",))
    assert recommend(pool, done, ["pts"], compute_bounds(pool, ["pts"]), NormalAdpModel(), rounds=1) == []


def test_plans_are_sorted_distinct_and_lineup_valid() -> None:
    players = load_players()
    keys = categories_in(players.columns)
    bounds = compute_bounds(players, keys)
    plans = recommend(players, DraftState(), keys, bounds, NormalAdpModel(), top_k=25)
    assert len(plans) == 25
    scores = [plan.total_score for plan in plans]
    assert scores == sorted(scores, reverse=True)
    assert len({frozenset(plan.player_ids) for plan in plans}) == 25
    positions = dict(zip(players["player_id"], players["pos_list"]))
    for plan in plans:
        assert plan.pick_numbers == tuple(my_picks(rounds=8))
        assert len(set(plan.player_ids)) == 8
        assert all_can_start([positions[pid] for pid in plan.player_ids])
        assert 0.0 < plan.survival <= 1.0


def test_pick_frequency_and_profile_on_real_data() -> None:
    players = load_players()
    keys = categories_in(players.columns)
    bounds = compute_bounds(players, keys)
    plans = recommend(players, DraftState(), keys, bounds, NormalAdpModel(), top_k=25)
    frequency = pick_frequency(plans)
    assert frequency["plans"].sum() == 25
    assert frequency["share"].iloc[0] == frequency["share"].max()
    profile = team_profile(players, plans[0].player_ids, keys, bounds)
    assert list(profile.index) == keys
    assert (profile["mean_score"].between(0, 100)).all()


def test_removing_a_category_changes_the_best_team() -> None:
    players = load_players()
    keys = categories_in(players.columns)
    bounds = compute_bounds(players, keys)
    with_to = recommend(players, DraftState(), keys, bounds, NormalAdpModel(), top_k=1)[0]
    no_to_keys = [key for key in keys if key != "to"]
    without_to = recommend(players, DraftState(), no_to_keys, bounds, NormalAdpModel(), top_k=1)[0]
    assert set(with_to.player_ids) != set(without_to.player_ids)


def _best_total_by_first_pick(pool: pd.DataFrame, rule: AvailabilityRule, state: DraftState, bounds: dict) -> Dict[str, float]:
    """Best total of any valid team that starts with each player, by trying every assignment."""
    scores = dict(zip(pool["player_id"], composite_score(pool, ["pts"], bounds)))
    positions = dict(zip(pool["player_id"], pool["pos_list"]))
    picks = [p for p in my_picks(rounds=ROUNDS) if p >= state.next_pick]
    remaining = pool[~pool["player_id"].isin(set(state.taken) | set(state.mine))]
    adp = remaining["adp_est"].to_numpy()
    ids = remaining["player_id"].to_numpy()
    eligible = [list(ids[rule.probability(adp, pick, state.picks_made) >= rule.threshold]) for pick in picks]
    base = sum(scores[p] for p in state.mine)
    best: Dict[str, float] = {}
    for combo in itertools.product(*eligible):
        if len(set(combo)) < len(combo) or not all_can_start([positions[p] for p in list(state.mine) + list(combo)]):
            continue
        total = base + sum(scores[p] for p in combo)
        best[combo[0]] = max(best.get(combo[0], -np.inf), total)
    return best


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("rule", [NormalAdpModel(), AdpWindow(slack=4.0)], ids=["normal", "window"])
def test_first_pick_options_are_the_best_plan_for_each_first_pick(seed: int, rule: AvailabilityRule) -> None:
    pool = _pool(seed)
    bounds = compute_bounds(pool, ["pts"])
    expected = _best_total_by_first_pick(pool, rule, DraftState(), bounds)
    result = plan_picks(
        pool, DraftState(), ["pts"], bounds, rule, rounds=ROUNDS, max_candidates=len(pool), node_budget=None, option_count=len(pool)
    )
    assert {option.player_id: option.plan.total_score for option in result.options} == pytest.approx(expected)
    assert not result.truncated
    assert result.options[0].plan.total_score == pytest.approx(result.plans[0].total_score)
    assert all(option.plan.player_ids[0] == option.player_id for option in result.options)


def test_options_are_sorted_best_first_and_cover_the_recommended_pick() -> None:
    players = load_players()
    keys = categories_in(players.columns)
    result = plan_picks(players, DraftState(), keys, compute_bounds(players, keys), NormalAdpModel())
    totals = [option.plan.total_score for option in result.options]
    assert totals == sorted(totals, reverse=True)
    assert result.plans[0].player_ids[0] in [option.player_id for option in result.options]
    assert len({option.player_id for option in result.options}) == len(result.options) <= FIRST_PICK_OPTIONS + 1


def _wide_open_search(node_budget: int) -> Recommendation:
    players = load_players()
    keys = ["fg_pct", "ft_pct"]
    by_adp = players.sort_values("adp_est")["player_id"].tolist()
    state = DraftState(taken=frozenset(by_adp[:26]) - {by_adp[1]}, mine=(by_adp[1],))  # 26 picks made, the second one mine
    # Everyone clears the bar for every pick, so the same 25 players are candidates for all seven picks
    rule = NormalAdpModel(base_sd=20.0, sd_per_adp=1.0, threshold=0.05)
    bounds = compute_bounds(players, keys, method="uncapped")
    return plan_picks(players, state, keys, bounds, rule, method="uncapped", node_budget=node_budget)


def test_a_search_that_runs_out_of_budget_says_so_and_stops_near_the_budget() -> None:
    result = _wide_open_search(node_budget=2_000)
    assert result.truncated
    searches = 1 + FIRST_PICK_OPTIONS + 1  # the main search and one per first-pick option, each stopping one node past its budget
    assert result.nodes <= searches * (2_000 + 1)
    assert result.plans, "a depth-first search reaches a first plan long before it runs out of budget"


def test_a_truncated_search_is_reproducible() -> None:
    first, second = _wide_open_search(5_000), _wide_open_search(5_000)
    assert [p.player_ids for p in first.plans] == [p.player_ids for p in second.plans]
    assert first.nodes == second.nodes


def test_the_search_is_exact_when_the_budget_is_not_reached() -> None:
    pool = _pool(seed=1)
    bounds = compute_bounds(pool, ["pts"])
    rule = NormalAdpModel()
    exact = recommend(pool, DraftState(), ["pts"], bounds, rule, rounds=ROUNDS, top_k=10, max_candidates=len(pool))
    budgeted = plan_picks(
        pool, DraftState(), ["pts"], bounds, rule, rounds=ROUNDS, top_k=10, max_candidates=len(pool), node_budget=NODE_BUDGET
    )
    assert not budgeted.truncated
    assert [p.total_score for p in budgeted.plans] == pytest.approx([p.total_score for p in exact])
