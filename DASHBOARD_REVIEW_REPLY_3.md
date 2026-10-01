# Reviewer's reply to DASHBOARD_STEP3A1_REPORT.md and DASHBOARD_WIREFRAME.md

From the reviewer, 2026-10-01. Reviewed at `8e6d475`. No code was changed and nothing was committed by me.

**Verdict: step 3a-1 is accepted. Step 3a-2 can start in the agreed order once the user approves it, with one
addition to the availability change (G1). The wireframe's shell is right; it needs six additions before any layout
code (step 6), none of which holds up 3a-2.** The user gives the approvals, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 250 passed, flake8 clean | Throwaway venv, Node v22 on the path | **Confirmed.** Without Node on the path: 228 passed, 22 skipped (G3) |
| F1: no waiting alternative contains the recommended player | My own walk over the 111 ADP-order states, page defaults and capped with games not counted | **Confirmed.** 0 of 618 in both settings (103 waiting states each) |
| Six alternatives by score are enough | Compared, in every state, against a search over every first-pick candidate with no budget | **Confirmed.** In 111 of 111 states, both settings, the best alternative is among the six |
| Labels | Chrome, 2 picks made and 26 picks made | **Confirmed.** "If Chet Holmgren is gone by pick 27, take instead: Kawhi Leonard (1.2 lower), ..." and "Or take instead: ..." |
| F5: per-search node counts | The answer's `search` block in Chrome | **Confirmed.** `mainNodes` 4,069 and `maxOptionNodes` 418 at 2 picks made |
| Clamping of saved values | Seeded `localStorage` with 0, 5, 9 and -3, reloaded | **Confirmed.** Inputs show 0.1, 1, 0.95 and 0; no error banner; the page loads |
| Clamping of typed values | Typed blank, 99, -5 and "abc" | **Confirmed.** 2, 20, 0.05 and 0.2; the request is accepted |
| F2: row marked while the reply is late | 600 ms delay on `fetch`, `MutationObserver` on the row | **Mark confirmed, threshold not.** The row shows "Logging the pick" and is removed on the reply. My tab was in the background this time (a 50 ms timer took 206 ms), so the mark came at 1.1 s. It hangs off the same timer I measured at 200 to 201 ms in step 2 |

Not checked: real light mode, Safari, Firefox, widths other than my window. Same gaps as before.

## 2. Your five questions

**1. Is "waiting" the right definition of "may be gone"? Yes.** First remaining pick later than the pick on the clock.
Do not add the model's odds on the clock: the player is on the board, and the user can see him there. A model saying
"under 50%" about a visible player would be the page contradicting the draft room.

**2. The 0.05 threshold and the six alternatives: both accepted.** Two notes.

- The six are enough on the evidence above.
- The constant is redundant with the server's rounding. `behind` arrives rounded to one decimal, so `>= 0.05` means
  "not zero after rounding". Keep the rule in one place: either compare with 0 in the page, or round in the page.

**3. The wireframe:** section 4.

**4. `logic.js` under Node: accepted, on three conditions.**

- It stays free of the DOM and holds no scoring or draft logic, ever. The project's rule is one Python core; this file
  is for what can only happen in the page (reading a box, reading storage).
- The server still accepts both pick shapes in 3a-2, as planned. Then a migration bug cannot lock the page out.
- The skip must not be quiet (G3).

**5. Can 3a-2 start in that order? Yes**, with G1 folded into the availability change.

## 3. Findings

### G1. "Last verified pick" is not enough once a seen pick follows unseen ones

My last reply said to condition on "the last pick at which the pool was verified". That is right only while the
unseen picks are the most recent ones. Your wireframe (correctly) lets the user log the next pick normally while
unseen picks are outstanding, and then they sit in the middle of the log. Neither reading of "last verified" is right
there.

**Measured**, default model, picks 21 to 26 unseen, pick 27 seen, pick 28 on the clock, my pick at 30:

| Player ADP | Conditioned on the last logged pick (27) | Conditioned on the last pick before any unseen one (20) | Product over unseen and future picks |
|---|---|---|---|
| 22 | 62% | 20% | 25% |
| 26 | 75% | 40% | 46% |
| 30 | 84% | 59% | 64% |

The first column ignores the unseen picks entirely. The second forgets that pick 27 was seen. The third is the rule
I now propose: a player's chance of being there is the product, over every pick that is unseen or still to come, of
his chance of surviving that pick given that he survived the ones before it. Seen picks contribute nothing, because
the pool was observed. With no unseen picks this is exactly today's formula. With unseen picks only at the end it is
the formula from my last reply.

Consequences to build in:

- **Marking a player as gone removes one unseen pick from the product**, so everyone else's odds rise. When no unseen
  pick is left, the odds are exact again.
- **A sanity test.** Summed over the pool, the expected number of players gone in k unseen picks should be near k.
  A rough count of mine gave 7.5 for 6 unseen picks, so the model over-counts by about a quarter. Either scale the
  per-pick chances so the sum is k, or accept it and say so. Decide with a test, not by eye.

### G2. On the clock, "same" can mean "the same team in the other order"

**Measured.** In 3 of the 8 on-the-clock states (picks 27, 55 and 83, the first of each pair of my picks) an
alternative shown as "same" is the recommended plan with its first two picks swapped: "Kawhi Leonard (same)" takes
Holmgren at 30. That is legitimate on the clock, and the score really is the same. What differs is the odds: the plan
then needs Holmgren to last three more picks (plan odds 12% against 13%; 52% against 56% at pick 83).

Small, and for step 7: when an on-the-clock alternative's plan takes the recommended player at my next pick, say so,
with his odds of lasting ("Kawhi Leonard now, Holmgren at 30 if he lasts", followed by that percentage), instead of
"same".

### G3. Without Node the page-logic tests skip, and nothing says so loudly

228 passed, 22 skipped. A step report that says "all passed" on a machine without Node would be true and
misleading, and the migration will live in this file. Put the skipped count in every step report, and say in the
README that the page-logic tests need Node.

## 4. The wireframe

**What is right, and should not change:** the page does not scroll and the table is the only scrolling region; the
recommendation is large only on the user's turn; every planned panel has a box; extra width becomes panels, not
margins; at 960 px the table keeps the full width with the name column fixed; the "At pick" column changes to the
following pick on the clock; the swap dialog. I also agree with your rule that panels become tabs and never drop
under the table.

**Six additions before layout code.**

**W1. There is no height budget, and at 1280 px the rail does not fit.** The drawing is about width only. At 1280 the
rail stacks REC, PLAN, MY TEAM, STANDING and a tab panel. My estimate, from the row heights the drawing implies: about
90 px for the compact recommendation (about 200 on the clock), 230 for a seven-line plan, 310 for ten slots and the
bench, 240 for nine categories, 340 for a 14-row tab. That is about 1,200 px waiting and 1,300 on the clock, in a
window that may be 950 px high on a 1080-line desktop. So either the rail scrolls, which breaks rule 1, or something
collapses. Please state the minimum height the design holds at, and what gives way first. Ask the user for
`innerHeight` along with `innerWidth`.

**W2. Nothing is drawn between 1280 and 1900 px, and those are likely widths.** Half of a 3440 or 3840-wide desktop
is 1720 or 1920. At 1720 the table and one 360 px rail leave about 460 px empty, enough for a third column, but the
drawing goes from two columns straight to four. More useful than another drawing: give the order in which panels
come out of tabs as width grows (I would say REC, PLAN, MY TEAM, STANDING, then 14 TEAMS, then LOG) and add a 1720
column to the "what drops out" table. That order is the real specification of a fluid grid.

**W3. The unseen-picks state contradicts the availability decision, and has no way in.**

- It says rows "show odds that assume nothing is gone yet". The decision is the opposite: rows show the chance that
  the player is still there given what was last seen (G1). I assume this is wording; please fix it so nobody builds it
  as written.
- There is no box for entering unseen picks. Give it one in the top bar. And ask for the draft's current pick
  ("Yahoo is at pick 31"), not for a count: the user comes back to a pick number on Yahoo's screen and should not do
  subtraction under a clock.
- "Mark as gone" on a row knows the player but not which team took him. E2 must not credit him to a team unless the
  user fills the pick from the log. Say which it is in the 14-team panel.

**W4. The position filter has no box.** All, PG, SG, SF, PF, C exist today and are used with the search. They belong
directly above the table.

**W5. Search belongs with the table, and Reset does not belong next to Undo.** At 2560 px the search box sits in the
middle of a bar 2,500 px wide while the table it filters is at the left. Put search and the position filter at the
head of the table column. Undo is the most used button on the page and Reset destroys the draft; move Reset into the
settings panel.

**W6. Show the last logged pick permanently, and the log can stay a tab.** This answers your third question to the
user. What the user needs while logging is confirmation of the pick just made, with Undo beside it ("Logged pick 24:
Tyrese Maxey. Undo"). One line next to the search does that at every width and costs no rail height. The full log is
then for looking back, and a tab is fine.

**On the 960 px question (tabs or a narrow rail):** my opinion for the user is tabs, as drawn, on one condition. On
the clock is when the user needs the recommendation, the plan and the team's standing together, with a timer
running. Tabs put those behind clicks at exactly that moment. So at 960 px the on-the-clock block should carry
enough to decide without switching: the recommendation, the reason, the alternatives line, and one line of standing
(the contested categories). I would not build the narrow-rail variant until the real width is known; the user can
also simply give the dashboard more than half the screen.

**Not missing a box, but worth a line in the file:** where the "search stopped early" note goes, and that "Other
strong plans" is dropped (I agree with dropping it).

## 5. Ready for 3a-2?

Yes. Order as agreed: schema v2 with the server accepting both pick shapes, the outside-the-list kind, the
availability change (as the product in G1, not a single "last verified" number), then the unseen kind and its entry.
The migration goes in `logic.js` with Node tests, and the server's tolerance of both shapes is the safety net.

For the user to decide: approval of 3a-2, and the three wireframe questions, plus `innerHeight` (W1).
