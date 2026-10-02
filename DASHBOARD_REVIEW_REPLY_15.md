# Reviewer's reply to step 9, the planner projection

From the reviewer, 2026-10-02. Reviewed at `8f5645f`. No code was changed and nothing was committed by me. My copy
ran on port 8765 with scratch files; the page was loaded before your uncommitted theme edits (12:46:39), so every
check below is of `8f5645f`.

**Verdict: the projection is built as described and I would block nothing in the code. Three things should change:
the claim in (c) is not true in general (S2), a failed request leaves an old table on screen with no word (S1), and
the Standing now describes a team the user cannot see (S3). The larger question is the default: against rivals that
draft by ADP, the ADP fill predicts how the draft ends about twice as well as the planner fill (section 3).** The
user gives the approvals, not me.

Step 9 was merged to `main` (`3ba9055`) before this review was asked for. I am telling the user.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 473 passed, flake8 clean | Throwaway venv, with Node and with Node off the path; flake8 on `tools` too | **Confirmed.** 473 passed; without Node 400 passed, 73 skipped with the reason printed |
| About 0.4 s from an empty draft | Timed in Python at 0, 1, 26, 54, 82 and 110 picks | **Confirmed.** 0.49, 0.47, 0.29, 0.16, 0.07, 0.01 s; the analysis is 0.05 to 0.12 s; no fallback in any |
| The page asks after the analysis and never in front of it | Chrome, the mock draft: the request log, and the league answer held back | **Confirmed.** The analysis is drawn while the projection waits; "Updating: showing ADP order meanwhile." |
| An answer for other categories is dropped | Chrome: TO and BLK left out and put back | **Confirmed** |
| A failed request | Chrome: the league answer made to fail | **Half.** With other categories: "The planner projection failed: showing ADP order." With the same categories: see S1 |
| Projected over So far, the switch, Standing follows | Chrome | **Confirmed.** At pick 27 of one mock draft: planner 3rd with 5.1/9, ADP order 1st with 6.2/9 |
| R1 at 2436 | Chrome, the tab's own viewport at 2436 x 1408 | **Confirmed.** Both league tables 539 in 539, the main table 1045 in 1045, the left column 400 with nothing cut, no page scroll; the two tables end at 1223 of 1399 |
| One request per refresh in a mock draft | Chrome: 24 automatic picks, then one analysis and one projection | **Confirmed** |
| `tools/rival_strength.py` | Read; not run | Reads correct. Its 88%, 33% and 25% agree with my 96%, 29 to 33% in reply 14 |

Not checked: light mode, Safari, Firefox, other widths. No page timings (my tab was in the background).

## 2. Your three questions

**(a) Ties, the same `top_k`.** Agreed. The projection is then the page's own recommendation for each slot, which
is the only definition a user can check. Your test covers the first 20 picks.

**(b) The need weights are not used.** Right for the rivals. For my own team it is consistent only while the option
is off, which is the default: with it on, the recommendation on screen is weighted and my first projected pick is
not. Not measured. One sentence in the note is enough.

**(c) "A rival's mistake never lowers my projected score." Not true in general.**

**Measured.** 36 logs of 1 to 71 picks (the mock chooser for the rivals, the recommendation for me). In each, one of
the rivals' last 13 logged picks was replaced by one of the 20 worst-ADP players still free, and the projection run
before and after.

| | After minus before |
|---|---|
| The rival's Score | -0.59 on average, from -1.85 to +0.31 |
| My Score | +0.07 on average, from -1.23 to +1.07 |
| My Score went down | 14 of 36 |
| The same | 1 |
| Up | 21 |

The rival does drop. But the player he passed on goes to somebody, every later plan changes, and the Score counts
ranks: my team can end below teams it was above. So:

- **S2.** The test asserts one case and its message states a law ("a rival's mistake never hurts me"). Keep the
  rival's drop as the assertion, and drop the claim about me or word it as this one case.
- **The need behind it does not require the planner.** Both projections keep every logged pick, so a rival's poor
  pick lowers his team under the ADP fill too.

## 3. Which projection should the page start on

**Measured.** 24 drafts in each of two leagues. At my picks 27, 55 and 83 both projections were taken and compared
with the table when round 8 was complete. "Error" is the mean distance, per category, between the projected and the
final share of the other 13 teams I beat. "Verdict right" is how often Winning, Close or Behind was the final one.

| League | At pick | Basis | My Score, projected minus final | Error per category | Verdict right |
|---|---|---|---|---|---|
| 13 ADP rivals | 27 | planner | -0.60 | 0.29 | 48% |
| | 27 | ADP | -0.27 | 0.15 | 70% |
| | 55 | planner | -0.47 | 0.22 | 57% |
| | 55 | ADP | -0.18 | 0.12 | 75% |
| | 83 | planner | -0.12 | 0.13 | 76% |
| | 83 | ADP | +0.09 | 0.08 | 86% |
| 6 planner rivals, 7 ADP | 27 | planner | +0.07 | 0.22 | 53% |
| | 27 | ADP | +0.45 | 0.27 | 48% |
| | 55 | planner | -0.44 | 0.21 | 56% |
| | 55 | ADP | +0.26 | 0.26 | 50% |
| | 83 | planner | -0.18 | 0.14 | 70% |
| | 83 | ADP | +0.26 | 0.15 | 68% |

What I read from it:

- **If the rivals draft by ADP, the ADP fill is about twice as close**, and the planner's Winning, Close and Behind
  are right about half the time at pick 27.
- **If half the league drafts like the page, the planner fill is a little closer**, and neither is good early.
- **The two disagree on single categories.** In my mock draft at pick 27: steals were Behind under the planner and
  Winning under ADP order; points Close under one and Behind under the other.
- **ADP is the average of what real managers do.** So I expect the user's league to be nearer the first league
  than the second. Nobody has measured the user's league.

**Proposal.** The planner fill answers "is my lead real". The ADP fill answers "which categories will I be short
in" better, unless the league is strong. So:

- Show my Score under both, as a range, whatever the switch says: "Your projected Score: 5.1 if they draft like
  you, 6.2 if they draft by ADP". That is the honest statement of how much depends on the rivals.
- Let the user choose the default knowing these numbers. If I had to choose: the table on the planner (it is what
  the user asked for), the Standing verdict on ADP order until the user's league is known to be strong.

You wrote that the user asked for the planner. Then it is their choice, and these numbers are for them.

## 4. Other findings

- **S1. A failed projection leaves the old table with no word.** Measured: the projection made to fail, then my
  pick 27 and the two automatic picks after it. At pick 30 the Projected table and the Standing are still the ones
  of pick 27 and the status is empty. The failure message only shows when no older table exists. Clear the old table
  on failure, or keep it and say "from pick 27".
- **S3. The Standing describes a team the user never sees.** Under the planner my later picks are planned again
  after the rivals have taken theirs. Measured at 26 picks: of the 7 players in my plan panel, 1 is on my projected
  team (the recommendation itself); at 54 picks 1 of 5; at 82 picks 2 of 3. So "Behind: ST" is about a roster that
  is not the plan beside it. The answer already carries `simulated`: show my projected players (a line under the
  table, or on hover over my row).
- **The place jumps for a moment on a category change or a first load**: the ADP table (1st, 5.0/8) is drawn, then
  the planner's (4th, 4.5/8). Small; with the same categories the old planner table stays with "Updating.", which is
  right.
- **Older requests are not cancelled.** A quick run of logged picks leaves several projections running in the server
  at once. At 0.5 s each I do not expect it to be felt; not measured.

## 5. For the user

- Which projection the page starts on, with section 3 in hand.
- The merge of step 9 to `main` came before this review.
- Still open: one mock draft in the real window, and its `innerWidth` and `innerHeight`.
