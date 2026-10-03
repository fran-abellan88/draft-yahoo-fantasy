"""
Save a draft-day snapshot, so the score can be checked against real results after the season.

    python tools/snapshot.py                              # page defaults: all nine categories, uncapped, games counted
    python tools/snapshot.py --categories pts,reb,ast --method capped --no-games
    python tools/snapshot.py --out somewhere.csv

One row per player in the pool: his XRank, Rank and ADP, his projected per-game stats and games, his score under the
chosen settings, each category's score, and the pick the plan from an empty draft gives him (blank when it does not
use him). Written to data/2026-27/snapshot_<date>.csv. After the season, compare the end-of-season 9-category value and
each team's category wins with the score, XRank, ADP and the tie-band rule (see the README), and tune TIE_BAND from that.
"""

import argparse
from datetime import date
from pathlib import Path
from typing import List, Optional

import pandas as pd

from fantasy_draft.data import DATA_DIR, load_players
from fantasy_draft.scoring import category_scores
from fantasy_draft.service import DraftService

DEFAULT_OUT = DATA_DIR / "2026-27"


def build_snapshot(categories: Optional[List[str]] = None, method: str = "uncapped", games_adjusted: bool = True) -> pd.DataFrame:
    """The snapshot as a table: one row per player, in XRank order."""
    players = load_players()
    service = DraftService(players)
    keys = categories or list(service.keys)
    answer = service.analyze({"categories": keys, "picks": [], "method": method, "gamesAdjusted": games_adjusted})
    score = {row["id"]: row["score"] for row in answer["pool"]}
    plan = {step["id"]: step["pick"] for step in answer["plans"][0]["steps"] if not step["filled"]} if answer["plans"] else {}
    filled = {step["id"]: step["pick"] for step in answer["plans"][0]["steps"] if step["filled"]} if answer["plans"] else {}
    parts = category_scores(players, keys, service.method_bounds[method], method)
    snapshot = players[["xrank", "rank", "adp", "adp_estimated", "player_id", "player", "team", "positions", "gp", "status"]].copy()
    for column in ("3ptm", "pts", "reb", "ast", "st", "blk", "to", "fg_pct", "ft_pct"):
        snapshot[column] = players[column]
    snapshot["score"] = snapshot["player_id"].map(score)
    for key in keys:
        snapshot[f"cat_{key}"] = parts[key]
    snapshot["plan_pick"] = snapshot["player_id"].map(plan)
    snapshot["plan_pick_filled_in"] = snapshot["player_id"].map(filled)
    snapshot.insert(0, "settings", f"{','.join(keys)} | {method} | {'games counted' if games_adjusted else 'games not counted'}")
    return snapshot.sort_values("xrank").reset_index(drop=True)


def main() -> None:
    """Write the snapshot to disk and say where."""
    parser = argparse.ArgumentParser(description="Save a draft-day snapshot of the pool, the scores and the plan")
    parser.add_argument("--categories", help="comma-separated category keys (default: all nine)")
    parser.add_argument("--method", default="uncapped", choices=["capped", "uncapped", "zscore"])
    parser.add_argument("--no-games", action="store_true", help="do not scale scores by projected games")
    parser.add_argument("--out", type=Path, help="file to write (default data/2026-27/snapshot_<today>.csv)")
    args = parser.parse_args()
    keys = args.categories.split(",") if args.categories else None
    snapshot = build_snapshot(keys, args.method, not args.no_games)
    out = args.out or DEFAULT_OUT / f"snapshot_{date.today().isoformat()}.csv"
    snapshot.to_csv(out, index=False)
    print(f"Wrote {len(snapshot)} players to {out}")


if __name__ == "__main__":
    main()
