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
function normalizePicks(raw, knownIds) {
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

// The log and history after undoing the last action; null when there is nothing to undo.
function undoLast(picks, history) {
  if (picks.length === 0) return null;
  const last = history[history.length - 1];
  if (last && last.type === 'gone') return { picks: unseenAgain(picks, last.index), history: history.slice(0, -1) };
  if (last && last.type === 'log') return { picks: picks.slice(0, picks.length - last.count), history: history.slice(0, -1) };
  return { picks: picks.slice(0, -1), history: [] };
}

// A gone entry back to an unseen pick, for a mistake noticed after other picks; null when it is not a gone entry.
function unmarkGone(picks, history, index) {
  if (!picks[index] || picks[index].kind !== 'gone') return null;
  return { picks: unseenAgain(picks, index), history: history.filter((action) => !(action.type === 'gone' && action.index === index)) };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { clampRuleValue, sanitizeRule, normalizePicks, pickSavedState, planBehind, markGone, sanitizeHistory, undoLast, unmarkGone, PICK_KINDS };
}
