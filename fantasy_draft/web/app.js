'use strict';

// Draft assistant front end. The server holds no state: this page keeps the ordered list of picks
// (also in localStorage, so a refresh mid-draft loses nothing) and asks the server what to do next.

const STORAGE_KEY = 'draft-assistant-v2';
const LEGACY_STORAGE_KEY = 'draft-assistant-v1'; // read once if v2 is absent, never rewritten, so a rollback has data
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

function currentSavedState() {
  return { version: 2, picks: state.picks, history: state.history, categories: state.categories, gamesAdjusted: state.gamesAdjusted, method: state.method, rule: state.rule };
}

function saveState() {
  if (draftRefused) return; // never write over a draft this page could not read
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(currentSavedState()));
  } catch (error) {
    // Private mode or blocked storage: the draft still works, it just will not survive a refresh
  }
  saveToServer();
}

// One save at a time, always of the latest state, each naming the version the last one produced
async function saveToServer() {
  if (serverSaveBlocked) return;
  if (serverSaving) {
    serverSaveAgain = true;
    return;
  }
  serverSaving = true;
  try {
    do {
      serverSaveAgain = false;
      const response = await fetch('/api/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ baseVersion: serverVersion, state: currentSavedState() }),
      });
      const data = await response.json();
      if (response.status === 409) {
        serverSaveBlocked = true;
        showError(data.error, false, true);
        return;
      }
      if (!response.ok) {
        showError(`The draft could not be saved on disk: ${data.error}. It is still kept in this browser.`);
        return;
      }
      serverVersion = data.version;
    } while (serverSaveAgain);
  } catch (error) {
    showError('The draft could not be saved on disk because the server cannot be reached. It is still kept in this browser.');
  } finally {
    serverSaving = false;
  }
}

// What the server has saved: {version, state, problem}. The page works without it, from the browser's own copy.
async function loadServerDraft() {
  try {
    const response = await fetch('/api/draft');
    if (!response.ok) return { version: 0, state: null, problem: null };
    return await response.json();
  } catch (error) {
    return { version: 0, state: null, problem: null };
  }
}

function restoreState(fromServer) {
  let saved = fromServer;
  if (!saved) {
    try {
      saved = pickSavedState(JSON.parse(localStorage.getItem(STORAGE_KEY)), JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY)));
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
  stickyError = sticky;
  $('error-text').textContent = message;
  $('error-retry').hidden = !retryable;
  $('error').hidden = false;
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
  document.querySelector('main').classList.add('busy');
  if (analysis) renderPool();
}

function setBusy(busy) {
  clearTimeout(busyTimer);
  busyTimer = busy ? setTimeout(showBusy, BUSY_AFTER_MS) : null;
  if (!busy) {
    busyShown = false;
    document.querySelector('main').classList.remove('busy');
  }
}

async function refresh() {
  editing = null; // an open edit was built from the log as it was
  choosing = null;
  const requestId = ++latestRequest;
  setBusy(true);
  const body = JSON.stringify({ categories: state.categories, picks: state.picks, rule: ruleForRequest(), gamesAdjusted: state.gamesAdjusted, method: state.method });
  let response = null;
  for (let attempt = 0; attempt <= NETWORK_RETRIES && response === null; attempt += 1) {
    if (attempt > 0) {
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
      if (requestId !== latestRequest) return;
    }
    try {
      response = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
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

function undo() {
  const result = undoLast(state.picks, state.history);
  if (!result) return;
  state.picks = result.picks;
  state.history = result.history;
  saveState();
  refresh();
}

function reset() {
  const button = $('reset');
  if (!resetArmed) {
    resetArmed = true;
    button.textContent = 'Click again to clear every pick';
    setTimeout(() => {
      resetArmed = false;
      button.textContent = 'Reset draft';
    }, 3500);
    return;
  }
  resetArmed = false;
  button.textContent = 'Reset draft';
  state.picks = [];
  state.history = [];
  draftRefused = false;
  hideError(true);
  saveState();
  refresh();
}

// ---------- rendering ----------
function render() {
  renderClock();
  renderHero();
  renderPlan();
  renderSearchNote();
  renderUnseenNote();
  renderPool();
  renderRoster();
  renderProfile();
  renderLog();
  renderChoosing();
}

function renderClock() {
  const clock = analysis.clock;
  const line = $('clock-line');
  if (clock.draftComplete) {
    line.textContent = 'The draft is complete.';
  } else if (clock.isMine) {
    line.textContent = `Pick ${clock.pick} (round ${clock.round}): you're up.`;
  } else {
    const wait = clock.picksUntilMine === null ? '' : ` You pick at ${clock.nextMyPick}, after ${plural(clock.picksUntilMine, 'more pick')}.`;
    line.textContent = `Pick ${clock.pick} (round ${clock.round}): slot ${clock.slotOnClock} is choosing.${wait}`;
  }

  const slots = Array.from({ length: pool.league.teams }, (_, index) => index + 1);
  if (clock.reversed) slots.reverse();
  const cells = slots.map((slot, index) => {
    const position = index + 1;
    const classes = ['cell'];
    if (slot === pool.league.slot) classes.push('me');
    if (!clock.draftComplete && position < clock.pickInRound) classes.push('done');
    if (!clock.draftComplete && position === clock.pickInRound) classes.push('now');
    return h('div', { class: classes.join(' ') }, slot);
  });
  put($('snake'), ...cells);
  $('snake-note').textContent = clock.reversed
    ? `Round ${clock.round}: picks run right to left. Slot numbers shown, yours is outlined.`
    : `Round ${clock.round}: picks run left to right. Slot numbers shown, yours is outlined.`;
  $('undo').disabled = state.picks.length === 0;
  $('undo').textContent = undoLabel(state.picks, state.history, nameOf);
  $('outside').disabled = analysis.clock.draftComplete;
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
    const best = analysis.pool[0];
    hero.className = 'hero';
    put(hero, 
      h('h2', {}, 'Your planned picks are made'),
      best ? h('p', { class: 'name' }, nameOf(best.id)) : null,
      best ? h('p', { class: 'facts' }, `Best available by score: ${detailOf(best.id)}, score ${oneDecimal(best.score)}`) : null,
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
    : `You pick at ${recommendation.pick}, after ${plural(clock.picksUntilMine, 'more pick')}. Today's plan says`;
  // On my turn the player is on the board unless picks were missed: then the doubt is shown and the user checks Yahoo
  const doubt = mine && hasUnseenPicks() && row.availability !== null;
  const odds = doubt
    ? (state.rule.type === 'window' ? "Picks were missed. Check he is still on Yahoo's board." : `${pct(row.availability)} chance he is still on the board. Check Yahoo.`)
    : !mine && row.availability !== null ? `${pct(row.availability)} chance he is still there.` : '';
  const lookFirst = doubt ? analysis.lookFirst : [];
  put(hero, 
    h('h2', {}, heading),
    h('p', { class: 'name' }, nameOf(recommendation.id)),
    h('p', { class: 'facts' }, `${detailOf(recommendation.id)}, score ${oneDecimal(row.score)}${odds ? `. ${odds}` : ''}`),
    analysis.search.truncated ? h('p', { class: 'facts' }, 'Approximate: the search was cut short. See the note under Plan.') : null,
    laterSteps.length ? h('p', { class: 'then' }, `Then ${laterSteps.join(', ')}.`) : null,
    lookFirst.length
      ? h('p', { class: 'facts' }, `If still on the board, look first at: ${lookFirst.map((entry) => `${nameOf(entry.id)} (${pct(entry.availability)})`).join(', ')}.`)
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

function renderPlan() {
  const container = $('plan');
  const alternatives = $('alternatives');
  if (analysis.plans.length === 0) {
    put(container, h('p', { class: 'note' }, 'No plan to show.'));
    put(alternatives, );
    return;
  }
  const [best, ...others] = analysis.plans;
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
  const foot = h(
    'div',
    { class: 'plan-foot' },
    `Roster score ${oneDecimal(best.totalScore)}. Odds the whole plan holds: ${pct(best.survival)}, every pick's odds multiplied. The plan is recomputed after each pick.`,
  );
  const otherPlans = others.length
    ? h(
        'details',
        { class: 'others' },
        h('summary', {}, `Other strong plans (${others.length})`),
        others.map((plan) =>
          h('div', { class: 'other-plan' }, `${plan.steps.map((step) => `${step.pick}: ${nameOf(step.id)}`).join(', ')}. Score ${oneDecimal(plan.totalScore)}.`),
        ),
      )
    : null;
  put(container, h('div', { class: 'plan' }, rows, foot), otherPlans);

  if (alternativesWorthShowing() && analysis.recommendation) {
    const text = analysis.alternatives.map((alt) => `${nameOf(alt.id)} (${alt.behind >= TIE_POINTS ? `${oneDecimal(alt.behind)} lower` : 'same'})`).join(', ');
    const lead = analysis.alternativesMode === 'gone'
      ? `If ${nameOf(analysis.recommendation.id)} is gone by pick ${analysis.recommendation.pick}, take instead: `
      : 'Or take instead: ';
    put(alternatives, h('span', {}, lead), h('strong', {}, text), h('span', {}, '. In brackets: how far the whole plan falls behind the best one.'));
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

function sortValue(row, player, key) {
  if (key === 'rank') return row.rank;
  if (key === 'name') return player.name;
  if (key === 'score') return row.score;
  if (key === 'availability') return row.availability;
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
  const needle = state.search.trim().toLowerCase();
  return !needle || player.name.toLowerCase().includes(needle) || player.team.toLowerCase().includes(needle);
}

let visibleIds = [];

function renderPool() {
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
    const cells = [
      h('td', {}, row.rank),
      h('td', { class: 'left player' }, h('strong', {}, player.name), h('div', { class: 'meta' }, `${player.team}, ${player.positions.join('/')}`), h('div', { class: 'notes' }, [
        ...(unconfirmed ? [badge('Logged, not confirmed. Click to retry', 'injury', 'The server has not confirmed this pick yet')] : []),
        ...(pending ? [badge('Logging the pick', 'info', 'Waiting for the server to confirm this pick')] : []),
        ...notesFor(row, player),
        ...(hasUnseenPicks() ? [goneButton(player)] : []),
      ])),
      h('td', { class: 'score' }, oneDecimal(row.score)),
      h('td', {}, row.availability === null ? '-' : pct(row.availability)),
      h('td', { title: player.adpEstimated ? 'Yahoo shows no ADP for him; estimated from nearby ranks' : '' }, `${player.adpEstimated ? '~' : ''}${player.adp.toFixed(1)}`),
      h('td', {}, player.xrank),
      h('td', {}, player.gp),
      ...STAT_COLUMNS.map((column) => h('td', {}, column.kind === 'rate' ? formatRate(player.stats[column.key]) : oneDecimal(player.stats[column.key]))),
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
          }
        },
      },
      cells,
    );
  });
  put($('pool-body'), ...body);
  if (rows.length === 0) $('pool-body').append(h('tr', {}, h('td', { colspan: POOL_COLUMNS.length, class: 'left' }, 'No available player matches. Clear the search or choose another position.')));

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
  if (analysis.roster.length === 0) {
    const first = pool.myPicks[0];
    put(list, h('li', { class: 'empty-row' }, `No picks yet. Your first pick is ${first}.`));
    $('roster-positions').textContent = '';
    return;
  }
  put(list, 
    ...analysis.roster.map((entry) =>
      entry.kind === 'outside'
        ? h('li', {}, h('span', { class: 'pick' }, `#${entry.pick}`), h('span', {}, h('strong', {}, 'Not in the list'), h('div', { class: 'note' }, 'Any position, replacement-level value')))
        : h('li', {}, h('span', { class: 'pick' }, `#${entry.pick}`), h('span', {}, h('strong', {}, nameOf(entry.id)), h('div', { class: 'note' }, detailOf(entry.id)))),
    ),
  );
  const counts = Object.fromEntries(POSITIONS.map((position) => [position, 0]));
  const outside = analysis.roster.filter((entry) => entry.kind === 'outside').length;
  for (const entry of analysis.roster) if (entry.kind !== 'outside') for (const position of playerById.get(entry.id).positions) counts[position] += 1;
  const outsideNote = outside ? `, plus ${outside} not in the list (any position)` : '';
  $('roster-positions').textContent = `Eligible at: ${POSITIONS.map((position) => `${position} ${counts[position]}`).join(', ')}${outsideNote}`;
}

function renderProfile() {
  const container = $('profile');
  const { roster, plan } = analysis.profile;
  if (!plan && !roster) {
    put(container, h('p', { class: 'note' }, 'Appears once you have picks or a plan.'));
    return;
  }
  const keys = pool.categories.map((category) => category.key).filter((key) => state.categories.includes(key));
  const labels = Object.fromEntries(pool.categories.map((category) => [category.key, category.label]));
  const bar = (kind, value) => h('div', { class: `bar ${kind}` }, h('span', { style: `width:${Math.max(0, Math.min(100, value))}%` }));
  const rows = keys.map((key) =>
    h(
      'div',
      { class: 'profile-row', title: key === 'to' ? 'Turnovers are scored so that fewer is better' : '' },
      h('span', {}, labels[key]),
      h('div', { class: 'bars' }, roster ? bar('roster', roster[key].score) : null, plan ? bar('plan', plan[key].score) : null),
      h('span', {}, plan ? plan[key].score : roster[key].score),
    ),
  );
  const legend = h(
    'div',
    { class: 'profile-legend' },
    roster ? h('span', {}, h('i', { style: 'background:var(--mine)' }), 'Drafted') : null,
    plan ? h('span', {}, h('i', { style: 'background:var(--taken)' }), 'With best plan') : null,
  );
  put(container, legend, ...rows, h('p', { class: 'note' }, '0 to 100 against the pool. The number is the team average per category.'));
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
    const row = h('li', { class: entry.mine ? 'mine' : '' }, h('span', {}, `#${entry.pick}`), h('span', {}, logLabel(entry), ...buttons));
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
  const selected = [...$('categories').querySelectorAll('input:checked')].map((input) => input.value);
  if (selected.length === 0) {
    event.target.checked = true;
    showError('Keep at least one category ticked.');
    return;
  }
  hideError();
  state.categories = selected;
  saveState();
  scheduleRefresh(); // several quick clicks become one request
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
  $('rule-probability').hidden = rule.type !== 'probability';
  $('rule-window').hidden = rule.type !== 'window';
}

function onRuleChange() {
  // Typed values are held inside the allowed range and written back, so the box shows what is being used
  state.rule = sanitizeRule(
    {
      type: document.querySelector('input[name="rule"]:checked').value,
      baseSd: $('rule-base-sd').value,
      sdPerAdp: $('rule-sd-per-adp').value,
      threshold: $('rule-threshold').value,
      slack: $('rule-slack').value,
    },
    pool.ruleLimits,
  );
  syncRuleInputs();
  saveState();
  scheduleRefresh();
}

function wireControls() {
  $('error-retry').addEventListener('click', refresh);
  $('undo').addEventListener('click', undo);
  $('outside').addEventListener('click', draftOutside);
  $('behind').addEventListener('click', toggleBehind);
  $('behind-form').addEventListener('submit', submitBehind);
  $('reset').addEventListener('click', reset);
  $('search').addEventListener('input', (event) => {
    state.search = event.target.value;
    renderPool();
  });
  $('search').addEventListener('keydown', (event) => {
    // Enter logs the pick only when exactly one player matches, so a slip of the keyboard cannot log the wrong one
    if (event.key === 'Enter' && visibleIds.length === 1) rowPicked(visibleIds[0]);
  });
  document.querySelector(`input[name="method"][value="${state.method}"]`).checked = true;
  for (const input of document.querySelectorAll('input[name="method"]')) {
    input.addEventListener('change', () => {
      state.method = document.querySelector('input[name="method"]:checked').value;
      saveState();
      scheduleRefresh();
    });
  }
  $('games-adjusted').checked = state.gamesAdjusted;
  $('games-adjusted').addEventListener('change', (event) => {
    state.gamesAdjusted = event.target.checked;
    saveState();
    scheduleRefresh();
  });
  for (const input of document.querySelectorAll('input[name="rule"], #rule-base-sd, #rule-sd-per-adp, #rule-threshold, #rule-slack')) {
    input.addEventListener('change', onRuleChange);
  }
}

async function init() {
  try {
    const response = await fetch('/api/pool');
    pool = await response.json();
  } catch (error) {
    showError("Can't reach the draft server. Check that run_dashboard.py is running, then reload.");
    return;
  }
  for (const player of pool.players) playerById.set(player.id, player);
  const server = await loadServerDraft();
  serverVersion = server.version;
  restoreState(server.state);
  if (server.problem) showError(server.problem, false, true);
  else if (!server.state && !draftRefused && state.picks.length > 0) saveToServer(); // a draft that so far lives only in this browser
  buildCategories();
  buildPositionChips();
  buildPoolHead();
  syncRuleInputs();
  wireControls();
  await refresh();
}

init();
