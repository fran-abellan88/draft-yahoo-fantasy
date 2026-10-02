# Report on your reply 10 (N1 to N4, C2, the log)

From the builder, 2026-10-02. For the reviewer. Not pushed.

| Finding | What it does now |
|---|---|
| N1 | There is no Rehearsal button. `run_dashboard.py --rehearsal` starts a rehearsal instance, and it refuses the real draft file (`--draft-file` required, exit with a message); the live instance's `/api/autopick` refuses with a message; the mode is read from `/api/pool` and never saved with a draft; the startup line says REHEARSAL or "Live draft"; in a rehearsal the Undo label says how many picks it removes ("Undo: 25 picks, back to my pick 2") |
| N2 | The startup line prints "Continuing a saved draft: N picks (version V)" or "No saved draft yet"; the page shows "Continuing a saved draft: N picks. Reset starts a new one." (a dismissable notice, not shown when the browser copy was kept aside). The 3 picks in the project's `saved_draft.json` (Jokic, Wembanyama, Gilgeous-Alexander, 10:27) are not mine as far as I can tell: every run of mine used `--draft-file`. I have NOT deleted it, because it may be the user's; I asked them |
| N3 | A team with an uncredited pick has its counting totals scaled up to the comparison size (a team with 1 credited of 2 counts double); ratios are not scaled; other teams untouched. Tests |
| N4 | The 40% limit is applied after normalising to a mean of 1 (the mean may then differ slightly from 1); docs and tests changed |
| C2 | Player name, team and positions on one line, tighter padding: about 40 rows visible at 1476 px |
| Log | The log is under the 14 teams (4th column); My team takes the whole third column |

Suite: **446 passed**, flake8 clean, Node on the path (skipped 0). Checked in Chrome at 2500 x 1476 through an iframe on a `--rehearsal` instance with its own file.
