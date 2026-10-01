"""
Check the snapshot-derived CSVs against Yahoo's player list, number by number.

    python verify_snapshots.py

Run fetch_yahoo_players.py first. Exits with 1 when any stat, team or position differs or a snapshot
player is missing from Yahoo's list. Injury tags that changed since the screenshots are listed but are
not failures.
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from fantasy_draft.verify import compare_with_yahoo

# (label, snapshot csv, Yahoo csv, tolerance per column)
# Projections are season totals read exactly; the averages on screen are rounded to one decimal.
PERCENT_TOLERANCE = 0.0006
CHECKS: List[Tuple[str, Path, Path, Dict[str, float]]] = [
    (
        "2026-27 projections (season totals)",
        Path("data/2026-27/projections.csv"),
        Path("data/2026-27/yahoo_projections.csv"),
        {"fg_pct": PERCENT_TOLERANCE, "ft_pct": PERCENT_TOLERANCE},
    ),
    (
        "2025-26 averages (per game, one decimal on screen)",
        Path("data/2025-26/averages.csv"),
        Path("data/2025-26/yahoo_averages.csv"),
        {"fg_pct": PERCENT_TOLERANCE, "ft_pct": PERCENT_TOLERANCE, **{c: 0.051 for c in ["3ptm", "pts", "reb", "ast", "st", "blk", "to"]}},
    ),
]


def main() -> int:
    """Run every check and print a summary; return the process exit code."""
    failed = False
    for label, snapshot_path, yahoo_path, tolerances in CHECKS:
        snapshot = pd.read_csv(snapshot_path, keep_default_na=False, na_values=[""])
        yahoo = pd.read_csv(yahoo_path, keep_default_na=False, na_values=[""])
        differences = compare_with_yahoo(snapshot, yahoo, tolerances)
        serious = differences[differences["kind"] != "volatile"]
        print(f"\n{label}: {len(snapshot)} players, {len(serious)} real differences, "
              f"{(differences['kind'] == 'volatile').sum()} injury-tag changes")
        if not differences.empty:
            print(differences.to_string(index=False))
        failed = failed or not serious.empty
    print("\nFAILED" if failed else "\nAll snapshot values match Yahoo's page.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
