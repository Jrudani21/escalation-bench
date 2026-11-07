# Copyright (c) 2026 Janak Rudani
"""Real lane adapters for runner.py: OpenAI-compatible chat/completions over urllib. Standard library only.

- Keys are read from a .env file and never printed or logged.
- 429 / 5xx / timeouts / empty replies -> Transient. 400-class errors (401, 403, 404...) -> Permanent.
- The model name the provider reports is returned as "served", so the runner can refuse rows served by another model.
- An honest User-Agent is sent. If a provider bans it (403, code 1010) the lane is reported dead; it is not disguised.
"""
import json
import socket
import urllib.error
import urllib.request

from runner import Lane, Permanent, Transient

USER_AGENT = "bench-runner/1.0 (personal research script)"
TRANSIENT_CODES = {408, 425, 429, 500, 502, 503, 504}

# name -> (base_url, model, key_env). Same lanes as lane-truth; cloudflare needs CLOUDFLARE_ACCOUNT_ID in the env file.
SPECS = {
    "nvidia": ("https://integrate.api.nvidia.com/v1", "nvidia/nemotron-3-ultra-550b-a55b", "NVIDIA_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "ministral-8b-latest", "MISTRAL_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "qwen/qwen3.8-27b", "GROQ_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.6-flash", "GOOGLE_API_KEY"),
    "ollama-cloud": ("https://ollama.com/v1", "gpt-oss:120b", "OLLAMA_API_KEY"),
    "nvidia-lightning": ("https://integrate.api.nvidia.com/v1", "nvidia/nemotron-3.5-lightning-30b-a3b", "NVIDIA_API_KEY"),
}


def load_env(path):
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def default_post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
        raise Transient(f"network: {type(e).__name__}") from None


def make_lane(name, env, post=default_post, max_tokens=1024, timeout=90, **lane_kw):
    base, model, key_env = SPECS[name]
    key = env.get(key_env)
    if not key:
        return None
    url = base.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": USER_AGENT}

    def call(prompt):
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                           "max_tokens": max_tokens, "temperature": 0}).encode("utf-8")
        status, text = post(url, headers, body, timeout)
        if status in TRANSIENT_CODES:
            raise Transient(f"HTTP {status}")
        if status >= 400:
            raise Permanent(f"HTTP {status}: {text[:120]}")
        try:
            data = json.loads(text)
            msg = data["choices"][0]["message"]
            reply = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            finish = data["choices"][0].get("finish_reason")
        except (ValueError, KeyError, IndexError, TypeError):
            raise Transient("unreadable reply") from None
        if not reply:
            raise Transient(f"empty reply (finish_reason={finish})")
        return reply, data.get("model", "")

    return Lane(name, model, call, **lane_kw)


def build_lanes(env, names, **kw):
    """Lanes whose key exists; returns (lanes, missing_names)."""
    lanes, missing = [], []
    for n in names:
        lane = make_lane(n, env, **kw)
        (lanes if lane else missing).append(lane or n)
    return lanes, missing
