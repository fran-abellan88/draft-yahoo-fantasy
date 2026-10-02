# Step 3b follow-up report (J1 to J6)

From the builder, 2026-10-02. For the reviewer. The 3b commits are pushed (the user asked); this one is not.

Approved by the user: the J1 to J6 follow-up and the push. **Not started: 3c (F3, A4) and layout code.**

Suite: **347 passed**, flake8 clean, with Node on the path (skipped: 0).

| Finding | What it does now |
|---|---|
| J1 | Edit panel has **Choose the player**. A note says "Choosing the player for pick N: click a player in the table" with Cancel; the next row click (or the hero Draft button) replaces that pick after a confirmation naming who goes back to the pool and whether the roster changes. Works on my own picks. A player already logged elsewhere is refused with "Use Swap with that pick" (rows of the table are the pool, so only the hero or a stale click can reach it) |
| J2 | Confirmation text is built by `logic.js` only for an allowed edit (`swapText`, `forgetText`, `placeText`, `chooseText`); empty or out-of-range numbers now show the refusal message. Node tests |
| J3 | `nextUndo`: with no history, a gone last entry becomes unseen, otherwise the entry is removed. The button reads "Undo: Gone on X", "Undo: 6 unseen picks", "Undo pick 27: X" |
| J4 | A swap, or a choice, that touches one of my picks adds "This changes your roster: pick N is yours." |
| J5 | Place at its own number turns the gone entry into a player pick |
| J6 | Under the window rule the hero says "Picks were missed. Check he is still on Yahoo's board." |

Checked in Chrome (picks 1-20 seen, 21-26 unseen): empty and 999 swaps show the message; swap with pick 2 on an unseen entry is refused; Choose the player at pick 3 asks "Log Amen Thompson at pick 3 (Luka Doncic) instead? Luka Doncic goes back to the pool." and Confirm applies it; a swap with pick 2 carries the roster note; Gone, then an edit, then Undo shows "Undo: Gone on Chet Holmgren" and keeps the log at 26; window rule shows the new sentence.

Not verified: light mode, Safari, Firefox, other widths. Your notes for 3c (saved draft carries history; a refused saved draft kept and reported) and for layout (look-first names as buttons, H4) are recorded for those steps.
