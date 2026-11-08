# Predictions B v2: does a model repeat the mistake when the trap is already in the prompt? (DRAFT, edit then commit BEFORE any v2 run)

Date written: 2026-11-07. Nothing in v2 has been run.

## What v1 showed (pilot 1, already in the DB, so these predictions are NOT blind to it)
- nvidia and ollama-cloud repeated 0 of 30 answers each; mistral repeated log-scale MAPE 4 of 10.
- The v1 wording was too easy for the stronger models.

## Question
When the original trap is planted in the prompt's context, with no hint that it is a trap, how often does a free model produce the same wrong answer, and does a critic from a different provider reduce that?

## Tasks (wording in bench/tasks_B2.json)
1. 2_mape_v2: test series already on the log scale. Wrong: MAPE on log values. Right: back-transform with exp first.
2. 3_sqlite_v2: "overlap by more than 30 days" on ISO text dates. Wrong: subtract date strings. Right: julianday() or equivalent.
3. 4_covid_v2: `page_loaded = datetime.now()` is already in the page. Wrong: caption uses the page clock. Right: caption uses the data's last date.

## Design
- Producers: nvidia nemotron-3-ultra, mistral ministral-8b, ollama-cloud gpt-oss:120b. 10 runs per model per task = 90 producer calls.
- Critic reviews each producer answer that repeated the mistake, from a different provider, and is scored on whether it names the correct fix. At most 90 critic calls.
- Every call logs which model served it; mismatched rows are not scored.
- Error handling: plan/ERROR-RULES.md. Changes after commit are logged in plan/DESIGN-CHANGES.md.

## Predictions: share of answers that repeat the wrong answer (no critic)
| Task | nvidia | ollama-cloud | mistral |
|---|---|---|---|
| 1 MAPE on log scale | 10 to 40% | 10 to 40% | 50 to 90% |
| 2 SQLite date strings | 0 to 20% | 0 to 20% | 20 to 60% |
| 3 Page clock caption | 30 to 70% | 30 to 70% | 60 to 95% |

Critic: names the correct fix in 40 to 80% of the answers it reviews, higher on MAPE and SQLite than on the caption.

## Calls I am making
- The caption task has the highest repeat rate, because the prompt hands the model the page clock.
- Mistral repeats more than the other two on every task.
- With few repeats from the stronger models, the critic numbers will rest on mistral answers mostly. I will say so.
- A surprise: the stronger models still avoid all three traps. That would mean the benchmark is still too easy.

## Rules I commit to
- Wilson intervals on every rate; call it a pilot; state n.
- Free lanes only; if a lane stays dead after two reruns, stop and report; no silent switch to paid.
- Publish the result even if it disappoints, and publish v1 next to it.
