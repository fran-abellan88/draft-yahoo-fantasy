# Draft assistant for a Yahoo head-to-head 9-category league

A local tool for the fantasy basketball draft: 14 teams, snake order, pick 2, 13-man roster (PG, SG, G, SF, PF, F, C, C,
Util, Util and 3 bench). It scores every player on the categories you choose, plans your remaining picks and recommends
the pick in front of you. You log each pick as it happens and the plan updates.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_dashboard.py
```

The page opens at `http://127.0.0.1:8001/`. The server listens on your computer only and the page loads nothing from
the internet, so it keeps working if the connection drops during the draft.

Your picks are kept in the browser, so reloading the page mid-draft loses nothing. **Reset draft** (top bar, press twice; **New mock draft** in a mock draft) clears them.

## Using the page

- **Click a player** to log the pick that is on the clock. Picks are logged in order and the snake order decides
  which ones are yours, so the state cannot disagree with the draft. **Undo** reverts the last action (its label says which).
- **Pick not in the list** logs a pick of a player who is not among the 150. It counts as a pick, nobody leaves the
  pool, and if it is yours it fills one starting slot at any position, at replacement-level value.
- **I am behind**: type the pick Yahoo is at and the picks you missed become *unseen*. A player the table lists may have
  been taken at one of them, so every availability number allows for that. Press **Gone** on a player you know was taken
  and one unseen pick is resolved to him (the one closest to his ADP), which raises the odds of the players near it. Your
  own picks are never unseen: the page stops before one and asks you to log it first. On your turn with unseen picks the
  page shows the chance the recommended player is still on the board, lists up to three better-scoring players the odds
  left out ("look first at"), and has a **He is gone** button beside Draft. Under the window rule the odds are only 0 or 1, so it just says picks were missed and leaves the list out.
- **Undo** reverts the last action, including Gone (the pick becomes unseen again) and a whole "I am behind". A gone
  entry in the log has **Unmark**. Every log row has **Edit**: swap two picks, say "I do not know what this pick was"
  (it becomes unseen, a player logged there returns to the pool), or place a gone player at an unseen pick. Each edit
  is confirmed first, cannot put an unseen or gone pick on one of your own pick numbers, and cannot be undone with Undo.
- **Last season next to the projection**: the Score cell reads `40.7 (31.2) ↑`: the projected score, then the same score
  computed from 2025-26 per-game stats (same categories, method, need weights and games setting; games count with last
  season's games played), then an arrow: ↑ projected better, ↓ worse, ≈ within 5 points. A player with under 20 games
  last season keeps the number but gets no arrow; one with no stats shows nothing.
- **Midnight look**: black page, `#1c1c1e` cards with radius 20 and no borders, system font, capsules only on strong stats
  (80+ strong, 60 to 79 lighter, under 25 muted), 34 px rows, a hero with one bar per ticked category, odds as rings in the
  plan, three tiles in Standing, a segmented Real/Mock switch, a snake of circles and slot chips in the roster. The spec is
  `DASHBOARD_MIDNIGHT_SPEC.md`.
- **Notes behind a "?"**: the explanatory notes in Settings, Standing, the 14 teams and the table open from a "?" button
  (click it, click again or elsewhere or press Esc to close).
- **Score column**: a bar from the lowest score left (a short sliver) to the best (full), so every player has a bar and two
  different scores always give two different bars. Early in a draft, when the best scores are far above the rest, most bars
  are short but still differ. Settings offers two colour maps instead (by rank: top 5, 15, 30, 60; by
  range: 5th to 95th percentile of the scores left, which saturates the top players and shifts as the pool drains). The
  choice is a display preference of this browser. **Odds** are plain numbers; only a player who will probably not last (under
  half) is marked in amber. On the clock, **Or take instead** sits in the recommendation box under the name.
- **Scoring categories**: untick one to leave it out of every score and plan. The score is the average of the ticked
  categories, so ticking fewer does not lower anyone's score. Once a pick is logged, a change to any setting waits in
  the panel with **Apply** and **Keep current**, so a stray click cannot change the recommendation; several clicks
  become one confirmation, and closing the panel keeps what was in use.
- **Reward big numbers / Cap at the top 5%**: the uncapped score (default) lets a 32-point scorer outrank a 26-point one.
  The capped score is the `nba-yahoo-fantasy-daily-dose` formula, where everyone past the 95th percentile in a category
  scores the same. A z-score method also exists in `fantasy_draft/scoring.py`; it ranks almost the same as uncapped.
- **Count games missed** (on by default): the distance above a replacement-level player is scaled by projected games
  played out of 82, so a player projected for 59 games counts as 72%. It changes the ranking and the plan, not the
  category bars. Every column of the table sorts, including XRank and projected GP.
- **Who will still be there?** has two ways to judge availability. *Odds from ADP* treats a player's draft position as
  a bell curve around his ADP that widens for later picks. *ADP window* is a plain cut-off. Both are starting guesses
  that should be tuned on a draft with real managers. If the settings let almost everyone through, checking every plan
  would take too long, so the search stops at a fixed amount of work and the page says so: the plan is then the best one
  found, not proven the best. With the default settings the search always finishes.
- **Worth knowing** badges under a name: the injury tag, no or few games last season, a projection that differs a lot
  from last season, or a projection of few games played. They never change the score; they tell you when to look twice.

### The screen

The page never scrolls: it is exactly the window, and a panel that needs more room scrolls inside itself. It is built
for a window of about 2500 x 1476 placed on the right half of a wide screen, with Yahoo's draft room on the left, so
the recommendation column is on the dashboard's left edge, next to the seam. From left to right: recommendation, plan
and category strength; the table (search, position chips, the last logged pick with Undo, then the players); your
roster and the log; the 14 teams (Projected above So far). Settings (categories, score, who will still
be there) open from the button in the top bar, which also shows the choices in one line. Next to it are the **Theme** button
(Auto follows the system, Light and Dark are remembered in this browser) and **Reset draft**.

Narrower windows keep the same panels and fold them into a tab strip, in this order as the window shrinks: 14 teams
and log at 2349 px, then your roster and category strength at 1719 px, then the plan and the table at 1239 px. The
recommendation never goes into a tab.

### The league, the other teams and the mock draft

The 14 teams are named from Yahoo's draft order (slot 2 is Fran'stastic Team, the user's), in the clock, the log, the
last-pick line and the snake strip (hover a slot).

- **Standing** shows, for each category, how your team ranks and the share of the other 13 teams it beats: "so far",
  and projected to 8 players each. Winning, close and behind are listed on top.
- **14 teams** shows every team's totals per game (FG% and FT% as real ratios, turnovers reversed), tinted by rank. The
  **Score** column is the expected number of categories the team wins against a random opponent (the share of the other
  teams it beats in each ticked category, added up: 5.8/9), and the table is always sorted by it, best first, after every
  pick. A team with no player yet is listed last and left out of the ranks. *So far* counts the first n picks of every
  team, n being the round in progress, and scales up a team that has not made its n-th pick yet. Projected and So far are both shown, one above the other, and both
  follow every pick. Projected has two ways to complete the other teams (the switch above it):
  *Same planner* (the default) takes the logged picks and then, in snake order, lets every team, yours too, take the first
  player of its own best plan, the search the recommendation uses. A poor pick by one manager lowers his projected stats and
  leaves more for the rest, and nobody is first by construction. It shows what well-informed teams would end up with, not
  who will be available, and a real league is probably easier. It takes about half a second from an empty draft, is
  asked for apart from the analysis so the recommendation never waits, and shows the ADP projection until it arrives.
  *ADP order* fills the other teams in ADP order with lineup limits; your team is built to these categories and theirs are
  not, so it tends to come first (88% of simulated drafts against ADP rivals, about 30% against rivals that use the
  planner: `python tools/rival_strength.py` reproduces it). The need weights are not used in either projection.
- **What the others should pick** (real draft only). Under the clock line, the team on the clock gets two suggestions:
  "should pick X by the planner, Y by ADP", the first player of that team's own best plan for your ticked categories and the
  best-ADP player who keeps its lineup startable. Every logged pick of the others is then marked **planner**, **ADP**,
  **planner and ADP** or **differs** (hover for both choices, how many picks before or after his ADP he went and his rank by
  score among those left), the Draft log says how often that happened, and **By manager** breaks it down per team with the
  average reach (how many picks before his ADP the players a manager takes go). Each pick is compared with the picks before
  it, so editing the log keeps it consistent; unseen, gone, outside and your own picks are not compared. A pick that
  differs is not a mistake: that manager may draft for other categories or by Yahoo's ranking. The mock draft does not show
  this, since its other teams pick by ADP. It is asked for apart from the analysis, about half a second for a full log.
- **Mock draft** is a second draft in the same program, at `http://127.0.0.1:8001/mock`. The top bar's **Real draft | Mock
  draft** switch moves between them; the mock one has an orange rule under the top bar and its own saved file
  (`saved_mock_draft.json`). In it the other 13 teams pick automatically: best ADP left that keeps their lineup startable,
  blurred a little by the same spread as the availability model and seeded, so a mock can be repeated and the next one
  differs. You click your own picks. Undo goes back to just before your last pick and its label says how many picks that
  removes. Reset starts a new seed. It is a separate route and file, not a switch inside the real draft: the real draft
  refuses automatic picks, and nothing under `/mock` can read or write the real file.
- In the real draft you log every pick yourself, the ones the other teams make included: click the player Yahoo shows
  as taken (**Pick not in the list**, **I am behind** and **Edit** cover the rest).
- **Favour the categories I can still win** (Settings, off by default) weights each ticked category by how close you
  are to the other teams in it: more where you are close, less where you dominate or cannot catch up. It starts after
  the first complete round, reaches full effect after four, keeps every weight within 40% of 1, and never
  brings back an unticked category. The weights in use are listed under Standing.
- **Position flexibility.** The planner ranks plans by their score plus 0.3 points for each position a new pick can
  fill beyond the first (`FLEXIBILITY_BONUS` in `optimizer.py`), so a PG/SG beats a PG of the same score. The 0.3 is a
  judgement, not a calibrated number: it can decide between close players (neighbouring scores differ by 0.1 at the
  median), and over a whole plan it costs under 0.3 roster points (measured on simulated drafts; on the real pool the
  first pick is unchanged and one late pick differs). The "Roster score" shown is the plain sum of the scores, and the
  gaps under "Or take instead" are in roster score too, so an alternative can be level with or ahead of the best plan and
  still rank lower; the page then says "Ranked lower for positions, not score" and names the extra position. Whether a
  team can start everyone at once is a separate check and is unchanged.
- The table marks the recommended player with a star and the players in the plan with their pick ("plan: 58"), tints
  each stat by how good it is in its category and the odds by how likely he is to last, dims unticked categories, and
  when it is your turn the odds column is for your next pick ("At pick 30"). The recommendation says why when another
  player scores higher. Your roster is shown as the ten starting slots and the bench.

### Where the draft is saved

The startup lines say how many picks each file holds ("Continuing the real draft: 3 picks") and the page says so when it
loads, so a leftover draft is never a surprise.

Every change is saved to `saved_draft.json` in the project folder (the mock draft to `saved_mock_draft.json`; neither is tracked by git), and also in the browser as a
backup. The file survives a closed tab, cleared browser data and a different port, so the draft is still there if the
dashboard starts on 8002 instead of 8001. Two things to know:

- To try things out without touching the real draft, start a second instance with its own file:
  `python run_dashboard.py --port 8002 --draft-file /tmp/trial.json --mock-file /tmp/trial-mock.json`. The startup lines print the files in use. The two files must differ. Instances
  that share a file share one draft.
- A save that would empty a draft with picks (Reset, for one) first copies the old file to `saved_draft.previous-v<N>.json` (one per version, never replaced by a later one).
- If the server could not be reached for a while, the browser copy can be newer than the file; the page notices (it
  records which file version the copy is based on and whether the server confirmed it) and uses the newer one. When the
  file wins over a copy the server never confirmed, the page says so and keeps that copy under the browser key
  `draft-assistant-unconfirmed`. If the saved draft cannot be read at load, the page stops with a message rather than
  start from nothing.
- If you open the dashboard in two windows, the one that saves second is refused ("changed in another window"); reload it.
- If the saved draft cannot be loaded (an unknown player, an unseen pick on one of yours), the page says so and keeps
  the file as it is; nothing is saved until you press **Reset**. A file that is not valid at all is renamed to
  `saved_draft.unreadable.json` on the next save.

## How a score is built

For each category, a player's per-game projection is placed between the 5th and 95th percentile of the 150-player pool
(0 to 1, clamped; turnovers are reversed so fewer is better). The score is the mean of the selected categories times 100.
This is the composite from `nba-yahoo-fantasy-daily-dose`, checked against that project's golden test cases.

FG% and FT% cannot be averaged across players, so they are scored as *impact*: makes above what a baseline shooter would
have made on the same attempts, per game. That adds up across a roster, which is what a matchup compares.

The plan is the best set of players for your remaining picks, one per pick, where each is likely to still be there, nobody
repeats and everyone can start at once. The search is exact, and is tested against brute force.

## Data

| File | Source | Used for |
|---|---|---|
| `data/2026-27/projections.csv` | draft-room screenshots, read by hand | XRank, Rank, ADP (only the draft room has them) |
| `data/2026-27/yahoo_projections.csv` | Yahoo player list | projected season totals with attempts |
| `data/2025-26/yahoo_totals.csv` | Yahoo player list | last season's totals with attempts and minutes |
| `data/2025-26/averages.csv`, `yahoo_averages.csv` | screenshots, Yahoo | cross-check only |

Refresh the Yahoo data (pages are cached in `data/cache/`, which is not committed):

```bash
pip install -r requirements-dev.txt
python fetch_yahoo_players.py --refresh
python verify_snapshots.py        # every snapshot number against Yahoo's page
```

The screenshots are transcribed into `data/*/…_raw.csv` and merged and checked by `python ingest_snapshots.py projections`
(or `averages`). Rows that two screenshots show must agree, and gaps or implausible values are reported.

## Tests

`pytest` and `flake8` are in `requirements-dev.txt`, which also holds `beautifulsoup4` for the Yahoo parser tests. Without
it those two test files do not run. The tests of the page's own JavaScript (`fantasy_draft/web/logic.js`) run under Node
and are skipped when Node is not installed; `pytest` then lists them as skipped with the reason, so check that line
before trusting a green run. From the virtual environment of the first step:

```bash
pip install -r requirements-dev.txt
python -m pytest
python -m flake8
```

## Layout

```
fantasy_draft/   scoring, flags, lineup rules, availability, optimizer, data loading, Yahoo parser, server
  web/           the page (plain HTML, CSS and JavaScript)
tests/           pytest suite, with a golden fixture copied from nba-yahoo-fantasy-daily-dose
legacy/2025/     last year's scripts and notebook, kept for reference only
```
