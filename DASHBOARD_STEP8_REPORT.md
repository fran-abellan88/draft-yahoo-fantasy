# Step 8 report

From the builder, 2026-10-02. For the reviewer. Branch `feat/mock-and-standings` from `main` (6a09567), 3 commits, nothing pushed.
Suite: 464 passed, flake8 clean.

Asked by the user: settings confirmation after the first pick; the small fixes; the real draft and the mock draft both
available in the app; the 14-team table updated with every pick, "so far" and projected, sorted by team score.

## What changed

| Commit | What it does |
|---|---|
| `e92c4ef` | A settings change after the first pick waits in the panel: "N picks logged. Apply: leave out TO? ...", with Apply and Keep current. Several clicks become one confirmation; closing the panel keeps what was in use; before the first pick changes apply at once. Also: the draft badge and log buttons are no longer green, no "Saved" on a new empty draft, and a wide My team lists its slots in two columns |
| `56401e5` | `league_table` gives every team a **score**: the sum over ticked categories of the share of the other compared teams it beats (expected categories won against a random team, "5.8/9"), a place, and returns rows best first. **So far** now compares the first n picks of every team, n being the round in progress, and scales up a team that has not made its n-th pick (the rule already used for uncredited picks). A team with no credited player is left out of ranks and listed last. The need weights still use complete rounds only |
| `ebda8ba` | The mock draft is served at `/mock` by the same program: its own `DraftService(rehearsal=True)` and its own file (`saved_mock_draft.json`). A Real draft / Mock draft switch in the top bar navigates between them; the mock one has an orange rule under the top bar. `--rehearsal` is gone, `--mock-file` is new, and the two files must differ |

## Decisions to challenge

1. **The mock draft is a route, not a switch inside the real draft.** The earlier rule (a rehearsal is never a button in the live draft) still holds in spirit: the real routes refuse `/api/autopick`, `/mock` cannot read or write the real file, and browser copies are keyed by file and mode.
2. **Score is unweighted** (need weights are not used) and counts only ticked categories.
3. **So far scales in the round in progress.** Early in round 1 only a few teams have a player, so ranks are among those teams; the note says how many teams are scaled.
4. **"Log the users' selections" I read as logging every manager's pick by clicking, which already existed.** Nothing new was built for it.

## Checked in Chrome (port 8100, scratch files)

Mock draft auto-played to pick 55; the projected table came out sorted (5.8/9 down to 3.4/9); So far showed "the 2 teams yet to make pick 4 are scaled up"; Apply, Keep current and closing the panel behaved as described; `/api/autopick` on the real route answered 400; the real page shows mode "real", no saved badge and 14 empty rows. Not checked: light mode, Safari, Firefox, other widths.

## After review 13 (Q1 to Q6)

Reviewer accepted all three parts. Fixed in one commit, suite 467 passed, flake8 clean:

- **Q1** a reloaded draft with a file behind it shows "Saved" again.
- **Q2** round 1: teams with no player are "left out", not "scaled" (`leftOut` in the league block, `waiting` counts only teams with a player); a lone team has no score or place; Standing says how many other teams it is compared against.
- **Q3** a browser copy with the same picks as the file raises no "the file never received" notice.
- **Q4** a pending settings change is dropped when the draft changes (every refresh, Reset included).
- **Q5** the confirmation names the availability change ("set the ADP window to 4", "judge availability with the ADP window"), with the value after clamping.
- **Q6** from 2350 px the log sits under My team in the third column and the 14 teams have the fourth to themselves (measured in an iframe at 2500 x 1400: team 380 x 73 at pick 0, log 380 x 1227, 14 teams 540 x 1315).
- The So far note now says a scaled team usually drops a little when it picks.

Not changed: the Projected table still puts my planned team against ADP-order teams, so being first there is close to automatic (see the user's question on opponent strength; an experiment is proposed, nothing built).
