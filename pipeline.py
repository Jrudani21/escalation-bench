#!/usr/bin/env python3
"""Free-lane-only escalation pipeline (no Claude calls). Ken --safe-mode on every call.

  A  = free model, one shot
  C  = nemotron-ultra, one shot (strong free baseline)
  B  = A draft -> nemotron-ultra critique (spec + draft only, no tests) -> A model fixes.
       Round 2 happens only if the critic still lists defects (test-blind stop rule), max 2.

  python pipeline.py T1 [T2 ...] --sample 1
"""
import argparse, json, subprocess, sys, time
from pathlib import Path
import bench

OUT = bench.OUT
ULTRA = ("nvidia", "nvidia/nemotron-3-ultra-550b-a55b")
MINI = ("mistral", "ministral-8b-latest")
FREE = {"T1": ULTRA, "T2": MINI, "T3": ULTRA, "T4": ULTRA, "T5": ULTRA}  # routed by task; T5 moved off ministral after 5 samples (ministral 0-6/9, ultra 9/9)

CRITIC = ("You are a code critic. Do not use tools. Check the DRAFT against the SPEC.\n"
          "Method: (1) list every concrete input the spec names or implies, including each "
          "spec example and each listed edge case; (2) for each, trace what the draft "
          "returns step by step; (3) compare with what the spec requires.\n"
          "Report numbered defects only, each as: input -> draft returns X -> spec requires "
          "Y. Quote the exact characters involved. Do not write the fix. Reply exactly "
          "`no defects found` only if every traced input matches.\n\n"
          "SPEC:\n{spec}\n\nDRAFT:\n```python\n{draft}\n```")
FIX = ("{brief}\n\nA previous draft was reviewed. Reviewer critique:\n{critique}\n\n"
       "Write a corrected version that fixes every listed defect and keeps everything else "
       "in the spec.\n\n" + bench.COMMON)


def ken(provider, model, prompt, stem):
    uf = OUT / f"{stem}_usage.json"
    uf.unlink(missing_ok=True)
    t0 = time.time()
    r = subprocess.run(["ken", "--safe-mode", "--provider", provider, "-m", model, "-z", prompt,
                        "--usage-file", str(uf)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    secs = time.time() - t0
    use = json.loads(uf.read_text(encoding="utf-8")) if uf.exists() else {}
    served = f"{use.get('provider')}/{use.get('model')}"
    ok = served == f"{provider}/{model}"
    (OUT / f"{stem}_reply.txt").write_text(r.stdout or "", encoding="utf-8")
    return r.stdout or "", use, secs, ok, served


def record(tid, approach, model, code, use, secs, ok, served, note=""):
    p1, t1, n1 = bench.run_tests(code, tid)
    p2, t2, _ = bench.run_tests(code, tid, v2=True)
    row = dict(task=tid, approach=approach, model=model, served=served,
               passed=p1 if ok else "", total=t1, secs=round(secs, 1),
               in_tok=use.get("input_tokens"), out_tok=use.get("output_tokens"),
               note=(f"v2={p2}/{t2}; " + ("WRONG LANE; " if not ok else "") + note + n1)[:200])
    bench.log(row)
    print(json.dumps({k: row[k] for k in ("task", "approach", "model", "passed", "total", "note")}))
    return p1, t1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="+")
    ap.add_argument("--sample", default="1")
    a = ap.parse_args()
    s = a.sample
    for tid in a.tasks:
        spec, brief = bench.TASKS[tid]["spec"], bench.brief(tid)
        fp, fm = FREE[tid]
        # A
        reply, use, secs, ok, served = ken(fp, fm, brief, f"{tid}_FA{s}")
        draft = bench.extract_code(reply)
        (OUT / f"{tid}_FA{s}.py").write_text(draft, encoding="utf-8")
        record(tid, f"FA_s{s}", fm, draft, use, secs, ok, served)
        # C (strong free baseline)
        reply, use, secs, ok, served = ken(*ULTRA, brief, f"{tid}_FC{s}")
        code = bench.extract_code(reply)
        (OUT / f"{tid}_FC{s}.py").write_text(code, encoding="utf-8")
        record(tid, f"FC_s{s}", ULTRA[1], code, use, secs, ok, served)
        # B: up to 2 critique+fix rounds, stop when the critic finds nothing
        cur = draft
        for rnd in (1, 2):
            creply, cuse, csecs, cok, cserved = ken(*ULTRA, CRITIC.format(spec=spec, draft=cur),
                                                    f"{tid}_FB{s}_crit{rnd}")
            if "no defects found" in creply.lower()[:80] or not cok:
                print(f"{tid} round {rnd}: critic {'found nothing' if cok else 'WRONG LANE'}")
                break
            freply, fuse, fsecs, fok, fserved = ken(fp, fm, FIX.format(brief=brief, critique=creply.strip()),
                                                    f"{tid}_FB{s}_fix{rnd}")
            cur = bench.extract_code(freply)
            (OUT / f"{tid}_FB{s}_r{rnd}.py").write_text(cur, encoding="utf-8")
            record(tid, f"FB_s{s}_r{rnd}", fm, cur, fuse, fsecs, fok, fserved)


if __name__ == "__main__":
    main()
