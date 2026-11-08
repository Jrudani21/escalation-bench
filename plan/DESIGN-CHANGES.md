# Design changes after pre-registration (793ebba)

1. 2026-11-07, scorer: 3_sqlite "repeat" rule tightened after a dry run showed a false positive (fdd98a2). No full-run results existed yet.
2. 2026-11-07, producer lane: groq dropped, ollama-cloud gpt-oss:120b added as third producer. Reason: groq returned HTTP 429 on most calls (13 transient events, 4 of 30 jobs done, 25 pending jobs marked `dropped`). Janak chose to replace it. The 4 completed groq rows stay in the DB, are not scored, and are not deleted. Predictions were written for "free models" in general, not for groq specifically, so the ranges stand.
3. Critic: scores whether the critic's reply names the correct fix, only over producer answers that repeated the mistake. Critic reviews the producer-alone answers (no separate with-critic producer runs).
