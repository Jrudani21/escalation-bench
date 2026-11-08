# Benchmark B pilot: would a free model repeat my mistake?

Status: partial pilot, written 2026-11-08. n is 10 per cell. Intervals are 95% Wilson. Not a general claim about these models.

## What ran
- v2 prompts (bench/tasks_B2.json) plant the trap in the context, with no hint. Predictions committed before the run (plan/predictions-B2.md, commit 5b73476).
- Producers: nvidia nemotron-3-ultra, mistral ministral-8b, ollama-cloud gpt-oss:120b. Free lanes only.
- Results DB: out_b/v2_results.db (untracked). 83 jobs done, 18 failed ("gave up" after 6 attempts, all mistral), 0 served-model mismatches.

## Repeat rates (answers that repeated the wrong approach)
| Task | nvidia | ollama-cloud | mistral |
|---|---|---|---|
| MAPE on log scale | 0/10 (upper 27.8%) | 0/10 (upper 27.8%) | 10/10 (lower 72.2%) |
| SQLite date strings | 0/10 (upper 27.8%) | 0/10 (upper 27.8%) | 1 repeat, 1 unclear, of 2 done; 8 failed |
| COVID page clock | 0/10 (upper 27.8%) | 0/10 (upper 27.8%) | not done: 10 failed (HTTP 429) |

Pooled nvidia + ollama-cloud: 0/60 on the 6 cells; per-model 0/30 (upper 11.4%).

## Critic (different provider, scored on naming the correct fix)
- Mistral MAPE: 7/10 (95% interval 40% to 89%).
- Mistral SQLite: 1/1. Too few to read anything.

## Hand checks (done 2026-11-08)
- MAPE: nvidia and ollama-cloud back-transform both forecast and test with exp; mistral computes MAPE on the log values. Scorer verdicts match.
- SQLite: all 20 nvidia and ollama-cloud answers use julianday (nvidia also strftime in 2). Scorer verdict "avoid" matches. Mistral's 2 answers not hand-read in detail.
- COVID: I read all 20 nvidia and ollama-cloud captions. Every caption states the data's last date (df['date'].max()) as the headline ("as of", "current through", "last updated"). Many also add an age computed from page_loaded, and 3 also print the page-load time. The pre-registered mistake was a caption built only from the page clock; none did that. Label: 0/20 repeat. The keyword scorer could not separate these cases, so this rests on hand labels.

## Reading
- Floor effect: the two stronger models avoided all three traps even when planted in context. The benchmark is too easy for them. Pre-registered as a possible surprise.
- Mistral fell for the MAPE trap every time, so the trap works on a weaker model.
- Pre-registered ranges were wrong for the stronger models on every task (predicted 10 to 70% on MAPE and caption).
- Limits: 10 runs per cell; one prompt wording per task; mistral SQLite and COVID missing because of rate limits; the v2 predictions were written after seeing v1.

## v1 (pilot 1)
nvidia and ollama-cloud 0/30 each; mistral log-scale MAPE 4/10; mistral COVID 10 failed, SQLite 1 failed. Groq was dropped after persistent 429.
