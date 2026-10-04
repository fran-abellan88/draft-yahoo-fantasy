'use strict';

// Pure helpers for the page: plain functions with no DOM access, so tests can load this file under Node
// (tests/test_page_logic.py). The browser loads it as a classic script before app.js.

// The server is the only place the allowed ranges are written down. `limits` is {key: {default, min, max}} as sent
// by /api/pool, so the page and the server cannot disagree about what a valid availability setting is.

// One value from the input box or from storage. Blank or non-numeric becomes the default (an empty box would
// otherwise read as 0), anything else is held inside the allowed range.
function clampRuleValue(raw, limit) {
  if (raw === null || raw === undefined || typeof raw === 'boolean') return limit.default;
  if (typeof raw === 'string' && raw.trim() === '') return limit.default;
  const value = Number(raw);
  if (!Number.isFinite(value)) return limit.default;
  return Math.min(limit.max, Math.max(limit.min, value));
}

// A whole availability rule, from the inputs or from localStorage, as the server will accept it.
function sanitizeRule(rule, limits) {
  const source = rule && typeof rule === 'object' ? rule : {};
  const clean = { type: source.type === 'window' ? 'window' : 'probability' };
  for (const key of Object.keys(limits)) clean[key] = clampRuleValue(source[key], limits[key]);
  return clean;
}

// ---------- my rules ----------
// A rule is {id, kind: 'only' | 'avoid', players: [ids], from, to, enabled}; from and to count my own picks (1 is my
// first) and a null `to` means through my last pick. The server checks them again, so this only keeps a damaged saved
// list from being sent: anything it cannot make sense of is dropped.
const RULE_KINDS = ['only', 'avoid'];
const MAX_RULES = 30;
const MAX_RULE_PLAYERS = 20;

function sanitizeRules(raw, knownIds, pickCount) {
  if (!Array.isArray(raw)) return [];
  const whole = (value) => Number.isInteger(value) && value >= 1 && value <= pickCount;
  const clean = [];
  for (const entry of raw.slice(0, MAX_RULES)) {
    if (!entry || typeof entry !== 'object' || !RULE_KINDS.includes(entry.kind)) continue;
    const players = Array.isArray(entry.players) ? [...new Set(entry.players.filter((id) => knownIds.has(id)))].slice(0, MAX_RULE_PLAYERS) : [];
    const to = entry.to === null || entry.to === undefined ? null : entry.to;
    if (players.length === 0 || !whole(entry.from) || (to !== null && (!whole(to) || to < entry.from))) continue;
    clean.push({ id: String(entry.id || `r${clean.length + 1}`), kind: entry.kind, players, from: entry.from, to, enabled: entry.enabled !== false });
  }
  return clean;
}

// "my pick 2", "my picks 1 to 3", "my pick 4 on"
function rulePicksText(rule) {
  if (rule.to === rule.from) return `my pick ${rule.from}`;
  if (rule.to === null) return `my pick ${rule.from} on`;
  return `my picks ${rule.from} to ${rule.to}`;
}

function joinNames(names) {
  if (names.length <= 1) return names.join('');
  return `${names.slice(0, -1).join(', ')} or ${names[names.length - 1]}`;
}

function ruleText(rule, nameOf) {
  const names = joinNames(rule.players.map(nameOf));
  return rule.kind === 'only' ? `At ${rulePicksText(rule)}: only ${names}` : `Not ${names} at ${rulePicksText(rule)}`;
}

// ---------- the saved draft ----------
// The pick log is a list of objects, {kind: 'player', id}. The first version of the page saved a bare list of player
// ids under another storage key. Both are read here, so a draft saved by an older page is not lost.
//   player   a player in the pool          outside  a player who is not in the pool (names no player)
//   unseen   a pick nobody reported        gone     an unseen pick resolved to a player known to be taken
const PICK_KINDS = ['player', 'outside', 'unseen', 'gone'];
const KINDS_WITH_A_PLAYER = ['player', 'gone'];

// A pick log in either shape, as a list of objects; null when any entry is unusable (so nothing half-valid is kept).
// With `myPicks` (the user's own pick numbers) an unseen or gone entry on one of them is unusable too: the server
// refuses such a log, so keeping it would leave the page unable to load.
function normalizePicks(raw, knownIds, myPicks = []) {
  if (!Array.isArray(raw)) return null;
  const seen = new Set();
  const picks = [];
  for (const entry of raw) {
    const pick = typeof entry === 'string' ? { kind: 'player', id: entry } : entry;
    if (!pick || typeof pick !== 'object') return null;
    const kind = pick.kind === undefined ? 'player' : pick.kind;
    if (!PICK_KINDS.includes(kind)) return null;
    if (KINDS_WITH_A_PLAYER.includes(kind)) {
      if (typeof pick.id !== 'string' || !knownIds.has(pick.id) || seen.has(pick.id)) return null;
      seen.add(pick.id);
      picks.push({ kind, id: pick.id });
    } else {
      if (pick.id !== undefined) return null; // these kinds name no player
      picks.push({ kind });
    }
    if (['unseen', 'gone'].includes(kind) && myPicks.includes(picks.length)) return null;
  }
  return picks;
}

// The saved state to use: the current version's if there is one, otherwise the first version's.
function pickSavedState(current, legacy) {
  if (current && typeof current === 'object') return current;
  if (legacy && typeof legacy === 'object') return legacy;
  return null;
}

// ---------- which saved copy to load ----------
// The draft lives in a file written by the server and, as a backup, in the browser. The file wins, except when the
// browser copy is newer: it was saved while the server could not be reached (so the server never confirmed it) and
// the file is still the version it was based on. `sync` is what the page wrote beside the browser copy:
// {basedOn: the file version the copy came from, confirmed: whether the server has this exact copy}.
function chooseSource(serverVersion, serverState, localState, sync) {
  if (!serverState) return localState ? 'browser' : 'none';
  if (localState && sync && sync.confirmed === false && sync.basedOn === serverVersion) return 'browser';
  return 'server';
}

// True when the file won although the browser copy had never been confirmed by the server: that copy is then kept aside
// and the user is told, so nothing is lost without a word. A copy with the very picks the file holds lost nothing (the
// page left before the answer came), so it needs no notice.
function discardsUnconfirmed(source, localState, sync, serverState) {
  if (source !== 'server' || !localState || !sync || sync.confirmed !== false) return false;
  const same = serverState && JSON.stringify(localState.picks) === JSON.stringify(serverState.picks);
  return !same;
}

// ---------- catching up ----------
// The user presses "I am behind" and types the pick Yahoo is at. The picks in between become unseen picks, except
// that a pick of the user's own is never unseen (they always know it): the list stops before it and the user logs
// that pick first. `myPicks` and `totalPicks` come from the server's /api/pool.
function planBehind(logLength, yahooPick, myPicks, totalPicks) {
  const next = logLength + 1;
  const blank = typeof yahooPick === 'string' && yahooPick.trim() === '';
  const target = blank || yahooPick === null || yahooPick === undefined ? NaN : Number(yahooPick);
  if (!Number.isInteger(target)) return { error: 'Type the pick number Yahoo is at.', unseen: [], stoppedAt: null };
  if (target <= next) {
    return { error: `Yahoo is at pick ${target}, which is not ahead of the next pick to log (${next}). Nothing is missing.`, unseen: [], stoppedAt: null };
  }
  if (target > totalPicks) return { error: `The draft has ${totalPicks} picks.`, unseen: [], stoppedAt: null };
  const unseen = [];
  for (let number = next; number < target; number += 1) {
    if (myPicks.includes(number)) return { error: null, unseen, stoppedAt: number };
    unseen.push(number);
  }
  return { error: null, unseen, stoppedAt: null };
}

// Marking a player as gone resolves one unseen pick to him. It logs no pick of its own: the list is the same length.
// The pick resolved is the unseen one closest to his ADP, where he most plausibly went (the first, when there is no
// ADP): the odds of the players near that pick are what his departure should change, and resolving the earliest pick
// instead would leave them untouched. Null when nothing is unseen or he is already in the log.
function markGone(picks, id, adp) {
  if (picks.some((pick) => pick.id === id)) return null;
  let chosen = -1;
  let smallestGap = Infinity;
  picks.forEach((pick, index) => {
    if (pick.kind !== 'unseen') return;
    const gap = Number.isFinite(adp) ? Math.abs(index + 1 - adp) : index;
    if (gap < smallestGap) {
      chosen = index;
      smallestGap = gap;
    }
  });
  if (chosen < 0) return null;
  const next = picks.slice();
  next[chosen] = { kind: 'gone', id };
  return next;
}

// ---------- editing the log ----------
// "pick 22 (unseen)", "pick 40 (not in the list)", "pick 24 (Tyrese Maxey)": what a confirmation names. `nameOf` turns a
// player id into a name.
function describePick(picks, number, nameOf) {
  const entry = picks[number - 1];
  if (!entry) return `pick ${number}`;
  const what = entry.kind === 'unseen' ? 'unseen' : entry.kind === 'outside' ? 'not in the list' : entry.kind === 'gone' ? `${nameOf(entry.id)}, gone` : nameOf(entry.id);
  return `pick ${number} (${what})`;
}

function rosterNote(numbers, myPicks) {
  const mine = numbers.filter((number) => myPicks.includes(number));
  return mine.length ? ` This changes your roster: pick ${mine.join(' and pick ')} ${mine.length > 1 ? 'are' : 'is'} yours.` : '';
}

// The wording of a confirmation, built only for an edit that is allowed (a refused edit has nothing to describe).
function swapText(picks, a, b, myPicks, nameOf) {
  return `Swap ${describePick(picks, a, nameOf)} and ${describePick(picks, b, nameOf)}?${rosterNote([a, b], myPicks)}`;
}

function forgetText(picks, number, nameOf) {
  const entry = picks[number - 1];
  const returns = entry.kind === 'player' || entry.kind === 'gone' ? ` ${nameOf(entry.id)} goes back to the pool.` : '';
  return `Make ${describePick(picks, number, nameOf)} unseen?${returns}`;
}

function placeText(picks, from, to, nameOf) {
  const name = nameOf(picks[from - 1].id);
  return from === to ? `Confirm that ${name} was taken at pick ${to}?` : `Log ${name} at ${describePick(picks, to, nameOf)}? Pick ${from} becomes unseen again.`;
}

function chooseText(picks, number, id, myPicks, nameOf) {
  const entry = picks[number - 1];
  const was = entry.kind === 'player' || entry.kind === 'gone' ? ` ${nameOf(entry.id)} goes back to the pool.` : '';
  return `Log ${nameOf(id)} at ${describePick(picks, number, nameOf)} instead?${was}${rosterNote([number], myPicks)}`;
}

// Every edit takes 1-based pick numbers and returns {picks} or {error}, and none can produce a log the server would
// refuse: an unseen or gone entry never lands on one of the user's own pick numbers (`myPicks`). Edits make the
// history of Undo meaningless, so the page clears it after one.
function pickNumberError(picks, number, label) {
  if (!Number.isInteger(number) || number < 1 || number > picks.length) return `${label} must be a pick already in the log (1 to ${picks.length}).`;
  return null;
}

function canHold(entry, number, myPicks) {
  return !(['unseen', 'gone'].includes(entry.kind) && myPicks.includes(number));
}

// Pick `a` and pick `b` exchange what was logged at them.
function swapPicks(picks, a, b, myPicks) {
  const error = pickNumberError(picks, a, 'The first pick') || pickNumberError(picks, b, 'The second pick');
  if (error) return { error };
  if (a === b) return { error: 'Choose two different picks.' };
  if (!canHold(picks[a - 1], b, myPicks) || !canHold(picks[b - 1], a, myPicks)) {
    return { error: 'Pick ' + (myPicks.includes(a) ? a : b) + ' is yours: it cannot hold an unseen or gone pick. Log your own pick there.' };
  }
  const next = picks.slice();
  next[a - 1] = picks[b - 1];
  next[b - 1] = picks[a - 1];
  return { picks: next };
}

// "I do not know what pick N was": it becomes an unseen pick again, and a player logged there returns to the pool.
function forgetPick(picks, number, myPicks) {
  const error = pickNumberError(picks, number, 'The pick');
  if (error) return { error };
  if (myPicks.includes(number)) return { error: `Pick ${number} is yours, so you know what it was.` };
  if (picks[number - 1].kind === 'unseen') return { error: `Pick ${number} is already unseen.` };
  const next = picks.slice();
  next[number - 1] = { kind: 'unseen' };
  return { picks: next };
}

// Confirm a gone entry: the player was taken at pick `to`, which is an unseen pick or the pick he is marked at (the
// guess was right). The entry he was marked at becomes unseen again unless that is `to`, and he is now an ordinary
// player pick.
function placeGone(picks, from, to) {
  const error = pickNumberError(picks, from, 'The gone pick') || pickNumberError(picks, to, 'The new pick');
  if (error) return { error };
  if (picks[from - 1].kind !== 'gone') return { error: `Pick ${from} is not a gone entry.` };
  if (from !== to && picks[to - 1].kind !== 'unseen') return { error: `Pick ${to} is not an unseen pick, so nothing can be placed there.` };
  const next = picks.slice();
  next[from - 1] = { kind: 'unseen' };
  next[to - 1] = { kind: 'player', id: picks[from - 1].id };
  return { picks: next };
}

// "Choose the player": the pick at `number` was logged wrongly and `id`, a player still in the pool, replaces it.
// A player already logged elsewhere is a swap, which has its own control.
function choosePlayer(picks, number, id) {
  const error = pickNumberError(picks, number, 'The pick');
  if (error) return { error };
  const elsewhere = picks.findIndex((entry) => entry.id === id);
  if (elsewhere >= 0) return { error: `He is already logged at pick ${elsewhere + 1}. Use Swap with that pick.` };
  const next = picks.slice();
  next[number - 1] = { kind: 'player', id };
  return { picks: next };
}

// ---------- undoing ----------
// Undo reverts the last action, whatever it was. `history` lists the actions of this session, oldest first:
//   {type: 'log', count}   `count` entries were appended (one pick, or the unseen picks of one "I am behind")
//   {type: 'gone', index}  the unseen pick at `index` was resolved to a player known to be taken
// The history may be shorter than the log (a draft saved before it existed, or after an edit): with nothing left to
// undo in it, Undo removes the last entry, which is what it always did.

// A saved history kept only if it still describes the log; anything else is dropped.
function sanitizeHistory(raw, picks) {
  if (!Array.isArray(raw)) return [];
  let logged = 0;
  for (const action of raw) {
    if (!action || typeof action !== 'object') return [];
    if (action.type === 'log') {
      if (!Number.isInteger(action.count) || action.count < 1) return [];
      logged += action.count;
    } else if (action.type === 'gone') {
      if (!Number.isInteger(action.index) || !picks[action.index] || picks[action.index].kind !== 'gone') return [];
    } else {
      return [];
    }
  }
  if (logged > picks.length) return [];
  return raw.map((action) => (action.type === 'log' ? { type: 'log', count: action.count } : { type: 'gone', index: action.index }));
}

function unseenAgain(picks, index) {
  const next = picks.slice();
  next[index] = { kind: 'unseen' };
  return next;
}

// What Undo does next: {gone: index} turns a gone entry back into an unseen pick, {remove: n} drops the last n entries.
// Without a history a gone last entry still becomes unseen, so Undo never makes the log shorter than Yahoo's.
function nextUndo(picks, history) {
  if (picks.length === 0) return null;
  const last = history[history.length - 1];
  if (last && last.type === 'gone') return { gone: last.index, fromHistory: true };
  if (last && last.type === 'log') return { remove: last.count, fromHistory: true };
  if (picks[picks.length - 1].kind === 'gone') return { gone: picks.length - 1, fromHistory: false };
  return { remove: 1, fromHistory: false };
}

// The log and history after undoing the last action; null when there is nothing to undo.
function undoLast(picks, history) {
  const action = nextUndo(picks, history);
  if (!action) return null;
  const rest = action.fromHistory ? history.slice(0, -1) : [];
  if (action.gone !== undefined) return { picks: unseenAgain(picks, action.gone), history: rest };
  return { picks: picks.slice(0, picks.length - action.remove), history: rest };
}

// What the Undo button says it will do, because after an edit what Undo means changes.
function undoLabel(picks, history, nameOf) {
  const action = nextUndo(picks, history);
  if (!action) return 'Undo';
  if (action.gone !== undefined) return `Undo: Gone on ${nameOf(picks[action.gone].id)}`;
  if (action.remove > 1) return `Undo: ${action.remove} unseen picks`;
  const number = picks.length;
  const entry = picks[number - 1];
  const what = entry.kind === 'unseen' ? 'unseen' : entry.kind === 'outside' ? 'not in the list' : nameOf(entry.id);
  return `Undo pick ${number}: ${what}`;
}

// A gone entry back to an unseen pick, for a mistake noticed after other picks; null when it is not a gone entry.
function unmarkGone(picks, history, index) {
  if (!picks[index] || picks[index].kind !== 'gone') return null;
  return { picks: unseenAgain(picks, index), history: history.filter((action) => !(action.type === 'gone' && action.index === index)) };
}

// What a pending settings change would do, in words, so the confirmation names it. `labels` maps a category key to
// its short name; the result is empty when nothing differs.
function settingChanges(current, proposed, labels) {
  const changes = [];
  const name = (key) => labels[key] || key;
  const dropped = current.categories.filter((key) => !proposed.categories.includes(key));
  const added = proposed.categories.filter((key) => !current.categories.includes(key));
  if (dropped.length) changes.push(`leave out ${dropped.map(name).join(', ')}`);
  if (added.length) changes.push(`count ${added.map(name).join(', ')}`);
  if (current.method !== proposed.method) changes.push(proposed.method === 'capped' ? 'cap scores at the top 5%' : 'reward big numbers');
  if (current.gamesAdjusted !== proposed.gamesAdjusted) changes.push(proposed.gamesAdjusted ? 'count games missed' : 'ignore games missed');
  if (current.needs !== proposed.needs) changes.push(proposed.needs ? 'favour the categories you can still win' : 'weight every category equally');
  const ruleNames = { baseSd: 'early-round spread', sdPerAdp: 'spread per ADP place', threshold: 'plan-on odds', slack: 'ADP window' };
  if (current.rule.type !== proposed.rule.type) changes.push(proposed.rule.type === 'window' ? 'judge availability with the ADP window' : 'judge availability with odds from ADP');
  for (const [key, label] of Object.entries(ruleNames)) {
    if (current.rule[key] !== proposed.rule[key]) changes.push(`set the ${label} to ${proposed.rule[key]}`);
  }
  return changes;
}

// ---------- the Score bar ----------
// A bar is as long as a player is good, from the lowest score left (a short sliver) to the best (full). Three earlier
// versions failed, so the rules are: nobody saturates (a better score is always a longer bar: calling the 5th best "full"
// gave 71.3 and 52.0 the same bar) and nobody vanishes (a fixed span of points, or calling the 60th best "empty", left
// real players with no bar at all). The cost is that early in a draft, when the best scores are far above the rest, most
// bars are short; they still differ.
const SCORE_BAR_MINIMUM = 0.05; // the lowest score left still shows this much bar

function scoreBarAnchors(scores) {
  const present = scores.filter((score) => score !== null && score !== undefined);
  if (present.length === 0) return { ceiling: 1, floor: 0 };
  return { ceiling: Math.max(...present), floor: Math.min(...present) };
}

// SCORE_BAR_MINIMUM to 1: how much of the bar a score fills
function scoreBarShare(score, anchors) {
  if (anchors.ceiling <= anchors.floor) return 1;
  const along = Math.max(0, Math.min(1, (score - anchors.floor) / (anchors.ceiling - anchors.floor)));
  return SCORE_BAR_MINIMUM + (1 - SCORE_BAR_MINIMUM) * along;
}

// A projection that differs from last season's score by at least this many points is called better or worse; a smaller
// gap is noise (the scale is 0 at the 5th percentile of a category and 100 at the 95th)
const SCORE_TREND_POINTS = 5;

// 'up' when the projection beats last season, 'down' when it is worse, 'same' inside the noise, null without last season
function scoreTrend(delta, threshold = SCORE_TREND_POINTS) {
  if (delta === null || delta === undefined || Number.isNaN(delta)) return null;
  if (delta >= threshold) return 'up';
  if (delta <= -threshold) return 'down';
  return 'same';
}

// How a stat is marked, from its 0-100 score in the category: only strong values get a capsule, weak ones are muted
function statLevel(score) {
  if (score === null || score === undefined || Number.isNaN(score)) return '';
  if (score >= 80) return 'strong';
  if (score >= 60) return 'mid';
  if (score < 25) return 'weak';
  return '';
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { sanitizeRules, ruleText, clampRuleValue, sanitizeRule, normalizePicks, pickSavedState, planBehind, markGone, sanitizeHistory, undoLast, unmarkGone, swapPicks, forgetPick, placeGone, choosePlayer, describePick, swapText, forgetText, placeText, chooseText, undoLabel, chooseSource, discardsUnconfirmed, settingChanges, scoreBarAnchors, scoreBarShare, scoreTrend, statLevel, PICK_KINDS };
}
