"""
My own beliefs about single players, applied on top of the projection.

The projection is Yahoo's: it knows last season's stats and the games a player is expected to play, not that a player
is out for the start of the season, will not start, or has a new set of teammates. Two judgements can carry that:

* expected games: replaces the projected games in the games adjustment (it matters while "Count games missed" is on);
* score offset: points added to the final score, for what no stat shows (a smaller role, more usage).

Both are mine, not the other teams': the other teams are planned as if the adjustments did not exist. Each adjustment
may carry a note and where the idea came from, which the page shows and the server never interprets.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set

import pandas as pd

MAX_ADJUSTMENTS = 150
GAMES_LIMITS = (0.0, 82.0)
OFFSET_LIMITS = (-30.0, 30.0)
MAX_TEXT = 300


@dataclass(frozen=True)
class Adjustment:
    """One enabled adjustment: the games to expect (None keeps the projection) and the points to add."""

    player_id: str
    games: Optional[float]
    offset: float


def parse_adjustments(raw: Any, known_ids: Set[str]) -> List[Adjustment]:
    """The enabled adjustments in a request; raises ValueError naming what is wrong.

    An entry is {id, player, games: number or null, offset: number, note, source, enabled}. Entries switched off are
    checked but not returned. Two enabled entries for one player are refused: which would win?
    """
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_ADJUSTMENTS:
        raise ValueError(f"adjustments must be a list of at most {MAX_ADJUSTMENTS} entries")
    found: Dict[str, Adjustment] = {}
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"adjustment {index} must be an object")
        player = entry.get("player")
        if player not in known_ids:
            raise ValueError(f"adjustment {index}: unknown player {player!r}")
        games = _number(entry.get("games"), index, "games", GAMES_LIMITS, allow_none=True)
        offset = _number(entry.get("offset", 0), index, "offset", OFFSET_LIMITS, allow_none=False)
        for key in ("note", "source"):
            text = entry.get(key, "")
            if not isinstance(text, str) or len(text) > MAX_TEXT:
                raise ValueError(f"adjustment {index}: {key} must be text of at most {MAX_TEXT} characters")
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"adjustment {index}: enabled must be true or false")
        if games is None and offset == 0:
            raise ValueError(f"adjustment {index}: give expected games, a score offset, or both")
        if not enabled:
            continue
        if player in found:
            raise ValueError(f"adjustment {index}: {player} already has an enabled adjustment")
        found[player] = Adjustment(str(player), games, float(offset))
    return list(found.values())


def _number(value: Any, index: int, name: str, limits: Sequence[float], allow_none: bool) -> Optional[float]:
    if value is None and allow_none:
        return None
    low, high = limits
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or not low <= value <= high:
        raise ValueError(f"adjustment {index}: {name} must be a number from {low:g} to {high:g}")
    return float(value)


def apply_adjustments(players: pd.DataFrame, adjustments: Sequence[Adjustment]) -> pd.DataFrame:
    """A copy of the player table with the expected games in `gp` and the offsets in a `score_offset` column."""
    adjusted = players.copy()
    adjusted["score_offset"] = 0.0
    for adjustment in adjustments:
        row = adjusted["player_id"] == adjustment.player_id
        if adjustment.games is not None:
            adjusted.loc[row, "gp"] = adjustment.games
        adjusted.loc[row, "score_offset"] = adjustment.offset
    return adjusted
