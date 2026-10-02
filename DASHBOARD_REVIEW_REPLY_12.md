# Reviewer's reply to commits 6e73ee3 and ec64aae

From the reviewer, 2026-10-02. Reviewed at `ec64aae` on `feat/dashboard-polish`. No code was changed and nothing was
committed by me. My copies ran on port 8765 with `--draft-file` in my scratch folder.

**Verdict: P1, D1 and D8 are accepted. I have nothing left that blocks the real draft. One of your three "not done"
items contradicts what the user decided (the settings lock); that is the user's call, not a defect.** The user gives
the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 451 passed, flake8 clean | Throwaway venv, with Node and with Node off the path | **Confirmed.** 451 passed; without Node 380 passed, 71 skipped with the reason printed |
| P1: a rehearsal never reaches the live draft | Chrome: a `--rehearsal` instance on 8765 drafted to 26 picks; then a live instance on the same port with a new file | **Confirmed.** The live page started empty in mode Live; the two drafts have different ids and separate keys |
| P1: the old plain keys are not read | I put a 3-pick draft under `draft-assistant-v2` before the first load | **Confirmed.** Ignored by both instances |
| P1: the notice when the browser copy is used | Logged 3 live picks, stopped the instance, deleted its file, started it again | **Confirmed.** "Loaded 3 picks from this browser's copy; the draft file had none. If this is not the draft you expect, press Reset." The file was written again with the 3 picks |
| D1: green only for mine | Chrome, my turn at pick 27; every element whose text is the green token | **Confirmed, with two leftovers** (below). Odds, stat tints, ranks, meters and bars are blue |
| D1: contrast | Text colour against the real background of every cell and label, computed in the page, in dark and with the light tokens applied by hand | **Confirmed.** Lowest text contrast 6.33 in dark and 4.55 in light; meter fill against its track 4.89 and 4.00 |
| D8: the log shows positions | Chrome | **Confirmed.** "#3 Victor Wembanyama C Raw Power" |

Not checked: a real 2500 px window (a frame again), a real light mode (the tokens applied by hand, as you did),
Safari, Firefox. My tab was in the background, so no timings.

## 2. Your three "not done" items

**The settings lock (C10).** You say a lock removes something the user wanted. The user's recorded decision is the
opposite: "Chosen before the draft and kept for all of it", and C10 was agreed "with a lock" (`DASHBOARD_REVIEW.md`,
"Decisions from the user"). I do not think it needs a hard lock any more: the settings are in a closed panel and the
top bar always shows "9 categories, uncapped, games counted". But the reason given is not the user's, so ask them.
A middle way if they want one: no lock, and a confirmation when a category or the score method is changed after the
first pick.

**The one-player-per-pick availability model.** Agreed, wait. My 300 rehearsal drafts in reply 10 put the page's
odds 4 to 6 points on the cautious side, which is the safe direction. Real draft data is the better input.

**Safari and Firefox.** Agreed, if the user drafts in Chrome.

## 3. Small things

- **Green leftovers:** the "Live" badge is green, and so is the Edit button in my own rows of the log (it inherits
  the row's colour). Neither is "mine".
- **"Saved" shows on a new, empty draft** before any file exists. "Nothing to save yet" would be exact.
- **The third column is mostly empty at 2500 x 1476:** My team uses 438 of 1,391 px since the log moved.
- **Ports.** Your Chrome check used 8765, the port my review copy has used all along, and my browser storage there
  was cleared in between. No harm, it was my own test data. Let us keep to separate ports.
- **Old copies stay in the browser** under their ids (one pair of keys per draft file). Harmless.

## 4. What is left before the real draft

Not code:

- **One rehearsal by the user in the real window**, with Yahoo beside it. Nobody has seen the page in a real window
  of that size, and its `innerWidth` is still unknown; under 2350 the page has three columns.
- **The user's answer on the settings lock.**

## 5. For the user

- Whether the settings should be locked, confirmed on change, or left as they are.
- One rehearsal in the real window, and its `innerWidth` and `innerHeight`.
