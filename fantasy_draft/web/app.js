'use strict';

// Draft assistant front end. The server holds no state: this page keeps the ordered list of picks
// (also in localStorage, so a refresh mid-draft loses nothing) and asks the server what to do next.

const STORAGE_KEY = 'draft-assistant-v1';
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
function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ picks: state.picks, categories: state.categories, gamesAdjusted: state.gamesAdjusted, method: state.method, rule: state.rule }));
  } catch (error) {
    // Private mode or blocked storage: the draft still works, it just will not survive a refresh
  }
}

function restoreState() {
  let saved = null;
  try {
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
  } catch (error) {
    saved = null;
  }
  const allKeys = pool.categories.map((category) => category.key);
  state.categories = allKeys;
  if (!saved || typeof saved !== 'object') return;
  if (Array.isArray(saved.picks) && saved.picks.every((id) => playerById.has(id)) && new Set(saved.picks).size === saved.picks.length) {
    state.picks = saved.picks;
  }
  if (Array.isArray(saved.categories) && saved.categories.length > 0 && saved.categories.every((key) => allKeys.includes(key))) {
    state.categories = allKeys.filter((key) => saved.categories.includes(key));
  }
  if (typeof saved.gamesAdjusted === 'boolean') state.gamesAdjusted = saved.gamesAdjusted;
  if (saved.method === 'capped' || saved.method === 'uncapped') state.method = saved.method;
  if (saved.rule && typeof saved.rule === 'object') state.rule = { ...DEFAULT_RULE, ...saved.rule };
}

// ---------- talking to the server ----------
function ruleForRequest() {
  const rule = state.rule;
  return rule.type === 'window'
    ? { type: 'window', slack: rule.slack }
    : { type: 'probability', baseSd: rule.baseSd, sdPerAdp: rule.sdPerAdp, threshold: rule.threshold };
}

function showError(message, retryable = false) {
  $('error-text').textContent = message;
  $('error-retry').hidden = !retryable;
  $('error').hidden = false;
}

function hideError() {
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

// Past this long the plan and recommendation are dimmed with a note, so a slow reply is not mistaken for a frozen page
const BUSY_AFTER_MS = 200;
let busyTimer = null;

function setBusy(busy) {
  clearTimeout(busyTimer);
  busyTimer = busy ? setTimeout(() => document.querySelector('main').classList.add('busy'), BUSY_AFTER_MS) : null;
  if (!busy) document.querySelector('main').classList.remove('busy');
}

async function refresh() {
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
    showError("Can't reach the draft server. Your picks are saved in this browser. Check that run_dashboard.py is still running.", true);
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
function draft(id) {
  if (!analysis || analysis.clock.draftComplete) return;
  if (state.picks.includes(id)) {
    if (refreshFailed) refresh(); // clicking a pick the server has not confirmed tries again
    return;
  }
  state.picks.push(id);
  state.search = '';
  $('search').value = '';
  saveState();
  refresh();
}

function undo() {
  if (state.picks.length === 0) return;
  state.picks.pop();
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
  saveState();
  refresh();
}

// ---------- rendering ----------
function render() {
  renderClock();
  renderHero();
  renderPlan();
  renderSearchNote();
  renderPool();
  renderRoster();
  renderProfile();
  renderLog();
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
  const odds = !mine && row.availability !== null ? `${pct(row.availability)} chance he is still there.` : '';
  put(hero, 
    h('h2', {}, heading),
    h('p', { class: 'name' }, nameOf(recommendation.id)),
    h('p', { class: 'facts' }, `${detailOf(recommendation.id)}, score ${oneDecimal(row.score)}${odds ? `. ${odds}` : ''}`),
    analysis.search.truncated ? h('p', { class: 'facts' }, 'Approximate: the search was cut short. See the note under Plan.') : null,
    laterSteps.length ? h('p', { class: 'then' }, `Then ${laterSteps.join(', ')}.`) : null,
    mine
      ? h('div', { class: 'cta' }, h('button', { type: 'button', class: 'primary', onclick: () => draft(recommendation.id) }, `Draft ${nameOf(recommendation.id)}`))
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
      meter(step.availability, step.pick === analysis.clock.pick),
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
    const unconfirmed = refreshFailed && state.picks.includes(player.id);
    const cells = [
      h('td', {}, row.rank),
      h('td', { class: 'left player' }, h('strong', {}, player.name), h('div', { class: 'meta' }, `${player.team}, ${player.positions.join('/')}`), h('div', { class: 'notes' }, [...(unconfirmed ? [badge('Logged, not confirmed. Click to retry', 'injury', 'The server has not confirmed this pick yet')] : []), ...notesFor(row, player)])),
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
        class: unconfirmed ? 'unconfirmed' : '',
        'data-id': player.id,
        title: `Log ${player.name} as the pick on the clock`,
        onclick: () => draft(player.id),
        onkeydown: (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            draft(player.id);
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
      h('li', {}, h('span', { class: 'pick' }, `#${entry.pick}`), h('span', {}, h('strong', {}, nameOf(entry.id)), h('div', { class: 'note' }, detailOf(entry.id)))),
    ),
  );
  const counts = Object.fromEntries(POSITIONS.map((position) => [position, 0]));
  for (const entry of analysis.roster) for (const position of playerById.get(entry.id).positions) counts[position] += 1;
  $('roster-positions').textContent = `Eligible at: ${POSITIONS.map((position) => `${position} ${counts[position]}`).join(', ')}`;
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

function renderLog() {
  const list = $('log');
  if (analysis.log.length === 0) {
    put(list, h('li', { class: 'empty-row' }, 'Nothing logged yet.'));
    return;
  }
  put(list, 
    ...[...analysis.log].reverse().map((entry) => h('li', { class: entry.mine ? 'mine' : '' }, h('span', {}, `#${entry.pick}`), h('span', {}, nameOf(entry.id)))),
  );
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
  document.querySelector(`input[name="rule"][value="${rule.type}"]`).checked = true;
  $('rule-base-sd').value = rule.baseSd;
  $('rule-sd-per-adp').value = rule.sdPerAdp;
  $('rule-threshold').value = rule.threshold;
  $('rule-slack').value = rule.slack;
  $('rule-probability').hidden = rule.type !== 'probability';
  $('rule-window').hidden = rule.type !== 'window';
}

function onRuleChange() {
  const type = document.querySelector('input[name="rule"]:checked').value;
  state.rule = {
    type,
    baseSd: Number($('rule-base-sd').value),
    sdPerAdp: Number($('rule-sd-per-adp').value),
    threshold: Number($('rule-threshold').value),
    slack: Number($('rule-slack').value),
  };
  $('rule-probability').hidden = type !== 'probability';
  $('rule-window').hidden = type !== 'window';
  saveState();
  scheduleRefresh();
}

function wireControls() {
  $('error-retry').addEventListener('click', refresh);
  $('undo').addEventListener('click', undo);
  $('reset').addEventListener('click', reset);
  $('search').addEventListener('input', (event) => {
    state.search = event.target.value;
    renderPool();
  });
  $('search').addEventListener('keydown', (event) => {
    // Enter logs the pick only when exactly one player matches, so a slip of the keyboard cannot log the wrong one
    if (event.key === 'Enter' && visibleIds.length === 1) draft(visibleIds[0]);
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
  restoreState();
  buildCategories();
  buildPositionChips();
  buildPoolHead();
  syncRuleInputs();
  wireControls();
  await refresh();
}

init();
