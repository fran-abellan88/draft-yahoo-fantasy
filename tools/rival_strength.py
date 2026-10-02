"""
How much of my lead is the rivals' weakness? Headless drafts to 8 rounds with my team (slot 2) against rivals of
different strength. Prints one summary line per condition: how often I finish first by team Score and my average place.

    python tools/rival_strength.py                 # 60 drafts per condition
    python tools/rival_strength.py --drafts 20

Conditions:
  adp_all        everyone, me included, takes the best ADP that fits (what slot 2 is worth by itself)
  plan_vs_adp    I follow the planner, rivals take ADP (what the page used to project)
  plan_vs_mild   rivals take the best score among their next 8 ADP players
  plan_vs_slippy rivals follow the same planner but one pick in four slips to ADP

A rival that follows the planner without slips drafts the same way every time, so it is not run in many copies.
Results from 60 drafts (48 for the slippy one): first place 12%, 88%, 33% and 25% in that order.
"""

import argparse
from multiprocessing import Pool
from typing import Dict, List, Tuple

import numpy as np

from fantasy_draft.autopick import choose, next_for_clock, startable
from fantasy_draft.data import load_players
from fantasy_draft.draft import TEAM_NAMES, Pick, slot_of_pick
from fantasy_draft.league import league_table, rosters_by_slot
from fantasy_draft.lineup import position_mask
from fantasy_draft.scoring import composite_score
from fantasy_draft.service import DraftService

ROUNDS = 8
TEAMS = 14
ME = 2
SLIP = 0.25
MILD_WINDOW = 8
CONDITIONS: Dict[str, Tuple[str, str]] = {
    "adp_all": ("adp", "adp"),
    "plan_vs_adp": ("plan", "adp"),
    "plan_vs_mild": ("plan", "mild"),
    "plan_vs_slippy": ("plan", "slippy"),
}


def _draft(condition: str, seed: int) -> int:
    """Play one draft and return my place by team Score."""
    players = load_players()
    service = DraftService(players)
    keys = service.keys
    scores = dict(zip(players["player_id"], composite_score(players, keys, service.method_bounds["uncapped"], True, "uncapped")))
    me_mode, other_mode = CONDITIONS[condition]
    rng = np.random.default_rng(seed)
    picks: List[Pick] = []
    for number in range(1, ROUNDS * TEAMS + 1):
        slot = slot_of_pick(number, TEAMS)
        mode = me_mode if slot == ME else other_mode
        if mode == "slippy":
            mode = "adp" if rng.random() < SLIP else "plan"
        taken = {pick.player_id for pick in picks}
        held = [pick.player_id for position, pick in enumerate(picks, start=1) if slot_of_pick(position, TEAMS) == slot]
        masks = [position_mask(players.set_index("player_id").loc[pid, "pos_list"]) for pid in held]
        if mode == "adp":
            chosen = choose(players, taken, masks, rng=rng)
        elif mode == "mild":
            pool = players[~players["player_id"].isin(taken)]
            adp = pool["adp_est"].to_numpy(dtype=float)
            order = np.argsort(adp + rng.normal(0.0, 2.0 + 0.2 * adp), kind="stable")
            legal = [str(pool.iloc[i]["player_id"]) for i in order if startable(masks + [position_mask(pool.iloc[i]["pos_list"])])]
            chosen = max(legal[:MILD_WINDOW], key=lambda pid: scores[pid]) if legal else None
        else:
            service_for_slot = DraftService(players, slot=slot)
            request = {"categories": keys, "picks": [pick.player_id for pick in picks], "method": "uncapped", "gamesAdjusted": True}
            answer = service_for_slot.analyze(request)
            chosen = answer["recommendation"]["id"] if answer["recommendation"] else next_for_clock(players, picks, TEAMS)
        picks.append(Pick("player", chosen))
    table = league_table(players, rosters_by_slot(picks, TEAMS), keys, ROUNDS, ME, TEAM_NAMES)
    return int(next(row["place"] for row in table["teams"] if row["mine"]))


def _run(job: Tuple[str, int]) -> int:
    return _draft(*job)


def main() -> None:
    """Run every condition and print how often my team finishes first."""
    parser = argparse.ArgumentParser(description="My place against rivals of different strength")
    parser.add_argument("--drafts", type=int, default=60, help="drafts per condition (default: %(default)s)")
    args = parser.parse_args()
    with Pool(4) as workers:
        for condition in CONDITIONS:
            places = workers.map(_run, [(condition, seed) for seed in range(1, args.drafts + 1)])
            first = sum(1 for place in places if place == 1) / len(places)
            print(f"{condition:15s} first {first:4.0%}  average place {sum(places) / len(places):.1f}  ({len(places)} drafts)")


if __name__ == "__main__":
    main()
