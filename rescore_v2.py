"""Post-hoc oracle v2: extra cases derived from rules the spec already states.
Added AFTER Opus critiques exposed gaps. Reported separately from v1; never replaces it."""
import csv, sys
from pathlib import Path
import bench

EXTRA = {
    "T1": [(("05m",), 300), (("00s",), 0)],
    "T3": [((b"a\rb\n", b"b"), None)],  # placeholder, replaced below
    "T4": [(('rm "-rf" x',), False), (("'rm' -rf /tmp/x",), False),
           (("Remove-Item x '-Recurse'",), False)],
}
EXTRA["T3"] = [((b"a\rb\n", b"b", b"X"), "!ValueError"),
               ((b"a\rb\n", b"a\rb", b"X"), b"X\n")]

for tid, cases in EXTRA.items():
    bench.TASKS[tid]["cases"] = bench.TASKS[tid]["cases"] + cases

# controls still hold under v2
for tid in EXTRA:
    t = bench.TASKS[tid]
    g = bench.run_tests(t["good"], tid)
    b = bench.run_tests(t["bad"], tid)
    print(f"control {tid}: good {g[0]}/{g[1]} bad {b[0]}/{b[1]}")

rows = []
for tid in EXTRA:
    for f in sorted(Path("out").glob(f"{tid}_*.py")):
        p, t, note = bench.run_tests(f.read_text(encoding="utf-8"), tid)
        rows.append((f.stem, p, t, note[:90]))
        print(f"{f.stem:14} v2 {p}/{t}  {note[:90]}")
