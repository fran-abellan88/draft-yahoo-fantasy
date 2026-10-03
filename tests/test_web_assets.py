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


TOKEN = r"--([\w-]+):\s*(#[0-9a-fA-F]{6}|rgba\([^)]*\))\s*;"


def _tokens(block: str) -> Dict[str, str]:
    """The tokens of one block as written: a hex colour, or an rgba() that sits on top of whatever is behind it."""
    return dict(re.findall(TOKEN, block))


def _flatten(tokens: Dict[str, str]) -> Dict[str, str]:
    """Turn every rgba() token into the hex colour it shows over the card, so contrast can be measured."""
    flat: Dict[str, str] = {}
    for name, value in tokens.items():
        if value.startswith("rgba"):
            red, green, blue, alpha = (float(part) for part in re.findall(r"[\d.]+", value))
            base = tokens["surface"]
            channels = [round(alpha * c + (1 - alpha) * int(base[i : i + 2], 16)) for c, i in zip((red, green, blue), (1, 3, 5))]
            value = "#" + "".join(f"{c:02x}" for c in channels)
        flat[name] = value
    return flat


def _themes() -> Dict[str, Dict[str, str]]:
    light_block = re.search(r":root\s*\{(.*?)\n\}", CSS, re.S)
    dark_block = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', CSS, re.S)
    media_block = re.search(r'@media \(prefers-color-scheme: dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)\s*\{(.*?)\}', CSS, re.S)
    assert light_block and dark_block and media_block, "the colour tokens moved; update this test"
    light = _tokens(light_block.group(1))
    assert _tokens(media_block.group(1)) == _tokens(dark_block.group(1)), "the two copies of the dark tokens must stay equal"
    return {"light": _flatten(light), "dark": _flatten({**light, **_tokens(dark_block.group(1))})}


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
    ("muted", "raised", "table headers, labels inside a card"),
    ("ink", "raised", "inputs, league tables, buttons"),
    ("cool", "surface", "odds and ranks as text"),
    ("flag", "surface", "warnings as text"),
    ("danger", "surface", "errors as text"),
    ("flag", "flag-soft", "badges and the search note"),
    ("danger", "danger-soft", "the error banner"),
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


def test_the_page_shows_a_negative_gap_and_says_when_positions_decided_the_order() -> None:
    assert "byPositions" in JS and "gapLabel(alt.behind)" in JS
    assert re.search(r"alt\.behind >= TIE_POINTS \|\| alt\.byPositions", JS)  # such a line is worth showing
    assert "Ranked lower for positions, not score." in JS
    # "also plays" only when the recommended player lists more positions than the alternative
    assert "recommended.length > alternative.length && extra.length" in JS


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


def _block(media: str) -> str:
    """The text of one media query in the stylesheet, up to the next one."""
    start = CSS.index(f"@media {media}")
    end = CSS.find("@media", start + 1)
    return CSS[start:end if end != -1 else len(CSS)]


def test_standing_sits_in_the_rail_between_my_team_and_the_log() -> None:
    html = (WEB / "index.html").read_text()
    rail = html[html.index('<div class="rail">'):]
    assert rail.index('data-panel="team"') < rail.index('data-panel="standing"') < rail.index('data-panel="log"')
    wide = _block("(min-width: 2350px)")
    assert '"standing' not in wide and ".rail .seam-standing" in wide and "grid-row: 5 / 7" not in wide
    assert "min-height: 180px" in wide, "the log keeps room for the latest picks"


def test_the_plan_has_no_height_cap_from_1720_px_up() -> None:
    for media in ("(min-width: 2350px)", "(min-width: 1720px) and (max-width: 2349.98px)"):
        assert ".seam-plan { max-height: none; }" in _block(media), media
    assert "max-height: 45vh" in CSS, "below 1720 it still scrolls inside itself"


def test_from_1720_to_2349_my_team_standing_and_the_rest_share_one_tab_panel_so_no_panel_is_squeezed_to_nothing() -> None:
    block = _block("(min-width: 1720px) and (max-width: 2349.98px)")
    assert ".team, .seam-standing, .teams, .panel.log { grid-area: tabp; }" in block
    assert block.count('"rec table') == 2, "the recommendation spans the two rows beside the tab strip and its panel"
    assert '"plan table tabp"' in block


def test_the_tab_strip_keeps_a_valid_active_tab_when_the_window_changes_width() -> None:
    assert "window.addEventListener('resize', syncTabs)" in JS
    sync = JS[JS.index("function syncTabs"): JS.index("function wireTabs")]
    assert "visibleTabs()" in sync and "aria-selected" in sync


def test_the_last_pick_and_the_settings_summary_are_shown_in_the_page() -> None:
    html = (WEB / "index.html").read_text()
    for element in ('id="last-pick"', 'id="settings-summary"', 'id="settings-toggle"', 'id="tabs"', 'id="modes"'):
        assert element in html
    assert "renderTopBar();" in JS[JS.index("function render()"):]
    assert html.index('id="reset"') < html.index('id="settings"'), "Reset is in the top bar, where it can be seen"
    assert 'id="theme"' in html and "THEME_KEY" in JS


def test_the_page_shows_the_standing_and_the_14_teams_and_can_rehearse() -> None:
    html = (WEB / "index.html").read_text()
    for element in ('id="league"', 'id="profile"'):
        assert element in html
    assert 'id="rehearsal"' not in html, "a mock draft is its own page and file, never a button that turns the real draft automatic"
    assert 'href="/mock"' in html and 'href="/"' in html and "const API = MOCK ?" in JS
    assert "state.rehearsal = pool.rehearsal === true" in JS and "saved.rehearsal" not in JS
    render = JS[JS.index("function render()"):]
    assert "renderStanding();" in render and "renderLeague();" in render
    assert "API + '/autopick'" in JS and "'/api/" not in JS and "noise: true" in JS and "seed: state.seed + state.picks.length" in JS
    undo = JS[JS.index("function undo()"): JS.index("// ---------- rehearsal")]
    assert "state.rehearsal" in undo, "in a rehearsal Undo goes back to just before my last pick"
    after_render = JS[JS.index("fetchPredictions(requestId, body);\n  if (state.rehearsal"):][:300]
    assert "autoPlayFailed" in JS and "!autoPlayFailed" in after_render
    assert "seed: state.seed" in JS and "rehearsal: state.rehearsal" not in JS, "the mode is never saved with a draft"


def test_the_need_weights_are_a_setting_that_is_saved_requested_and_shown() -> None:
    assert 'id="needs"' in (WEB / "index.html").read_text()
    assert "needs: state.needs" in JS and "state.needs = saved.needs === true" in JS
    assert "analysis.needs" in JS and "Weights in use" in JS


def test_the_table_marks_the_plan_tints_the_stats_and_the_hero_explains_itself() -> None:
    assert "pick-tag" in JS and "plan: ${planned}" in JS
    assert "statCell(column, player, row)" in JS and "row.categoryScores[column.key]" in JS and "td.dim" in CSS
    assert "statLevel(" in JS and "background: var(--cool-strong)" in CSS, "a capsule only on strong stats, no fill on every cell"
    assert "UNSEEN_RISK_SHOWN" in JS and "row.unseenRisk >= UNSEEN_RISK_SHOWN" in JS, "Gone only where the unseen picks matter"
    assert "whyNotTheTopScore(recommendation, plan)" in JS and "You pick at ${recommendation.pick}" in JS and "Today's plan" not in JS
    assert "Odds the whole plan holds" not in JS and "Other strong plans" not in JS
    assert "analysis.bestAvailable" in JS and "are not planned" in JS
    assert "oddsAtColumn(row)" in JS and "analysis.laterPick" in JS
    assert "ArrowDown" in JS and "split(/\\s+/)" in JS


def test_the_roster_shows_slots_and_the_tab_and_saved_state_are_kept() -> None:
    assert "lineup.slots" in JS and "rosterRows(entries, analysis.lineup" in JS and "canAdd" in JS and "Eligible at:" not in JS
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
    assert tints and all(("var(--cool)" in line or "var(--score)" in line) and "var(--mine)" not in line for line in tints)
    assert ".ring-fill { fill: none; stroke: var(--cool);" in CSS
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
    assert ".mode " not in CSS and ".modes a[aria-current" in CSS, "the draft switch does not use green"
    assert ".log li button { color: var(--ink)" in CSS
    assert "container-type: inline-size" in CSS and "@container" in CSS
    assert "state.picks.length === 0 && serverVersion === 0" in JS
    assert 'title="Whether the draft is saved in the draft file"></div>' in (WEB / "index.html").read_text()


def test_the_review_fixes_of_step_8_stay() -> None:
    assert "showSaved('Saved', true); // the file is what was loaded" in JS, "a reloaded draft says it is saved"
    assert "keepSettings(); // a pending change was worded for the draft as it was" in JS[JS.index("async function refresh()"):][:200]
    assert "server.state)" in JS and "a scaled team usually drops a little when it picks" in JS
    assert '<div class="rail">' in (WEB / "index.html").read_text() and ".rail { display: contents; }" in CSS


def test_the_planner_projection_is_asked_for_apart_from_the_analysis_and_shown_with_so_far() -> None:
    refresh = JS[JS.index("async function refresh()"): JS.index("function scheduleRefresh()")]
    assert "fetchPlannerLeague(requestId, body);" in refresh
    assert refresh.index("render();") < refresh.index("fetchPlannerLeague"), "the analysis never waits"
    fetch_league = JS[JS.index("async function fetchPlannerLeague"): JS.index("function scheduleRefresh()")]
    assert "API + '/league'" in fetch_league and "requestId !== latestRequest" in fetch_league, "an answer for an older log is dropped"
    assert "plannerKeys !== keysAsked" in fetch_league, "a table for other categories is never shown"
    league = JS[JS.index("function renderLeague()"): JS.index("// A gone entry back to an unseen pick")]
    assert "h3', {}, 'Projected'" in league and "h3', {}, 'So far'" in league, "both tables at once, no switch between them"
    assert "ADP order" in league and "Same planner" in league and "projectedTable()" in JS[JS.index("function renderStanding()"):]
    assert "minmax(400px, 400fr) minmax(900px, 1130fr) minmax(340px, 340fr) minmax(500px, 500fr)" in CSS
    assert ".league-table td.left { max-width" in CSS


def test_the_theme_follows_the_system_unless_chosen_and_is_set_before_the_first_paint() -> None:
    html = (WEB / "index.html").read_text()
    assert html.index("draft-assistant-theme") < html.index('href="/style.css"'), "applied before the stylesheet paints"
    assert ':root[data-theme="light"] { color-scheme: light; }' in CSS and 'color-scheme: dark;' in CSS
    assert ':root:not([data-theme="light"])' in CSS, "the system's dark scheme does not override a chosen light theme"
    assert "THEMES = ['auto', 'light', 'dark']" in JS and "delete document.documentElement.dataset.theme" in JS


def test_the_inline_theme_script_leaves_no_global_that_app_js_could_clash_with() -> None:
    head = (WEB / "index.html").read_text().split("</head>")[0]
    inline = head[head.index("<script>"): head.index("</script>")]
    assert "(function ()" in inline and "var theme" not in inline, "a global `var theme` once stopped app.js from loading"


def test_a_failed_projection_never_leaves_an_older_table_and_my_score_is_shown_under_both_projections() -> None:
    fetch_league = JS[JS.index("async function fetchPlannerLeague"): JS.index("function scheduleRefresh()")]
    assert fetch_league.count("plannerLeague = null") >= 3, "other categories, a refused answer and a failed request all clear it"
    league = JS[JS.index("function renderLeague()"): JS.index("// A gone entry back to an unseen pick")]
    assert "if the others draft like you" in league and "if they draft by ADP" in league
    assert "Your team in this projection" in league and "projected.myPlayers" in league


def test_the_pick_predictions_are_real_draft_only_asked_apart_and_tied_to_the_log_they_were_made_for() -> None:
    html = (WEB / "index.html").read_text()
    for element in ('id="predict-line"', 'id="prediction-summary"', 'id="managers"'):
        assert element in html
    fetch_predictions = JS[JS.index("async function fetchPredictions"): JS.index("const predictionRows")]
    assert "if (state.rehearsal) return;" in fetch_predictions and "API + '/predict'" in fetch_predictions
    assert "requestId !== latestRequest" in fetch_predictions
    refresh = JS[JS.index("async function refresh()"): JS.index("// What each other team should have picked")]
    assert refresh.index("render();") < refresh.index("fetchPredictions(requestId, body);"), "the analysis never waits"
    assert "predictionsFor === picksSignature()" in JS, "a stale answer is never shown for another log"
    assert "item.pick === entry.pick && item.id === entry.id" in JS, "a log row is marked only by the pick it was computed for"
    assert "not a mistake" in JS


def test_the_columns_grow_together_the_table_starts_on_adp_and_the_score_has_its_own_colour_map() -> None:
    columns = re.findall(r"grid-template-columns:([^;]*);", CSS)
    assert columns and not any(re.search(r"(?<![\w(,] )\b(?:380|400|420|540)px\s*(?:minmax|;|$)", value) for value in columns)
    assert "sort: { key: 'adp', direction: 1 }" in JS
    score_tint = JS[JS.index("const scoreFill"): JS.index("// A stat marked by")]
    assert "scoreTint(row)" in JS and "var(--score)" in score_tint and "var(--cool)" not in score_tint
    for kind in ("planner", "adp", "both"):
        assert f".predict-mark.{kind}" in CSS
    assert "'both'" in JS


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_ink_stays_readable_on_the_score_map_and_the_log_tags(theme: str) -> None:
    tokens = _themes()[theme]
    # the strongest each fill reaches, and what it can sit on: the Score cell on a hovered row, a tag only in the log
    for name, share, bases in (("score", 0.40, ("surface", "hover")), ("tag-planner", 0.42, ("surface",)), ("tag-adp", 0.42, ("surface",))):
        for base in bases:
            ratio = _contrast(tokens["ink"], _blend(tokens[name], tokens[base], share))
            assert ratio >= WCAG_TEXT, f"ink on the strongest {name} fill over {base} in {theme} mode is {ratio:.2f}:1"
    assert _contrast(tokens["muted"], _blend(tokens["cool"], tokens["surface"], 0.22)) >= 4.0, "dim text on the strongest stat tint"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_panels_stand_apart_from_the_page_and_the_inside_of_a_card_from_the_card(theme: str) -> None:
    tokens = _themes()[theme]
    assert _contrast(tokens["paper"], tokens["surface"]) >= 1.15, "a card must be visible against the page"
    assert _contrast(tokens["surface"], tokens["raised"]) >= 1.07, "a table header or input must be visible inside a card"
    assert _contrast(tokens["line"], tokens["surface"]) >= 1.4, "hairlines must be visible"
    assert "#ffffff" not in {value.lower() for key, value in tokens.items() if key in ("paper", "surface", "raised")}, "no pure white"


def test_every_panel_is_a_card() -> None:
    cards = re.search(r"(\.team, [^{]*)\{([^}]*)\}", CSS)
    assert cards and all(name in cards.group(1) for name in (".panel.log", ".seam-standing", ".teams"))
    assert "background: var(--surface)" in cards.group(2) and "border-radius" in cards.group(2)


def test_a_notice_is_not_dressed_as_an_error_and_hidden_log_buttons_do_not_take_room() -> None:
    assert "classList.add('notice')" in JS and "classList.remove('notice')" in JS
    assert ".banner.notice { background: var(--raised)" in CSS
    assert ".row-actions { position: absolute;" in CSS, "out of the flow: hidden buttons once made rows wrap"
    assert "h('span', { class: 'row-actions' }, ...buttons)" in JS
    assert CSS.count("Follow the system unless the theme button chose one") == 1


def test_the_score_column_defaults_to_a_bar_of_the_gap_to_the_best_player_left_and_offers_two_colour_maps() -> None:
    html = (WEB / "index.html").read_text()
    assert html.count('name="scorestyle"') == 3 and 'value="bar" checked' in html
    assert "let scoreStyle = 'bar';" in JS and "SCORE_STYLES = ['bar', 'rank', 'range']" in JS
    tint = JS[JS.index("function scoreTint(row)"): JS.index("function scoreTitle")]
    assert "--bar:" in tint and "::after" in CSS and "scoreBarShare(score, scoreAnchors)" in tint and "SCORE_BAR_SPAN" not in JS
    assert "row.rank <= limit" in tint, "colour by rank uses the rank among the players left, not the score"
    assert "localStorage.setItem(SCORE_STYLE_KEY" in JS and "scorestyle" in JS[JS.index("function wireControls()"):], "a browser preference"
    assert "behind the best score left" in JS


def test_the_second_thing_on_the_clock_is_in_the_recommendation_box_and_the_odds_column_marks_only_the_risky() -> None:
    html = (WEB / "index.html").read_text()
    assert 'id="alternatives"' not in html
    hero = JS[JS.index("function renderHero()"): JS.index("function meter(")]
    assert "alternativesBlock()" in hero
    block = JS[JS.index("function alternativesBlock()"): JS.index("function renderPlan()")]
    assert "analysis.alternativesMode === 'gone'" in block and "alternativesWorthShowing()" in block
    odds = JS[JS.index("function oddsCell"): JS.index("// The Score column")]
    assert "color-mix" not in odds and "wont-last" in odds and "value < 0.5" in odds
    assert "td.wont-last { color: var(--flag)" in CSS


def test_the_score_column_is_wide_enough_for_its_bar_and_the_other_cells_pay_for_it() -> None:
    assert "#pool th:nth-child(3), #pool td.score-cell { min-width: 100px; }" in CSS
    # The numbers and the Score bar grow with the table panel (cqw), so a wide table spreads its slack instead of leaving it in Player
    assert ".tablecol { container-type: inline-size; }" in CSS
    assert re.search(r"#pool th:nth-child\(3\), #pool td\.score-cell \{ min-width: clamp\(100px, calc\(15\.2cqw - 54px\), 200px\); \}", CSS)
    assert "#pool td { padding-inline: clamp(3px, calc(1.5cqw - 13.5px), 18px); }" in CSS
    assert "#pool td { padding: 4px 5px; }" in CSS and "#pool th button { padding: 9px 5px; }" in CSS
    columns = re.findall(r"\{ key: '(\w+)', label", JS[JS.index("const POOL_COLUMNS"): JS.index("function buildPoolHead")])
    assert columns[2] == "score", "the width rule names the third column: keep Score third"


def test_the_font_stack_starts_with_a_family_chrome_knows() -> None:
    # ui-sans-serif is ignored by Chrome, which then fell through to Avenir Next
    stack = re.search(r"--font:\s*([^;]+);", CSS)
    assert stack and stack.group(1).startswith("system-ui"), "the font stack must start with system-ui"


def test_taken_is_never_used_as_a_text_colour() -> None:
    assert not re.search(r"(?<![\w-])color:\s*var\(--taken\)", CSS), "--taken is for bars and outlines, its contrast is too low for text"


def test_midnight_has_the_roles_the_later_steps_need() -> None:
    dark = _themes()["dark"]
    for name in ("selected", "cool-strong", "cool-mid"):
        assert name in dark, f"--{name} is missing from the dark tokens"
    assert dark["paper"] == "#000000" and dark["surface"] == "#1c1c1e"
    assert _contrast(dark["ink"], dark["surface"]) >= 15
    assert _contrast(dark["muted"], dark["surface"]) >= 7


def test_a_badge_never_disappears_from_the_player_table() -> None:
    # The name and the meta line give way (with an ellipsis) before a badge does, and the Player column takes what the numbers leave
    assert "td.player { width: 99%; max-width: 0; }" in CSS
    assert re.search(r"\.player-line \.notes \{[^}]*flex: none", CSS)
    assert re.search(r"\.player-line \.meta \{[^}]*text-overflow: ellipsis", CSS)


def test_the_team_name_is_the_elastic_column_of_the_league_tables_and_projected_has_no_count() -> None:
    assert re.search(r"\.league-table td\.left \{[^}]*width: 99%; max-width: 0", CSS)
    assert "leagueTable(projected, keys, labels, false," in JS, "every projected team has the same number of players"


def test_the_top_bar_roster_and_log_use_the_midnight_shapes() -> None:
    assert "class: 'clock-pick'" in JS and ".clock-pick { display: block; font-size: 22px" in CSS
    assert re.search(r"\.snake \.cell \{[^}]*width: 25px[^}]*border-radius: 50%", CSS), "the snake is a row of 25 px circles"
    switch = re.search(r"\.modes a\[aria-current=\"page\"\] \{[^}]*background: var\(--selected\)", CSS)
    assert switch, "the draft switch is a segmented control"
    assert re.search(r"\.roster \.slot \.pick \{[^}]*width: 40px; height: 28px; border-radius: 9px", CSS), "slot chips"
    assert ".team-name::before" in CSS, "the log joins its details with a middle dot"


def test_the_category_bars_show_the_stat_and_standing_names_its_categories() -> None:
    bars = JS[JS.index("function categoryBars(row)"): JS.index("// A ring that fills")]
    assert "player.stats[category.key]" in bars, "the stat on top of each bar"
    assert "among the players in the pool" in bars, "the 0 to 100 score is in the title"
    assert "class: 'tile-names'" in JS, "the categories are named in the tile, not only in its title"
    meta_rule = re.search(r"\.player-line \.meta \{[^}]*flex: 0 1000 auto", CSS)
    assert meta_rule, "the meta line gives way completely before the name"


def test_the_mock_draft_is_marked_beside_the_pick_number() -> None:
    clock = JS[JS.index("const clockText"): JS.index("if (clock.draftComplete)")]
    assert "state.rehearsal" in clock and "class: 'mock-tag'" in clock, "a mock draft must never look like the real one"
    assert re.search(r"\.mock-tag \{[^}]*var\(--flag-soft\)[^}]*var\(--flag\)", CSS)
    assert re.search(r"\.tile \.tile-names \{[^}]*font-size: 12px", CSS), "no important text under 12 px"


POSITION_GROUPS = ["guard", "forward", "center"]  # Yahoo's three colours: PG/SG, SF/PF, C
POSITION_BACKGROUNDS = ["surface", "raised", "hover", "mine-soft", "selected"]  # cards, inputs, hovered, recommended and viewed rows
ROLE_TOKENS = ["mine", "cool", "flag", "danger", "tag-adp", "tag-planner", "focus", "score", "ink", "muted"]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("group", POSITION_GROUPS)
@pytest.mark.parametrize("background", POSITION_BACKGROUNDS)
def test_position_colours_are_readable_on_every_surface_a_name_sits_on(theme: str, group: str, background: str) -> None:
    tokens = _themes()[theme]
    ratio = _contrast(tokens[f"pos-{group}"], tokens[background])
    assert ratio >= WCAG_TEXT, f"pos-{group} on {background} is {ratio:.2f}:1 in {theme} mode"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_a_position_colour_never_repeats_another_group_or_a_role(theme: str) -> None:
    tokens = _themes()[theme]
    groups = [tokens[f"pos-{group}"] for group in POSITION_GROUPS]
    assert len(set(groups)) == len(groups), "two groups share a colour"
    roles = {tokens[role] for role in ROLE_TOKENS}
    assert not set(groups) & roles, "a position colour equals a role colour (mine, cool, flag, danger, tags...)"


def test_every_place_that_shows_positions_or_a_name_uses_the_group_colours() -> None:
    assert "function positionsNode(" in JS and "'data-grp': POSITION_GROUP[position]" in JS
    assert "const POSITION_GROUP = { PG: 'guard', SG: 'guard', SF: 'forward', PF: 'forward', C: 'center' };" in JS
    detail = JS[JS.index("const detailOf"): JS.index("};", JS.index("const detailOf"))]
    assert "positionsNode(player.positions)" in detail
    assert ".positions.join('/')" not in JS, "positions are shown as plain text somewhere"
    for group in POSITION_GROUPS:
        assert f'[data-grp="{group}"] {{ color: var(--pos-{group}); }}' in CSS
    assert 'chips button[data-position="PG"]:not([aria-pressed="true"]), .chips button[data-position="SG"]' in CSS
    # A name takes the colour of his first listed position, in the table and in every card, row and list
    assert "const groupOf = (id) => POSITION_GROUP[playerById.get(id).positions[0]];" in JS
    assert "'data-grp': groupOf(player.id)" in JS  # the name in the main table
    places = ("h('p', { class: 'name' }, nameNode(recommendation.id))", "h('strong', {}, nameNode(alt.id))")
    for place in places + ("h('strong', {}, nameNode(step.id))", "nameNode(cardId)"):
        assert place in JS, place
    assert "tr.recommended td.player strong { color: var(--mine); }" not in CSS  # the row tint marks it; the name keeps its position colour


def test_the_roster_panel_can_show_any_team() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for element in ('id="roster-team"', 'id="roster-back"', 'id="roster-basis"', 'id="roster-title"', 'id="roster-note"'):
        assert element in html, element
    assert 'data-basis="sofar"' in html and 'data-basis="projected"' in html
    # One component draws my roster and the others', so they cannot drift apart
    assert JS.count("rosterRows(") >= 3 and "function rosterRows(" in JS
    # A team name in either league table is a real button that opens that team, never a click handler on the row
    assert "class: 'team-link'" in JS and "onclick: () => viewTeam(team.slot, basis)" in JS
    assert "leagueTable(projected, keys, labels, false, 'projected')" in JS and "leagueTable(now, keys, labels, true, 'sofar')" in JS


def test_the_roster_panel_goes_back_to_mine_when_i_log_my_own_pick_and_not_before() -> None:
    assert "if (analysis.roster.length > lastMineCount) viewSlot = null;" in JS
    assert JS.index("lastMineCount = analysis.roster.length;") < JS.index("  renderRoster();\n  renderStanding();")
    other = JS[JS.index("function renderOtherRoster"): JS.index("const ordinal = (value)")]
    assert "viewSlot = null;" not in other  # no switching while others pick


def test_another_teams_roster_never_uses_the_colour_that_means_yours() -> None:
    assert ".roster.other .slot.filled .pick { background: var(--selected);" in CSS
    assert "dashed var(--taken)" in CSS  # a projected player has an outlined tile
    assert ".league-table tr.selected-row td { background: var(--selected); }" in CSS
    assert "selected-row" not in re.search(r"\.mine-row[^\n]*", CSS).group(0)


def test_a_click_on_a_players_name_opens_his_card_and_only_the_draft_button_drafts() -> None:
    row = JS[JS.index("return h(\n      'tr',\n      {\n        tabindex: '0',"): JS.index("cells,\n    );", JS.index("tabindex: '0'"))]
    assert "onclick" not in row, "the row itself must not draft"
    assert "showCard(player.id)" in row and "event.target === event.currentTarget" in row  # Enter on the row shows the card
    assert "class: 'name-link'" in JS and "onclick: () => showCard(player.id)" in JS
    assert "function draftButton(" in JS and "onclick: () => rowPicked(player.id)" in JS
    assert "choosing ? 'Choose' : 'Draft'" in JS  # while choosing a player for an earlier pick the button says so
    assert "press Choose beside a player" in JS


def test_the_player_card_closes_when_it_should_and_not_before() -> None:
    assert "function renderPlayerCard(" in JS and "categoryBars(row)" in JS[JS.index("function renderPlayerCard("):]
    assert "if (cardId !== null && !poolRowById.has(cardId)) cardId = null;" in JS  # drafted: gone from the pool
    assert "if (analysis.clock.isMine && !lastIsMine) cardId = null;" in JS  # my turn: the recommendation comes back
    assert "closeCard();" in JS[JS.index("if (event.key === 'Escape')"):][:80]


def test_the_header_keeps_its_height_while_the_prediction_is_on_its_way() -> None:
    body = JS[JS.index("function renderPredictions()"): JS.index("if (state.rehearsal || !current")]
    assert "line.classList.add('empty')" in body and "line.classList.remove('empty')" in body
    assert body.count("line.hidden = true") == 1 and "if (state.rehearsal) {\n    line.hidden = true;" in body  # only the mock hides it
    assert ".topbar .predict-line.empty { visibility: hidden; }" in CSS and ".topbar .predict-line { min-height: 1.4em; }" in CSS


def test_the_league_tables_keep_a_width_for_the_category_columns() -> None:
    assert ".teams { container-type: inline-size; }" in CSS
    assert "#league .league-table .lcat { min-width: clamp(0px, calc(12cqw - 33px), 64px); }" in CSS
    # `cat` is the category bar of the recommendation box (display: grid): a table cell must not share the name
    assert "class: 'lcat'" in JS and "class: 'cat'," not in JS[JS.index("function leagueCell("): JS.index("function leagueTable(")]


def test_the_main_table_lists_the_categories_in_the_order_of_every_other_table() -> None:
    from fantasy_draft.categories import CATEGORIES

    block = JS[JS.index("const STAT_COLUMNS = ["): JS.index("];", JS.index("const STAT_COLUMNS = ["))]
    assert re.findall(r"key: '(\w+)'", block) == list(CATEGORIES), "the table, the league tables and the bars share one order"
    assert list(CATEGORIES)[:2] == ["fg_pct", "ft_pct"]  # the percentages come first


def test_the_page_shows_why_yahoo_disagrees_and_offers_the_punt_through_the_settings_flow() -> None:
    assert "function disagreementBlock" in JS and "function marketTieNote" in JS
    punt = JS[JS.index("function puntCategory"): JS.index("function whyNotTheTopScore")]
    assert "settingChanged()" in punt and "toggleSettings()" in punt, "after the first pick the confirmation is in the settings panel"
    assert "puntCategory(category.key)" in JS


def test_the_table_has_a_sortable_vs_yahoo_column_beside_xrank() -> None:
    columns = JS[JS.index("const POOL_COLUMNS"): JS.index("function buildPoolHead")]
    assert columns.index("key: 'xrank'") < columns.index("key: 'vsyahoo'") < columns.index("key: 'gp'")
    assert "key === 'vsyahoo'" in JS and "updateYahooGap()" in JS


def test_signed_keeps_its_one_decimal_for_the_deltas_and_the_vs_yahoo_column_has_its_own_whole_number_label() -> None:
    assert "const signed = (value) => `${value > 0 ? '+' : ''}${value.toFixed(1)}`;" in JS
    assert "const placesLabel = (value) =>" in JS and "placesLabel(yahooGap.get(player.id))" in JS
    assert JS.count("const signed =") == 1 and JS.count("const placesLabel =") == 1


def test_a_click_outside_the_settings_closes_them_and_the_punt_opens_them_after_the_click_has_finished() -> None:
    wire = JS[JS.index("function wireControls"):]
    click = wire[wire.index("document.addEventListener('click'"): wire.index("$('outside')")]
    assert "$('settings').hidden" in click and "composedPath()" in click and "$('settings-toggle')" in click and "toggleSettings()" in click
    punt = JS[JS.index("function puntCategory"): JS.index("function whyNotTheTopScore")]
    assert "setTimeout(" in punt, "opened at once, the same click would close it again"


def test_the_table_shows_the_score_of_the_other_method_in_a_sortable_column_after_score() -> None:
    columns = JS[JS.index("const POOL_COLUMNS"): JS.index("function buildPoolHead")]
    assert columns.index("key: 'score'") < columns.index("key: 'altscore'") < columns.index("key: 'availability'")
    assert "key === 'altscore'" in JS and "analysis.altMethod" in JS and "row.altScore" in JS
