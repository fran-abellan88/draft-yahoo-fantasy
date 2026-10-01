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

Three scoring methods share that structure:

* ``capped``    the formula above (golden-tested against daily-dose). Anyone beyond the 95th percentile in a
                category scores the same as someone exactly at it.
* ``uncapped``  the same scale (0 at the 5th percentile, 1 at the 95th) without the clamp, so a 32-point
                scorer is worth more than a 26-point one. Scores can fall below 0 and rise above 1.
* ``zscore``    standard deviations from the pool mean in each category (reversed for turnovers), x10 at the
                composite. It measures distance in units of how much players actually differ in that category.
"""

from typing import Dict, Sequence, Tuple

import numpy as np
import pandas as pd

from fantasy_draft.categories import CATEGORIES

Bounds = Dict[str, Tuple[float, float]]

SEASON_GAMES = 82
METHODS = ("capped", "uncapped", "zscore")
Z_SCALE = 10.0  # the z-score composite is the mean z x 10, so it reads on a scale similar to the others


def compute_bounds(
    players: pd.DataFrame, keys: Sequence[str], low: float = 5.0, high: float = 95.0, method: str = "capped"
) -> Bounds:
    """Return each category's reference points over the player pool.

    That is (p_low, p_high) for ``capped`` and ``uncapped``, and (mean, standard deviation) for ``zscore``.
    """
    _check_keys(players, keys)
    _check_method(method)
    bounds: Bounds = {}
    for key in keys:
        values = players[CATEGORIES[key].column].dropna().astype(float)
        if method == "zscore":
            bounds[key] = (float(values.mean()), float(values.std(ddof=0)))
        else:
            bounds[key] = (float(np.percentile(values, low)), float(np.percentile(values, high)))
    return bounds


def category_scores(players: pd.DataFrame, keys: Sequence[str], bounds: Bounds, method: str = "capped") -> pd.DataFrame:
    """Score each selected category, one column per category: 0-1 for ``capped``, unbounded otherwise."""
    _check_keys(players, keys)
    _check_method(method)
    missing_bounds = [key for key in keys if key not in bounds]
    if missing_bounds:
        raise ValueError(f"No bounds for categories: {missing_bounds}")
    _check_no_missing_values(players, keys)

    scores: Dict[str, pd.Series] = {}
    for key in keys:
        low, high = bounds[key]
        values = players[CATEGORIES[key].column].astype(float)
        if method == "zscore":
            if high == 0:
                scores[key] = pd.Series(0.0, index=players.index)
                continue
            scores[key] = (low - values) / high if CATEGORIES[key].lower_is_better else (values - low) / high
            continue
        span = high - low
        if span == 0:
            # A degenerate boundary carries no information, so nobody is advantaged or penalised.
            scores[key] = pd.Series(0.5, index=players.index)
            continue
        raw = (high - values) / span if CATEGORIES[key].lower_is_better else (values - low) / span
        scores[key] = raw.clip(0.0, 1.0) if method == "capped" else raw
    return pd.DataFrame(scores, index=players.index)


def games_factor(players: pd.DataFrame) -> pd.Series:
    """Share of a full season each player is projected to play (capped at 1), from the projected `gp` column."""
    if "gp" not in players.columns or players["gp"].isna().any():
        raise ValueError("The games-played adjustment needs a projected gp for every player")
    return (players["gp"].astype(float) / SEASON_GAMES).clip(0.0, 1.0)


def composite_score(
    players: pd.DataFrame, keys: Sequence[str], bounds: Bounds, games_adjusted: bool = False, method: str = "capped"
) -> pd.Series:
    """Return the composite of the selected categories for every player (0-100 for ``capped``).

    With `games_adjusted` the distance above a replacement-level player is scaled by the share of the season
    the player is projected to play, so a missed game is worth a replacement-level game. Replacement level is
    a player at the 5th percentile of every category (the 95th for turnovers). For ``capped`` and ``uncapped``
    that player scores 0 and the adjustment is a plain multiplication. For ``zscore`` the level comes from
    `players`, so pass the whole pool.
    """
    composite = _composite(players, keys, bounds, method)
    if not games_adjusted:
        return composite
    anchor = _replacement_composite(players, keys, bounds, method)
    return anchor + (composite - anchor) * games_factor(players)


def _composite(players: pd.DataFrame, keys: Sequence[str], bounds: Bounds, method: str) -> pd.Series:
    scale = Z_SCALE if method == "zscore" else 100.0
    return category_scores(players, keys, bounds, method).mean(axis=1) * scale


def _replacement_composite(players: pd.DataFrame, keys: Sequence[str], bounds: Bounds, method: str) -> float:
    """Composite of a player at replacement level in every selected category."""
    if method != "zscore":
        return 0.0  # the 5th percentile (95th for turnovers) is where these scales start
    values: Dict[str, float] = {}
    for key in keys:
        category = CATEGORIES[key]
        pool = players[category.column].dropna().astype(float)
        values[category.column] = float(np.percentile(pool, 95.0 if category.lower_is_better else 5.0))
    return float(_composite(pd.DataFrame([values]), keys, bounds, method).iloc[0])


def _check_method(method: str) -> None:
    if method not in METHODS:
        raise ValueError(f"Unknown scoring method: {method!r}")


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
