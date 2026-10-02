"""Tests for category weights from team needs."""

from typing import Dict

import pytest

from fantasy_draft.needs import MAX_SHIFT, RAMP_ROUNDS, category_weights, closeness
from fantasy_draft.optimizer import plan_picks
from fantasy_draft.scoring import composite_score, compute_bounds
from fantasy_draft.draft import DraftState
from fantasy_draft.availability import NormalAdpModel
from fantasy_draft.data import load_players

KEYS = ["pts", "reb", "ast", "to"]


def _standing(beaten: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    return {key: {"beaten": value} for key, value in beaten.items()}


def test_closeness_peaks_at_half_and_is_zero_at_the_ends() -> None:
    assert closeness(0.5) == 1.0 and closeness(0.0) == 0.0 and closeness(1.0) == 0.0
    assert closeness(0.25) == closeness(0.75) == pytest.approx(0.75)


def test_with_no_complete_round_every_weight_is_one() -> None:
    weights, ramp = category_weights(_standing({"pts": 0.0, "reb": 0.5, "ast": 1.0, "to": 0.3}), KEYS, 0)
    assert ramp == 0.0 and all(value == pytest.approx(1.0) for value in weights.values())


def test_a_close_category_outweighs_one_far_ahead_or_far_behind() -> None:
    weights, ramp = category_weights(_standing({"pts": 0.95, "reb": 0.5, "ast": 0.05, "to": 0.5}), KEYS, RAMP_ROUNDS)
    assert ramp == 1.0
    assert weights["reb"] > weights["pts"] and weights["reb"] > weights["ast"]
    assert weights["pts"] == pytest.approx(weights["ast"])


def test_weights_never_leave_the_cap_after_normalising_and_cover_only_the_ticked_categories() -> None:
    standing = _standing({"pts": 0.9, "reb": 0.5, "ast": 0.1, "to": 0.6, "blk": 0.5})
    weights, _ = category_weights(standing, ["pts", "reb"], 8)
    assert set(weights) == {"pts", "reb"}, "an unticked category is never given a weight"
    assert all(1 - MAX_SHIFT <= value <= 1 + MAX_SHIFT for value in weights.values())
    # a lopsided league: one category close, the rest decided; the cap holds even after dividing by the mean
    lopsided = _standing({"a": 0.5, **{key: 0.0 for key in "bcdefgh"}})
    spread, _ = category_weights(lopsided, list("abcdefgh"), 8)
    assert max(spread.values()) <= 1 + MAX_SHIFT and min(spread.values()) >= 1 - MAX_SHIFT


def test_the_ramp_grows_with_complete_rounds() -> None:
    standing = _standing({"pts": 0.95, "reb": 0.5})
    spreads = []
    for rounds in range(0, RAMP_ROUNDS + 2):
        weights, _ = category_weights(standing, ["pts", "reb"], rounds)
        spreads.append(weights["reb"] - weights["pts"])
    assert spreads == sorted(spreads) and spreads[-1] == spreads[-2], "grows, then stops at the full effect"


def test_equal_weights_give_exactly_todays_scores_and_plans() -> None:
    players = load_players()
    keys = ["fg_pct", "ft_pct", "3ptm", "pts", "reb", "ast", "st", "blk", "to"]
    bounds = compute_bounds(players, keys, method="uncapped")
    plain = composite_score(players, keys, bounds, True, "uncapped")
    equal = composite_score(players, keys, bounds, True, "uncapped", {key: 1.0 for key in keys})
    assert equal.to_numpy() == pytest.approx(plain.to_numpy(), abs=1e-9)
    weights = {key: 1.0 for key in keys}
    state = DraftState()
    one = plan_picks(players, state, keys, bounds, NormalAdpModel(), games_adjusted=True, method="uncapped")
    two = plan_picks(players, state, keys, bounds, NormalAdpModel(), games_adjusted=True, method="uncapped", weights=weights)
    assert one.plans[0].player_ids == two.plans[0].player_ids and one.plans[0].total_score == pytest.approx(two.plans[0].total_score)


def test_a_heavier_category_moves_the_score_towards_players_strong_in_it() -> None:
    players = load_players()
    keys = ["pts", "blk"]
    bounds = compute_bounds(players, keys, method="uncapped")
    plain = composite_score(players, keys, bounds, False, "uncapped")
    heavy = composite_score(players, keys, bounds, False, "uncapped", {"pts": 0.5, "blk": 1.5})
    best_block = players["blk"].idxmax()
    assert heavy[best_block] - plain[best_block] > 0


@pytest.mark.parametrize("weights", [{"pts": 1.0}, {"pts": -1.0, "blk": 1.0}, {"pts": 0.0, "blk": 0.0}])
def test_bad_weights_are_refused(weights: Dict[str, float]) -> None:
    players = load_players()
    bounds = compute_bounds(players, ["pts", "blk"], method="uncapped")
    with pytest.raises(ValueError):
        composite_score(players, ["pts", "blk"], bounds, False, "uncapped", weights)
