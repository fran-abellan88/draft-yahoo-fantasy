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

Your picks are kept in the browser, so reloading the page mid-draft loses nothing. **Reset draft** clears them.

## Using the page

- **Click a player** to log the pick that is on the clock. Picks are logged in order and the snake order decides
  which ones are yours, so the state cannot disagree with the draft. **Undo last pick** removes the latest one.
- **Pick not in the list** logs a pick of a player who is not among the 150. It counts as a pick, nobody leaves the
  pool, and if it is yours it fills one starting slot at any position, at replacement-level value.
- **I am behind**: type the pick Yahoo is at and the picks you missed become *unseen*. A player the table lists may have
  been taken at one of them, so every availability number allows for that. Press **Gone** on a player you know was taken
  and one unseen pick is resolved to him (the one closest to his ADP), which raises the odds of the players near it. Your
  own picks are never unseen: the page stops before one and asks you to log it first. On your turn with unseen picks the
  page shows the chance the recommended player is still on the board, lists up to three better-scoring players the odds
  left out ("look first at"), and has a **He is gone** button beside Draft.
- **Undo** reverts the last action, including Gone (the pick becomes unseen again) and a whole "I am behind". A gone
  entry in the log has **Unmark**. Every log row has **Edit**: swap two picks, say "I do not know what this pick was"
  (it becomes unseen, a player logged there returns to the pool), or place a gone player at an unseen pick. Each edit
  is confirmed first, cannot put an unseen or gone pick on one of your own pick numbers, and cannot be undone with Undo.
- **Scoring categories**: untick one to leave it out of every score and plan. The score is the average of the ticked
  categories, so ticking fewer does not lower anyone's score.
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
