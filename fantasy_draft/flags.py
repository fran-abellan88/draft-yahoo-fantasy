"""
Flags that put the projected score in the context of last season and of availability.

The score itself is always the projection. These flags never change it; they tell the user when a
projection deserves a second look.
"""

from typing import Sequence

import numpy as np
import pandas as pd

from fantasy_draft.data import LAST_SEASON_SUFFIX
from fantasy_draft.scoring import Bounds, composite_score

# Last season's average is noise below this many games (Kessler played 5, T. Young 15).
SMALL_SAMPLE_GP = 20
# Projected games played below this is a durability warning (Embiid is projected at 49).
LOW_PROJECTED_GP = 60
# Composite points (0-100) between the projection and last season before the gap is worth flagging.
DIVERGENCE_POINTS = 10.0


def last_season_composite(players: pd.DataFrame, keys: Sequence[str], bounds: Bounds) -> pd.Series:
    """
    Score last season's per-game averages on the same scale as the projections.

    Players with no data last season get NaN. The bounds come from the projection pool, so the two
    scores are directly comparable.
    """
    last_season = pd.DataFrame({key: players[f"{key}{LAST_SEASON_SUFFIX}"] for key in keys}, index=players.index)
    last_season["player"] = players["player"]
    has_data = last_season[list(keys)].notna().all(axis=1)
    scores = pd.Series(np.nan, index=players.index)
    if has_data.any():
        scores.loc[has_data] = composite_score(last_season[has_data], keys, bounds)
    return scores


def build_flags(
    players: pd.DataFrame,
    keys: Sequence[str],
    bounds: Bounds,
    small_sample_gp: int = SMALL_SAMPLE_GP,
    low_projected_gp: int = LOW_PROJECTED_GP,
    divergence_points: float = DIVERGENCE_POINTS,
) -> pd.DataFrame:
    """
    Return the projected and last-season composites with one boolean flag per concern.

    flag_ly_missing       no stats last season (injured, rookie, or a gap in Yahoo's data)
    flag_ly_small_sample  fewer than `small_sample_gp` games last season, so the average is noisy
    flag_ly_diverges      projection and last season differ by at least `divergence_points`; only raised
                          when last season is a usable sample, otherwise the small-sample flag explains it
    flag_low_projected_gp projected games played below `low_projected_gp`
    """
    projected = composite_score(players, keys, bounds)
    last_season = last_season_composite(players, keys, bounds)
    games_last_season = players[f"gp{LAST_SEASON_SUFFIX}"]

    missing = last_season.isna()
    small_sample = ~missing & (games_last_season < small_sample_gp)
    delta = projected - last_season
    diverges = ~missing & ~small_sample & (delta.abs() >= divergence_points)

    return pd.DataFrame(
        {
            "proj_composite": projected,
            "ly_composite": last_season,
            "ly_delta": delta,
            "flag_ly_missing": missing,
            "flag_ly_small_sample": small_sample,
            "flag_ly_diverges": diverges,
            "flag_low_projected_gp": players["gp"] < low_projected_gp,
        },
        index=players.index,
    )
