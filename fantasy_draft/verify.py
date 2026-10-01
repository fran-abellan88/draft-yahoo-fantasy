"""
Compare the draft-room snapshots (transcribed from screenshots) with Yahoo's player-list page.

The two are independent readings of the same numbers, so any difference is either a transcription
error or something that really changed between the two moments (injury tags change daily).
"""

from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from fantasy_draft.names import normalize_name

STAT_COLUMNS: List[str] = ["gp", "fg_pct", "ft_pct", "3ptm", "pts", "reb", "ast", "st", "blk", "to"]
TEXT_COLUMNS: List[str] = ["team", "positions"]
# Values that legitimately change between a screenshot and a later download
VOLATILE_COLUMNS: List[str] = ["status"]


def compare_with_yahoo(
    snapshot: pd.DataFrame,
    yahoo: pd.DataFrame,
    tolerances: Dict[str, float],
    stat_columns: Sequence[str] = STAT_COLUMNS,
) -> pd.DataFrame:
    """
    Return one row per difference between the snapshot and Yahoo, matched on normalised player name.

    Columns: xrank, player, column, snapshot, yahoo, kind. `kind` is "missing" for a snapshot player
    that Yahoo does not list, "stat" or "text" for a differing value, and "volatile" for fields that
    are expected to drift (injury status). `tolerances` gives the absolute tolerance per stat column
    (default 0, i.e. exact).
    """
    left = snapshot.assign(key=snapshot["player"].map(normalize_name))
    right = yahoo.assign(key=yahoo["player"].map(normalize_name))
    merged = left.merge(right, on="key", how="left", suffixes=("", "_yahoo"), indicator=True)

    differences: List[Dict[str, object]] = []
    for _, row in merged[merged["_merge"] == "left_only"].iterrows():
        differences.append(_difference(row, "player", "listed", "not listed", "missing"))
    found = merged[merged["_merge"] == "both"]

    for column in stat_columns:
        snapshot_values, yahoo_values = found[column].astype(float), found[f"{column}_yahoo"].astype(float)
        both_blank = snapshot_values.isna() & yahoo_values.isna()
        close = np.isclose(snapshot_values, yahoo_values, atol=tolerances.get(column, 0.0), rtol=0.0)
        for _, row in found[~both_blank & ~close].iterrows():
            differences.append(_difference(row, column, row[column], row[f"{column}_yahoo"], "stat"))
    for column, kind in [(c, "text") for c in TEXT_COLUMNS] + [(c, "volatile") for c in VOLATILE_COLUMNS]:
        snapshot_text, yahoo_text = found[column].fillna(""), found[f"{column}_yahoo"].fillna("")
        for _, row in found[snapshot_text != yahoo_text].iterrows():
            differences.append(_difference(row, column, row[column], row[f"{column}_yahoo"], kind))
    return pd.DataFrame(differences, columns=["xrank", "player", "column", "snapshot", "yahoo", "kind"])


def _difference(row: pd.Series, column: str, snapshot: object, yahoo: object, kind: str) -> Dict[str, object]:
    return {"xrank": row["xrank"], "player": row["player"], "column": column, "snapshot": snapshot, "yahoo": yahoo, "kind": kind}
