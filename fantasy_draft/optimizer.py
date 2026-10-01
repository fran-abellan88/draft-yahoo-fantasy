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

Work is bounded. Branch and bound is exact but its worst case is huge: when the availability rule lets almost
everyone through, every pick shares the same candidates and the same team is reached in thousands of orders.
`plan_picks` therefore counts search nodes and stops at a budget, and says so (`truncated`). A stopped search is
depth first and tries the highest-scoring candidate first, so what it returns is the best plan found, which tends
to start with the highest-scoring player available, not a proven best.

The plan is a guide for the pick in front of you. Once real picks come in, call `recommend` again with
the updated state: availability for players already gone becomes exact.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from fantasy_draft.availability import AvailabilityRule
from fantasy_draft.draft import MY_SLOT, ROSTER_SIZE, DraftState, my_picks
from fantasy_draft.lineup import ALL_MASK, all_masks_can_start, position_mask
from fantasy_draft.scoring import Bounds, category_scores, composite_score, replacement_score

# When nobody clears the availability threshold for a pick, fall back to the likeliest few.
FALLBACK_CANDIDATES = 5

# Search nodes per request. With the default rule a whole simulated draft needs at most about 25,000 for the main
# search, so these leave a wide margin (tests/test_optimizer.py checks it) and only bind on pathological settings.
NODE_BUDGET = 150_000
OPTION_NODE_BUDGET = 30_000  # for each search that fixes one first pick
FIRST_PICK_OPTIONS = 6


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
    mask: int  # positions he can fill, as a bit mask (see lineup.py)


@dataclass(frozen=True)
class FirstPickOption:
    """The best plan that starts with one particular player."""

    player_id: str
    plan: Plan


@dataclass(frozen=True)
class Recommendation:
    """Plans for the rest of the draft, how the other first picks compare, and whether the search was cut short."""

    plans: List[Plan]
    options: List[FirstPickOption]  # the other first picks, best first; never the recommended player
    truncated: bool
    nodes: int  # all searches together
    assumed_gone: Optional[str] = None  # the recommended player, when the options plan as if he will be taken first
    main_nodes: int = 0  # the search for the plans alone, to compare with NODE_BUDGET
    max_option_nodes: int = 0  # the busiest single first-pick search, to compare with OPTION_NODE_BUDGET


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
    games_adjusted: bool = False,
    method: str = "capped",
    node_budget: Optional[int] = None,
) -> List[Plan]:
    """Return the best `top_k` distinct plans, best first. Empty when no picks of mine remain.

    Exact unless a `node_budget` is given; see `plan_picks` for the version the dashboard uses.
    """
    return plan_picks(
        players, state, keys, bounds, rule, slot, rounds, top_k, max_candidates, games_adjusted, method, node_budget, option_count=0
    ).plans


def plan_picks(
    players: pd.DataFrame,
    state: DraftState,
    keys: Sequence[str],
    bounds: Bounds,
    rule: AvailabilityRule,
    slot: int = MY_SLOT,
    rounds: int = 8,
    top_k: int = 10,
    max_candidates: int = 25,
    games_adjusted: bool = False,
    method: str = "capped",
    node_budget: Optional[int] = NODE_BUDGET,
    option_count: int = FIRST_PICK_OPTIONS,
) -> Recommendation:
    """Plan the remaining picks within a work budget, and price the best alternatives for the next pick.

    The alternatives are searched directly, one search per first pick with that player fixed, so `top_k` only has
    to cover the plans shown and does not decide which alternatives can appear.

    There are two questions, and the options answer the one that applies. While I am waiting for my pick, the
    recommended player may be taken before it, so the options plan without him at any of my picks (`assumed_gone`):
    what losing him really costs. On the clock he is on the board, so the options leave him in: what choosing
    someone else costs. Without this, "if he is gone" would be priced on plans that take him one pick later.
    """
    _check_state(players, state, slot, rounds)
    remaining_picks = [pick for pick in my_picks(slot, rounds) if pick >= state.next_pick]
    if not remaining_picks:
        return Recommendation([], [], False, 0)

    scores = pd.Series(composite_score(players, keys, bounds, games_adjusted, method).to_numpy(), index=players["player_id"])
    positions = {player_id: tuple(pos) for player_id, pos in zip(players["player_id"], players["pos_list"])}
    unavailable = set(state.taken) | set(state.mine)
    pool = players[~players["player_id"].isin(unavailable)]

    candidates = [
        _candidates_for_pick(pool, scores, positions, rule, pick, state.picks_made, state.unseen, max_candidates)
        for pick in remaining_picks
    ]
    # A pick of a player outside the pool still fills a starting slot: any position, replacement-level value
    mine_masks = [position_mask(positions[player_id]) for player_id in state.mine] + [ALL_MASK] * state.mine_outside
    outside_value = replacement_score(players, keys, bounds, method) if state.mine_outside else 0.0
    base_score = float(sum(scores[player_id] for player_id in state.mine)) + outside_value * state.mine_outside
    plans, truncated, nodes = _search(candidates, remaining_picks, mine_masks, base_score, top_k, node_budget)
    main_nodes, max_option_nodes = nodes, 0

    options: List[FirstPickOption] = []
    assumed_gone: Optional[str] = None
    if option_count and plans:
        recommended = plans[0].player_ids[0]
        waiting = remaining_picks[0] > state.next_pick
        assumed_gone = recommended if waiting else None
        later = candidates[1:]
        if assumed_gone is not None:
            later = [[c for c in candidate_list if c.player_id != assumed_gone] for candidate_list in later]
        wanted = [c for c in candidates[0] if c.player_id != recommended][:option_count]
        for first in wanted:
            budget = None if node_budget is None else min(node_budget, OPTION_NODE_BUDGET)
            found, cut, used = _search([[first]] + later, remaining_picks, mine_masks, base_score, 1, budget)
            truncated, nodes = truncated or cut, nodes + used
            max_option_nodes = max(max_option_nodes, used)
            if found:
                options.append(FirstPickOption(first.player_id, found[0]))
        options.sort(key=lambda option: (option.plan.total_score, option.plan.survival), reverse=True)
    return Recommendation(plans, options, truncated, nodes, assumed_gone, main_nodes, max_option_nodes)


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
    # Count across the whole roster, not just the planning horizon: later picks may already be made
    expected_mine = sum(1 for pick in my_picks(slot, ROSTER_SIZE) if pick < state.next_pick)
    mine_count = len(state.mine) + state.mine_outside
    if mine_count != expected_mine:
        raise ValueError(
            f"{state.picks_made} picks are done, so slot {slot} should own {expected_mine} of them, "
            f"but {mine_count} are marked as mine"
        )


def _candidates_for_pick(
    pool: pd.DataFrame,
    scores: pd.Series,
    positions: Dict[str, Tuple[str, ...]],
    rule: AvailabilityRule,
    pick: int,
    picks_made: int,
    unseen: Sequence[int],
    max_candidates: int,
) -> List[_Candidate]:
    """The best players who will likely still be there at `pick`, highest score first."""
    probabilities = rule.probability(pool["adp_est"].to_numpy(dtype=float), pick, picks_made, unseen)
    chosen = np.flatnonzero(probabilities >= rule.threshold)
    if len(chosen) == 0:
        chosen = np.argsort(-probabilities, kind="stable")[:FALLBACK_CANDIDATES]
    ids = pool["player_id"].to_numpy()[chosen]
    candidates = [
        _Candidate(pid, float(scores[pid]), float(probabilities[i]), position_mask(positions[pid])) for pid, i in zip(ids, chosen)
    ]
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return candidates[:max_candidates]


def _search(
    candidates: List[List[_Candidate]],
    picks: List[int],
    mine_masks: List[int],
    base_score: float,
    top_k: int,
    node_budget: Optional[int] = None,
) -> Tuple[List[Plan], bool, int]:
    """Branch and bound for the `top_k` best distinct teams.

    Returns the plans, whether the `node_budget` ran out before the search finished, and the nodes visited.
    """
    n_picks = len(candidates)
    if any(not candidate_list for candidate_list in candidates):
        return [], False, 0  # a pick nobody can fill leaves no plan (possible once a player is assumed gone)
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

    nodes = [0]
    out_of_budget = [False]

    def recurse(k: int, total: float, survival: float) -> None:
        nodes[0] += 1
        if node_budget is not None and nodes[0] > node_budget:
            out_of_budget[0] = True
            return
        if k == n_picks:
            record(total, survival)
            return
        for candidate in candidates[k]:
            if cannot_improve(total + candidate.score + suffix_best[k + 1]):
                break  # candidates are sorted by score, so none of the rest can do better
            if candidate.player_id in chosen_ids:
                continue
            if not all_masks_can_start(mine_masks + [c.mask for c in chosen] + [candidate.mask]):
                continue
            chosen.append(candidate)
            chosen_ids.add(candidate.player_id)
            recurse(k + 1, total + candidate.score, survival * candidate.probability)
            chosen_ids.discard(candidate.player_id)
            chosen.pop()
            if out_of_budget[0]:
                return

    recurse(0, base_score, 1.0)
    plans = sorted(found.values(), key=lambda plan: (plan.total_score, plan.survival), reverse=True)
    return plans, out_of_budget[0], nodes[0]
