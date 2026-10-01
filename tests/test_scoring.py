"""Tests for the composite score, including parity with the daily-dose golden fixture."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from fantasy_draft.scoring import Bounds, category_scores, composite_score, compute_bounds

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
    stats = {GOLDEN_TO_KEY[name]: value for name, value in case["stats"].items()}
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
