"""Checks on the static page files that a browser would otherwise be the only judge of."""

import re
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from fantasy_draft.categories import CATEGORIES


WEB = Path(__file__).resolve().parent.parent / "fantasy_draft" / "web"
CSS = (WEB / "style.css").read_text()
JS = (WEB / "app.js").read_text()

WCAG_TEXT = 4.5


def _tokens(block: str) -> Dict[str, str]:
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", block))


def _themes() -> Dict[str, Dict[str, str]]:
    light_block = re.search(r":root\s*\{(.*?)\n\}", CSS, re.S)
    dark_block = re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{(.*?)\}", CSS, re.S)
    assert light_block and dark_block, "the colour tokens moved; update this test"
    light = _tokens(light_block.group(1))
    return {"light": light, "dark": {**light, **_tokens(dark_block.group(1))}}


def _luminance(colour: str) -> float:
    channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# (text token, background token, where it is used)
TEXT_PAIRS: List[Tuple[str, str, str]] = [
    ("on-mine", "mine", "primary button and the snake cell for my pick on the clock"),
    ("ink", "line", "snake cells for picks already made"),
    ("mine", "mine-soft", "snake cells for my picks already made"),
    ("mine", "surface", "snake cells for my coming picks, roster pick numbers"),
    ("muted", "surface", "secondary text on cards"),
    ("paper", "ink", "snake cell on the clock, active filter chip"),
]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("foreground,background,usage", TEXT_PAIRS)
def test_text_colours_are_readable_in_both_themes(theme: str, foreground: str, background: str, usage: str) -> None:
    tokens = _themes()[theme]
    ratio = _contrast(tokens[foreground], tokens[background])
    assert ratio >= WCAG_TEXT, f"{foreground} on {background} is {ratio:.2f}:1 in {theme} mode ({usage})"


def test_the_hidden_attribute_wins_over_display_rules() -> None:
    # Without this, `.fields { display: grid }` keeps a `hidden` element visible
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", CSS)


def test_the_page_declares_both_colour_schemes() -> None:
    # Otherwise form controls and scrollbars stay light in dark mode
    assert re.search(r"color-scheme:\s*light dark", CSS)


def test_table_labels_use_the_same_names_as_the_categories() -> None:
    labels = dict(re.findall(r"\{ key: '([\w]+)', label: '([^']+)', kind:", JS))
    assert labels, "the stat columns moved; update this test"
    for key, label in labels.items():
        assert label == CATEGORIES[key].label, f"{key}: the table says {label}, the category list says {CATEGORIES[key].label}"


def test_the_sorted_column_is_marked_on_its_header_cell_with_an_arrow() -> None:
    assert "header.setAttribute('aria-sort'" in JS and "button.setAttribute('aria-sort'" not in JS
    assert re.search(r'th\[aria-sort="ascending"\] button::after', CSS)
    assert re.search(r'th\[aria-sort="descending"\] button::after', CSS)


def test_the_error_banner_stays_on_screen_and_offers_a_retry() -> None:
    banner = re.search(r"\.banner\s*\{(.*?)\}", CSS, re.S)
    assert banner and "position: fixed" in banner.group(1), "a banner in the page flow is off-screen when the table is scrolled"
    html = (WEB / "index.html").read_text()
    assert re.search(r'id="error"[^>]*>.*?id="error-retry"', html, re.S)
    assert "$('error-retry').addEventListener('click', refresh)" in JS


def test_only_network_failures_are_retried_automatically() -> None:
    # A rejected request (4xx) fails the same way again, so it must not be in the retry loop
    assert "NETWORK_RETRIES" in JS and "response.status >= 500" in JS
    loop = JS[JS.index("for (let attempt"): JS.index("if (response === null)")]
    assert "response.ok" not in loop


def test_the_page_shows_a_busy_state_and_the_search_note() -> None:
    html = (WEB / "index.html").read_text()
    assert 'id="search-note"' in html
    assert "BUSY_AFTER_MS" in JS and "main.busy" in CSS
    assert "analysis.search.truncated" in JS, "an incomplete search must be said on the page, not hidden"


def test_the_page_prices_alternatives_with_the_gap_the_server_sends() -> None:
    assert "alt.behind" in JS and "alt.share" not in JS


def test_the_alternatives_line_is_hidden_when_it_says_nothing() -> None:
    # A cut-short search prices them approximately, and all-equal alternatives leave nothing to choose between
    worth_showing = re.search(r"function alternativesWorthShowing\(\)\s*\{\s*return (.*?);", JS, re.S)
    assert worth_showing and "!analysis.search.truncated" in worth_showing.group(1) and "alternatives.some" in worth_showing.group(1)
    assert "analysis.alternativesMode === 'gone'" in JS


def test_a_late_reply_marks_the_row_that_was_just_clicked() -> None:
    # The hero dims after 200 ms, but the user is looking at the table
    assert re.search(r"function showBusy\(\)\s*\{[^}]*renderPool\(\)", JS, re.S)
    assert "badge('Logging the pick'" in JS
    assert "with a note" not in JS, "the busy state dims the plan, it shows no note"


def test_the_page_can_log_a_pick_that_is_not_in_the_list() -> None:
    html = (WEB / "index.html").read_text()
    assert 'id="outside"' in html
    assert "$('outside').addEventListener('click', draftOutside)" in JS
    assert "state.picks.push({ kind: 'outside' })" in JS


def test_the_page_can_catch_up_and_mark_players_gone() -> None:
    html = (WEB / "index.html").read_text()
    for element in ('id="behind"', 'id="behind-form"', 'id="behind-pick"', 'id="unseen-note"'):
        assert element in html
    assert "$('behind-form').addEventListener('submit', submitBehind)" in JS
    assert "planBehind(" in JS and "markGone(state.picks" in JS
    # The Gone button must not also log the row it sits in
    gone = JS[JS.index("function goneButton"): JS.index("function matchesFilters")]
    assert "event.stopPropagation()" in gone and gone.count("stopPropagation") == 2


def test_on_my_turn_with_unseen_picks_the_page_shows_the_doubt_the_better_players_and_a_gone_button() -> None:
    hero = JS[JS.index("function renderHero"): JS.index("function meter")]
    assert "hasUnseenPicks()" in hero and "Check Yahoo" in hero
    assert "analysis.lookFirst" in hero and "look first at" in hero
    assert "markPlayerGone(recommendation.id)" in hero and "He is gone" in hero
    plan = JS[JS.index("function renderPlan"):]
    assert "!hasUnseenPicks()" in plan[: plan.index("\nfunction ", 10)]
