# Dashboard wireframe, second pass

For approval by the user and comment by the reviewer. **No layout code follows from this until it is approved.** It
sketches regions, not detail: where things live at four window widths, in the two states that matter while drafting,
what gives way when the window gets smaller, and the states that step 3 creates. Finding IDs refer to
`DASHBOARD_REVIEW.md`.

Revised after the reviewer's second reply (W1 to W6): a height budget, the order in which panels leave tabs, a 1720 px
column, a corrected unseen-picks state with an entry control, a place for the position filter, search and filter at the
head of the table, Reset moved into settings, and a permanent last-pick line.

Widths and heights are the dashboard window, not the monitor: the user drafts with Yahoo's draft room beside it. The real
`innerWidth` and `innerHeight` are still to be reported; the design must hold from about 960 to 2560 px wide and down to
**900 px high**, so the layout is a fluid grid with minimum panel sizes, not fixed breakpoints (B2).

## Rules this drawing follows

1. **The page does not scroll.** A top bar is always visible and the table fills the rest of the height. A panel that
   needs more height than it has scrolls inside itself; the page never does (B1).
2. **The main action is always on screen**: the search and the table. Logging a pick never starts below the fold.
3. **The recommendation is large only when it is the user's turn.** Waiting, it is compact; on the clock it takes the
   top of its column and carries the Draft button (B1, C8).
4. **Everything planned but not yet built has a box**, so no later feature reopens the shell: 14-team panel (E2),
   settings summary and button (C10), mode indicator (E3), unseen-pick entry (step 3).
5. **Width becomes panels, not margins, and panels leave tabs in a fixed order** (below). Below the two-column width
   panels are tabs, never rows under the table, so nothing needed is ever far down the page (B2).
6. **Undo stays beside the last logged pick. Reset lives in the settings panel**, because Reset destroys the draft.

## Regions

| Box | What it holds | Source |
|---|---|---|
| **MODE** | "Live: every pick logged by you" or "Rehearsal: other teams automatic"; the count of unseen picks when there are any | E3, step 3 |
| **CLOCK** | Pick, round, who is choosing, picks until mine | existing |
| **SNAKE** | The current round's order, mine marked | existing |
| **BEHIND** | "I am behind": opens "Yahoo is at pick [ ]". The page makes the picks in between unseen | step 3 |
| **SETTINGS** | One line "9 categories, uncapped, games counted" and a button that opens the panel. Locked after the first pick; **Reset draft** sits in the panel's footer and stays usable when locked | C10 |
| **SEARCH + FILTER** | Search (`/` focuses it) and the position chips All, PG, SG, SF, PF, C, at the head of the table column | B1, C9 |
| **LAST PICK** | "Logged pick 24: Tyrese Maxey. [Undo]", always visible, next to the search | W6, D4 |
| **TABLE** | The pool: sortable columns, rank vs ADP, category tints, one line per player. The only scrolling region in its column | C1, C2, C3 |
| **REC** | Recommendation: compact while waiting, large with the Draft button on the clock; one line says why when it is not the top score | B5 |
| **PLAN** | One line per planned pick, with odds; the "if he is gone" / "or take instead" line (hidden when it says nothing); the "search stopped early" note sits above it. "Other strong plans" is dropped | A2, C6 |
| **MY TEAM** | The ten starting slots plus bench, and whether one more of each position still fits | C5 |
| **STANDING** | My team in each category against the other 13 (rank, share of teams beaten), real FG% and FT% ratios | E2, replaces C4 |
| **14 TEAMS** | All 14 teams' category totals, mine highlighted, labelled "so far, n players each" or "projected, 8 each". A row "taken by unseen picks, not counted" holds players marked as gone whose team is unknown | E2, W3 |
| **LOG** | The draft log with the picking slot; any entry can be edited | D8, X1 |

## The fluid grid: when each panel leaves its tab

Minimum sizes the grid is built on: table 860 px wide, any panel 320 px wide. Gaps and padding add about 100 px. Panels
leave tabs as the window widens, in this order:

| Window width | Columns | Panels that have their own space | Still in tabs |
|---|---|---|---|
| below 1240 | 1 | REC (a strip) | PLAN, MY TEAM, STANDING, 14 TEAMS, LOG |
| 1240 and up | 2 | REC, PLAN | MY TEAM, STANDING, 14 TEAMS, LOG |
| 1580 and up | 3 | REC, PLAN, MY TEAM, STANDING | 14 TEAMS, LOG |
| 1920 and up | 4 | + 14 TEAMS | LOG |
| 2240 and up | 4 | + LOG (under 14 TEAMS) | none |

The first four thresholds follow from the minimum sizes (860 + 320 per panel + about 60 to 100 for gaps and padding). The
2240 figure is an estimate that gives each panel about 400 px; it is the least certain number here.

So 1280, which was the edge in the review, sits inside the two-column band, not on a breakpoint. 960 is the one-column
layout. 1720 is three columns.

## The height budget

900 px high is the middle of the range, not the floor: a window on a 1080-line desktop is roughly 830 to 950 px high, so
the **800 px case is part of the design** (below). Budget for the two-column rail at 900, which is the tightest:

| Part | Waiting | On the clock |
|---|---|---|
| Top bar (MODE, CLOCK, SNAKE, SETTINGS) | 56 | 56 |
| REC | 90 | 200 |
| PLAN, 7 steps and header | 230 | 230 |
| Tab strip | 40 | 40 |
| **Left for the tab panel** | **about 480** | **about 370** |

At **800 px** the tab panel has about 380 px waiting and about 270 on the clock, PLAN already shows four steps with
"+3 more" on the clock, and the snake strip is in the CLOCK tooltip. The REC block is unchanged.

The tab panel scrolls inside itself. What gives way, in order, when the window is shorter: the tab panel gets less
height (it scrolls more); then PLAN shows its first four steps with "+3 more"; then the snake strip folds into the CLOCK
tooltip. **REC never gives way.**

## 2560 px: four columns

Waiting for my pick (24 made, I pick at 27):

```
+----------------------------------------------------------------------------------------------------------+
| MODE: Live | CLOCK: Pick 25, slot 11 | SNAKE ▢▢▢▣▢▢▢ | [I am behind]   | SETTINGS: 9 cats, uncapped ⚙    |
+------------------------------------------+------------------+----------------+---------------------------+
| [ / Search players ] [All PG SG SF PF C] | REC (compact)    | MY TEAM        | 14 TEAMS                  |
| Logged pick 24: T. Maxey  [Undo]         |  At 27: Holmgren |  PG  Jokic     |  team FG FT 3P PT RB AS … |
|                                          |  59% still there |  SG  .....     |  1    .. .. ..            |
| #  Player    Score Atpick ADP XR GP ...  |  below #1: why   |  G   .....     |  2 (me) ..                |
| 1  ........                              +------------------+  SF  .....     |  ...                      |
| 2  ........                              | PLAN             |  PF  ....      |  14                       |
| 3  ........                              |  27 Holmgren 59% |  F   (open)    |  unseen, not counted: 0   |
| .  (only this scrolls)                   |  30 Leonard  54% |  C   (open) x2 +---------------------------+
| .                                        |  55 Alexander .. |  Util (open) x2| LOG                       |
| .                                        |  If Holmgren is  |  Bench x3      |  #24 Maxey slot 11        |
| .                                        |  gone by 27: ... |  fits: PG, C   |  #23 ...                  |
| .                                        |                  +----------------+                           |
| .                                        |                  | STANDING       |                           |
|                                          |                  |  FG% 3rd of 14 |                           |
+------------------------------------------+------------------+----------------+---------------------------+
```

On the clock (pick 27 is mine): the top bar is tinted "YOUR PICK 27", REC is large with `[ Draft Holmgren ]` and the reason
("Daniels scores higher but should last to 58 at 67%"), the At-pick column reads "At 30", rows are marked ★ for the
recommended player and "plan: 58" for planned ones, and the alternatives line reads "Or take instead: ...". Nothing else
moves.

## 1720 px: three columns

```
+--------------------------------------------------------------------------------+
| MODE | Pick 25 · you: 27 | SNAKE ▢▢▣▢▢ | [I am behind] | SETTINGS: 9 cats ⚙      |
+----------------------------------------+------------------+--------------------+
| [ / Search ] [All PG SG SF PF C]       | REC (compact)    | MY TEAM            |
| Logged pick 24: T. Maxey  [Undo]       +------------------+ STANDING           |
| TABLE                                  | PLAN             +--------------------+
| .  (only this scrolls)                 |  27 · 30 · 55 …  | [14 TEAMS] [LOG]   |  ← tabs
+----------------------------------------+------------------+--------------------+
```

On the clock: tinted bar, large REC with the Draft button, PLAN below it.

## 1280 px: two columns

```
+----------------------------------------------------------------+
| MODE | Pick 25 · you: 27 | SNAKE ▢▢▣▢ | [Behind] | SETTINGS ⚙   |
+-------------------------------------------------+--------------+
| [ / Search ] [All PG SG SF PF C]                | REC (compact)|
| Logged pick 24: T. Maxey  [Undo]                |  At 27 ...   |
| TABLE                                           +--------------+
| #  Player   Score Atpick ADP XR GP PTS … FT%    | PLAN         |
| .  (only this scrolls)                          |  27 · 30 · …  |
| .                                               +--------------+
| .                                               |[My team]     |
| .                                               |[Standing]    |
| .                                               |[14 teams]    |
| .                                               |[Log]         |  ← tabs, panel scrolls inside
+-------------------------------------------------+--------------+
```

On the clock: tinted bar, large REC with the Draft button at the top of the rail, PLAN below, the tab panel keeps what is
left (see the height budget).

## 960 px: one column, tabs

Nothing fits beside the table. The table takes the full width, with `#` and `Player` fixed and the other columns
scrolling sideways. **The recommendation never hides**: it is a strip under the top bar.

Waiting:

```
+---------------------------------------------------+
| MODE | Pick 25 · you: 27 | [Behind] | SETTINGS ⚙  |   ← snake strip is in the CLOCK tooltip
+---------------------------------------------------+
| REC strip: At 27 Holmgren, 59% there     [plan ▾] |
+---------------------------------------------------+
| [Table][Plan][My team][Standing][14 teams][Log]    |   ← Table is open
+---------------------------------------------------+
| [ / Search ] [All PG SG SF PF C]                  |
| Logged pick 24: T. Maxey  [Undo]                  |
| #  Player      Score Atpick ADP | XR GP PTS …     |   ← columns after ADP scroll sideways
| .  (only this scrolls)                            |
+---------------------------------------------------+
```

**On the clock the strip grows to carry the whole decision without a tab switch**, because that is when a timer is
running: the recommendation, the reason, the "or take instead" line and one line of standing in three groups:
"Winning: REB, AST. Close: 3PM, ST, BLK. Behind: FT%".

## What drops out, by width

| Region | 960 | 1280 | 1720 | 2560 |
|---|---|---|---|---|
| TABLE | full width, 2 columns fixed | full | full | full |
| SEARCH + FILTER, LAST PICK | head of table | head of table | head of table | head of table |
| REC | strip (grows on the clock) | rail | rail | column |
| PLAN | tab | rail | rail | column |
| MY TEAM | tab | tab | column | column |
| STANDING | tab | tab | column | column |
| 14 TEAMS | tab | tab | tab | column |
| LOG | tab | tab | tab | column |
| SNAKE | in CLOCK tooltip | top bar | top bar | top bar |
| SETTINGS | gear (summary in tooltip) | summary + gear | summary + gear | summary + gear |
| MODE | "Live" / "Rehearsal" | full | full | full |
| "Search stopped early" note | in the Plan tab, flagged on the strip | above PLAN | above PLAN | above PLAN |

## Two states that step 3 creates (1280 px)

**Unseen picks present.** The user presses **[I am behind]** and enters the pick Yahoo is at ("Yahoo is at pick 31").
The page makes every pick between the last logged one and 30 an unseen pick. Unseen picks may never be the user's own
pick numbers; the page asks for those directly.

```
| MODE: Live · 3 UNSEEN picks (25–27)  ·  Yahoo is at 28   [I am behind]  |
+-------------------------------------------------+--------------+
| [ / Search ] [All PG SG SF PF C]                | REC          |
| Logged pick 24: ...                  [Undo]     |  approximate |
| TABLE: each row's odds are the chance he is     |  until the   |
| still there GIVEN the unseen picks (the product |  unseen picks|
| over unseen and future picks), so they are      |  are marked  |
| lower than usual. Rows have  [mark as gone]     +--------------+
| Clicking a player logs the NEXT pick, never an  | UNSEEN       |
| unseen one.                                     |  25 ?  26 ?  |
|                                                 |  27 ?        |
|                                                 | Marking a    |
|                                                 | player gone  |
|                                                 | removes one  |
|                                                 | unseen pick  |
+-------------------------------------------------+--------------+
```

In the 14-team panel a player marked as gone is **not credited to any team** unless the user fills the pick from the log;
until then the row "taken by unseen picks, not counted" shows how many.

**Edit a pick, with a swap.**

```
+----------------------------------------------------------------------+
|  Kawhi Leonard is logged at pick 47.  Swap picks 40 and 47?           |
|  This changes your roster: pick 40 is yours.                          |
|                                                                      |
|  [ Swap ]   [ I do not know what 47 was ]   [ Cancel ]               |
+----------------------------------------------------------------------+
```

## Notes carried to step 6 (the reviewer's fourth reply)

None of these changes the drawing; they are conditions on building it.

1. **Build and measure the table first (C2, C3), then set the grid minimums.** The 860 px table and the 320 px panel
   are today's sizes; the new table (one line per player, Rank vs ADP) may need about 1,000, so all four thresholds above
   are provisional. Whenever the table is narrower than its natural width, at any window width, `#` and `Player` stay
   fixed and the rest scroll sideways. The columns that give way first are XRank, then GP.
2. **The decision gap also exists from 1240 to 1580 px**, where MY TEAM and STANDING share one tab panel and 1280 is a
   likely width. Wherever STANDING has no space of its own, the on-the-clock REC carries the one-line standing
   ("Winning / Close / Behind"). The tab panel remembers the last tab.
3. **The 14-team panel does not fit 320 px as nine columns of totals** (it needs about 370 to 400). Either a larger
   minimum for that panel, or cells show ranks with the totals on hover.
4. **The error banner gets its own row under the top bar**: it is fixed to the top of the window, which is now the top
   bar.
5. **These are breakpoints, so each is checked one pixel either side in a real window** (B2 lived on such an edge).
   Every panel is a child of the same grid at all widths, and the tabbed panels share one grid area, so the layout holds
   by construction instead of by a script swapping elements.
6. **[I am behind]** refuses a pick that is not ahead of the log. **[mark as gone]** works only while unseen picks are
   outstanding, and must not also log the row.

## What this drawing does not decide

- **Table columns kept at 960 px**, beyond which two stay fixed. **Colours and tint scales** (C3, B4, D1): step 7.
- **The 14-team panel's detail**: a grid of nine categories, mine highlighted, is assumed.
- **Rehearsal controls** (E3): only the indicator has a place; starting a rehearsal comes with step 5.

## Questions for the user

1. **Window size.** What are `innerWidth` and `innerHeight` of the dashboard window on the real monitor? Type
   `innerWidth + " x " + innerHeight` in the browser console. Width picks the column count in the table above; height
   decides how much of the rail fits (the budget assumes 900).
2. **Is a one-column tabbed layout acceptable at 960 px**, given that on the clock the strip carries the recommendation,
   the reason, the alternatives and one line of standing? The alternative, a narrow rail with fewer table columns, is
   not drawn until the real width is known.
3. **Is "last logged pick with Undo beside the search, the full log in a tab" enough**, or do you want the log visible
   at all times at 1280 px?
