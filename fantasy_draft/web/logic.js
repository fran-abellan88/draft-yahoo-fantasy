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

if (typeof module !== 'undefined' && module.exports) module.exports = { clampRuleValue, sanitizeRule };
