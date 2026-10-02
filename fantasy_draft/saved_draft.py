"""
The draft the page saves, kept in one file next to the project so it survives a closed tab, a cleared browser and a
change of port (the browser's own storage is per address, and the dashboard may start on another port).

The server stores what the page sends and never interprets it: the picks are checked by the same code that analyses
them, when the page asks for an analysis. What it does guarantee:

* one fixed file, written atomically (a temporary file in the same folder, then a rename), so a crash or a full disk
  leaves the previous draft whole;
* a size limit and a short list of known keys, so the file cannot grow without bound or collect arbitrary data;
* a version number that rises with every save. A save names the version the page last saw, and a save based on an
  older one is refused, so two open windows cannot silently overwrite each other;
* a file that cannot be read is reported and set aside, never overwritten without a trace;
* a save that would empty a draft that has picks first copies the old file to `saved_draft.previous-v<version>.json` (one per version, so a
  later copy never replaces an earlier one), so Reset or anything else that empties it can be taken back by hand.
"""

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "saved_draft.json"
DEFAULT_MOCK_PATH = Path(__file__).resolve().parent.parent / "saved_mock_draft.json"
MAX_BYTES = 200_000
MAX_PICKS = 200
KNOWN_KEYS = ("version", "picks", "history", "categories", "gamesAdjusted", "method", "rule", "rehearsal", "seed", "needs")


class SavedDraftError(ValueError):
    """The draft cannot be saved; the message is safe to show to the user."""


class Conflict(SavedDraftError):
    """The save was based on an older version than the one on disk."""

    def __init__(self, current: int) -> None:
        super().__init__("The draft was changed in another window. Reload the page to see the current draft.")
        self.current = current


def check(state: Any) -> Dict[str, Any]:
    """Return the state if it has the expected outer shape, else raise SavedDraftError."""
    if not isinstance(state, dict):
        raise SavedDraftError("The saved draft must be a JSON object")
    unknown = sorted(set(state) - set(KNOWN_KEYS))
    if unknown:
        raise SavedDraftError(f"Unknown keys in the saved draft: {unknown}")
    picks = state.get("picks", [])
    if not isinstance(picks, list) or len(picks) > MAX_PICKS:
        raise SavedDraftError(f"picks must be a list of at most {MAX_PICKS} entries")
    if len(json.dumps(state)) > MAX_BYTES:
        raise SavedDraftError("The saved draft is too large")
    return state


class SavedDraft:
    """One draft file and the lock that keeps its reads and writes in order."""

    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        """Return (version, state, problem). With no file, (0, None, None); with an unreadable one, (0, None, why)."""
        with self._lock:
            return self._read()

    def save(self, state: Any, base_version: Any) -> int:
        """Store `state` if the page's `base_version` is the one on disk; return the new version."""
        state = check(state)
        if isinstance(base_version, bool) or not isinstance(base_version, int):
            raise SavedDraftError("baseVersion must be a whole number")
        with self._lock:
            version, current, problem = self._read()
            if problem is not None:
                self._set_aside()
            if base_version != version:
                raise Conflict(version)
            if current and current.get("picks") and not state.get("picks"):
                shutil.copy2(self.path, self.path.with_name(f"{self.path.stem}.previous-v{version}.json"))
            payload = json.dumps({"version": version + 1, "state": state}, separators=(",", ":"))
            self._write(payload)
            return version + 1

    def _read(self) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return 0, None, None
        except OSError as error:
            return 0, None, f"The saved draft could not be read: {error.strerror or error}"
        try:
            if len(raw) > MAX_BYTES + 1000:
                raise ValueError("it is too large")
            data = json.loads(raw)
            version = data["version"]
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise ValueError("it has no valid version")
            return version, check(data["state"]), None
        except (ValueError, KeyError, TypeError, SavedDraftError) as error:
            return 0, None, f"The saved draft was set aside because it could not be used ({error})"

    def _set_aside(self) -> None:
        """Keep an unusable file under another name instead of overwriting it."""
        try:
            os.replace(self.path, self.path.with_suffix(".unreadable.json"))
        except OSError:
            pass

    def _write(self, payload: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".saved_draft_", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
