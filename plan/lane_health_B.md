# Lane health for benchmark B (probe 2026-11-07, one tiny chat/completions each, via lane-truth in a scratch copy)

| Lane | Model | Result | Code | Latency s |
|---|---|---|---|---|
| nvidia | nemotron-3-ultra-550b | ok | 200 | 1.11 |
| mistral | ministral-8b-latest | ok | 200 | 0.45 |
| groq | qwen3.8-27b | ok | 200 | 0.25 |
| gemini | gemini-3.6-flash | ok | 200 | 1.83 |
| nvidia-lightning | nemotron-3.5-lightning-30b | ok | 200 | 0.86 |
| ollama-cloud | gpt-oss:120b | ok | 200 | 0.58 |
| dashscope | qwen3.5-27b | auth | 403 | 0.97 |
| sambanova | DeepSeek-V3.2 | dead | 401 | 0.38 |

Not probed (metered, excluded by default): openrouter, cloudflare. Probe before using as critic.

Caveats
- A tiny probe is not a full-size request. The catalogue records nvidia returning 503 overloaded on larger requests on 2026-11-02; re-test with a real B-size prompt and a burst before trusting it for 80 calls.
- Key drift: GROQ_API_KEY and NVIDIA_API_KEY differ between the shell environment and E:\Local\ken-desktop\.env. The harness must read the .env file (lane-truth already does) and never print either value.
- Reasoning models return empty text at small max_tokens; use 256 or more and read finish_reason.
- ollama-cloud answered 200 now though the catalogue noted a monthly limit on 2026-10-30; watch for 429 mid-run.
