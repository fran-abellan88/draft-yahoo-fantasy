"""Tests for development mode: off by default, and when on, a stamp the page compares and a file watcher."""

import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator, List, Tuple

import pytest

from fantasy_draft import devmode
from fantasy_draft.data import load_players
from fantasy_draft.devmode import DevMode, broken_source
from fantasy_draft.saved_draft import SavedDraft
from fantasy_draft.server import HOST, make_server
from fantasy_draft.service import DraftService


def _get(url: str) -> Tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


@pytest.fixture(scope="module")
def servers(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Tuple[str, str]]:
    players = load_players()
    started = []
    urls: List[str] = []
    for name, dev in (("plain", None), ("dev", DevMode())):
        server = make_server(DraftService(players), port=0, saved=SavedDraft(tmp_path_factory.mktemp(name) / "saved.json"), dev=dev)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        started.append(server)
        urls.append(f"http://{HOST}:{server.server_address[1]}")
    yield urls[0], urls[1]
    for server in started:
        server.shutdown()
        server.server_close()


def test_a_normal_run_has_no_reload_script_and_no_dev_routes(servers: Tuple[str, str]) -> None:
    plain, _ = servers
    status, page = _get(plain + "/")
    assert status == 200 and b"dev.js" not in page
    assert _get(plain + "/dev.js")[0] == 404 and _get(plain + "/api/dev")[0] == 404


def test_dev_mode_adds_the_reload_script_and_a_stamp(servers: Tuple[str, str]) -> None:
    _, dev = servers
    status, page = _get(dev + "/")
    assert status == 200 and page.count(b'<script src="/dev.js"></script>') == 1
    assert page.index(b"/dev.js") < page.rindex(b"</body>")
    assert b"location.reload" in _get(dev + "/dev.js")[1]
    first, second = _get(dev + "/api/dev")[1], _get(dev + "/api/dev")[1]
    assert first == second and b"stamp" in first


def test_the_mock_page_gets_the_script_and_its_assets_come_from_the_real_routes(tmp_path: Path) -> None:
    players = load_players()
    mock = (DraftService(players, rehearsal=True), SavedDraft(tmp_path / "mock.json"))
    server = make_server(DraftService(players), port=0, saved=SavedDraft(tmp_path / "real.json"), mock=mock, dev=DevMode())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://{HOST}:{server.server_address[1]}"
        assert b'<script src="/dev.js"></script>' in _get(base + "/mock")[1]
        assert _get(base + "/mock/dev.js")[0] == 404 and _get(base + "/mock/api/dev")[0] == 404  # only the real routes serve them
    finally:
        server.shutdown()
        server.server_close()


def test_the_stamp_changes_when_a_web_file_changes_and_after_a_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = tmp_path / "style.css"
    page.write_text("a {}")
    monkeypatch.setattr(devmode, "web_sources", lambda: [page])
    mode = DevMode()
    before = mode.stamp()
    time.sleep(0.01)
    page.write_text("a { color: red; }")
    assert mode.stamp() != before
    assert DevMode().stamp() != mode.stamp()  # a new process has a new start id


def test_a_syntax_error_is_found_before_a_restart(tmp_path: Path) -> None:
    good, bad = tmp_path / "good.py", tmp_path / "bad.py"
    good.write_text("x = 1\n")
    bad.write_text("def broken(:\n")
    assert broken_source([good]) is None
    assert broken_source([good, bad]) is not None


def test_the_watcher_restarts_on_a_change_but_waits_while_the_file_is_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "module.py"
    source.write_text("x = 1\n")
    monkeypatch.setattr(devmode, "python_sources", lambda: [source])
    monkeypatch.setattr(devmode, "POLL_SECONDS", 0.02)
    restarted = threading.Event()
    DevMode().watch(8123, restarted.set)
    time.sleep(0.1)
    assert not restarted.is_set()  # nothing changed yet
    source.write_text("def broken(:\n")
    assert not restarted.wait(0.3)  # a broken file does not restart the server
    source.write_text("x = 2\n")
    assert restarted.wait(2.0)
    assert devmode.os.environ[devmode.PORT_ENV] == "8123"
    devmode.os.environ.pop(devmode.PORT_ENV, None)
    devmode.os.environ.pop(devmode.RESTARTED_ENV, None)


def test_the_watched_files_are_the_sources_and_never_the_saved_draft() -> None:
    names = {path.name for path in devmode.python_sources() + devmode.web_sources()}
    assert {"service.py", "optimizer.py", "run_dashboard.py", "app.js", "style.css", "index.html"} <= names
    assert not any(name.startswith("saved_") and name.endswith(".json") for name in names)
