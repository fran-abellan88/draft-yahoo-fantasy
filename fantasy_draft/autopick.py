"""
Automatic picks for the other teams: an ADP draft with lineup limits.

Used three ways, all from the same chooser:

* Rehearsal. The page asks for the pick on the clock and logs it, so a whole practice draft takes minutes.
* Projection. The picks other teams have not made yet are filled to the end of the planning horizon, so all 14 teams
  can be compared as complete teams (league.py). Logged picks are never touched, and the players the user's plan
  counts on are protected from the projected teams, because the plan already assumes they are available.
* (Catch-up was decided differently: missed picks become unseen picks, not assumed names.)

A team picks the best-ADP player left who keeps its roster startable: every player it holds, up to the ten starting
slots, must fit the lineup at once, so no automatic team ends with five centres. With `noise` the ADP is blurred by the
same spread the availability model uses, from a seeded generator, so rehearsals differ but each one can be repeated.
"""

from typing import Dict, List, Optional, Sequence, Set

import numpy as np
import pandas as pd

from fantasy_draft.draft import Pick, slot_of_pick
from fantasy_draft.lineup import STARTING_SLOTS, _max_matching, position_mask

STARTERS = len(STARTING_SLOTS)


def startable(masks: Sequence[int]) -> bool:
    """True when the first ten players (or all, if fewer) can all be in the starting lineup at once."""
    canonical = tuple(sorted(masks))
    return _max_matching(canonical) >= min(len(canonical), STARTERS)


def choose(
    players: pd.DataFrame,
    taken: Set[str],
    roster_masks: Sequence[int],
    base_sd: float = 2.0,
    sd_per_adp: float = 0.2,
    rng: Optional[np.random.Generator] = None,
) -> Optional[str]:
    """The player this team takes next, or None when nobody left fits."""
    pool = players[~players["player_id"].isin(taken)]
    if pool.empty:
        return None
    adp = pool["adp_est"].to_numpy(dtype=float)
    key = adp if rng is None else adp + rng.normal(0.0, base_sd + sd_per_adp * adp)
    for index in np.argsort(key, kind="stable"):
        row = pool.iloc[index]
        if startable(list(roster_masks) + [position_mask(row["pos_list"])]):
            return str(row["player_id"])
    return None


def _masks(players: pd.DataFrame, ids: Sequence[str]) -> List[int]:
    by_id = players.set_index("player_id")["pos_list"]
    return [position_mask(by_id[pid]) for pid in ids]


def next_for_clock(
    players: pd.DataFrame, picks: Sequence[Pick], teams: int, seed: Optional[int] = None, noise: bool = False
) -> Optional[str]:
    """The pick the team on the clock would make, given the log so far."""
    taken = {pick.player_id for pick in picks if pick.player_id is not None}
    slot = slot_of_pick(len(picks) + 1, teams)
    held = [pick.player_id for number, pick in enumerate(picks, start=1) if slot_of_pick(number, teams) == slot and pick.kind == "player"]
    rng = np.random.default_rng(seed) if noise else None
    return choose(players, taken, _masks(players, [pid for pid in held if pid]), rng=rng)


def project(
    players: pd.DataFrame,
    picks: Sequence[Pick],
    teams: int,
    until_pick: int,
    my_slot: int,
    protect: Set[str],
    seed: Optional[int] = None,
    noise: bool = False,
) -> Dict[int, List[str]]:
    """Fill the other teams' picks after the log, up to `until_pick`; return each slot's added players in order.

    The user's own picks are skipped (they come from the plan), and `protect` (the plan's players) is kept out of
    reach of the other teams.
    """
    taken: Set[str] = {pick.player_id for pick in picks if pick.player_id is not None} | set(protect)
    held: Dict[int, List[str]] = {slot: [] for slot in range(1, teams + 1)}
    for number, pick in enumerate(picks, start=1):
        if pick.kind == "player" and pick.player_id is not None:
            held[slot_of_pick(number, teams)].append(pick.player_id)
    masks: Dict[int, List[int]] = {slot: _masks(players, ids) for slot, ids in held.items()}
    added: Dict[int, List[str]] = {slot: [] for slot in range(1, teams + 1)}
    rng = np.random.default_rng(seed) if noise else None
    for number in range(len(picks) + 1, until_pick + 1):
        slot = slot_of_pick(number, teams)
        if slot == my_slot:
            continue
        chosen = choose(players, taken, masks[slot], rng=rng)
        if chosen is None:
            continue
        taken.add(chosen)
        added[slot].append(chosen)
        masks[slot] += _masks(players, [chosen])
    return added
