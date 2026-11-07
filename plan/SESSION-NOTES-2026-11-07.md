# Session notes, 2026-11-07 (benchmark B setup)

Read first in a fresh session, after `E:\Local\projects\_shared\handoff-2026-11-07\HANDOFF.md`.

## Decisions (Janak)
- Runner lives inside escalation-bench (`bench/`).
- Project B prompts are hand-typed, no code execution.
- Use the keys in `E:\Local\ken-desktop\.env` (GROQ_API_KEY, NVIDIA_API_KEY).
- Penguin task (mistake 1) dropped: the 0.057 result could not be reproduced. Interaction p is 0.000197 with Type I, Type III or sequential sums of squares, either term order, in R 4.6.2 `datasets::penguins` (n=333). Also tried: sex as 0/1 (same p), log mass (0.006), missing-sex as a level (0.0003), year block (0.0002). None gave 0.057. Add it back only if the original cause is found.

## Done
- Branch `feat/mistake-repeat-bench` in escalation-bench.
- Copied `bench/` (runner, adapters, smoke, tests) from the handoff folder. 20 tests pass.
- Copied `plan/predictions-A.md`, `predictions-B.md`, `lane_health_B.md`.
- Drafted `bench/tasks_B.json` (tasks 2_mape, 3_sqlite, 4_covid) and `bench/score_B.py` (keyword checks, self-test passes).
- Edited `plan/predictions-B.md` to 3 mistakes: 3 models x 3 tasks x 10 runs x 2 conditions = 180 producer + 90 critic calls.

## Not done
- Nothing committed or pushed.
- Janak has not reviewed predictions or prompts. Commit them locally (no push) BEFORE any producer call: the commit time is the pre-registration.
- No lane probes, no runs. Re-probe lanes first (handoff says probe is dated).
- Not read yet: `llm-catalogue.md` routing card, `CHEAT-SHEET-code-and-llm.md`.
- Project A untouched. Gated by security-audit of the canary harness, sandbox checkpoint, disclosure note.
- Scorers are keyword rules and can be fooled (e.g. a comment mentioning `exp`). Review before the pilot.
- predictions-B.md numbering is 1, 2, 3 but task keys are 2_mape, 3_sqlite, 4_covid. Cosmetic. Heading also reads awkwardly.

## Next action
Edit `plan/predictions-B.md` and `bench/tasks_B.json`, then commit locally with the Co-Authored-By trailer.
