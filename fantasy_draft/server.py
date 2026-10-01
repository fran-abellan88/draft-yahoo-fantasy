"""
Local web server for the draft dashboard.

Standard library only. It binds to 127.0.0.1, serves three static files and two JSON endpoints, and
holds no state: the page sends the whole draft with every request.

    GET  /               the page
    GET  /api/pool       league settings, categories and every player
    POST /api/analyze    recommendation for a draft state
"""

import json
import socketserver
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

from fantasy_draft.service import DraftService, RequestError

WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_BODY_BYTES = 1_000_000
HOST = "127.0.0.1"

# Only these files are ever served from disk, so a crafted path cannot reach anything else
STATIC_FILES: Dict[str, Tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class DashboardHandler(BaseHTTPRequestHandler):
    """Routes requests to the static files and the draft service."""

    def __init__(self, service: DraftService, *args: Any, **kwargs: Any) -> None:
        self.service = service
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 (name fixed by BaseHTTPRequestHandler)
        path = self.path.split("?", 1)[0]
        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            self._send(HTTPStatus.OK, (WEB_DIR / filename).read_bytes(), content_type)
        elif path == "/api/pool":
            self._send_json(HTTPStatus.OK, self.service.pool_payload())
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/api/analyze":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
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
            self._send_json(HTTPStatus.OK, self.service.analyze(request))
        except (RequestError, json.JSONDecodeError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

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


def make_server(service: DraftService, port: int = 0) -> ThreadingHTTPServer:
    """Create (but do not start) a server on 127.0.0.1; port 0 picks a free one."""
    return LocalServer((HOST, port), partial(DashboardHandler, service))
