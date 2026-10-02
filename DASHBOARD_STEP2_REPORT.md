# Step 2 report: server safety (X2) and bounded search (A2)

From the agent that builds the dashboard, 2026-10-01. For the reviewer. Nothing is pushed.

## Where things stand after steps 1 and 2

Branch `feat/2026-27-projections`, 9 commits of mine since the review, **none pushed**. Suite: 213 passed, flake8
clean, golden fixture untouched. One commit per item or closely related group, tests with each change.

### Implemented

| Step | Finding | Commit | What it does now |
|---|---|---|---|
| 1 | B3 | `cc4e234` | `[hidden]` wins over display rules, so the unused availability fields really hide |
| 1 | D3 | `cc4e234` | `color-scheme: light dark`, so dark-mode radios and scrollbars match |
| 1 | D2 | `5497da9` | One `--on-mine` text token; the dark snake cell on the clock is 7.98:1 (was 1.98:1); "done" cells use `--ink`. A test checks 6 colour pairs in both themes |
| 1 | D7 | `98d6074` | Table header says 3PTM like the category list; a test keeps the two in step |
| 1 | C1 | `eb7ee5c` | `aria-sort` on the `th`, with a ▲ or ▼ arrow |
| 1 | A3 | `cfd592d` | Error banner is fixed on screen with a Retry button; a network failure is retried twice on its own, a rejected request is not; a pick the server has not confirmed is marked in the table and clicking it retries |
| 1 | X3 | `28e8817` | README says the tests need `requirements-dev.txt` |
| 2 | X2 | `edb424a` | `Host`, `Origin` and `Content-Type` checks on every request (403 or 415) |
| 2 | A2 | `ee6aa1f` | Node budget (150,000, and 30,000 per first-pick search), a `truncated` flag shown on the page, first-pick alternatives searched directly, `topK` default 10 and cap 50, busy state after 200 ms |
| 2 | A2 docs | `cb048ff` | README explains the "search stopped early" message |

### Not yet done, in the agreed order

| Step | Content | Notes |
|---|---|---|
| 3 | Storage schema v2 (picks as objects, `draft-assistant-v2`, migration from v1); A1 with two kinds of unknown pick (outside the list, unseen); availability conditioned on the last verified pick (E3 correction); X1 edit any logged pick; A4 server-side saved draft | Atomic write, size limit, fixed path, version counter, confirm on load. Needs your answer on X1: swap or refuse when the replacement was logged at a later pick |
| 3 or 4 | Wireframe for about 1280 and 2560 px, in the waiting and on-the-clock states | Not code; the user approves it while engine work proceeds |
| 4 | E2: all 14 teams scored, real FG% and FT% ratios, "so far" and "projected" readings | Replaces the category strength panel (C4) |
| 5 | E3 projection and rehearsal, in the Python core, seeded and lineup-legal, with a visible mode indicator | A prerequisite of E1 |
| 6 | Layout: B1, B2, C2, C10 | Designed against the approved wireframe; needs the real `innerWidth` |
| 7 | B4, B5, B6, C3, C5, C6 (rest), C7, C9, D4, D6 | B4 tint vs C3 tint still open (below) |
| 8 | E1 weights, behind a switch, off until rehearsals check it | Your two-step form: one-pass projection, Normal-fit weights |
| 9 | D1, D5, D8, C8 | Polish |

### Decisions the user has made

Catch-up uses unseen picks, not assumed names. Rehearsal mode and projection are wanted. Step-by-step approval. The
monitor is 32 or 49 inch with Yahoo's draft room beside the dashboard, `innerWidth` still to be reported.

### Open between us (from your reply)

- A2: I did not tighten input limits (see below). Hide the alternatives line when the search was truncated?
- A1: two kinds of unknown pick, agreed in principle; what an outside-the-list pick of mine means for the lineup check.
- B4 tint: the availability column and the C3 category tints would use the same mechanism with different meanings.
  My suggestion is a distinct hue for availability; to settle at step 7.
- E1: the one-pass projection and Normal-fit weight, to challenge at step 8.

---

Step 2 detail follows. It is three commits on `feat/2026-27-projections`:

| Commit | Item |
|---|---|
| `edb424a` | X2: refuse requests that do not come from the dashboard's own page |
| `ee6aa1f` | A2: work budget, truncation flag, direct first-pick alternatives, busy state |
| `cb048ff` | README note for the new "search stopped early" message |

Suite: **213 passed** (was 175 after step 1), flake8 clean. The golden fixture is untouched.

## X2: what the server now checks

Applied to every request, GET and POST:

- `Host` must be `127.0.0.1:<port>` or `localhost:<port>` for the port the server is on. Anything else, including a
  missing header or a missing port, gets 403. This is the DNS-rebinding check.
- `Origin`, when present, must be `http://` plus one of those hosts. `null`, other sites and other ports get 403. A
  missing `Origin` is allowed (same-origin GETs, `curl`, tests).
- POST must be `application/json` (a `charset` suffix is fine), otherwise 415. This is the cross-site-post check.
  Order: host and origin first, then path, then content type, then the size limit.

Tests: 19 new tests in `tests/test_server.py`, sending raw requests with exact headers (`http.client` otherwise fills
in `Host` itself). They cover foreign and portless hosts, a missing `Host`, foreign origins including `null`, the
accepted spellings (`LOCALHOST` too), four non-JSON content types and none, and the charset suffix.

I did **not** add a write endpoint. These checks come first, as agreed. A4 is step 3.

## A2: your three points, one by one

**1. What a truncated search returns: said exactly on the page.**
`plan_picks` counts nodes and stops at `NODE_BUDGET = 150,000` for the main search and 30,000 for each first-pick
search. A budget smaller than the default also caps the first-pick searches (a test found that the per-option cap
ignored a smaller overall budget; fixed). The answer carries `search: {truncated, nodes}`. When `truncated`:

- A note above the plan: "The search stopped early: these availability settings let so many players through that
  checking every plan would take too long. The plan is the best one found, not proven the best, and every plan starts
  with Jalen Duren, the highest-scoring player it tried first." The last clause appears only when every returned plan
  does start with the same player.
- If no plan was found at all, it says that and tells the user to narrow the availability settings.
- One line in the hero: "Approximate: the search was cut short."

**2. `topK` and C6: fallbacks are computed directly.**
For the best plan's first pick and the top six candidates by score, I fix that player as the first pick and search
with `top_k=1`. The result is `Recommendation.options`, each with its own best plan. That removed the dependence on
`topK`: the default fell from 100 to **10** and the request cap from 200 to **50**. The "choice across the best plans:
68%" line is gone. In its place: "If Nikola Jokic is gone, take instead: Shai Gilgeous-Alexander (3.3 lower), Victor
Wembanyama (7.7 lower), ...", where the brackets are how far the whole plan falls behind the best one. This is C6's
proposal, built early because the `topK` cap needed it. The "Other strong plans" list is unchanged (step 7).

**3. The budget never binds at defaults: a test says so.**
`test_the_work_budget_never_binds_with_default_rules_over_a_whole_draft` walks a simulated ADP-order draft (every
third state plus the state just before each of my picks, which is where the search is busiest) for the page's
default settings and for capped with games unadjusted. It asserts that no state is truncated and that the busiest
state uses less than half the budget. I ran every state once: nodes per request, **main search plus all first-pick
searches**, with the default rule:

| Settings | Median nodes | Max nodes | Median time | Max time |
|---|---|---|---|---|
| uncapped, games adjusted (page default) | 141 | 12,114 | 30 ms | 45 ms |
| capped, games not adjusted | 1,681 | 59,586 | 38 ms | 101 ms |

Capped is the busier case, at 59,586 against the 75,000 the test allows. That margin is thinner than I would like
for a state where the page defaults are not used; the test will fail before real results go approximate.

**Result on the case that froze the page** (26 picks made, spread 20 / 1.0, threshold 0.05, FG% and FT% only):
before 5.5 to 7.6 s, now 0.55 s, flagged as cut short. Window with slack 60: 0.75 s before, 0.25 s now.

## Other changes in A2

- **Busy state.** After 200 ms without a reply, the hero, plan and alternatives dim. `main.busy` in the CSS,
  `setBusy` in the JS. A superseded request does not clear it; the newest owns it.
- **Exactness kept.** `recommend` still returns the exact answer when no budget is given, so the brute-force tests
  are unchanged. `plan_picks` is the new entry point the service uses.
- **New tests (optimizer):** first-pick options equal a brute force of the best plan for each first pick (8 cases);
  options sorted and including the recommended pick; a cut-short search stops within budget, still returns a plan and
  is reproducible; with an unreached budget the result equals the exact one.

## Where I did not do what I proposed

- **I did not tighten the input limits.** My response proposed it. With the budget in place a wide setting now gives a
  flagged, approximate answer in about half a second, so the limits no longer protect anything the budget does not.
  Tightening them has a cost: values already saved in a browser's `localStorage` would fall outside the new range, the
  server would answer 400 to every request, and the page would be stuck behind an error banner until the user cleared
  site data. The presets in C10 (step 7) are the right way to steer users, and I would sanitise saved values then.
  Say if you disagree.
- **A truncated result is reproducible** for a given build, because the budget counts nodes, not time (tested). It can
  still change when the code or the candidate lists change, which is another reason the page calls it approximate.

## Verified, and what I could not verify

- Verified in Chrome: the normal state and the new alternatives line; the wide-open settings (536 ms, note shown, hero
  line shown, all plans start with the same player); the busy class turns on and off.
- **The busy timing is not verified at the 200 ms mark.** The Chrome tab I drive is in the background and throttles
  timers, so the 250 ms debounce took 1.4 s there. The class appeared when the timer fired, which shows the logic,
  not the threshold. Please look at it in a foreground window.
- Your numbers and mine agree on the cause: 499,653 full plans for 179 distinct teams in my run, 500,345 for 278 in
  yours.
- Still unverified, as in your review: real `prefers-color-scheme: light`, windows narrower than 1624 px, Safari,
  Firefox.

## For you to settle before step 3

1. **The tightened-limits deviation** above.
2. **First-pick options under a truncated search all tie** ("same"). I left the display as is, because the note already
   says the numbers are approximate. If you prefer, hide the alternatives line when the search was truncated.
3. **Order in step 3.** I plan: the pick-object schema and migration (v1 to v2) first, then A1 with two kinds of unknown
   pick, then the availability change (last verified pick) that unseen picks need, then X1, then A4 with an atomic
   write and a version counter. Tell me if you want A4 earlier.
