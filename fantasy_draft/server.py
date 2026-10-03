"""
Local web server for the draft dashboard.

Standard library only. It binds to 127.0.0.1, serves four static files and JSON endpoints, and
analyses without state: the page sends the whole draft with every request. The only thing kept is the saved draft
(see saved_draft.py).

Binding to 127.0.0.1 keeps other computers out, but not other web pages in the user's own browser. A page
on any site can make the browser send a request here, and DNS rebinding can even make it read the reply. So
every request (checked once, in `parse_request`) must name this server in its `Host` header, a browser-supplied `Origin` must be this server
too, and POSTs must be `application/json`, which a foreign page cannot send without a preflight we never grant.

    GET  /               the page
    GET  /api/pool       league settings, categories and every player
    POST /api/analyze    recommendation for a draft state
    GET  /api/draft      the saved draft and its version
    POST /api/draft      save the draft, naming the version it is based on
    POST /api/league     the league projected with every team completed by the same planner (slow early on)
    POST /api/predict    what each other team should have picked against what was logged (real draft only)
    POST /api/autopick   the pick the team on the clock would make (mock draft only)

The same page and routes also exist under /mock/ (/mock, /mock/api/pool, ...). That is the mock draft: its own service
and its own saved draft file, where the other 13 teams pick automatically. The real draft's routes never answer
/api/autopick, and nothing under /mock/ can read or write the real draft file, so a practice cannot mix with it.
"""

import hashlib
import json
import socketserver
import sys
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fantasy_draft.devmode import DevMode
from fantasy_draft.saved_draft import Conflict, SavedDraft, SavedDraftError
from fantasy_draft.service import DraftService, RequestError

WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_BODY_BYTES = 1_000_000
HOST = "127.0.0.1"
LOCAL_NAMES = ("127.0.0.1", "localhost")
MOCK_PREFIX = "/mock"

Draft = Tuple[DraftService, SavedDraft]  # a draft is served by its analysis service and its saved file

# Only these files are ever served from disk, so a crafted path cannot reach anything else
STATIC_FILES: Dict[str, Tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/logic.js": ("logic.js", "text/javascript; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class DashboardHandler(BaseHTTPRequestHandler):
    """Routes requests to the static files and the draft service."""

    def __init__(self, real: Draft, mock: Optional[Draft], *args: Any, dev: Optional[DevMode] = None, **kwargs: Any) -> None:
        self.real = real
        self.mock = mock
        self.dev = dev
        super().__init__(*args, **kwargs)

    def parse_request(self) -> bool:
        """The one gate: nothing reaches a `do_*` method, present or future, unless it names this server.

        BaseHTTPRequestHandler calls this after reading the request line and headers and before choosing the method
        to run; a False answer ends the request. A method with no `do_*` (PUT, DELETE, HEAD...) is gated too.
        """
        return super().parse_request() and self._is_local_request()

    def _route(self) -> Tuple[Optional[Draft], str]:
        """The draft a path belongs to (None if there is none) and the path without its /mock prefix."""
        path = self.path.split("?", 1)[0]
        if path == MOCK_PREFIX or path.startswith(MOCK_PREFIX + "/"):
            return self.mock, path[len(MOCK_PREFIX):] or "/"
        return self.real, path

    def do_GET(self) -> None:  # noqa: N802 (name fixed by BaseHTTPRequestHandler)
        draft, path = self._route()
        if draft is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        service, saved = draft
        if path in STATIC_FILES and (draft is self.real or path == "/"):  # under /mock only the page itself
            filename, content_type = STATIC_FILES[path]
            body = (WEB_DIR / filename).read_bytes()
            if self.dev is not None and path == "/":  # development mode: the page follows the files (see devmode.py)
                body = body.replace(b"</body>", b'<script src="/dev.js"></script>\n</body>')
            self._send(HTTPStatus.OK, body, content_type)
        elif self.dev is not None and draft is self.real and path == "/dev.js":
            self._send(HTTPStatus.OK, (WEB_DIR / "dev.js").read_bytes(), "text/javascript; charset=utf-8")
        elif self.dev is not None and draft is self.real and path == "/api/dev":
            self._send_json(HTTPStatus.OK, {"stamp": self.dev.stamp()})
        elif path == "/api/pool":
            self._send_json(HTTPStatus.OK, service.pool_payload())
        elif path == "/api/draft":
            version, state, problem = saved.load()
            # The id names this draft file in this mode, so the page can keep its browser copy per draft, not per port:
            # a mock draft and the real one may share a port and must never share a copy
            ident = hashlib.sha1(f"{saved.path.resolve()}|{service.rehearsal}".encode()).hexdigest()[:12]
            self._send_json(HTTPStatus.OK, {"id": ident, "version": version, "state": state, "problem": problem})
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        draft, path = self._route()
        if draft is None or path not in ("/api/analyze", "/api/league", "/api/predict", "/api/draft", "/api/autopick"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        service, saved = draft
        if self.headers.get_content_type() != "application/json":
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Send the request as application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_BODY_BYTES:
                # Refuse without reading the body, and do not keep the connection for the unread bytes
                self.close_connection = True
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "The request body is too large"})
                return
            if length <= 0:
                raise RequestError("The request body is missing")
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise RequestError("The request body must be a JSON object")
            if path == "/api/draft":
                version = saved.save(request.get("state"), request.get("baseVersion"))
                self._send_json(HTTPStatus.OK, {"version": version})
            elif path == "/api/autopick":
                self._send_json(HTTPStatus.OK, service.autopick(request))
            elif path == "/api/predict":
                self._send_json(HTTPStatus.OK, service.predict_picks(request))
            elif path == "/api/league":
                self._send_json(HTTPStatus.OK, service.project_league(request))
            else:
                self._send_json(HTTPStatus.OK, service.analyze(request))
        except Conflict as conflict:
            self._send_json(HTTPStatus.CONFLICT, {"error": str(conflict), "version": conflict.current})
        except (RequestError, SavedDraftError, json.JSONDecodeError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def _is_local_request(self) -> bool:
        """Answer 403 and return False unless the request names this server as its host and, if sent, its origin."""
        port = self.server.server_address[1]
        hosts = {f"{name}:{port}" for name in LOCAL_NAMES}
        origin = self.headers.get("Origin")
        if self.headers.get("Host", "").lower() in hosts and (origin is None or origin.lower() in {f"http://{h}" for h in hosts}):
            return True
        self.close_connection = True
        self._send_json(HTTPStatus.FORBIDDEN, {"error": "This server only answers requests made from its own page"})
        return False

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        self._send(status, json.dumps(payload, separators=(",", ":")).encode("utf-8"), "application/json")

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Stay quiet: the console should show the URL, not every request."""


class LocalServer(ThreadingHTTPServer):
    """ThreadingHTTPServer without the reverse-DNS lookup HTTPServer does while binding.

    That lookup (socket.getfqdn) can stall for 30 seconds or more on some networks, which would make the
    dashboard hang at startup. Nothing here needs the host's full name.
    """

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Stay quiet when the page hung up before the answer was sent (a reload or a cancelled request); report the rest."""
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


def make_server(
    service: DraftService,
    port: int = 0,
    saved: Optional[SavedDraft] = None,
    mock: Optional[Draft] = None,
    dev: Optional[DevMode] = None,
) -> ThreadingHTTPServer:
    """Create (but do not start) a server on 127.0.0.1; port 0 picks a free one. `mock` adds the /mock/ draft.

    `dev` turns on development mode: the page gets a small script that reloads it when the files change.
    """
    return LocalServer((HOST, port), partial(DashboardHandler, (service, saved or SavedDraft()), mock, dev=dev))
