"""
My own rules for the plan: who I will pick, and who I will not, at which of my picks.

Both kinds come down to one question, "may this player be my pick N?", so the planner only needs a filter on its
candidate list:

* `only`: at the picks in range, I choose among these players (Jokic or Wembanyama at pick 2);
* `avoid`: at the picks in range, never these players (no Kawhi Leonard in my first three picks).

Ranges count my own picks, not the draft: "my pick 3" is overall pick 30 in slot 2. Rules shape my plan only. The
other teams are planned as if the rules did not exist, because they do not know about them.

A rule never leaves a pick empty. If every player an `only` rule allows is gone, the rule is dropped for that pick and
the page says it could not be met.
"""

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set

KINDS = ("only", "avoid")
MAX_RULES = 30
MAX_RULE_PLAYERS = 20


@dataclass(frozen=True)
class PickRule:
    """One rule, with its range already turned into overall pick numbers."""

    rule_id: str
    kind: str
    players: FrozenSet[str]
    picks: FrozenSet[int]


def restrict(rules: Sequence[PickRule], pick: int, available: Iterable[str]) -> Optional[Set[str]]:
    """The players who may be my `pick` among `available`, or None when no rule applies there.

    Returns an empty set only when the rules leave nobody; the caller then ignores them for that pick.
    """
    allowed: Optional[Set[str]] = None
    for rule in rules:
        if pick not in rule.picks:
            continue
        pool = set(available) if allowed is None else allowed
        allowed = pool & rule.players if rule.kind == "only" else pool - rule.players
    return allowed


def parse_rules(raw: Any, known_ids: Set[str], my_numbers: Sequence[int]) -> List[PickRule]:
    """The enabled rules in a request as `PickRule`s; raises ValueError naming what is wrong.

    A rule is {id, kind, players: [ids], from: n, to: n or null, enabled}. `from` and `to` are my pick numbers
    (1 is my first pick); a missing `to` means through my last pick. Rules switched off are checked but not returned.
    """
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_RULES:
        raise ValueError(f"rules must be a list of at most {MAX_RULES} entries")
    parsed: List[PickRule] = []
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"rule {index} must be an object")
        kind = entry.get("kind")
        if kind not in KINDS:
            raise ValueError(f"rule {index}: kind must be one of {list(KINDS)}")
        players = entry.get("players")
        if not isinstance(players, list) or not players or len(players) > MAX_RULE_PLAYERS:
            raise ValueError(f"rule {index}: players must be a list of 1 to {MAX_RULE_PLAYERS} player ids")
        unknown = [player for player in players if player not in known_ids]
        if unknown:
            raise ValueError(f"rule {index}: unknown players {unknown}")
        first = _pick_number(entry.get("from"), index, "from", len(my_numbers))
        last_raw = entry.get("to")
        last = len(my_numbers) if last_raw is None else _pick_number(last_raw, index, "to", len(my_numbers))
        if last < first:
            raise ValueError(f"rule {index}: to must not be before from")
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"rule {index}: enabled must be true or false")
        if enabled:
            rule_id = str(entry.get("id", index))
            parsed.append(PickRule(rule_id, kind, frozenset(players), frozenset(my_numbers[first - 1:last])))
    return parsed


def _pick_number(value: Any, index: int, name: str, most: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= most:
        raise ValueError(f"rule {index}: {name} must be a whole number from 1 to {most}")
    return value


def rule_states(rules: Sequence[PickRule], gone: Set[str], next_pick: int, unmet: Set[int]) -> Dict[str, str]:
    """For each enabled rule: "moot" when it can no longer change anything, "unmet" when it was dropped, else "active".

    Moot: every pick in range is past, or (for `only`) every player it allows is taken, or (for `avoid`) every player it
    bans is taken. `gone` is everyone drafted so far; `unmet` the overall pick numbers where the rules left nobody.
    """
    states: Dict[str, str] = {}
    for rule in rules:
        ahead = {pick for pick in rule.picks if pick >= next_pick}
        if not ahead or rule.players <= gone:
            states[rule.rule_id] = "moot"
        elif rule.kind == "only" and ahead & unmet:
            states[rule.rule_id] = "unmet"
        else:
            states[rule.rule_id] = "active"
    return states
