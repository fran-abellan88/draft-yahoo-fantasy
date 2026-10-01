# Step 3b report

From the builder, 2026-10-01. For the reviewer. The earlier commits are pushed (the user asked for it); these are not.

Approved by the user: 3b with H1 and H3. **Not started: 3c (F3, A4) and layout code (step 6).**

Suite: **341 passed**, flake8 clean (with Node on the path; skipped count: 0).

| Commit | Finding | What it does now |
|---|---|---|
| `72211e1` | H3, notes | On the clock the window rule is measured from the latest unseen pick. Test docstring reworded; module notes say the sum is not k with your measured ranges |
| `0c4546b` | H2 | An action history (`log` of n entries, `gone` at an index) is saved with the draft; Undo reverts the last action (Gone back to unseen; a whole "I am behind" at once). With no history it pops the last entry as before. Unmark on gone entries. Log text says "pick assumed" |
| `00a7bf7` | X1, 3b additions | Edit on each log row: swap (confirmation names both picks with their kind), "I do not know what this pick was" (unseen; player returns to the pool), place a gone player at an unseen pick. `normalizePicks` takes my pick numbers and refuses a saved log with unseen/gone on one. Edits clear the history |
| `3670041` | H1 | The server sends `lookFirst` (my turn, unseen picks, better score than the recommendation, odds 10% to under the threshold, up to 3). The page shows "N% chance he is still on the board. Check Yahoo.", the look-first line, a **He is gone** button, and the odds in the plan's first step |

Checked in Chrome (page defaults, picks 1-20 seen, 21-26 unseen): the hero shows 70% for Holmgren and "look first at: Amen Thompson (49%)"; He is gone gives Thompson at 57%; Undo makes pick 26 unseen again with the log still 26 long; a swap of unseen 24 with my pick 2 is refused with a message; swapping 24 with pick 10 asks, then moves Cooper Flagg to 24 and leaves 10 unseen; no console errors.

Decisions of mine to challenge:
1. An edit clears the Undo history instead of recording itself. Simpler and safe; the cost is that an edit cannot be undone except by editing back.
2. Placing a gone player only works onto an unseen pick; "edit an unseen pick into a player logged as gone" is that same move from the other side, so there is no separate dialog.
3. `lookFirst` compares scores, not plan value, as you said, and does not exclude players the optimizer left out for lineup reasons (Dyson Daniels, 47.1 at 99.6%, is not listed because his odds are above the threshold).

Not verified: real light mode, Safari, Firefox, other widths, foreground timings. Not exercised in a browser: the "place a gone player" form.
