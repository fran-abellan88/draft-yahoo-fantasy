"""
Category weights from team needs: favour the categories where one more unit changes the chance of winning most.

In head-to-head a category is won by beating the opponent, so one more unit is worth most where the category is close
and little where the team already dominates it or is far behind. The standing (league.py) gives, for each category,
the share of the other 13 teams the user's team beats; `closeness` is 1 when that share is one half and 0 at either end.

Three limits keep the weights trustworthy (they are an option, off by default, and the page shows the weights in use):

* A ramp. With one or two players "need" is only those players' profiles, so the weights start at 1 and reach their
  full effect after `RAMP_ROUNDS` complete rounds.
* A cap. After normalising to a mean of 1, no weight is further than `MAX_SHIFT` from 1, so the ranking cannot lurch.
  (Clamping afterwards can leave the mean slightly off 1; that is accepted, it is the cap that matters.)
* Punting stays explicit. Only ticked categories get a weight, so an unticked category is never brought back.
"""

from typing import Dict, Mapping, Sequence, Tuple

RAMP_ROUNDS = 4
MAX_SHIFT = 0.4


def closeness(beaten: float) -> float:
    """1 when the team beats half of the others, falling to 0 when it beats none or all of them."""
    return 4.0 * beaten * (1.0 - beaten)


def category_weights(standing: Mapping[str, Mapping[str, float]], keys: Sequence[str], rounds_done: int) -> Tuple[Dict[str, float], float]:
    """Return (weight per ticked category, ramp). With no complete round every weight is exactly 1."""
    ramp = min(1.0, max(0.0, rounds_done / RAMP_ROUNDS))
    # A category with no standing (my team has no credited player yet) is neutral
    raw = {key: 1.0 + ramp * MAX_SHIFT * 2.0 * ((closeness(standing[key]["beaten"]) if key in standing else 0.5) - 0.5) for key in keys}
    mean = sum(raw.values()) / len(raw)
    low, high = 1.0 - MAX_SHIFT, 1.0 + MAX_SHIFT
    return {key: min(high, max(low, value / mean)) for key, value in raw.items()}, ramp
