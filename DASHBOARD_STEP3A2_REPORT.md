# Step 3a-2 report

From the builder, 2026-10-01. For the reviewer. Nothing is pushed.

Approved by the user: 3a-2, the revised wireframe, and "implement what you think is best" for the three wireframe
questions (tabs at 960 px; a last-pick line with Undo and the log as a tab; the wireframe as the basis for the layout
step). **Not started, because it is not approved: 3b (X1), 3c (F3, A4), and any layout code (step 6).**

Suite: **326 passed** (250 after 3a-1), flake8 clean, golden fixture untouched. 53 of those run under Node.

## What changed, in the agreed order

| Commit | Finding | What it does now |
|---|---|---|
| `cef18d8` | schema v2 | A pick is an object `{kind, id?}`. The server accepts a plain id or an object; the page stores `draft-assistant-v2` and reads `draft-assistant-v1` once if v2 is absent, never rewriting it. Migration and validation are in `logic.js`, tested under Node |
| `84b3b54` | outside the list | `Pick not in the list` logs a pick of a player outside the 150. Others' outside picks advance the counter; mine fill one starting slot at **any position, replacement-level value** (the optimizer matches him with the all-positions mask). Exact against brute force |
| `ecab1cd` | availability (G1) | `probability(adp, pick, picks_made, unseen)`: the product, over every unseen or future pick before `pick`, of the chance of surviving it given survival of the ones before. Consecutive picks telescope into one factor per run. With no unseen picks it equals the old formula (tested against an independent copy of it) |
| `30c2a57` | unseen and gone | Kinds `unseen` and `gone`; never on my own pick numbers (server refuses, page stops before one); `I am behind` / "Yahoo is at pick N"; `Gone` button on rows; unseen note; log and roster labels |
| `62c7bfe` | G3 | `pytest.ini` has `-rs`, so a skipped Node test prints with its reason; README says to check that line |
| `981e7d2` | docs | README describes the three new controls |

## Decisions I took, for you to challenge

1. **No normalisation of the availability model.** You measured 7.5 players gone for 6 unseen picks. I get **5.7 for
   6** (0.95), 9.8 for 10 (0.98), 9.4 for 10 later in the draft (0.93), 2.55 for 3 (0.85) with the default model on the
   real pool, and 5.8 and 6.1 for the other two spreads I tried. The test asserts the sum stays between 0.8 and 1.15 of
   the number of unseen picks. Two possible reasons for the difference: I take the pool as everyone except the first
   `n` by ADP, which is exactly the set the seen picks removed; if you measured against a different pool, the sum can
   differ. Please re-check with `tests/test_availability.py::test_the_expected_number_of_players_gone...` and tell me if
   your setup was different, because that is the one number where we disagree.
2. **Which unseen pick "Gone" resolves.** Your note said marking removes one unseen pick from the product; it did not
   say which. I first resolved the earliest, and the browser showed it was wrong: marking a player of ADP 24 changed
   nobody's odds (0 players), because pick 5 only matters to players near ADP 5. It now resolves the **unseen pick
   closest to his ADP**. In Chrome: Amen Thompson (ADP 23.6) resolved pick 24, and the odds of 31 nearby players rose
   (Murray 0.168 to 0.204, Holmgren 0.593 to 0.631), none fell. Tested in `logic.js`.
3. **`gone` is its own kind**, not a player pick. It leaves the pool and counts as a pick made, but credits no team
   (for E2). It cannot be mine.
4. **Seen picks contribute exactly nothing**, as you corrected me. Not conservative: exact.
5. **AdpWindow with unseen picks.** On the clock with unseen picks, the window rule now applies its normal window
   instead of "everyone is available", so a player with ADP well before the pick is treated as gone. For later picks it
   already did.
6. **"Yahoo is at pick N" can stop early.** If a pick of mine lies in the gap, the page adds the unseen picks before it
   and says to log mine first, then press again for the rest. Picks beyond 182 or not ahead of the log are refused with a
   message.
7. **Reset and Undo.** Undo pops the last entry of any kind. Undoing a `gone` in the middle of the log is not possible
   (it is not the last entry); that is what X1 (3b) is for.

## What I verified in Chrome

- A saved v1 draft of three bare ids loads as three player picks; the v1 key is unchanged. (The v2 key is written on
  the first change, not at load.)
- `Pick not in the list` at pick 4: the log says "Not in the list", the pool keeps its 147 players, the clock moves to 5.
- `I am behind` with 4 at pick 5: refused, "not ahead of the next pick". With 31 at pick 5: 22 unseen picks (5 to 26),
  stopped before my pick 27, form left open; after logging 27, 31 again adds 28 and 29 and stops before 30.
- The unseen note shows; 147 `Gone` buttons appear; a keydown on one does not log the row; a click logs no pick (the
  log keeps its length) and shows "Amen Thompson (gone, pick unknown)".
- No console errors.

## Not verified

Real light mode, Safari, Firefox, widths other than my window, a foreground-tab timing of the 200 ms mark. Also not
exercised in a browser: swapping settings while unseen picks are outstanding.

## Open points I would like your view on

1. **The 0.95 against your 7.5** (decision 1 above).
2. **Resolving the unseen pick nearest the ADP** (decision 2). An alternative is to ask the user which pick he was
   taken at; I think that is too much to ask under a clock.
3. **The `gone` entry sits at the pick number it resolved**, so the log reads "#24 Amen Thompson (gone, pick unknown)"
   while pick 5 is still "Unseen". Is that the right way to show it, or should gone entries be listed separately?
4. **Should `I am behind` be allowed while the search is cut short?** Nothing prevents it today.
5. **3b**: I plan the swap with confirmation as agreed, with "I do not know what pick N was" turning the later pick
   into an unseen one. Anything to add before the user approves it?
