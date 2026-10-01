"""Tests for the page's pure JavaScript (fantasy_draft/web/logic.js), run under Node.

The project has no JavaScript test runner, so logic that only exists in the page is otherwise reached by nothing but
a browser. Keep such logic in logic.js, free of the DOM, and test it here. Skipped when Node is not installed.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest

from fantasy_draft.service import RULE_LIMITS, RequestError, parse_rule

WEB = Path(__file__).resolve().parent.parent / "fantasy_draft" / "web"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is not installed")

LIMITS = {key: {"default": d, "min": low, "max": high} for key, (d, low, high) in RULE_LIMITS.items()}


def _run(expression: str) -> Any:
    """Evaluate a JavaScript expression with logic.js loaded and return its JSON."""
    script = f"const L = require({json.dumps(str(WEB / 'logic.js'))}); console.log(JSON.stringify({expression}));"
    assert NODE is not None
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)


SPREAD = {"default": 2.0, "min": 0.1, "max": 20.0}


@pytest.mark.parametrize(
    "raw,expected",
    [
        (5, 5),
        ("3.5", 3.5),
        (0.1, 0.1),
        (20, 20),
        (25, 20),
        (-4, 0.1),
        (0, 0.1),  # zero is below the lowest allowed value, not "blank"
        ("", 2.0),
        ("   ", 2.0),
        ("abc", 2.0),
        (None, 2.0),
        (True, 2.0),
    ],
)
def test_one_value_is_held_in_range_and_a_blank_becomes_the_default(raw: Any, expected: float) -> None:
    assert _run(f"L.clampRuleValue({json.dumps(raw)}, {json.dumps(SPREAD)})") == pytest.approx(expected)


def test_undefined_and_non_finite_values_become_the_default() -> None:
    assert _run(f"[L.clampRuleValue(undefined, {json.dumps(SPREAD)}), L.clampRuleValue(NaN, {json.dumps(SPREAD)}), "
                f"L.clampRuleValue(Infinity, {json.dumps(SPREAD)})]") == [2.0, 2.0, 2.0]


def test_a_rule_is_completed_clamped_and_stripped_of_unknown_keys() -> None:
    rule = _run(f"L.sanitizeRule({{type: 'window', baseSd: 99, slack: '12', extra: 1}}, {json.dumps(LIMITS)})")
    assert rule == {"type": "window", "baseSd": 20.0, "sdPerAdp": 0.2, "threshold": 0.5, "slack": 12.0}


@pytest.mark.parametrize("garbage", ["null", "undefined", "'text'", "42", "[]", "{type: 'bogus'}"])
def test_a_rule_that_is_not_a_rule_becomes_the_default_probability_rule(garbage: str) -> None:
    rule = _run(f"L.sanitizeRule({garbage}, {json.dumps(LIMITS)})")
    assert rule == {"type": "probability", "baseSd": 2.0, "sdPerAdp": 0.2, "threshold": 0.5, "slack": 3.0}


def test_whatever_the_page_sanitises_the_server_accepts() -> None:
    """The clamp exists so a saved or typed value cannot be refused on every request; check it against the server."""
    nasty: List[str] = ["''", "'0'", "-1", "1e9", "NaN", "null", "true", "'abc'", "Infinity", "-Infinity", "0.0001", "[]"]
    rules: List[Dict[str, Any]] = _run(
        "[" + ", ".join(
            f"L.sanitizeRule({{type: {kind}, baseSd: {v}, sdPerAdp: {v}, threshold: {v}, slack: {v}}}, {json.dumps(LIMITS)})"
            for kind in ("'probability'", "'window'")
            for v in nasty
        ) + "]"
    )
    assert len(rules) == 2 * len(nasty)
    for rule in rules:
        try:
            parse_rule(rule)
        except RequestError as error:  # pragma: no cover - only on failure
            pytest.fail(f"the server refused {rule}: {error}")


def test_the_page_defaults_and_input_ranges_match_the_server_limits() -> None:
    js = (WEB / "app.js").read_text()
    default = re.search(r"const DEFAULT_RULE = \{([^}]*)\};", js)
    assert default
    page_defaults = {key: float(value) for key, value in re.findall(r"(\w+): ([\d.]+)", default.group(1))}
    assert page_defaults == {key: d for key, (d, _, _) in RULE_LIMITS.items()}
    html = (WEB / "index.html").read_text()
    inputs = {"baseSd": "rule-base-sd", "sdPerAdp": "rule-sd-per-adp", "threshold": "rule-threshold", "slack": "rule-slack"}
    for key, element in inputs.items():
        tag = re.search(rf'<input id="{element}"[^>]*>', html)
        assert tag, element
        low = float(re.search(r'min="([\d.]+)"', tag.group(0)).group(1))
        high = float(re.search(r'max="([\d.]+)"', tag.group(0)).group(1))
        assert (low, high) == (RULE_LIMITS[key][1], RULE_LIMITS[key][2]), f"{element} in index.html disagrees with the server"


KNOWN = "new Set(['a', 'b', 'c'])"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("['a', 'b']", [{"kind": "player", "id": "a"}, {"kind": "player", "id": "b"}]),  # the first version's shape
        ("[{kind: 'player', id: 'a'}, 'b']", [{"kind": "player", "id": "a"}, {"kind": "player", "id": "b"}]),
        ("[{id: 'a'}]", [{"kind": "player", "id": "a"}]),  # no kind means a player
        ("[]", []),
    ],
)
def test_a_saved_pick_log_in_either_shape_becomes_a_list_of_objects(raw: str, expected: List[Dict[str, Any]]) -> None:
    assert _run(f"L.normalizePicks({raw}, {KNOWN})") == expected


@pytest.mark.parametrize(
    "raw",
    ["['a', 'a']", "['nobody']", "[{kind: 'player'}]", "[{kind: 'dunk', id: 'a'}]", "[null]", "[['a']]", "'a'", "null", "undefined", "[7]"],
)
def test_a_pick_log_with_any_unusable_entry_is_refused_as_a_whole(raw: str) -> None:
    assert _run(f"L.normalizePicks({raw}, {KNOWN})") is None


def test_the_current_saved_state_wins_and_the_first_version_is_the_fallback() -> None:
    assert _run("L.pickSavedState({version: 2, picks: []}, {picks: ['a']})") == {"version": 2, "picks": []}
    assert _run("L.pickSavedState(null, {picks: ['a']})") == {"picks": ["a"]}
    assert _run("L.pickSavedState(null, null)") is None
    assert _run("L.pickSavedState('junk', 5)") is None


def test_a_page_pick_log_is_accepted_by_the_server() -> None:
    """What the page saves must be what the server reads: run the page's normaliser and parse the result."""
    from fantasy_draft.data import load_players
    from fantasy_draft.service import DraftService

    service = DraftService(load_players())
    ids = service.players["player_id"].tolist()[:4]
    picks = _run(f"L.normalizePicks({json.dumps(ids)}, new Set({json.dumps(ids)}))")
    assert len(service._parse_picks(picks)) == 4


def test_an_outside_pick_has_no_id_and_a_player_pick_needs_one() -> None:
    assert _run(f"L.normalizePicks([{{kind: 'outside'}}, 'a'], {KNOWN})") == [{"kind": "outside"}, {"kind": "player", "id": "a"}]
    assert _run(f"L.normalizePicks([{{kind: 'outside', id: 'a'}}], {KNOWN})") is None


def test_unseen_and_gone_picks_are_kept_and_checked_like_the_other_kinds() -> None:
    assert _run(f"L.normalizePicks([{{kind: 'unseen'}}, {{kind: 'gone', id: 'a'}}, 'b'], {KNOWN})") == [
        {"kind": "unseen"},
        {"kind": "gone", "id": "a"},
        {"kind": "player", "id": "b"},
    ]
    assert _run(f"L.normalizePicks([{{kind: 'unseen', id: 'a'}}], {KNOWN})") is None  # an unseen pick names nobody
    assert _run(f"L.normalizePicks([{{kind: 'gone'}}], {KNOWN})") is None  # a gone pick must name the player
    assert _run(f"L.normalizePicks(['a', {{kind: 'gone', id: 'a'}}], {KNOWN})") is None  # one player, once


MY_PICKS = [2, 27, 30, 55, 58, 83, 86, 111]


def _behind(logged: int, yahoo: Any, mine: List[int] = MY_PICKS, total: int = 182) -> Dict[str, Any]:
    return _run(f"L.planBehind({logged}, {json.dumps(yahoo)}, {json.dumps(mine)}, {total})")


def test_being_behind_adds_the_picks_in_between_as_unseen() -> None:
    plan = _behind(logged=3, yahoo=9)  # picks 1 to 3 logged, Yahoo is at 9: picks 4 to 8 were missed
    assert plan == {"error": None, "unseen": [4, 5, 6, 7, 8], "stoppedAt": None}
    assert _behind(logged=3, yahoo="9")["unseen"] == [4, 5, 6, 7, 8]  # a typed value arrives as a string


def test_being_behind_stops_before_one_of_my_own_picks() -> None:
    """I always know my own pick, so it is never unseen: the user logs it and then asks again for the rest."""
    plan = _behind(logged=24, yahoo=31)  # 25 to 30 missed, but 27 and 30 are mine
    assert plan == {"error": None, "unseen": [25, 26], "stoppedAt": 27}
    assert _behind(logged=26, yahoo=31) == {"error": None, "unseen": [], "stoppedAt": 27}  # the first missed pick is mine
    assert _behind(logged=27, yahoo=31) == {"error": None, "unseen": [28, 29], "stoppedAt": 30}


@pytest.mark.parametrize(
    "logged,yahoo,message",
    [
        (24, 25, "not ahead of the next pick"),  # nothing missing: the next pick to log is 25
        (24, 20, "not ahead of the next pick"),
        (24, "", "Type the pick number"),
        (24, "abc", "Type the pick number"),
        (24, 28.5, "Type the pick number"),
        (24, None, "Type the pick number"),
        (24, 200, "The draft has 182 picks"),
    ],
)
def test_a_pick_that_is_not_ahead_of_the_log_is_refused(logged: int, yahoo: Any, message: str) -> None:
    plan = _behind(logged, yahoo)
    assert message in plan["error"] and plan["unseen"] == []


def test_marking_a_player_gone_resolves_the_unseen_pick_closest_to_his_adp_and_logs_nothing_new() -> None:
    picks = json.dumps([{"kind": "player", "id": "a"}] + [{"kind": "unseen"}] * 5)  # pick 1 seen; picks 2 to 6 unseen
    assert _run(f"L.markGone({picks}, 'b', 5.2)")[1:] == [{"kind": "unseen"}] * 3 + [{"kind": "gone", "id": "b"}, {"kind": "unseen"}]
    assert _run(f"L.markGone({picks}, 'b', 1)")[1:3] == [{"kind": "gone", "id": "b"}, {"kind": "unseen"}]  # nearest to the first
    assert _run(f"L.markGone({picks}, 'b', 90)")[5] == {"kind": "gone", "id": "b"}  # nearest to the last
    assert len(_run(f"L.markGone({picks}, 'b', 4)")) == 6, "the list is the same length: no pick is logged"


def test_with_no_usable_adp_the_first_unseen_pick_is_resolved() -> None:
    picks = json.dumps([{"kind": "player", "id": "a"}] + [{"kind": "unseen"}] * 3)
    for adp in ("undefined", "null", "NaN"):
        assert _run(f"L.markGone({picks}, 'b', {adp})")[1] == {"kind": "gone", "id": "b"}


def test_marking_gone_needs_an_unseen_pick_and_a_player_not_already_logged() -> None:
    assert _run("L.markGone([{kind: 'player', id: 'a'}], 'b', 5)") is None  # nothing unseen to resolve
    assert _run("L.markGone([{kind: 'unseen'}, {kind: 'player', id: 'a'}], 'a', 5)") is None  # already in the log
    picks = [{"kind": "unseen"}]
    before = json.dumps(picks)
    _run(f"L.markGone({before}, 'b', 3)")
    assert picks == [{"kind": "unseen"}], "the list given is not changed"


def test_what_the_page_builds_for_a_gap_is_accepted_by_the_server() -> None:
    """Page and server must agree on the shapes: build a log the way the page does and parse it."""
    from fantasy_draft.data import load_players
    from fantasy_draft.service import DraftService

    service = DraftService(load_players())
    ids = service.players.sort_values("adp_est")["player_id"].tolist()
    log = _run(f"L.normalizePicks({json.dumps(ids[:20])}, new Set({json.dumps(ids)}))")
    plan = _behind(logged=len(log), yahoo=27)
    log += [{"kind": "unseen"}] * len(plan["unseen"])
    log = _run(f"L.markGone({json.dumps(log)}, {json.dumps(ids[20])}, 21)")
    assert len(plan["unseen"]) == 6  # picks 21 to 26; pick 27 is mine, so the page stops there
    assert [pick.kind for pick in service._parse_picks(log)[18:]] == ["player", "player", "gone"] + ["unseen"] * 5


def test_undo_reverts_the_last_action_whatever_it_was() -> None:
    picks = [{"kind": "player", "id": "a"}, {"kind": "unseen"}, {"kind": "unseen"}, {"kind": "gone", "id": "b"}]
    history = [{"type": "log", "count": 1}, {"type": "log", "count": 3}, {"type": "gone", "index": 3}]
    first = _run(f"L.undoLast({json.dumps(picks)}, {json.dumps(history)})")
    assert first["picks"][3] == {"kind": "unseen"} and len(first["picks"]) == 4, "Gone is undone, no pick is lost"
    second = _run(f"L.undoLast({json.dumps(first['picks'])}, {json.dumps(first['history'])})")
    assert second["picks"] == [{"kind": "player", "id": "a"}], "the three unseen picks of one catch-up go together"


def test_undo_in_the_middle_of_the_log_does_not_touch_a_later_unseen_pick() -> None:
    picks = [{"kind": "gone", "id": "b"}, {"kind": "unseen"}]
    history = [{"type": "log", "count": 2}, {"type": "gone", "index": 0}]
    assert _run(f"L.undoLast({json.dumps(picks)}, {json.dumps(history)})")["picks"] == [{"kind": "unseen"}, {"kind": "unseen"}]


def test_undo_with_no_history_removes_the_last_entry_and_with_no_picks_does_nothing() -> None:
    assert _run("L.undoLast([{kind: 'unseen'}, {kind: 'unseen'}], [])")["picks"] == [{"kind": "unseen"}]
    assert _run("L.undoLast([], [])") is None


def test_a_saved_history_that_does_not_describe_the_log_is_dropped() -> None:
    picks = json.dumps([{"kind": "unseen"}])
    assert _run(f"L.sanitizeHistory([{{type: 'log', count: 1}}], {picks})") == [{"type": "log", "count": 1}]
    assert _run(f"L.sanitizeHistory([{{type: 'log', count: 5}}], {picks})") == []  # more than the log holds
    assert _run(f"L.sanitizeHistory([{{type: 'gone', index: 0}}], {picks})") == []  # that entry is not gone
    assert _run(f"L.sanitizeHistory([{{type: 'nope'}}], {picks})") == []
    assert _run(f"L.sanitizeHistory('x', {picks})") == []


def test_unmarking_a_gone_entry_makes_it_unseen_and_forgets_its_action() -> None:
    picks = json.dumps([{"kind": "gone", "id": "b"}, {"kind": "player", "id": "a"}])
    history = json.dumps([{"type": "log", "count": 2}, {"type": "gone", "index": 0}])
    result = _run(f"L.unmarkGone({picks}, {history}, 0)")
    assert result == {"picks": [{"kind": "unseen"}, {"kind": "player", "id": "a"}], "history": [{"type": "log", "count": 2}]}
    assert _run(f"L.unmarkGone({picks}, {history}, 1)") is None
