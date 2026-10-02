# UI colour and legibility: the reviewer's reply to DASHBOARD_UI_BRIEF.md

From the reviewer, 2026-10-02. Reviewed at `628880e` on `feat/ui-polish`. No code was changed and nothing was
committed by me. My copy ran on port 8765 with scratch files; trial styles were injected into my own browser tab
only and removed afterwards.

**Verdict: your diagnosis is right on three of five points, but the proposal does not fix the two that matter most.
Dark mode is hard to read because its grey text is far weaker than the WCAG ratio says, and your dark palette keeps
the same panel step it calls the problem. I agree with your light neutrals. Below: my measurements, token values,
what fits the columns, and what a drafter on the clock needs.** The user gives the approvals, not me.

## 1. How I measured

- **Tokens:** WCAG 2 ratio and APCA lightness contrast (Lc) for every text and background pair, tints included.
  APCA is a perceptual model, not a standard. Its usual guidance, from memory: Lc 90 preferred and 75 the floor
  for body text, 60 for other content text, 45 for large headings.
- **The real page:** Chrome, the mock draft at my pick 27, viewport 2436 x 1408, both themes. A script walked every
  visible text node and took its size, weight, colour and the background actually behind it.
- **Colour vision:** the Machado, Oliveira and Fernandes (2009) matrices at full severity, distances in OKLab
  x 100. A model, not a person; nobody with a deficiency has looked.
- **Looking:** zoomed screenshots of both themes, then of my proposed tokens injected into the page.

## 2. What I found

### F1. Dark mode: WCAG says the grey text is fine, APCA says it is weak

| Text on surface | WCAG, light | Lc, light | WCAG, dark | Lc, dark |
|---|---|---|---|---|
| ink | 16.35 | 103 | 13.66 | 93 |
| muted | 5.74 | 79 | 6.64 | **52** |
| cool (blue) | 5.42 | 77 | 6.74 | **53** |
| danger | 6.57 | 81 | 7.10 | **55** |
| muted on the strongest stat tint | 3.86 | 54 | 3.86 | **42** |

By WCAG the dark grey is better than the light one. By APCA it is 27 points worse. On the page, at pick 27:

| Share of the characters on screen | Light | Dark |
|---|---|---|
| Under 14 px | 62% | 62% |
| At 12 px | 35% | 35% |
| Under Lc 60 | 0% | **41%** |
| Under 14 px and under Lc 60 | 0% | **39%** |
| Under 4.5:1 by WCAG | 0% | 0% |

Four characters in ten in dark mode are small and weak at once: the notes, the player's team and positions, the
log, the ranks, the table headers. That is "hard to read". The ink is not the problem (Lc 93).

### F2. Light mode is legible and almost all white

Nothing in light mode is under Lc 60. The complaint is light, not contrast: a page that is three quarters surface
and one quarter background has 97% of the luminance of pure white.

### F3. The page reads as one slab for two reasons, not one

- The step from background to panel is 5 L* in both themes (1.14 and 1.11), as you measured.
- **Four of the seven panels have no surface at all.** Your roster, the log, Standing and the 14 teams sit straight
  on the background; the hero, the plan and the table are boxes. So the eye gets boxes in two columns and loose
  text in two.

### F4. The table carries three heat maps side by side

- **Score** in purple, **odds** in blue, **nine stat columns** in blue. At my pick most odds are 90 to 100%, so
  that column is one solid blue block that says nothing.
- **The emphasis of the odds is the wrong way round.** The strongest colour goes to the players who will certainly
  last. The ones that matter on the clock are those who will not.
- **"differs" is in the warning colour** on most log rows, under a note that says a differing pick is not a
  mistake.
- **An Edit button on every log row** (26 at pick 27), and **seven explanatory notes** (1,144 characters, 13% of
  the text on screen) in 13 px grey.

### F5. Colour vision

Distances between the role colours (under about 8 is hard to tell apart as small coloured text):

| Pair, current dark | Normal | Protan | Deutan | Tritan |
|---|---|---|---|---|
| cool and score, as colours | 10.2 | 6.1 | **2.4** | 12.2 |
| planner and ADP tags | 24.1 | 12.8 | **4.8** | 28.5 |
| mine and danger | 26.9 | 11.4 | **4.6** | 30.0 |
| mine and planner tag | 8.9 | 8.4 | 8.0 | **2.9** |
| flag and danger (light theme) | 8.1 | 5.0 | **0.5** | 6.5 |

What it means in practice:

- **Score map and stat tints:** as filled cells they stay apart (8 to 10 in every simulation), because the Score
  fill is lighter and has its own column. Acceptable.
- **Tags:** teal and pink collapse for a deutan eye, but each tag carries its word ("planner", "ADP"). The word is
  the code; keep it, and never drop it for a dot.
- **Warning and danger in light mode** are the same colour to a deutan eye. They are told apart by their text and
  place (a "P" or "Q" circle against a sentence). Acceptable; I did not find a pair of dark reds and ambers that
  separates them.

## 3. Your proposal

**Agreed:** charcoal in place of navy; a "raised" step; warm paper with no pure white for light; nothing that
matters below 13 px; the log in ink; muted for true labels only.

**Where it falls short:**

| Your point | What the proposal does | Measured |
|---|---|---|
| Panels do not separate at 1.1:1 | Dark paper `#121418`, surface `#1b1e24` | 1.10:1, L* step 4.9: the same as today |
| Halation from near-white ink | Ink `#e8e6e1` | 13.39:1 against 13.66 today: no change. I would not change it: Lc 90 is right for 14 px |
| Too much weak grey | Muted `#aab1bd` | Lc 58, from 52. Better, still under 60 |
| Score has its own hue | Score `#b69cff`, cool `#7db4ff` | Deutan distance 0.6 as colours (2.4 today). Fills still 8.5 |
| Light accents "darkened to keep 4.5:1" | No values | With today's accents on `#ece9e2`: mine 4.35, cool 4.47, planner 3.94. Values below |
| Table 14.5 px | | At 2436 the table is 1049 px in 1044: FT% is cut by 5 px. At 15 px, by 15 px |
| Body 16 px | | Changes nothing in the table, the log or the league tables, which set their own sizes |

## 4. What I propose

### Tokens

Dark. The background goes down and the panels up, so the step is 8 L*; the grey goes up to Lc 66.

| Token | Now | Proposed | On surface |
|---|---|---|---|
| paper | `#0f1722` | `#0e1013` | L* 4.6 |
| surface | `#17212f` | `#1e2127` | L* 12.7, 1.18:1 against paper |
| raised (new) | | `#282c34` | L* 17.9: table header, inputs, league tables |
| line | `#2b3949` | `#3a3f49` | 1.53:1 |
| ink | `#e7ecf3` | `#e4e3df` | 12.56, Lc 88 |
| muted | `#9aa7b8` | `#bac0c9` | 8.81, Lc 66 (64 on raised) |
| taken | `#6c7a8c` | `#8a919c` | 5.08: bars and borders, never text |
| mine | `#3ecf9b` | `#5fd3a4` | 8.71, Lc 66 |
| cool | `#6aa9ff` | `#9cc4ff` | 9.03, Lc 67 |
| score | `#a98af2` | `#c79bff` | fill only; ink on its 40% fill Lc 71 |
| tag-planner | `#4fd0d8` | `#56d4dc` | fill only |
| tag-adp | `#f08ab8` | `#f590bd` | fill only |
| flag | `#f0a95a` | `#f2b05e` | 8.56, Lc 65 |
| danger | `#ff8a80` | `#ffa29b` | 8.37, Lc 64 |
| hover | `#263a52` | `#2c3440` | ink on it Lc 84 |

`mine-soft` `#17382d`, `flag-soft` `#3a2a14`, `danger-soft` `#3d1c1a`, `on-mine` `#06281d`.

Light. Your neutrals, with accents that hold on them. Mean luminance falls from 0.97 to 0.78 of white.

| Token | Now | Proposed | On surface |
|---|---|---|---|
| paper | `#edf0f3` | `#d9d6ce` (yours) | L* 85.7 |
| surface | `#ffffff` | `#ece9e2` (yours) | L* 92.4, 1.20:1 against paper |
| raised | | `#f5f3ee` (yours) | L* 95.9 |
| line | `#d8dee6` | `#b4afa3` (yours) | 1.80:1 |
| ink | `#142033` | `#1c2330` (yours) | 13.00, Lc 90 |
| muted | `#5b6778` | `#464f5c` (yours) | 6.84, Lc 76 |
| taken | `#8a94a3` | `#737c89` | 3.48: never text |
| mine | `#0f7b55` | `#096040` | 6.28, Lc 73; white on it 7.61 |
| cool | `#2b6cb0` | `#1f5590` | 6.27, Lc 73 |
| score | `#7c4fc9` | `#6f3fc0` | fill only; ink on its 40% fill Lc 57, bold 14 px |
| tag-planner | `#0f7f86` | `#09636a` | fill only |
| tag-adp | `#b83a76` | `#a82f69` | fill only |
| flag | `#9a4a05` | `#7d4300` | 6.48, Lc 74 |
| danger | `#b42318` | `#a81f14` | 6.03, Lc 71 |

`mine-soft` `#cfe3d6`, `flag-soft` `#f0dcb8`, `danger-soft` `#f0d3ce`, `hover` `#dcd8cf`.

A 19% cut in luminance is modest. If the user still finds light mode harsh, the monitor's brightness will do more
than any palette.

### Rules that go with the tokens

1. **Every panel is a card on `surface`.** Roster, log, Standing and 14 teams get the same box as the plan. Boxes
   inside a card (table header, league tables, inputs) use `raised`. Borders can then go or stay as hairlines.
2. **Coloured text only where it holds Lc 60:** mine, cool, flag, danger. Score and the two tag colours are fills;
   the text on a fill is ink (Lc 71 to 80 in dark, 57 to 71 in light).
3. **Stat tint to 22% at most** (ink on it Lc 79 dark, 70 light). Consider tinting only the upper half of the
   scale, so that strengths light up and the rest stays quiet.
4. **Odds without the blue fill.** Plain numbers; mark only the ones that will not last (under 50% in `flag`).
   That frees the blue from one of its jobs and turns a block into a few signals.
5. **"differs" in muted with a hairline**, not in the warning colour. Planner and ADP keep their fills and words.
6. **Edit shown on the hovered or focused log row only.**
7. **Notes behind a "?" or in the titles**, one line left where it is needed.

### Type

The columns have no slack at 2436, so sizes are chosen by what fits. Measured in my tab:

| Change | Main table at 2436 | Result |
|---|---|---|
| Today (14 px) | 1044 in 1044 | fits |
| Table 14.5 px | 1049 | FT% cut by 5 px |
| Table 15 px | 1059, 30.5 px rows | cut by 15 px; 37 rows for 38 |
| Player team and positions 12 to 13 px | 1044 | fits |
| Badges 12 to 13 px | 1056 | cut by 12 px |
| League tables 12 to 13 px, no card padding | 539 in 539 | fits |
| League tables 13 px inside a card with 14 px padding | 535 in 511 | cut by 24 px |
| League tables 12 px inside a card with 8 px padding | 523 in 523 | fits |

So:

| Text | Now | Proposed |
|---|---|---|
| Body, hero facts, plan names | 15 | 15 |
| Main table | 14 | 14; 15 only if a column goes (XRank or GP) or the cell padding drops to 6 px and the badges get shorter |
| Player team and positions | 12 muted | 13 muted. The positions decide a roster slot; they are not fine print |
| Log rows | 13 muted | 14, name in ink, team in muted 13 |
| Table headers, notes, ranks, meters, saved state, snake cells | 12 to 13 | 13 |
| Badges in the table | 12 | 12 (no room) |
| Tags in the log | 11 | 12 |
| League tables | 12 | 12, numbers in ink; the card padding at 8 px |
| Hero name | 36 | 36 |

Nothing below 12, and only badges and league numbers at 12. With the grey at Lc 66 the size matters less than it
does today.

The user's screen matters here and I do not know it. If it is a 49 inch panel at 5120 x 1440, its pixels are about
12% smaller than the usual reference and it sits further away, so 12 px there is small in the hand. Chrome's zoom
would fix the size and break the layout: at 110% the window has about 2270 CSS px and drops to three columns.

## 5. What a drafter on a one-minute clock needs first

On my pick, in this order:

1. **It is my pick, and who to take.** The hero does this well: the one large green thing on the page.
2. **Who else, if I do not like him or he is gone.** Today this is one 13 px grey sentence under the seven steps
   of the plan, 600 px below the name. It is the second thing I need and the hardest to find. Put the three or four
   alternatives in the hero, under the name, each with its score difference.
3. **Can he wait until my next pick.** The odds are in the table (57% for the recommended player in my run) and
   not in the hero. One line: "57% to last to pick 30".
4. **Does he fit a slot.** In the hero in grey, fine once the grey is readable.
5. **The button.** Good.

Between my picks, about a hundred times:

1. **Find the player Yahoo shows and click him.** Search and the table: good, and ADP order puts him near the top.
2. **See that it was logged.** "Logged pick 8 (Mallorca Red Devils): Evan Mobley" is 14 px grey. It is the
   feedback for the most frequent action on the page; give it ink.
3. **How long until my pick.** The clock line: good.

Everything else (Standing, 14 teams, the log, the predictions) is read in the gaps and is in the right columns.

What hurts the hierarchy today, by how much I think it matters:

1. The alternatives are buried (point 2 above).
2. The table's three heat maps compete with each other and with the hero.
3. Half the panels have no box.
4. Grey fine print everywhere, so nothing reads as secondary because everything does.

## 6. What I am not sure of

- **I judged from zoomed screenshots of a background tab at 2436 px.** I have not seen the page at its real size on
  the user's screen, and neither has anyone but the user.
- **My trial of the dark tokens looked clearly better to me** (panels separate, the grey is readable, the tints
  stand out on charcoal). That is one opinion from one look.
- **Charcoal against navy, warm against neutral paper, are taste.** The numbers do not choose between them.
- **The APCA guidance levels are from memory**, and APCA is not part of WCAG 2.
- **The user's monitor and window size are unknown.** Section 4's "what fits" is for 2436 px.

## 7. For the user

- Whether the alternatives should move into the recommendation box (section 5): it is a layout change, not a
  colour one.
- Whether the odds column may lose its blue fill and mark only the players who will not last.
- A look at both themes after the change, in the real window, and its `innerWidth` and `innerHeight`.
