# What to do when a B run errors out

Fixed before any run. These rules decide the response, so nobody improvises mid-run.
The runner (`bench/runner.py`) already does the first column. Rerunning `run_b.py` with the same DB path resumes: finished jobs are kept, duplicates are ignored.

| What happened | What the runner does | What I do | Never |
|---|---|---|---|
| 503, timeout, network error | Retries, then cools the lane down (3 fails in a row) and buffers the job | Rerun later. If still failing after 2 reruns, pause that lane and tell Janak (checkpoint 4) | Switch to another lane for a producer job |
| 429 or daily cap reached | Buffers the job until tomorrow | Resume tomorrow | Raise the cap or use a paid lane |
| 401 or 403 (dead or blocked key) | Marks the lane dead for this run | Check `.env`, re-probe with `smoke.py`. 403 code 1010 means a client-signature block, not a dead key | Print or paste a key |
| Served model differs from requested | Logs a mismatch, does not score the row, re-queues it | Count mismatches per lane in the table. More than 10% of a lane's rows: stop that lane and report | Score a mismatched row |
| Job failed after 6 attempts | Marks it `failed` | Report the count. Rerun failed cells next evening | Drop the cell quietly or fill it with other data |
| Empty or truncated reply | Stored as-is | Scorer returns `unclear`. Report the unclear count per cell | Retry until the answer looks right |
| Scorer says `unclear` often | Nothing | If over 20% of a cell is unclear, stop and read 5 replies by hand before changing the scorer | Change the scorer after seeing results without logging the change |
| Script crashes (Python error) | Nothing | Read the traceback, fix the cause, rerun. Max 2 repair rounds, then stop and report | Delete the DB to "start fresh" |
| Results look wrong or too good | Nothing | Re-read 3 raw replies against the scorer's verdict | Publish before that check |

## Hard stops (report to Janak, do not continue)
- Any lane would need a paid model.
- A lane stays dead after 2 reruns.
- More than 10% mismatches on one lane.
- Same error twice after a fix.

## Always
- Keep the DB. Never delete a results row. Corrections go in a new row or a note.
- Report faithfully: failed, buffered and mismatched counts go in the table, not only the good rows.
- Any change to prompts or scorer after the pre-registration commit gets its own commit and a line in the write-up.
