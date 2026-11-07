# Copyright (c) 2026 Janak Rudani
"""One tiny real call per lane through the Runner. Prints lane, requested vs served model, outcome. Never prints keys."""
import os
import sys
import tempfile

from adapters import SPECS, build_lanes, load_env
from runner import Runner

env = load_env(sys.argv[1])
names = list(SPECS)
lanes, missing = build_lanes(env, names, daily_cap=5, rpm=10)
db = os.path.join(tempfile.mkdtemp(prefix="smoke_"), "smoke.db")
r = Runner(db, lanes)
for lane in lanes:
    r.add("smoke-" + lane.name, [lane.name], "Reply with exactly the single word: ok")
out = r.run()
print("summary", out, "| no key for:", missing)
for key, status, lane, served, reply, attempts in r.db.execute(
        "SELECT key, status, served_lane, served_model, reply, attempts FROM jobs ORDER BY rowid"):
    name = key.replace("smoke-", "")
    asked = SPECS[name][1]
    print(f"{name:17s} {status:8s} asked={asked!r} served={served!r} match={served == asked} reply={(reply or '')[:30]!r}")
for ts, key, lane, kind, detail in r.db.execute("SELECT * FROM events"):
    print("event", lane, kind, detail[:100])
