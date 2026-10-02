# L1 to L4 report

From the builder, 2026-10-02. For the reviewer. Commits up to `ae35205` (and your reply 8) are pushed; `0729210` and this report are not.

Approved by the user: L1 to L4 and the push. **Not started: layout code (step 6).** The user will put the dashboard on the right half and Yahoo on the left (their choice, I recommended it: the seam is where the eyes rest).

Suite: **393 passed**, flake8 clean, with Node on the path (skipped: 0).

| Finding | What it does now |
|---|---|
| L1 | The browser copy has a sync record `{basedOn, confirmed}` written beside it: `confirmed:false` on every local save, `true` once the server has that exact copy. `chooseSource` (in `logic.js`, Node tests) picks the browser copy only when it is unconfirmed and `basedOn` equals the file's current version (or the file has no draft), then pushes it up |
| L2 | `run_dashboard.py --draft-file PATH`; the startup line prints the file in use; README says instances sharing a file share a draft. I used it for the browser check below (port 8002, a file in the scratchpad) |
| L3 | A save that would empty a draft with picks first copies the old file to `saved_draft.previous.json` (copy, then the atomic write). Not made for ordinary saves |
| L4 | `showError` ignores an ordinary message while a sticky one is up; the sticky one stays until Reset or a reload |

Checked in Chrome on the trial instance: 3 picks on the file; I made saves fail, clicked two rows (page 5, file 3, sync `{basedOn: 3, confirmed: false}`), let requests through and reloaded: 5 picks shown and the file at 5 with `{basedOn: 4, confirmed: true}`, no banner.

A thing I did not fix: if the server cannot be reached when the page loads, the page starts from the browser copy with file version 0, and its first save then gets a 409 ("changed in another window") if the file already has a draft. Safe, but the wording is wrong for that case. Say if you want it handled.

Not verified: light mode, Safari, Firefox, other widths.
