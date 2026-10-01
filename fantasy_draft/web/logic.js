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
// ids under another storage key. Both are read here, so a draft saved by an older page is not lost. `outside` is a
// pick of a player who is not in the pool. Other kinds are added to PICK_KINDS as they are built.
const PICK_KINDS = ['player', 'outside'];

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
    if (kind === 'player') {
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

if (typeof module !== 'undefined' && module.exports) module.exports = { clampRuleValue, sanitizeRule, normalizePicks, pickSavedState, PICK_KINDS };
