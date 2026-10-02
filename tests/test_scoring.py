"""Tests for the composite score, including parity with the daily-dose golden fixture."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from fantasy_draft.categories import CATEGORIES
from fantasy_draft.scoring import Bounds, category_scores, composite_score, compute_bounds, games_factor

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "composite_score_golden.json"

# daily-dose stat names -> the column names used here
GOLDEN_TO_KEY: Dict[str, str] = {
    "points": "pts",
    "rebounds": "reb",
    "assists": "ast",
    "steals": "st",
    "blocks": "blk",
    "turnovers": "to",
    "field_goal_percentage": "fg_pct",
    "free_throw_percentage": "ft_pct",
    "three_pointers_made": "3ptm",
}


def _golden() -> Dict[str, Any]:
    with open(GOLDEN_PATH) as handle:
        return json.load(handle)


def _golden_bounds() -> Bounds:
    boundaries = _golden()["boundaries"]
    return {GOLDEN_TO_KEY[name]: (b["percentile_5th"], b["percentile_95th"]) for name, b in boundaries.items()}


def _frame(rows: List[Dict[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows).assign(player=lambda d: [f"p{i}" for i in range(len(d))])


@pytest.mark.parametrize("case", _golden()["cases"], ids=lambda case: case["name"])
def test_matches_daily_dose_golden_cases(case: Dict[str, Any]) -> None:
    # The formula does not care what the number is, so the golden percentages go in the impact columns here
    stats = {CATEGORIES[GOLDEN_TO_KEY[name]].column: value for name, value in case["stats"].items()}
    keys = list(GOLDEN_TO_KEY.values())
    score = composite_score(_frame([stats]), keys, _golden_bounds())
    assert score.iloc[0] == pytest.approx(case["expected"], abs=1e-6)


def test_lower_is_better_for_turnovers() -> None:
    bounds: Bounds = {"to": (1.0, 3.0)}
    players = _frame([{"to": 1.0}, {"to": 2.0}, {"to": 3.0}])
    assert category_scores(players, ["to"], bounds)["to"].tolist() == [1.0, 0.5, 0.0]


def test_scores_are_clamped_to_unit_interval() -> None:
    bounds: Bounds = {"pts": (10.0, 20.0)}
    players = _frame([{"pts": 0.0}, {"pts": 15.0}, {"pts": 40.0}])
    assert category_scores(players, ["pts"], bounds)["pts"].tolist() == [0.0, 0.5, 1.0]


def test_degenerate_bounds_score_everyone_the_same() -> None:
    players = _frame([{"pts": 5.0}, {"pts": 30.0}])
    assert category_scores(players, ["pts"], {"pts": (7.0, 7.0)})["pts"].tolist() == [0.5, 0.5]


def test_divisor_is_the_number_of_selected_categories() -> None:
    bounds: Bounds = {"pts": (0.0, 10.0), "reb": (0.0, 10.0), "ast": (0.0, 10.0)}
    players = _frame([{"pts": 10.0, "reb": 0.0, "ast": 5.0}])
    assert composite_score(players, ["pts"], bounds).iloc[0] == pytest.approx(100.0)
    assert composite_score(players, ["pts", "reb"], bounds).iloc[0] == pytest.approx(50.0)
    assert composite_score(players, ["pts", "reb", "ast"], bounds).iloc[0] == pytest.approx(50.0)


def test_toggling_a_category_does_not_move_the_others() -> None:
    players = _frame([{"pts": 12.0, "reb": 8.0}, {"pts": 25.0, "reb": 3.0}])
    bounds = compute_bounds(players, ["pts", "reb"])
    alone = category_scores(players, ["pts"], bounds)["pts"]
    together = category_scores(players, ["pts", "reb"], bounds)["pts"]
    assert alone.tolist() == together.tolist()


def test_bounds_are_percentiles_of_the_pool() -> None:
    players = _frame([{"pts": float(value)} for value in range(101)])
    assert compute_bounds(players, ["pts"]) == {"pts": (5.0, 95.0)}


def test_missing_value_is_an_error_not_a_zero() -> None:
    players = _frame([{"pts": 10.0}, {"pts": float("nan")}])
    with pytest.raises(ValueError, match="p1"):
        composite_score(players, ["pts"], {"pts": (0.0, 20.0)})


@pytest.mark.parametrize(
    "keys, message",
    [
        ([], "at least one"),
        (["pts", "pts"], "Duplicated"),
        (["dunks"], "Unknown"),
        (["reb"], "no column"),
    ],
)
def test_invalid_selection_is_rejected(keys: List[str], message: str) -> None:
    players = _frame([{"pts": 10.0}])
    with pytest.raises(ValueError, match=message):
        composite_score(players, keys, {"pts": (0.0, 20.0), "reb": (0.0, 10.0)})


def test_selected_category_without_bounds_is_rejected() -> None:
    with pytest.raises(ValueError, match="No bounds"):
        composite_score(_frame([{"pts": 10.0}]), ["pts"], {})


def test_games_adjustment_scales_the_composite_by_the_share_of_the_season() -> None:
    players = pd.DataFrame({"pts": [10.0, 20.0, 30.0], "gp": [82.0, 41.0, 90.0]})
    bounds = {"pts": (10.0, 30.0)}
    plain = composite_score(players, ["pts"], bounds)
    adjusted = composite_score(players, ["pts"], bounds, games_adjusted=True)
    assert list(plain) == [0.0, 50.0, 100.0]
    assert list(adjusted) == [0.0, 25.0, 100.0]  # 41 games is half a season; more than 82 is not a bonus


def test_games_adjustment_is_off_by_default_and_needs_games() -> None:
    players = pd.DataFrame({"pts": [10.0, 30.0], "gp": [82.0, float("nan")]})
    bounds = {"pts": (10.0, 30.0)}
    assert list(composite_score(players, ["pts"], bounds)) == [0.0, 100.0]
    with pytest.raises(ValueError, match="projected gp"):
        composite_score(players, ["pts"], bounds, games_adjusted=True)
    with pytest.raises(ValueError, match="projected gp"):
        games_factor(players.drop(columns="gp"))


def test_uncapped_scores_exceed_the_unit_interval_instead_of_clamping() -> None:
    players = pd.DataFrame({"pts": [5.0, 10.0, 20.0, 30.0, 40.0]})
    bounds = {"pts": (10.0, 30.0)}
    capped = category_scores(players, ["pts"], bounds)["pts"].tolist()
    uncapped = category_scores(players, ["pts"], bounds, method="uncapped")["pts"].tolist()
    assert capped == [0.0, 0.0, 0.5, 1.0, 1.0]
    assert uncapped == [-0.25, 0.0, 0.5, 1.0, 1.5]


def test_uncapped_matches_capped_inside_the_bounds() -> None:
    players = pd.DataFrame({"pts": [12.0, 20.0, 28.0], "to": [1.5, 2.0, 2.5]})
    bounds = compute_bounds(pd.DataFrame({"pts": [10.0, 20.0, 30.0], "to": [1.0, 2.0, 3.0]}), ["pts", "to"], 0, 100)
    assert composite_score(players, ["pts", "to"], bounds, method="uncapped").tolist() == pytest.approx(
        composite_score(players, ["pts", "to"], bounds).tolist()
    )


def test_zscore_is_distance_from_the_mean_in_standard_deviations_with_turnovers_reversed() -> None:
    pool = pd.DataFrame({"pts": [10.0, 20.0, 30.0], "to": [1.0, 2.0, 3.0]})
    bounds = compute_bounds(pool, ["pts", "to"], method="zscore")
    assert bounds["pts"][0] == pytest.approx(20.0) and bounds["pts"][1] == pytest.approx((200 / 3) ** 0.5)
    scores = category_scores(pool, ["pts", "to"], bounds, method="zscore")
    assert scores["pts"].tolist() == pytest.approx([-1.2247, 0.0, 1.2247], abs=1e-4)
    assert scores["to"].tolist() == pytest.approx([1.2247, 0.0, -1.2247], abs=1e-4)
    assert composite_score(pool, ["pts", "to"], bounds, method="zscore").tolist() == pytest.approx([0.0, 0.0, 0.0], abs=1e-9)


def test_zscore_games_adjustment_pulls_towards_replacement_level_not_towards_average() -> None:
    pool = pd.DataFrame({"pts": [10.0, 20.0, 30.0, 40.0], "gp": [41.0, 41.0, 82.0, 82.0]})
    bounds = compute_bounds(pool, ["pts"], method="zscore")
    plain = composite_score(pool, ["pts"], bounds, method="zscore")
    adjusted = composite_score(pool, ["pts"], bounds, games_adjusted=True, method="zscore")
    assert adjusted[1] < plain[1]  # an average-ish scorer who misses half the season is worth less
    # Replacement level is the 5th percentile (11.5 points): z = (11.5 - 25) / sqrt(125), x10
    replacement = (11.5 - 25.0) / 125.0 ** 0.5 * 10.0
    assert adjusted[0] == pytest.approx(replacement + (plain[0] - replacement) * 0.5)
    assert adjusted[2] == plain[2] and adjusted[3] == plain[3]


def test_unknown_method_is_rejected() -> None:
    pool = pd.DataFrame({"pts": [10.0, 20.0, 30.0]})
    with pytest.raises(ValueError, match="scoring method"):
        compute_bounds(pool, ["pts"], method="rank")
