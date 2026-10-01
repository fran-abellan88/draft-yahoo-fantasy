"""
Download Yahoo's player list in the three stat views and write them as CSVs.

    python fetch_yahoo_players.py               # uses data/cache/ when pages are already there
    python fetch_yahoo_players.py --refresh     # download everything again

Outputs:
    data/2026-27/yahoo_projections.csv   projected season totals with attempts
    data/2025-26/yahoo_totals.csv        last season's totals with attempts and minutes
    data/2025-26/yahoo_averages.csv      last season's per-game averages (used as a cross-check)
"""

import argparse
from pathlib import Path
from typing import Dict

from fantasy_draft.yahoo import VIEWS, download_view, parse_view

OUTPUTS: Dict[str, Path] = {
    "projections": Path("data/2026-27/yahoo_projections.csv"),
    "totals_2025_26": Path("data/2025-26/yahoo_totals.csv"),
    "averages_2025_26": Path("data/2025-26/yahoo_averages.csv"),
}
CACHE_DIR = Path("data/cache/yahoo")


def main() -> None:
    """Download, parse and save every view."""
    parser = argparse.ArgumentParser(description="Download Yahoo's player list")
    parser.add_argument("--league", default="53548", help="Yahoo league id (default: %(default)s)")
    parser.add_argument("--pages", type=int, default=12, help="Pages of 25 players, by pre-season rank (default: %(default)s)")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached pages and download again")
    args = parser.parse_args()

    for name, view_id in VIEWS.items():
        pages = download_view(args.league, view_id, args.pages, CACHE_DIR / view_id, refresh=args.refresh)
        players = parse_view(pages)
        OUTPUTS[name].parent.mkdir(parents=True, exist_ok=True)
        players.to_csv(OUTPUTS[name], index=False)
        print(f"{name:18s} {view_id:10s} {len(players)} players -> {OUTPUTS[name]}")


if __name__ == "__main__":
    main()
