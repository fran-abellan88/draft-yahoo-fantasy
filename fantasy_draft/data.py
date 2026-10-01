"""
Load the player pool: projected per-game stats for 2026-27 with last season's averages alongside.

The projections file holds season totals, so counting stats are divided by projected games played.
Percentages are kept as rates and are not selectable until attempts are available (see categories.py).
"""

import re
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROJECTIONS_PATH = DATA_DIR / "2026-27" / "projections.csv"
AVERAGES_PATH = DATA_DIR / "2025-26" / "averages.csv"

COUNTING_STATS: List[str] = ["3ptm", "pts", "reb", "ast", "st", "blk", "to"]
RATE_STATS: List[str] = ["fg_pct", "ft_pct"]
LAST_SEASON_SUFFIX = "_ly"


def slugify(name: str) -> str:
    """Return a stable ASCII id for a player name, e.g. "Jaren Jackson Jr." -> "jaren-jackson-jr"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_players(projections_path: Path = PROJECTIONS_PATH, averages_path: Path = AVERAGES_PATH) -> pd.DataFrame:
    """
    Return one row per player with projected per-game stats and last season's per-game averages.

    Last season's columns carry the `_ly` suffix and are NaN for players with no stats last season
    (injured, rookies, or a gap in Yahoo's data).
    """
    projections = pd.read_csv(projections_path, keep_default_na=False, na_values=[""])
    averages = pd.read_csv(averages_path, keep_default_na=False, na_values=[""])
    projections["status"] = projections["status"].fillna("")

    if (projections["gp"] <= 0).any():
        raise ValueError("Projected games played must be positive to convert totals to per-game")
    for stat in COUNTING_STATS:
        projections[stat] = projections[stat] / projections["gp"]

    last_season_cols = ["gp"] + COUNTING_STATS + RATE_STATS
    last_season = averages[["xrank", "player"] + last_season_cols].rename(
        columns={col: f"{col}{LAST_SEASON_SUFFIX}" for col in last_season_cols} | {"player": "player_ly_name"}
    )
    players = projections.merge(last_season, on="xrank", how="left")

    mismatched = players[players["player_ly_name"].notna() & (players["player_ly_name"] != players["player"])]
    if not mismatched.empty:
        raise ValueError(f"Projections and averages disagree on the player at XRank: {mismatched['xrank'].tolist()}")

    players = players.drop(columns="player_ly_name")
    players["player_id"] = players["player"].map(slugify)
    if players["player_id"].duplicated().any():
        raise ValueError("Two players share the same id")
    players["pos_list"] = players["positions"].str.split(",")
    players = players.sort_values("xrank").reset_index(drop=True)

    # Yahoo shows no ADP for a few players (nobody drafts them early). Estimate it from the neighbouring
    # XRanks so availability can still be modelled, and keep the original column untouched.
    known = players["adp"].notna()
    players["adp_estimated"] = ~known
    players["adp_est"] = players["adp"]
    players.loc[~known, "adp_est"] = np.interp(players.loc[~known, "xrank"], players.loc[known, "xrank"], players.loc[known, "adp"])
    return players
