"""
Will a player still be there at a given pick?

Two interchangeable rules, both answering with a probability that is compared with `threshold`:

* NormalAdpModel   the player's draft position is Normal(ADP, sd) with sd growing with ADP, so early
                   picks are predictable and late ones are not. Conditioned on the picks already made.
* AdpWindow        deterministic: available if ADP >= pick - slack. Simple to reason about and a good
                   cross-check on the probabilistic rule.

For the pick about to be made, everyone still in the pool is available by definition.

The parameters are starting points, not measurements. They should be calibrated against real drafts;
the mock draft was mostly auto-picks, which follow ADP far more closely than people do.
"""

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

_erf = np.vectorize(math.erf, otypes=[float])


class AvailabilityRule(Protocol):
    """Probability that each player is still available when `pick` is made, `picks_made` picks in."""

    threshold: float

    def probability(self, adp: np.ndarray, pick: int, picks_made: int) -> np.ndarray:
        """Return one probability per player, in the order of `adp`."""
        ...


def _survival(position: float, mean: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """P(draft position > `position`) for Normal(mean, sd)."""
    return 0.5 * (1.0 - _erf((position - mean) / (sd * math.sqrt(2.0))))


@dataclass(frozen=True)
class NormalAdpModel:
    """Draft position ~ Normal(ADP, base_sd + sd_per_adp * ADP)."""

    base_sd: float = 2.0
    sd_per_adp: float = 0.2
    threshold: float = 0.5

    def probability(self, adp: np.ndarray, pick: int, picks_made: int) -> np.ndarray:
        """Return P(still there at `pick` | not drafted in the first `picks_made` picks)."""
        if pick <= picks_made + 1:
            return np.ones(len(adp))
        sd = self.base_sd + self.sd_per_adp * adp
        # "Still there at pick n" means the draft position is n or later, i.e. above n - 0.5.
        still_there = _survival(pick - 0.5, adp, sd)
        not_yet_taken = np.maximum(_survival(picks_made + 0.5, adp, sd), 1e-12)
        return np.clip(still_there / not_yet_taken, 0.0, 1.0)


@dataclass(frozen=True)
class AdpWindow:
    """Available if the player's ADP is no earlier than `slack` picks before this one."""

    slack: float = 3.0
    threshold: float = 0.5

    def probability(self, adp: np.ndarray, pick: int, picks_made: int) -> np.ndarray:
        """Return 1.0 for players expected to last until `pick`, else 0.0."""
        if pick <= picks_made + 1:
            return np.ones(len(adp))
        return (adp >= pick - self.slack).astype(float)
