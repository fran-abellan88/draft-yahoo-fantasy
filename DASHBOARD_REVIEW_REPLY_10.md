# Reviewer's reply to the step 3e, step 6 and step 7 reports

From the reviewer, 2026-10-02. Reviewed at `dbcf066`. No code was changed and nothing was committed by me. My copy ran
on port 8765 with `--draft-file` in my scratch folder; the project's `saved_draft.json` has the same size and time
before and after my tests.

**Verdict: M1 to M4, the layout at 2500 x 1476, the 14-team scoring, the need weights and the step 7 items are
accepted. Two things must change before the real draft: one click on Rehearsal during a live draft logs invented picks
and its Undo then removes real ones (N1), and the real draft file holds three test picks (N2). N3 should be fixed if
"I am behind" is going to be used.** The user gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 444 passed, flake8 clean | Throwaway venv, with Node and with Node off the path | **Confirmed.** 444 passed; without Node 373 passed, 71 skipped with the reason printed |
| M1 | Chrome: the page loaded in a frame where only the read of the draft fails | **Confirmed.** Sticky "Can't read the saved draft", no table, no save sent, browser copy and sync record untouched |
| M2 | Read the code | Reads correct |
| M3 | Chrome: Reset on 29 picks, then one pick and Undo | **Confirmed.** `draft.previous-v34.json` and `draft.previous-v37.json` both exist |
| M4 | Chrome: a browser copy of 20 picks, unconfirmed, based on an older version; file at 26 | **Confirmed.** 26 picks shown, the notice with Dismiss, the 20 picks kept under `draft-assistant-unconfirmed` |
| Layout, no page scroll | A frame at ten sizes from 2500 x 1476 to 960 x 880, with the resize event sent by hand | **Confirmed.** The document is exactly the window at every size |
| 14 teams, totals and standing | 42 picks; every team's nine totals summed by me from the player file, and my own count of teams beaten | **Confirmed.** Largest difference 0.0005 (rounding); ranks and shares match |
| Need weights off give today's scores | Your tests; I did not repeat them | Not checked |
| Analysis time | 0, 1, 26, 42 picks, weights off and on | 84 to 122 ms |
| Saved badge | Chrome: saves made to fail, a pick, then saves restored | **Confirmed.** "Not saved on disk", then "Saved" |
| H4, G2, B5, C9, D5, look-first | Chrome, my turn at pick 30 with picks 28 and 29 unseen | **Confirmed.** Gone on 13 of 123 rows; "Each of those plans takes Amen Thompson at 30 if he lasts (57%)"; the reason line; "jokic" answers "was taken at pick 2"; the arrow key moves to the next row |

Not checked: a real 2500 px window (mine is 1804 x 1043, so I used a frame, as you did), light mode, Safari, Firefox,
two real windows. My tab was in the background, so no page timings.

## 2. Must change before the real draft

### N1. One click on Rehearsal during a live draft

**Measured in Chrome.** A live draft with 33 picks logged, Rehearsal off.

1. One click on **Rehearsal**: the page logged picks 34 to 54 by itself (21 invented picks), saved them to the file
   and cleared the Undo history. No question asked.
2. **Undo**, labelled "Undo pick 54: Pascal Siakam": 25 picks removed. The log is at 29. Real picks 30 to 33 are
   gone, my own pick 30 among them. No copy was made, because the draft was not emptied.

The button sits beside **I am behind**, which is the button pressed in a hurry.

Two more, same cause:

- **Reset keeps Rehearsal on.** Measured: Reset, then the page logged pick 1 by itself. A user who rehearsed the day
  before and presses Reset on draft day starts the real draft in rehearsal.
- **The Undo label names one pick and removes up to 26.**

**Proposal.** Keep rehearsal out of the real draft altogether:

- `run_dashboard.py --rehearsal` starts in rehearsal with its own file (`saved_draft.rehearsal.json`). Without the
  option the page has no Rehearsal button and ignores `rehearsal: true` in a saved draft.
- If you keep the button: enabled only on an empty draft, with a confirmation; switching it off always allowed;
  Reset switches it off.
- In rehearsal, Undo reads "Back to before your pick 30 (25 picks)".

### N2. The real draft file holds three picks

`saved_draft.json` in the project folder: version 3, Jokic, Wembanyama, Gilgeous-Alexander, written at 10:27:18,
the minute before your step 3e report says the real file was deleted. It was not written by me. If it is not the
user's, it is a layout check run without `--draft-file`, the second time this has happened.

**Proposal.**

- Remove it, with the user's agreement, and run every check with `--draft-file`.
- Print the state at startup: "Saving the draft in ... (3 picks, last changed 10:27)".
- When the page loads a draft that has picks, say so once: "Continuing a saved draft: 3 picks, last changed 10:27".

## 3. Should change

### N3. Unseen picks make the other teams look weaker than they are

A pick with no player adds nothing to its team, and the standing compares totals. **Measured:** 42 picks, then the
same log with six picks of round 3 made unseen.

| Category | Teams beaten, complete log | With 6 unseen |
|---|---|---|
| BLK | 15% | 46% |
| PTS | 69% | 85% |
| REB | 69% | 85% |
| TO | 8% | 0% |

The page does say "6 picks not counted", but the "Winning / Close / Behind" line and the need weights use these
numbers (BLK weight 0.95 becomes 1.26).

**Proposal.** For a team with a missing pick, scale its counting totals to the common size (total x size / players
counted), mark the team in the 14-team table, and leave the percentages alone. In the projection, fill an unseen
pick's slot with the automatic pick for that team, so the same players are not handed to the teams that pick later.

### N4. The need weights move more than the page says

**Measured over 60 rehearsal drafts:** the final weights ran from 0.49 to 1.65. The 40% limit is applied before the
weights are scaled to average 1, so it does not hold afterwards, and "a little more ... a little less" in the
settings is not what happens. Either limit the weights after scaling, or say "between about half and one and a half".

## 4. Your questions

**1. Is the projection's treatment right?** Yes, as a guess. I drew 60 drafts with your rehearsal chooser for the
other 13 teams and took the page's recommendation at each of my picks.

| | Categories won of 9 against a random team |
|---|---|
| Projection at pick 2 | 5.85 |
| Projection at pick 27 | 5.86 |
| Projection at pick 55 | 5.96 |
| What I ended with | 6.12 |

So protecting the plan's players does not make the projection optimistic. Of the eight players in the first plan
only 3.2 end up on my team on average, so the projected roster is not a forecast of names; the label "a guess at the
league" is right. The weak part is the other 13 teams drafting in ADP order, not the protection.

**2. Do the weights look sound?** As an option that is off by default, yes. Same 60 drafts, weights on against off:

- categories won: +0.18 of 9 (standard error 0.06);
- matchups won: +0.008 (standard error 0.008), better in 16 drafts, the same in 31, worse in 13.

A small gain in categories and none I can separate from noise in matchups. The opponents here are ADP drafters, whom
the page already beats in 96% of matchups, so this test cannot show much. Keep it off by default, with N3 and N4.

**3. Anything to block before the real draft?** N1 and N2.

## 5. The layout at 2500 x 1476

Four columns, no page scroll, no table column cut (the table is 1,089 px wide). Both sides of the top threshold
hold: at 2350 four columns with the table at 939 and nothing cut; at 2349 three columns.

- **The row density pass (C2) is the thing still missing here.** Rows are 55 px and taller with a note, so about 20
  players are visible in 1,256 px. One line per player would show about 40.
- **The 14 TEAMS column is 1,391 px high and uses 533.** The log sits under the roster in the 380 px column. Moving
  the log under 14 TEAMS, as the wireframe had it, gives the roster and the log both more room.
- **From 1720 to 2349 the spare width goes to the table**, not the panels: at 2240 the table is 1,383 px wide while
  the 14-team table (496) is cut in a 380 px tab panel. Only matters if the real window is under 2350.
- **Narrower widths:** FT% is cut at 1720; FG% and FT% at 1280; TO, FG% and FT% at 1240. Below 1240 the table is a
  tab and was not the open one in my run. None of this is the user's window.
- **Still wanted from the user:** the real `innerWidth`. Under 2350 the page drops to three columns.

## 6. Smaller things

- **Rehearsal drafts are a little kinder than the odds on the page.** 300 rehearsal drafts: players the page gives
  20% to 90% at pick 27 were still there 62% of the time against 58% on the page; at pick 55, 71% against 65%. The
  page's expected number gone is 26.8 before pick 27 and 56.0 before pick 55, where 26 and 54 picks are made. The
  page errs on the cautious side. These draws are the one-player-per-pick model that was postponed; the odds could
  be read from them later.
- **Automatic picks stop at pick 150** with "Nobody left fits that team's lineup". The pool is empty; say that.
- **Settings are not locked after the first pick** (C10). They are in a closed panel now, so the risk is small.
- **The Gone threshold uses the default spread**, whatever spread the user set.
- **With no server draft and only a version 1 browser draft**, the page loads the old draft and does not save it to
  the file until the next change.
- **Not done, by your own list:** D1 colour roles, D8, light mode, Safari, Firefox.

## 7. For the user

- Approval of N1 and N2 before the real draft; N3 and N4 with them or after.
- Whether the three picks in `saved_draft.json` are theirs.
- The real `innerWidth` and `innerHeight`.
