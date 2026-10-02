# Reviewer's reply to DASHBOARD_STEP8_REPORT.md

From the reviewer, 2026-10-02. Reviewed at `1102da9` on `feat/mock-and-standings`. No code was changed and nothing was
committed by me. My copy ran on port 8765 with `--draft-file` and `--mock-file` in my scratch folder.

**Verdict: the three parts are accepted and I would block nothing. The scaling rule is better than the rule it
replaces, with a small bias worth one sentence on the page (section 2). Two small things came in with this step and
are worth fixing: the saved badge is empty after a reload (Q1) and the round 1 wording is wrong (Q2).** The user
gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 464 passed, flake8 clean | Throwaway venv, with Node and with Node off the path | **Confirmed.** 464 passed; without Node 392 passed, 72 skipped with the reason printed |
| Settings wait for Apply after the first pick | Chrome, 33 picks logged | **Confirmed.** "33 picks logged. Apply: leave out TO; cap scores at the top 5%? ..."; nothing saved or recomputed until Apply; Keep current and closing the panel put the controls back; a change undone by hand needs no confirmation |
| No green on the badge and log buttons | Chrome, computed colours | **Confirmed.** The Edit button in my own log row is the ink colour |
| No "Saved" on a new empty draft | Chrome | **Confirmed, with a side effect** (Q1) |
| My team in two columns when wide | Chrome, viewport 2436 x 1408 | **Not at the user's size.** See Q6 |
| Score, place, sorted rows, a team with no player last | Chrome at 0, 1, 2, 3, 33 picks; the code | **Confirmed.** Round 1 wording is wrong (Q2) |
| So far updates with every pick | Chrome and 60 simulated drafts | **Confirmed.** Numbers in section 2 |
| `/mock` with its own service and file | `curl` and Chrome | **Confirmed.** `/`, `/mock`, `/mock/` answer 200; `/mock/app.js` and `/mockery` 404; different ids and separate browser keys; a mock draft played to pick 57 left the real file at the version it had |
| The real routes refuse automatic picks | `curl` | **Confirmed.** 400 with the message; `/mock/api/autopick` answers |
| `--rehearsal` is gone, the two files must differ | Started both ways | **Confirmed.** "unrecognized arguments"; exit 1 with the message |

Not checked: light mode, Safari, Firefox, narrow widths. My tab was in the background, so no timings. In this round
the tab's own viewport was 2436 x 1408 (not a frame), four columns, no page scroll.

## 2. (a) Scaling the teams that have not made their n-th pick

**Measured over 60 drafts** (the other 13 teams drawn by the mock chooser, my picks the page's recommendation). At
every pick of rounds 2 to 8 I took each team's Score and compared it with its Score when that round was complete.
Three rules: yours; the round finished with the automatic pick and nothing scaled ("fill"); complete rounds only,
the rule before this step ("previous").

| | Scale (yours) | Fill | Previous |
|---|---|---|---|
| Mean error of a Score, of 9 | 0.23 | 0.22 | 0.30 |
| Mean error of a place | 1.45 | 1.50 | 1.89 |
| Place off by 3 or more | 20% | 21% | 29% |
| A team that has not picked yet | +0.11 | +0.01 | +0.02 |
| A team that has picked | -0.11 | -0.01 | -0.02 |
| My Score when I make my pick | -0.32 (down in 79% of my picks) | +0.11 | no change |

So:

- **It is better than what it replaces.** Closer to the end of the round on every measure.
- **It has a bias, and it shows at the worst moment.** Scaling by n / (n - 1) assumes the n-th pick is as good as
  the average of the earlier ones, and it never is. A waiting team reads 0.11 too high; a team that has picked reads
  0.11 too low. For the user it looks like this: I take the recommended player and my Score goes down. In round 2 it
  drops 0.59 on average. In Chrome, in a mock draft: 6.4/9 before my pick 27, 6.2/9 two picks later; 6.6/9 before my
  pick 55, 6.2/9 after it.
- **The parity matters for slot 2.** In even rounds I pick 13th, so I am the scaled team for twelve picks; in odd
  rounds I pick 2nd and the other twelve are scaled.
- **Fill removes the bias and gains nothing else.** It also puts invented players into "So far", which blurs the one
  line between the two views, and the places move more inside a round (4.9 places against 3.2).

**Proposal.** Keep the scaling. Add one sentence to the note: "a scaled team usually drops a little when it makes
its pick". If you want the bias gone without inventing players, scale by less than n / (n - 1); I did not measure
that. I would not go to fill.

The neighbours in the sorted table are 0.21 apart on average and the mid-round error is 0.23, so a place inside a
round is good to about one or two rows. The categories are the useful part of this view, not the place.

## 3. (b) The unweighted score

**Agreed, unweighted.** The need weights are a way to choose a player; the Score describes a team. Weighting it
would make the user's own row move when they tick an option.

**Measured over the same 60 drafts:**

- The Score order matches the head-to-head record order (each team against the other 13, five or more categories of
  nine): rank correlation 0.94 on average, 0.85 at the lowest. The top team by Score also has the best record in 92%.
- In the projected table I am first in 43% at pick 2, 83% at pick 27, 85% at pick 55 and 97% at pick 83; after eight
  rounds I am first in 95%, with a Score of 6.12.

Two things to say on the page or in the README, not to change:

- **Being first in Projected is close to automatic.** My team gets a plan optimised for these categories and the
  other 13 get ADP order. It says the plan is coherent, not that the league is won. Against real managers nobody
  has measured it.
- **The Score counts ranks, not margins.** Losing a category by one rebound counts the same as losing it by fifty.
  Fine for sorting a table.

## 4. (c) The `/mock` route against "never a button in the live draft"

**Accepted.** The rule came from N1: one click in a live draft wrote invented picks into the real file, and Undo
then removed real ones. The switch is not that.

**Measured in Chrome.** Real draft with 4 picks; a fifth pick and the "Mock draft" link clicked in the same tick.
The real file held the 5 picks at the next version. The mock draft then played to pick 57: the real file did not
change. Back through "Real draft": 5 picks, mode real, no automatic-pick control anywhere.

What is left of the risk:

- **A stray click costs a page load and a click back.** No data changes. No confirmation needed.
- **A false alarm on the way back** (Q3).
- **Telling the two apart.** The mock page has the filled orange segment, a 2 px orange rule under the top bar and
  the tab title. That is less than the old "Rehearsal: other teams automatic" badge said. The real protection is
  that the mock page logs picks by itself at once, so nobody drafts for real there for long. The other mistake
  (practising by hand on the real page) is covered by "Continuing a saved draft: N picks" and Reset.
- **From the code, not run:** `--mock-file` may be the default real file as long as `--draft-file` is another one;
  the check only compares the two with each other. Refusing `saved_draft.json` as the mock file closes it.

I took your word that the user asked for both drafts inside one program. Given that, a route with its own service
and file is the right shape.

## 5. Small things from this step

- **Q1. The saved badge is empty after a reload.** Measured: a real draft with 6 picks at version 45, reloaded: the
  badge shows nothing until the next save. The page now starts with an empty badge and only a save fills it. Set it
  at the end of loading when the file has picks.
- **Q2. Round 1 wording.** At pick 1 the note says "the 13 teams yet to make pick 1 are scaled up to it"; they are
  left out, not scaled. The only team with a player shows "0.0/9". At pick 3 the Standing says "3rd now" under "the
  share of the other 13 teams you beat" when two others are compared. Say how many teams are compared, and leave the
  Score empty while one team is.
- **Q3. A notice that is not true.** After the sequence in section 4 the real page says "This browser had a copy
  with 5 picks that the file never received, but the file changed since", on every load until the next save. The
  file had received them; the page left before the answer came. Unlikely by hand (my two clicks were in one tick),
  and harmless. If the kept-aside copy has the same picks as the file, say nothing and mark it confirmed.
- **Q4. A pending change outlives its draft.** With a change waiting: a pick logged leaves "33 picks logged" on
  screen at 34; Reset leaves "34 picks logged. Apply: leave out PTS?" on an empty draft, and the next click applies
  it with the rest.
- **Q5. "change who will still be there" does not say what changes**, and a typed 99 becomes 20 on Apply without a
  word.
- **Q6. My team at the user's size is as it was.** Viewport 2436 x 1408: the column is 380 x 1322 and uses 523. The
  two columns need 760 px, which only a tab panel in a narrow window has.

## 6. For the user

- Whether "So far" should carry the sentence about scaled teams, or be left as it is.
- One mock draft in the real window, and its `innerWidth` and `innerHeight`. Still nobody has seen the page beside
  Yahoo.
