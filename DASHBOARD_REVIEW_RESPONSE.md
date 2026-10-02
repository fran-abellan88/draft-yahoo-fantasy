# Response to DASHBOARD_REVIEW.md

Written by the agent that built the dashboard. No code has been changed; the only file added is this one.

## Test run (step 1)

| Check | Result |
|---|---|
| `pytest` (full suite, in a throwaway venv built from `requirements-dev.txt`) | **157 passed** in 3.7 s |
| `flake8` | clean |
| Working tree before this file | clean, on `feat/2026-27-projections` |

Why you could not run it: none of the interpreters on this machine has the dev requirements, and `python` is not on
the PATH. `/usr/bin/python3` has `pandas` but no `pytest`; python.org 3.11 has neither. The README says
`pip install -r requirements.txt`, but `pytest` itself and the `beautifulsoup4` that `tests/test_yahoo.py` and
`tests/test_verify.py` need are in `requirements-dev.txt`. With `pytest` present but not `beautifulsoup4`, those two
files fail to collect and 20 of the 157 tests do not run (137 pass). That is a README gap, listed below as X3.

## What I verified myself

You marked several findings "Read" or "Judgement". I did not take those on trust.

| Finding | How I checked | Result |
|---|---|---|
| A1 (first part) | Read `draft()` and `_parse_picks` | Confirmed: unknown ids are rejected on both sides |
| A2 | Ran `DraftService.analyze` with your reproduction, then instrumented a copy of `_search` | Cliff confirmed. **The cause is not what the review says** (see A2) |
| A3 | Read `refresh()`, then called `showError` in Chrome with the page scrolled to the table | Banner at -741 to -699 px, `position: static`. Failed-pick dead row confirmed by reading |
| A4 | Read `run_dashboard.py` and `saveState` | Confirmed. Also found a security issue that matters here (X2) |
| B3 | `getComputedStyle` in Chrome | `hidden` is true, `display` is `grid` |
| B4 | Read `availability.py:50-51` and `service.py` | Confirmed: `pick <= picks_made + 1` returns ones |
| B5 | My own first screenshot of the page, before any pick | Holmgren 46.1 at pick 27, Daniels 47.1 at pick 58 in the same plan. Same pattern |
| B6 | Read `renderHero` | Confirmed: `analysis.pool[0]`, no lineup check |
| C1 | Chrome | `aria-sort` is on the button, not the `th`; the header text has no arrow |
| C3, D6 | `grep` in `app.js` | `categoryScores`, `horizonDone`, `lastSeason` stats other than `gp` are never read |
| C4, C5, C6, C7 | Read `renderProfile`, `renderRoster`, `_alternatives`, `meter` | All confirmed, including the hard-coded `0.6` |
| C9 | Read `matchesFilters` | Single substring, confirmed |
| D2, D4, C4 colours | Computed WCAG ratios from the CSS tokens | 1.98, 1.11, 1.14, 2.69, 2.27, 4.24: all match the review |
| D5 | Chrome | 150 tab stops, 363 `title` attributes, no `<h1>`. Your 148 / 358 differ only because I had no rows drafted |
| E3 table | Re-ran the simulation from scratch (4,000 draws per row, seed 0) | 3.6 / 5.5 / 8.4 / 12.0 players wrongly removed; 1.5 to 1.9 of the next 5 already gone. **Reproduced** |

I could **not** verify the real window-width findings (B2). The Chrome window here is 1804 px wide and I cannot
resize it, so I checked only the arithmetic: 330 + 300 + 895 + 2 x 20 gaps + 2 x 20 padding = 1605 px, which matches
your 1607. The 1280 / 1281 edge is a CSS reading, not something I saw.

## Answers by finding

### P0

**A1. Agree, with a counter on the data shape.**
The placeholder is needed and it is P0 even at 8 rounds: today there is no way out if a manager takes someone outside
the top 150. Counter: do not add a string convention (`other:17`) on top of a list of ids. The same change must also
carry E3's "assumed" flag and X1's edit. Make a pick an object (`{kind: "player" | "unknown" | "assumed", id?}`) once, in
a new storage key `draft-assistant-v2` with a migration from v1, instead of three successive schema changes.
Pick numbers stay implicit from list position, so the snake guarantee in your "keep" list survives.

**A2. Agree on the problem. Counter on the cause and the fix.**
Reproduced: 5.5 to 7.6 s here (your 11.4 s and 2.8 s were another machine; my "all nine categories" case was the
slowest, yours the fastest, so the ordering is not stable and the fix must not depend on it). What I measured about the
cause, for the 26-pick wide-open case:

- All seven remaining picks get **the same 25 candidates**.
- At `topK=100` the search reached **499,653 full plans for only 179 distinct teams**: 2,791 orderings of the same
  players per team. De-duplicating plans as sets does not prevent the work, it only hides it.
- Time grows with `topK`: 1.6 s at 1, 3.1 s at 20, 5.7 s at 100, 8.1 s at 200.
- At `topK=1` there is one full plan and still 1.1 million search nodes, so the bound is also loose.
- Your suggested fix to the bound (count distinct players, which I prototyped in a scratch copy) gave **only 15%**
  (5.8 s to 4.9 s), with identical results. So a tighter bound of that kind is not the answer.

Proposal: (1) a node budget, not wall-clock, so results stay reproducible (about 150,000 nodes is about 0.2 s here);
when it is hit, return the best plans so far with `approximate: true` and say so on the page. (2) Cap `topK` by
rule: the page shows five plans and one frequency table, so 100 is more than it needs. (3) Presets from C10 and
tighter input limits. (4) Later, if wanted: search over sets of players and assign them to picks in a second step,
which removes the ordering explosion at its root. That is a rewrite of `_search`, so only if the budget proves to cut
too much. Busy state: agree.

**A3. Agree.**
Fixed banner with a Retry button. One refinement: retry automatically only on a network failure. A 400 means the
request is wrong and retrying changes nothing. Also keep the pick but mark it "not confirmed" in the table until the
server answers, so a failed pick is visible and not a dead row.

**A4. Agree on the problem, counter on the design.**
The server-side file is better than export and import, for your reason. Three conditions:
- The page remains the source of truth and the server stores a copy. Two browsers can both write, so the file needs a
  version counter, and on load the page asks ("The server has 14 picks from 21:40. Use them?") and never silently
  overwrites.
- Written by a dedicated `PUT /api/draft`, not as a side effect of `analyze`, which also runs on every settings click.
- It needs the security checks in X2 first.
Also print the port fallback in capitals; with the file, the port stops mattering.

### P1

**B1. Agree, with one counter.**
My own screenshot confirms it: the table starts below the visible plan. Agree with the app shell, the top bar and the
compact plan. Counter: keep the full hero on the user's turn, as you say, but build a wireframe and approve it before
code, because B1, B2, C2, C10 and the E panels all land on the same layout. A wrong guess here is the most expensive
mistake in the list.

**B2. Agree.**
The 1280 breakpoint is the wrong place for half of a 2560-px desktop, which is the likely case for a 32-inch monitor
at 150% scaling. Counter: no hard "4 columns above 1900". Use a fluid grid with minimum panel widths (auto-fit), so
panels appear as width allows. Test at 960, 1280, 1720, 1920 and 2560 in a real window once the monitor exists.
Open point 1 applies: I need the user's `innerWidth`.

**B3. Agree.** Verified, one line.

**B4. Agree.**
When on the clock, show availability at the following pick, and name the pick in the header. Counter on the small
bar: the table is already dense (C2), so colour the number instead and keep bars for the plan.

**B5. Agree.** Required once E1 exists. The "plan: 58" marker in the table is the most useful part.

**B6. Agree.**
Wording now. For "best available", use the same `all_masks_can_start` test the planner uses, in `service.py`.

### P2

**C1. Agree.** Verified.

**C2. Agree.** One line per player; keep badges but make them compact.

**C3. Partly agree, counter on the "value" column.**
Tint by category score: agree. Dim unticked columns: agree. A column of "ADP rank minus score rank" is a
different matter. Our uncapped score puts Giannis 43rd against an ADP of 7.5, because of FT%, and that is a punt
candidate. A column called "value" would call him a bad pick on a basis the user may reject. Call it "Rank vs ADP",
compute it from the currently ticked categories, and keep the wording neutral. Same warning as in the C10 comparison.

**C4. Agree.** E2 supersedes it; fix the number and colour problems anyway.

**C5. Agree, counter on method.**
A single slot assignment is not unique, so showing "who fills which slot" can mislead. Show, for each position,
whether one more player of that position still fits (using the matching), plus the count of open starting slots.

**C6. Agree.**
Verified: the share is a fraction of the top-100 plans. Show the fallback and its cost from the plans already
returned. Only first picks that appear in those plans can be listed, which is fine.

**C7. Agree.**
Remove the product of odds, and use the user's planning threshold for the amber colour instead of the literal 0.6.

**C8. Agree, P3.**

**C9. Agree, with a counter on Enter.**
Token matching and "taken at pick 3" are right. For several matches, arrow keys plus Enter beat a "keep typing"
message; do both cheaply.

**C10. Agree, with three counters.**
Panel, summary line and lock: agree. (1) A "rank change vs the other setting" column in the table is clutter and
risks being read as "which is right"; make it a short "biggest movers" list inside the settings panel. (2) The
availability presets must be labelled with their numbers: "managers follow ADP closely" suggests knowledge we do
not have, since the spreads are uncalibrated until the real draft arrives. (3) Lock after the first pick, with an
explicit unlock: agree.

### P3

**D1. Agree.** **D2. Agree** (ratios verified). **D3. Agree.** **D4. Agree** (hover plus an undo toast).
**D5. Agree, low priority**; arrow-key row navigation first. **D6. Agree**: use `categoryScores` (C3) and drop the
rest. **D7. Agree**: Yahoo's own label is 3PTM, so use that everywhere. **D8. Agree, defer**: a draft log with the
slot is cheap, but only worth doing when runs on a position become a real question.

### E

**E1. Agree with the direction. Counter on order, inputs and scale.**
The marginal-chance-of-winning rule is the right idea. Four problems I would settle first.

1. **Compare projected teams, not current partial teams.** With one or two picks, the standings are an artefact of
   who was drafted. The weights should be computed from projected final rosters (drafted + planned for me, drafted +
   filled for the others). That makes E3's projection a prerequisite of E1, not a later extra.
2. **Weekly spread is an assumption.** The chance of winning a category depends on the weekly variance of each
   statistic, and we have no weekly data. Counting stats (3PM, steals, blocks) are noisier than points. I would start
   with the empirical share of the other 13 projected teams that I beat (no variance needed), smooth it, and take its
   slope. State this clearly on the page.
3. **Units.** The weight has to multiply the normalised player score, so I need to derive how a team-total gap
   translates into a standardised unit. Normalise the weights to a mean of 1 across ticked categories so the score
   scale does not change.
4. **No way to check it.** There are no historical drafts and no weekly results here, so the only test is rehearsal
   (E3). Ship E1 behind a switch, off by default, until rehearsals show it behaves sensibly.

I agree with your ramp, with punts staying explicit and with showing the weights.

**E2. Agree, with two counters.**
(1) For FG% and FT%, compare the real team percentage (sum of makes over sum of attempts), not the sum of impact
values. Impact is a good linear way to rank players, but a matchup compares percentages, and two teams with
different attempt volumes can rank differently under the two measures. (2) Show two readings, as you suggest, but
define them: "so far, at n players each" and "projected, at 8 players each", and label which one is on screen.
Placeholders and unknown picks count as replacement level, labelled.

**E3. Agree with the hybrid, counter on catch-up.**
The simulation is reproduced. Two caveats on its meaning: the drift is measured under the tool's own uncalibrated
model, and the mock draft you gave us was mostly automatic picks that tracked ADP closely. So the real drift may be
smaller or larger; the shared real draft will tell. Rehearsal and projection: agree, generated in Python from the
availability model with a seed. Catch-up: **counter.** Filling missed picks with ADP-ordered players is precisely the
biased step, and it turns a gap in knowledge into false precision. Cheaper and more honest: let the user log "N
picks I did not see" as unknown picks (the same mechanism as A1), plus a "mark as gone" action on any row. The
model already conditions on the number of picks made; it does not need names to do that. If you want assumed
names anyway, I would build it after the rest and make it opt-in.

## Additional findings of mine

**X1. A mistaken earlier pick cannot be corrected.** Only the last pick can be undone. If a misclick logs the wrong
player at pick 40 and you notice at pick 52, the only repair is to undo twelve picks. Propose: edit or replace any
logged pick from the draft log, and recompute. With the schema in A1 this is a small change.

**X2. The server accepts any caller, which matters before A4.** Measured with `curl`: `POST /api/analyze` returns 200
with `Content-Type: text/plain`, with `Host: evil.example` and with `Origin: https://evil.example`. There are no
CORS headers, so a foreign page cannot read replies, but a plain text POST needs no preflight, and DNS rebinding is
a way around the read restriction. Today the endpoint only computes, so the risk is small. A4 adds a write endpoint,
so first: require `Content-Type: application/json` (forces a preflight), accept only `Host` values of
`127.0.0.1:<port>` and `localhost:<port>`, and reject a foreign `Origin`. A few lines in `server.py` and three tests.

**X3. README gap.** Say that `pytest` needs `requirements-dev.txt`, and show `python3 -m pytest`.

## Proposed implementation order

Each step is committed on its own and left unpushed until you say otherwise.

1. **Quick, independent fixes**: B3, D2, D3, C1, D7, A3, X3.
2. **Server safety**: X2, then A2 (node budget, `topK` cap, busy state, input limits).
3. **State**: schema v2 with pick objects and migration, then A1 (placeholder), X1 (edit a pick) and A4 (server copy
   with version counter and a confirm on load).
4. **Engine for the 14 teams**: E2, with real FG% / FT% ratios and the two readings. Replaces the C4 panel.
5. **E3 projection and rehearsal** in the Python core (seeded, lineup-legal), plus the always-visible mode indicator.
6. **Layout**: ASCII wireframe for your approval first, then B1, B2, C2, C10, with the E2 and E3 panels in the design.
7. **Workflow items**: B4, B5, B6, C3, C5, C6, C7, C9, D4, D6.
8. **E1**, behind a switch, once steps 4 and 5 give it real inputs.
9. **P3 leftovers**: D1, D5, D8, C8, and E3 catch-up if still wanted.

I would change one thing from the review's suggested order: E3's projection comes before E1, not after.

## Questions I need answered

1. What is the dashboard window's `innerWidth` on the real monitor (B2)?
2. Do you want the unknown-picks approach for catch-up, or assumed names (E3)?
3. May I start with step 1, or do you want to discuss anything above first?
