"""
Composite score over a user-selected set of categories.

Same formula as the composite in nba-yahoo-fantasy-daily-dose (src/etl/composite_score.py)::

    score = (value - p5) / (p95 - p5)        clamped to [0, 1]
    score = (p95 - value) / (p95 - p5)       for categories where lower is better (TO)
    composite = mean(selected scores) * 100

Two deliberate differences from that implementation:

* The mean is over the categories the user selected, not over a fixed nine. The divisor is a choice
  made by the user, not missing data.
* A missing value is an error. The daily-dose version reads it as 0, which is right for a game log
  but would silently turn "no data" into "worst player" here.

Bounds are computed once over the whole player pool and every selectable category, so toggling a
category never moves the scores of the others.
"""

from typing import Dict, Sequence, Tuple

import numpy as np
import pandas as pd

from fantasy_draft.categories import CATEGORIES

Bounds = Dict[str, Tuple[float, float]]

SEASON_GAMES = 82


def compute_bounds(players: pd.DataFrame, keys: Sequence[str], low: float = 5.0, high: float = 95.0) -> Bounds:
    """Return the (p_low, p_high) boundary of each category over the player pool."""
    _check_keys(players, keys)
    bounds: Bounds = {}
    for key in keys:
        values = players[CATEGORIES[key].column].dropna().astype(float)
        bounds[key] = (float(np.percentile(values, low)), float(np.percentile(values, high)))
    return bounds


def category_scores(players: pd.DataFrame, keys: Sequence[str], bounds: Bounds) -> pd.DataFrame:
    """Score each selected category on a 0-1 scale, one column per category."""
    _check_keys(players, keys)
    missing_bounds = [key for key in keys if key not in bounds]
    if missing_bounds:
        raise ValueError(f"No bounds for categories: {missing_bounds}")
    _check_no_missing_values(players, keys)

    scores: Dict[str, pd.Series] = {}
    for key in keys:
        low, high = bounds[key]
        span = high - low
        if span == 0:
            # A degenerate boundary carries no information, so nobody is advantaged or penalised.
            scores[key] = pd.Series(0.5, index=players.index)
            continue
        values = players[CATEGORIES[key].column].astype(float)
        raw = (high - values) / span if CATEGORIES[key].lower_is_better else (values - low) / span
        scores[key] = raw.clip(0.0, 1.0)
    return pd.DataFrame(scores, index=players.index)


def games_factor(players: pd.DataFrame) -> pd.Series:
    """Share of a full season each player is projected to play (capped at 1), from the projected `gp` column."""
    if "gp" not in players.columns or players["gp"].isna().any():
        raise ValueError("The games-played adjustment needs a projected gp for every player")
    return (players["gp"].astype(float) / SEASON_GAMES).clip(0.0, 1.0)


def composite_score(players: pd.DataFrame, keys: Sequence[str], bounds: Bounds, games_adjusted: bool = False) -> pd.Series:
    """Return the 0-100 composite of the selected categories for every player.

    With `games_adjusted` the composite is scaled by the share of the season the player is projected to play.
    The scale is anchored at 0, which is the 5th-percentile player in every category, so a missed game is
    worth roughly a replacement-level game.
    """
    composite = category_scores(players, keys, bounds).mean(axis=1) * 100.0
    return composite * games_factor(players) if games_adjusted else composite


def _check_keys(players: pd.DataFrame, keys: Sequence[str]) -> None:
    """Reject an empty, duplicated, unknown or absent selection."""
    if not keys:
        raise ValueError("Select at least one category")
    if len(set(keys)) != len(keys):
        raise ValueError(f"Duplicated categories would be counted twice: {list(keys)}")
    unknown = [key for key in keys if key not in CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown categories: {unknown}")
    absent = [key for key in keys if CATEGORIES[key].column not in players.columns]
    if absent:
        raise ValueError(f"The player table has no column for: {absent}")


def _check_no_missing_values(players: pd.DataFrame, keys: Sequence[str]) -> None:
    """Fail loudly when a selected category has missing values."""
    missing = players[[CATEGORIES[key].column for key in keys]].isna().any(axis=1)
    if missing.any():
        names = players.loc[missing, "player"].tolist() if "player" in players.columns else players.index[missing].tolist()
        raise ValueError(f"Missing values in the selected categories for: {names}")
