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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { clampRuleValue, sanitizeRule, normalizePicks, pickSavedState, planBehind, markGone, sanitizeHistory, undoLast, unmarkGone, swapPicks, forgetPick, placeGone, choosePlayer, describePick, swapText, forgetText, placeText, chooseText, undoLabel, PICK_KINDS };
}
