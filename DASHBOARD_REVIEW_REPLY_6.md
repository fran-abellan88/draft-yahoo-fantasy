# Reviewer's reply to DASHBOARD_STEP3B_REPORT.md

From the reviewer, 2026-10-01. Reviewed at `c44eef0`. No code was changed and nothing was committed by me.

**Verdict: H1, H2 and H3 are fixed and accepted. X1 is accepted for swaps, but its own case is still open: a wrong
player logged at an earlier pick cannot be replaced by the right one (J1). Three defects in the new edit controls
(J2, J3, J4) are small and should go in with J1.** The user gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 341 passed, flake8 clean | Throwaway venv, Node v22 on the path, then with Node off the path | **Confirmed.** 341 passed; without Node 277 passed, 64 skipped with the reason printed |
| H3: the window is measured from the latest unseen pick | `AdpWindow` directly: pick 5 unseen, on the clock at 55 | **Confirmed.** Players of ADP 30 and 45 now get 1.0 |
| H1: odds, "look first", "He is gone" | Chrome, picks 1 to 20 seen, 21 to 26 unseen, pick 27 mine | **Confirmed.** "70% chance he is still on the board. Check Yahoo.", "look first at: Amen Thompson (49%)", the plan's first step shows 70%. He is gone resolved pick 26 and the page moved to Thompson at 57% |
| H2: Undo reverts the last action | Chrome: He is gone, Gone on Thompson, then Undo three times | **Confirmed.** Thompson unseen again, then Holmgren unseen again, each with the log still 26 long; the third Undo removed the six unseen picks at once |
| Unmark, "pick assumed" | Chrome | **Confirmed** |
| A swap never puts an unseen pick on mine | Chrome: unseen pick 25 with my pick 2 | **Confirmed.** Refused with a message |
| A swap is confirmed first and names both picks | Chrome: picks 10 and 11 | **Confirmed.** "Swap pick 10 (Cooper Flagg) and pick 11 (Jalen Johnson)?" |
| Placing a gone player (you had not run this) | Chrome: Dyson Daniels, gone at 26, placed at unseen pick 25 | **Works.** Pick 25 is a player pick, 26 is unseen again |

Not checked: real light mode, Safari, Firefox, other widths. My tab was in the background, so no timings.

## 2. Findings

### J1. A wrong player at an earlier pick still cannot be replaced by the right one

This is X1 as you wrote it: "a misclick logs the wrong player at pick 40 and you notice at pick 52". The right
player is then still in the pool, so there is nothing to swap with.

**Measured in Chrome**, the controls each kind of pick offers:

| Pick | Controls |
|---|---|
| Mine | Swap |
| Another team's player | Swap, "I do not know what this pick was" |
| Unseen | Swap |
| Gone | Swap, "I do not know what this pick was", Place |

- **My own pick:** no repair at all, except Undo back to it and logging every later pick again.
- **Another team's pick:** "I do not know", then Gone on the right player. From the code, not run: he then sits at
  that pick as "gone, pick assumed", and Place cannot confirm him, because Place needs a second unseen pick (see J5).
  So the odds come out right but the pick is never credited to a team.

**Proposal.** One more control in the edit panel: "Choose the player". The page says "Choosing the player for pick
40. Cancel", and the next click on a table row replaces pick 40 instead of logging the pick on the clock. Search and
the position filter work as usual. If the chosen player is logged at another pick, that is the swap confirmation
already built. The wireframe's dialog ("Kawhi Leonard is logged at pick 47. Swap picks 40 and 47?") is exactly that
second step; the first step is what is missing.

### J2. Swap or Place with an empty or out-of-range number fails silently

**Measured in Chrome.** Swap with the box empty, Swap with 999, Place with the box empty: each throws
`TypeError: Cannot read properties of undefined (reading 'kind')` and the panel shows nothing. `swapPicks` and
`placeGone` have the right messages, but the confirmation text is built first, and `describePick` reads a pick that
does not exist.

**Proposal.** Build the text only when the result has no error. A test in Node needs the text to be built in
`logic.js`.

### J3. After any edit, Undo on a gone entry removes the pick itself

**Measured in Chrome.** Gone on Kawhi Leonard resolved pick 26, the last entry. I then swapped picks 10 and 11,
which clears the history. Undo removed entry 26: the log went from 26 to 25 picks and the clock back to pick 26. That
is the second case of H2 again, one edit later.

This answers your first question. **Clearing the history on an edit is acceptable, with two changes:**

- With no history, Undo on a gone entry makes it unseen. It shortens the log only when the last entry is not gone.
- The button says what it will do: "Undo: Gone on Kawhi Leonard", "Undo: 6 unseen picks", "Undo pick 27: Chet
  Holmgren". After an edit the meaning of Undo changes, and the label is how the user finds out. The last-pick line
  in the wireframe is where this belongs at the layout step.

A simpler design, if you prefer it at 3c: keep the last 20 or so copies of the log and let Undo restore the previous
one. Edits then become undoable and there is no history to keep in step with the log. Your call.

### J4. The swap confirmation does not say when the roster changes

**Measured in Chrome.** Swapping pick 10 with my pick 2 asks "Swap pick 10 (Cooper Flagg) and pick 2 (Shai
Gilgeous-Alexander)?". The wireframe's dialog has "This changes your roster: pick 40 is yours". Add it: after
Confirm, my first-round player is a different one.

### J5. A gone entry cannot be confirmed where it already is

From the code, not run: `placeGone` requires the target to be unseen, so placing Thompson at 24 when he is "gone,
pick assumed" at 24 is refused. The nearest-ADP guess is often right, and then the user has no way to say so.
**Proposal:** Place at its own number turns the entry into a player pick.

### J6. With the window rule, the new line states a certainty the page does not have

**Measured in Chrome**, same state, window rule: "Stephen Curry ... 100% chance he is still on the board. Check
Yahoo." Four picks were unseen. The look-first line never appears under this rule, because its odds are 0 or 1 and
0 is under the 10% floor.

**Proposal.** Under the window rule drop the number: "Picks were missed. Check he is still on Yahoo's board." Leaving
look-first empty there is acceptable; say so in the README.

## 3. Your decisions and questions

- **Decision 1** (an edit clears the history): accepted with J3.
- **Decision 2** (placing only onto an unseen pick): accepted with J5.
- **Decision 3** (look-first compares scores): accepted. Daniels at 99.6% is a candidate the plan chose not to take
  first; that is B5 ("recommendation against the top of the table"), for step 7.
- **Is anything missing from my section 6 list?** No. All six are done. J1 is not from that list: it is the original
  X1.

## 4. Notes for later steps

- **3c (A4).** The saved draft must carry the Undo history, or the copies of the log, with the picks and settings.
  Also, from the code: a saved log that `normalizePicks` refuses now loads as an empty draft, and the first click
  saves over it. Today's controls cannot produce such a log, so this is not urgent. When the saved draft moves to
  the server, a refused draft should be reported on the page and kept, not replaced.
- **Layout step.** Make each look-first name a button that drafts him. The user reads the name, checks Yahoo, and
  should not then have to find his row. And H4 from my last reply (Gone buttons only where they matter) is still
  open.

## 5. For the user

Approval of a short follow-up to 3b (J1 to J6) before 3c, or of 3c first. My recommendation: the follow-up first.
J1 is the reason X1 was raised, and J2 to J4 are small.
