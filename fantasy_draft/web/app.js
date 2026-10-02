'use strict';

// Draft assistant front end. The server holds no state: this page keeps the ordered list of picks
// (also in localStorage, so a refresh mid-draft loses nothing) and asks the server what to do next.

// Browser copies are keyed by the draft file's id (from the server), not only by this address: a mock draft and the real
// draft can sit on one port and must never share a copy
// The real draft is served at / and a mock draft at /mock (its own file, automatic picks); the routes follow the address
const MOCK = location.pathname === '/mock' || location.pathname.startsWith('/mock/');
const API = MOCK ? '/mock/api' : '/api';
const STORAGE_KEY = 'draft-assistant-v2';
const ASIDE_KEY = 'draft-assistant-unconfirmed'; // a browser copy the file replaced, kept so nothing is lost
const THEME_KEY = 'draft-assistant-theme'; // 'light', 'dark' or absent (follow the system): a per-browser convenience
const TAB_KEY = 'draft-assistant-tab'; // the tab last open, a per-browser convenience
const SYNC_KEY = 'draft-assistant-sync'; // which file version the browser copy is based on, and whether the server has it
let draftId = ''; // set from /api/draft before anything is read or written
const storageKey = () => `${STORAGE_KEY}:${draftId}`;
const syncKey = () => `${SYNC_KEY}:${draftId}`;
const asideKey = () => `${ASIDE_KEY}:${draftId}`;
const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
const STAT_COLUMNS = [
  { key: 'pts', label: 'PTS', kind: 'number' },
  { key: 'reb', label: 'REB', kind: 'number' },
  { key: 'ast', label: 'AST', kind: 'number' },
  { key: '3ptm', label: '3PTM', kind: 'number' },
  { key: 'st', label: 'ST', kind: 'number' },
  { key: 'blk', label: 'BLK', kind: 'number' },
  { key: 'to', label: 'TO', kind: 'number' },
  { key: 'fg_pct', label: 'FG%', kind: 'rate' },
  { key: 'ft_pct', label: 'FT%', kind: 'rate' },
];
const STATUS_TITLES = { Q: 'Questionable', P: 'Probable', O: 'Out', GTD: 'Game-time decision', INJ: 'Injured', NA: 'Not active' };
const DEFAULT_RULE = { type: 'probability', baseSd: 2, sdPerAdp: 0.2, threshold: 0.5, slack: 3 };

const state = {
  picks: [],
  history: [], // the actions Undo reverts, newest last (see logic.js)
  needs: false, // weight the categories by team need (an option, off by default)
  rehearsal: false, // set from the server (the draft served at /mock), never from a saved draft
  seed: 0, // makes one rehearsal repeatable and the next one different
  categories: [],
  gamesAdjusted: true,
  method: 'uncapped',
  rule: { ...DEFAULT_RULE },
  search: '',
  position: 'ALL',
  sort: { key: 'rank', direction: 1 },
};
const playerById = new Map();
let pool = null;
let analysis = null;
let poolRowById = new Map();
let latestRequest = 0;
let resetArmed = false;
let debounceTimer = null;

const $ = (id) => document.getElementById(id);

// ---------- small DOM helper ----------
function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (value === false || value === null || value === undefined) continue;
    if (name === 'class') node.className = value;
    else if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// Replace a node's children, skipping null/false entries (replaceChildren would write the word "null")
function put(node, ...children) {
  node.replaceChildren(...children.flat().filter((child) => child !== null && child !== undefined && child !== false));
}

// ---------- formatting ----------
const pct = (value) => `${Math.round(value * 100)}%`;
const oneDecimal = (value) => (value === null || value === undefined ? '-' : value.toFixed(1));
const formatRate = (value) => (value === null || value === undefined ? '-' : value.toFixed(3).replace(/^0/, ''));
const signed = (value) => `${value > 0 ? '+' : ''}${value.toFixed(1)}`;
const teamName = (slot) => (pool.league.teamNames ? pool.league.teamNames[slot - 1] : `Slot ${slot}`);
const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`;
const nameOf = (id) => playerById.get(id).name;
const detailOf = (id) => {
  const player = playerById.get(id);
  return `${player.team}, ${player.positions.join('/')}`;
};

// ---------- persistence ----------
// The draft is kept in two places: a file next to the project, written by the server (it survives a closed browser
// and a change of port), and this browser's storage as a backup for when the server cannot be reached.
let serverVersion = 0; // the version of the file this page last saw
let draftRefused = false; // the saved draft could not be loaded: it is kept as it is until Reset
let serverSaveBlocked = false; // another window saved first: this one must reload before it saves
let serverSaving = false;
let serverSaveAgain = false;

function writeSync(confirmed) {
  try {
    localStorage.setItem(syncKey(), JSON.stringify({ basedOn: serverVersion, confirmed }));
  } catch (error) {
    // see saveState
  }
}

function readStored(key) {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch (error) {
    return null;
  }
}

function currentSavedState() {
  return { version: 2, picks: state.picks, history: state.history, seed: state.seed, needs: state.needs, categories: state.categories, gamesAdjusted: state.gamesAdjusted, method: state.method, rule: state.rule };
}

function saveState() {
  if (draftRefused) return; // never write over a draft this page could not read
  try {
    localStorage.setItem(storageKey(), JSON.stringify(currentSavedState()));
    writeSync(false);
  } catch (error) {
    // Private mode or blocked storage: the draft still works, it just will not survive a refresh
  }
  saveToServer();
}

// One save at a time, always of the latest state, each naming the version the last one produced
function showSaved(text, ok) {
  const badge = $('saved-state');
  // A new draft with nothing logged has nothing to be saved: say nothing rather than "Saved"
  badge.textContent = text === 'Saved' && state.picks.length === 0 && serverVersion === 0 ? '' : text;
  badge.classList.toggle('bad', !ok);
}

async function saveToServer() {
  if (serverSaveBlocked) {
    showSaved('Not saved: reload', false);
    return;
  }
  if (serverSaving) {
    serverSaveAgain = true;
    return;
  }
  serverSaving = true;
  showSaved('Saving', true);
  try {
    do {
      serverSaveAgain = false;
      const response = await fetch(API + '/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ baseVersion: serverVersion, state: currentSavedState() }),
      });
      const data = await response.json();
      if (response.status === 409) {
        serverSaveBlocked = true;
        showError(data.error, false, true);
        showSaved('Not saved: reload', false);
        return;
      }
      if (!response.ok) {
        showError(`The draft could not be saved on disk: ${data.error}. It is still kept in this browser.`);
        showSaved('Not saved on disk', false);
        return;
      }
      serverVersion = data.version;
      writeSync(!serverSaveAgain); // confirmed only if nothing newer is waiting; either way based on this version
      if (!serverSaveAgain) showSaved('Saved', true);
    } while (serverSaveAgain);
  } catch (error) {
    showError('The draft could not be saved on disk because the server cannot be reached. It is still kept in this browser.');
    showSaved('Not saved on disk', false);
  } finally {
    serverSaving = false;
  }
}

// What the server has saved: {version, state, problem}. A failed read is an error like a failed read of the pool: the
// page stops, because starting without knowing the file's version would later overwrite it.
async function loadServerDraft() {
  const response = await fetch(API + '/draft');
  if (!response.ok) throw new Error(`the server answered ${response.status}`);
  return response.json();
}

function restoreState(fromServer) {
  let saved = fromServer;
  if (!saved) {
    try {
      saved = pickSavedState(JSON.parse(localStorage.getItem(storageKey())), null);
    } catch (error) {
      saved = null;
    }
  }
  const allKeys = pool.categories.map((category) => category.key);
  state.categories = allKeys;
  if (!saved || typeof saved !== 'object') return;
  const picks = normalizePicks(saved.picks, new Set(playerById.keys()), pool.myPicks);
  if (picks === null) {
    // Not replaced by an empty draft: nothing is saved until the user chooses Reset
    draftRefused = true;
    showError('The saved draft could not be loaded (a pick is unknown or in a place the draft does not allow). It is kept as it is. Reset starts a new draft.', false, true);
  }
  state.picks = picks || [];
  state.history = sanitizeHistory(saved.history, state.picks);
  state.needs = saved.needs === true;
  state.seed = Number.isInteger(saved.seed) ? saved.seed : 0;
  if (Array.isArray(saved.categories) && saved.categories.length > 0 && saved.categories.every((key) => allKeys.includes(key))) {
    state.categories = allKeys.filter((key) => saved.categories.includes(key));
  }
  if (typeof saved.gamesAdjusted === 'boolean') state.gamesAdjusted = saved.gamesAdjusted;
  if (saved.method === 'capped' || saved.method === 'uncapped') state.method = saved.method;
  // A saved value outside the allowed range would be refused by the server on every request, so it is put back in range
  if (saved.rule && typeof saved.rule === 'object') state.rule = sanitizeRule({ ...DEFAULT_RULE, ...saved.rule }, pool.ruleLimits);
}

// ---------- talking to the server ----------
function ruleForRequest() {
  const rule = state.rule;
  return rule.type === 'window'
    ? { type: 'window', slack: rule.slack }
    : { type: 'probability', baseSd: rule.baseSd, sdPerAdp: rule.sdPerAdp, threshold: rule.threshold };
}

// A sticky message is about the saved draft, not about one request: a successful analysis must not clear it
let stickyError = false;

function showError(message, retryable = false, sticky = false) {
  if (stickyError && !sticky) return; // an ordinary error must not replace a message about the saved draft
  stickyError = sticky;
  $('error-text').textContent = message;
  $('error-retry').hidden = !retryable;
  $('error-dismiss').hidden = true;
  $('error').hidden = false;
}

// Something to know rather than a failure: stays until dismissed
function showNotice(message) {
  showError(message, false, true);
  $('error-dismiss').hidden = false;
}

function hideError(force = false) {
  if (stickyError && !force) return;
  stickyError = false;
  $('error').hidden = true;
}

// A failed request leaves the page showing the last answer it had, so picks logged since then are marked until
// a request succeeds. Only a network failure is retried on its own; a rejected request would fail the same way again.
const NETWORK_RETRIES = 2;
const RETRY_DELAY_MS = 700;
let refreshFailed = false;

function markRefreshFailed() {
  refreshFailed = true;
  if (analysis) renderPool();
}

// Past this long the plan and recommendation are dimmed and a pick just logged is marked "Logging", so a slow reply
// is not mistaken for a frozen page. The user is looking at the table, so the row has to say it, not only the hero.
const BUSY_AFTER_MS = 200;
let busyTimer = null;
let busyShown = false;

function showBusy() {
  busyShown = true;
  $('app').classList.add('busy');
  if (analysis) renderPool();
}

function setBusy(busy) {
  clearTimeout(busyTimer);
  busyTimer = busy ? setTimeout(showBusy, BUSY_AFTER_MS) : null;
  if (!busy) {
    busyShown = false;
    $('app').classList.remove('busy');
  }
}

async function refresh() {
  if (!$('setting-confirm').hidden) keepSettings(); // a pending change was worded for the draft as it was
  editing = null; // an open edit was built from the log as it was
  choosing = null;
  const requestId = ++latestRequest;
  setBusy(true);
  const body = JSON.stringify({ categories: state.categories, picks: state.picks, rule: ruleForRequest(), gamesAdjusted: state.gamesAdjusted, method: state.method, needs: state.needs });
  let response = null;
  for (let attempt = 0; attempt <= NETWORK_RETRIES && response === null; attempt += 1) {
    if (attempt > 0) {
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
      if (requestId !== latestRequest) return;
    }
    try {
      response = await fetch(API + '/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
    } catch (error) {
      response = null;
    }
  }
  if (response === null) {
    if (requestId !== latestRequest) return;
    setBusy(false);
    markRefreshFailed();
    showError("Can't reach the draft server. Your picks are saved. Check that run_dashboard.py is still running.", true);
    return;
  }
  let data;
  try {
    data = await response.json();
  } catch (error) {
    data = { error: 'The server sent a reply this page cannot read.' };
  }
  if (requestId !== latestRequest) return; // a newer request has already replaced this one
  setBusy(false);
  if (!response.ok) {
    markRefreshFailed();
    showError(data.error || 'The server could not handle that request.', response.status >= 500);
    return;
  }
  hideError();
  refreshFailed = false;
  analysis = data;
  poolRowById = new Map(data.pool.map((row) => [row.id, row]));
  render();
  fetchPlannerLeague(requestId, body);
  if (state.rehearsal && !rehearsing && !autoPlayFailed && !data.clock.isMine && !data.clock.draftComplete) autoPlayOthers();
}

// The league projected with every team completed by the same planner. It takes longer than the analysis (up to a few
// seconds early in the draft), so it is asked for apart from it and the recommendation never waits for it. Until it
// arrives the table shows the quick ADP projection, and a result for an older log or other categories is dropped.
async function fetchPlannerLeague(requestId, body) {
  const keysAsked = JSON.stringify(state.categories);
  if (plannerKeys !== keysAsked) plannerLeague = null; // other categories: the old table has other columns
  plannerPending = true;
  plannerFailed = false;
  renderLeague();
  try {
    const response = await fetch(API + '/league', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
    const data = await response.json();
    if (requestId !== latestRequest) return;
    if (response.ok) {
      plannerLeague = data;
      plannerKeys = keysAsked;
    } else {
      plannerFailed = true;
    }
  } catch (error) {
    if (requestId !== latestRequest) return;
    plannerFailed = true;
  }
  plannerPending = false;
  renderLeague();
  renderStanding();
}

function scheduleRefresh() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(refresh, 250);
}

// ---------- actions ----------
function pickedIds() {
  return new Set(state.picks.filter((pick) => pick.id !== undefined).map((pick) => pick.id));
}

// A click on a table row (or Enter in the search box): the pick on the clock, or the player for the pick being chosen.
// The hero's Draft button is not this: it always logs the pick on the clock and ends any choosing.
function rowPicked(id) {
  if (choosing) choosePlayerFor(id);
  else draft(id);
}

function draft(id) {
  if (!analysis || analysis.clock.draftComplete) return;
  if (pickedIds().has(id)) {
    if (refreshFailed) refresh(); // clicking a pick the server has not confirmed tries again
    return;
  }
  autoPlayFailed = false;
  state.picks.push({ kind: 'player', id });
  state.history.push({ type: 'log', count: 1 });
  state.search = '';
  $('search').value = '';
  saveState();
  refresh();
}

// A pick of a player who is not in the pool: it advances the draft and, if it is mine, fills a starting slot
function draftOutside() {
  if (!analysis || analysis.clock.draftComplete) return;
  state.picks.push({ kind: 'outside' });
  state.history.push({ type: 'log', count: 1 });
  saveState();
  refresh();
}

// "I am behind": the picks between my log and the pick Yahoo is at become unseen picks, up to one of my own picks
function submitBehind(event) {
  event.preventDefault();
  if (!analysis || analysis.clock.draftComplete) return;
  const plan = planBehind(state.picks.length, $('behind-pick').value, pool.myPicks, pool.league.teams * pool.league.rosterSize);
  const note = $('behind-note');
  if (plan.error) {
    note.textContent = plan.error;
    return;
  }
  for (const number of plan.unseen) state.picks.push({ kind: 'unseen' });
  if (plan.unseen.length) state.history.push({ type: 'log', count: plan.unseen.length });
  note.textContent = plan.stoppedAt === null
    ? `${plan.unseen.length} unseen picks added.`
    : `${plan.unseen.length ? `${plan.unseen.length} unseen picks added. ` : ''}Pick ${plan.stoppedAt} is yours: log it now, then press I am behind again for the rest.`;
  if (plan.stoppedAt === null) {
    $('behind-form').hidden = true;
    $('behind').setAttribute('aria-expanded', 'false');
    $('behind-pick').value = '';
  }
  saveState();
  refresh();
}

function toggleBehind() {
  const form = $('behind-form');
  form.hidden = !form.hidden;
  $('behind').setAttribute('aria-expanded', String(!form.hidden));
  $('behind-note').textContent = '';
  if (!form.hidden) $('behind-pick').focus();
}

// Marking a player as gone logs no pick; it resolves the unseen pick closest to his ADP to him
function markPlayerGone(id) {
  const next = markGone(state.picks, id, playerById.get(id).adp);
  if (!next) return;
  state.history.push({ type: 'gone', index: next.findIndex((pick, index) => pick.id === id && state.picks[index].kind === 'unseen') });
  state.picks = next;
  saveState();
  refresh();
}

function hasUnseenPicks() {
  return state.picks.some((pick) => pick.kind === 'unseen');
}

// In a rehearsal Undo goes back to just before my last pick, which can remove many automatic picks: say how many
function rehearsalUndoLabel() {
  const mine = pool.myPicks.filter((number) => number <= state.picks.length);
  const count = state.picks.length - (mine.length ? mine[mine.length - 1] - 1 : 0);
  if (state.picks.length === 0) return 'Undo';
  return `Undo: ${plural(count, 'pick')}, back to ${mine.length ? `my pick ${mine[mine.length - 1]}` : 'the start'}`;
}

function undo() {
  if (state.rehearsal && state.picks.length > 0) {
    // The other teams' picks are automatic, so Undo goes back to just before my last pick
    const mine = pool.myPicks.filter((number) => number <= state.picks.length);
    state.picks = state.picks.slice(0, mine.length ? mine[mine.length - 1] - 1 : 0);
    state.history = [];
    saveState();
    refresh();
    return;
  }
  const result = undoLast(state.picks, state.history);
  if (!result) return;
  state.picks = result.picks;
  state.history = result.history;
  saveState();
  refresh();
}

// ---------- rehearsal ----------
let rehearsing = false;
let autoPlayFailed = false; // stops a failing automatic pick from retrying forever; the next action clears it

// Log the other teams' automatic picks until it is my turn, then refresh once
async function autoPlayOthers() {
  if (rehearsing || !state.rehearsal) return;
  rehearsing = true;
  try {
    const total = pool.league.teams * pool.league.rosterSize;
    while (state.picks.length < total && !pool.myPicks.includes(state.picks.length + 1)) {
      const response = await fetch(API + '/autopick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ picks: state.picks, noise: true, seed: state.seed + state.picks.length }),
      });
      const data = await response.json();
      if (!response.ok) {
        showError(data.error || 'The automatic pick failed.');
        autoPlayFailed = true;
        break;
      }
      state.picks.push({ kind: 'player', id: data.id });
    }
  } catch (error) {
    showError("Can't reach the draft server for the automatic picks.");
    autoPlayFailed = true;
  } finally {
    rehearsing = false;
  }
  state.history = [];
  saveState();
  await refresh();
}

const resetLabel = () => (state.rehearsal ? 'New mock draft' : 'Reset draft');

function reset() {
  const button = $('reset');
  if (!resetArmed) {
    resetArmed = true;
    button.textContent = 'Click again to clear every pick';
    setTimeout(() => {
      resetArmed = false;
      button.textContent = resetLabel();
    }, 3500);
    return;
  }
  resetArmed = false;
  button.textContent = resetLabel();
  state.picks = [];
  state.history = [];
  if (state.rehearsal) state.seed = Math.floor(Math.random() * 1000000) + 1; // a new rehearsal is a different draft
  draftRefused = false;
  hideError(true);
  saveState();
  refresh();
}

// ---------- rendering ----------
function render() {
  renderTopBar();
  renderClock();
  renderHero();
  renderPlan();
  renderSearchNote();
  renderUnseenNote();
  renderPool();
  renderRoster();
  renderStanding();
  renderLeague();
  renderLog();
  renderChoosing();
}

function renderClock() {
  const clock = analysis.clock;
  const line = $('clock-line');
  if (clock.draftComplete) {
    line.textContent = 'The draft is complete.';
  } else if (clock.isMine) {
    line.textContent = `Pick ${clock.pick} (round ${clock.round}): ${teamName(pool.league.slot)}, you're up.`;
  } else {
    const wait = clock.picksUntilMine === null ? '' : ` You pick at ${clock.nextMyPick}, after ${plural(clock.picksUntilMine, 'more pick')}.`;
    line.textContent = `Pick ${clock.pick} (round ${clock.round}): ${clock.teamOnClock} is choosing.${wait}`;
  }

  const slots = Array.from({ length: pool.league.teams }, (_, index) => index + 1);
  if (clock.reversed) slots.reverse();
  const cells = slots.map((slot, index) => {
    const position = index + 1;
    const classes = ['cell'];
    if (slot === pool.league.slot) classes.push('me');
    if (!clock.draftComplete && position < clock.pickInRound) classes.push('done');
    if (!clock.draftComplete && position === clock.pickInRound) classes.push('now');
    return h('div', { class: classes.join(' '), title: teamName(slot) }, slot);
  });
  put($('snake'), ...cells);
  $('snake-note').textContent = clock.reversed
    ? `Round ${clock.round}: picks run right to left. Hover a slot for the team; yours is outlined.`
    : `Round ${clock.round}: picks run left to right. Hover a slot for the team; yours is outlined.`;
  $('undo').disabled = state.picks.length === 0;
  $('undo').textContent = state.rehearsal ? rehearsalUndoLabel() : undoLabel(state.picks, state.history, nameOf);
  $('outside').disabled = analysis.clock.draftComplete;
}

// The last logged pick, always visible beside the table, with the Undo button that reverts it
function renderLastPick() {
  const entries = analysis.log;
  const last = entries[entries.length - 1];
  $('last-pick').textContent = last ? `Logged pick ${last.pick} (${last.team}): ${logLabel(last)}.` : 'Nothing logged yet.';
}

function renderSettingsSummary() {
  const method = state.method === 'uncapped' ? 'uncapped' : 'capped';
  const games = state.gamesAdjusted ? 'games counted' : 'games not counted';
  $('settings-summary').textContent = `${state.categories.length} ${state.categories.length === 1 ? 'category' : 'categories'}, ${method}, ${games}`;
}

function renderTopBar() {
  if (!resetArmed) $('reset').textContent = resetLabel();
  $('app').dataset.mode = state.rehearsal ? 'mock' : 'real';
  $('mode-real').setAttribute('aria-current', state.rehearsal ? 'false' : 'page');
  $('mode-mock').setAttribute('aria-current', state.rehearsal ? 'page' : 'false');
  document.title = state.rehearsal ? 'Mock draft - Draft assistant' : 'Draft assistant';
  renderLastPick();
  renderSettingsSummary();
}

// ---------- panels and tabs ----------
// Which panels share a tab strip depends on the window width (the stylesheet decides); the strip shows only the tabs
// that apply, and the page keeps the active one valid when the window is resized.
function visibleTabs() {
  return [...$('tabs').querySelectorAll('button')].filter((button) => getComputedStyle(button).display !== 'none');
}

function syncTabs() {
  const tabs = visibleTabs();
  try {
    const remembered = localStorage.getItem(TAB_KEY);
    if (remembered && !syncTabs.started) $('app').dataset.tab = remembered;
  } catch (error) {
    // no storage: the default tab is used
  }
  syncTabs.started = true;
  if (tabs.length === 0) return;
  if (!tabs.some((button) => button.dataset.tab === $('app').dataset.tab)) $('app').dataset.tab = tabs[0].dataset.tab;
  for (const button of $('tabs').querySelectorAll('button')) button.setAttribute('aria-selected', String(button.dataset.tab === $('app').dataset.tab));
}

function wireTabs() {
  for (const button of $('tabs').querySelectorAll('button')) {
    button.addEventListener('click', () => {
      $('app').dataset.tab = button.dataset.tab;
      try {
        localStorage.setItem(TAB_KEY, button.dataset.tab);
      } catch (error) {
        // see syncTabs
      }
      syncTabs();
    });
  }
  window.addEventListener('resize', syncTabs);
  syncTabs();
}

// Auto (the system), Light, Dark: one button, remembered in this browser
const THEMES = ['auto', 'light', 'dark'];
let themeChoice = 'auto';

function applyTheme() {
  if (themeChoice === 'auto') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = themeChoice;
  $('theme').textContent = `Theme: ${themeChoice[0].toUpperCase()}${themeChoice.slice(1)}`;
}

function cycleTheme() {
  themeChoice = THEMES[(THEMES.indexOf(themeChoice) + 1) % THEMES.length];
  applyTheme();
  try {
    if (themeChoice === 'auto') localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, themeChoice);
  } catch (error) {
    // Storage blocked: the choice lasts until the page is reloaded
  }
}

function toggleSettings() {
  const panel = $('settings');
  panel.hidden = !panel.hidden;
  if (panel.hidden && !$('setting-confirm').hidden) keepSettings(); // closing without Apply keeps what was in use
  $('settings-toggle').setAttribute('aria-expanded', String(!panel.hidden));
}

// One line when the recommendation is not the best score in the table, so the page never seems to contradict itself
function whyNotTheTopScore(recommendation, plan) {
  const top = analysis.pool[0];
  if (!top || top.id === recommendation.id) return '';
  const lead = `${nameOf(top.id)} scores higher (${oneDecimal(top.score)})`;
  const step = plan.steps.find((candidate) => candidate.id === top.id);
  if (step) return `${lead} but the plan takes him at pick ${step.pick}, where he should still be there (${pct(step.availability)}).`;
  const waiting = !analysis.clock.isMine && top.availability !== null && top.availability < state.rule.threshold;
  if (waiting) return `${lead} but is only ${pct(top.availability)} likely to last to pick ${recommendation.pick}.`;
  const alternative = analysis.alternatives.find((candidate) => candidate.id === top.id);
  if (alternative && alternative.behind >= TIE_POINTS) return `${lead} but taking him first makes the whole plan ${oneDecimal(alternative.behind)} lower.`;
  return '';
}

function renderHero() {
  const hero = $('hero');
  const clock = analysis.clock;
  const recommendation = analysis.recommendation;

  if (clock.draftComplete) {
    hero.className = 'hero';
    put(hero, h('h2', {}, 'Draft complete'), h('p', { class: 'name' }, 'Good luck this season.'));
    return;
  }
  if (!recommendation) {
    const best = analysis.bestAvailable ? poolRowById.get(analysis.bestAvailable.id) : null;
    hero.className = 'hero';
    put(hero,
      h('h2', {}, `Rounds ${pool.league.rounds + 1} to ${pool.league.rosterSize} are not planned. Best available who fits your lineup:`),
      best ? h('p', { class: 'name' }, nameOf(best.id)) : null,
      best ? h('p', { class: 'facts' }, `${detailOf(best.id)}, score ${oneDecimal(best.score)}`) : null,
      best && clock.isMine ? h('div', { class: 'cta' }, h('button', { type: 'button', class: 'primary', onclick: () => draft(best.id) }, `Draft ${nameOf(best.id)}`)) : null,
    );
    return;
  }

  const row = poolRowById.get(recommendation.id);
  const plan = analysis.plans[0];
  const laterSteps = plan.steps.slice(1, 4).map((step) => `${nameOf(step.id)} at ${step.pick}`);
  const mine = clock.isMine;
  hero.className = `hero${mine ? ' yours' : ''}`;

  const heading = mine
    ? `Pick ${recommendation.pick} is yours. Take`
    : `You pick at ${recommendation.pick}, after ${plural(clock.picksUntilMine, 'more pick')}. Current plan:`;
  // On my turn the player is on the board unless picks were missed: then the doubt is shown and the user checks Yahoo
  const doubt = mine && hasUnseenPicks() && row.availability !== null;
  const odds = doubt
    ? (state.rule.type === 'window' ? "Picks were missed. Check he is still on Yahoo's board." : `${pct(row.availability)} chance he is still on the board. Check Yahoo.`)
    : !mine && row.availability !== null ? `${pct(row.availability)} chance he is still there.` : '';
  const lookFirst = doubt ? analysis.lookFirst : [];
  const reason = whyNotTheTopScore(recommendation, plan);
  put(hero, 
    h('h2', {}, heading),
    h('p', { class: 'name' }, nameOf(recommendation.id)),
    h('p', { class: 'facts' }, `${detailOf(recommendation.id)}, score ${oneDecimal(row.score)}${odds ? `. ${odds}` : ''}`),
    reason ? h('p', { class: 'facts' }, reason) : null,
    analysis.search.truncated ? h('p', { class: 'facts' }, 'Approximate: the search was cut short. See the note under Plan.') : null,
    laterSteps.length ? h('p', { class: 'then' }, `Then ${laterSteps.join(', ')}.`) : null,
    lookFirst.length
      ? h('p', { class: 'facts' }, 'If still on the board, look first at: ', ...lookFirst.flatMap((entry) => [
        h('button', { type: 'button', class: 'gone', title: `Log ${nameOf(entry.id)} as the pick on the clock`, onclick: () => { cancelChoosing(); draft(entry.id); } }, `${nameOf(entry.id)} (${pct(entry.availability)})`),
        ' ',
      ]))
      : null,
    mine
      ? h(
          'div',
          { class: 'cta' },
          h('button', { type: 'button', class: 'primary', onclick: () => {
            cancelChoosing();
            draft(recommendation.id);
          } }, `Draft ${nameOf(recommendation.id)}`),
          doubt ? h('button', { type: 'button', onclick: () => markPlayerGone(recommendation.id) }, 'He is gone') : null,
        )
      : null,
  );
}

function meter(availability, isCurrent) {
  if (isCurrent) return h('div', { class: 'meter' }, h('span', {}, 'On the clock'));
  const low = availability < 0.6 ? ' low' : '';
  return h(
    'div',
    { class: 'meter', title: 'Chance he is still available at this pick, from ADP' },
    h('span', {}, `${pct(availability)} likely there`),
    h('div', { class: 'track' }, h('div', { class: `fill${low}`, style: `width:${Math.round(availability * 100)}%` })),
  );
}

// Shown only when it says something: a cut-short search prices its alternatives approximately, and when every
// alternative ties with the best plan there is nothing to choose between.
const TIE_POINTS = 0.05;
function alternativesWorthShowing() {
  return !analysis.search.truncated && analysis.alternatives.some((alt) => alt.behind >= TIE_POINTS);
}

// "Kawhi Leonard (1.2 lower)"; a plan that is the same team in the other order says when the recommended player comes
function alternativeText(alt) {
  return `${nameOf(alt.id)} (${alt.behind >= TIE_POINTS ? `${oneDecimal(alt.behind)} lower` : 'same score'})`;
}

// When the alternatives are the same team in the other order, say once that the recommended player comes next
function thenSentence() {
  const thens = analysis.alternatives.filter((alt) => alt.then).map((alt) => alt.then);
  if (thens.length === 0) return '';
  const first = thens[0];
  const same = thens.length === analysis.alternatives.length && thens.every((then) => then.id === first.id);
  return same ? ` Each of those plans takes ${nameOf(first.id)} at ${first.pick} if he lasts (${pct(first.availability)}).` : '';
}

function renderPlan() {
  const container = $('plan');
  const alternatives = $('alternatives');
  if (analysis.plans.length === 0) {
    put(container, h('p', { class: 'note' }, 'No plan to show.'));
    put(alternatives, );
    return;
  }
  const [best] = analysis.plans;
  const rows = best.steps.map((step) => {
    const row = poolRowById.get(step.id);
    return h(
      'div',
      { class: 'step' },
      h('div', { class: 'pick' }, `Pick ${step.pick}`),
      h('div', { class: 'who' }, h('strong', {}, nameOf(step.id)), h('div', { class: 'meta' }, detailOf(step.id))),
      h('div', { class: 'score-col' }, h('strong', {}, oneDecimal(row.score)), h('div', { class: 'meta' }, 'score')),
      meter(step.availability, step.pick === analysis.clock.pick && !hasUnseenPicks()),
    );
  });
  const foot = h('div', { class: 'plan-foot' }, `Roster score ${oneDecimal(best.totalScore)}. The plan is recomputed after each pick.`);
  put(container, h('div', { class: 'plan' }, rows, foot));

  if (alternativesWorthShowing() && analysis.recommendation) {
    const text = analysis.alternatives.map(alternativeText).join(', ');
    const lead = analysis.alternativesMode === 'gone'
      ? `If ${nameOf(analysis.recommendation.id)} is gone by pick ${analysis.recommendation.pick}, take instead: `
      : 'Or take instead: ';
    put(alternatives, h('span', {}, lead), h('strong', {}, text), h('span', {}, `. In brackets: how far the whole plan falls behind the best one.${thenSentence()}`));
  } else {
    put(alternatives, );
  }
}

// --- pool table ---
const POOL_COLUMNS = [
  { key: 'rank', label: '#', left: false, defaultDirection: 1 },
  { key: 'name', label: 'Player', left: true, defaultDirection: 1 },
  { key: 'score', label: 'Score', left: false, defaultDirection: -1 },
  { key: 'availability', label: 'At your pick', left: false, defaultDirection: -1, title: 'Chance he is still available when you next pick' },
  { key: 'adp', label: 'ADP', left: false, defaultDirection: 1 },
  { key: 'xrank', label: 'XRank', left: false, defaultDirection: 1, title: "Yahoo's own expert ranking" },
  { key: 'gp', label: 'GP', left: false, defaultDirection: -1, title: 'Games projected for 2026-27' },
  ...STAT_COLUMNS.map((column) => ({ key: column.key, label: column.label, left: false, defaultDirection: column.key === 'to' ? 1 : -1 })),
];

function buildPoolHead() {
  const cells = POOL_COLUMNS.map((column) => {
    const th = h('th', { class: column.left ? 'left' : '' });
    if (column.defaultDirection === 0) {
      th.append(h('button', { type: 'button', disabled: true }, column.label));
      return th;
    }
    const button = h('button', { type: 'button', 'data-key': column.key, title: column.title, onclick: () => sortBy(column) }, column.label);
    th.append(button);
    return th;
  });
  put($('pool-head'), h('tr', {}, cells));
}

function sortBy(column) {
  if (state.sort.key === column.key) state.sort.direction *= -1;
  else state.sort = { key: column.key, direction: column.defaultDirection };
  renderPool();
}

// The pick the column is about: my next pick, or on my turn the one after it ("if I pass on him now, will he be there?")
function columnPick() {
  return analysis.clock.isMine ? analysis.laterPick : analysis.clock.nextMyPick;
}

function oddsAtColumn(row) {
  return analysis.clock.isMine ? row.later : row.availability;
}

function sortValue(row, player, key) {
  if (key === 'rank') return row.rank;
  if (key === 'name') return player.name;
  if (key === 'score') return row.score;
  if (key === 'availability') return oddsAtColumn(row);
  if (key === 'adp') return player.adp;
  if (key === 'xrank') return player.xrank;
  if (key === 'gp') return player.gp;
  return player.stats[key];
}

function badge(text, kind, title) {
  return h('span', { class: `badge ${kind}`.trim(), title }, text);
}

function notesFor(row, player) {
  const notes = [];
  if (player.status) notes.push(badge(player.status, 'injury', STATUS_TITLES[player.status] || 'Injury report'));
  const flags = row.flags;
  if (flags.noLastSeason) notes.push(badge('No 2025-26 stats', 'info', 'No stats last season: injured, a rookie, or missing in Yahoo. The score rests on the projection alone.'));
  if (flags.smallSample) notes.push(badge(`${player.lastSeason.gp} GP in 2025-26`, 'info', 'Too few games last season for the average to mean much.'));
  if (flags.diverges) {
    notes.push(badge(`Proj ${signed(row.lastSeasonDelta)} vs 2025-26`, '', `Projected score minus last season's score, on the same scale. Last season: ${oneDecimal(row.lastSeasonScore)}.`));
  }
  if (flags.lowGames) notes.push(badge(`Proj ${player.gp} GP`, '', 'Projected to miss a lot of games. Scores are per game, so availability is not in the number.'));
  return notes;
}

// A player the unseen picks could not plausibly have taken needs no Gone button: it shows from this chance up
const UNSEEN_RISK_SHOWN = 0.05;

// The odds as a tint of the cell (the same mechanism as the stats), text at full contrast
function oddsCell(value) {
  if (value === null || value === undefined) return h('td', {}, '-');
  const style = value >= 0.5
    ? `background: color-mix(in srgb, var(--cool) ${Math.round(value * 28)}%, transparent)`
    : '';
  return h('td', { style }, pct(value));
}

// A stat tinted by how good it is in its category (0 to 100 on the capped scale); unticked categories are dimmed
function statCell(column, player, row) {
  const score = row.categoryScores[column.key];
  const ticked = state.categories.includes(column.key);
  const style = ticked && score !== null && score !== undefined ? `background: color-mix(in srgb, var(--cool) ${Math.round(Math.max(0, Math.min(100, score)) * 0.28)}%, transparent)` : '';
  return h('td', { class: ticked ? '' : 'dim', style }, column.kind === 'rate' ? formatRate(player.stats[column.key]) : oneDecimal(player.stats[column.key]));
}

// Only offered while picks are unseen; it must not also log the row, so its clicks and keys stop here
function goneButton(player) {
  return h(
    'button',
    {
      type: 'button',
      class: 'gone',
      title: `${player.name} was taken at one of the unseen picks`,
      onclick: (event) => {
        event.stopPropagation();
        markPlayerGone(player.id);
      },
      onkeydown: (event) => event.stopPropagation(),
    },
    'Gone',
  );
}

function matchesFilters(player) {
  if (state.position !== 'ALL' && !player.positions.includes(state.position)) return false;
  const text = `${player.name} ${player.team}`.toLowerCase();
  return state.search.toLowerCase().split(/\s+/).filter(Boolean).every((token) => text.includes(token));
}

// An empty table says why: a player already drafted is named with the pick that took him
function emptyTableMessage() {
  const tokens = state.search.toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length) {
    const taken = analysis.log.find((entry) => entry.id && tokens.every((token) => `${nameOf(entry.id)} ${playerById.get(entry.id).team}`.toLowerCase().includes(token)));
    if (taken) return `${nameOf(taken.id)} was taken at pick ${taken.pick} (${taken.team}).`;
  }
  return 'No available player matches. Clear the search or choose another position.';
}

let visibleIds = [];

let plannedPicks = new Map();

function renderPool() {
  plannedPicks = new Map(analysis.plans.length ? analysis.plans[0].steps.map((step) => [step.id, step.pick]) : []);
  const pickLabel = columnPick();
  const availabilityHead = $('pool-head').querySelector('button[data-key="availability"]');
  if (availabilityHead) availabilityHead.textContent = pickLabel ? `At pick ${pickLabel}` : 'At your pick';
  const rows = analysis.pool
    .map((row) => ({ row, player: playerById.get(row.id) }))
    .filter(({ player }) => matchesFilters(player));
  const { key, direction } = state.sort;
  rows.sort((a, b) => {
    const left = sortValue(a.row, a.player, key);
    const right = sortValue(b.row, b.player, key);
    if (left === right) return a.row.rank - b.row.rank;
    if (left === null || left === undefined) return 1; // blanks always last
    if (right === null || right === undefined) return -1;
    return (left < right ? -1 : 1) * direction;
  });
  visibleIds = rows.map(({ player }) => player.id);

  const body = rows.map(({ row, player }) => {
    const logged = pickedIds().has(player.id); // still in the table because the server has not answered yet
    const unconfirmed = refreshFailed && logged;
    const pending = busyShown && logged && !unconfirmed;
    const planned = plannedPicks.get(player.id);
    const isRecommended = analysis.recommendation && analysis.recommendation.id === player.id;
    const cells = [
      h('td', {}, row.rank),
      h('td', { class: 'left player' }, h('strong', {}, isRecommended ? `★ ${player.name}` : player.name), h('div', { class: 'meta' }, `${player.team}, ${player.positions.join('/')}`), h('div', { class: 'notes' }, [
        ...(planned && !isRecommended ? [badge(`plan: ${planned}`, 'info', `The current plan takes him at pick ${planned}`)] : []),
        ...(unconfirmed ? [badge('Logged, not confirmed. Click to retry', 'injury', 'The server has not confirmed this pick yet')] : []),
        ...(pending ? [badge('Logging the pick', 'info', 'Waiting for the server to confirm this pick')] : []),
        ...notesFor(row, player),
        ...(hasUnseenPicks() && row.unseenRisk >= UNSEEN_RISK_SHOWN ? [goneButton(player)] : []),
      ])),
      h('td', { class: 'score' }, oneDecimal(row.score)),
      oddsCell(oddsAtColumn(row)),
      h('td', { title: player.adpEstimated ? 'Yahoo shows no ADP for him; estimated from nearby ranks' : '' }, `${player.adpEstimated ? '~' : ''}${player.adp.toFixed(1)}`),
      h('td', {}, player.xrank),
      h('td', {}, player.gp),
      ...STAT_COLUMNS.map((column) => statCell(column, player, row)),
    ];
    return h(
      'tr',
      {
        tabindex: '0',
        class: unconfirmed || pending ? 'unconfirmed' : '',
        'data-id': player.id,
        title: `Log ${player.name} as the pick on the clock`,
        onclick: () => rowPicked(player.id),
        onkeydown: (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            rowPicked(player.id);
          } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            const sibling = event.key === 'ArrowDown' ? event.currentTarget.nextElementSibling : event.currentTarget.previousElementSibling;
            if (sibling) sibling.focus();
          }
        },
      },
      cells,
    );
  });
  put($('pool-body'), ...body);
  if (rows.length === 0) $('pool-body').append(h('tr', {}, h('td', { colspan: POOL_COLUMNS.length, class: 'left' }, emptyTableMessage())));

  for (const button of $('pool-head').querySelectorAll('button[data-key]')) {
    // aria-sort belongs on the column header cell, and the stylesheet draws the arrow from it
    const header = button.parentElement;
    if (button.dataset.key === key) header.setAttribute('aria-sort', direction === 1 ? 'ascending' : 'descending');
    else header.removeAttribute('aria-sort');
  }
}

// --- right rail ---
// What an incomplete search gives back: the best plan found, which usually starts with the highest-scoring player
// Said whenever picks are unseen: the odds in the table already allow for them
function renderUnseenNote() {
  const note = $('unseen-note');
  const numbers = analysis.log.filter((entry) => entry.kind === 'unseen').map((entry) => entry.pick);
  if (numbers.length === 0) {
    note.hidden = true;
    return;
  }
  const range = numbers.length === 1 ? `pick ${numbers[0]}` : `picks ${numbers[0]} to ${numbers[numbers.length - 1]}`;
  note.textContent = `${plural(numbers.length, 'unseen pick')} (${range}). The odds in the table allow for players taken there. Press Gone on a player you know was taken to remove one.`;
  note.hidden = false;
}

function renderSearchNote() {
  const note = $('search-note');
  if (!analysis.search.truncated) {
    note.hidden = true;
    return;
  }
  const plans = analysis.plans;
  const sameStart = plans.length > 0 && plans.every((plan) => plan.steps[0].id === plans[0].steps[0].id);
  const reason = 'The search stopped early: these availability settings let so many players through that checking every plan would take too long.';
  note.textContent = plans.length === 0
    ? `${reason} It stopped before it found a plan. Narrow "Who will still be there?" and try again.`
    : `${reason} The plan is the best one found, not proven the best${sameStart ? `, and every plan starts with ${nameOf(plans[0].steps[0].id)}, the highest-scoring player it tried first` : ''}.`;
  note.hidden = false;
}

function renderRoster() {
  const list = $('roster');
  const entries = analysis.roster;
  if (entries.length === 0) {
    const first = pool.myPicks[0];
    put(list, h('li', { class: 'empty-row' }, `No picks yet. Your first pick is ${first}.`));
    $('roster-positions').textContent = '';
    return;
  }
  const who = (entry) => (entry.kind === 'outside' ? 'Not in the list' : nameOf(entry.id));
  const detail = (entry) => (entry.kind === 'outside' ? 'Any position, replacement-level value' : detailOf(entry.id));
  const slotRows = analysis.lineup.slots.map((slot) => {
    const entry = slot.entry === null ? null : entries[slot.entry];
    return entry
      ? h('li', { class: 'slot filled' }, h('span', { class: 'pick' }, slot.slot), h('span', {}, h('strong', {}, who(entry)), h('div', { class: 'note' }, `#${entry.pick}, ${detail(entry)}`)))
      : h('li', { class: 'slot open' }, h('span', { class: 'pick' }, slot.slot), h('span', { class: 'note' }, 'open'));
  });
  const bench = analysis.lineup.bench.map((index) =>
    h('li', { class: 'slot bench' }, h('span', { class: 'pick' }, 'Bench'), h('span', {}, h('strong', {}, who(entries[index])), h('div', { class: 'note' }, `#${entries[index].pick}, ${detail(entries[index])}`))),
  );
  put(list, ...slotRows, ...bench);
  const fits = analysis.lineup.canAdd;
  $('roster-positions').textContent = fits.length
    ? `One more player can start at: ${fits.join(', ')}.`
    : 'The lineup is full: another player would sit on the bench.';
}

const ordinal = (value) => {
  const tail = value % 100;
  if (tail >= 11 && tail <= 13) return `${value}th`;
  return `${value}${{ 1: 'st', 2: 'nd', 3: 'rd' }[value % 10] || 'th'}`;
};

// Which categories I win, contest or lose against the other 13 teams, from the share of them I beat
function standingGroup(beaten) {
  if (beaten >= 0.65) return 'Winning';
  if (beaten >= 0.35) return 'Close';
  return 'Behind';
}

function renderWeightsNote(keys, labels) {
  const needs = analysis.needs;
  if (!needs.on) return h('p', { class: 'note' }, 'Every category counts equally. Settings can favour the ones you can still win.');
  if (needs.ramp === 0) return h('p', { class: 'note' }, 'Favouring the categories you can still win: not yet, it starts after the first complete round.');
  const list = keys.map((key) => `${labels[key]} ${needs.weights[key].toFixed(2)}`).join(', ');
  return h('p', { class: 'note' }, `Weights in use (${pct(needs.ramp)} of full effect): ${list}.`);
}

function renderStanding() {
  const container = $('profile');
  const league = analysis.league;
  const keys = pool.categories.map((category) => category.key).filter((key) => state.categories.includes(key));
  const labels = Object.fromEntries(pool.categories.map((category) => [category.key, category.label]));
  const haveNow = Object.keys(league.standing).length > 0;
  const rows = keys.map((key) => {
    const projected = projectedTable().standing[key];
    const now = league.standing[key];
    return h(
      'div',
      { class: 'profile-row standing-row', title: `Beats ${Math.round(projected.beaten * 13 * 10) / 10} of the other 13 teams projected${key === 'to' ? '. Fewer turnovers is better' : ''}` },
      h('span', {}, labels[key]),
      h('div', { class: 'bars' }, h('div', { class: 'bar roster' }, h('span', { style: `width:${Math.round(projected.beaten * 100)}%` }))),
      h('span', { class: 'rank' }, haveNow ? `${ordinal(now.rank)} now, ${ordinal(projected.rank)} proj.` : `${ordinal(projected.rank)} proj.`),
    );
  });
  const groups = { Winning: [], Close: [], Behind: [] };
  for (const key of keys) groups[standingGroup(projectedTable().standing[key].beaten)].push(labels[key]);
  const summary = Object.entries(groups).filter(([, names]) => names.length).map(([name, names]) => `${name}: ${names.join(', ')}`).join('. ');
  put(
    container,
    h('p', { class: 'note standing-summary' }, summary ? `${summary}.` : ''),
    ...rows,
    h('p', { class: 'note' }, `Bar: the share of the other 13 teams you beat, ${projectedTable().basis}. "Now" counts the first ${league.size} pick${league.size === 1 ? '' : 's'} of each team, against ${plural(Math.max(league.compared - 1, 0), 'other team')}.`),
    renderWeightsNote(keys, labels),
  );
}

// ---------- the 14 teams ----------
let projectedBasis = 'planner'; // which projection the 14 teams and Standing show: 'planner' or 'adp'
let plannerLeague = null; // the planner-completed projection for the log last asked about
let plannerKeys = ''; // the categories it was computed for
let plannerPending = false;
let plannerFailed = false;

// The projected table in use: the planner's when chosen and ready, otherwise the quick ADP fill that comes with the analysis
function projectedTable() {
  const planner = projectedBasis === 'planner' && plannerLeague !== null && plannerKeys === JSON.stringify(state.categories);
  return planner ? plannerLeague : analysis.league.projected;
}

function tintFor(rank, teams) {
  const good = teams > 1 ? (teams - rank) / (teams - 1) : 0.5; // 1 for the best, 0 for the worst
  return `background: color-mix(in srgb, var(--cool) ${Math.round(good * 30)}%, transparent)`;
}

function cellValue(key, value) {
  return key === 'fg_pct' || key === 'ft_pct' ? formatRate(value) : oneDecimal(value);
}

function leagueTable(table, keys, labels) {
  const head = h(
    'tr',
    {},
    h('th', { title: 'Place by team score' }, '#'),
    h('th', { class: 'left' }, 'Team'),
    h('th', { title: 'Expected categories won against a random team: the share of the other teams beaten, added over the ticked categories' }, 'Score'),
    h('th', { title: 'Players counted' }, 'n'),
    ...keys.map((key) => h('th', {}, labels[key])),
  );
  const rows = table.teams.map((team) =>
    h(
      'tr',
      { class: team.mine ? 'mine-row' : '' },
      h('td', {}, team.place === null ? '' : team.place),
      h('td', { class: 'left', title: `${team.name}, slot ${team.slot}` }, team.name),
      h('td', { class: 'score' }, team.score === null ? '' : `${oneDecimal(team.score)}/${keys.length}`),
      h('td', {}, team.players),
      ...keys.map((key) =>
        team.totals === null
          ? h('td', { class: 'dim' }, '')
          : h('td', { style: tintFor(team.ranks[key], table.compared), title: `${ordinal(team.ranks[key])} of ${table.compared}` }, cellValue(key, team.totals[key])),
      ),
    ),
  );
  return h('div', { class: 'league-wrap' }, h('table', { class: 'league-table' }, h('thead', {}, head), h('tbody', {}, ...rows)));
}

// Projected and So far, one above the other, both updated with every pick and sorted by team score
function renderLeague() {
  const container = $('league');
  const keys = pool.categories.map((category) => category.key).filter((key) => state.categories.includes(key));
  const labels = Object.fromEntries(pool.categories.map((category) => [category.key, category.label]));
  const projected = projectedTable();
  const usingPlanner = projected === plannerLeague;
  const switcher = h(
    'div',
    { class: 'league-views', role: 'group', 'aria-label': 'How the other teams are completed' },
    ...[['planner', 'Same planner'], ['adp', 'ADP order']].map(([view, label]) =>
      h('button', { type: 'button', 'aria-pressed': String(projectedBasis === view), onclick: () => { projectedBasis = view; renderLeague(); renderStanding(); } }, label),
    ),
  );
  let status = '';
  if (projectedBasis === 'planner' && !usingPlanner) status = plannerFailed ? 'The planner projection failed: showing ADP order.' : 'Updating: showing ADP order meanwhile.';
  else if (usingPlanner && plannerPending) status = 'Updating.';
  const projectedNote = usingPlanner
    ? `${projected.basis}: logged picks, then every team, yours too, takes the first player of its own best plan in turn. It shows what well-informed teams would end up with, not who will be available, and your league is probably easier.${projected.fallbacks ? ` ${plural(projected.fallbacks, 'pick')} fell back to ADP order.` : ''}`
    : `${projected.basis}: logged picks, your best plan for your team, and the other teams filled in ADP order with lineup limits. Your team is built to these categories and the others are not, so it tends to come first.`;
  const now = analysis.league;
  const nowNote = `The first ${now.size} pick${now.size === 1 ? '' : 's'} of every team. Totals per game; FG% and FT% are real ratios; fewer turnovers is better.${now.waiting ? ` ${plural(now.waiting, 'team')} yet to make pick ${now.size} ${now.waiting === 1 ? 'is' : 'are'} scaled up to it, and a scaled team usually drops a little when it picks.` : ''}${now.leftOut ? ` ${plural(now.leftOut, 'team')} with no player yet ${now.leftOut === 1 ? 'is' : 'are'} left out.` : ''}`;
  const uncounted = now.notCounted ? ` ${plural(now.notCounted, 'pick')} not counted (unseen, gone or not in the list).` : '';
  put(
    container,
    h('h3', {}, 'Projected'),
    switcher,
    status ? h('p', { class: 'note league-status', role: 'status' }, status) : null,
    leagueTable(projected, keys, labels),
    h('p', { class: 'note' }, projectedNote),
    h('h3', {}, 'So far'),
    leagueTable(now, keys, labels),
    h('p', { class: 'note' }, nowNote + uncounted),
  );
}

// A gone entry back to an unseen pick, for a mistake noticed after other picks were logged
function unmark(index) {
  const result = unmarkGone(state.picks, state.history, index);
  if (!result) return;
  state.picks = result.picks;
  state.history = result.history;
  saveState();
  refresh();
}

function logLabel(entry) {
  if (entry.kind === 'outside') return 'Not in the list';
  if (entry.kind === 'unseen') return 'Unseen pick';
  if (entry.kind === 'gone') return `${nameOf(entry.id)} (gone, pick assumed)`;
  return nameOf(entry.id);
}

// Editing the log: which pick is open, and an edit waiting for its confirmation ({picks, text})
let editing = null;
// "Choose the player": the pick whose player the next click on a table row replaces
let choosing = null;

function closeEditing() {
  editing = null;
  choosing = null;
  renderChoosing();
  renderLog();
}

// The wording is built only for an edit that is allowed: a refused edit has nothing to describe
function askToConfirm(result, textFor) {
  if (result.error) {
    editing.error = result.error;
    editing.pending = null;
  } else {
    editing.error = null;
    editing.pending = { picks: result.picks, text: textFor() };
  }
  renderLog();
}

function applyEdit() {
  state.picks = editing.pending.picks;
  state.history = []; // an edit is not something Undo can take back
  editing = null;
  saveState();
  refresh();
}

function cancelChoosing() {
  if (choosing === null) return;
  choosing = null;
  renderChoosing();
  renderLog();
}

// The note stays in view and holds the confirmation, so nothing changes out of sight (the log may be below the window)
function renderChoosing() {
  const note = $('choosing-note');
  if (analysis) $('outside').disabled = analysis.clock.draftComplete || choosing !== null; // it would log the pick on the clock
  note.hidden = choosing === null;
  if (choosing === null) return;
  if (choosing.pending) {
    put(note, choosing.pending.text, ' ', h('button', { type: 'button', onclick: applyChosen }, 'Confirm'), h('button', { type: 'button', onclick: cancelChoosing }, 'Cancel'));
  } else {
    put(note, `Choosing the player for pick ${choosing.pick}: click a player in the table. `, choosing.error ? h('strong', {}, `${choosing.error} `) : null, h('button', { type: 'button', onclick: cancelChoosing }, 'Cancel'));
  }
  note.scrollIntoView({ block: 'nearest' });
}

function applyChosen() {
  state.picks = choosing.pending.picks;
  state.history = [];
  choosing = null;
  saveState();
  refresh();
}

// A table row was clicked while choosing: that player replaces the pick, after a confirmation. Row clicks are
// ignored while a confirmation waits, so a second click cannot log anything.
function choosePlayerFor(id) {
  if (choosing.pending) return;
  const number = choosing.pick;
  const result = choosePlayer(state.picks, number, id);
  choosing.error = result.error || null;
  choosing.pending = result.error ? null : { picks: result.picks, text: chooseText(state.picks, number, id, pool.myPicks, nameOf) };
  renderChoosing();
}

function editPanel(entry) {
  const number = entry.pick;
  const mine = pool.myPicks.includes(number);
  const field = (id, label) => h('label', {}, label, ' ', h('input', { id, type: 'number', min: 1, max: state.picks.length, class: 'pick-number' }));
  const readNumber = (id) => ($(id).value.trim() === '' ? NaN : Number($(id).value));
  const controls = [
    h('div', { class: 'edit-row' }, h('button', { type: 'button', onclick: () => {
      choosing = { pick: number, pending: null, error: null };
      editing = null;
      renderChoosing();
      renderLog();
    } }, 'Choose the player')),
    h('div', { class: 'edit-row' }, field('edit-swap', `Swap pick ${number} with pick`),
      h('button', { type: 'button', onclick: () => {
        const other = readNumber('edit-swap');
        askToConfirm(swapPicks(state.picks, number, other, pool.myPicks), () => swapText(state.picks, number, other, pool.myPicks, nameOf));
      } }, 'Swap')),
  ];
  if (!mine && entry.kind !== 'unseen') {
    controls.push(h('div', { class: 'edit-row' }, h('button', { type: 'button', onclick: () => {
      askToConfirm(forgetPick(state.picks, number, pool.myPicks), () => forgetText(state.picks, number, nameOf));
    } }, 'I do not know what this pick was')));
  }
  if (entry.kind === 'gone') {
    controls.push(h('div', { class: 'edit-row' }, field('edit-place', `${nameOf(entry.id)} was taken at pick`),
      h('button', { type: 'button', onclick: () => {
        const to = readNumber('edit-place');
        askToConfirm(placeGone(state.picks, number, to), () => placeText(state.picks, number, to, nameOf));
      } }, 'Place')));
  }
  const pending = editing.pending
    ? h('div', { class: 'edit-confirm' }, h('span', {}, editing.pending.text), h('button', { type: 'button', onclick: applyEdit }, 'Confirm'), h('button', { type: 'button', onclick: closeEditing }, 'Cancel'))
    : null;
  return h('li', { class: 'edit-panel' }, ...controls, editing.error ? h('p', { class: 'note error-note' }, editing.error) : null, pending,
    h('button', { type: 'button', class: 'gone', onclick: closeEditing }, 'Close'));
}

function renderLog() {
  const list = $('log');
  if (analysis.log.length === 0) {
    put(list, h('li', { class: 'empty-row' }, 'Nothing logged yet.'));
    return;
  }
  const rows = [...analysis.log].reverse().flatMap((entry) => {
    const buttons = [];
    if (entry.kind === 'gone') buttons.push(h('button', { type: 'button', class: 'gone', onclick: () => unmark(entry.pick - 1) }, 'Unmark'));
    buttons.push(h('button', { type: 'button', class: 'gone', 'aria-expanded': String(editing !== null && editing.pick === entry.pick), onclick: () => {
      editing = editing && editing.pick === entry.pick ? null : { pick: entry.pick, pending: null, error: null };
      renderLog();
    } }, 'Edit'));
    const row = h('li', { class: entry.mine ? 'mine' : '' }, h('span', {}, `#${entry.pick}`), h('span', {}, logLabel(entry), entry.id ? h('span', { class: 'team-name' }, playerById.get(entry.id).positions.join('/')) : null, h('span', { class: 'team-name' }, entry.team), ...buttons));
    return editing && editing.pick === entry.pick ? [row, editPanel(entry)] : [row];
  });
  put(list, ...rows);
}

// ---------- controls ----------
function buildCategories() {
  const boxes = pool.categories.map((category) =>
    h(
      'label',
      {},
      h('input', {
        type: 'checkbox',
        value: category.key,
        checked: state.categories.includes(category.key),
        onchange: onCategoryChange,
      }),
      category.label,
    ),
  );
  put($('categories'), ...boxes);
}

function onCategoryChange(event) {
  if ($('categories').querySelectorAll('input:checked').length === 0) {
    event.target.checked = true;
    showError('Keep at least one category ticked.');
    return;
  }
  hideError();
  settingChanged();
}

// ---------- settings changes ----------
// Before the first pick a change applies at once. After it, every score and the plan would change under the user's
// hands on one stray click, so the change waits in the panel until Apply (several clicks become one confirmation)
// and Keep current puts the controls back.
function controlSettings() {
  return {
    categories: [...$('categories').querySelectorAll('input:checked')].map((input) => input.value),
    method: document.querySelector('input[name="method"]:checked').value,
    gamesAdjusted: $('games-adjusted').checked,
    needs: $('needs').checked,
    rule: sanitizeRule(
      {
        type: document.querySelector('input[name="rule"]:checked').value,
        baseSd: $('rule-base-sd').value,
        sdPerAdp: $('rule-sd-per-adp').value,
        threshold: $('rule-threshold').value,
        slack: $('rule-slack').value,
      },
      pool.ruleLimits,
    ),
  };
}

function settingChanged() {
  const proposed = controlSettings();
  syncRuleFields(proposed.rule);
  const labels = Object.fromEntries(pool.categories.map((category) => [category.key, category.label]));
  const changes = settingChanges(state, proposed, labels);
  if (state.picks.length === 0 || changes.length === 0) {
    applySettings();
    return;
  }
  $('setting-confirm-text').textContent = `${plural(state.picks.length, 'pick')} logged. Apply: ${changes.join('; ')}? Every score and your plan are recomputed.`;
  $('setting-confirm').hidden = false;
}

function applySettings() {
  const next = controlSettings();
  state.categories = next.categories;
  state.method = next.method;
  state.gamesAdjusted = next.gamesAdjusted;
  state.needs = next.needs;
  state.rule = next.rule;
  $('setting-confirm').hidden = true;
  syncRuleInputs();
  saveState();
  scheduleRefresh(); // several quick clicks become one request
}

function keepSettings() {
  $('setting-confirm').hidden = true;
  buildCategories();
  document.querySelector(`input[name="method"][value="${state.method}"]`).checked = true;
  $('games-adjusted').checked = state.gamesAdjusted;
  $('needs').checked = state.needs;
  syncRuleInputs();
}

function buildPositionChips() {
  const chips = ['ALL', ...POSITIONS].map((position) =>
    h(
      'button',
      {
        type: 'button',
        'aria-pressed': String(state.position === position),
        onclick: () => {
          state.position = position;
          for (const chip of $('positions').children) chip.setAttribute('aria-pressed', String(chip.dataset.position === position));
          renderPool();
        },
        'data-position': position,
      },
      position === 'ALL' ? 'All' : position,
    ),
  );
  put($('positions'), ...chips);
}

function syncRuleFields(rule) {
  $('rule-probability').hidden = rule.type !== 'probability';
  $('rule-window').hidden = rule.type !== 'window';
}

function syncRuleInputs() {
  const rule = state.rule;
  for (const [key, id] of [['baseSd', 'rule-base-sd'], ['sdPerAdp', 'rule-sd-per-adp'], ['threshold', 'rule-threshold'], ['slack', 'rule-slack']]) {
    $(id).min = pool.ruleLimits[key].min;
    $(id).max = pool.ruleLimits[key].max;
  }
  document.querySelector(`input[name="rule"][value="${rule.type}"]`).checked = true;
  $('rule-base-sd').value = rule.baseSd;
  $('rule-sd-per-adp').value = rule.sdPerAdp;
  $('rule-threshold').value = rule.threshold;
  $('rule-slack').value = rule.slack;
  syncRuleFields(rule);
}

function wireControls() {
  $('error-retry').addEventListener('click', refresh);
  $('error-dismiss').addEventListener('click', () => hideError(true));
  $('undo').addEventListener('click', undo);
  $('settings-toggle').addEventListener('click', toggleSettings);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !$('settings').hidden) toggleSettings();
  });
  $('outside').addEventListener('click', draftOutside);
  $('behind').addEventListener('click', toggleBehind);
  $('behind-form').addEventListener('submit', submitBehind);
  $('reset').addEventListener('click', reset);
  $('theme').addEventListener('click', cycleTheme);
  $('search').addEventListener('input', (event) => {
    state.search = event.target.value;
    renderPool();
  });
  $('search').addEventListener('keydown', (event) => {
    // Enter logs the pick only when exactly one player matches, so a slip of the keyboard cannot log the wrong one
    if (event.key === 'Enter' && visibleIds.length === 1) rowPicked(visibleIds[0]);
  });
  document.querySelector(`input[name="method"][value="${state.method}"]`).checked = true;
  for (const input of document.querySelectorAll('input[name="method"]')) input.addEventListener('change', settingChanged);
  $('games-adjusted').checked = state.gamesAdjusted;
  $('games-adjusted').addEventListener('change', settingChanged);
  $('needs').checked = state.needs;
  $('needs').addEventListener('change', settingChanged);
  for (const input of document.querySelectorAll('input[name="rule"], #rule-base-sd, #rule-sd-per-adp, #rule-threshold, #rule-slack')) {
    input.addEventListener('change', settingChanged);
  }
  $('setting-apply').addEventListener('click', applySettings);
  $('setting-keep').addEventListener('click', keepSettings);
}

async function init() {
  try {
    const response = await fetch(API + '/pool');
    pool = await response.json();
  } catch (error) {
    showError("Can't reach the draft server. Check that run_dashboard.py is running, then reload.");
    return;
  }
  for (const player of pool.players) playerById.set(player.id, player);
  state.rehearsal = pool.rehearsal === true;
  if (state.rehearsal && !state.seed) state.seed = Math.floor(Math.random() * 1000000) + 1;
  let server = null;
  try {
    server = await loadServerDraft();
  } catch (error) {
    showError("Can't read the saved draft from the draft server. Nothing was changed. Check that run_dashboard.py is running, then reload.", false, true);
    return;
  }
  serverVersion = server.version;
  draftId = server.id || '';
  const local = readStored(storageKey());
  const source = chooseSource(server.version, server.state, local, readStored(syncKey()));
  const keptAside = discardsUnconfirmed(source, local, readStored(syncKey()), server.state);
  if (keptAside) {
    try {
      localStorage.setItem(asideKey(), JSON.stringify(local));
    } catch (error) {
      // nothing more can be done
    }
    showNotice(`The draft file was used. This browser had a copy with ${plural((local.picks || []).length, 'pick')} that the file never received, but the file changed since. That copy is kept aside in this browser.`);
  }
  restoreState(source === 'server' ? server.state : null);
  if (source === 'browser' && state.picks.length > 0) {
    showNotice(`Loaded ${plural(state.picks.length, 'pick')} from this browser's copy; the draft file had none. If this is not the draft you expect, press Reset.`);
  } else if (state.picks.length > 0 && !draftRefused && !server.problem && !keptAside) {
    showNotice(`Continuing a saved draft: ${plural(state.picks.length, 'pick')}${state.rehearsal ? ' (a mock draft)' : ''}. Reset starts a new one.`);
  }
  if (server.problem) showError(server.problem, false, true);
  else if (serverVersion > 0 && !draftRefused) showSaved('Saved', true); // the file is what was loaded: say so until the next save
  if (!server.problem && source === 'browser' && !draftRefused && state.picks.length > 0) saveToServer(); // a draft the file does not have yet
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') themeChoice = stored;
  } catch (error) {
    // follow the system
  }
  applyTheme();
  buildCategories();
  buildPositionChips();
  buildPoolHead();
  syncRuleInputs();
  wireControls();
  wireTabs();
  await refresh();
}

init();
