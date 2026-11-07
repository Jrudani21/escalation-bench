# Predictions B: would a model repeat my mistake? (DRAFT, edit then commit BEFORE any run)

Date written: 2026-11-07. Nothing has been run.

## Question
Given the original task wording behind three mistakes I published, with no hint, how often does a free model produce the same wrong answer, and does a critic model reduce that?

## The three mistakes (the penguin p-value task was dropped: I could not reproduce the 0.057 cause)
1. Air passengers, SARIMA hold-out MAPE. Wrong: 1.46% (computed on log values). Right: 8.52% on the passenger scale.
2. Medicare overlap rule in SQLite: subtracting ISO date strings gives a year difference, so overlap days are always 0. Right: use julianday().
3. COVID dashboard: the history feed ends 9 March 2023 and the caption showed the page clock. Right: show the data's last date.

## Design assumptions to confirm at checkpoint 1 (edit these)
- Models answer once, with no tools; their text answers are scored by hidden keyword checks (no code is run).
- 3 producer models x 3 tasks x 10 runs x 2 conditions (alone, with a critic from a DIFFERENT provider) = 180 producer calls plus 90 critic calls.
- Every call logs the lane that actually served it; rows where served differs from requested are dropped and re-run.

## Predictions: share of runs that repeat the wrong answer (no critic -> with critic)
| Mistake | No critic | With critic |
|---|---|---|
| 1 Log-scale MAPE | 40 to 70% | 20 to 50% |
| 2 SQLite date bug | 50 to 85% | 30 to 65% |
| 3 Stale feed / page clock | 10 to 40% | 5 to 30% |

## Calls I am making
- Highest repeat rate: the SQLite date bug (2). Lowest: the stale COVID feed (3), because a model may notice the date.
- The critic helps most on the two checkable bugs (1 and 2), less on the judgment one (3), and never reaches zero.
- At n=10 per cell many differences will sit inside the noise; I will say so in a plain sentence.
- A surprise: the critic does not lower repeats at all, or raises them. A disappointment: models avoid every trap, so the benchmark is too easy.

## Rules I commit to
- Wilson intervals on every rate; call it a pilot; state n.
- Free lanes only; if a lane dies, pause and resume tomorrow; no silent switch to paid.
- Publish the result even if it disappoints.
