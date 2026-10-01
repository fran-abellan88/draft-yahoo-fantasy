# Step 3a-1 report, and the first wireframe

From the builder, 2026-10-01. For the reviewer. Nothing is pushed.

Approved by the user: 3a-1 (F1, F2, F4, F5 and clamping saved and typed rule values) and the minimum wireframe. **Not
started, because it is not approved yet: 3a-2, 3b, 3c.**

Suite: **250 passed** (213 after step 2), flake8 clean, golden fixture untouched. One commit per item.

## What changed

| Commit | Finding | What it does now |
|---|---|---|
| `5a2907a` | F1, (b) | While waiting for my pick, the alternatives are planned **without the recommended player at any of my picks**; on the clock he stays in. The page says "If X is gone by pick N, take instead" or "Or take instead". The line is hidden when the search was cut short and when every alternative ties with the best plan |
| `0d8ad38` | F5 | The answer reports the main search and the busiest single first-pick search; the budget test asserts on the tighter first-pick cap |
| `9e4a20b` | F2, F4 | A row clicked while the reply is later than 200 ms is marked "Logging the pick", then becomes "not confirmed" if the retries fail. The comment that mentioned a note is corrected |
| `164ed5b` | (a) | The server's limits table is the only place the allowed rule values are written; `/api/pool` sends it. Saved values are put back in range on load, typed values on change, and the box shows what is being used. A blank box becomes the default, not 0 |

Also new: `fantasy_draft/web/logic.js`, a pure-JavaScript file with the clamping, and `tests/test_page_logic.py`, which
runs it under Node (skipped when Node is not installed). This is my answer to your remark that a migration written only
in `app.js` is out of pytest's reach: step 3's pick-shape migration can live in the same file.

## F1 in detail

`plan_picks` now computes `assumed_gone` (the recommended player when my first pick is later than the pick on the clock,
else none) and removes him from the candidate lists of the later picks in each option search. The options never include
the recommended player as a first pick any more. `behind` is no longer clamped at 0: an option can only beat the best
plan if the search was cut short, in which case the line is hidden; float noise around zero is rounded away. A
search with an empty candidate list (possible once a player is removed) returns no plan instead of failing.

Tests: brute force for both modes on small pools (the waiting form compared against a brute force that excludes him
from later picks, the on-the-clock form against one that does not); and a walk over 111 states of an ADP-order draft at
the page defaults asserting that in every waiting state no alternative plan contains the recommended player and no
alternative beats the best plan.

Measured separately over the same 111 ADP-order states, counting only the 103 waiting states (an on-the-clock option may
legitimately contain him): the old option searches (`682b3b2`) priced 515 alternatives and **91 of them (18%) still
contained the recommended player**; the new code prices 618 and **none do**. These counts differ from your 98 of 555
because I leave out the 8 on-the-clock states and no longer count the recommended player's own option.

## F5 in detail

Nodes at the page defaults over every state of the ADP-order draft:

| Settings | Main search, max (budget 150,000) | Busiest first-pick search, max (budget 30,000) |
|---|---|---|
| uncapped, games adjusted (page default) | 4,393 | 1,314 |
| capped, games not adjusted | 15,171 | 11,295 |

Both are below half their budgets, which the test asserts. Your sweep found 15,471 and 11,911, so the numbers agree to
within the changes I made to the option searches.

## Verified in Chrome

- Seeded `localStorage` with `{baseSd: 0, sdPerAdp: 5, threshold: 9, slack: -3}` and reloaded: no error banner, the
  inputs show 0.1, 1, 0.95 and 0, and the page loads.
- Typed an empty box (becomes 2), 99 (becomes 20) and -5 in the threshold (becomes 0.05); the request is accepted.
- With a 1.5 s reply, the clicked row shows "Logging the pick" once the busy state starts, and the mark is gone after
  the reply. **I called `showBusy()` directly to make the 200 ms threshold deterministic**, because my tab throttles
  timers. The threshold itself you confirmed in a foreground window.

## Not verified

- Real light mode, Safari, Firefox, windows narrower than 1624 px (unchanged).
- The dim and "Logging" mark on a real 200 ms boundary in my own browser (see above).

## Where I made a call you may want to overrule

- **Hide rule.** The alternatives line is hidden when every alternative is within 0.05 points of the best plan, not only
  when they are exactly equal. Rounding to one decimal made 0.0 and "same" the same thing for a user.
- **Option count.** The options now take the top six candidates other than the recommended player (it used to be six
  including him). Same cost, one more real alternative.
- **`logic.js` and Node.** An optional test dependency for JavaScript is new. If you would rather have no Node
  dependency, the alternative is to keep all logic in Python and send the page only data. Say if you prefer that.

## The wireframe

`DASHBOARD_WIREFRAME.md`. As agreed: waiting and on-the-clock at 960, 1280 and 2560 px, with the 14-team panel (E2),
the settings summary and button (C10) and the mode indicator (E3) as labelled boxes already in the shell; a table of
what drops out at each width; and the two states step 3 creates (unseen picks present, the swap dialog). Three
questions for the user are at the end of the file; I added a design rule the reviewer may want to challenge: below about
1900 px panels become tabs, not rows under the table, so nothing a user needs is ever 1,500 px down the page (B2).

## What I would like your opinion on

1. F1: is the "gone" definition right? I treat "waiting" as my first remaining pick being later than the pick on the
   clock. A different reading: also treat a player as possibly gone if the availability model gives him under 50% at my
   pick, even on the clock. I did not, because on the clock he is visibly on the board.
2. The hide rule threshold of 0.05 points.
3. The wireframe: regions, what drops out, the tabbed 960 px layout, and whether anything planned is missing a box.
4. Whether `logic.js` under Node is acceptable for page logic.
5. Whether 3a-2 can start in the order you gave: schema v2 with the server accepting both pick shapes, then the
   outside-the-list kind, then the availability change, then the unseen kind.
