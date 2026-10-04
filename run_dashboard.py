"""
Start the draft dashboard on this computer and open it in the browser.

    python run_dashboard.py              # http://127.0.0.1:8001, or the next free port
    python run_dashboard.py --port 9000
    python run_dashboard.py --no-browser
    python run_dashboard.py --draft-file /tmp/trial.json   # a separate saved draft, for trying things out
    python run_dashboard.py --mock-file /tmp/mock.json     # keep the mock draft somewhere else
    python run_dashboard.py --dev                          # while changing the app: reload the page and restart on edits

The page serves two drafts: the real one at / (you log every pick) and a mock draft at /mock (the other teams pick
automatically), each with its own saved file. The top bar switches between them.

The server only listens on 127.0.0.1, so nobody else on the network can reach it.
"""

import argparse
import os
import sys
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple

from fantasy_draft.data import load_players
from fantasy_draft.devmode import PORT_ENV, RESTARTED_ENV, DevMode, restart_in_place
from fantasy_draft.saved_draft import DEFAULT_MOCK_PATH, DEFAULT_PATH, SavedDraft
from fantasy_draft.server import HOST, make_server
from fantasy_draft.service import DraftService

PORT_ATTEMPTS = 20


def bind(
    service: DraftService,
    first_port: int,
    saved: SavedDraft,
    mock: Tuple[DraftService, SavedDraft],
    dev: Optional[DevMode] = None,
    host: str = HOST,
    allow_names: Tuple[str, ...] = (),
) -> ThreadingHTTPServer:
    """Bind to the first free port at or after `first_port`."""
    for port in range(first_port, first_port + PORT_ATTEMPTS):
        try:
            return make_server(service, port, saved, mock, dev, host, allow_names)
        except OSError:
            print(f"Port {port} is busy, trying the next one")
    raise SystemExit(f"No free port between {first_port} and {first_port + PORT_ATTEMPTS - 1}")


def main() -> None:
    """Load the data, start the server and wait until Ctrl+C."""
    parser = argparse.ArgumentParser(description="Draft assistant dashboard")
    parser.add_argument("--port", type=int, default=8001, help="first port to try (default: %(default)s)")
    parser.add_argument(
        "--host",
        default=HOST,
        help="the address to listen on (default: %(default)s, this computer only). 0.0.0.0 listens on every network of the computer",
    )
    parser.add_argument(
        "--allow-name",
        action="append",
        default=[],
        metavar="NAME",
        help="a name or address other devices will use to reach the dashboard, e.g. 192.168.1.131; repeat for several. "
        "There is no login: use this only on a network you trust",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument(
        "--draft-file",
        type=Path,
        default=DEFAULT_PATH,
        help="where the draft is saved (default: %(default)s). Instances sharing a file share one draft: use another file for trials",
    )
    parser.add_argument(
        "--mock-file",
        type=Path,
        default=DEFAULT_MOCK_PATH,
        help="where the mock draft is saved (default: %(default)s). It must not be the real draft file",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="development mode: the page reloads when a file changes and the server restarts when a Python file changes. "
        "Leave it off during a real draft",
    )
    args = parser.parse_args()
    if os.environ.get(PORT_ENV):  # a development restart: keep the port the open page is using
        args.port = int(os.environ[PORT_ENV])
    if args.mock_file.resolve() == args.draft_file.resolve():
        sys.exit("The mock draft needs its own file, so it cannot mix with the real draft. Use another --mock-file or --draft-file.")

    try:
        players = load_players()
        service = DraftService(players)
        mock_service = DraftService(players, rehearsal=True)
    except FileNotFoundError as error:
        sys.exit(f"Missing data file: {error.filename}. Run fetch_yahoo_players.py first.")
    saved = SavedDraft(args.draft_file)
    mock_saved = SavedDraft(args.mock_file)
    dev = DevMode() if args.dev else None
    server = bind(service, args.port, saved, (mock_service, mock_saved), dev, args.host, tuple(args.allow_name))
    shown_host = HOST if args.host in (HOST, "0.0.0.0") else args.host  # the page on this computer is always at 127.0.0.1
    url = f"http://{shown_host}:{server.server_address[1]}/"
    if args.host != HOST:
        reachable = ", ".join(args.allow_name) or "localhost only (no --allow-name given)"
        print(f"Listening on {args.host}, reachable as: {reachable}. There is no login.")
    print(f"Draft assistant running at {url}  (Ctrl+C to stop)")
    print(f"Real draft:  {url}  you log every pick. Saved in {saved.path}")
    print(f"Mock draft:  {url}mock  the other teams pick automatically. Saved in {mock_saved.path}")
    for label, file in (("real draft", saved), ("mock draft", mock_saved)):
        version, state, problem = file.load()
        if problem:
            print(f"Warning ({label}): {problem}")
        elif state is not None:
            print(f"Continuing the {label}: {len(state.get('picks', []))} picks (version {version}).")
        else:
            print(f"No saved {label} yet: starting empty.")
    if dev is not None:
        dev.watch(server.server_address[1], restart_in_place)
        print("Development mode: the page reloads on edits and the server restarts when a Python file changes.")
    if not args.no_browser and not os.environ.get(RESTARTED_ENV):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
