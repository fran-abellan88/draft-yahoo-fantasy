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

**While changing the app**, start it with `python run_dashboard.py --dev`. The page reloads itself when a file under
`fantasy_draft/web/` changes, and the server restarts itself (same port, same process) when a Python file changes; a
Python file with a syntax error is reported in the console and the server keeps running until it is fixed. Only the source
files are watched, never the saved drafts, and the data files are read once at startup, so restart by hand after changing
them. Leave `--dev` off during a real draft: a normal run watches nothing and the page carries no extra script.

Your picks are kept in the browser, so reloading the page mid-draft loses nothing. **Reset draft** (top bar, press twice; **New mock draft** in a mock draft) clears them.

## Using the page

- **Click a player** to log the pick that is on the clock. Picks are logged in order and the snake order decides
  which ones are yours, so the state cannot disagree with the draft. **Undo** reverts the last action (its label says which).
- **Pick not in the list** logs a pick of a player who is not among the 245. It counts as a pick, nobody leaves the
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
  played out of 70 (a few missed games are the same as none, so 70 or more counts in full), so a player projected for 59 games counts as 84%. It changes the ranking and the plan, not the
  category bars. Every column of the table sorts, including XRank and projected GP.
- **Who will still be there?** first asks which ranking the other teams follow: Yahoo's own rank (**XRank**, the default) or
  **ADP**. In the two Yahoo mock drafts in `data/mock_drafts/` the other drafters took players almost in XRank order (a
  correlation of 0.98 to 0.99 with the pick, against 0.92 to 0.93 for ADP, and a miss of about 6 picks against 16), while ADP
  ran well behind the picks late in the draft. Centred on XRank, a spread of 2.1 plus 0.07 per place matched how often a
  player was taken at each pick; centred on ADP the model expected players to go too early. Those were Yahoo mock lobbies,
  not your league: pick ADP if your league drafts by it, and rerun `python tools/calibrate_availability.py` after each new
  mock draft you add. Then there are two ways to judge availability. *Odds* treats a player's draft position as
  a bell curve around his rank that widens for later picks. *Window* is a plain cut-off. Both are starting guesses
  that should be tuned on a draft with real managers. If the settings let almost everyone through, checking every plan
  would take too long, so the search stops at a fixed amount of work and the page says so: the plan is then the best one
  found, not proven the best. With the default settings the search always finishes.
- **Worth knowing** badges under a name: the injury tag, no or few games last season, a projection that differs a lot
  from last season, or a projection of few games played. They never change the score; they tell you when to look twice.

### The screen

The page never scrolls: it is exactly the window, and a panel that needs more room scrolls inside itself. It is built
for a window of about 2500 x 1476 placed on the right half of a wide screen, with Yahoo's draft room on the left, so
the recommendation column is on the dashboard's left edge, next to the seam. From left to right: recommendation and the
plan (all 13 rows); the table (search, position chips, the last logged pick with Undo, then the players); the rail that
reads as "my team" (your roster, Standing with your category strength, then the log, newest first); the 14 teams
(Projected above So far). Settings (categories, score, who will still
be there) open from the button in the top bar, which also shows the choices in one line. Next to it are the **Theme** button
(Auto follows the system, Light and Dark are remembered in this browser) and **Reset draft**.

Narrower windows keep the same panels and fold them into a tab strip, in this order as the window shrinks: your
roster, Standing, 14 teams and log at 2349 px (they share one tab panel beside the table and the plan fills the first
column), then the plan moves into the right column at 1719 px, then the table and the plan at 1239 px. The
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
  player of its own best plan, the search the recommendation uses, for all nine categories (only your own team follows your ticked ones, so punting a category never changes what the others are assumed to pick). A poor pick by one manager lowers his projected stats and
  leaves more for the rest, and nobody is first by construction. It shows what well-informed teams would end up with, not
  who will be available, and a real league is probably easier. It takes about a second from an empty draft (every team plans 8 rounds ahead and then fills in by score), is
  asked for apart from the analysis so the recommendation never waits, and shows the ADP projection until it arrives.
  *ADP order* fills the other teams in ADP order with lineup limits; your team is built to these categories and theirs are
  not, so it tends to come first (88% of simulated drafts against ADP rivals, about 30% against rivals that use the
  planner: `python tools/rival_strength.py` reproduces it). The need weights are not used in either projection.
- **What the others should pick** (real draft only). Under the clock line, the team on the clock gets two suggestions:
  "should pick X by the planner, Y by ADP", the first player of that team's own best plan for all nine categories and the
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
- **One category order.** Every table and bar lists the categories in the same order: FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO (the main table, the league tables, the Standing bars and the recommendation's stat bars).
- **Draft button and player card.** In the main table each row has a **Draft** button left of the name; only that button logs
  the pick (it says **Choose** while you are picking the player for an earlier pick). A click on the name, or Enter on a
  row, opens the **player card** in the recommendation box: the same stat bars, the score with last season's, the odds,
  and Draft / Back to the recommendation. The card closes on Back, Esc, the same name again, when that player is drafted
  and when it becomes your turn, so the recommendation is never hidden when you pick. Enter in the search box still logs
  the pick when exactly one player matches.
- **Other teams' rosters.** Click a team name in either 14-team table, or use the select in the roster panel, to see that
  team's players in the roster panel: the ten starting slots and the bench with each pick number, then which positions
  one more player could still start at (what the teams picking before you will look for). **So far** shows the logged
  picks; **Projected** adds the players the projection gives the team, drawn with a dashed tile and marked "Projected",
  following the table's Same planner / ADP order switch (both go to the full 13 players). An unseen pick is listed as
  "Not known", a pick not in the list fills a slot at any position, and a gone pick shows "(assumed)". The panel stays on
  the team you chose while other picks come in, and goes back to yours when you log your own pick or press **Back to your
  roster**. In a narrow window the click switches to the My team tab. The server sends every team's roster and lineup
  with the league tables (`rosters`), built by the same matching as your own lineup.
- **Position colours.** As on Yahoo's draft board there are three: guards (PG, SG) blue, forwards (SF, PF) green and
  centers orange. A player's name takes the colour of his first listed position (a PF/C is green), and each position letter
  beside a name takes the colour of its own group, with a muted slash between them. It applies to the names in the table,
  the recommendation box and player card, the alternatives, the plan, the rosters and the log, and the position filter
  chips are the legend. The colours are the `--pos-guard`, `--pos-forward` and `--pos-center` tokens, tested for contrast
  on every surface in both themes. Green is also the colour of "yours" and orange of warnings, so the recommended row is
  marked by its tint and the Pick tag, not by a green name.
- **Model against Yahoo.** The score weighs all nine categories equally, as a head-to-head week does, and that disagrees
  with Yahoo's XRank (rank correlation about 0.72 over the top 100; fitting category weights to XRank explains far more,
  with points counted about twice and turnovers not at all, which is taste, not information). The page does not copy the
  market, it shows the disagreement:
  - the **vs Yahoo** column (beside XRank, sortable) is the places the model ranks a player above (+) or below (−)
    his XRank among the players left; gaps of 15 or more are coloured, so sleepers and fades are one click away;
  - **Yahoo disagrees** appears under the recommendation when an available player ranks at least 15 places better by XRank
    and scores lower: it names the category that costs him most (Giannis against Kawhi: FT% alone costs about 20 points and
    his other categories win back most of it) and where he and the pick would rank with that category left out, with a
    **Punt FT%** button that unticks it through the settings flow (after the first pick it asks to apply first);
  - on your turn, when the best plan and another plan are within **1.5** roster points, the one whose first player is the
    least likely to last until your next pick is recommended (by at least 5 points of chance), and the page says so ("Level
    with Lauri Markkanen ... Kevin Durant is the likelier to be gone by your pick 30"). The player more likely to still be
    there can wait; taking him first would waste the pick. With no later pick nothing is re-ranked, and while you are
    waiting nothing is either. The 1.5 is a judgement (about half the median gap between a player's projected and last
    season's score), not validated.

  `python tools/snapshot.py` saves a draft-day snapshot (pool, XRank/ADP, scores under your settings, the plan) to
  `data/2026-27/snapshot_<date>.csv`, so after the season the score, XRank, ADP and the tie band can be compared with real
  results and the band tuned.
- **My rules** (top of the Plan panel) restrict your own plan: **Never pick** keeps players out of the picks you give, and
  **Choose only from** limits a pick to the players you list ("my pick 1: only Jokic or Wembanyama", "not Kawhi Leonard at
  my picks 1 to 3"). Picks count your own picks (1 is overall pick 2 in slot 2), and a blank end means to the end. Each rule
  is a switch (click to turn it off) with a cross to remove it, and rules are saved with the draft and kept by Reset. They
  filter the planner's candidates, so they shape the recommendation, the plan, the alternatives and the late-round fill,
  and never the other teams, who are planned as if the rules did not exist. A rule nobody can satisfy (every player it
  allows is gone) is dropped for that pick and marked "could not be met". The page says what the rules cost: the roster
  score of the best plan without them, and who it would start with. Players a "Never pick" rule keeps out of your next
  pick carry a "rule" tag in the table. Code: `rules.py`.
- **Position flexibility.** The planner ranks plans by their score plus 0.3 points for each position a new pick can
  fill beyond the first (`FLEXIBILITY_BONUS` in `optimizer.py`), so a PG/SG beats a PG of the same score. The 0.3 is a
  judgement, not a calibrated number: it can decide between close players (neighbouring scores differ by 0.1 at the
  median), and over a whole plan it costs under 0.3 roster points (measured on simulated drafts). With the page's own
  settings (uncapped, games counted) it changed no recommendation in 96 simulated states and gives the same 8-step plan
  from an empty draft; with capped scores one late pick differs. The "Roster score" shown is the plain sum of the scores, and the
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

## Home server (use it from a phone)

The dashboard can run on the home server so any device on the home network can open `http://192.168.1.131:8001/`.
There is no login: it answers only to the names in `deploy/docker-compose.yml` (`--allow-name`), and the port must not be
forwarded on the router. The server keeps its own saved draft in `~/dashboards/draft-yahoo-fantasy/deploy/state/`, so use
that address on every device (the copy on a laptop is a different draft). To install or update, from this folder:

```
rsync -a --delete --exclude-from=.dockerignore --exclude deploy/state ./ fran@192.168.1.131:dashboards/draft-yahoo-fantasy/
ssh fran@192.168.1.131 'cd ~/dashboards/draft-yahoo-fantasy/deploy && docker compose up -d --build'
```

`run_dashboard.py --host 0.0.0.0 --allow-name <address>` does the same without Docker. Without `--allow-name` the server still
refuses any request that does not name `127.0.0.1` or `localhost`.

## How a score is built

For each category, a player's per-game projection is placed between the 5th and 95th percentile of the first 150 players (the scale is fixed on them, so the 95 deeper players are scored on it and nobody's score moves when the pool grows)
(0 to 1, clamped; turnovers are reversed so fewer is better). The score is the mean of the selected categories times 100.
This is the composite from `nba-yahoo-fantasy-daily-dose`, checked against that project's golden test cases.

FG% and FT% cannot be averaged across players, so they are scored as *impact*: makes above what a baseline shooter would
have made on the same attempts, per game. That adds up across a roster, which is what a matchup compares.

The plan is the best set of players for your remaining picks, one per pick, where each is likely to still be there, nobody
repeats and everyone can start at once. The search is exact, and is tested against brute force.

The search is exact for the first 8 rounds, whatever the score method and however many categories are ticked (about 0.2
seconds). Searching more is out of reach: with a category unticked, 10 rounds took up to 100 times longer and 11 ran past
150,000 steps with no plan. So rounds 9 to 13 are **filled in by score**: each takes the best player likely to last, a player
who fills a starting slot still open first (a PG or an F that the eight planned players left open). They show dimmed in the
plan and do not count in the "Roster score", which is for the planned picks. The odds shown for the filled-in picks are
low: Yahoo's ADP says almost everyone is gone by pick 125, and the pool ends at 245. The search prunes with two bounds, a
pick cannot beat its best remaining candidate and the same star cannot fill two picks.

## Data

| File | Source | Used for |
|---|---|---|
| `data/2026-27/projections.csv` | draft-room screenshots, read by hand | XRank, Rank, ADP for the first 245 players (only the draft room has them). A missing ADP below the 150th is estimated: after every player who has one |
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
fantasy_draft/   scoring, flags, lineup rules, my pick rules, availability, optimizer, data loading, Yahoo parser, server
  web/           the page (plain HTML, CSS and JavaScript)
tests/           pytest suite, with a golden fixture copied from nba-yahoo-fantasy-daily-dose
legacy/2025/     last year's scripts and notebook, kept for reference only
```
