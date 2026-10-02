"""
All 14 teams scored, not only mine.

Every team's roster follows from the pick log and the snake order, so no new input is needed. Each category is
totalled per team and the user's team is placed among the 14 two ways: its rank, and the share of the other 13 teams
it beats (the chance of winning the category against a random opponent; ties count half).

Rules that keep the comparison honest:

* Equal sizes. In a snake draft teams differ by one pick mid-round, so the comparison uses the first `n` picks of every
  team, where `n` is the number of complete rounds. The page says which `n`.
* Percentages are ratios of totals (sum of makes over sum of attempts), never an average of players' percentages.
* Turnovers are reversed: fewer is better.
* A pick that names no player in the pool (outside, unseen, gone) has no stats and is not credited to a team. The
  number of such picks inside the comparison is reported, so a total is never mistaken for a complete one. A team
  with such a pick would otherwise look weaker only because of the gap, so its counting totals are scaled up to the
  comparison size (a team with 7 credited players of 8 counts 8/7 of its total). Ratios need no scaling.
"""

from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from fantasy_draft.categories import CATEGORIES
from fantasy_draft.draft import Pick, slot_of_pick

# Percentage categories are ratios of these two per-game columns
RATIO_PARTS = {"fg_pct": ("fgm", "fga"), "ft_pct": ("ftm", "fta")}


def rosters_by_slot(picks: Sequence[Pick], teams: int) -> Dict[int, List[Optional[str]]]:
    """Each slot's picks in order; a pick that is not a player in the pool is None (not credited to a team)."""
    rosters: Dict[int, List[Optional[str]]] = {slot: [] for slot in range(1, teams + 1)}
    for number, pick in enumerate(picks, start=1):
        credited = pick.player_id if pick.kind == "player" else None
        rosters[slot_of_pick(number, teams)].append(credited)
    return rosters


def _total(frame: pd.DataFrame, key: str, size: int = 0) -> float:
    """One team's total in one category over its credited players, scaled to `size` players for counting stats."""
    if frame.empty:
        return 0.0
    if key in RATIO_PARTS:
        made, attempted = RATIO_PARTS[key]
        attempts = float(frame[attempted].sum())
        return float(frame[made].sum()) / attempts if attempts > 0 else 0.0
    total = float(frame[CATEGORIES[key].column].sum())
    return total * size / len(frame) if size > len(frame) else total


def _rank(values: Dict[int, float], slot: int, lower_is_better: bool) -> int:
    """1 is best; teams with an equal value share the better rank."""
    mine = values[slot]
    ahead = sum(1 for other, value in values.items() if other != slot and (value < mine if lower_is_better else value > mine))
    return ahead + 1


def _beaten(values: Dict[int, float], slot: int, lower_is_better: bool) -> float:
    """Share of the other teams this team beats in the category, ties counting half."""
    mine = values[slot]
    others = [value for other, value in values.items() if other != slot]
    if not others:
        return 0.0
    score = sum(1.0 if (mine < value if lower_is_better else mine > value) else 0.5 if mine == value else 0.0 for value in others)
    return score / len(others)


def league_table(
    players: pd.DataFrame,
    rosters: Dict[int, List[Optional[str]]],
    keys: Sequence[str],
    size: int,
    my_slot: int,
    names: Sequence[str],
) -> Dict[str, Any]:
    """Totals, ranks and the user's standing over the first `size` picks of every team."""
    by_id = players.set_index("player_id")
    totals: Dict[int, Dict[str, float]] = {}
    counts: Dict[int, int] = {}
    missing: Dict[int, int] = {}
    for slot, picks in rosters.items():
        window = picks[:size]
        ids = [pid for pid in window if pid is not None]
        frame = by_id.loc[ids] if ids else by_id.iloc[0:0]
        totals[slot] = {key: _total(frame, key, size) for key in keys}
        counts[slot] = len(ids)
        missing[slot] = len(window) - len(ids)

    rows = []
    for slot in sorted(rosters):
        ranks = {key: _rank({s: totals[s][key] for s in rosters}, slot, CATEGORIES[key].lower_is_better) for key in keys}
        rows.append(
            {
                "slot": slot,
                "name": names[slot - 1],
                "mine": slot == my_slot,
                "players": counts[slot],
                "notCounted": missing[slot],
                "totals": {key: round(totals[slot][key], 3) for key in keys},
                "ranks": ranks,
            }
        )
    standing = {
        key: {
            "rank": _rank({s: totals[s][key] for s in rosters}, my_slot, CATEGORIES[key].lower_is_better),
            "beaten": round(_beaten({s: totals[s][key] for s in rosters}, my_slot, CATEGORIES[key].lower_is_better), 3),
        }
        for key in keys
    }
    return {"size": size, "teams": rows, "standing": standing, "notCounted": sum(missing.values())}
