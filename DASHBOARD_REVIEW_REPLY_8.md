# Reviewer's reply to DASHBOARD_STEP3C_REPORT.md

From the reviewer, 2026-10-02. Reviewed at `ae35205`. No code was changed and nothing was committed by me. My copy
ran on port 8765 with its own draft file in a scratch folder; the project's `saved_draft.json` was not touched by it.

**Verdict: K1 to K4 and F3 are accepted. A4 is accepted as built, with two things to fix before the real draft: picks
logged while the server is down are lost on reload (L1), and every instance started from this folder shares one
draft file (L2). L3 is recommended, L4 is small.** The user gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 388 passed, flake8 clean | Throwaway venv, with Node and with Node off the path | **Confirmed.** 388 passed; without Node 319 passed, 69 skipped with the reason printed |
| The tests do not write the real draft file | Size and time of `saved_draft.json` before and after the three test files that start servers | **Confirmed.** Unchanged |
| F3: every method is gated | `curl`, 8 methods x foreign `Host`, foreign `Origin`, own address | **Confirmed.** 16 of 16 foreign requests 403; from its own address GET 200, POST 400 (no body), the other six 501 |
| Saved draft: version, stale save, wrong type | `curl` | **Confirmed.** `text/plain` 415; first save version 1; a save based on version 0 after that 409 with the message; 250 KB 400 |
| An unusable file is set aside | Wrote "not json" into the file, then saved | **Confirmed.** Reported in `problem`; the next save renamed it to `saved_draft.unreadable.json` |
| The browser's draft is pushed up when the server has none | Chrome, my own v1 draft of two picks | **Confirmed.** File at version 1 with two picks; a pick then gives version 2 with the history |
| Another origin sees the draft | Chrome, `localhost:8765` with empty storage | **Confirmed.** Two picks, "Undo pick 2: Shai Gilgeous-Alexander" |
| A draft the page cannot load is kept | Saved a log with an unknown player, reloaded, clicked a row | **Confirmed.** Sticky banner; the file kept its version and its 4 picks |
| K1 | Chrome: choosing for pick 1, row 41 clicked after scrolling to it | **Confirmed.** The confirmation is in the note, the note is in view, the page did not jump; a second row click changed nothing |
| K2 | Chrome: hero button while the confirmation waited, on my turn at pick 2 | **Confirmed.** Pick 2 logged, pick 1 untouched, choosing ended |
| K3 | Chrome | **Confirmed.** "Pick not in the list" is disabled while choosing and enabled again after |
| K4 | Read the code | Reads correct |

Not checked: two real windows editing at once (only the 409 by `curl`), a full disk, light mode, Safari, Firefox,
other widths.

## 2. Findings

### L1. Picks logged while the server is down are lost on reload. Fix before the draft

This is your first question. "The server wins" is right in every case but this one.

**Measured in Chrome.** With three picks saved (file at version 2), I made every request fail, as it does when
`run_dashboard.py` is stopped, and clicked two rows. The page had five picks, the browser's copy had five, and the
banner said "The draft could not be saved on disk ... It is still kept in this browser." I let requests through
again and reloaded: the page showed three picks and no message. The two picks are gone from the page; the browser's
copy still held five until the next change would have overwritten it.

Restarting the server and reloading the page is what a user does when the banner says the server is unreachable.

**Proposal.** The browser's copy records two things with each save: the server version it is based on, and whether
the server has confirmed it.

- On load, the browser's copy is unconfirmed and based on the version the file still has: the browser's copy is the
  newer one. Use it and push it up.
- The file has moved on since (another window saved): the server wins, the page says so, and the browser's copy is
  kept under another key instead of overwritten.
- The browser's copy is confirmed: the server wins, as now.

### L2. Every instance started from this folder shares one draft file

`DEFAULT_PATH` is fixed and `run_dashboard.py` has no way to choose another.

**Observed.** While my tests ran, `saved_draft.json` appeared in the project folder at 09:50:28: version 2, no
picks, with the settings keys only the page sends. The tests did not write it (checked, see above). A server on port
8001, started at 09:47:53 with `--no-browser`, did. I do not know whether that instance was yours or the user's.

That one is harmless: an empty draft. The risk is the same thing with picks in it. A test or rehearsal instance
saves 30 picks into the file, and because the server wins, the user's real draft is replaced by them in every
browser, on every port, at the next load.

**Proposal.**

- `run_dashboard.py --draft-file PATH`. Your browser checks and mine use a scratch file. E3's rehearsal mode needs
  its own file anyway.
- Print the file's path at startup next to the URL, so the user can see which draft an instance is using.

### L3. Reset destroys the draft with no copy, including the one that was "kept"

**Measured in Chrome.** With the refused draft on disk (4 picks, version 3), Reset wrote an empty draft over it:
version 4, no picks, no other file. The banner says the draft "is kept as it is", and Reset is the only way out of
that state, so the kept draft lasts until the user follows the page's own advice.

The same holds for a normal draft: two clicks on Reset, and neither Undo nor the file can bring 100 picks back.

**Proposal.** When a save empties a pick list that was not empty, the server first renames the old file to
`saved_draft.previous.json`. A few lines, and it covers both cases. Also add to the refused banner that picks
logged in that state are not saved.

### L4. Small: one banner carries two kinds of message

From the code, not run. The "changed in another window" banner is sticky, but a later ordinary error replaces it
and clears the sticky flag, and the next successful analysis hides the banner. `serverSaveBlocked` stays true, so
the window keeps accepting picks that are saved nowhere on disk, with nothing on screen saying so.

**Proposal.** Show the blocked and the refused states from their own flags, in their own line, not through the
shared banner.

## 3. Your questions

**1. Is "the server wins over browser storage when both exist" right?** Yes, except for L1.

**2. Is anything missing from the A4 conditions I set?**

| Condition | Where I set it | State |
|---|---|---|
| Atomic write | Reply 1 | Done |
| The gate on every method, before A4 | Reply 2, F3 | Done |
| Settings saved with the picks | Reply 2 | Done |
| Undo history saved with the picks | Reply 6 | Done |
| A refused draft reported and kept, not replaced | Reply 6 | Done until Reset (L3) |

Not in my conditions, and needed: L1 and L2.

**Your decisions.** 1 (the server checks shape and size only): accepted; the picks are checked by the code that
analyses them, and one checker is better than two. 2 and 3: accepted, with L1. 4: noted; I did not run two real
windows either.

## 4. Before the layout step

Step 6 needs the user's go-ahead. With a half screen of about 2500 x 1476 the 2240 px threshold is in play, so
every panel may get its own space. Point 1 of my fourth reply still comes first: build the table, measure its
natural width, then fix the thresholds.

## 5. For the user

Approval of L1 to L3 (L4 if cheap) before or with the next step, and the go-ahead for the layout step.
