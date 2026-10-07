"""
What the commentators say about single players, kept with where it was said.

`data/2026-27/player_notes.csv` is a reading list, not a model input: one row per claim with the video and the time
it was said, so the page can show it on the player's card next to the numbers. It changes no score. A row may carry a
suggested number of games or score offset; the page offers it as a starting point for the user's own adjustment
(see adjustments.py), who decides whether to apply it.

Columns: player (name as in the pool), kind (injury, role, market or skill), note, source, games, offset, and an optional
exclude ("yes" when the commentators say not to draft him at all; the page offers to turn those into one "never pick" rule).
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from fantasy_draft.names import normalize_name

NOTES_PATH = Path(__file__).resolve().parent.parent / "data" / "2026-27" / "player_notes.csv"
KINDS = ("injury", "role", "market", "skill")


def load_notes(players: pd.DataFrame, path: Path = NOTES_PATH) -> List[Dict[str, Any]]:
    """The notes as page-ready dicts, in file order; raises ValueError on a name not in the pool or a bad value."""
    if not path.exists():
        return []
    frame = pd.read_csv(path, keep_default_na=False)
    by_name = {normalize_name(name): player_id for name, player_id in zip(players["player"], players["player_id"])}
    notes: List[Dict[str, Any]] = []
    for line, row in enumerate(frame.to_dict("records"), start=2):
        player_id = by_name.get(normalize_name(str(row["player"])))
        if player_id is None:
            raise ValueError(f"{path.name} line {line}: {row['player']!r} is not in the player pool")
        if row["kind"] not in KINDS:
            raise ValueError(f"{path.name} line {line}: kind must be one of {list(KINDS)}")
        note: Dict[str, Any] = {"player": player_id, "kind": row["kind"], "note": str(row["note"]), "source": str(row["source"])}
        for key in ("games", "offset"):
            if str(row[key]).strip() != "":
                note[key] = float(row[key])
        if str(row.get("exclude", "")).strip().lower() == "yes":
            note["exclude"] = True
        notes.append(note)
    return notes
