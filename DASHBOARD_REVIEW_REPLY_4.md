# Reviewer's reply on the revised wireframe

From the reviewer, 2026-10-01. Reviewed `DASHBOARD_WIREFRAME.md` at `80daa88`. Document only; I ran nothing and
changed nothing.

**Verdict: W1 to W6 are all addressed. I would let you build the shell from this drawing, once the user approves it,
with the five points below folded in at step 6. None of them needs another drawing, and none touches 3a-2.**

## Your three questions

**1. Is 900 px a sensible floor, and are the thresholds sound?**

- **Height: design at 900, but say what happens down to 800.** A browser window on a 1080-line desktop loses the
  menu bar, the tab and address bars, possibly a bookmarks bar and a dock. That lands between roughly 830 and 950, so
  900 is the middle of the range, not the floor. Your give-way order already covers it. By my sum, with about 60 px of
  gaps that the budget table leaves out, the tab panel gets about 420 px waiting and 310 on the clock at 900, and at
  800 the plan has to fold to four steps on the clock. That is acceptable. Write the 800 case into the file so the
  fold is built as a rule and not discovered. On the user's monitor the real height is likely well above this; do not
  spend more on it until `innerHeight` is reported.
- **Width: the thresholds are sound as arithmetic, but they rest on a number nobody has measured.** The table's
  minimum of 860 px is today's table (895 px, measured in the review) minus a little. The new table has one line per
  player (a longer name cell), a "Rank vs ADP" column, and tints. It may well need 1,000 px. So treat all four
  thresholds as provisional, as you already do for 2240. See point 1 below.

**2. Is one line of standing enough on the 960 px on-the-clock strip?** Yes, if the line carries three groups and not
one: "Winning: FG%, AST. Close: 3PTM, ST, BLK. Behind: REB." "Contested" alone does not tell the user which
categories are safe and which are lost, and all nine fit on one line at 960 px.

**3. Anything I would still not let you build from?** No. Five points to fold in:

## Points to fold in at step 6

1. **Build and measure the table before fixing the grid's minimum sizes.** Make C2 and C3 first, read the table's
   natural width, then set the thresholds from it. Also state two rules that the drawing only applies at 960: the
   first two columns stay fixed and the rest scroll sideways **whenever** the table is narrower than its natural
   width, at any window width; and which columns give way first (I suggest XRank and GP, since neither feeds a
   decision the score does not already carry).

2. **The same decision gap exists in the two-column band, and 1280 px is a likely width.** Between 1240 and 1580 px
   MY TEAM and STANDING share one tab panel, so on the clock the user sees one of them. Put the one-line standing
   from question 2 in the on-the-clock REC block at every width where STANDING has no space of its own, not only at
   960. Let the tab panel remember the last tab chosen.

3. **The 14-team panel does not fit 320 px as a grid of totals.** Nine numeric columns and a team label need about
   370 to 400 px. Either give this panel a larger minimum, or decide now that its cells show ranks (1 to 14) with the
   totals on hover. Ranks are also what the user compares.

4. **The error banner needs a place in the shell.** Today it is fixed at the top of the window, which in this layout
   is the top bar: it would cover the clock, "I am behind" and the settings button exactly when something has gone
   wrong. Give it a row under the top bar.

5. **These are breakpoints, so test their edges.** The file says "a fluid grid, not fixed breakpoints" and then lists
   four thresholds. That is fine, and derived breakpoints are the right approach, but the defect in the review (B2)
   lived on an edge: 1280 against 1281 px. When building, check each threshold one pixel either side in a real
   window: no horizontal overflow of the page, no column cut off, no panel missing from both its space and its tab.
   A simple way to make that hold by construction: keep every panel a child of the grid at all widths, and let the
   "tabbed" ones share one grid area with only the selected one shown. Nothing is moved in the document when the width
   changes.

## Small notes

- **"I am behind"** should refuse a pick number that is not ahead of the log, and say why.
- **"Mark as gone"** buttons should exist only while unseen picks are outstanding, and a click on the button must
  not also log the row as the next pick.
- **On your G1 caveat:** counting a seen pick as "contributes nothing" is not conservative, it is exact. A seen pick
  that was someone else is a survival of 100% for our player at that pick, which is what a factor of 1 says. The
  approximation in the rule is elsewhere: it treats players independently, which is why the expected number gone does
  not sum to the number of unseen picks. Your plan to measure that and then decide on normalising is the right one.
- **Skips made visible** with `-rs` in `pytest.ini`: agreed.

## For the user

Approval of the wireframe, approval of step 3a-2, and the three questions at the end of the wireframe file. My views
on those are unchanged from my last reply: tabs at 960 px, and the log as a tab with the last-pick line always shown.
