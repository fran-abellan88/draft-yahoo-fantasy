# Dashboard review

Reviewer notes for the agent that built `fantasy_draft/web/` and its server. Reviewed at commit `0be34eb` on
`feat/2026-27-projections`, 2026-10-01.

Updated the same day with the user's answers. Start with "How to use this file", which says what is expected of you
before any code changes. Then read "Decisions from the user": it overrides anything below that
conflicts. Findings it changed are marked **Updated**, and section E is new.

## How to use this file

**Do not change any code yet.** The user wants the findings debated before anything is built. Please:

1. Run the test suite first and report the result. I could not run it (see "How I reviewed").
2. Write `DASHBOARD_REVIEW_RESPONSE.md` in the repository root, answering every finding ID (A1 to A4, B1 to B6, C1 to
   C10, D1 to D8, E1 to E3) with one of: **agree**, **disagree** (with the reason), or **counter** (with a better
   proposal).
3. Verify the findings marked "Read" and "Judgement" yourself before agreeing. I did not see those happen.
4. End the response with a proposed implementation order, then wait for the user's approval.

The reviewer will read your response file and go through the disagreements with the user. I would rather be told I am
wrong than have a finding implemented that should not be. Where I already see a reasonable objection I have written it
down under "Possible objection".

Each finding is marked with how I know it:

- **Measured**: I ran it and have a number or a screenshot.
- **Read**: it follows from the code, I did not see it happen.
- **Judgement**: a design opinion. These are the ones most open to challenge.

## How I reviewed

- Read `web/index.html`, `web/app.js`, `web/style.css`, `server.py`, `service.py`, `optimizer.py`, `scoring.py`,
  `availability.py`, `lineup.py`, `flags.py`, `draft.py`, `run_dashboard.py` and the README.
- Ran a second copy of the server on port 8765 (the one on 8001 was left alone) and drove it in Chrome: first load,
  pick 3 (waiting), pick 27 (on the clock), pick 112 (past the planning horizon), pick 151 (pool empty), sorting,
  search, keyboard logging, double-click, the settings panel.
- Timed both endpoints over a simulated 112-pick draft, profiled one request, and timed 144 settings combinations.
- Computed WCAG contrast for every colour pair in both themes.

Not verified, so treat anything I say about these as unconfirmed:

- **Real light mode.** I forced the light tokens with an injected style sheet. `prefers-color-scheme: light` itself
  was not exercised.
- **Real window resizing.** Chrome ignored the resize in my session, so widths below 1624 px were measured in a
  same-origin iframe of that width. Media queries respond to it, but it is not a real window.
- **Windows wider than 1624 px.** The user will draft on a 32 or 49 inch monitor. What I say about wide windows comes
  from reading the CSS.
- Safari, Firefox, a touch device, and a draft under real time pressure.
- The test suite. `pytest` is not installed in the interpreter I used, so I did not run it.

## Verdict

The engineering is sound and it is fast. The page is calm, readable and consistent in both themes. What it is not yet
is shaped around what the user does during a draft. In a 14-team snake draft, 13 of every 14 picks belong to someone
else, so the dominant action is "find a player and log him, quickly". That action currently starts below the fold. The
second thing: four situations can stall or corrupt a live draft, and none of them shows up in a quiet test session.

What I would keep as it is:

- One Python core for scoring, with the page as a thin view. No scoring logic is duplicated in JavaScript.
- Picks as an ordered list with ownership derived from the snake order. The state cannot contradict the draft.
- Stateless server, `latestRequest` guard against out-of-order replies, debounce on settings.
- Type a name and press Enter to log when exactly one player matches. I tested it: focus stays in the search box and
  the box clears, so the next pick can be typed immediately. This is the best interaction on the page.
- Design tokens, tabular numerals, visible focus ring, reduced-motion rule, no network dependencies.
- All body text passes contrast in both themes (5.0:1 to 16.4:1).

## Decisions from the user

Given after the first version of this review.

| Topic | Decision | What it changes here |
|---|---|---|
| Screen | A big monitor, 32 or 49 inch. No phone. Resolution not known yet: "prepare for anything" | D9 dropped. B2 rewritten for wide windows |
| Arrangement | Dashboard and Yahoo's draft room side by side, or in two browsers, on the same machine | C8 downgraded. A4 matters more |
| Rounds | 8 for now, all 13 later | B6 is a wording fix for now. A1's placeholder stays P0 |
| Settings | Chosen before the draft and kept for all of it. The user is still deciding the configuration | C10 goes ahead, with a lock and a comparison aid |
| Recommendation | Must follow team needs, judged against the other 13 teams | New E1 and E2 |
| Other teams' picks | Hybrid: automatic picks for rehearsal, catch-up and projection. In the real draft the user logs picks | New E3 |

## Priorities

| ID | Finding | Evidence | Effort |
|---|---|---|---|
| **P0** | *Can break a live draft* | | |
| A1 | A pick of a player outside the 150-player pool cannot be logged, and the pool runs out at pick 150 of 182 | First part read, second measured | Medium |
| A2 | Settings the page allows make one request take 1 to 11 s, with no busy state | Measured | Small to medium |
| A3 | The error banner is off-screen when you are at the table, and a failed pick leaves the row dead | First part measured, second read | Small |
| A4 | The saved draft is tied to the port number; the port fallback silently shows an empty draft | Read, partly measured | Small to medium |
| **P1** | *Core workflow* | | |
| B1 | Search and the player table start below the fold; three scroll areas compete | Measured | Medium |
| B2 | **Updated.** The layout breaks at likely window widths: columns cut off from 1281 to 1606 px, roster and category strength under the table at 1280 px and below, nothing uses width beyond 1760 px | Measured, last part read | Medium |
| B3 | `hidden` does not hide the availability fields | Measured | One line |
| B4 | "At your pick" reads 100% for every player exactly when you are on the clock | Measured | Small |
| B5 | The recommendation disagrees with the table's #1 and does not say why; planned players are not marked in the table | Measured | Small |
| B6 | **Updated.** Past pick 111 the hero says "Your planned picks are made" while the clock says "You pick at 114". Wording fix for now | Measured | Small |
| **P2** | *Makes it clearly better* | | |
| C1 | No sort arrow; the sorted column is only a slightly brighter label | Measured | Small |
| C2 | 10 to 11 rows visible; rows are 56 to 70 px tall | Measured | Small |
| C3 | Per-category scores are sent for every player and never shown | Read | Medium |
| C4 | Category strength: the number does not belong to the bar the eye reads first | Measured | Small |
| C5 | "Eligible at: PG 1, SG 0..." instead of which lineup slots are filled | Judgement | Small |
| C6 | "Choice for pick 27 across the best plans: 68%" reads as a probability and is not one | Read | Small |
| C7 | "Odds the whole plan holds: 5%" | Judgement | Trivial |
| C8 | **Updated, downgraded to P3.** "It is your turn" is signalled by a 6 px border changing colour | Judgement | Small |
| C9 | Search is single-substring only; no message when a searched player is already taken | Measured | Small |
| C10 | **Updated.** Settings fill the left rail permanently, a third of it explanatory prose. Add a lock and a comparison aid | Judgement | Medium |
| **P3** | *Polish* | | |
| D1 to D8 | Colour roles, two contrast failures, `color-scheme`, hover, accessibility, unused payload, labels. D9 (phone) is dropped | Mixed | Small each |
| **E** | *Engine changes the user has asked for* | | |
| E1 | The recommendation should follow team needs: weight the categories where one more unit most changes the odds of winning | Agreed with the user | Medium (step 1), large (step 2) |
| E2 | Score all 14 teams from the pick log and show where the user's team stands in each category | Agreed with the user | Medium |
| E3 | Automatic picks for the other teams, as a hybrid: rehearsal, catch-up and projection, not a replacement for logging | Decided by the user; drift measured by simulation | Medium |

Suggested order: A1 to A4 and B3 first, since they are independent of everything else. Then E2, because E1 and the
new category panel both need it. Then the layout (B1, B2) designed with E2's panel in mind, so it is not built twice.

---

## P0: can break a live draft

### A1. Picks outside the pool cannot be logged, and the pool is smaller than the draft

**Measured.** The pool is 150 players. The draft is 14 x 13 = 182 picks (`service.py:199`, `_clock` uses
`teams * ROSTER_SIZE`). I advanced my copy to 150 picks: the clock read "Pick 151 (round 11): slot 11 is choosing. You
pick at 167, after 16 more picks", the table read "No available player matches. Clear the search or choose another
position", and nothing further could be logged. Two of the user's own picks (167 and 170) are behind that wall.

**Read.** Well before that, any manager who takes a player outside Yahoo's top 150 creates a pick that cannot be
entered. `draft()` only accepts an id in `playerById`, and `_parse_picks` rejects unknown ids (`service.py:194`). The
only way to keep the pick counter right is to log some other player in his place, which removes a real player from the
pool and from the plan.

**Why it matters.** The whole design rests on "picks are logged in order, so the state cannot disagree with the
draft". One unloggable pick breaks that, and every later "you pick in N" and every availability number is then off by
one.

**Proposal.** A "Player not in the list" action that logs a placeholder pick. It needs a reserved id form (for example
`other:17`) accepted by `_parse_picks` and `_check_state` and ignored by scoring. Show it in the log as "Pick 17: not
in the list". Give the empty-pool state its own message.

**Possible objection.** "The memory file says keep XRank 1 to 150, the user decided that." Agreed, and I am not asking
for a bigger pool. The placeholder is what makes a 150-player pool safe.

**Updated.** The user plans 8 rounds for now (112 picks), so the empty pool at pick 150 is not reached yet. The
placeholder is still P0: a manager can take a player outside the top 150 in any round. For the later move to 13
rounds, note the two prerequisites now: the pool must exceed 182 players, and the exact search will not stretch from 7
planned picks to 12 (see A2), so the late rounds need a budget or a greedy fill.

### A2. Allowed settings make a request take seconds, with nothing on screen

**Measured.** With defaults the server is fast (see Performance). But the inputs in "Who will still be there?" accept
values (`index.html:42-47`, mirrored in `service.py:41-46`) that blow the search up:

| Rule | Categories | Method | Picks made | Time |
|---|---|---|---|---|
| probability, spread 20 / 1.0, threshold 0.05 | FG% + FT% | uncapped | 26 | **11.4 s** |
| same | 8 (no TO) | capped | 26 | 8.0 s |
| same | all 9 | uncapped | 26 | 2.8 s |
| window, slack 60 | FG% + FT% | uncapped | 26 | 2.6 s |
| window, slack 60 | all 9 | uncapped | 26 | 2.2 s |
| window, slack 10 or less; probability at defaults | any | any | any | 0.1 s or less |

Median over 144 combinations was 51 ms, so this is a cliff, not a slope. To reproduce: `DraftService.analyze` with
`{"type": "probability", "baseSd": 20, "sdPerAdp": 1.0, "threshold": 0.05}`, categories `["fg_pct", "ft_pct"]`,
`method: "uncapped"`, and the first 26 players by ADP as picks.

**Read (my explanation, not proven).** When the rule lets almost everyone through, every pick gets nearly the same 25
candidates. `suffix_best` (`optimizer.py:150-152`) adds up each pick's best candidate without requiring them to be
different players, so the bound is loose, and plans are de-duplicated as sets (`optimizer.py:154`), so the same seven
players are reached in many orders. Please check this before acting on it.

**Why it matters.** There is no busy state, so the page simply stops responding. The work cannot be cancelled either:
a second click queues behind the first on the same CPU.

**Proposal, in order of value.**

1. Give `_search` a budget (nodes or wall-clock, about 300 ms) and return the best plans found so far with a flag.
2. Show a busy state on the hero and plan when a reply takes longer than about 200 ms.
3. Replace the three raw numbers with presets (see C10), which also removes most ways to reach the cliff.

**Possible objection.** "Nobody will type spread 20." Slack 60 is one field and a plausible thing to try ("show me
everyone"). And a budget costs little and protects against pool or roster changes that move the cliff later.

### A3. Failures are invisible where the user works

**Measured.** `.banner` is `position: static` at the top of the page (`style.css:71`). With the page scrolled to the
table (scrollY 742) I called `showError`: the banner's box was at -741 to -700 px, entirely off-screen.

**Read.** On a failed request `draft()` has already pushed the pick and saved it (`app.js:161-164`), but the table is
not re-rendered. The row is still there, and clicking it again returns early at the `state.picks.includes(id)` guard
(`app.js:160`). From the user's side: I clicked, nothing happened, I click again, nothing happens.

**Proposal.** Make the banner fixed or sticky with a Retry button that calls `refresh()`. Retry automatically once or
twice. When it appears at the top it also shifts the whole layout down, which a fixed position avoids.

### A4. The saved draft depends on the port

**Read.** Picks live only in `localStorage`, which is per origin, and the origin includes the port.
`run_dashboard.py:23-30` falls back to the next free port when 8001 is busy. So: the server dies mid-draft, the old
process still holds 8001, the restart lands on 8002, and the page opens with an empty draft. The picks are not lost,
they are under the other origin, but nothing tells the user that.

**Partly measured.** My copy on 8765 opened with two picks left by an earlier session on that port, not with whatever
8001 holds. So state does follow the port.

**Proposal.** Pick one:

- Smallest: when the port fallback happens, print it loudly, and add Export picks / Import picks (a text box with the
  ordered ids is enough).
- Sturdier: have the server append the pick list to a file on each analyze and offer it back when the page loads with
  no saved state. The server stays stateless for computation.

**Possible objection.** "Stateless was deliberate." It was a good call for computation. This is about a backup for
state that takes an hour to rebuild.

**Updated.** The user may run the dashboard and Yahoo in two different browsers. `localStorage` is also per browser,
so opening the dashboard in the other one shows an empty draft. That is a second way to hit this, and an argument for
the server-side file over export and import.

---

## P1: core workflow

### B1. The main action starts below the fold

**Measured**, 1564 x 939 viewport, first load:

| Element | Top (px) | Height (px) |
|---|---|---|
| Hero | 20 | 171 |
| Plan | 250 | 504 |
| Alternatives line | 764 | 38 |
| Search and position chips | 861 | 40 |
| Table | 910 | 657, with its own scroll |

The first table row is at 949 px in a 939 px viewport. To log any pick by mouse you scroll the page, then scroll
inside the table (`max-height: 70vh`, `style.css:160`). Each rail is a third scroll area (`style.css:83`), and the
right rail starts scrolling as soon as the log grows.

**Judgement.** Hero plus plan take the best 750 px to answer "what should I take?", a question that is live for 8
picks out of 112. Between pick 3 and pick 27 the hero shows a guess with a "59% chance he is still there" while the
user's actual job, 24 times in a row, is logging.

**Proposal.** An app-shell layout: the page itself does not scroll.

- A slim top bar: pick and round, who is choosing, picks until yours, the snake strip, Undo, and the search box.
  Add `/` to focus the search.
- The table takes the full remaining height in the main column and is the only thing that scrolls there.
- Recommendation and plan move to the right column in compact form (one line per pick: pick, name, odds), above
  roster and category strength.
- Settings go behind a button (see C10).

**Possible objection.** "The recommendation is the product; it should be the biggest thing." It should be the biggest
thing *when it is your pick*. A compact always-visible plan in the right column, which grows into a prominent state on
your turn, serves both moments. If you prefer to keep the hero, then at least move search and table above the plan.

**Updated.** Design this together with B2 and E2. On the user's monitor there is room for more than three columns,
and E2 adds a panel that does not exist yet.

### B2. Columns are cut off at common laptop widths

**Measured.** The table needs 895 px. Hidden width at each viewport:

| Viewport width | Layout | Table hidden (px) | Right rail starts at (px) |
|---|---|---|---|
| 1624 | 3 columns | 0 | 20 |
| 1512 | 3 columns | 95 | 20 |
| 1440 | 3 columns | 167 | 20 |
| 1366 | 3 columns | 241 | 20 |
| 1281 | 3 columns | 326 | 20 |
| 1280 | 2 columns | 0 | 1536 |
| 1024 | 2 columns | 233 | 1555 |
| 801 | 2 columns | 456 | 1794 |
| 390 | 1 column | 531 | 3093 |

From the grid arithmetic (not measured at the edges), everything fits only at about 1607 px and wider, or in the
narrow band of about 1257 to 1280. At 1440 the hidden columns are
FT%, FG%, TO, BLK and part of ST, and scrolling sideways to see them moves the player name out of view because the
name column is not sticky. At 1280 and below the right rail goes under the table, so roster and category strength are
1500 px down.

**Proposal.** Solving B1 gives the table more width. Beyond that: make the first two columns sticky on horizontal
scroll, shorten "At your pick" (86 px for a 4-character value), and move the 3-column breakpoint to where the table
fits rather than a round number.

**Updated.** The user will draft on a 32 or 49 inch monitor with Yahoo's draft room beside the dashboard. The window
width then depends on the monitor's resolution and scaling, which are not known. My assumption about likely
half-screen widths, to be replaced by the real number: about 960 px (1920-wide desktop), 1280 (2560), 1720 (3440),
1920 (3840) and 2560 (5120). Against those:

- **1280 is exactly the breakpoint** (`style.css:195`). Measured at 1280: two columns, right rail at 1536 px, under
  the table. Measured at 1281: three columns with 326 px of the table hidden. Half of a 2560-wide desktop sits on that
  edge, and a scrollbar or window border decides which of the two the user gets.
- **960** lies between my measurements at 801 and 1024: 233 to 456 px of the table hidden and the right rail under
  the table.
- **Above 1760 the layout stops growing** (`max-width: 1760px`, `style.css:78`). Read, not measured: a 2560 px window
  leaves about 800 px empty while the plan, roster and the new 14-team comparison (E2) compete for space.

Target: one fluid layout that holds from about 960 to 2560 px, with no band where columns are cut or a panel drops
out of sight, and that spends extra width on more panels rather than margins. A 4-column arrangement above roughly
1900 px (table, plan, my team, the 14 teams) is the obvious use of a 49 inch screen.

### B3. `hidden` does not hide the availability fields

**Measured.** With "Odds from ADP" selected, `#rule-window` has `hidden = true` and a computed `display: grid`.
`.fields { display: grid }` (`style.css:119`) outranks the browser's `[hidden]` rule. All four inputs are always
visible, so the field for the rule you did not choose looks like it applies.

**Fix.** `[hidden] { display: none !important; }` near the top of `style.css`.

### B4. "At your pick" tells you nothing when you are on the clock

**Measured.** At pick 27 (mine), all 124 rows read 100%. `availability.py:51` returns ones for the pick being made,
which is correct, and the page prints it. At pick 3, 85 of 148 rows read 100% and 10 read 0%.

**Why it matters.** On the clock, the real question is "if I pass on him now, is he there at my next pick?" That is
the take-now-or-wait decision, and the model already computes it for the plan rows.

**Proposal.** When it is my pick, compute the column for my *following* pick and rename the header to match ("At pick
30"). In the header always name the pick ("At pick 27") instead of "At your pick". Draw the value as a small bar so
the column can be scanned; plain 0% and 100% repeated down a column is hard to read.

### B5. The recommendation disagrees with the table and does not explain itself

**Measured.** At pick 27 the hero says "Take Chet Holmgren" (score 46.1). The table directly below ranks Dyson Daniels
#1 (47.1). The plan is doing something sensible: it expects Daniels to last until pick 58 (67%) and Holmgren not to.
But the page never says so, and a user who sees the tool pass over its own top-ranked player will stop trusting it.

Also measured: neither Holmgren nor any other planned player is marked in the table.

**Proposal.**

- One line in the hero when the recommendation is not the top score: "Daniels scores higher (47.1) but should still be
  there at pick 58 (67%)."
- Mark rows: the recommended player, and players in the plan with their pick number ("plan: 58").
- Reword the heading "Today's plan says" (`app.js:262`); "today" has no meaning here. "Current plan:" is enough.

### B6. Past the planning horizon the page contradicts itself

**Measured.** At pick 112: the hero says "Your planned picks are made", the clock beside it says "You pick at 114,
after 2 more picks", the plan says "No plan to show", and "At your pick" is "-" for every row. The hero then names the
best available by raw score (Ty Jerome, PG/SG) for a roster that, in my test draft, already had 6 PG-eligible players.
It ignores lineup legality, which the plan was enforcing up to this point.

**Read.** `rounds = 8` in `DraftService` while the roster is 13. This was a stated starting point ("start with 8
rounds, extend later"), so I am flagging the presentation, not the scope.

**Proposal.** At minimum, honest copy: "Rounds 9 to 13 are not planned. Best available who fits your lineup: ...".
Better: extend the horizon. If the search cost worries you, a greedy pick for the late rounds is fine.

**Updated.** The user confirmed 8 rounds for now and all 13 later. Do the wording fix now and make "best available"
respect the lineup rules. Leave the horizon alone until the prerequisites in A1 are met.

---

## P2: makes it clearly better

### C1. No sort indicator

**Measured.** After sorting by ADP the only change is the label colour, from `rgb(154,167,184)` to
`rgb(231,236,243)`, same weight, no arrow. Direction is not shown at all. `aria-sort` is set on the `<button>`
(`app.js:446`); it belongs on the `<th>`.

**Fix.** An arrow on the active header and `aria-sort` on the `th`.

### C2. Row density

**Measured.** Rows are 56 px, 70 px with a badge. The table shows 10 to 11 rows. A draft board is for scanning 25 to
30 names.

**Proposal.** One line per player: name, then team and positions in muted text on the same line, badges inline or in
their own narrow column. About 32 px per row doubles what is visible. Fix the column widths so the table does not
reflow when rows change.

### C3. The most useful data on the wire is not shown

**Read.** `categoryScores` (0 to 100 for each of 9 categories, for every player) is built in `service.py:245` and
never read in `app.js`. In a 9-category league the shape of a player matters as much as his total: 47.1 from steals
and assists is a different pick from 47.1 from points and threes.

**Proposal.** Tint each stat cell by its category score. One hue, low opacity, strongest for the best values, with
turnovers already reversed by the server. Keep the number as the content and check the text contrast on the strongest
tint. Dim the columns of unticked categories so the table reflects the settings.

A cheap extra with the data already on the page: a "value" column, ADP rank minus score rank. Sorting by ADP showed me
Trae Young at ADP 26.6 and score rank 52, and Chet Holmgren at ADP 28.3 and score rank 2. That gap is the insight, and
the user currently has to compute it by eye.

### C4. Category strength: the number does not match the bar you look at

**Measured.** With one player drafted, FG% shows a bright green bar at about 88, a grey bar at 47, and the number 47.
The number is the plan's value whenever a plan exists (`app.js:486`), but the green "Drafted" bar is first and
brighter. The grey bar uses `--taken`, a token that elsewhere means other teams' picks, and it sits at 2.3:1 (light)
and 2.7:1 (dark) against its track.

**Judgement.** With one or two players the "Drafted" bar is just those players' own scores, so it swings wildly and
then regresses toward the middle as the roster fills. It answers no question the user has.

**Proposal.** One bar per category for the projected team (drafted plus plan), with a tick mark for "drafted so far",
and the number labelling the bar. Add a reference mark at the pool average so "am I strong here?" has an anchor.

**Updated.** E2 replaces this panel's scale. Once all 14 teams are scored, the anchor is no longer the pool average
but the other 13 teams: show the user's rank or chance of winning each category. Fix the number and colour problems
above either way.

### C5. Roster: show slots, not eligibility counts

**Judgement.** "Eligible at: PG 6, SG 4, SF 1, PF 1, C 1" makes the user do the lineup arithmetic. `lineup.py` already
solves the matching. Showing the ten starting slots (PG, SG, G, SF, PF, F, C, C, Util, Util) with who fills each and
which are open answers "what do I still need?" directly.

### C6. "Choice for pick 27 across the best plans"

**Read.** The share is the fraction of the top 100 plans (`topK` default, `service.py:122`) that start with that
player. "Chet Holmgren 68%, Kawhi Leonard 10%" reads like odds or confidence. It is neither, and it changes with
`topK`.

**Proposal.** Show what the user wants at that moment: the fallback and its cost. "If Holmgren is gone: Kawhi Leonard
(plan 0.8 lower), Jalen Duren (1.6 lower)." Those numbers are made up to show the format. The real ones are the best
plan total for each first pick, which the returned plans already contain for every first pick that appears in them. Related: "Other strong plans" lists seven names per plan as run-on text, and the plans differ
from the best one by a single player. Show only the difference.

### C7. "Odds the whole plan holds: 5%"

**Judgement.** It is a correct product of seven numbers and it tells the user the plan will almost certainly fail,
next to a sentence saying the plan is recomputed after every pick anyway. It costs trust and informs no decision. I
would remove it and keep the per-pick odds. Related: the amber threshold is hard-coded at 0.6 (`app.js:277`) while the
planning threshold is a user setting with default 0.5, so at defaults a pick can be both "good enough to plan on" and
"warning colour".

**Possible objection.** "It is honest." Per-pick odds are equally honest and each one is actionable.

### C8. "It is your turn" should be unmissable

**Judgement.** The state change is a 6 px left border going from grey to green and the name turning green
(`style.css:124-128`). The user will have Yahoo's draft room in another window. Suggested: tint the whole top bar or
hero, and change `document.title` (for example "YOUR PICK: 27") so the tab itself shows it. Likewise show a countdown
in the title while waiting ("3 picks to go").

**Updated: I overstated this.** The dashboard only knows it is the user's turn because the user logged the picks, and
with Yahoo beside it the user sees the turn there first. A stronger "your pick" state is still a cheap improvement,
but the tab title adds little. Treat as P3.

### C9. Search

**Measured.** Matching is one substring against name or team (`app.js:391-395`). "holmgren chet" and "c holmgren"
return nothing. Searching a player who is already drafted returns the generic "No available player matches".
Pressing Enter with several matches does nothing, silently.

**Proposal.** Split the query on spaces and require every token to match. For a drafted player say "Luka Doncic: taken
at pick 3". On an ambiguous Enter, say "28 matches, keep typing", or let arrow keys move a highlight and Enter log the
highlighted row.

### C10. Settings occupy the left rail permanently

**Judgement.** Categories, scoring method, games toggle and availability are set before the draft and rarely touched
during it. They hold 330 px of width for the whole session, and about a third of the rail is explanatory paragraphs.
Move them behind a Settings button (a panel or `<dialog>`), with a one-line summary always visible ("9 categories,
uncapped, games counted") so the user can see the scoring basis without opening it.

For availability, the labels "Early-round spread" and "Spread added per ADP place" take a statistics background to
read and have no units. Offer three presets (managers follow ADP closely / normally / loosely) with the raw numbers
under an "advanced" disclosure. That also keeps most users away from A2.

**Possible objection.** "The user asked to toggle categories and see rankings recompute." Yes, and that still works
from a panel. If the user does this often mid-draft, keep the category ticks visible and move only the rest.

**Updated.** The user keeps one configuration for the whole draft and is still choosing it. So the panel goes ahead,
with two additions:

- **Lock the settings once the first pick is logged**, with an explicit unlock. A stray click on a category mid-draft
  silently reorders every ranking and the plan.
- **Help with choosing.** Today a toggle reshuffles the table and nothing shows what moved. A "rank change against
  the other setting" column, or a short list of the biggest movers, would. Be clear in the copy that this shows where
  two settings disagree, not which is right. The rehearsal mode in E3 is the better tool for this decision.

---

## P3: polish

- **D1. Green means five things** (judgement): mine (roster, log, snake, hero), good odds (meter), a ticked control,
  the primary button, and the "Drafted" bar. Amber means both "low odds" and "flag badge". Reserve green for "yours"
  and use a neutral or a second hue for odds.
- **D2. Contrast failures** (measured). `.snake .cell.now.me` in dark mode is white on `#3ecf9b`, 1.98:1
  (`style.css:106`); use the dark text that `button.primary` already uses in dark mode. The light-mode "done" snake
  cell is 4.24:1 at 12 px. Input and track borders are 1.2:1 to 1.5:1, which is fine for card edges but is the only
  boundary of the search box.
- **D3. No `color-scheme`** (measured, screenshot). In dark mode the unticked radio is a bright white disc and
  scrollbars are light. Add `color-scheme: light dark` to `:root`.
- **D4. Row hover is nearly invisible** (measured): 1.11:1 dark, 1.14:1 light, on the page's main click target.
  Strengthen it and show a "Log pick" hint on hover and focus. There is also no confirmation of what was just logged
  beyond the log in the right rail; a short "Logged pick 4: Tyrese Maxey. Undo" next to the search would cover
  mis-clicks. Note that a click logs immediately and the next row slides under the cursor, so a slow double-click
  logs two players. I did not reproduce this (a fast double-click logged one, the guard caught the second), so it is
  a risk, not an observed bug.
- **D5. Keyboard and screen reader** (measured): 148 of 193 tab stops are table rows; rows are clickable `<tr>` with
  no role; 358 `title` attributes carry explanations that keyboard and touch users cannot reach; no `<h1>`; the two
  radio groups have no `fieldset`/`legend`. For a one-user tool this is low priority, but arrow-key row navigation
  would help the user too.
- **D6. Unused payload** (read): `categoryScores`, the `lastSeason` stat lines (only `gp` is used), `fga`/`fta`,
  `horizonDone`, and `profile.*.total` are sent and never read. Use them (C3) or drop them.
- **D7. Labels** (measured): the table header says "3PM", the category list and strength panel say "3PTM".
- **D8. Draft log** (judgement): names only. Adding the slot that picked would let the user see runs on a position.
- **D9. Phone: dropped.** The user will not use a phone. For the record, at 390 px the table starts at 2468 px with
  531 px of columns hidden. Do not spend time on it.

---

## Performance

**Measured. Short version: it is fast, and I recommend not optimising anything except A2.**

| What | Result |
|---|---|
| `GET /api/pool` | 23 ms, 67 KB, once per load |
| `POST /api/analyze`, defaults, 113 states of a simulated draft | median 37 ms, p90 64 ms, max 132 ms |
| Analyze payload | 51 KB at pick 1, 18 KB at pick 112 |
| Browser: fetch | about 60 ms |
| Browser: `render()` script time | 5 to 8 ms for 148 rows |
| Browser: click to painted | about 150 ms |
| DOM size | 3,338 nodes |
| Page load | DOMContentLoaded 216 ms, load 289 ms |

Profile of one request: about half is the plan search, the rest is pandas overhead on small frames
(`category_scores` runs 7 times per request, `composite_score` is computed in both `service.analyze` and
`optimizer.recommend`, flags are rebuilt on every request though they depend only on the categories, `_pool_rows`
uses `iterrows`).

Things I considered and recommend **against**, so nobody spends time on them:

- Virtualising the table. 148 rows render in 8 ms.
- Diffing the DOM instead of rebuilding. Same reason.
- Caching scores server-side. It would save about 25 ms of a 150 ms interaction.
- HTTP keep-alive, static file caching, compression. It is `127.0.0.1`; connection time measured 0 to 1 ms.

The one real performance problem is the worst case in A2.

---

## E. Engine changes the user has asked for

These go beyond the page, but they decide what the page has to show, and the user has agreed to the direction. The
pitfalls and the staging are mine. Challenge them like any other finding.

### E1. The recommendation should follow team needs

**Today (read).** The plan maximises the sum of composite scores (`optimizer.py:10-12`). The category strength panel
is display only. The page shows it beside a recommendation that ignores it.

**What the user wants.** As the team takes shape, the next pick should favour the categories that help most, given
positions and who is left in the pool. Example given: if three-pointers are needed and few sources remain, take one
now.

**The rule, agreed with the user.** Not "improve the weakest category". In head-to-head a category is won by beating
the opponent, so one more unit is worth most where the category is close, and little where the team already dominates
or is far behind. Weight each category by how much one more unit changes the chance of winning it against the other
teams (E2 supplies those teams).

**Pitfalls.**

- **Early rounds are noise.** With one or two players, "need" is just those players' profiles (see C4: with one
  player drafted, the FG% bar was near 90 and the REB bar under 20, read off a screenshot). Start the need weighting
  near zero and grow it with roster size.
- **Punting must stay explicit.** An unticked category has weight zero. The automatic weighting must not quietly
  revive it, and should not quietly abandon a ticked one without saying so.
- **Explanation becomes mandatory.** The recommendation will leave the score ranking more often, so B5 moves from
  nice to required. An example of the form, with invented numbers: "3PM is contested (you would win it against 6 of
  13) and 4 strong sources are left after pick 30". Show the weights in use.
- **Keep a switch back to the plain score** so the user can compare, and so the golden tests keep a fixed target.

**Staging I recommend.**

1. **Per-request category weights.** Compute the weights once per request from the current standings, and make the
   composite a weighted mean. The score stays additive across players, so `_search` and its `suffix_best` bound
   (`optimizer.py:150-152`) work unchanged and stay fast. Scarcity then comes out of the existing plan: availability
   and lineup rules over the later picks already decide "take him now or he is gone". Limit: the weights do not change
   inside one plan, only after each real pick, so a plan can over-stack one category on paper. The pick in front of
   the user is recomputed every time, which is the part that matters.
2. **Score whole teams by categories won.** Only if step 1 proves too crude. The objective is no longer a sum over
   players, the current bound is invalid, a new search is needed, and A2 gets worse.

**Tests to ask for.** With equal weights the results equal today's. Weights are zero for unticked categories. A team
far ahead or far behind in a category gets a lower weight there than a team in the middle.

**Possible objection.** "Weights that move after every pick make the ranking jumpy and hard to trust." Fair. The ramp
and the visible weights are the answer. If it still feels unstable, cap how far a weight can move from 1.

### E2. Score all 14 teams

**What the user wants.** Every team's score, not only the user's, so the comparison behind E1 is against the real
league.

**Read.** No new input is needed. Picks are logged in order and the snake order gives the slot of each pick
(`service._clock` already derives it), so all 14 rosters follow from the pick list.

**Proposal.** Per category, total each team and place the user's team among the 14. Two readings are useful: the rank
(3rd of 14 in steals) and the share of the other 13 the user would beat, which is the chance of winning that category
against a random opponent. E1's weights come from how steeply that share would change with one more unit.

**Pitfalls.**

- **Unequal roster sizes mid-round.** In a snake draft some teams have one more player than others. Compare at equal
  sizes, or compare projected final rosters (E3, third use). Say in the panel which it is.
- **Percentages.** Use the per-game impact values that scoring already uses, which add up across a roster. Never
  average FG% or FT% across players.
- **Turnovers** are reversed, as everywhere else.
- **Placeholder picks (A1)** have no stats. Count them at replacement level or leave them out, and say which.
- **Eight rounds.** The comparison is over 8 players per team, not 13. Label it so.

**Page.** This replaces the scale of the category strength panel (C4) and adds a compact 14-team view. On the user's
monitor there is room for it (B2). Cost is negligible: 14 small sums per request.

### E3. Automatic picks for the other teams

**What the user wants.** An option so that the other 13 teams are filled automatically, for example by ADP with
position limits, instead of logging every pick.

**Decided by the user: the hybrid below.** Build it, but not as a replacement for logging during the real draft. It
answers two different questions with very different reliability.

- *What does a typical opponent's team look like?* Automatic picks answer this well. The category totals of an
  ADP-built team are a fair picture of the league whoever really holds which player. So E1 and E2 survive it.
- *Who is still available?* Automatic picks answer this badly, and the recommendation depends on it.

**Measured (simulation, not a real draft).** I compared picks in ADP order with 4,000 drafts drawn from the tool's
own availability model. Those parameters are uncalibrated by the README's own account, so read this as "what the tool
already assumes", not as how real managers behave.

| At the user's pick | Players auto-pick has removed | Of those, really still available | Of the next 5 by ADP, really already gone |
|---|---|---|---|
| 27 | 26 | 3.6 (14%) | 1.8 |
| 55 | 54 | 5.6 (10%) | 1.6 |
| 83 | 82 | 8.5 (10%) | 1.9 |
| 111 | 110 | 12.0 (11%) | 1.8 |

With half the spread (managers following ADP twice as closely) the last column is still 1.4 to 2.0. So at every pick
of the user, about a third of the players the page would offer first are not there, and several who are available
are hidden. Position limits were not modelled. They would change which players go, not the size of the drift.

**Three uses for one component.**

1. **Rehearsal before the draft.** The 13 other teams pick automatically, the user makes only their own picks, and a
   whole draft takes minutes. This is the right tool for the user's open question (which configuration?). Add seeded
   randomness from the availability model as an option, otherwise every rehearsal is the same draft.
2. **Catch-up during the real draft.** If the user falls behind, fill the missed picks automatically, mark them as
   assumed, and let each one be corrected to the real pick. Add "mark as gone" on any row for the moment a
   recommended player turns out to be taken.
3. **Projection.** Fill the picks that have not happened yet, for the other teams, to the end of the horizon, so E2
   compares complete teams. This never touches logged picks.

**Design points.**

- Generate the picks in the Python core, not in the page, in keeping with the single-core rule.
- Respect the lineup rules through `all_masks_can_start`, so no automatic team ends with five centres.
- Picks need an "assumed" flag. That changes the stored state (a new storage key, with a migration from
  `draft-assistant-v1`), the request, and `_parse_picks`.
- Assumed picks must look different in the log, and the page should always show how many are assumed.

**Possible objection.** "Logging 104 picks is the tedious part; that is why the user asked." Logging is a name and
Enter per pick, and it is what keeps availability true. The catch-up use removes the penalty for missing some. The
user has accepted this. Rehearsal mode is technically full automatic mode, so nothing stops it being used in a real
draft; the page must therefore always show which mode it is in and how many picks are assumed.

---

## Open points

1. **Window width.** Once the monitor is set up, the user should report the dashboard window's width (`innerWidth`
   in the browser console). Until then, design for about 960 to 2560 px (B2).
2. **Order for automatic picks.** ADP is the natural default. Whether Yahoo's own autopick follows ADP or its ranking
   I do not know; the project notes say the mock draft's automatic picks tracked ADP closely.
