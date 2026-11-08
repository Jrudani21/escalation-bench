# Design changes after pre-registration (793ebba)

1. 2026-11-07, scorer: 3_sqlite "repeat" rule tightened after a dry run showed a false positive (fdd98a2). No full-run results existed yet.
2. 2026-11-07, producer lane: groq dropped, ollama-cloud gpt-oss:120b added as third producer. Reason: groq returned HTTP 429 on most calls (13 transient events, 4 of 30 jobs done, 25 pending jobs marked `dropped`). Janak chose to replace it. The 4 completed groq rows stay in the DB, are not scored, and are not deleted. Predictions were written for "free models" in general, not for groq specifically, so the ranges stand.
3. Critic: scores whether the critic's reply names the correct fix, only over producer answers that repeated the mistake. Critic reviews the producer-alone answers (no separate with-critic producer runs).

## 2026-11-08: v2 mistral rerun and COVID hand labels
- Reran loop_v2.sh on the same DB. Mistral still returned 429; 18 jobs ended "gave up" (SQLite 8, COVID 10). Hard stop in ERROR-RULES.md reached; no lane switch, no rows deleted.
- COVID v2 answers hand-labeled (20 nvidia + ollama-cloud): all show the data's last date, so 0 repeat. The keyword scorer is unchanged; the hand labels replace its COVID verdicts in the write-up only.
