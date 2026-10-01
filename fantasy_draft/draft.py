"""Snake draft order and the state of a draft in progress."""

from dataclasses import dataclass
from typing import FrozenSet, List, Tuple

TEAMS = 14
MY_SLOT = 2
ROSTER_SIZE = 13


def snake_pick(slot: int, round_number: int, teams: int = TEAMS) -> int:
    """Return the overall pick number of `slot` in `round_number` (both 1-based) of a snake draft."""
    if not 1 <= slot <= teams:
        raise ValueError(f"Draft slot {slot} is outside 1..{teams}")
    if round_number < 1:
        raise ValueError("Rounds start at 1")
    position = slot if round_number % 2 == 1 else teams - slot + 1
    return (round_number - 1) * teams + position


def my_picks(slot: int = MY_SLOT, rounds: int = 8, teams: int = TEAMS) -> List[int]:
    """Return the overall pick numbers of one slot over the first `rounds` rounds."""
    return [snake_pick(slot, round_number, teams) for round_number in range(1, rounds + 1)]


@dataclass(frozen=True)
class DraftState:
    """Who has been drafted so far; picks are assumed to be made in order with none skipped."""

    taken: FrozenSet[str] = frozenset()
    mine: Tuple[str, ...] = ()

    @property
    def picks_made(self) -> int:
        """Number of picks made by everyone so far."""
        return len(self.taken) + len(self.mine)

    @property
    def next_pick(self) -> int:
        """Overall number of the pick about to be made."""
        return self.picks_made + 1
