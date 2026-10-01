"""
Merge and validate the per-screenshot transcription of Yahoo's projected stats.

Input:  <season_dir>/projections_raw.csv (one row per player per screenshot, overlaps included)
Output: <season_dir>/projections.csv (one row per player, sorted by XRank)

Rows seen in two consecutive screenshots must agree on every field, otherwise the run fails.
Gaps in XRank and values outside plausible ranges are reported as warnings.
"""

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd

VALID_POSITIONS = {"PG", "SG", "SF", "PF", "C"}
VALID_STATUS = {"", "Q", "P", "O"}
STAT_COLS = ["3ptm", "pts", "reb", "ast", "st", "blk", "to"]
# (column, min, max) plausible bounds for a season projection
RANGES = [
    ("gp", 20, 82),
    ("fg_pct", 0.35, 0.75),
    ("ft_pct", 0.50, 0.95),
    ("3ptm", 0, 400),
    ("pts", 300, 2600),
    ("reb", 40, 1200),
    ("ast", 40, 900),
    ("st", 10, 200),
    ("blk", 0, 300),
    ("to", 20, 350),
    ("adp", 1, 200),
]


def load_raw(path: Path) -> pd.DataFrame:
    """Read the raw transcription keeping `status` empty (not NaN) and the image id as text."""
    return pd.read_csv(path, dtype={"image": str}, keep_default_na=False, na_values=[""]).assign(
        status=lambda d: d["status"].fillna("")
    )


def find_overlap_mismatches(raw: pd.DataFrame) -> List[str]:
    """Return a message for every XRank whose readings differ between screenshots."""
    problems: List[str] = []
    value_cols = [c for c in raw.columns if c not in ("image", "xrank")]
    for xrank, group in raw.groupby("xrank"):
        if len(group.drop_duplicates(subset=value_cols)) > 1:
            images = ", ".join(group["image"])
            problems.append(f"XRank {xrank} differs between screenshots {images}:\n{group.to_string(index=False)}")
    return problems


def find_gaps(xranks: pd.Series) -> List[int]:
    """Return the XRanks missing between the first and last one seen."""
    seen = set(xranks.astype(int))
    return [x for x in range(min(seen), max(seen) + 1) if x not in seen]


def find_range_warnings(df: pd.DataFrame) -> List[str]:
    """Return a message for every value outside its plausible range."""
    warnings: List[str] = []
    for col, low, high in RANGES:
        bad = df[(df[col] < low) | (df[col] > high)]
        for _, row in bad.iterrows():
            warnings.append(f"{row['player']} ({row['team']}): {col}={row[col]} outside [{low}, {high}]")
    return warnings


def find_schema_problems(df: pd.DataFrame) -> List[str]:
    """Return errors for structural problems that make the data unusable."""
    problems: List[str] = []
    for _, row in df.iterrows():
        positions = set(str(row["positions"]).split(","))
        if not positions <= VALID_POSITIONS:
            problems.append(f"{row['player']}: unknown positions {sorted(positions - VALID_POSITIONS)}")
        if row["status"] not in VALID_STATUS:
            problems.append(f"{row['player']}: unknown status {row['status']!r}")
        if len(str(row["team"])) != 3:
            problems.append(f"{row['player']}: team {row['team']!r} is not a 3-letter code")
    duplicated = df[df.duplicated("player", keep=False)]
    if not duplicated.empty:
        problems.append(f"Players listed more than once:\n{duplicated[['xrank', 'player', 'team']].to_string(index=False)}")
    missing = df[df[STAT_COLS + ["gp", "fg_pct", "ft_pct", "rank", "xrank"]].isna().any(axis=1)]
    if not missing.empty:
        problems.append(f"Rows with missing required values:\n{missing[['xrank', 'player']].to_string(index=False)}")
    return problems


def main() -> int:
    """Merge the raw transcription, validate it and write the clean CSV."""
    parser = argparse.ArgumentParser(description="Merge and validate the Yahoo projection snapshots")
    parser.add_argument("--season-dir", type=Path, default=Path("data/2026-27"), help="Folder holding projections_raw.csv")
    args = parser.parse_args()

    raw = load_raw(args.season_dir / "projections_raw.csv")
    print(f"Read {len(raw)} raw rows from {raw['image'].nunique()} screenshots")

    mismatches = find_overlap_mismatches(raw)
    if mismatches:
        print("\nERROR: overlapping rows disagree, fix the transcription:")
        print("\n".join(mismatches))
        return 1
    print(f"Overlap check passed: {len(raw) - raw['xrank'].nunique()} repeated rows all agree")

    merged = raw.drop(columns="image").drop_duplicates().sort_values("xrank").reset_index(drop=True)

    problems = find_schema_problems(merged)
    if problems:
        print("\nERROR: invalid data:")
        print("\n".join(problems))
        return 1

    gaps = find_gaps(merged["xrank"])
    if gaps:
        print(f"\nWARNING: XRanks missing from the screenshots: {gaps}")
    for message in find_range_warnings(merged):
        print(f"WARNING: {message}")

    output = args.season_dir / "projections.csv"
    merged.to_csv(output, index=False)
    print(f"\nWrote {len(merged)} players to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
