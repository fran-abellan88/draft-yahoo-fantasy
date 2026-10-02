# Reviewer's reply to DASHBOARD_STEP7B_REPORT.md

From the reviewer, 2026-10-02. Reviewed at `eae941a`. No code was changed and nothing was committed by me. My copies
ran on ports 8765 and 8766 with `--draft-file` in my scratch folder.

**Verdict: N1 to N4, the row density and the log move are accepted. I would block nothing in the code. One fix is
worth making before the real draft (P1): a rehearsal can still reach the live draft through the browser's own copy
when both ran on the same port.** The user gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 446 passed, flake8 clean | Throwaway venv, with Node and with Node off the path | **Confirmed.** 446 passed; without Node 375 passed, 71 skipped with the reason printed |
| N1: a rehearsal refuses the real file | `--rehearsal` alone, and with `--draft-file ./saved_draft.json` | **Confirmed.** Both exit 1 with the message; the real file was not touched |
| N1: the live instance refuses automatic picks | `curl` to `/api/autopick`; my own simulation script also stopped on it | **Confirmed.** 400 with the message |
| N1: no button, mode from the server, not saved | Chrome on a `--rehearsal` instance | **Confirmed.** No Rehearsal button; "Rehearsal: other teams automatic"; the saved keys have no `rehearsal` |
| N1: the Undo label | Chrome | **Confirmed.** "Undo: 25 picks, back to my pick 2", "Undo: 3 picks, back to my pick 27" |
| N2: startup lines and the notice | Started three instances; Chrome | **Confirmed.** "REHEARSAL ..." or "Live draft ...", "No saved draft yet: starting empty." or "Continuing a saved draft: 29 picks (version 1)."; the page notice |
| N3 | My measurement from reply 10 again: 42 picks, six of round 3 made unseen | **Confirmed.** Mean share of teams beaten: 0.590 complete, 0.581 with the unseen picks (it was 0.641) |
| N4 | 40 drafts with the weights on | **Confirmed.** Final weights from 0.60 to 1.40 (they were 0.49 to 1.65) |
| C2 | Chrome, frame at 2500 x 1476 | **Confirmed.** Rows 29 to 30 px, 41 fully visible, no player cell cut |
| Log under the 14 teams | Same | **Confirmed.** 14 teams 791 px high, log 589 px under it, my team the whole third column |

Not checked: a real 2500 px window (a frame again), light mode, Safari, Firefox. My tab was in the background, so no
timings.

## 2. One thing to fix before the real draft

### P1. A rehearsal becomes the live draft through the browser copy

The browser copy belongs to the port, not to the draft file. This is the point I called optional in reply 9; with a
rehearsal instance it is now the likely sequence.

**Measured in Chrome.**

1. A `--rehearsal` instance on port 8765 with its own file. I drafted to 29 picks. Stopped it.
2. A live instance on the same port with a draft file that did not exist. The terminal said "Live draft: you log
   every pick." and "No saved draft yet: starting empty."
3. The page: mode "Live", 29 picks, "Continuing a saved draft: 29 picks. Reset starts a new one." The live draft
   file now holds the 29 rehearsal picks.

On the user's machine the port is 8001 for both unless they choose otherwise, and the real draft file does not
exist at the moment (see 4). It is not silent: the notice is there and Reset keeps a copy. But it is the one way
left for a rehearsal to end up in the real file, and the terminal and the page contradict each other.

**Proposal.**

- Give the browser copy the identity of its draft file: the server sends an id (a hash of the file's full path and
  the mode will do, since it must exist before the file does), and the storage keys carry it
  (`draft-assistant-v2:<id>`, the sync record the same). A copy made for another file is then never read.
- The minimum, if you prefer: a rehearsal instance uses its own storage keys.
- When the draft comes from the browser and the file had none, say that, not "Continuing a saved draft": "Loaded 29
  picks from this browser's copy; the draft file had none. Reset starts a new one."

## 3. Your questions

**1. Should an unseen pick of mine be impossible by construction?** Yes, keep it. The user can always read their
own roster in Yahoo, even when Yahoo picked for them, and my roster decides the lineup limits, the plan and the
standing, so a hole there would make every later recommendation wrong. The server refusal I checked in earlier
rounds; I did not repeat it.

**2. Anything else I would block?** No. What is left before the real draft is not code:

- **One rehearsal by the user in the real window.** Nobody has seen this page in a real 2500 px window, in the
  foreground, with Yahoo beside it. The real `innerWidth` is still unknown; under 2350 the page has three columns.
- **The real draft file** (see 4).

## 4. The real draft file is gone

`saved_draft.json` was in the project folder when I started this round (3 picks, 10:27:18) and after my two refused
rehearsal starts. It is not there now; the folder changed at 11:13. I did not remove it: every instance of mine used
a file in my scratch folder. If the user removed it, good. A live start now says "No saved draft yet", which is the
case P1 is about.

## 5. Numbers from this round

Forty drafts, the other 13 teams drawn by the rehearsal chooser, the page's recommendation taken at each of my picks:

| | Weights off | Weights on |
|---|---|---|
| Categories won of 9 against a random team | 6.16 | 6.39 |
| Matchups won | 96% | 97% |

On minus off, same seeds: +0.23 categories (standard error 0.07), +0.019 matchups (standard error 0.010); better in
13 drafts, the same in 22, worse in 5. A small gain against ADP drafters. Off by default is still right.

## 6. Small things, none new

- With unseen picks single categories still move (blocks 15% to 31% of teams beaten in my case). That cannot be
  avoided with unknown players; the mean is now right. A team with no credited player at all has totals of 0.
- Automatic picks stop at pick 150 with "Nobody left fits that team's lineup"; the pool is empty.
- Settings are not locked after the first pick (C10); D1 colour roles, light mode, Safari and Firefox are open.

## 7. For the user

- Approval of P1.
- One rehearsal in the real window, and its `innerWidth` and `innerHeight`.
- Whether they removed `saved_draft.json`.
