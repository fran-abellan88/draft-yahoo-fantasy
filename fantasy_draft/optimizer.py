"""
Plan the rest of the draft: which player to take at each of my remaining picks.

A plan assigns one player to each of my remaining picks. It is valid when

* every player is still likely to be there at his pick (the availability rule),
* nobody appears twice, and
* everyone drafted so far, mine included, can start at once (see lineup.py).

Its value is the sum of the players' composite scores. That is additive on purpose: the point of
planning is the order of the picks, not interactions between players. Taking A at pick 27 and B at
pick 30 beats the reverse when A will not last and B will.

The search is exact (branch and bound over candidate lists sorted by score) and returns the best
`top_k` distinct teams. Tests compare it with brute force on small pools.

The plan is a guide for the pick in front of you. Once real picks come in, call `recommend` again with
the updated state: availability for players already gone becomes exact.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from fantasy_draft.availability import AvailabilityRule
from fantasy_draft.draft import MY_SLOT, DraftState, my_picks
from fantasy_draft.lineup import all_can_start
from fantasy_draft.scoring import Bounds, category_scores, composite_score

# When nobody clears the availability threshold for a pick, fall back to the likeliest few.
FALLBACK_CANDIDATES = 5


@dataclass(frozen=True)
class Plan:
    """One way to spend my remaining picks."""

    pick_numbers: Tuple[int, ...]
    player_ids: Tuple[str, ...]
    total_score: float  # sum of composite scores over the whole roster, players already drafted included
    survival: float  # product of each pick's availability probability, a rough chance the plan holds


@dataclass(frozen=True)
class _Candidate:
    player_id: str
    score: float
    probability: float
    positions: Tuple[str, ...]


def recommend(
    players: pd.DataFrame,
    state: DraftState,
    keys: Sequence[str],
    bounds: Bounds,
    rule: AvailabilityRule,
    slot: int = MY_SLOT,
    rounds: int = 8,
    top_k: int = 50,
    max_candidates: int = 25,
) -> List[Plan]:
    """Return the best `top_k` distinct plans, best first. Empty when no picks of mine remain."""
    _check_state(players, state, slot, rounds)
    remaining_picks = [pick for pick in my_picks(slot, rounds) if pick >= state.next_pick]
    if not remaining_picks:
        return []

    scores = pd.Series(composite_score(players, keys, bounds).to_numpy(), index=players["player_id"])
    positions = {player_id: tuple(pos) for player_id, pos in zip(players["player_id"], players["pos_list"])}
    unavailable = set(state.taken) | set(state.mine)
    pool = players[~players["player_id"].isin(unavailable)]

    candidates = [
        _candidates_for_pick(pool, scores, positions, rule, pick, state.picks_made, max_candidates) for pick in remaining_picks
    ]
    mine_positions = [positions[player_id] for player_id in state.mine]
    base_score = float(sum(scores[player_id] for player_id in state.mine))
    return _search(candidates, remaining_picks, mine_positions, base_score, top_k)


def pick_frequency(plans: Sequence[Plan], pick_index: int = 0) -> pd.DataFrame:
    """Count how often each player is the choice for one of my remaining picks across the plans."""
    counts = Counter(plan.player_ids[pick_index] for plan in plans)
    frame = pd.DataFrame(counts.most_common(), columns=["player_id", "plans"])
    frame["share"] = frame["plans"] / len(plans)
    return frame


def team_profile(players: pd.DataFrame, player_ids: Sequence[str], keys: Sequence[str], bounds: Bounds) -> pd.DataFrame:
    """Per-category team totals (per game) and the team's mean category score on a 0-100 scale."""
    team = players[players["player_id"].isin(player_ids)]
    scores = category_scores(team, keys, bounds)
    return pd.DataFrame({"total_per_game": team[list(keys)].sum(), "mean_score": scores.mean() * 100.0})


def _check_state(players: pd.DataFrame, state: DraftState, slot: int, rounds: int) -> None:
    """Reject states that cannot have come from this draft."""
    known = set(players["player_id"])
    unknown = (set(state.taken) | set(state.mine)) - known
    if unknown:
        raise ValueError(f"Unknown players in the draft state: {sorted(unknown)}")
    if set(state.taken) & set(state.mine):
        raise ValueError("A player cannot be both mine and taken by someone else")
    expected_mine = sum(1 for pick in my_picks(slot, rounds) if pick < state.next_pick)
    if len(state.mine) != expected_mine:
        raise ValueError(
            f"{state.picks_made} picks are done, so slot {slot} should own {expected_mine} of them, "
            f"but {len(state.mine)} are marked as mine"
        )


def _candidates_for_pick(
    pool: pd.DataFrame,
    scores: pd.Series,
    positions: Dict[str, Tuple[str, ...]],
    rule: AvailabilityRule,
    pick: int,
    picks_made: int,
    max_candidates: int,
) -> List[_Candidate]:
    """The best players who will likely still be there at `pick`, highest score first."""
    probabilities = rule.probability(pool["adp_est"].to_numpy(dtype=float), pick, picks_made)
    chosen = np.flatnonzero(probabilities >= rule.threshold)
    if len(chosen) == 0:
        chosen = np.argsort(-probabilities, kind="stable")[:FALLBACK_CANDIDATES]
    ids = pool["player_id"].to_numpy()[chosen]
    candidates = [_Candidate(pid, float(scores[pid]), float(probabilities[i]), positions[pid]) for pid, i in zip(ids, chosen)]
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return candidates[:max_candidates]


def _search(
    candidates: List[List[_Candidate]],
    picks: List[int],
    mine_positions: List[Tuple[str, ...]],
    base_score: float,
    top_k: int,
) -> List[Plan]:
    """Branch and bound for the `top_k` best distinct teams."""
    n_picks = len(candidates)
    suffix_best = [0.0] * (n_picks + 1)
    for k in range(n_picks - 1, -1, -1):
        suffix_best[k] = suffix_best[k + 1] + candidates[k][0].score

    found: Dict[FrozenSet[str], Plan] = {}
    floor = [-np.inf]  # score a new plan must beat once `top_k` plans are known
    chosen: List[_Candidate] = []
    chosen_ids: Set[str] = set()

    def record(total: float, survival: float) -> None:
        team = frozenset(chosen_ids)
        plan = Plan(tuple(picks), tuple(c.player_id for c in chosen), total, survival)
        existing = found.get(team)
        if existing is not None and existing.survival >= survival:
            return
        found[team] = plan
        if len(found) > top_k:
            del found[min(found, key=lambda key: found[key].total_score)]
        if len(found) >= top_k:
            floor[0] = min(p.total_score for p in found.values())

    def cannot_improve(optimistic_total: float) -> bool:
        return len(found) >= top_k and optimistic_total <= floor[0]

    def recurse(k: int, total: float, survival: float) -> None:
        if k == n_picks:
            record(total, survival)
            return
        for candidate in candidates[k]:
            if cannot_improve(total + candidate.score + suffix_best[k + 1]):
                break  # candidates are sorted by score, so none of the rest can do better
            if candidate.player_id in chosen_ids:
                continue
            roster = mine_positions + [c.positions for c in chosen] + [candidate.positions]
            if not all_can_start(roster):
                continue
            chosen.append(candidate)
            chosen_ids.add(candidate.player_id)
            recurse(k + 1, total + candidate.score, survival * candidate.probability)
            chosen_ids.discard(candidate.player_id)
            chosen.pop()

    recurse(0, base_score, 1.0)
    return sorted(found.values(), key=lambda plan: (plan.total_score, plan.survival), reverse=True)
