# Reviewer's reply to DASHBOARD_STEP3B2_REPORT.md

From the reviewer, 2026-10-02. Reviewed at `87cbd8c`. No code was changed and nothing was committed by me.

**Verdict: J1 to J6 are fixed and accepted. X1 is closed: a wrong pick can now be replaced, on my own picks too.
"Choose the player" has three rough edges (K1 to K3), one of which answers your question. None blocks 3c; K1 and K2
should be fixed before the real draft.** The user gives the approvals, not me.

## 1. What I checked

| Finding | How I checked | Result |
|---|---|---|
| Suite | Throwaway venv, with Node and with Node off the path | **Confirmed.** 347 passed, flake8 clean; without Node 278 passed, 69 skipped with the reason printed |
| J1 | Chrome: my pick 2 replaced by Stephen Curry, found with the search box | **Confirmed.** The note stays up while I type in the search; Shai returns to the pool; pick 2 is Curry |
| J1 on an unseen pick | Chrome: unseen pick 25, chose Kawhi Leonard | **Confirmed.** Pick 25 is a player pick. This also gives an exact way to fill unseen picks, which Gone did not |
| J2 | Chrome: Swap with an empty box and with 999, Place with an empty box | **Confirmed.** "The second pick must be a pick already in the log (1 to 26)." No console error |
| J3 | Chrome: Gone on Kawhi Leonard at pick 26, a swap of picks 10 and 11, then Undo | **Confirmed.** The button read "Undo: Gone on Kawhi Leonard"; the log stayed 26 long; then "Undo pick 26: unseen" |
| J4 | Chrome: swap of pick 10 with my pick 2 | **Confirmed.** "... This changes your roster: pick 2 is yours." |
| J5 | Chrome: Thompson gone at 24, Place at 24 | **Confirmed.** Pick 24 is a player pick |
| J6 | Read the code and the README; not run this time | Reads correct |

Not checked: real light mode, Safari, Firefox, other widths. My tab was in the background, so no timings.

## 2. Findings

### K1. After a row is clicked, the confirmation appears where the user is not looking

**Measured in Chrome**, window 1804 x 1043, choosing for pick 10, row 31 of the table centred and clicked: the note
"Choosing the player for pick 10" disappears and "Log Alex Sarr at pick 10 (Jalen Johnson) instead? Confirm" appears
in the log panel, 1 px below the bottom of the window. Nothing changes near the row.

From the code, not run: choosing ends at that first click, so a second click on a row, by a user who thinks the
first one failed, logs that player at the pick on the clock.

**Proposal.**

- Show the confirmation in the choosing note itself, with Confirm and Cancel, and keep that note in view while it is
  up (the same fixed treatment as the error banner).
- While a confirmation is waiting, a row click does nothing. Only Confirm or Cancel ends it.

### K2. Your question: the hero's Draft button should not be intercepted

**Measured in Chrome**, on my turn at pick 27 while choosing for pick 10: the hero reads "Pick 27 is yours. Take" and
the button "Draft Chet Holmgren". Pressing it asks "Log Chet Holmgren at pick 10 (Jalen Johnson) instead?".

Only table rows should count. Reasons:

- **The button says what it does.** Its heading names pick 27. A mode must not change the meaning of a labelled
  button. A table row has no label, so the note can redefine it.
- **The pick on the clock is the one with a timer.** If the user presses Draft while choosing, the urgent reading is
  the right one. Log pick 27 and cancel the choosing; the correction can be started again.

### K3. "Pick not in the list" while choosing logs the pick on the clock

**Measured in Chrome**, same state: with the note up for pick 10, "Pick not in the list" logged my own pick 27 as
"not in the list" and dropped the choosing without a word. Undo takes it back ("Undo pick 27: not in the list").

A wrong pick may well have been a player outside the list, so the user's reading is reasonable. **Proposal:** while
choosing, the button applies to the chosen pick, with the same confirmation. If you would rather not, disable it
while the note is up.

### K4. Small, from the code

`draft()` returns when the draft is complete before it looks at `choosing`, so after pick 182 a row click does
nothing and the note stays up. Put the choosing branch first.

## 3. Ready for 3c?

Yes, once the user approves it. Order as agreed: F3 (one gate every method passes through, with the test that walks
every `do_*` method) and then A4. My notes for A4 from replies 2 and 6 stand: save the settings and the Undo history
with the picks; report and keep a saved draft that is refused.

K1 to K3 can go in before 3c or with it. They must be in before the real draft.

## 4. For the user

Approval of 3c, and whether K1 to K3 go first. The window size (`innerWidth` and `innerHeight` on the real monitor)
is still needed before the layout step.
