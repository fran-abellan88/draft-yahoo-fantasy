# Reviewer's reply to commit 116ca6a, and data on stronger opponents

From the reviewer, 2026-10-02. Reviewed at `116ca6a` on `feat/mock-and-standings`. No code was changed and nothing was
committed by me. My copy ran on port 8765 with scratch files.

**Verdict: Q1 to Q5 are fixed and accepted. Q6 is accepted with one thing to fix: at my viewport the 14-team table
is cut by 24 px (R1). On opponent strength I have new data: against opponents that use the page's own optimiser I
am first in about a third of drafts, not 95%. I would put that in words on the page, not as a live number
(section 3).** The user gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 467 passed, flake8 clean | Throwaway venv, with Node and with Node off the path | **Confirmed.** 467 passed; without Node 394 passed, 73 skipped with the reason printed |
| Q1 | Chrome: a real draft with 5 picks, reloaded | **Confirmed.** "Saved" |
| Q2 | Chrome at 0, 1 and 3 picks | **Confirmed.** "13 teams with no player yet are left out"; the lone team has no Score and no place; "against 2 other teams" |
| Q3 | Chrome: a pick and the Mock draft link in the same tick, then back | **Confirmed.** File at the next version with 5 picks; only "Continuing a saved draft: 5 picks" |
| Q4 | Chrome: a pending change, then a pick; a pending change, then Reset | **Confirmed.** The confirmation goes and the control is put back both times |
| Q5 | Chrome: 99 typed in the spread; the window rule | **Confirmed.** "set the early-round spread to 20"; "judge availability with the ADP window" |
| Q6 | Chrome, the tab's own viewport at 2436 x 1408 | **Confirmed, with R1.** My team 457 px, the log 792 px under it, 14 teams the whole fourth column, no page scroll |
| The sentence about scaled teams | Read the code; my Chrome run was in round 1, where no team is scaled | Reads correct |

Not checked: light mode, Safari, Firefox, narrow widths. No timings.

## 2. From this commit

- **R1. The 14-team table is wider than its column.** At 2436 x 1408 the table is 564 px in a 539 px panel: the TO
  column ends 24 px past the edge. The column is a fixed 540 px, so 2500 will not help. Probably since `#` and
  `Score` were added; I did not measure it in reply 13. Make the column 570 or tighten the cells.
- **The main table is 14 px short at 2436** (FT% ends 14 px past the edge; 1039 px in 1025). It fits at 2500 by my
  earlier measurement. One more reason to get the user's real `innerWidth`.
- **The empty space moved to the fourth column**: 14 teams is 1264 px high and uses 570. That is the better place
  for it, because the log grows and the table does not. There is room to show So far and Projected one under the
  other, with no switch.

## 3. Opponents that draft as well as the page

**I had no such data; every opponent in my earlier rounds was an ADP drafter. Measured now.** 24 drafts per line,
eight rounds, nine categories. My slot 2 always takes the page's recommendation. An "optimiser opponent" takes the
page's recommendation for its own slot (a `DraftService` per slot); the rest pick with the mock chooser. Which slots
are optimisers is drawn per draft.

| Optimiser opponents | I am 1st | Top 3 | Mean place | Worst | My Score | Matchups I win | Their Score | ADP teams' Score |
|---|---|---|---|---|---|---|---|---|
| 0 | 96% | 100% | 1.0 | 2 | 6.15 | 96% | | 4.37 |
| 3 | 92% | 100% | 1.1 | 3 | 6.03 | 92% | 4.97 | 4.20 |
| 6 | 29% | 67% | 2.8 | 7 | 5.23 | 79% | 4.79 | 4.15 |
| 10 | 33% | 58% | 3.6 | 11 | 4.98 | 66% | 4.58 | 4.09 |
| 13, each taking the ADP pick one time in five | 33% | 75% | 2.7 | 9 | 5.12 | 75% | 4.45 | |
| 13, always the recommendation (one draft, no chance in it) | 3rd | | 3 | | 4.69 | 58% | 4.49 | |

In that last draft the Scores by slot were 5.5, 4.7, 5.0, 4.6, 4.7, 4.1, 4.0, 4.5, 3.9, 4.1, 4.7, 4.4, 4.5, 4.4.

What I read from it, with 24 drafts per line (a share near 30% is good to about 10 points either way):

- **The optimiser is worth about 0.6 to 0.8 categories of nine over ADP drafting**, at any slot. My 6.1 against ADP
  drafters is that plus a league where nobody competes for the same players.
- **Slot 2 keeps a small edge**: third of 14 and 4.69 when everybody drafts the same way (the average is 4.5).
- **With six or more opponents of that level I am first in about a third of drafts** and win 66 to 79% of
  matchups. The drop between 3 and 6 opponents is sharper than I would trust from 24 drafts.
- **This corrects what I said in reply 10.** "The projection is not optimistic" holds against ADP drafters only.
  The projected Score at pick 2 is 5.85; against six or more optimisers I end near 5.0 to 5.2.

**On your proposal.**

- **The headless experiment: yes.** The table above is two of your three levels already. The middle one (ADP with
  some category sense) is the one closest to real managers and the one nobody has.
- **A "my edge" number next to the Score: I would not.** It depends on how thirteen real people draft, which the
  page cannot know, and it changes no pick. A number there would read as a measurement.
- **What I would do.** One sentence in the Projected note: "The other teams are filled in ADP order; against
  managers who draft as well as this page, the same plan finishes around 3rd". And tell the user that the honest
  view of the opponents is **So far**: it is made of their real picks, and Projected becomes real one round at a
  time (at pick 83 five of the eight rounds are real).
- **If the user wants it on the page anyway**, change the fill, not the label: let the projection fill the other
  teams with the middle-level chooser. Then first place stops being automatic and no new number is needed.

## 4. For the user

- Whether a sentence in the Projected note is enough, or the projection should assume stronger opponents.
- The real `innerWidth` and `innerHeight`: at 2436 two tables are cut by a few pixels.
