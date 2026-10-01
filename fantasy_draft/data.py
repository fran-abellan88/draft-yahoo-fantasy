"""
Load the player pool: projected per-game stats for 2026-27 with last season's per-game stats alongside.

Sources
    data/2026-27/projections.csv         draft-room snapshot: XRank, Rank and ADP (only the draft room has them)
    data/2026-27/yahoo_projections.csv   Yahoo player list: projected season totals with attempts, GP, status
    data/2025-26/yahoo_totals.csv        Yahoo player list: last season's totals with attempts and minutes

The snapshot's own stat columns are not used here; they were verified against the Yahoo page (see
verify_snapshots.py) and the page is the better source because it carries attempts.

Totals are divided by games played to get per-game values. FG% and FT% are turned into volume-weighted
"impact" columns: makes above what a baseline shooter would have made on the same attempts, per game.
Unlike a raw percentage, impact adds up across a roster, which is what a head-to-head matchup compares.
"""

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from fantasy_draft.names import normalize_name, slugify

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_PATH = DATA_DIR / "2026-27" / "projections.csv"
YAHOO_PROJECTIONS_PATH = DATA_DIR / "2026-27" / "yahoo_projections.csv"
YAHOO_TOTALS_PATH = DATA_DIR / "2025-26" / "yahoo_totals.csv"

COUNTING_STATS: List[str] = ["3ptm", "pts", "reb", "ast", "st", "blk", "to"]
ATTEMPT_STATS: List[str] = ["fgm", "fga", "ftm", "fta"]
PER_GAME_STATS: List[str] = COUNTING_STATS + ATTEMPT_STATS
LAST_SEASON_SUFFIX = "_ly"


def load_players(
    snapshot_path: Path = SNAPSHOT_PATH,
    projections_path: Path = YAHOO_PROJECTIONS_PATH,
    totals_path: Path = YAHOO_TOTALS_PATH,
) -> pd.DataFrame:
    """
    Return one row per player with projected per-game stats and last season's per-game stats.

    Last season's columns carry the `_ly` suffix and are NaN for players with no stats last season
    (injured, rookies, or a gap in Yahoo's data). `fg_impact` / `ft_impact` (and their `_ly` versions)
    are the per-game makes above the pool's projected baseline; the baselines are kept in `.attrs`.
    """
    snapshot = pd.read_csv(snapshot_path, keep_default_na=False, na_values=[""])[["xrank", "rank", "adp", "player"]]
    projections = _read_yahoo(projections_path)
    totals = _read_yahoo(totals_path)

    players = _join_on_name(snapshot, projections, "projections")
    if (players["gp"] <= 0).any():
        raise ValueError("Projected games played must be positive to convert totals to per-game")
    players = _per_game(players)

    last_season = _per_game(totals).rename(columns=lambda column: f"{column}{LAST_SEASON_SUFFIX}")
    last_season["match_key"] = last_season[f"match_key{LAST_SEASON_SUFFIX}"]
    keep = [f"{column}{LAST_SEASON_SUFFIX}" for column in ["gp", "mpg", "fg_pct", "ft_pct"] + PER_GAME_STATS]
    players = players.merge(last_season[["match_key"] + keep], on="match_key", how="left")

    baselines = _baselines(projections.loc[projections["match_key"].isin(players["match_key"])])
    for prefix, rate in (("fg", baselines["fg"]), ("ft", baselines["ft"])):
        for suffix in ("", LAST_SEASON_SUFFIX):
            made, attempted = f"{prefix}m{suffix}", f"{prefix}a{suffix}"
            players[f"{prefix}_impact{suffix}"] = players[made] - rate * players[attempted]

    players["player_id"] = players["player"].map(slugify)
    if players["player_id"].duplicated().any():
        raise ValueError("Two players share the same id")
    players["pos_list"] = players["positions"].str.split(",")
    players = players.sort_values("xrank").reset_index(drop=True)
    players = _estimate_missing_adp(players)
    players.attrs["baselines"] = baselines
    return players


def _read_yahoo(path: Path) -> pd.DataFrame:
    """Read a Yahoo player-list CSV and add the key used to join it to the snapshot."""
    frame = pd.read_csv(path, keep_default_na=False, na_values=[""])
    frame["status"] = frame["status"].fillna("")
    frame["match_key"] = frame["player"].map(normalize_name)
    if frame["match_key"].duplicated().any():
        raise ValueError(f"{path.name} lists two players with the same normalised name")
    return frame


def _join_on_name(snapshot: pd.DataFrame, yahoo: pd.DataFrame, label: str) -> pd.DataFrame:
    """Attach Yahoo's stats to each snapshot player; every snapshot player must be found."""
    # The snapshot's ASCII name stays the canonical one (ids, tests); Yahoo's spelling is kept for display
    snapshot = snapshot.assign(match_key=snapshot["player"].map(normalize_name))
    joined = snapshot.merge(yahoo.rename(columns={"player": "yahoo_name"}), on="match_key", how="left", indicator=True)
    missing = joined[joined["_merge"] == "left_only"]
    if not missing.empty:
        raise ValueError(f"Snapshot players not found in the Yahoo {label} list (XRank): {missing['xrank'].tolist()}")
    return joined.drop(columns="_merge")


def _per_game(totals: pd.DataFrame) -> pd.DataFrame:
    """Divide every counting and attempt column by games played."""
    per_game = totals.copy()
    games = totals["gp"].replace(0, np.nan)  # no games played means no per-game value, not infinity
    for stat in PER_GAME_STATS:
        per_game[stat] = totals[stat] / games
    return per_game


def _baselines(projections: pd.DataFrame) -> Dict[str, float]:
    """Pool-wide shooting rates: total makes over total attempts, from the projected totals."""
    return {
        "fg": float(projections["fgm"].sum() / projections["fga"].sum()),
        "ft": float(projections["ftm"].sum() / projections["fta"].sum()),
    }


def _estimate_missing_adp(players: pd.DataFrame) -> pd.DataFrame:
    """
    Yahoo shows no ADP for a few players (nobody drafts them early). Estimate it from the neighbouring
    XRanks so availability can still be modelled; the original column is left untouched.
    """
    known = players["adp"].notna()
    players["adp_estimated"] = ~known
    players["adp_est"] = players["adp"]
    players.loc[~known, "adp_est"] = np.interp(players.loc[~known, "xrank"], players.loc[known, "xrank"], players.loc[known, "adp"])
    return players
