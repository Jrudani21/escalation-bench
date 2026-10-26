#!/usr/bin/env python3
"""Escalation-ladder benchmark: 5 real-bug-flavoured tasks, mechanically scored.

A = routed free model via Ken, single shot
B = A draft -> Opus critique (no hidden tests) -> same free model fixes (max 2 rounds)
C = Opus single shot, no tools

Oracle = hidden cases run in a subprocess. No LLM judge. Controls: every task has a
known-good solution (must score full) and a known-bad one (must NOT score full).

  python bench.py selfcheck
  python bench.py brief T1
  python bench.py ken T1 --provider P --model M [--tag A] [--prompt-file f]
  python bench.py score T1 path.py --approach C --model opus
"""
from __future__ import annotations
import csv, json, subprocess, sys, tempfile, textwrap, time, argparse, os
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "out"
CSV = ROOT / "results.csv"
FIELDS = ["task", "approach", "model", "served", "passed", "total", "secs",
          "in_tok", "out_tok", "note"]

COMMON = ("Standard library only. Return ONLY the function (plus any imports/helpers it "
          "needs) inside a single ```python fence. No explanation, no tests, no tool calls.")

# ---------------------------------------------------------------- tasks
# cases: (args_tuple, expected). expected "!X" means: must raise exception class X.
TASKS = {}

TASKS["T1"] = dict(
    fn="parse_duration",
    spec="""Write `parse_duration(s: str) -> int` returning total seconds.
Format: one or more segments `<digits><unit>`, unit in d,h,m,s (d=86400, h=3600, m=60, s=1).
Rules:
- Case-insensitive; surrounding whitespace is ignored; no whitespace inside.
- Units must appear in descending order d,h,m,s and each at most once.
- Anything else raises ValueError: empty string, bare number without unit, unit without
  digits, decimals, negatives, repeated unit, out-of-order units, unknown unit.
Examples: "1h30m" -> 5400, "90s" -> 90, "2d4h" -> 187200.""",
    cases=[
        (("1h30m",), 5400), (("90s",), 90), (("2d4h",), 187200),
        (("1d1h1m1s",), 90061), ((" 5M ",), 300), (("0s",), 0),
        (("",), "!ValueError"), (("30m1h",), "!ValueError"), (("1h1h",), "!ValueError"),
        (("10",), "!ValueError"), (("h",), "!ValueError"), (("1.5h",), "!ValueError"),
        (("-5s",), "!ValueError"), (("1h 30m",), "!ValueError"), (("5x",), "!ValueError"),
    ],
    good='''import re
def parse_duration(s):
    s = s.strip().lower()
    m = re.fullmatch(r"(?:(\\d+)d)?(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?", s)
    if not s or not m:
        raise ValueError(s)
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se
''',
    bad='''def parse_duration(s):
    total = 0
    n = ""
    for ch in s.strip().lower():
        if ch.isdigit():
            n += ch
        else:
            total += int(n or 0) * {"d": 86400, "h": 3600, "m": 60, "s": 1}.get(ch, 0)
            n = ""
    return total
''',
)

TASKS["T2"] = dict(
    fn="merge_intervals",
    spec="""Write `merge_intervals(iv: list[list[int]]) -> list[list[int]]`.
Merge overlapping OR touching intervals (end == next start counts as touching).
Input may be unsorted; each interval is [start, end] with start <= end. Return a new list
of [start, end] lists sorted by start. Empty input returns [].
Examples: [[1,3],[2,6],[8,10]] -> [[1,6],[8,10]]; [[1,4],[4,5]] -> [[1,5]].""",
    cases=[
        (([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]),
        (([[1, 4], [4, 5]],), [[1, 5]]),
        (([[5, 6], [1, 2]],), [[1, 2], [5, 6]]),
        (([[1, 10], [2, 3]],), [[1, 10]]),
        (([],), []),
        (([[1, 1]],), [[1, 1]]),
        (([[1, 2], [3, 4]],), [[1, 2], [3, 4]]),
        (([[2, 3], [1, 10], [11, 12]],), [[1, 10], [11, 12]]),
    ],
    good='''def merge_intervals(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out
''',
    bad='''def merge_intervals(iv):
    out = []
    for a, b in sorted(iv):
        if out and a < out[-1][1]:
            out[-1][1] = b
        else:
            out.append([a, b])
    return out
''',
)

TASKS["T3"] = dict(
    fn="replace_line",
    spec="""Write `replace_line(data: bytes, old: bytes, new: bytes) -> bytes`.
Replace the FIRST line whose content, excluding its line ending, equals `old` exactly
(whole-line match, not substring) with `new`. Keep that line's original ending byte-for-byte:
b"\\r\\n", b"\\n", or none if it is the last line without a terminator. Every other byte is
untouched, including other lines' endings (a file may mix CRLF and LF).
If no line matches, raise ValueError.
Example: replace_line(b"a\\r\\nb\\r\\n", b"b", b"X") -> b"a\\r\\nX\\r\\n".""",
    cases=[
        ((b"a\r\nb\r\nc\r\n", b"b", b"X"), b"a\r\nX\r\nc\r\n"),
        ((b"a\nb\r\nc\n", b"b", b"X"), b"a\nX\r\nc\n"),
        ((b"a\nb", b"b", b"X"), b"a\nX"),
        ((b"a\r\nb\r\n", b"c", b"X"), "!ValueError"),
        ((b"b\nb\n", b"b", b"X"), b"X\nb\n"),
        ((b"ab\nb\n", b"b", b"Y"), b"ab\nY\n"),
        ((b"", b"b", b"X"), "!ValueError"),
        ((b"x\r\n", b"x", b""), b"\r\n"),
    ],
    good='''def replace_line(data, old, new):
    pos = 0
    n = len(data)
    while pos < n:
        nl = data.find(b"\\n", pos)
        end = n if nl == -1 else nl + 1
        line = data[pos:end]
        if line.endswith(b"\\r\\n"):
            body, eol = line[:-2], b"\\r\\n"
        elif line.endswith(b"\\n"):
            body, eol = line[:-1], b"\\n"
        else:
            body, eol = line, b""
        if body == old:
            return data[:pos] + new + eol + data[end:]
        pos = end
    raise ValueError("no matching line")
''',
    bad='''def replace_line(data, old, new):
    text = data.decode()
    if old.decode() not in text:
        raise ValueError("no")
    return text.replace(old.decode(), new.decode(), 1).replace("\\n", "\\r\\n").encode()
''',
)

TASKS["T4"] = dict(
    fn="is_destructive",
    spec="""Write `is_destructive(cmd: str) -> bool` for a shell-command safety hook.
True when the command line would recursively force-delete:
- `rm` with BOTH a recursive flag (-r, -R, --recursive) AND a force flag (-f, --force),
  in any combination or order (-rf, -fr, -Rf, -r -f, --recursive --force);
- PowerShell `Remove-Item` or its alias `ri` with `-Recurse` (case-insensitive).
The command may be chained (`;`, `&&`, `||`, `|`) or prefixed with `sudo`; check every part.
Text inside single or double quotes is data, not a command, so it never counts.
False for: `rm` without both flags, `git rm ...`, `grep -rf ...`, `Remove-Item` without
-Recurse, and anything else.
Examples: "rm -rf /tmp/x" -> True; "git rm --cached a.txt" -> False.""",
    cases=[
        (("rm -rf /tmp/x",), True), (("rm -fr x",), True), (("rm -r -f x",), True),
        (("rm --recursive --force x",), True), (("ls && rm -Rf build",), True),
        (("sudo rm -rf x",), True), (("ls; rm -rf build",), True),
        (("Remove-Item -Recurse C:\\x",), True), (("remove-item -recurse -force x",), True),
        (("ri -Recurse x",), True),
        (("rm file.txt",), False), (("rm -r dir",), False),
        (("git rm --cached a.txt",), False), (('echo "rm -rf /"',), False),
        (("echo 'Remove-Item -Recurse x'",), False), (("grep -rf pats src",), False),
        (("Remove-Item a.txt",), False), (("echo hi",), False),
    ],
    good='''import re, shlex
def _parts(cmd):
    out, cur, q = [], [], None
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            if c == q:
                q = None
            cur.append("\\0")
        elif c in "'\\"":
            q = c
            cur.append("\\0")
        elif c in ";|&":
            out.append("".join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    out.append("".join(cur))
    return out
def is_destructive(cmd):
    for part in _parts(cmd):
        toks = [t for t in part.split() if "\\0" not in t]
        while toks and toks[0] == "sudo":
            toks = toks[1:]
        if not toks:
            continue
        head, args = toks[0].lower(), toks[1:]
        if head == "rm":
            rec = force = False
            for a in args:
                if a == "--recursive": rec = True
                elif a == "--force": force = True
                elif a.startswith("-") and not a.startswith("--"):
                    rec = rec or any(ch in "rR" for ch in a[1:])
                    force = force or "f" in a[1:]
            if rec and force:
                return True
        elif head in ("remove-item", "ri"):
            if any(a.lower() == "-recurse" for a in args):
                return True
    return False
''',
    bad='''def is_destructive(cmd):
    c = cmd.lower()
    return "rm -rf" in c or "remove-item" in c
''',
)

TASKS["T5"] = dict(
    fn="ps_quote",
    spec="""Write `ps_quote(s: str) -> str` that turns any string into a PowerShell single-quoted
literal (the safe way to pass a path such as C:\\Users\\Jane's PC).
Wrap in single quotes, and double every character PowerShell treats as a single quote:
the ASCII apostrophe ' (U+0027) AND the typographic quotes U+2018, U+2019, U+201A, U+201B.
Nothing else is escaped ($ and backtick are literal inside single quotes).
Examples: "plain" -> "'plain'"; "Jane's" -> "'Jane''s'"; "" -> "''".""",
    cases=[
        (("C:\\Users\\Jane's PC",), "'C:\\Users\\Jane''s PC'"),
        (("plain",), "'plain'"), (("",), "''"),
        (("it\u2019s",), "'it\u2019\u2019s'"),
        (("\u2018x\u2019",), "'\u2018\u2018x\u2019\u2019'"),
        (("a$b`c",), "'a$b`c'"),
        (("''",), "''''''"),
        (("\u201a\u201b",), "'\u201a\u201a\u201b\u201b'"),
        (("a\"b",), "'a\"b'"),
    ],
    good='''def ps_quote(s):
    out = []
    for ch in s:
        out.append(ch + ch if ch in "'\\u2018\\u2019\\u201a\\u201b" else ch)
    return "'" + "".join(out) + "'"
''',
    bad='''def ps_quote(s):
    return "'" + s.replace("'", "''") + "'"
''',
)


def brief(tid: str) -> str:
    t = TASKS[tid]
    return f"{t['spec']}\n\n{COMMON}"


# ---------------------------------------------------------------- oracle
def extract_code(reply: str) -> str:
    if "```" in reply:
        parts = reply.split("```")
        for i in range(1, len(parts), 2):
            lines = parts[i].splitlines()
            if lines and lines[0].strip().lower() in ("python", "py", "python3"):
                lines = lines[1:]
            block = "\n".join(lines)
            if block.strip():
                return block
    return reply


# Post-hoc oracle v2: cases derived from rules the spec already states, added after
# critiques exposed gaps in v1. Report beside v1, never instead of it.
EXTRA_V2 = {
    "T1": [(("05m",), 300), (("00s",), 0)],
    "T3": [((b"a\rb\n", b"b", b"X"), "!ValueError"), ((b"a\rb\n", b"a\rb", b"X"), b"X\n")],
    "T4": [(('rm "-rf" x',), False), (("'rm' -rf /tmp/x",), False),
           (("Remove-Item x '-Recurse'",), False)],
}


def run_tests(code: str, tid: str, v2: bool = False) -> tuple[int, int, str]:
    t = TASKS[tid]
    cases = t["cases"] + (EXTRA_V2.get(tid, []) if v2 else [])
    if not code.strip():
        return 0, len(cases), "empty code"
    harness = (f"import json, sys\nCASES = {cases!r}\nFN = {t['fn']!r}\n" + code + textwrap.dedent("""

        if __name__ == "__main__":
            fn = globals().get(FN)
            if not callable(fn):
                print(json.dumps({"passed": 0, "total": len(CASES), "note": "fn not defined"}))
                sys.exit(0)
            ok, bad = 0, []
            for args, exp in CASES:
                try:
                    got = fn(*args)
                except Exception as e:
                    if isinstance(exp, str) and exp == "!" + type(e).__name__:
                        ok += 1
                    else:
                        bad.append(f"{args!r}: raised {type(e).__name__}")
                    continue
                if isinstance(exp, str) and exp.startswith("!"):
                    bad.append(f"{args!r}: no raise, got {got!r}")
                elif got == exp and type(got) is type(exp):
                    ok += 1
                else:
                    bad.append(f"{args!r}: got {got!r} want {exp!r}")
            print(json.dumps({"passed": ok, "total": len(CASES), "note": "; ".join(bad[:3])}))
    """))
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "cand.py"
        p.write_text(harness, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-I", str(p)], capture_output=True, text=True,
                               timeout=30, cwd=td)
        except subprocess.TimeoutExpired:
            return 0, len(cases), "timed out"
    for line in reversed((r.stdout or "").strip().splitlines()):
        try:
            d = json.loads(line)
            return d["passed"], d["total"], d.get("note", "")
        except Exception:
            continue
    return 0, len(cases), "no result; stderr=" + r.stderr.strip()[-160:]


def log(row: dict) -> None:
    new = not CSV.exists()
    with CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


# ---------------------------------------------------------------- commands
def cmd_selfcheck(_a) -> int:
    ok = True
    for tid, t in TASKS.items():
        gp, gt, gn = run_tests(t["good"], tid)
        bp, bt, bn = run_tests(t["bad"], tid)
        good_ok, bad_ok = gp == gt, bp < bt
        ok &= good_ok and bad_ok
        print(f"{tid} good {gp}/{gt} {'OK' if good_ok else 'ORACLE BROKEN ' + gn}  "
              f"bad {bp}/{bt} {'OK' if bad_ok else 'ORACLE TOO LENIENT'}")
    return 0 if ok else 1


def cmd_ken(a) -> int:
    OUT.mkdir(exist_ok=True)
    prompt = Path(a.prompt_file).read_text(encoding="utf-8") if a.prompt_file else brief(a.task)
    stem = f"{a.task}_{a.tag}"
    uf = OUT / f"{stem}_usage.json"
    if uf.exists():
        uf.unlink()
    t0 = time.time()
    r = subprocess.run(["ken", "--provider", a.provider, "-m", a.model, *a.ken_args.split(),
                        "-z", prompt, "--usage-file", str(uf)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    secs = time.time() - t0
    reply = r.stdout or ""
    (OUT / f"{stem}_reply.txt").write_text(reply, encoding="utf-8")
    use = json.loads(uf.read_text(encoding="utf-8")) if uf.exists() else {}
    served = f"{use.get('provider')}/{use.get('model')}"
    wanted = f"{a.provider}/{a.model}"
    valid = served == wanted
    code = extract_code(reply)
    (OUT / f"{stem}.py").write_text(code, encoding="utf-8")
    p, t, note = run_tests(code, a.task)
    if not valid:
        note = f"WRONG LANE served={served}; " + note
    row = dict(task=a.task, approach=a.tag, model=a.model, served=served,
               passed=p if valid else "", total=t, secs=round(secs, 1),
               in_tok=use.get("input_tokens"), out_tok=use.get("output_tokens"), note=note[:200])
    log(row)
    print(json.dumps(row))
    return 0


def cmd_score(a) -> int:
    code = extract_code(Path(a.path).read_text(encoding="utf-8"))
    p, t, note = run_tests(code, a.task)
    row = dict(task=a.task, approach=a.approach, model=a.model, served=a.model, passed=p,
               total=t, secs=a.secs, in_tok=a.in_tok, out_tok=a.out_tok, note=note[:200])
    log(row)
    print(json.dumps(row))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selfcheck")
    b = sub.add_parser("brief"); b.add_argument("task")
    k = sub.add_parser("ken")
    k.add_argument("task"); k.add_argument("--provider", required=True)
    k.add_argument("--model", required=True); k.add_argument("--tag", default="A")
    k.add_argument("--prompt-file"); k.add_argument("--ken-args", default="--safe-mode")
    s = sub.add_parser("score")
    s.add_argument("task"); s.add_argument("path"); s.add_argument("--approach", required=True)
    s.add_argument("--model", required=True); s.add_argument("--secs", default="")
    s.add_argument("--in-tok", dest="in_tok", default=""); s.add_argument("--out-tok", dest="out_tok", default="")
    a = ap.parse_args()
    if a.cmd == "brief":
        print(brief(a.task)); return 0
    return {"selfcheck": cmd_selfcheck, "ken": cmd_ken, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
