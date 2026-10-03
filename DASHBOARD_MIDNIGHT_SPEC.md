# Midnight: handover spec for the dark theme redesign

From the reviewer, 2026-10-03. The user chose **Midnight** from three drawn redesigns and asked for it to be built.
Drawing: https://claude.ai/artifact/KXa5qbQYMMV4aGS2pAAEkF (switch to "Midnight"). Its source, with every value
below, is `/private/tmp/claude-501/-Users-a0844243-FranHome-WorkArea-draft-yahoo-fantasy/c56eeaab-fb94-43ab-89fb-e289c8436a04/scratchpad/palettes/template2.html`
(CSS under `.bd`, Midnight is the base token set). The drawing is not the page: it has the real column widths
(400 / 1044 / 380 / 540 at 2436) but none of the page's behaviour.

The user approves each step, not me. I review each one before it goes to them.

## 0. Before starting

- The working tree on `main` holds uncommitted changes in 10 files (`scoring.py`, `service.py`, `app.js`,
  `index.html`, `logic.js`, `style.css`, three test files, `README.md`). Finish or park them first, then branch.
- **Open decision for the user: light mode.** Midnight is dark only, but the new parts (capsules, rings, tiles)
  show in light mode too and need light values. Either (a) light mode takes the Daylight values from the same
  drawing (drawn and measured: card 73% of white, ink 12.6 : 1), or (b) today's light palette stays and the new roles
  get values derived from it. I recommend (a); the user has not chosen. Step 1 does not need the answer.

## 1. Step 1: tokens, font, card shapes (no new parts)

**Font.** The stack starts with `ui-sans-serif`, which this Chrome does not recognise, so the page falls back to
Avenir Next (lowercase 47% of the size). Use `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. Measured
in Chrome: SF lowercase is 51% of the size and names come out 8% narrower. `font-stretch` works on `system-ui` here
(75% = 14% narrower), which step 2 uses.

**Dark tokens** (both copies):

| Token | Midnight | Notes |
|---|---|---|
| `--paper` | `#000000` | |
| `--surface` | `#1c1c1e` | cards; no border |
| `--raised` | `#2c2c2e` | inset groups, tracks, inputs, capsule buttons |
| new `--selected` | `#3a3a3c` | the chosen segment in a segmented control |
| `--line` | `rgba(120,120,128,.28)` | hairlines only |
| `--ink` | `#f5f5f7` | 15.6 : 1 on surface |
| `--muted` | `#a8a8b0` | 7.2 : 1; every secondary text |
| `--taken` | `#6c6c74` | 3.3 : 1: **never text**, only bars and outlines |
| `--mine` | `#30d158` | 8.4 : 1 |
| `--mine-soft` | `rgba(48,209,88,.16)` | |
| `--on-mine` | `#00210b` | |
| `--cool` | `#64d2ff` | stat marks, odds rings; 9.9 : 1 |
| new `--cool-strong` / `--cool-mid` | `rgba(100,210,255,.24)` / `.10` | stat capsules; ink on the strong one 9.4 : 1 |
| `--score` | none | Midnight has no purple: the Score bar is `--taken`, the recommended row's is `--mine` |
| `--flag` / `--flag-soft` | `#ff9f0a` / `rgba(255,159,10,.18)` | 8.3 : 1 |
| `--danger` / `--danger-soft` | `#ff6b61` / `rgba(255,69,58,.2)` | 6.1 : 1 |
| `--focus` | `#0a84ff` | |
| `--tag-planner` / `--tag-adp` | not drawn | `#64d2ff` is now the stat colour, so the planner tag must move off cyan. Propose values; I will measure them, colour-blind simulation included |

**Shapes.** Cards: radius 20, padding 16px 18px, no border, 14 px between cards, 16 px page padding. Inset
groups radius 14, segmented controls radius 10 (selected segment `--selected` with `0 1px 3px rgba(0,0,0,.4)`),
capsule buttons radius 999, stat capsules radius 7.

**Type.** Body 15/1.4, letter-spacing -0.003em. Section titles 19/700, -0.018em. Small capital labels
11.5/650, uppercase, letter-spacing .07em, `font-stretch: 112%`, `--muted`.

## 2. Step 2: the two kinds of table

**Player table.** 15 px / 500, names 600, meta 13 px / 450 `--muted` with " · " separators. Headers 11/650
uppercase, .045em, `--muted`. Rows 34 px with a hairline. Stat cells: the number in a capsule (`padding: 2px 4px`,
cell `padding: 0 1px`), by the category score the page already has: at least 80 `--cool-strong` and 700, 60 to 79
`--cool-mid` and 600, under 25 `--muted` and 450, the rest plain. No fill on any other cell. Score: bold number,
last season 12.5 px `--muted`, a 3 px bar 4 px above the row line (6 px insets), width by the existing
`scoreBarShare`. Recommended row: `--mine-soft` background, name in `--mine`, a "Pick" capsule. Odds the page marks as
unlikely to last: `--flag`, 650.

**Fit, measured in the drawing at 2436:** 1043 px in 1043, the Player column 341 px wide; one long row ("Kyrie
Irving" with two badges) ends in an ellipsis. **Rows visible: about 32 where 38 show today.** That cost is the
user's to accept; tell them the measured number on their window.

**14-team tables.** 14.5 px at `font-stretch: 80%` (12 px today), headers 10.5 px at 86%, rows 30 px, capsules
`padding: 2px 1px`, radius 5, team names 500 at 76%. My row: `--mine-soft`, ends rounded 10, name `--mine` 700. In
the drawing every name fits at 540 px (team column 149 px). **The "n" column:** the drawing drops it from both
tables, with "Every team completed to 8 players by the same planner." under Projected. In **So far** it varies
(1 or 2: who is still waiting), so keep it there. That is my correction to my own drawing.

## 3. Step 3: the left column

**Recommendation card.** A "Your pick · 27" capsule (`--mine-soft`, `--mine`, 13/650, 7 px dot). Name 40/800,
-0.035em, line-height .98 (two lines in 400 px is fine); meta 15 `--muted`. The Score on the right: 40/300,
-0.04em, a "Score" label under it. **Nine category bars:** 9 columns, gap 5; value 12/600 `--muted` (strong:
`--cool`, 750); track 44 px high, `--raised`, radius 7; fill height = max(8, category score)%, strong `--cool`,
60 to 79 a 55% mix of `--cool` and `--taken`, others `--taken`; label 10/650. Draft button full width, `--mine`,
16/650, padding 12, radius 14. Alternatives as an inset group: name 600, meta 13 `--muted`, hairlines, "Same score"
in `--mine` or "−0.4" in `--muted`. The drawing drops the "Then …" line, because the plan card says the same.

**Plan card.** Rows `34px | 1fr | auto | 74px`, 5 px padding; pick number in a 34 px tile, radius 11 (the pick on
the clock: `--mine`); a 2 px `--line` joins the tiles. Odds: the % and a 24 px SVG ring (r 15, stroke 4.2, round
caps, `pathLength=100`), `--cool`; unlikely odds in `--flag`, the same rule as the table.

**Standing card.** Three tiles first (`--raised`, radius 14, numeral 26/750): Winning in `--mine`, Close in ink,
Behind in `--flag`. Then nine rows: label, a 7 px track, rank. Fill `--mine`, `--muted` or `--flag` by the page's
own 0.65 / 0.35 rule.

**Height, measured:** recommendation 509, plan 462, standing 351, so **1,351 px with gaps**. The page does not scroll.
Measure it in the user's window; if it does not fit, shorten the alternatives or the standing rows first, and tell
me what you cut.

## 4. Step 4: top bar, roster, log

Top bar: the Real/Mock switch as a segmented control; "Pick 27" 22/750 with "Round 2 · you're on the clock" 13.5
`--muted`; the snake as 25 px circles (done: `--raised` with `--muted` text, mine: `--mine` plus a 3 px
`--mine-soft` ring, next: 1.5 px outline); the other buttons as capsules. Roster: slot chips 40 x 28, radius 9 (filled
`--mine`, open a 1.5 px outline and "Open" in `--muted`). Log: hairline rows, pick number 13/550 `--muted`, name 550,
" · " meta.

## 5. What I will check at each step

Tests and flake8; the token-equality test; text against `--taken` (none allowed); WCAG and APCA of every pair,
colour-blind distances for the role colours; fit and rows visible at 2436 and at the user's window once it is known;
focus states; every state (empty draft, mid-draft, pick on the clock, a notice, an error).
