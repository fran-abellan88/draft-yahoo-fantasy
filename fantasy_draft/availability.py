"""
Will a player still be there at a given pick?

Two interchangeable rules, both answering with a probability that is compared with `threshold`:

* NormalAdpModel   the player's draft position is Normal(ADP, sd) with sd growing with ADP, so early
                   picks are predictable and late ones are not. Conditioned on the picks already made.
* AdpWindow        deterministic: available if ADP >= pick - slack. Simple to reason about and a good
                   cross-check on the probabilistic rule.

For the pick about to be made, everyone still in the pool is available by definition, unless some earlier picks
were never seen (see below).

Unseen picks. The user may fall behind and not see some picks. A player the pool still lists may then have been
taken at one of them. His chance of being there at a later pick is the product, over every pick that is unseen or
still to come, of his chance of surviving that pick given that he survived the ones before it. A pick that was seen
contributes nothing: the pool was observed, so a seen pick was somebody else. With no unseen picks this is exactly
the formula for the picks still to come, and as unseen picks are marked (a player known to be gone) they leave the
product and the odds of everyone else rise.

The parameters are starting points, not measurements. They should be calibrated against real drafts;
the mock draft was mostly auto-picks, which follow ADP far more closely than people do.
"""

import math
from dataclasses import dataclass
from typing import List, Protocol, Sequence, Tuple

import numpy as np

_erf = np.vectorize(math.erf, otypes=[float])


class AvailabilityRule(Protocol):
    """Probability that each player is still available when `pick` is made, `picks_made` picks in.

    `unseen` lists the pick numbers (all before `pick`) nobody has reported; see the module notes.
    """

    threshold: float

    def probability(self, adp: np.ndarray, pick: int, picks_made: int, unseen: Sequence[int] = ()) -> np.ndarray:
        """Return one probability per player, in the order of `adp`."""
        ...


def _runs(picks: Sequence[int]) -> List[Tuple[int, int]]:
    """Group pick numbers into runs of consecutive picks, as (first, last)."""
    runs: List[Tuple[int, int]] = []
    for number in sorted(set(picks)):
        if runs and number == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], number)
        else:
            runs.append((number, number))
    return runs


def _survival(position: float, mean: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """P(draft position > `position`) for Normal(mean, sd)."""
    return 0.5 * (1.0 - _erf((position - mean) / (sd * math.sqrt(2.0))))


@dataclass(frozen=True)
class NormalAdpModel:
    """Draft position ~ Normal(ADP, base_sd + sd_per_adp * ADP)."""

    base_sd: float = 2.0
    sd_per_adp: float = 0.2
    threshold: float = 0.5

    def probability(self, adp: np.ndarray, pick: int, picks_made: int, unseen: Sequence[int] = ()) -> np.ndarray:
        """Return P(still there at `pick`): survival of every unseen pick and every pick still to come before it."""
        unseen_before = [number for number in unseen if number < pick]
        if not unseen_before and pick <= picks_made + 1:
            return np.ones(len(adp))
        sd = self.base_sd + self.sd_per_adp * adp
        # Surviving pick k means the draft position is above k + 0.5. Given survival of the picks before a run of
        # consecutive picks a..b, the chance of surviving all of them is S(b + 0.5) / S(a - 0.5), which is why a run
        # is one factor and why, with no unseen picks, the result is the single ratio it always was.
        probability = np.ones(len(adp))
        for first, last in _runs(unseen_before + list(range(picks_made + 1, pick))):
            before = np.maximum(_survival(first - 0.5, adp, sd), 1e-12)
            probability *= np.clip(_survival(last + 0.5, adp, sd) / before, 0.0, 1.0)
        return probability


@dataclass(frozen=True)
class AdpWindow:
    """Available if the player's ADP is no earlier than `slack` picks before this one."""

    slack: float = 3.0
    threshold: float = 0.5

    def probability(self, adp: np.ndarray, pick: int, picks_made: int, unseen: Sequence[int] = ()) -> np.ndarray:
        """Return 1.0 for players expected to last until `pick`, else 0.0.

        On the clock everyone listed is available, unless some picks were unseen: then the same window applies,
        so a player whose ADP is well before this pick is treated as gone.
        """
        if pick <= picks_made + 1 and not any(number < pick for number in unseen):
            return np.ones(len(adp))
        return (adp >= pick - self.slack).astype(float)
