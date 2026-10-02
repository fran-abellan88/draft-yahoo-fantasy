# Step 3c report, and the K1 to K4 fixes

From the builder, 2026-10-02. For the reviewer. Everything up to the J1 to J6 commits is pushed; these commits are not.

Approved by the user: K1 to K4, then 3c. **Not started: layout code (step 6).** The user's half screen is about 2500 x 1476 and the window size is adjustable.

Suite: **388 passed**, flake8 clean, with Node on the path (skipped: 0).

| Commit | Finding | What it does now |
|---|---|---|
| `fa926b7` | K1-K4 | Only table rows (and Enter on one match) count as choosing; the hero Draft button logs the pick on the clock and ends the choosing (K2). The confirmation is in the choosing note, scrolled into view, and row clicks are ignored while it waits (K1). Pick not in the list is disabled while choosing (K3). Choosing is checked before `draft()` can refuse on a complete draft (K4) |
| (this step) | F3 | `parse_request` is the only caller of the host/origin check, so every method, supported or not, is gated; a test counts the call sites. PUT, DELETE, PATCH, OPTIONS, HEAD, TRACE from another host: 403; from the page's own address the unsupported ones: 501 |
| `588701e` | A4 server | `saved_draft.py`: one fixed file, atomic write (temp file in the same folder, fsync, rename), 200 KB limit, known keys only, at most 200 picks, a version that rises on every save; a save names the version it is based on and a stale one is a 409. An unreadable file is reported and renamed to `.unreadable.json` on the next save, never overwritten. `GET/POST /api/draft`, gated like the rest |
| last | A4 page | The page loads the file first (browser storage only if the server has none, and then pushes it up), saves after every change one request at a time, 409 and refusal messages are sticky. A saved draft the page cannot load (unknown player, unseen on my pick) is kept: nothing is saved until Reset |

Checked in Chrome: draft on the file after picks; opened at `localhost:8001` (another origin, empty browser storage) and the 30 picks were all there with "Undo pick 30: Chet Holmgren"; a save with an old version is refused with the sticky banner; a file with an unknown player gives the sticky "could not be loaded" banner, a click on a row did not change the file.

Decisions to challenge:
1. The server stores what the page sends and checks only shape and size; picks are validated when analysed, as before.
2. History is saved with the draft (as you asked). Settings too.
3. Browser storage is still written as a backup but only read when the server has no draft or cannot be reached; if the server has an older draft than the browser, the server wins.
4. Not exercised in a browser: a full disk, two windows editing at the same time (only the 409 path via a forced old version).

Not verified: light mode, Safari, Firefox, other widths.
