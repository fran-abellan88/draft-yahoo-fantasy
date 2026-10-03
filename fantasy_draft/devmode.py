"""
Development mode (`python run_dashboard.py --dev`): the page and the server follow the source files.

* The page reloads itself when a file under web/ changes, or when the server has restarted.
* The server restarts itself (in place, same process and port) when a Python file changes.

It is off by default. During a real draft nothing should reload or restart on its own, so a normal run watches
nothing and its page carries no extra script. Only fantasy_draft/*.py, run_dashboard.py and web/ are watched, never
the saved draft files, so saving a pick cannot trigger a restart. The data files are read once at startup: change
them, then restart by hand.
"""

import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

PACKAGE_DIR = Path(__file__).resolve().parent
WEB_DIR = PACKAGE_DIR / "web"
ROOT_DIR = PACKAGE_DIR.parent
POLL_SECONDS = 0.5
PORT_ENV = "DRAFT_DEV_PORT"  # the port in use, kept across a restart so the open page keeps working
RESTARTED_ENV = "DRAFT_DEV_RESTARTED"  # set after a restart so the browser is not opened again


def python_sources() -> List[Path]:
    """The Python files whose change restarts the server."""
    return sorted(PACKAGE_DIR.glob("*.py")) + [ROOT_DIR / "run_dashboard.py"]


def web_sources() -> List[Path]:
    """The files the page is made of."""
    return sorted(path for path in WEB_DIR.iterdir() if path.is_file())


def snapshot(paths: List[Path]) -> Dict[Path, int]:
    """Modification time of every file, in nanoseconds; a file that vanished mid-edit is left out."""
    found: Dict[Path, int] = {}
    for path in paths:
        try:
            found[path] = path.stat().st_mtime_ns
        except OSError:
            continue
    return found


def broken_source(paths: List[Path]) -> Optional[str]:
    """The first syntax error among `paths`, or None. A restart into one would leave no server running."""
    for path in paths:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as error:
            return f"{path.name}, line {error.lineno}: {error.msg}"
        except (OSError, ValueError) as error:  # unreadable or half-written right now
            return f"{path.name}: {error}"
    return None


class DevMode:
    """What the server needs in dev mode: a stamp for the page to compare, and the file watcher."""

    def __init__(self) -> None:
        self.started = f"{os.getpid()}-{time.time_ns()}"  # new after every restart, so the page reloads once the server is back

    def stamp(self) -> str:
        """Changes when a web file changes or the server restarts."""
        files = snapshot(web_sources())
        return f"{self.started}:{max(files.values(), default=0)}:{len(files)}"

    def watch(self, port: int, restart: Callable[[], None] = lambda: None) -> threading.Thread:
        """Start a background thread that restarts the server when a Python source changes."""
        thread = threading.Thread(target=self._watch, args=(port, restart), daemon=True, name="dev-watcher")
        thread.start()
        return thread

    def _watch(self, port: int, restart: Callable[[], None]) -> None:
        known = snapshot(python_sources())
        warned: Optional[Dict[Path, int]] = None  # the broken state already reported, so it is said once
        while True:
            time.sleep(POLL_SECONDS)
            current = snapshot(python_sources())
            if current == known:
                continue
            problem = broken_source(list(current))
            if problem:
                if warned != current:
                    print(f"A source file has an error, so the server was not restarted yet:\n{problem}")
                    warned = current
                continue
            print("A source file changed: restarting the server.")
            os.environ[PORT_ENV] = str(port)
            os.environ[RESTARTED_ENV] = "1"
            restart()
            return


def restart_in_place() -> None:
    """Replace this process by a fresh run of the same command. Never returns."""
    os.execv(sys.executable, [sys.executable] + sys.argv)
