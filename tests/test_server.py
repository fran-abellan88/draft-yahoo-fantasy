"""Tests for the local HTTP server, run against a real server on a free port."""

import http.client
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

import pytest

from fantasy_draft.data import load_players
from fantasy_draft.saved_draft import SavedDraft
from fantasy_draft.server import HOST, LocalServer, make_server
from fantasy_draft.service import DraftService

ALL = ["fg_pct", "ft_pct", "3ptm", "pts", "reb", "ast", "st", "blk", "to"]


@pytest.fixture(scope="module")
def base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    saved = SavedDraft(tmp_path_factory.mktemp("saved") / "saved_draft.json")
    server = make_server(DraftService(load_players()), port=0, saved=saved)
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
    assert len(payload["players"]) == 245 and payload["league"]["slot"] == 2


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


def test_the_saved_draft_round_trips_through_the_server_and_rejects_a_stale_save(base_url: str) -> None:
    empty = json.loads(_get(base_url + "/api/draft")[2])
    assert {key: empty[key] for key in ("version", "state", "problem")} == {"version": 0, "state": None, "problem": None}
    state = {"version": 2, "picks": [{"kind": "unseen"}], "method": "uncapped"}
    status, payload = _post(base_url + "/api/draft", json.dumps({"baseVersion": 0, "state": state}).encode())
    assert (status, payload) == (200, {"version": 1})
    saved = json.loads(_get(base_url + "/api/draft")[2])
    assert {key: saved[key] for key in ("version", "state", "problem")} == {"version": 1, "state": state, "problem": None}
    assert saved["id"] == empty["id"], "the id names the file and mode, so it does not change with the contents"
    status, payload = _post(base_url + "/api/draft", json.dumps({"baseVersion": 0, "state": state}).encode())
    assert status == 409 and payload["version"] == 1 and "another window" in payload["error"]


MALFORMED_SAVES = [
    {"baseVersion": 1, "state": {"evil": 1}},
    {"baseVersion": 1, "state": []},
    {"baseVersion": "1", "state": {}},
    {"state": {}},
]


@pytest.mark.parametrize("body", MALFORMED_SAVES)
def test_a_malformed_save_is_a_400(base_url: str, body: Dict[str, Any]) -> None:
    status, payload = _post(base_url + "/api/draft", json.dumps(body).encode())
    assert status == 400 and "error" in payload


def test_the_saved_draft_endpoint_is_gated_like_the_rest(base_url: str) -> None:
    port = _port(base_url)
    headers = {"Host": "evil.example", "Content-Type": "application/json"}
    assert _raw(port, "GET", "/api/draft", headers)[0] == 403
    assert _raw(port, "POST", "/api/draft", headers, b'{"baseVersion": 0, "state": {}}')[0] == 403


def test_the_draft_id_names_the_file_and_the_mode_so_browser_copies_never_cross(tmp_path: Any) -> None:
    ids = set()
    for name, rehearsal in (("a.json", False), ("a.json", True), ("b.json", False)):
        server = make_server(DraftService(load_players(), rehearsal=rehearsal), port=0, saved=SavedDraft(tmp_path / name))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            ids.add(json.loads(_get(f"http://{HOST}:{server.server_address[1]}/api/draft")[2])["id"])
        finally:
            server.shutdown()
            server.server_close()
    assert len(ids) == 3 and all(len(value) == 12 for value in ids)


@pytest.fixture(scope="module")
def both(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Tuple[str, Path, Path]]:
    folder = tmp_path_factory.mktemp("both")
    players = load_players()
    real, mock = SavedDraft(folder / "real.json"), SavedDraft(folder / "mock.json")
    server = make_server(DraftService(players), port=0, saved=real, mock=(DraftService(players, rehearsal=True), mock))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://{HOST}:{server.server_address[1]}", folder / "real.json", folder / "mock.json"
    server.shutdown()
    server.server_close()


def test_the_mock_draft_is_served_apart_and_only_it_picks_automatically(both: Tuple[str, Path, Path]) -> None:
    url, _, _ = both
    status, content_type, body = _get(url + "/mock")
    assert status == 200 and content_type.startswith("text/html") and b"Draft assistant" in body
    assert _get(url + "/mock/")[0] == 200 and _get(url + "/mock/app.js")[0] == 404, "under /mock only the page itself"
    assert json.loads(_get(url + "/api/pool")[2])["rehearsal"] is False
    assert json.loads(_get(url + "/mock/api/pool")[2])["rehearsal"] is True
    players = load_players()
    body_picks = json.dumps({"picks": [players.iloc[0]["player_id"]]}).encode()
    assert _post(url + "/mock/api/autopick", body_picks)[0] == 200
    status, answer = _post(url + "/api/autopick", body_picks)
    assert status == 400 and "mock" in answer["error"].lower(), "the real draft refuses automatic picks"


def test_the_two_drafts_keep_separate_files_and_ids(both: Tuple[str, Path, Path]) -> None:
    url, real, mock = both
    real_id = json.loads(_get(url + "/api/draft")[2])["id"]
    mock_id = json.loads(_get(url + "/mock/api/draft")[2])["id"]
    assert real_id != mock_id
    state = {"version": 2, "picks": [], "history": [], "categories": ALL}
    assert _post(url + "/mock/api/draft", json.dumps({"baseVersion": 0, "state": state}).encode())[0] == 200
    assert mock.exists() and not real.exists(), "a mock save never touches the real file"
    assert json.loads(_get(url + "/api/draft")[2])["version"] == 0


def test_without_a_mock_draft_the_mock_routes_do_not_exist(base_url: str) -> None:
    assert _get(base_url + "/mock")[0] == 404 and _get(base_url + "/mock/api/pool")[0] == 404
    assert _post(base_url + "/mock/api/analyze", b"{}")[0] == 404


def test_the_mock_routes_are_gated_like_the_rest(both: Tuple[str, Path, Path]) -> None:
    url, _, _ = both
    port = _port(url)
    assert _raw(port, "GET", "/mock/api/draft", {"Host": "evil.example"})[0] == 403
    assert _raw(port, "POST", "/mock/api/autopick", {"Host": "evil.example", "Content-Type": "application/json"}, b"{}")[0] == 403


def test_the_planner_projection_has_its_own_route_in_both_drafts(both: Tuple[str, Path, Path]) -> None:
    url, _, _ = both
    body = json.dumps({"categories": ALL, "picks": [], "method": "uncapped", "gamesAdjusted": True}).encode()
    for prefix in ("", "/mock"):
        status, answer = _post(f"{url}{prefix}/api/league", body)
        assert status == 200 and len(answer["teams"]) == 14 and answer["fallbacks"] == 0
    assert _post(url + "/api/league", b'{"categories": [], "picks": []}')[0] == 400


def test_the_prediction_route_answers_in_the_real_draft_and_is_refused_in_the_mock_draft(both: Tuple[str, Path, Path]) -> None:
    url, _, _ = both
    body = json.dumps({"categories": ALL, "picks": [], "method": "uncapped", "gamesAdjusted": True}).encode()
    status, answer = _post(url + "/api/predict", body)
    assert status == 200 and answer["clock"]["pick"] == 1 and answer["picks"] == []
    status, answer = _post(url + "/mock/api/predict", body)
    assert status == 400 and "real draft" in answer["error"]


def test_a_page_that_hangs_up_before_the_answer_is_not_reported_as_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    server = LocalServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    try:
        try:
            raise BrokenPipeError()
        except BrokenPipeError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert capsys.readouterr().err == ""
        try:
            raise ValueError("a real bug")
        except ValueError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert "a real bug" in capsys.readouterr().err
    finally:
        server.server_close()
