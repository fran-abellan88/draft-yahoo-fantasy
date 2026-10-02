# UI colour and legibility: brief for the joint review

From the builder, 2026-10-02. The user (who has authorised talking to the reviewer for this, and only for this) says:
the current UI is fine but not high quality; light mode is "very white" and hurts the eyes, so they use dark mode;
dark mode "does not feel well, it is hard to read". They use Chrome only. Goal: the best result we can reach together.
The user approves in the end.

## What I measured on the current tokens (WCAG ratios)

| | Light | Dark |
|---|---|---|
| ink on surface | 16.35 | 13.66 |
| muted on surface | 5.74 | 6.64 |
| page background vs panel surface | 1.14 | 1.11 |
| row line vs surface | 1.35 | 1.38 |
| ink on the strongest stat tint (cool 28%) | 11.0 | 8.0 |
| ink on the Score tint (46%) | 8.2 | 6.0 |

So the numbers are not the problem; perception is. My reading:

1. **Panels do not separate.** Background and surface differ by 1.1:1, so the page reads as one slab and the eye has no
   structure to follow.
2. **Glare in light mode:** `#ffffff` surfaces on `#edf0f3`. **Halation in dark mode:** near-white text (13.7:1) on
   saturated navy, thin 12 to 13 px.
3. **Too much of the page is muted 12 to 13 px grey text:** the log rows, the player meta line, notes, labels. Important
   information is styled like fine print.
4. **One hue does too many jobs:** the blue (`--cool`) is odds, stat tints, ranks, bars, ticked controls and now Standing
   bars, so nothing stands out.
5. **Type scale:** body 15 px, table 14 px, many 12 and 13 px; the hero name 36 px against everything else small.

## Colour roles that must stay distinguishable (also for colour-blind eyes)

mine (green) = only my team and the Draft button; stat/odds tint; **Score map** (own hue); log tags **planner**, **ADP**,
**both** (split) and **differs**; warning (amber); danger (red). The Score map and the tags were just added with provisional
values (`--score`, `--tag-planner`, `--tag-adp`).

## My first proposal (to be attacked)

Direction: calm, neutral, a bit warmer; separate panels by lightness steps, not by borders; a type scale where nothing
that matters is below 13 px; muted only for true labels.

Dark (charcoal, not navy): paper `#121418`, surface `#1b1e24`, raised `#232730`, line `#363c48`, ink `#e8e6e1`
(soft off-white), muted `#aab1bd`, cool `#7db4ff`, mine `#5fd3a4`, score `#b69cff`, planner `#4fd0d8`, adp `#f08ab8`,
flag `#f2b05e`, danger `#ff8f87`.
Light (warm paper, no pure white): paper `#d9d6ce`, surface `#ece9e2`, raised `#f5f3ee`, line `#b4afa3`, ink `#1c2330`,
muted `#464f5c`, with the accents darkened to keep 4.5:1 on surface.
Type: body 16, table 14.5, notes and labels 13.5 (never below 13), log rows in ink not muted, hero unchanged.
Tints: stat tint max 24%, Score map 8 to 40% in its own hue.

## What I ask the reviewer

1. Independently measure and critique: contrast of every text/background pair in both themes (including text on tints),
   panel separation, and a colour-vision-deficiency simulation (protanopia, deuteranopia, tritanopia) of the roles above.
2. Say what in my proposal is wrong, and propose concrete token values and type sizes where you can do better. Look at
   the real page in Chrome (port of your choice, scratch files), at several states: empty draft, mid-draft, a pick
   on the clock, the Standing and the 14 teams.
3. Say what a fantasy drafter under a one-minute clock needs to see first, and whether the layout hierarchy (not only the
   colours) helps or hurts that.

Reply in `DASHBOARD_UI_REVIEW.md` (new file) and message me; I will fold the agreed result into `style.css` and the
colour tokens, check both themes in Chrome, and send it back for a second look before the user sees it.
