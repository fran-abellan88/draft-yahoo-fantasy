# Steps 4 to 9 report: the rest of the features

From the builder, 2026-10-02. For the reviewer. Commits since `8d13bcc` are not pushed. The user gave the go-ahead for "the rest of the features" and asked that you be told when it is done.

Suite: **444 passed**, flake8 clean, with Node on the path (skipped: 0).

| Step | What it does now |
|---|---|
| Team names | `draft.TEAM_NAMES` (Yahoo's draft order, slot 2 is the user's) in the clock, log, last pick and snake tooltips |
| E2, `league.py` | All 14 teams from the pick log: totals per game, FG% and FT% as ratios of totals, turnovers reversed, equal size (first n picks, n = complete rounds), uncredited picks (unseen, gone, outside) counted and shown. The user's rank and the share of the other 13 beaten. A projected view: logged picks, my best plan, other teams filled by autopick, 8 each |
| E3, `autopick.py` | Best ADP left that keeps the roster startable (ten slots, bench beyond); optional seeded noise from the availability spread. Used for the projection (the plan's players protected from the other teams) and for a rehearsal mode (`/api/autopick`, the page logs the other teams' picks until my turn; Undo goes back to before my last pick; the mode and seed are saved with the draft). Catch-up stays "unseen", as decided |
| E1, `needs.py` | Optional weighted composite: weight by closeness `4s(1-s)` of the share beaten, a ramp over 4 complete rounds, a cap of 40%, normalised to mean 1, ticked categories only. Off by default; equal weights give exactly today's scores and plans (tests); the weights in use are shown under Standing |
| Step 7 | B4 (odds column for my following pick on my turn, tinted); B5 (reason line when the recommendation is not the top score, star and "plan: N" in the table); B6 (rounds not planned wording, best available that fits the lineup); C3 (stat tint by category score, unticked columns dimmed); C5 (ten slots and bench, positions that still fit); C7 (plan odds line removed, "Other strong plans" removed); C9 (every word must match; a drafted player is named with his pick); D4 (visible hover, tested contrast); D5 (arrow keys on rows); G2 (the same team in the other order says when the recommended player comes next); H4 (Gone only where the unseen picks move the odds 5% or more); look-first names are buttons; the tab is remembered; a saved-state badge |
| Not done | D1 colour roles (green still has several meanings), D8 beyond the team name in the log, the C2 row density pass, a measured table width for the thresholds, light mode and Safari/Firefox, and the decision on the 7.5 vs 5.7 availability count (E3-style one-player-per-pick model is not built: the availability model is unchanged) |

Checked in Chrome through an iframe at 2500 x 1476 (the real window cannot be resized past my screen): rehearsal from pick 1 to my pick and back with Undo; standing and 14 teams; the reviewer's B5 example (Daniels scores higher, the plan takes him at 58, 67%); the on-the-clock alternatives with the next-pick note; slots and "one more player can start at".

Questions for you: (1) is the projection's treatment right (other teams' fill never takes my plan's players)? (2) do the weights (closeness, 40% cap, 4-round ramp) look sound? (3) anything you would block before the real draft?
