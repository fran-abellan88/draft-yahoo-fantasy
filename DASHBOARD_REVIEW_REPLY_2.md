# Reviewer's reply to DASHBOARD_STEP2_REPORT.md

From the reviewer, 2026-10-01. Reviewed at `682b3b2`. No code was changed and nothing was committed by me.

**Verdict: steps 1 and 2 are accepted. Step 3 is ready to start once the user approves it, with one change of order
inside it and one defect from step 2 to fix first (F1).** The user gives the approval, not me.

## 1. What I checked

| Your claim | How I checked | Result |
|---|---|---|
| 213 passed, flake8 clean | Throwaway venv from `requirements-dev.txt`, `python -m pytest`, `python -m flake8` | **Confirmed.** 213 passed in 14.7 s, flake8 clean |
| The frozen case now takes about 0.5 s and is flagged | `DraftService.analyze` in process, and the page in Chrome | **Confirmed.** 451 to 536 ms end to end in the page, `truncated` true, 330,007 nodes. The three other slow cases from my review (was 8.0 s, 2.8 s, 2.2 s) are now 0.6 to 0.7 s, measured while other jobs were using the CPU |
| Foreign `Host` 403, foreign `Origin` 403, `text/plain` 415 | `curl` against a copy on port 8765 | **Confirmed**, plus 5 cases you did not list (below) |
| Busy state at 200 ms | Chrome tab with `visibilityState` "visible", focused, a 50 ms timer measured at 51 ms; `MutationObserver` on `main` | **Confirmed.** On at 200 to 201 ms, off when the reply lands (451 to 536 ms). Never on for a 67 ms default request |
| Error banner fixed, Retry, unconfirmed pick | Replaced `fetch` with a rejecting stub, clicked a row, then restored it and clicked Retry | **Confirmed**, with one timing remark (F2) |
| Sort arrow, `aria-sort` on the `th` | Chrome | **Confirmed.** `th[aria-sort="ascending"]`, arrow drawn |
| D3 | Screenshot in dark mode | **Confirmed.** The unticked radio is dark now |
| The budget never binds at defaults | Every state (0 to 111 picks) of an ADP-order draft, for 108 settings, not only your two | **Confirmed and widened.** 12,096 requests, none cut short. See F5 for the margin |

Server checks beyond your list, all as they should be: `Host` with the right name and the wrong port 403; `Host`
without a port 403; lookalike `127.0.0.1:8765.evil.example` 403; `Origin: https://` on the right host 403;
form-urlencoded 415. `localhost:8765` and a `charset` suffix are accepted. No CORS headers on replies.

Not checked by me: real light mode, Safari, Firefox, widths other than 1624 px. Same gaps as before.

## 2. Findings on steps 1 and 2

### F1. "If X is gone, take instead" still plans on X. Fix before step 3

The alternatives fix one player as the first pick and leave the later picks' candidates unchanged
(`optimizer.py`, the `_search([[by_id[player_id]]] + candidates[1:], ...)` call). So the "gone" player can come back
at a later pick, and the cost in brackets assumes he is still available.

**Measured.** Over the 111 states of an ADP-order draft at the page defaults, 555 alternatives were priced. In **98 of
them (18%)** the alternative's plan still contains the recommended player. Example at 19 picks made, waiting for pick
27: the page recommends Chet Holmgren, and says "if he is gone" Kawhi Leonard is 0.0 lower. That plan takes Holmgren
at pick 30. It is the same team in another order, which is why it costs nothing.

This is also the real reason for the ties you saw under a cut-short search ("same", "same", "same"): with a wide-open
rule every alternative is the same team reordered.

**Proposal.** The line answers two different questions, so give it two forms:

- **Waiting** (the recommended player may be taken before my pick): remove him from every pick's candidates in the
  alternative searches. Label: "If Holmgren is gone by pick 27, take instead: ...". The cost is then what losing him
  really costs.
- **On the clock** (he is available, the question is what another choice costs): leave him in. Label: "Or take
  instead: ...". "If he is gone" makes no sense when the user can see him on the board.

Add a test: in the waiting form, no alternative's plan contains the recommended player.

Related: `behind` is clamped at 0 (`service.py`, `_alternatives`). When the main search is cut short, an alternative
can find a better plan than the "best" one, and the clamp hides it as "same". With the answer to 2(b) below this
stops mattering, but do not rely on the clamp elsewhere.

### F2. A failed pick shows nothing at the row for 1.4 s

**Measured.** With the server unreachable: attempts at 0, 702 and 1404 ms, banner and "not confirmed" badge at
1421 ms. Until then the clicked row looks untouched. The hero dims after 200 ms, but the user is looking at the table.

**Proposal.** Mark the row as pending as soon as the reply is late (the same 200 ms threshold), then turn it into
"not confirmed" when the retries are spent. Small; do it with step 3's pick-object work, which touches the same
rendering.

### F3. New methods are outside the gate

**Measured.** `PUT`, `OPTIONS` and `HEAD` answer 501, because there is no handler. That is correct today. But the
check is called from inside `do_GET` and `do_POST`, so the `do_PUT` that A4 adds will be unprotected unless someone
remembers the call. Before A4: one place that every method passes through, and a test that walks every `do_*` method
on the handler and asserts a foreign `Host` gets 403.

### F4. A comment says more than the code does

`app.js:134` says the plan is "dimmed with a note". There is no note, only the dimming. With a worst case near half a
second, dimming is enough. Fix the comment.

### F5. The budget holds over settings a user might choose; the tighter margin is the per-option one

**Measured.** 9 availability rules (probability with thresholds 0.3, 0.5, 0.7 and spreads from 1 / 0.1 to 4 / 0.4;
window with slack 3, 10, 20) x 3 category sets (all nine, without TO, without TO and FT%) x 2 methods x games counted
or not: 108 settings, every state of a 112-pick draft each. No request was cut short.

| Search | Busiest request | Budget | Headroom |
|---|---|---|---|
| Main | 15,471 nodes | 150,000 | 9.7 times |
| One first-pick option | 11,911 nodes | 30,000 | 2.5 times |

Both maxima come from the same setting: spread 4 / 0.4, all nine categories, capped, games not counted. So the user
can try configurations freely without results going approximate, which matters because the configuration is still
being chosen.

Your test asserts on the sum of all searches against half the main budget. The cap that would bind first is the
per-option one. Add an assertion on it (the busiest single option search stays under half of `OPTION_NODE_BUDGET`),
so the test fails for the right reason.

## 3. Your open points

**(a) Input limits not tightened: accepted.** Your reasoning holds: the budget now protects what the limits would
have, and narrower limits would turn saved values into permanent 400s. But that second point is a defect in its own
right, and it exists today: `restoreState` copies `saved.rule` without checking ranges, and the number inputs accept
typed values outside `min` and `max` (an empty field becomes 0). One bad value is saved before the request, so it
survives a reload. The user can retype it, so it is not fatal, but it should not wait for step 7. Clamp saved and
typed values to the server's ranges on load and on change, in step 3, where `restoreState` is being rewritten anyway.

**(b) Hide the alternatives line when the search was cut short: yes.** An approximate cost of an approximate plan is
noise, and the note above the plan already says why. With F1 fixed, also hide it whenever every alternative ties
with the best plan, cut short or not.

**(c) An outside-the-list pick of mine, for the lineup check.** Treat him as eligible at every position, at
replacement level, labelled "not in the list" in the roster. Reasons:

- He does occupy one of the ten starting slots, so leaving him out of the matching would let the plan fill a slot
  that is taken.
- "Any position" can never wrongly block a plan. A guessed position could.
- With 8 planned players for 10 slots it rarely changes the answer, so the cheap rule is enough.

If the user wants precision later, let them pick his positions when logging. Not now.

One related rule for step 3: **an unseen pick cannot sit on one of the user's own pick numbers.** The user always
knows their own pick. If "N picks I did not see" would cover one, the page must ask for that pick.

**(d) B4 tint against C3 tint.** You are right that one mechanism with two meanings would confuse. I would not solve
it with a second hue on a second continuous scale. The two columns answer different kinds of question:

- Category cells: a continuous single-hue tint (how strong). Not green, which already means "mine" (D1).
- Availability: a threshold, not a scale. Number in normal ink, and one flag tint (`--flag-soft`) on cells below the
  user's planning threshold, the same amber and the same threshold as the plan meter after C7.

Different in kind as well as in colour. To settle at step 7; this is my recommendation, not a decision.

## 4. X1: swap or refuse

**Recommendation: swap, with a confirmation that names both picks.** "Kawhi Leonard is logged at pick 47. Swap picks
40 and 47?"

- **The usual cause is a transposition**: the user fell behind and entered two picks in the wrong order. A swap is
  exactly that correction, in one action.
- **A swap cannot break the state.** The same players are logged before and after, so nobody enters or leaves the
  pool. Only order and ownership change.
- **Refusing forces a puzzle under time pressure.** The user would have to edit the later pick to something else
  first, to free the player, then come back. Two edits in a required order, with an error message to read.
- **When it is not a transposition, a swap costs nothing extra**: swap, then edit the later pick. Still two edits.
- **Why a confirmation and not a silent swap:** a pick the user did not touch changes. If either pick is the user's
  own, the roster changes, and the dialog must say so.

Offer one more choice in the same dialog if it is cheap: "I do not know what pick 47 was", which turns the later pick
into an unseen pick. That is the honest state when the user is unsure.

## 5. Step 3 order

Keep A4 last. Written before the schema change it would store the v1 shape and need its own migration. Nothing is
dropped. Three changes:

1. **Never expose unseen picks before the availability change.** Your order puts "A1 with two kinds of unknown pick"
   ahead of "availability conditioned on the last verified pick". In between, the page would show the overstated
   numbers from my last reply (63% where the model says 21%). Order: schema, then the outside-the-list kind (safe on
   its own), then the availability change, then the unseen kind and its entry in the page.
2. **Let the server accept both pick shapes** (a plain id and an object), and normalise in `_parse_picks`. There is no
   JavaScript test runner in this project, so a migration written only in `app.js` is the one piece of step 3 that
   pytest cannot reach. With the server tolerant of both, the page's migration is a trivial wrap and the logic that
   matters is tested. Leave the `draft-assistant-v1` key in place after migrating, so a rollback has data.
3. **Report in three parts**, so the user can approve them separately: (3a) schema, both unknown kinds, availability,
   the clamping from (a), F1 and F2; (3b) X1; (3c) F3 then A4. A4 should save the settings as well as the picks: the
   user fixes one configuration for the whole draft.

## 6. Wireframe

Your two widths and two states are the minimum. Add:

- **A third width, about 960 px.** Half of a 1920-wide desktop is a plausible window on the user's monitor, and it is
  where panels have to drop out. The wireframe should show which ones and where they go.
- **States that step 3 creates and nobody has drawn:** unseen picks present (how they are entered, how the pool looks
  while unverified, where "mark as gone" lives); the edit-a-pick dialog with the swap confirmation; the error banner
  with a pending and an unconfirmed row.
- **States from the review:** settings panel open and locked (C10); past the horizon (B6); the 14-team panel (E2);
  the mode indicator for rehearsal (E3).

To keep it small: every state at one middle width, and only waiting and on-the-clock at the other two.

## 7. Ready for step 3?

Yes, on these conditions: F1 is fixed first or as the first commit of 3a; the order in section 5; and the user
approves. Nothing in step 3 depends on the monitor's width.
