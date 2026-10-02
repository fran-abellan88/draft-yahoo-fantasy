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
    ("ink", "hover", "the row under the pointer, the main click target"),
    ("muted", "hover", "player details on the hovered row"),
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


def test_the_error_banner_has_its_own_row_and_offers_a_retry() -> None:
    banner = re.search(r"\.banner\s*\{(.*?)\}", CSS, re.S)
    assert banner and "grid-area: err" in banner.group(1), "the banner has its own row under the top bar"
    assert re.search(r"html, body \{[^}]*overflow: hidden", CSS), "the page never scrolls, so a banner in the grid is always in view"
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
    assert "BUSY_AFTER_MS" in JS and "#app.busy" in CSS
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


def test_only_table_rows_choose_a_player_and_the_hero_button_ends_the_choosing() -> None:
    html = (WEB / "index.html").read_text()
    assert 'id="choosing-note"' in html
    row = JS[JS.index("function rowPicked"): JS.index("function draft(id)")]
    assert "if (choosing) choosePlayerFor(id)" in row, "checked before draft() can refuse on a complete draft"
    assert "if (choosing)" not in JS[JS.index("function draft(id)"): JS.index("function draftOutside")]
    assert "onclick: () => rowPicked(player.id)" in JS and "rowPicked(visibleIds[0])" in JS
    hero = JS[JS.index("function renderHero"): JS.index("function meter")]
    assert "cancelChoosing();" in hero and "draft(recommendation.id)" in hero
    assert "state.rule.type === 'window'" in JS and "Picks were missed" in JS
    assert "undoLabel(" in JS


def test_the_choosing_note_holds_the_confirmation_and_blocks_a_second_click_and_the_outside_button() -> None:
    note = JS[JS.index("function renderChoosing"): JS.index("function editPanel")]
    assert "choosing.pending.text" in note and "applyChosen" in note and "scrollIntoView" in note
    assert "$('outside').disabled = analysis.clock.draftComplete || choosing !== null" in note
    assert "if (choosing.pending) return;" in note


def test_the_page_saves_to_the_server_one_save_at_a_time_and_never_over_a_draft_it_could_not_read() -> None:
    save = JS[JS.index("function saveState"): JS.index("async function loadServerDraft")]
    assert "if (draftRefused) return;" in save, "a refused draft is kept, not replaced"
    assert "baseVersion: serverVersion" in save and "response.status === 409" in save
    assert "serverSaveAgain" in save, "one save in flight, then the latest state"
    assert "stickyError" in JS and "hideError(true)" in JS, "only Reset clears a message about the saved draft"
    init = JS[JS.index("async function init"):]
    assert "await loadServerDraft()" in init and "Can't read the saved draft" in init, "a failed read stops the page like the pool does"
    assert "loadServerDraft()" in init and "restoreState(source === 'server' ? server.state : null)" in init


def test_the_browser_copy_records_what_the_server_confirmed_and_an_ordinary_error_cannot_hide_a_sticky_one() -> None:
    assert "writeSync(false)" in JS and "writeSync(!serverSaveAgain)" in JS
    assert "chooseSource(server.version, server.state, local, readStored(syncKey()))" in JS
    show = JS[JS.index("function showError"): JS.index("function hideError")]
    assert "if (stickyError && !sticky) return;" in show


def test_the_sync_record_follows_every_successful_save_and_a_replaced_browser_copy_is_kept_and_announced() -> None:
    assert "writeSync(!serverSaveAgain)" in JS
    init = JS[JS.index("async function init"):]
    assert "discardsUnconfirmed(" in init and "asideKey()" in init and "showNotice(" in init
    assert 'id="error-dismiss"' in (WEB / "index.html").read_text()


def test_the_page_never_scrolls_and_each_width_has_its_own_named_areas() -> None:
    assert re.search(r"html, body \{[^}]*overflow: hidden", CSS)
    assert ".app {" in CSS and "height: 100vh" in CSS
    widths = (
        "(min-width: 2350px)",
        "(min-width: 1720px) and (max-width: 2349.98px)",
        "(min-width: 1240px) and (max-width: 1719.98px)",
        "(max-width: 1239.98px)",
    )
    for width in widths:
        assert f"@media {width}" in CSS, width
    for area in ("rec", "plan", "standing", "table", "team", "log", "teams", "tabs", "tabp"):
        assert f'{area}' in CSS
    html = (WEB / "index.html").read_text()
    for panel in ("rec", "plan", "standing", "table", "team", "log", "teams"):
        assert f'data-panel="{panel}"' in html, f"{panel} is a child of the one grid"
    # the recommendation never goes into a tab, at any width
    assert 'data-tab="rec"' not in html and '[data-panel="rec"]' not in CSS


def test_the_tab_strip_keeps_a_valid_active_tab_when_the_window_changes_width() -> None:
    assert "window.addEventListener('resize', syncTabs)" in JS
    sync = JS[JS.index("function syncTabs"): JS.index("function wireTabs")]
    assert "visibleTabs()" in sync and "aria-selected" in sync


def test_the_last_pick_and_the_settings_summary_are_shown_in_the_page() -> None:
    html = (WEB / "index.html").read_text()
    for element in ('id="last-pick"', 'id="settings-summary"', 'id="settings-toggle"', 'id="tabs"', 'id="mode"'):
        assert element in html
    assert "renderTopBar();" in JS[JS.index("function render()"):]
    assert html.index('id="reset"') > html.index('id="settings"'), "Reset lives in the settings panel"


def test_the_page_shows_the_standing_and_the_14_teams_and_can_rehearse() -> None:
    html = (WEB / "index.html").read_text()
    for element in ('id="league"', 'id="profile"'):
        assert element in html
    assert 'id="rehearsal"' not in html, "there is no button: a rehearsal is a separate instance, started with --rehearsal"
    assert "state.rehearsal = pool.rehearsal === true" in JS and "saved.rehearsal" not in JS
    render = JS[JS.index("function render()"):]
    assert "renderStanding();" in render and "renderLeague();" in render
    assert "'/api/autopick'" in JS and "noise: true" in JS and "seed: state.seed + state.picks.length" in JS
    undo = JS[JS.index("function undo()"): JS.index("// ---------- rehearsal")]
    assert "state.rehearsal" in undo, "in a rehearsal Undo goes back to just before my last pick"
    assert "autoPlayFailed" in JS and "!autoPlayFailed" in JS[JS.index("render();\n  if (state.rehearsal"):][:200]
    assert "seed: state.seed" in JS and "rehearsal: state.rehearsal" not in JS, "the mode is never saved with a draft"


def test_the_need_weights_are_a_setting_that_is_saved_requested_and_shown() -> None:
    assert 'id="needs"' in (WEB / "index.html").read_text()
    assert "needs: state.needs" in JS and "state.needs = saved.needs === true" in JS
    assert "analysis.needs" in JS and "Weights in use" in JS


def test_the_table_marks_the_plan_tints_the_stats_and_the_hero_explains_itself() -> None:
    assert "★" in JS and "plan: ${planned}" in JS
    assert "statCell(column, player, row)" in JS and "row.categoryScores[column.key]" in JS and "td.dim" in CSS
    assert "UNSEEN_RISK_SHOWN" in JS and "row.unseenRisk >= UNSEEN_RISK_SHOWN" in JS, "Gone only where the unseen picks matter"
    assert "whyNotTheTopScore(recommendation, plan)" in JS and "Current plan:" in JS and "Today's plan" not in JS
    assert "Odds the whole plan holds" not in JS and "Other strong plans" not in JS
    assert "analysis.bestAvailable" in JS and "are not planned" in JS
    assert "oddsAtColumn(row)" in JS and "analysis.laterPick" in JS
    assert "ArrowDown" in JS and "split(/\\s+/)" in JS


def test_the_roster_shows_slots_and_the_tab_and_saved_state_are_kept() -> None:
    assert "analysis.lineup.slots" in JS and "canAdd" in JS and "Eligible at:" not in JS
    assert "TAB_KEY" in JS and "showSaved('Saved', true)" in JS and 'id="saved-state"' in (WEB / "index.html").read_text()


def test_browser_copies_are_keyed_by_the_draft_file_not_only_the_address() -> None:
    assert "draftId = server.id" in JS
    for key in ("storageKey()", "syncKey()", "asideKey()"):
        assert key in JS
    assert "localStorage.getItem(STORAGE_KEY)" not in JS and "localStorage.setItem(STORAGE_KEY" not in JS
    assert "the draft file had none" in JS


def _blend(foreground: str, background: str, share: float) -> str:
    first = [int(foreground[i: i + 2], 16) for i in (1, 3, 5)]
    second = [int(background[i: i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(a * share + b * (1 - share)):02x}" for a, b in zip(first, second))


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_stays_readable_on_the_strongest_tint_of_a_table_cell(theme: str) -> None:
    tokens = _themes()[theme]
    for share in (0.30,):  # the most any tint reaches
        tinted = _blend(tokens["cool"], tokens["surface"], share)
        assert _contrast(tokens["ink"], tinted) >= WCAG_TEXT, f"ink on the strongest tint in {theme} mode"
        assert _contrast(tokens["ink"], _blend(tokens["cool"], tokens["hover"], share)) >= WCAG_TEXT


def test_green_means_only_mine_and_the_odds_and_stats_use_the_second_hue() -> None:
    tints = [line for line in JS.splitlines() if "color-mix" in line]
    assert tints and all("var(--cool)" in line and "var(--mine)" not in line for line in tints)
    assert ".meter .fill { height: 100%; background: var(--cool); }" in CSS
    assert "accent-color: var(--cool)" in CSS


def test_a_settings_change_after_the_first_pick_waits_for_a_confirmation() -> None:
    change = JS[JS.index("function settingChanged()"): JS.index("function applySettings()")]
    assert "state.picks.length === 0" in change and "setting-confirm" in change, "applies at once only before the first pick"
    assert JS.count("settingChanged") >= 6, "every settings control goes through the one gate"
    assert "onRuleChange" not in JS and "state.method = " not in JS[JS.index("function wireControls()"):]
    closing = JS[JS.index("function toggleSettings()"): JS.index("function whyNotTheTopScore")]
    assert "keepSettings()" in closing, "closing the panel keeps what was in use"
    assert 'id="setting-apply"' in (WEB / "index.html").read_text()


def test_the_small_colour_and_badge_fixes_stay() -> None:
    assert ".mode { padding: 3px 10px; border-radius: 999px; background: color-mix(in srgb, var(--cool)" in CSS
    assert ".log li button { color: var(--ink)" in CSS
    assert "container-type: inline-size" in CSS and "@container" in CSS
    assert "state.picks.length === 0 && serverVersion === 0" in JS
    assert 'title="Whether the draft is saved in the draft file"></div>' in (WEB / "index.html").read_text()
