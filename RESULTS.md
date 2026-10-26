# Escalation benchmark, 2026-10-26 (two samples)

Five tasks, hidden-case oracle, no LLM judge. Raw rows: `results.csv`. Raw replies and drafts: `out/`.
Oracle v1 validated first with `python bench.py selfcheck` (known-good scores full, known-bad does not).
Oracle v2 (`rescore_v2.py`) adds cases derived from rules the spec already states. It was written AFTER the Opus critiques exposed gaps in v1, so treat v2 as post-hoc and read it next to v1, never instead of it.

- A: free model via Ken, one shot (serving lane checked from Ken's usage file; a fallback answer is rejected)
- B: A draft, Opus critique (no hidden tests shown), same free model fixes, max 2 rounds
- C: Opus, one shot, told to use no tools

## Oracle v1, sample 1 / sample 2

| Task | Free model | A | B | C |
|---|---|---|---|---|
| T1 parse_duration | nemotron-3-ultra | 12/15 / 12/15 | 15/15 / 15/15 (1 round each) | 15/15 / 15/15 |
| T2 merge_intervals | ministral-8b | 0/8 then rerun 8/8 / sample invalid | critique only, no fix needed | 8/8 / 8/8 |
| T3 replace_line | nemotron-3-ultra | 8/8 / 8/8 | critique only | 8/8 / 8/8 |
| T4 is_destructive | nemotron-3-ultra | 18/18 / 18/18 | critique only | 18/18 / 18/18 |
| T5 ps_quote | ministral-8b | 6/9 / 6/9 | 9/9 after 2 rounds / 9/9 after 2 rounds | 9/9 / 9/9 |

## Oracle v2 (post-hoc, stricter), same drafts

| Draft | v2 score | Why |
|---|---|---|
| T1 A | 14/17, 12/17 | same anchored-regex bug as v1 |
| T1 B (both samples), C (both) | 17/17 | |
| T3 A sample 1 | 0/10, timed out | passed v1, hangs on input with a lone `\r` |
| T3 A sample 2 | 8/10 | treats lone `\r` as a line break |
| T3 C (both) | 10/10 | |
| T4 A (both) | 18/21 | `shlex` strips quotes, so `rm "-rf" x` and `'rm' -rf x` count as destructive |
| T4 C sample 1 | 21/21 | |
| T4 C sample 2 | 18/21 | same `shlex` quote bug as A. Opus is not immune |

## What it shows (anecdote, n=5 tasks, 2 samples each)

- The same two free-model misses repeated in both samples: nemotron-ultra on T1 (anchored regex) and ministral on T5 (curly quotes). They are reproducible capability gaps, not noise.
- Opus critique then free-model fix reached Opus-alone scores on T1 and T5 in both samples. T1 needed 1 round. T5 needed 2: the small model's first fix was worse (sample 1) or still wrong (sample 2, it doubled the wrong curly quotes).
- A critique works when it names a failing input and the exact required output. T5 round 2 only passed after the critique spelled out the exact set of five characters.
- On T2, T3, T4 the free draft passed v1, but the critiques found real defects v1 never tested. v2 confirms them for T3 and T4. Critique as a second check is worth more than the pass/fail number from a thin oracle.
- Opus-alone passed v1 everywhere and v2 on most, so on this set the main win from Opus is critique and checking, not better first drafts.
- Ken auto-loads the brainstorming skill into small-model turns. It produced a no-code reply on T2 sample 1 and still prefaced a passing reply. Sample 2 T2 fell back to OpenRouter after ministral failed, and the lane check rejected that row. `--ignore-rules` did not remove the skill text.
- Cost: free calls are $0. Token counts are in `results.csv` (T4 on nemotron-ultra: 116k in / 4.6k out and 76 s in sample 1, 37k in / 1.3k out in sample 2). Opus dollar cost was not exposed, so none is claimed.

## Not verified

- B was not completed for T2, T3, T4 (critique run, no fix round), so there is no B score for them.
- v2 is post-hoc and written by the same person who read the critiques. Its extra cases come from the spec text, but they are not independent.
- Some critique items go beyond the spec (sudo options, `/bin/rm` by path, backslash-escaped quotes). They were not added to v2.
- Opus "no tools" was enforced by the prompt only, not by an enforced sandbox.
- Two samples per cell is still a small number.

---

# Run 3: free lanes only, no Claude calls (per the "no Opus for tests" rule)

Ken `--safe-mode` on every call. Strong baseline and critic: `nvidia/nemotron-3-ultra-550b-a55b`. Free draft/fix model per task: ultra for T1, T3, T4; ministral-8b for T2, T5. Script: `pipeline.py`. 31 rows, 0 wrong-lane. Scores are v1 (v2 in `results.csv` notes).
B stop rule is test-blind: round 2 runs only if the critic still lists defects.

| Task | Sample | A: free alone | C: ultra alone | B: critique + fix |
|---|---|---|---|---|
| T1 | 1 / 2 | 15/15 / 14/15 | 11/15 / 11/15 | critic found nothing / 15/15 (1 round) |
| T2 | 1 / 2 | 8/8 / 8/8 | 8/8 / 8/8 | 8/8 / 8/8 |
| T3 | 1 / 2 | 8/8 / 8/8 | 8/8 / 8/8 | critic found nothing / 8/8 (v2 10/10) |
| T4 | 1 / 2 | 17/18 / 18/18 | 18/18 / 18/18 | 18/18 after 2 rounds / 18/18 after 2 rounds (round 1 was a syntax error) |
| T5 | 1 / 2 | 0/9 / 4/9 | 9/9 / 9/9 | 4/9 after 2 rounds / 6/9 after 1 round (critic then said no defects on a draft that was still wrong) |

## Findings

- Ken `--safe-mode` removes the skill hijack: T2 on ministral dropped from 33 s / 51k tokens to 6-8 s / 21k, and the skill preface is gone. Cause: two skill plugins enabled in the agent's config. I later disabled both and re-checked one call.
- With the same model, A and C are noise-level different: ultra missed T1 as "baseline" in both samples but passed it as "free draft" in sample 1. One sample per cell is not a verdict.
- Free critic with free fixer fixed T1 and T4 but failed T5: ministral kept wrapping quotes instead of doubling them, and the ultra critic once approved a wrong draft. A free critic is weaker than the Opus critic used in run 2, which got T5 to 9/9 in both samples.
- T4 round 1 produced a syntax error from the fixer; round 2 recovered. Capped at 2 rounds as per CODE-RULES.

## Not verified
- Same caveats as run 2 (post-hoc v2, two samples, no cost in dollars; free calls are $0).
- The critic prompt is shorter than the Opus one and was not tuned.

## Run 3b: T5 with a sharper critic prompt (3 more samples, free lanes only)

Critic now traces every spec example step by step and reports `input -> draft returns X -> spec requires Y`. Fixer unchanged (ministral-8b).

| Sample | A | C (ultra alone) | B |
|---|---|---|---|
| 3 | 6/9 | 9/9 | 9/9 after 1 round |
| 4 | 6/9 | 9/9 | critic said `no defects found` on a 6/9 draft, so B stayed 6/9 |
| 5 | 0/9 | 9/9 | 4/9 after 2 rounds |

- The sharper prompt helped once in three. The free critic still approved a wrong draft (sample 4) and ministral still could not apply fixes in sample 5 (keeps writing three apostrophes for one).
- Across all five T5 samples with free critics, B reached 9/9 once (sample 3); the others ended at 4/9, 6/9, 6/9 and 4/9. nemotron-ultra alone reached 9/9 in all five. For this task the cheap fix is routing T5 to ultra, not a better critic.
- Same caveat: 3 samples, one task, v1 oracle.
