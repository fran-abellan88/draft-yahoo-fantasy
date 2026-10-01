"""
Start the draft dashboard on this computer and open it in the browser.

    python run_dashboard.py              # http://127.0.0.1:8001, or the next free port
    python run_dashboard.py --port 9000
    python run_dashboard.py --no-browser

The server only listens on 127.0.0.1, so nobody else on the network can reach it.
"""

import argparse
import sys
import webbrowser
from http.server import ThreadingHTTPServer

from fantasy_draft.data import load_players
from fantasy_draft.server import HOST, make_server
from fantasy_draft.service import DraftService

PORT_ATTEMPTS = 20


def bind(service: DraftService, first_port: int) -> ThreadingHTTPServer:
    """Bind to the first free port at or after `first_port`."""
    for port in range(first_port, first_port + PORT_ATTEMPTS):
        try:
            return make_server(service, port)
        except OSError:
            print(f"Port {port} is busy, trying the next one")
    raise SystemExit(f"No free port between {first_port} and {first_port + PORT_ATTEMPTS - 1}")


def main() -> None:
    """Load the data, start the server and wait until Ctrl+C."""
    parser = argparse.ArgumentParser(description="Draft assistant dashboard")
    parser.add_argument("--port", type=int, default=8001, help="first port to try (default: %(default)s)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args()

    try:
        service = DraftService(load_players())
    except FileNotFoundError as error:
        sys.exit(f"Missing data file: {error.filename}. Run fetch_yahoo_players.py first.")
    server = bind(service, args.port)
    url = f"http://{HOST}:{server.server_address[1]}/"
    print(f"Draft assistant running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
