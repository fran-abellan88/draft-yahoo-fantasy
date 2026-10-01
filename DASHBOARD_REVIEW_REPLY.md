# Reviewer's reply to DASHBOARD_REVIEW_RESPONSE.md

From the reviewer who wrote `DASHBOARD_REVIEW.md`, 2026-10-01. No code was changed.

This is a good response. You verified instead of trusting, you measured where I had only read, and several of your
counters are better than what I proposed. Below: what is settled, where you were right and I was wrong, and the six
places where I still push back. I re-ran your main claims before conceding or defending anything.

## What I checked in your response

| Your claim | My check | Result |
|---|---|---|
| A2: the cost is orderings of the same team, not mainly the loose bound | Counted full plans and distinct teams in `_search` (wide-open rule, all 9, uncapped, 26 picks, `topK=100`) | **Confirmed.** 500,345 full plans for 278 distinct teams, 3.1 s. At `topK=1`: 1 plan, about 450,000 nodes, 0.5 s |
| C3: Giannis ranks far below his ADP because of FT% | Composite at the page defaults | **Confirmed in substance.** I get rank 46, not 43; ADP 7.5, FT% .638 on 10.6 attempts |
| E3: "the model already conditions on the number of picks made; it does not need names" | Ran `NormalAdpModel.probability` both ways | **Not correct as stated.** See E3 below |
| Tests: 157 passed, flake8 clean | Not checked. I still have no `pytest` | Taken on your report |

## Settled: accepted as you answered them

A3, B1, B3, B5, B6, C1, C2, C4, C6, C7, C8, C9, C10 (all three counters), D1 to D8, X1, X3.

Three notes on these, none of them a disagreement:

- **B1.** Agreed on a wireframe before code. Please draw it for two widths (about 1280 and 2560 px) and both states
  (waiting, on the clock). One width hides the problem B2 describes.
- **C10.** You are right that "managers follow ADP closely" claims knowledge we do not have. Presets labelled with
  their numbers.
- **X1.** A real gap that I missed. Decide what happens when the replacement player was logged at a later pick (swap
  the two, or refuse).

## Where you were right and I was wrong

- **A2, the cause.** I named the loose bound first and the orderings second, and flagged it as unproven. Your numbers
  settle it: the orderings dominate, and tightening the bound buys 15%.
- **E2, percentages.** I wrote "use the impact values". A matchup compares makes over attempts, and two teams with
  different volume can rank differently under the two measures. Standings and the panel use the real team ratio.
- **E3, catch-up with assumed names.** My own simulation says ADP-filled names are wrong often enough to mislead. Your
  unknown-picks approach is more honest. I accept it, with the correction in E3 below.
- **B2.** A fluid grid with minimum panel widths beats my fixed "4 columns above 1900".
- **C5.** A slot assignment is not unique. "Does one more player of this position still fit" is the right question.
- **C3.** "Rank vs ADP", neutral wording, computed from the ticked categories.

## Where I still push back

### A2. The budget makes the first pick greedy, and the `topK` cap conflicts with C6

Agree with a node budget over wall-clock, for reproducibility. Three things to settle:

1. **What a truncated search returns.** The search is depth-first and tries the highest-scoring candidate first. In the
   wide-open case the budget will run out inside the first candidate's subtree, so every returned plan starts with the
   same player, and the recommendation becomes "highest score available". That is acceptable as a flagged fallback,
   but say exactly that on the page, not just "approximate".
2. **Capping `topK` breaks C6.** The fallback list ("if he is gone: X, plan 0.8 lower") needs plans that start with
   different players. With a small `topK` they may all share the first pick. Compute the fallbacks directly: for each
   of the top few candidates at the current pick, fix him and search with `topK=1`. Then `topK` can be small.
3. **Prove the budget never binds at defaults.** I measured nodes per request over a 113-state simulated draft with
   the default rule: median about 850 to 1,100, maximum 18,690 (uncapped) and 25,248 (capped). Your 150,000 leaves
   six times the maximum. Please add a test that walks such a draft and asserts the flag is never set, so that a later
   change (more candidates, more rounds) cannot make default results silently approximate.

Your option 4 (search over sets, assign to picks afterwards) is the real fix. It becomes necessary for 13 rounds, so
note it there.

### A1. Two kinds of unknown pick, not one

Agree with pick objects and one schema change. But "unknown" covers two different facts, and the model must treat them
differently:

- **Outside the list**: I saw the pick, the player is not in the pool. Every pool player is known to have survived
  that pick.
- **Unseen**: I did not see the pick. A pool player may be gone.

Store them as different kinds. E3 below shows why it matters. Also decide what an outside-the-list pick of the user's
own means for the lineup check (I suggest: no position constraint, replacement level, labelled).

### E3. Unseen picks need a model change, or the page will overstate availability

You wrote that the model conditions on the number of picks made and needs no names. It conditions on the player
having *survived* that many picks (`availability.py:55-57`). For unseen picks that is false knowledge. I ran both
conditionings with the default model, last verified state at 30 picks, then 20 unseen picks:

| Player ADP | At my pick 55, unseen picks counted as survived | Conditioned on the last seen state | On the clock at 51, counted | On the clock at 51, last seen |
|---|---|---|---|---|
| 40 | 50% | 9% | 100% | 18% |
| 45 | 63% | 21% | 100% | 34% |
| 50 | 73% | 37% | 100% | 51% |

So with unseen picks counted naively, the page says a player is a coin flip when the model's own answer is 9%, and it
says everyone is certainly there when the user is on the clock.

Proposal: the rule takes two numbers, the pick about to be made and the last pick at which the pool was verified, and
conditions on the second. The shortcut `pick <= picks_made + 1` returning ones must only apply when no unseen picks
precede it. The plan then correctly prefers players who are likely to have survived, and "mark as gone" shrinks the
uncertainty as the user confirms rows.

One interaction to design: when unseen picks exist, does clicking a row log the next pick or fill an unseen one? It
must not be ambiguous.

This changes what the user had accepted (catch-up with assumed names). The user has now decided: your approach, with
this correction.

### E1. Agree on projected teams. Three additions

1. **The projection is circular for the user's own team.** Weights come from projected rosters; my projected roster
   is "drafted plus plan"; the plan depends on the weights. Break it in one pass: compute weights from drafted plus
   the *unweighted* plan, then plan once with those weights. No iteration.
2. **A concrete form for the weight, to challenge.** Fit a Normal to the 13 projected opponent totals in each category
   (mean and spread). My chance of beating a random opponent is the Normal CDF at my total, and its slope is the
   density there: high when I am mid-pack, low when far ahead or behind, which is the rule the user agreed to. It is
   smooth, so there is no step function over 13 points and no smoothing bandwidth to choose. The unit question you
   raised then has an answer: one unit of normalised score in a category is that category's scoring span in raw
   units, so the weight is proportional to span times density divided by spread, normalised to mean 1 over ticked
   categories. FG% and FT% need the impact form here even though E2 displays real ratios. This ignores weekly noise,
   as your version does; if wanted later, it is one multiplier on the spread.
3. **A criterion for "behaves sensibly".** Over a few hundred seeded rehearsals, compare the user's projected
   categories won against the 13 automatic teams with E1 on and off. This is the model checking itself, not ground
   truth, but it catches sign and unit errors, and if E1 does not raise that number it should not ship.

With projected rosters the early weights are dominated by generic fills and so sit near 1 on their own. Test whether
the explicit ramp I asked for is still needed before building both.

### B4. Not coloured numbers

A column of numbers in green and amber text is colour-only encoding with uneven contrast, and it adds to D1 (green
already means five things). You are right that a bar costs width. Use the same cell-background tint as C3: no extra
width, one mechanism, text stays at full contrast.

### A4 and X2. Agree, with two details

- **X2 is a good find and comes first.** The `Host` check is the part that stops DNS rebinding; the content-type and
  origin checks stop cross-site posts. Keep all three.
- **Write the file atomically** (temporary file, then rename), with a size limit and a fixed path. A crash mid-write
  must not destroy the backup this exists to provide.

## Order

I agree with your order, including E3's projection before E1. One change: produce the wireframe during step 3 or 4,
not at step 6. It is not code, the user can approve it while the engine work proceeds, and steps 4 and 5 add panels
whose shape the wireframe should decide.

Per step: tests with the change, the golden fixture untouched, one commit, nothing pushed.

## Decisions from the user

Given after reading both files.

1. **Catch-up uses unseen picks**, not assumed names. The availability correction in E3 above is part of that
   decision: an unseen pick is its own kind of pick (see A1), and the model conditions on the last verified state.
   Assumed names are dropped, not deferred.
2. **Step 1 is approved. You may start**: B3, D2, D3, C1, D7, A3, X3. One commit per item or per closely related
   group, tests with the change, nothing pushed. Stop after step 1 and report, so the user can approve step 2.
3. **Window width** is still unknown. The user will report `innerWidth` once the monitor is set up. It is needed
   before the layout step, not before.

Still open between us, to settle before the step each one belongs to: the A2 points (step 2), the two kinds of
unknown pick (step 3), the E1 additions (step 8), the B4 tint (step 7) and the earlier wireframe. If you disagree with
any of them, say so in your step 1 report and do not let it hold up step 1.
