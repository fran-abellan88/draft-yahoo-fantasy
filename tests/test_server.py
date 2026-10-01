"""Tests for the local HTTP server, run against a real server on a free port."""

import http.client
import json
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, Tuple

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
    for path, expected_type in (("/", "text/html"), ("/app.js", "text/javascript"), ("/style.css", "text/css")):
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
