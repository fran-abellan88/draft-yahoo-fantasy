# M1 to M4 report

From the builder, 2026-10-02. For the reviewer. Commits up to `8a4e0f4` plus this one are not pushed.

Approved by the user: M1 to M4, then the layout. I cleaned up as you asked: the trial servers are stopped, the browser copies under 127.0.0.1:8001 and :8002 are cleared (nothing under localhost:8001), and the real `saved_draft.json` (rule "window", no picks, left by my own J6 check) is deleted.

Suite: **396 passed**, flake8 clean, with Node (skipped: 0).

| Finding | What it does now |
|---|---|
| M1 | `loadServerDraft` throws on a failed read; `init` shows a sticky "Can't read the saved draft" message and stops, like a failed pool read |
| M2 | `writeSync(!serverSaveAgain)` after every successful save, so `basedOn` is always the version just confirmed |
| M3 | A save that empties a draft with picks copies the old file to `saved_draft.previous-v<N>.json`, one per version; a test does Reset then Undo and keeps both |
| M4 | When the file wins over a browser copy the server never confirmed, the copy goes to `draft-assistant-unconfirmed` and a notice with a Dismiss button says how many picks it had |

Checked in Chrome (trial instance on 8003, own file): file at 4 picks, a browser copy of 3 based on an older version and unconfirmed: reload shows the file's 4 picks, the notice, the copy kept (3 picks), Dismiss hides it. M1's failure path (pool reads, draft read fails) was not exercised in a browser; it is covered by a code-shape test only.

Next: the layout step, from your section 3 for a 2500 x 1476 window.
