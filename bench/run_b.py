# Copyright (c) 2026 Janak Rudani
"""Stage 1 producer-only benchmark. Stdlib only."""
import json
import sys
from pathlib import Path

from adapters import SPECS, build_lanes, load_env
from runner import Runner
from score_B import score


def main():
    if len(sys.argv) < 3:
        print("Usage: python run_b.py ENV_PATH DB_PATH [N=10]", file=sys.stderr)
        sys.exit(1)

    env_path = sys.argv[1]
    db_path = sys.argv[2]
    n_runs = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    env = load_env(env_path)
    tasks_json = json.loads((Path(__file__).parent / (sys.argv[4] if len(sys.argv) > 4 else "tasks_B.json")).read_text(encoding="utf-8"))
    tasks = tasks_json["tasks"]

    producer_lanes = ["nvidia", "mistral", "ollama-cloud"]  # groq dropped 2026-11-07 (persistent 429)
    lanes, missing = build_lanes(env, producer_lanes, daily_cap=100, rpm=10)

    if missing:
        print(f"Warning: no key for {missing}", file=sys.stderr)

    r = Runner(db_path, lanes)

    for lane_name in producer_lanes:
        if lane_name not in [l.name for l in lanes]:
            continue
        lane_model = SPECS[lane_name][1]
        for task_name, prompt in tasks.items():
            for i in range(n_runs):
                key = f"{lane_name}|{task_name}|{i}|alone"
                r.add(key, [lane_name], prompt)

    r.run(max_jobs=10**9)

    rows = r.db.execute(
        "SELECT key, served_lane, served_model, reply FROM jobs WHERE status='done' AND key LIKE '%|alone'"
    ).fetchall()

    from collections import defaultdict
    stats = defaultdict(lambda: {"done": 0, "repeat": 0, "avoid": 0, "unclear": 0})
    mismatches = defaultdict(int)

    for key, served_lane, served_model, reply in rows:
        lane_name, task_name = key.split("|", 2)[:2]
        requested_model = SPECS[served_lane][1] if served_lane in SPECS else ""
        if served_model != requested_model:
            mismatches[(served_lane, task_name)] += 1
            continue
        result = score(task_name, reply or "")
        stats[(served_lane, task_name)]["done"] += 1
        stats[(served_lane, task_name)][result] += 1

    print(f"{'Lane':<12} {'Task':<8} {'Done':>5} {'Repeat':>7} {'Avoid':>6} {'Unclear':>8} {'Mismatch':>9}")
    for lane_name in producer_lanes:
        if lane_name not in [l.name for l in lanes]:
            continue
        for task_name in tasks:
            s = stats[(lane_name, task_name)]
            mm = mismatches.get((lane_name, task_name), 0)
            print(f"{lane_name:<12} {task_name:<8} {s['done']:>5} {s['repeat']:>7} {s['avoid']:>6} {s['unclear']:>8} {mm:>9}")

    total_mismatch = sum(mismatches.values())
    if total_mismatch:
        print(f"\nTotal served_model mismatches (excluded from scoring): {total_mismatch}")

    # Stage 2: critic reviews each producer answer that scored 'repeat'. Critic lanes never include the producer's provider.
    tasks_text = tasks
    CRITICS = ["nvidia", "mistral", "ollama-cloud", "groq", "gemini"]  # gemini last: tiny daily allowance
    SAME_PROVIDER = {"nvidia": {"nvidia", "nvidia-lightning"}}
    cl, _ = build_lanes(env, CRITICS, daily_cap=100, rpm=10)
    r.lanes.update({l.name: l for l in cl if l.name not in r.lanes})
    for key, served_lane, served_model, reply in rows:
        lane_name, task_name, i, _ = key.split("|")
        if lane_name not in producer_lanes:
            continue
        if served_model != SPECS[served_lane][1] or score(task_name, reply or "") != "repeat":
            continue
        ok = [c for c in CRITICS if c in r.lanes and c not in SAME_PROVIDER.get(lane_name, {lane_name})]
        prompt = ("Review this answer to the task below. List any mistakes and say what the correct approach is.\n\n"
                  f"TASK:\n{tasks_text[task_name]}\n\nANSWER:\n{reply}")
        r.add(f"{lane_name}|{task_name}|{i}|critic", ok, prompt)
    r.run(max_jobs=10**9)
    crit = r.db.execute("SELECT key, served_lane, served_model, reply FROM jobs WHERE status='done' AND key LIKE '%|critic'").fetchall()
    flagged, total = defaultdict(int), defaultdict(int)
    for key, sl, sm, rep in crit:
        lane_name, task_name = key.split("|")[:2]
        if sm != SPECS[sl][1]:
            continue
        total[(lane_name, task_name)] += 1
        flagged[(lane_name, task_name)] += score(task_name, rep or "") == "avoid"
    print("\nCritic flagged the right fix, among producer answers that repeated the mistake:")
    for k in sorted(total):
        print(f"{k[0]:<12} {k[1]:<8} {flagged[k]}/{total[k]}")


if __name__ == "__main__":
    main()