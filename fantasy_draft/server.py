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
    POST /api/autopick   the pick the team on the clock would make (rehearsal)
"""

import hashlib
import json
import socketserver
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fantasy_draft.saved_draft import Conflict, SavedDraft, SavedDraftError
from fantasy_draft.service import DraftService, RequestError

WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_BODY_BYTES = 1_000_000
HOST = "127.0.0.1"
LOCAL_NAMES = ("127.0.0.1", "localhost")

# Only these files are ever served from disk, so a crafted path cannot reach anything else
STATIC_FILES: Dict[str, Tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/logic.js": ("logic.js", "text/javascript; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class DashboardHandler(BaseHTTPRequestHandler):
    """Routes requests to the static files and the draft service."""

    def __init__(self, service: DraftService, saved: SavedDraft, *args: Any, **kwargs: Any) -> None:
        self.service = service
        self.saved = saved
        super().__init__(*args, **kwargs)

    def parse_request(self) -> bool:
        """The one gate: nothing reaches a `do_*` method, present or future, unless it names this server.

        BaseHTTPRequestHandler calls this after reading the request line and headers and before choosing the method
        to run; a False answer ends the request. A method with no `do_*` (PUT, DELETE, HEAD...) is gated too.
        """
        return super().parse_request() and self._is_local_request()

    def do_GET(self) -> None:  # noqa: N802 (name fixed by BaseHTTPRequestHandler)
        path = self.path.split("?", 1)[0]
        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            self._send(HTTPStatus.OK, (WEB_DIR / filename).read_bytes(), content_type)
        elif path == "/api/pool":
            self._send_json(HTTPStatus.OK, self.service.pool_payload())
        elif path == "/api/draft":
            version, state, problem = self.saved.load()
            # The id names this draft file in this mode, so the page can keep its browser copy per draft, not per port:
            # a rehearsal and the live draft may share a port one after the other and must never share a copy
            ident = hashlib.sha1(f"{self.saved.path.resolve()}|{self.service.rehearsal}".encode()).hexdigest()[:12]
            self._send_json(HTTPStatus.OK, {"id": ident, "version": version, "state": state, "problem": problem})
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path not in ("/api/analyze", "/api/draft", "/api/autopick"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
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
                version = self.saved.save(request.get("state"), request.get("baseVersion"))
                self._send_json(HTTPStatus.OK, {"version": version})
            elif path == "/api/autopick":
                self._send_json(HTTPStatus.OK, self.service.autopick(request))
            else:
                self._send_json(HTTPStatus.OK, self.service.analyze(request))
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


def make_server(service: DraftService, port: int = 0, saved: Optional[SavedDraft] = None) -> ThreadingHTTPServer:
    """Create (but do not start) a server on 127.0.0.1; port 0 picks a free one."""
    return LocalServer((HOST, port), partial(DashboardHandler, service, saved or SavedDraft()))
