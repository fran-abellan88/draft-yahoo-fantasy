# Step 6 report: the layout

From the builder, 2026-10-02. For the reviewer. Not pushed. Commits: this one and `64a4b00`, `6620e8d` since the last push.

Approved by the user: M1 to M4, then the layout. The user's window is about 2500 x 1476, adjustable, on the right half of a 49 inch screen with Yahoo on the left. **Not started: step 4 (14-team scoring) onward.** The wireframe items below marked "not yet" are step 7 or later.

Suite: **399 passed**, flake8 clean, with Node (skipped: 0).

## What is built (from your section 3 for 2500 x 1476)

- The page is one grid, exactly the window high; `html, body` do not scroll. Every panel is a child of that grid; only the named areas change by width, and panels without an area of their own share `tabp` under a tab strip.
- **2350 and up** (4 columns, 420 | table | 380 | 450): REC, PLAN, STANDING (the existing "Category strength" bars until E2) on the left next to the seam; the table; MY TEAM over LOG; the 14 TEAMS box (reserved). **1720 to 2349:** 14 teams and log share a tab panel under MY TEAM. **1240 to 1719:** table | rail with REC, PLAN and a tab panel for team, standing, 14 teams, log. **Below 1240:** REC strip, then tabs for everything else including the table. REC is never in a tab.
- Top bar: MODE ("Live" only), clock, snake, I am behind, a settings button that shows "9 categories, uncapped, games counted" and opens the settings panel (categories, score, availability, Reset draft). Banner has its own row under the top bar. Search, position chips, Pick not in the list, and "Logged pick N: name" with Undo are at the head of the table. Table: first two columns sticky when it scrolls sideways.
- The plan panel is capped at 45% of the height and scrolls inside itself.

## Checked

In Chrome, using an iframe at the real widths (my window is 1804 x 981, and resize to 2500 is refused): 2500 x 1476, 1720 x 1100, 1280 x 950, 960 x 880. The document never scrolled (`scrollHeight` equals the window height); the tab strip showed the right tabs at each width and kept a valid active one; logging a pick shows "Logged pick 1: Nikola Jokic." with "Undo pick 1: Nikola Jokic"; changing the score updates the summary line; settings open and close.

Background-tab note: resize events do not fire in my background tab, so I dispatched them by hand; the code path is the same.

## Not yet (and why)

Saved-state indicator in MODE, the "taken by unseen picks" row, real STANDING and 14 TEAMS (E2), look-first names as buttons, Gone buttons only where odds move 5% (H4), "Other strong plans" is still shown (the wireframe drops it), the tab panel does not remember its tab across a reload, and the thresholds have not been tuned against the final table width (I did not measure the table first, as your note 1 asked: at 1720 FG% and FT% already scroll sideways). Light mode and Safari/Firefox unchecked.
