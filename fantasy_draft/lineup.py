"""
Lineup legality for the Yahoo roster: PG, SG, G, SF, PF, F, C, C, Util, Util plus 3 bench spots.

This replaces the 2025 heuristic ("2 to 5 players eligible per position"). The question that matters is
whether the players drafted so far can all be started at once, which is a bipartite matching of
players to starting slots. A player who cannot be placed sits on the bench and adds nothing to the
weekly categories, so a roster that fails this check is wasting a pick.

Eligibility is held as a 5-bit mask (one bit per position) so the optimizer, which asks this question
tens of thousands of times per request, can use cheap integer tuples as cache keys.
"""

from functools import lru_cache
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

ALL_POSITIONS: FrozenSet[str] = frozenset({"PG", "SG", "SF", "PF", "C"})
POSITION_BIT: Dict[str, int] = {"PG": 1, "SG": 2, "SF": 4, "PF": 8, "C": 16}
ALL_MASK = sum(POSITION_BIT.values())

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


def position_mask(positions: Iterable[str]) -> int:
    """Bit mask of the positions a player can fill, e.g. ["PG", "SG"] -> 3."""
    mask = 0
    for position in positions:
        mask |= POSITION_BIT[position]
    return mask


_SLOT_MASKS: Tuple[int, ...] = tuple(position_mask(eligible) for _, eligible in STARTING_SLOTS)


@lru_cache(maxsize=None)
def _max_matching(masks: Tuple[int, ...]) -> int:
    """Size of a maximum matching of players to starting slots (augmenting paths)."""
    slot_owner: List[Optional[int]] = [None] * len(_SLOT_MASKS)

    def try_assign(player: int, seen: Set[int]) -> bool:
        for slot_index, slot_mask in enumerate(_SLOT_MASKS):
            if slot_index in seen or not masks[player] & slot_mask:
                continue
            seen.add(slot_index)
            owner = slot_owner[slot_index]
            if owner is None or try_assign(owner, seen):
                slot_owner[slot_index] = player
                return True
        return False

    return sum(try_assign(player, set()) for player in range(len(masks)))


def all_masks_can_start(masks: Iterable[int]) -> bool:
    """Return True when every player (given as position masks) fits in the starting lineup at once."""
    canonical = tuple(sorted(masks))  # order does not matter, so equal rosters share a cache entry
    return len(canonical) <= len(_SLOT_MASKS) and _max_matching(canonical) == len(canonical)


def assign_slots(masks: Sequence[int]) -> List[Optional[int]]:
    """Which player (an index into `masks`) starts in each of the ten starting slots, or None for an open slot.

    A maximum matching, so as many players as possible start; players left over sit on the bench.
    """
    slot_owner: List[Optional[int]] = [None] * len(_SLOT_MASKS)

    def try_assign(player: int, seen: Set[int]) -> bool:
        for slot_index, slot_mask in enumerate(_SLOT_MASKS):
            if slot_index in seen or not masks[player] & slot_mask:
                continue
            seen.add(slot_index)
            owner = slot_owner[slot_index]
            if owner is None or try_assign(owner, seen):
                slot_owner[slot_index] = player
                return True
        return False

    for player in range(len(masks)):
        try_assign(player, set())
    return slot_owner


def max_starters(position_lists: Iterable[Sequence[str]]) -> int:
    """Return how many of these players can start at the same time."""
    return _max_matching(tuple(sorted(position_mask(positions) for positions in position_lists)))


def all_can_start(position_lists: Iterable[Sequence[str]]) -> bool:
    """Return True when every player can be placed in the starting lineup simultaneously."""
    return all_masks_can_start(position_mask(positions) for positions in position_lists)
