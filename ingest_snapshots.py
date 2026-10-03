"""
Merge and validate the per-screenshot transcription of Yahoo player stats.

Two kinds of snapshots are supported:
  projections  data/2026-27/projections_raw.csv -> projections.csv  (projected season totals)
  averages     data/2025-26/averages_raw.csv    -> averages.csv     (last season's per-game averages)

Rows seen in two consecutive screenshots must agree on every field, otherwise the run fails.
Averages are also cross-checked against the projections: both views show the same player list, so
XRank, name, team, positions, status and ADP were read twice independently and must match.
Gaps in XRank and values outside plausible ranges are reported as warnings.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

import pandas as pd

VALID_POSITIONS = {"PG", "SG", "SF", "PF", "C"}
VALID_STATUS = {"", "Q", "P", "O"}
STAT_COLS = ["gp", "fg_pct", "ft_pct", "3ptm", "pts", "reb", "ast", "st", "blk", "to"]
SHARED_COLS = ["player", "team", "positions", "status", "adp"]
# Only the first 250 XRanks are kept in both datasets; the raw files keep every row that was transcribed
MAX_XRANK = 250

Range = Tuple[str, float, float]


class Kind(NamedTuple):
    """Where a kind of snapshot lives and what a plausible value looks like."""

    raw_name: str
    out_name: str
    season_dir: str
    ranges: List[Range]
    allow_no_data: bool


KINDS: Dict[str, Kind] = {
    "projections": Kind(
        "projections_raw.csv",
        "projections.csv",
        "data/2026-27",
        [
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
        ],
        False,
    ),
    "averages": Kind(
        "averages_raw.csv",
        "averages.csv",
        "data/2025-26",
        [
            ("gp", 1, 82),
            ("fg_pct", 0.35, 0.75),
            ("ft_pct", 0.45, 1.0),
            ("3ptm", 0, 5.5),
            ("pts", 2, 40),
            ("reb", 0.5, 15),
            ("ast", 0, 12),
            ("st", 0, 2.5),
            ("blk", 0, 3.5),
            ("to", 0, 5),
            ("adp", 1, 200),
        ],
        True,
    ),
}


def load_raw(path: Path) -> pd.DataFrame:
    """Read the raw transcription keeping `status` empty (not NaN) and the image id as text."""
    raw = pd.read_csv(path, dtype={"image": str}, keep_default_na=False, na_values=[""])
    raw["status"] = raw["status"].fillna("")
    return raw


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


def find_range_warnings(df: pd.DataFrame, ranges: List[Range]) -> List[str]:
    """Return a message for every value outside its plausible range."""
    warnings: List[str] = []
    for col, low, high in ranges:
        bad = df[(df[col] < low) | (df[col] > high)]
        for _, row in bad.iterrows():
            warnings.append(f"{row['player']} ({row['team']}): {col}={row[col]} outside [{low}, {high}]")
    return warnings


def find_schema_problems(df: pd.DataFrame, allow_no_data: bool) -> List[str]:
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
    stats = df[STAT_COLS]
    # A player with no data last season (injured, rookie) has every stat blank; a partly blank row is a typo
    partial = df[stats.isna().any(axis=1) & ~stats.isna().all(axis=1)]
    if not partial.empty:
        problems.append(f"Rows with some stats missing:\n{partial[['xrank', 'player']].to_string(index=False)}")
    if not allow_no_data:
        empty = df[stats.isna().all(axis=1)]
        if not empty.empty:
            problems.append(f"Rows with no stats:\n{empty[['xrank', 'player']].to_string(index=False)}")
    return problems


def cross_check(averages: pd.DataFrame, projections: pd.DataFrame) -> List[str]:
    """Compare the fields both Yahoo views show for the same XRank, which were read independently."""
    problems: List[str] = []
    joined = averages.merge(projections, on="xrank", suffixes=("_avg", "_proj"))
    for col in SHARED_COLS:
        left, right = joined[f"{col}_avg"], joined[f"{col}_proj"]
        differs = ~((left == right) | (left.isna() & right.isna()))
        for _, row in joined[differs].iterrows():
            problems.append(
                f"XRank {row['xrank']} {row['player_proj']}: {col} is {row[f'{col}_avg']!r} in averages, "
                f"{row[f'{col}_proj']!r} in projections"
            )
    missing_in_averages = sorted(set(projections["xrank"]) - set(averages["xrank"]))
    if missing_in_averages:
        problems.append(f"XRanks in projections but not in averages: {missing_in_averages}")
    print(f"Cross-check against projections: {len(joined)} players compared on {', '.join(SHARED_COLS)}")
    return problems


def main() -> int:
    """Merge the raw transcription, validate it and write the clean CSV."""
    parser = argparse.ArgumentParser(description="Merge and validate the Yahoo snapshots")
    parser.add_argument("kind", choices=sorted(KINDS), help="Which snapshots to ingest")
    args = parser.parse_args()
    kind = KINDS[args.kind]
    season_dir = Path(kind.season_dir)

    raw = load_raw(season_dir / kind.raw_name)
    print(f"Read {len(raw)} raw rows from {raw['image'].nunique()} screenshots")

    mismatches = find_overlap_mismatches(raw)
    if mismatches:
        print("\nERROR: overlapping rows disagree, fix the transcription:")
        print("\n".join(mismatches))
        return 1
    print(f"Overlap check passed: {len(raw) - raw['xrank'].nunique()} repeated rows all agree")

    merged = raw.drop(columns="image").drop_duplicates().sort_values("xrank").reset_index(drop=True)
    merged = merged[merged["xrank"] <= MAX_XRANK].reset_index(drop=True)

    problems = find_schema_problems(merged, kind.allow_no_data)
    if args.kind == "averages":
        projections_kind = KINDS["projections"]
        projections = pd.read_csv(Path(projections_kind.season_dir) / projections_kind.out_name, keep_default_na=False, na_values=[""])
        projections["status"] = projections["status"].fillna("")
        projections = projections[projections["xrank"] <= merged["xrank"].max()]  # averages stop where their screenshots do
        problems += cross_check(merged, projections)
    if problems:
        print("\nERROR: invalid data:")
        print("\n".join(problems))
        return 1

    gaps = find_gaps(merged["xrank"])
    if gaps:
        print(f"\nWARNING: XRanks missing from the screenshots: {gaps}")
    for message in find_range_warnings(merged, kind.ranges):
        print(f"WARNING: {message}")
    no_data = merged[merged[STAT_COLS].isna().all(axis=1)]
    if not no_data.empty:
        print(f"NOTE: {len(no_data)} players have no stats in this view: {', '.join(no_data['player'])}")

    output = season_dir / kind.out_name
    merged.to_csv(output, index=False)
    print(f"\nWrote {len(merged)} players to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
