<div align="center">

# escalation-bench

**When does a free AI model need a critic?**<br>
Five small coding tasks, hidden-test scoring, no model judging another model.

[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11-3776ab)
![Standard library only](https://img.shields.io/badge/dependencies-none-444)
![Tested on Windows 11](https://img.shields.io/badge/tested%20on-Windows%2011-0078d4)

[Case study](https://jrudani21.github.io/case-study-escalation.html) &middot; [Full results](RESULTS.md) &middot; [Raw rows](results.csv)

</div>

I route work to free model lanes first and escalate only when needed. This repo is the experiment I ran to replace a feeling with numbers. It compares three setups on the same tasks:

| setup | what it is |
|---|---|
| **A** | a free model, one shot |
| **B** | the free model's draft is reviewed by a critic that sees only the spec and the draft (never the tests); the free model applies the fix; at most two rounds |
| **C** | a strong model, one shot |

> **This is not a leaderboard.** There are five tasks and one to five samples per cell, and the same model flipped between pass and fail across samples. Read it as a worked example of measuring a routing decision without fooling yourself.

## What I found

| setup | parse durations (`1h30m`) | PowerShell quoting |
|---|---|---|
| free model alone | 11/15 to 15/15 across six one-shot runs | 0/9 to 6/9 in every sample |
| strong critic + free fixer (Claude Opus) | 15/15 in both samples, 1 round | 9/9 in both samples, 2 rounds |
| free critic + free fixer (nemotron-3-ultra) | 15/15 after 1 round where a defect was found | 9/9 in 1 of 5 samples |
| larger free model alone (nemotron-3-ultra) | same spread as the first row (same model) | 9/9 in 5 of 5 samples |

Tasks 2, 3 and 4 (interval merging, line replacement that keeps CRLF/LF, and a recursive-force-delete detector) passed the first set of tests in almost every free-model sample. The critiques still found real defects in them that my tests had missed. See [RESULTS.md](RESULTS.md) for every table.

- **A critique only helps when it names a failing input and the exact required output.** Vague review did nothing for the small model.
- **The critic matters more than the fixer.** A free critic once approved a draft that was still wrong.
- **For a narrow task, routing to a larger free model beat adding a review step.**
- **Thin tests hide defects a review finds.** I wrote stricter tests afterwards from rules the spec already stated. They came after I had read the critiques, so they are reported beside the first scores and never instead of them (`rescore_v2.py`).
- **Check which model actually answered.** The CLI's usage file says which provider served each call, and a fallback's answer was discarded instead of counted.
- **Look at the replies.** An auto-loaded "brainstorming" skill made a small model answer with a plan and no code. A scorer that did not read the replies would have counted that as a model failure.

## The tasks

Each comes from a bug class I have actually hit on Windows:

| id | function | what makes it hard |
|---|---|---|
| T1 | `parse_duration("1h30m")` | several segments, ordering and repeat rules, strict errors |
| T2 | `merge_intervals(...)` | touching intervals, unsorted input |
| T3 | `replace_line(data, old, new)` | whole-line match, keep each line's own CRLF/LF/none ending |
| T4 | `is_destructive(cmd)` | `rm -rf` in any flag order, `Remove-Item -Recurse`, chaining, quoting |
| T5 | `ps_quote(s)` | PowerShell also treats U+2018, U+2019, U+201A and U+201B as quotes |

## How it is scored

1. **Hidden cases** run in a subprocess. A wrong answer, an exception and a timeout all score zero.
2. **The tests were tested first.** Every task ships a known-good and a known-bad solution; `python bench.py selfcheck` fails if the good one is not perfect or the bad one is not caught. A zero therefore means the model failed, not the harness.
3. **Test-blind critic loop.** The critic never sees the tests. Round two runs only if the critic still lists defects, never because the tests passed, and the loop is capped at two rounds.
4. **Lane check.** Each call records the provider and model that really served it. A mismatch is logged as `WRONG LANE` and has no score.

## Run it

Needs Python 3.11 and nothing to install.

```bash
python bench.py selfcheck                       # validate the oracles against known-good / known-bad solutions
python bench.py brief T4                        # print the exact prompt a model gets
python bench.py score T4 my_answer.py --approach mine --model whatever
```

`pipeline.py` runs the free-lane pipeline end to end. It shells out to the `ken` agent CLI because that is what I route through. To use another client, replace the small `ken()` function at the top of `pipeline.py` so it returns `(reply, usage, seconds, served_ok, served_name)`.

```bash
python pipeline.py T1 T2 --sample 1
```

Results append to `results.csv`. The `approach` column tells you the run. In the `A*`, `B*` and `C*` rows the free drafts and fixes came from free models via `ken`, while the strong baseline (`C`) and the critiques behind `B` were Claude Opus. The `FA`, `FB` and `FC` rows are the all-free run with nemotron-3-ultra as baseline and critic.

## Files

| file | purpose |
|---|---|
| `bench.py` | tasks, hidden cases, oracle, `selfcheck`, `score` |
| `pipeline.py` | free-lane A / B / C pipeline |
| `rescore_v2.py` | rescores the drafts you save under `out/` (not committed) against the stricter, post-hoc cases |
| `results.csv` | every scored row, with the lane that served it |
| `RESULTS.md` | the full tables and the findings per run |

## Limits

- Five tasks, one to five samples per cell. No claim generalises past that.
- Free calls cost $0. I record no dollar figure for the strong-model calls, because none was exposed.
- The stricter tests (`v2`) were written after reading the critiques. They are not independent of them.
- Some critic findings went beyond the spec (sudo options, commands given by full path) and were not added to `v2`.
- The strong model ran with a prompt asking it not to use tools. That is a request, not an enforced sandbox.

## License

MIT. See [LICENSE](LICENSE).
