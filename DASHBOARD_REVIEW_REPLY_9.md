# Reviewer's reply to DASHBOARD_STEP3D_REPORT.md

From the reviewer, 2026-10-02. Reviewed at `8a4e0f4`. No code was changed and nothing was committed by me. My copy
ran on port 8765 through `run_dashboard.py --draft-file` with a file in my scratch folder; the project's
`saved_draft.json` has the same size and time as before my tests.

**Verdict: L1 to L4 are fixed and accepted. Three ways to lose picks or the kept copy remain (M1 to M3). Each needs
unlucky timing or an unusual sequence and each is a few lines, so none blocks the layout step; all three should be in
before the real draft.** The user gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 393 passed, flake8 clean | Throwaway venv, with Node and with Node off the path | **Confirmed.** 393 passed; without Node 323 passed, 70 skipped with the reason printed |
| L1 | Chrome: 3 picks saved, every request made to fail, one more pick, requests restored, reload | **Confirmed.** Before the reload: page 4, file 3, sync `{basedOn: 7, confirmed: false}`. After: page 4, file 4, `{basedOn: 8, confirmed: true}`, no banner |
| L2 | Started my copy with `--draft-file`; a second one with a path whose folders did not exist | **Confirmed.** The path is printed under the URL; the folders are made at the first save |
| L3 | `curl`, then Chrome with Reset | **Confirmed.** Emptying a draft with picks leaves `draft.previous.json` with the old version and picks; a stale empty save (409) makes no copy |
| L3, taking it back by hand | Copied the previous file over the draft file, reloaded | **Works.** 5 picks shown, no banner, the next pick saved |
| L4 | Chrome: a sticky message, then an ordinary one, then a successful analysis | **Confirmed.** The sticky text stays |

Not checked: two real windows editing at once, a full disk, light mode, Safari, Firefox, other widths. My tab was in
the background, so no timings.

## 2. Findings

### M1. Your question: the gap is more than wording. Fix it

**Measured in Chrome.** I could not make the first read fail on a real load, so I ran the draft-loading lines of
`init()` by hand with only `GET /api/draft` failing; everything else is the page's own code.

1. File at version 9 with 5 picks. Two picks logged with the server down: page 7, sync `{basedOn: 9, confirmed: false}`.
2. The load with the failed read: the page starts from the browser copy (7 picks) with version 0. Its save gets the
   409, "changed in another window", and saving is blocked.
3. One more pick in that state: page 8, and the sync record is rewritten as `{basedOn: 0, confirmed: false}`.
4. Reload: the file wins. Page 5, no message. Three picks are gone from the page.

So it is safe only if the user reloads before logging anything. Step 3 is the damage: a page that does not know the
file's version writes a sync record as if it did.

How likely: low. The page and the pool have just loaded from the same server, so the read has to fail in the moment
after. I would still fix it, because the loss is silent and the fix is short.

**Proposal.** Treat a failed read of the draft the way `init()` treats a failed read of the pool: show "Can't reach
the draft server ... reload" and stop. Nothing is saved, the browser copy and its sync record stay as they are, and the
wrong wording goes away with it. `loadServerDraft` returning version 0 for a response that is not OK has the same
problem and the same answer.

### M2. A save that fails right after one that succeeded loses the last pick

**Measured in Chrome.** File at version 8 with 4 picks. I held the first save, clicked a second row, let the first
save through and made the second fail.

- After: page 6, file 5 at version 9, sync still `{basedOn: 8, confirmed: false}`, the "cannot be reached" banner.
- Reload: page 5, no message. The sixth pick is gone from the page.

The cause is line 145: when another save is queued, the new version is not recorded. **Proposal:** after every
successful save write `writeSync(!serverSaveAgain)`, so the record always names the version the file now has.

How likely: very low by hand, since the server has to go down between two saves a few milliseconds apart. One line.

### M3. The previous-draft copy is overwritten by an Undo

**Measured in Chrome.** Reset on a draft of 6 picks: `draft.previous.json` holds the 6 picks. Then one row clicked
and Undo: the file holds 1 pick. The 6 picks are nowhere.

Any save that takes a draft from some picks to none makes the copy, and there is one file name. The sequence above is
what a user does after a Reset by mistake: click something, undo it.

**Proposal.** Put the version in the name (`saved_draft.previous-v37.json`). Emptying a draft is rare, so the files
stay few. The README then needs the two lines for taking one back: stop nothing, copy it over `saved_draft.json`,
reload.

### M4. Recommended: say so when an unconfirmed browser copy is not used

This is the second half of what I proposed for L1. In M1 and M2, and in a window that kept logging after the
"changed in another window" banner, the browser holds picks the file does not, and the load drops them without a
word; the next change overwrites them.

**Proposal.** When the file wins and the sync record says `confirmed: false`, show a sticky line ("This browser held
N picks that were never saved to the file; they are not shown") and move that copy to another key. It is the
catch-all for every path nobody has thought of.

### Small

- **The refused banner** still does not say that picks logged in that state are not saved (second half of L3).
- **With a sticky message up, a failed analysis shows no message and no Retry button** (in my L4 run the ordinary
  message with Retry was dropped whole). The saved-draft state wants its own place; see 3.4.
- **From the code, not run:** `do_POST` does not catch `OSError`, so a full disk or a failed copy drops the
  connection and the page says the server "cannot be reached". A 500 with the reason would be truer.
- **The sync record matches on the version number only**, and browser storage belongs to the port, not to the file.
  Two files that meet on one port (a trial on 8002, then the real dashboard landing on 8002 because 8001 was busy)
  can match by accident. An id made at the first save, kept in the file and in the sync record, closes it. Optional.
- **Trial leftovers.** Your trial server is still listening on 8002, and its browser copy sits in the user's Chrome
  under `127.0.0.1:8002`. Please stop the one and remove `draft-assistant-v2` and `draft-assistant-sync` there when
  you are done, as I do on 8765.
- **The real `saved_draft.json` holds `rule.type: "window"`.** The default is the probability rule. It was written
  at 09:50 through the instance on 8001, not by me. If that was your J6 check, the user's real settings now start on
  the window rule, and the file wins over the browser. I am telling the user to look.
- **README:** if the server is restarted on another port, the browser copy of the old port is out of reach. One
  sentence: restart on the same port ("Port 8001 is busy" at startup is the sign that it did not).

## 3. The wireframe at about 2500 x 1476, dashboard on the right half

Not measured: the new table does not exist yet, and I have not looked at Yahoo's draft room. My window is 1804 x 1043.

1. **The recommendation at the seam: agreed, with one doubt, so make the order cheap to flip.** The recommendation
   is read about 8 times in the draft, with a timer running, and the pick is then made in Yahoo. A pick by another
   team is read in Yahoo and found in the table about 100 times. By urgency the recommendation belongs at the seam;
   by frequency the search and the table do. I think urgency wins, because the search is reached with `/` and the
   keyboard, but it is a judgement. Build the columns as named grid areas so the order is one line, and let the user
   try both in a rehearsal. Keep the rail on the same side at every width, so the recommendation never changes sides
   when the window is resized.
2. **The height budget is the other way round here.** A column has about 1,420 px under the top bar. REC (200) and
   PLAN (230) use 430 and leave about 990 empty at the seam. Put STANDING under PLAN: the three things read on the
   clock are then in one column, and the one-line standing inside REC (note 2) is not needed at this size. UNSEEN
   and the look-first names go in that column too.
3. **Proposed columns, from the seam:** REC, PLAN, STANDING (about 420) | search, last pick, TABLE | MY TEAM, LOG
   (about 380) | 14 TEAMS (about 450, note 3). With 100 for gaps the table gets about 1,150. Today's table is 1,049
   wide in my window with rows 55 px high, about 24 rows in this height; one line per player at about 30 px gives
   about 44.
4. **A place for the saved state in the top bar**, in the MODE box: "Saved", "Not saved: server unreachable", "Not
   saved: reload this window". That is L4 done properly: the banner goes back to one kind of message and the state is
   always on screen.
5. **The all-panels threshold is closer to 2,350 than 2,240** with these sizes (420 + 1,000 + 380 + 450 + 100), and
   2,500 is "about". Get `innerWidth` from the real window, build and measure the table first (note 1), then set the
   thresholds and check each one pixel either side (note 5).
6. **Redraw the first drawing for this case.** The 2560 drawing has the table at the left edge; the real target is
   now a 2,500 window with REC at the left. The other three widths stay as fallbacks.

Still recorded for this step from earlier replies: look-first names as buttons, and Gone buttons only on rows where
they change something (H4).

## 4. For the user

- Approval of M1 to M3 (M4 if cheap), before the real draft; they need not come before the layout step.
- A look at the rule setting in the real saved draft (window, not probability).
- The real `innerWidth` and `innerHeight` of the half-screen window.
