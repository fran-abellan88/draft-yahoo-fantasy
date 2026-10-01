"""Snake draft order and the state of a draft in progress."""

from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Tuple

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


# What one entry of the pick log can be. Extended as each kind is built.
#   player   a player in the pool, picked by whoever's turn it was
#   outside  a pick I saw but whose player is not in the pool: every pool player is known to have survived it
#   unseen   a pick I did not see: any player the pool still lists may have been taken at it. Never one of my own
#   gone     an unseen pick resolved to a player known to be taken, without knowing which pick or team: he leaves the
#            pool and the number of unseen picks falls by one. Never one of my own picks
PICK_KINDS: Tuple[str, ...] = ("player", "outside", "unseen", "gone")


@dataclass(frozen=True)
class Pick:
    """One entry of the pick log. The log is in the order the picks happened; who made a pick follows from its position."""

    kind: str = "player"
    player_id: Optional[str] = None


@dataclass(frozen=True)
class DraftState:
    """Who has been drafted so far; picks are assumed to be made in order with none skipped."""

    taken: FrozenSet[str] = frozenset()
    mine: Tuple[str, ...] = ()
    mine_outside: int = 0  # my picks of players outside the pool: they fill a slot but have no stats
    other_outside: int = 0  # other teams' picks of players outside the pool
    unseen: Tuple[int, ...] = ()  # pick numbers nobody reported; the pool may be missing players taken at them

    @property
    def picks_made(self) -> int:
        """Number of picks made by everyone so far."""
        return len(self.taken) + len(self.mine) + self.mine_outside + self.other_outside + len(self.unseen)

    @property
    def next_pick(self) -> int:
        """Overall number of the pick about to be made."""
        return self.picks_made + 1
