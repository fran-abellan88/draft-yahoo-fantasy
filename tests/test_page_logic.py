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
