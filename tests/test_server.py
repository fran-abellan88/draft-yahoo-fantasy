"""Tests for the local HTTP server, run against a real server on a free port."""

import http.client
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

import pytest

from fantasy_draft.data import load_players
from fantasy_draft.server import HOST, make_server
from fantasy_draft.service import DraftService

ALL = ["fg_pct", "ft_pct", "3ptm", "pts", "reb", "ast", "st", "blk", "to"]


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    server = make_server(DraftService(load_players()), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://{HOST}:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _get(url: str) -> Tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.headers["Content-Type"], response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read()


def _post(url: str, body: bytes, content_type: str = "application/json") -> Tuple[int, Dict[str, Any]]:
    request = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_the_page_and_its_assets_are_served(base_url: str) -> None:
    pages = (("/", "text/html"), ("/app.js", "text/javascript"), ("/logic.js", "text/javascript"), ("/style.css", "text/css"))
    for path, expected_type in pages:
        status, content_type, body = _get(base_url + path)
        assert status == 200 and content_type.startswith(expected_type) and body


def test_the_page_references_only_local_assets(base_url: str) -> None:
    html = _get(base_url + "/")[2].decode()
    assert "http://" not in html and "https://" not in html, "the page must work with no network"


def test_pool_endpoint(base_url: str) -> None:
    status, content_type, body = _get(base_url + "/api/pool")
    payload = json.loads(body)
    assert status == 200 and content_type == "application/json"
    assert len(payload["players"]) == 150 and payload["league"]["slot"] == 2


def test_analyze_endpoint(base_url: str) -> None:
    status, payload = _post(base_url + "/api/analyze", json.dumps({"categories": ALL, "picks": []}).encode())
    assert status == 200
    assert payload["clock"]["pick"] == 1 and payload["recommendation"]["pick"] == 2


def test_a_bad_request_gets_a_readable_400(base_url: str) -> None:
    status, payload = _post(base_url + "/api/analyze", json.dumps({"categories": [], "picks": []}).encode())
    assert status == 400 and "at least one" in payload["error"]


@pytest.mark.parametrize("body", [b"not json", b"[]", b"", b'"text"'])
def test_malformed_bodies_get_a_400_not_a_crash(base_url: str, body: bytes) -> None:
    status, payload = _post(base_url + "/api/analyze", body)
    assert status == 400 and "error" in payload


def test_an_oversized_body_is_refused_before_it_is_read(base_url: str) -> None:
    # Announce a huge body without sending it: the server must answer from the header alone
    connection = http.client.HTTPConnection(HOST, int(base_url.rsplit(":", 1)[1]), timeout=10)
    try:
        connection.putrequest("POST", "/api/analyze")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", "5000000")
        connection.endheaders()
        response = connection.getresponse()
        assert response.status == 413
        assert "too large" in json.loads(response.read())["error"]
    finally:
        connection.close()


@pytest.mark.parametrize(
    "path",
    ["/nope", "/../fantasy_draft/server.py", "/..%2fserver.py", "/app.js/../../data/2026-27/projections.csv", "/api/analyze"],
)
def test_nothing_outside_the_whitelist_is_served(base_url: str, path: str) -> None:
    status, _, body = _get(base_url + path)
    assert status == 404
    assert b"DashboardHandler" not in body and b"xrank" not in body


def test_post_to_other_paths_is_404(base_url: str) -> None:
    status, _ = _post(base_url + "/api/pool", b"{}")
    assert status == 404


def test_the_server_only_listens_on_localhost() -> None:
    server = make_server(DraftService(load_players()), port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def _raw(port: int, method: str, path: str, headers: Dict[str, str], body: bytes = b"") -> Tuple[int, Dict[str, Any]]:
    """Send a request with exactly these headers (http.client would otherwise fill in Host itself)."""
    connection = http.client.HTTPConnection(HOST, port, timeout=10)
    try:
        connection.putrequest(method, path, skip_host=True)
        for name, value in headers.items():
            connection.putheader(name, value)
        if body:
            connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def _port(base_url: str) -> int:
    return int(base_url.rsplit(":", 1)[1])


ANALYZE = json.dumps({"categories": ["pts"], "picks": []}).encode()


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1", "127.0.0.1:1", "localhost.evil.example:{port}", "evil.example:{port}"])
def test_a_request_for_another_host_is_refused(base_url: str, host: str) -> None:
    # DNS rebinding: a hostile site's name pointing at 127.0.0.1 would otherwise be answered
    port = _port(base_url)
    headers = {"Host": host.format(port=port), "Content-Type": "application/json"}
    assert _raw(port, "GET", "/api/pool", headers)[0] == 403
    assert _raw(port, "POST", "/api/analyze", headers, ANALYZE)[0] == 403


def test_a_request_with_no_host_header_is_refused(base_url: str) -> None:
    assert _raw(_port(base_url), "GET", "/api/pool", {})[0] == 403


@pytest.mark.parametrize("origin", ["https://evil.example", "http://evil.example", "null", "http://127.0.0.1:1", "http://localhost"])
def test_a_request_from_another_origin_is_refused(base_url: str, origin: str) -> None:
    port = _port(base_url)
    headers = {"Host": f"{HOST}:{port}", "Origin": origin, "Content-Type": "application/json"}
    assert _raw(port, "POST", "/api/analyze", headers, ANALYZE)[0] == 403


@pytest.mark.parametrize("name", ["127.0.0.1", "localhost", "LOCALHOST"])
def test_the_page_own_address_is_accepted_with_or_without_an_origin(base_url: str, name: str) -> None:
    port = _port(base_url)
    host = f"{name}:{port}"
    plain = {"Host": host, "Content-Type": "application/json"}
    assert _raw(port, "POST", "/api/analyze", plain, ANALYZE)[0] == 200
    assert _raw(port, "POST", "/api/analyze", {**plain, "Origin": f"http://{host}"}, ANALYZE)[0] == 200


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data", None])
def test_a_post_that_is_not_json_is_refused(base_url: str, content_type: Optional[str]) -> None:
    # text/plain is what a foreign page can send without a preflight
    port = _port(base_url)
    headers = {"Host": f"{HOST}:{port}"}
    if content_type:
        headers["Content-Type"] = content_type
    status, payload = _raw(port, "POST", "/api/analyze", headers, ANALYZE)
    assert status == 415 and "application/json" in payload["error"]


def test_json_with_a_charset_is_accepted(base_url: str) -> None:
    port = _port(base_url)
    headers = {"Host": f"{HOST}:{port}", "Content-Type": "application/json; charset=utf-8"}
    assert _raw(port, "POST", "/api/analyze", headers, ANALYZE)[0] == 200


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE"])
def test_every_method_is_refused_for_another_host_before_anything_else(base_url: str, method: str) -> None:
    port = _port(base_url)
    connection = http.client.HTTPConnection(HOST, port, timeout=10)
    try:
        connection.putrequest(method, "/api/analyze", skip_host=True)
        connection.putheader("Host", "evil.example")
        connection.putheader("Content-Length", "0")
        connection.endheaders()
        assert connection.getresponse().status == 403
    finally:
        connection.close()


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH", "OPTIONS"])
def test_a_method_the_server_does_not_support_is_501_from_its_own_page(base_url: str, method: str) -> None:
    port = _port(base_url)
    connection = http.client.HTTPConnection(HOST, port, timeout=10)
    try:
        connection.request(method, "/api/analyze")
        assert connection.getresponse().status == 501
    finally:
        connection.close()


def test_the_gate_is_in_one_place_not_repeated_in_each_method() -> None:
    from fantasy_draft import server

    source = Path(server.__file__).read_text()
    assert source.count("self._is_local_request()") == 1, "only parse_request calls the check"
