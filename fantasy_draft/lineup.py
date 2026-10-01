"""
Lineup legality for the Yahoo roster: PG, SG, G, SF, PF, F, C, C, Util, Util plus 3 bench spots.

This replaces the 2025 heuristic ("2 to 5 players eligible per position"). The question that matters is
whether the players drafted so far can all be started at once, which is a bipartite matching of
players to starting slots. A player who cannot be placed sits on the bench and adds nothing to the
weekly categories, so a roster that fails this check is wasting a pick.
"""

from functools import lru_cache
from typing import FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

ALL_POSITIONS: FrozenSet[str] = frozenset({"PG", "SG", "SF", "PF", "C"})

STARTING_SLOTS: Tuple[Tuple[str, FrozenSet[str]], ...] = (
    ("PG", frozenset({"PG"})),
    ("SG", frozenset({"SG"})),
    ("G", frozenset({"PG", "SG"})),
    ("SF", frozenset({"SF"})),
    ("PF", frozenset({"PF"})),
    ("F", frozenset({"SF", "PF"})),
    ("C", frozenset({"C"})),
    ("C", frozenset({"C"})),
    ("Util", ALL_POSITIONS),
    ("Util", ALL_POSITIONS),
)
BENCH_SPOTS = 3


def _canonical(position_lists: Iterable[Sequence[str]]) -> Tuple[FrozenSet[str], ...]:
    """Order-independent form of a roster, so equal rosters share a cache entry."""
    sets = [frozenset(positions) for positions in position_lists]
    return tuple(sorted(sets, key=lambda eligible: sorted(eligible)))


@lru_cache(maxsize=None)
def _max_matching(position_sets: Tuple[FrozenSet[str], ...]) -> int:
    """Size of a maximum matching of players to starting slots (augmenting paths)."""
    slot_owner: List[Optional[int]] = [None] * len(STARTING_SLOTS)

    def try_assign(player: int, seen: Set[int]) -> bool:
        for slot_index, (_, eligible) in enumerate(STARTING_SLOTS):
            if slot_index in seen or not position_sets[player] & eligible:
                continue
            seen.add(slot_index)
            owner = slot_owner[slot_index]
            if owner is None or try_assign(owner, seen):
                slot_owner[slot_index] = player
                return True
        return False

    return sum(try_assign(player, set()) for player in range(len(position_sets)))


def max_starters(position_lists: Iterable[Sequence[str]]) -> int:
    """Return how many of these players can start at the same time."""
    return _max_matching(_canonical(position_lists))


def all_can_start(position_lists: Iterable[Sequence[str]]) -> bool:
    """Return True when every player can be placed in the starting lineup simultaneously."""
    canonical = _canonical(position_lists)
    return len(canonical) <= len(STARTING_SLOTS) and _max_matching(canonical) == len(canonical)
