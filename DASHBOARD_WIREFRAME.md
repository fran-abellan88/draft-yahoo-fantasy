# Dashboard wireframe, first pass

For approval by the user and comment by the reviewer. **No code follows from this until it is approved.** It is a
sketch of regions, not of detail: where things live at three window widths, in the two states that matter while
drafting, and what drops out as the window narrows. Finding IDs refer to `DASHBOARD_REVIEW.md`.

Widths are the dashboard window, not the monitor: the user drafts with Yahoo's draft room beside it. Assumed halves of
a 1920, 2560 and 5120-wide desktop. The real `innerWidth` is still to be reported; the design must hold between about
960 and 2560 px, so the layout is a fluid grid with minimum panel widths, not fixed breakpoints (B2).

## Rules this drawing follows

1. **The page does not scroll.** A top bar is always visible and the pool table fills the rest of the height. The
   table is the only thing that scrolls in the middle of the screen (B1).
2. **The main action is always on screen**: search (`/` focuses it) and the table. Logging a pick never starts below
   the fold.
3. **The recommendation is large only when it is the user's turn.** Waiting, it is a compact block; on the clock it
   takes the top of its column and carries the Draft button (B1, C8).
4. **Everything planned but not yet built has a box**, so no later feature reopens the shell: the 14-team panel
   (E2), the settings summary and button (C10), the mode indicator (E3).
5. **Panels are added by width, not by margin.** Beyond about 1900 px the extra width becomes more panels (4 columns),
   never wider gutters (B2). Below that, panels move into tabs rather than under the table.

## Regions

| Box | What it holds | Source |
|---|---|---|
| **MODE** | "Live: every pick logged by you" or "Rehearsal: other teams automatic", and the count of unseen picks when there are any | E3, step 3 |
| **CLOCK** | Pick, round, who is choosing, picks until mine | existing |
| **SNAKE** | The current round's order, mine marked | existing |
| **SEARCH** | Name or team, all words must match, Enter logs a unique match | B1, C9 |
| **UNDO / RESET** | Undo last pick, reset with confirmation | existing |
| **SETTINGS** | One line: "9 categories, uncapped, games counted", and a button that opens the panel; locked after the first pick | C10 |
| **TABLE** | The 150 players: sortable columns, rank vs ADP, category tints, 32 px rows, one line per player | C1, C2, C3 |
| **REC** | The recommendation: compact while waiting, large with the Draft button on the clock. One line says why when it is not the top score | B5 |
| **PLAN** | One line per planned pick: pick, name, odds; the "if he is gone" line (hidden when it says nothing) | A2, C6, C7 |
| **MY TEAM** | Roster as the ten starting slots plus bench, and whether one more of each position still fits | C5 |
| **STANDING** | My team in each category against the other 13 (rank, share of teams beaten), real FG% and FT% ratios | E2, replaces C4 |
| **14 TEAMS** | All 14 teams' category totals, mine highlighted; labelled "so far, n players each" or "projected, 8 each" | E2 |
| **LOG** | Draft log with the picking slot; any entry can be edited | D8, X1 |

## 2560 px: four columns

Waiting for my pick (24 made, I pick at 27):

```
+------------------------------------------------------------------------------------------------------------------+
| MODE: Live | CLOCK: Pick 25, slot 11 | SNAKE ▢▢▢▢▣▢▢▢▢▢▢▢▢▢ | SEARCH [ / ]      | UNDO RESET | SETTINGS: 9 cats ⚙ |
+--------------------------------------------+-------------------+------------------+-------------------------------+
| TABLE                                      | REC (compact)     | MY TEAM          | 14 TEAMS                      |
| #  Player      Score Atpick ADP XR GP ...  |  At 27: Holmgren  |  PG  Jokic       |  team  FG FT 3P PT RB AS ST BK TO|
| 1  ........                                |  59% still there  |  SG  .....       |  1     .. .. .. .. ..           |
| 2  ........                                |  scores below #1  |  G   .....       |  2 (me) ..                      |
| 3  ........                                +-------------------+  SF  .....       |  3     ..                       |
| .  (only this scrolls)                     | PLAN              |  PF  ....        |  ...                            |
| .                                          |  27 Holmgren 59%  |  F   (open)      |  14                             |
| .                                          |  30 Leonard  54%  |  C   (open)      +---------------------------------+
| .                                          |  55 Alexander 65% |  C   (open)      | STANDING                        |
| .                                          |  If Holmgren is   |  Util (open) x2  |  FG% 3rd  of 14  ████░░         |
| .                                          |  gone: Leonard -… |  Bench x3        |  3PM 9th         ██░░░░         |
| .                                          |                   |  fits: PG C only |  ...                            |
|                                            |                   +------------------+---------------------------------+
|                                            |                   | LOG  #24 ... #1  |                                 |
+--------------------------------------------+-------------------+------------------+---------------------------------+
```

On the clock (pick 27 is mine):

```
+------------------------------------------------------------------------------------------------------------------+
| MODE: Live | ██ YOUR PICK 27 ██ (whole bar tinted) | SNAKE | SEARCH [ / ] | UNDO RESET | SETTINGS: 9 cats ⚙       |
+--------------------------------------------+-------------------+------------------+-------------------------------+
| TABLE  (At-pick column now reads "At 30")  | REC (large)       | MY TEAM          | 14 TEAMS                      |
| rows marked: ★ recommended, "plan: 58"     |  Chet Holmgren    |  (as above,      |  (as above)                   |
|                                            |  OKC · PF/C       |   plus the slot  |                               |
|                                            |  [ Draft Holmgren]|   he would fill) +-------------------------------+
|                                            |  Daniels scores   |                  | STANDING                      |
|                                            |  higher but …58   |                  |  (as above)                   |
|                                            +-------------------+                  +-------------------------------+
|                                            | PLAN              |                  | LOG                           |
|                                            |  Or take instead: |                  |                               |
+--------------------------------------------+-------------------+------------------+-------------------------------+
```

## 1280 px: two columns

TABLE needs about 900 px, so one rail of about 360 px fits beside it. 14 TEAMS and LOG move into tabs in the rail.

Waiting:

```
+--------------------------------------------------------------------------+
| MODE | Pick 25 · you pick at 27 | SNAKE ▢▢▢▣▢▢▢▢ | SEARCH [ / ] | UNDO ⚙ 9 cats |
+------------------------------------------------------+-------------------+
| TABLE                                                | REC (compact)     |
| #  Player     Score Atpick ADP XR GP PTS REB ... FT% |  At 27: Holmgren  |
| 1  ........                                          |  59% still there  |
| 2  ........                                          +-------------------+
| .  (only this scrolls)                               | PLAN  27 · 30 · … |
| .                                                    +-------------------+
| .                                                    | MY TEAM (slots)   |
| .                                                    +-------------------+
| .                                                    | STANDING          |
|                                                      +-------------------+
|                                                      | [14 TEAMS] [LOG]  |  ← tabs
+------------------------------------------------------+-------------------+
```

On the clock: the top bar is tinted, REC becomes large with the Draft button at the top of the rail, and PLAN stays
below it. Nothing else moves.

## 960 px: one column, tabs

Nothing fits beside the table, and 960 is where panels have to drop out. The table keeps the full width; its first
two columns (#, Player) stay fixed and the other columns scroll sideways behind them. Panels become tabs under the top
bar. **The recommendation never hides**: it is a one-line strip under the top bar.

Waiting:

```
+----------------------------------------------------+
| MODE | Pick 25 · you: 27 | SEARCH [ / ] | UNDO | ⚙  |   ← snake strip drops into the CLOCK tooltip
+----------------------------------------------------+
| REC strip: At 27 Holmgren, 59% there     [plan ▾]  |
+----------------------------------------------------+
| [Table] [Plan] [My team] [Standing] [14 teams] [Log]|   ← tabs; Table is open
+----------------------------------------------------+
| #  Player        Score  Atpick  ADP | XR GP PTS …  |   ← columns after ADP scroll sideways
| 1  ........                                        |
| .  (only this scrolls)                             |
+----------------------------------------------------+
```

On the clock: the top bar is tinted, the REC strip becomes a two-line block with the Draft button, and the tab strip
is unchanged.

### What drops out, and where it goes

| Region | 2560 | 1280 | 960 |
|---|---|---|---|
| TABLE | full, 4-column layout | full | full width, #/Player fixed, rest scrolls sideways |
| REC | own block | own block in the rail | one-line strip, large on the clock |
| PLAN | own block | rail | tab (the strip links to it) |
| MY TEAM | own column | rail | tab |
| STANDING | own column | rail | tab |
| 14 TEAMS | own column | tab in the rail | tab |
| LOG | column | tab in the rail | tab |
| SNAKE | in the top bar | in the top bar | in the CLOCK tooltip |
| SETTINGS | one-line summary + button | summary + button | gear button only (summary in its tooltip) |
| MODE | in the top bar | in the top bar | in the top bar, shortened to "Live" / "Rehearsal" |

## Two states that step 3 creates (1280 px)

Unseen picks present: the user logs "N picks I did not see", and the plan is uncertain until players are confirmed.

```
| MODE: Live · 3 UNSEEN picks (24–26) |  …  |
+------------------------------------------------------+-------------------+
| TABLE                                                | REC  (approximate |
| pool is "unverified": rows show odds that assume     |  until the unseen |
| nothing is gone yet                                  |  picks are marked)|
| each row has  [mark as gone]                         +-------------------+
| clicking a player logs the NEXT pick, not an unseen  | UNSEEN picks      |
| one; unseen picks are filled from the LOG            |  24 ?  25 ?  26 ? |
+------------------------------------------------------+  [mark as gone…]  |
```

An unseen pick can never be one of the user's own pick numbers (the page asks for that pick instead).

Edit a pick, with a swap:

```
+-----------------------------------------------+
|  Kawhi Leonard is logged at pick 47.          |
|  Swap picks 40 and 47?                        |
|  This changes your roster: pick 40 is yours.  |
|                                               |
|  [ Swap ]  [ I do not know what 47 was ]  [ Cancel ] |
+-----------------------------------------------+
```

## What this drawing does not decide

- **Table columns kept at 960 px.** Only the order of the scrolled columns and which two stay fixed are drawn.
- **Colours and the tint scales** (C3, B4, D1): to be settled at step 7.
- **The 14-team panel's detail** (E2): a grid of the nine categories, mine highlighted, is assumed.
- **Rehearsal mode controls** (E3): only the indicator has a place; how a rehearsal is started comes with step 5.

## Questions for the user

1. **Window width.** What is `innerWidth` in the dashboard's browser window on the real monitor? It decides which
   column of the table above is the one that matters.
2. **Is a one-column tabbed layout acceptable at 960 px?** The alternative keeps a narrow rail of about 320 px beside
   the table (REC, PLAN, MY TEAM and STANDING visible together) and shows only Score, ADP and a few stat columns, with
   the rest behind a "more columns" toggle. It trades table width for always-visible panels.
3. **Should the draft log stay visible at 1280 px?** Here it is a tab. A picks log you glance at while logging may be
   worth a permanent strip.
