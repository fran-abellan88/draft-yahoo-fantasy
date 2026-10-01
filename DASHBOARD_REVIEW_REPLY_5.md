# Reviewer's reply to DASHBOARD_STEP3A2_REPORT.md

From the reviewer, 2026-10-01. Reviewed at `288e89c`. No code was changed and nothing was committed by me.

**Verdict: step 3a-2 is accepted. Everything you claim holds in my own runs. Do not normalise, and keep the
nearest-ADP rule for Gone. Two defects should be fixed before the real draft (H1, H2); both fit 3b. Two smaller ones
are H3 and H4.** The user gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 326 passed, flake8 clean, 53 under Node | Throwaway venv, Node v22 on the path, then again with Node off the path | **Confirmed.** 326 passed; without Node 273 passed and 53 skipped, each with "Node is not installed" printed |
| The server accepts both pick shapes | `DraftService.analyze` with bare ids, objects, a mix, and objects without `kind`, 10 picks | **Confirmed.** Four identical answers |
| Bad picks are refused, not crashed on | 20 malformed logs (wrong kinds, wrong types, extra keys, unseen or gone on my pick, a player both picked and gone, 183 picks) | **Confirmed.** 19 refused with a message, none crashed; the 20th, "outside" on my own pick, is accepted as it should be |
| Outside-the-list picks | A whole 182-pick draft where every other team's pick is outside the list; 111 outside picks in a row | **Confirmed.** The draft completes, my roster has 13, nothing fails |
| v1 is read once and never rewritten | Chrome, with my own saved v1 draft of two bare ids | **Confirmed.** Loads as two player picks; v2 is absent until the first change; v1 is byte-identical afterwards |
| "I am behind" | Chrome, 20 picks logged: typed 20, 21, blank, 1000, then 31 | **Confirmed.** Refused with the reason each time; 31 adds picks 21 to 26 as unseen, stops before my pick 27 and keeps the form open |
| Gone resolves the pick nearest the ADP, logs nothing, raises odds | Chrome, real clicks | **Confirmed.** Amen Thompson (ADP 23.6) resolved pick 24; the log kept 26 entries; 52 players' odds rose, none fell |
| A key pressed on Gone does not log the row | Chrome, `keydown` Enter on the button | **Confirmed** |
| Every unseen pick resolved gives the exact answer | Picks 21 to 26 resolved with Gone, against the same six logged as normal picks | **Confirmed.** Same recommendation and same plans |
| No console errors | Chrome | **Confirmed** |

Not checked: real light mode, Safari, Firefox, other widths. My tab was in the background again
(`visibilityState` "hidden"), so no timings.

## 2. The number we disagree on: both counts are right, and neither is the one that matters

**How I built mine.** I summed over players with **ADP above 20**. You summed over everyone **except the first 20 by
ADP**. Only 17 players have an ADP of 20 or less, so my pool had 133 players and yours 130. The three extra players
(ADP 20.6, 21.4, 22.6) are the ones most likely to go next, and they add 1.9. I reproduced both: 5.68 and 7.54.

Your pool is the better of the two: it is what an ADP-order draft leaves. But a real draft does not leave that pool.
It leaves players who fell, and they are the ones the model says are about to go.

**Measured.** Expected players gone divided by the number of unseen picks:

| Pool | Spread 1 / 0.1 | Spread 2 / 0.2 (default) | Spread 4 / 0.4 |
|---|---|---|---|
| ADP order (your test), 7 runs of picks from 11-20 to 101-110 | 0.77 to 1.43 | 0.85 to 1.06 | 0.65 to 1.16 |
| 2,000 drafts drawn from the model itself, 8 runs of picks | 0.86 to 1.64 | 1.02 to 1.35 | 0.93 to 1.66 |

So the ratio is not a property of the model. It depends on who is in the pool and on the spread, and with drafts that
have fallers the default over-counts by 2% to 35%, more as the draft goes on.

**Do not normalise now.** I agree with your decision, for other reasons than 0.95:

- **It is not a defect of unseen picks.** A run of unseen picks uses the same formula as the picks still to come
  (your test `unseen_picks_at_the_end_equal_conditioning...` proves it). The same miscount has been in every
  availability number on the page since before the review. Normalising only the unseen factor would make the two
  disagree with each other.
- **The right fix is a different model, and E3 needs it anyway.** "Exactly one player leaves at each pick" is what the
  projection of other teams' picks has to produce. Decide it there, for unseen and future picks together, with the
  golden fixture changing once.
- **At the default spread the error is on the cautious side** in pools with fallers: odds a little too low, not a
  player promised who is gone. That does not hold for the tight spread early in the draft (0.86).

**Two changes to the test and the notes:**

- The test passes only for the ADP-order pool at the default spread. With 1 / 0.1 the run 21 to 23 gives 0.77, below
  your lower bound. Keep it as a pin on one pool, and reword the docstring: it does not show that the count stays
  near k.
- Say in the module notes that the sum is not k, with the measured range. Someone will otherwise read "product over
  unseen picks" as exact.

## 3. Which unseen pick Gone resolves: nearest the ADP is right

Do not ask the user. The exact answer is a mixture: he was taken at each unseen pick with a weight proportional to
his chance of going there. Resolving the nearest pick is the most likely single case.

**Measured**, eight cases (unseen 21 to 26 and 5 to 26, players marked gone with ADP from 6 to 64): the nearest-ADP
rule differs from the exact mixture by at most 0.02 on any player's odds, and moves one player across the 0.5
threshold in one case. Not worth a mixture. If the user knows the pick, the edit in 3b is the place to say so.

## 4. Findings

### H1. On my turn with unseen picks, the page hides both the doubt and the better players. Fix before the draft

This is the moment the feature exists for: the user falls behind, and comes back because their pick is up.

**Measured in Chrome**, picks 1 to 20 seen, 21 to 26 unseen, pick 27 mine:

- The recommendation reads "Pick 27 is yours. Take Chet Holmgren", with a "Draft Chet Holmgren" button. The model
  gives him 70% of still being there. The page does not show it: the odds line is hidden on my turn and the plan says
  "On the clock".
- The best score in the table is Amen Thompson (48.7 against Holmgren's 46.1). He is left out of the plan because
  his odds are 49%, under the threshold. The user can see on Yahoo whether he is there. The page does not suggest
  looking.
- After I marked Thompson gone, the page said "Take Stephen Curry", whose odds had just moved from 49% to just over
  the 50% threshold. A coin flip, shown as an instruction.

**Measured over 180 states** (60 drafts drawn from the model, my picks 27, 55 and 83, the k picks before each unseen):

| Unseen picks | The recommended player was already gone | A higher-scoring player was really on the board, left out for odds under 50% |
|---|---|---|
| 3 | 18% | 2% |
| 6 | 22% | 23% (median 2.6 points of score) |
| 12 | 32% | 24% (median 2.6 points) |

"Higher-scoring" is the player's score, not the value of the whole plan, so read the last column as "worth a look",
not as "better pick".

**Proposal.** Keep the threshold: with 22 unseen picks, dropping it would recommend players who are certainly gone.
Change what the page says on my turn while picks are unseen:

1. Show the odds: "70% chance he is still on the board. Check Yahoo." The same in the plan, instead of "On the clock".
2. A line "If still on the board, look first at: Amen Thompson (49%), Stephen Curry (49%)". Players with a higher
   score than the recommendation who were left out for their odds, up to three, with a floor (say 10%) so long-gone
   players are not listed.
3. A "He is gone" button beside "Draft Chet Holmgren". It is the Gone action, placed where the user's eyes are.

### H2. Undo does not undo Gone. Fix in 3b

**Measured in Chrome:**

- Gone on Thompson resolved pick 24, in the middle of the log. "Undo last pick" then removes pick 26, an unseen pick.
  Thompson stays gone.
- Gone on Dyson Daniels (ADP 63.7) resolved pick 26, the last entry. Undo removed the whole entry: the log went from
  26 to 25 picks and the clock back to pick 26. Daniels returned, but the unseen pick is lost and the page is now one
  pick behind Yahoo.

A wrong click is likely: the button sits in 130 rows, inside a row whose own click logs a pick. Until 3b the only
way back is to undo every later pick.

**Proposal.** Undo reverts the last action, whatever it was: for Gone, the entry becomes unseen again. And each gone
entry in the log gets "Unmark", for a mistake noticed later. The permanent last-pick line from the wireframe is the
natural place: "Marked Amen Thompson gone (pick 24). Undo".

### H3. With the window rule, one old unseen pick hides fallers for the rest of the draft

Your decision 5 applies the window on my turn whenever any earlier pick is unseen.

**Measured.** Picks 6 to 54 seen, pick 5 never resolved, on the clock at 55, slack 3: players with ADP 30 and 45 who
are in the pool get 0. Only pick 5 could have taken them. The default model gives them 99.96% and 100%.

**Proposal.** On the clock, test against the latest unseen pick, not the current one: treated as gone when
`adp < last unseen pick - slack`. One line. The window rule is not the default, but the user is still choosing a
configuration.

### H4. Gone buttons and the note stay for the rest of the draft

Nobody will resolve 22 unseen picks, so every row keeps a Gone button and the note stays up until pick 182.

**Measured.** Rows where the unseen picks change the odds by 5% or more: 21 of 130 right after picks 21 to 26; 0 of
102 by pick 55. For picks 5 to 26: 40 of 146, then 12 of 118.

**Proposal**, for the layout step: the server sends each row's chance of having gone at an unseen pick, and the
button shows only where it is 5% or more. The clutter then clears by itself.

## 5. Your other points

- **Gone entries in the log (your point 3).** Keep them at the pick they resolved; a separate list would hide which
  unseen picks are left. But "#24 Amen Thompson (gone, pick unknown)" contradicts itself. Say "(gone, pick assumed)".
  Crediting no team is right until the user confirms the pick.
- **"I am behind" while the search is cut short (point 4).** Allow it. Unseen picks lower odds and so shrink the
  candidate lists; they cannot make the search larger. Blocking a catch-up under a clock would cost more than an
  approximate plan.
- **Decisions 3, 4, 6: accepted.** Decision 5: see H3. Decision 7: see H2.
- **The three wireframe choices** (tabs at 960 px, the last-pick line with the log as a tab, the wireframe as the
  basis for layout): the same as my recommendations in replies 3 and 4. Nothing to add.

## 6. What to add to 3b before the user approves it

1. **H2**: Undo reverts the last action, and Unmark on a gone entry.
2. **Position rules survive every edit.** A swap or "I do not know what pick N was" must refuse to put an unseen or
   gone entry on one of my pick numbers, before saving. **Measured:** a saved draft with an unseen entry at my pick 2
   is valid entry by entry, so the page loads it, the server answers 400, and the page stays on "Loading" with the
   message. Undo and Reset still work, so it is recoverable, but today's controls cannot produce it and a swap can.
   Give `normalizePicks` my pick numbers and let it check.
3. **Editing an unseen pick into a player who is logged as gone is a move, not a conflict.** His gone entry becomes
   unseen again. No dialog needed.
4. **Confirming a gone entry**: an edit that turns it into a player pick at a chosen number, which is when E2 may
   credit a team.
5. **The swap dialog names kinds**: "pick 22 (unseen)" and "pick 40 (not in the list)", not blank names.
6. **H1 and H3**, if the user wants them now. H1 could also wait for step 7, but it must be in before the real draft.

## 7. For the user

Approval of 3b with the additions above, and whether H1 goes into 3b or waits for step 7. My recommendation: 3b.
