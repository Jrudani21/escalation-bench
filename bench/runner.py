# Copyright (c) 2026 Janak Rudani
"""Job queue with lane failover and a buffer. Standard library only.

Rules that matter for a benchmark:
- A job lists the lanes it may use, in order. A producer job lists ONE lane (switching model would change what is
  measured); a critic job lists several providers (never the producer's).
- Transient failure (429, 503, timeout): try the next allowed lane right away; if none is usable, the job is BUFFERED.
- Permanent failure (401/403): the lane is disabled for this run.
- The served model must equal the requested model, otherwise the row is not scored and is re-queued.
- Daily call caps persist in the database, so a stopped run resumes tomorrow without overspending.
- Paid lanes are refused unless allow_paid=True.
"""
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta


class Transient(Exception):
    """429, 503, timeout: worth retrying later or on another lane."""


class Permanent(Exception):
    """401, 403, bad model: this lane will not work this run."""


@dataclass
class Lane:
    name: str
    model: str
    call: object              # call(prompt) -> (reply_text, served_model)
    daily_cap: int = 100
    rpm: int = 30
    paid: bool = False


MAX_ATTEMPTS = 6


class Runner:
    def __init__(self, db, lanes, allow_paid=False, now=time.time, sleep=time.sleep):
        for lane in lanes:
            if lane.paid and not allow_paid:
                raise ValueError(f"lane {lane.name} is paid; pass allow_paid=True to use it")
        self.lanes = {lane.name: lane for lane in lanes}
        self.now, self.sleep = now, sleep
        self.db = sqlite3.connect(db)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, lanes TEXT, prompt TEXT, status TEXT DEFAULT 'pending',
              attempts INT DEFAULT 0, next_ts REAL DEFAULT 0, served_lane TEXT, served_model TEXT, reply TEXT, err TEXT);
            CREATE TABLE IF NOT EXISTS usage(day TEXT, lane TEXT, calls INT, PRIMARY KEY(day, lane));
            CREATE TABLE IF NOT EXISTS events(ts REAL, key TEXT, lane TEXT, kind TEXT, detail TEXT);""")
        self.down = {}        # lane -> cooldown_until
        self.fails = {}       # lane -> consecutive transient failures
        self.dead = set()     # permanently failed this run
        self.last = {}        # lane -> last call time

    def add(self, key, lanes, prompt):
        self.db.execute("INSERT OR IGNORE INTO jobs(key, lanes, prompt) VALUES (?,?,?)", (key, json.dumps(lanes), prompt))
        self.db.commit()

    def _day(self):
        return datetime.fromtimestamp(self.now()).strftime("%Y-%m-%d")

    def _used(self, lane):
        r = self.db.execute("SELECT calls FROM usage WHERE day=? AND lane=?", (self._day(), lane)).fetchone()
        return r[0] if r else 0

    def _log(self, key, lane, kind, detail=""):
        self.db.execute("INSERT INTO events VALUES (?,?,?,?,?)", (self.now(), key, lane, kind, str(detail)[:300]))

    def _tomorrow(self):
        d = datetime.fromtimestamp(self.now()) + timedelta(days=1)
        return d.replace(hour=0, minute=5, second=0, microsecond=0).timestamp()

    def _usable(self, name):
        lane = self.lanes.get(name)
        if lane is None or name in self.dead:
            return False
        return self.down.get(name, 0) <= self.now() and self._used(name) < lane.daily_cap

    def _wait_rpm(self, lane):
        wait = self.last.get(lane.name, -1e9) + 60.0 / lane.rpm - self.now()
        if wait > 0:
            self.sleep(wait)

    def _try(self, lane, prompt):
        self._wait_rpm(lane)
        self.last[lane.name] = self.now()
        self.db.execute("INSERT INTO usage VALUES (?,?,1) ON CONFLICT(day, lane) DO UPDATE SET calls=calls+1",
                        (self._day(), lane.name))
        return lane.call(prompt)

    def run(self, max_jobs=10**9):
        out = {"done": 0, "buffered": 0, "failed": 0, "redirected": 0, "mismatch": 0}
        rows = self.db.execute(
            "SELECT key, lanes, prompt, attempts FROM jobs WHERE status='pending' AND next_ts<=? ORDER BY rowid LIMIT ?",
            (self.now(), max_jobs)).fetchall()
        for key, lanes_json, prompt, attempts in rows:
            allowed, finished, tried = json.loads(lanes_json), False, 0
            for name in allowed:
                if not self._usable(name):
                    continue
                lane = self.lanes[name]
                if tried:
                    out["redirected"] += 1
                    self._log(key, name, "redirect")
                tried += 1
                try:
                    reply, served = self._try(lane, prompt)
                except Transient as e:
                    self.fails[name] = self.fails.get(name, 0) + 1
                    if self.fails[name] >= 3:
                        self.down[name] = self.now() + min(900, 30 * 2 ** self.fails[name])
                    self._log(key, name, "transient", e)
                    continue
                except Permanent as e:
                    self.dead.add(name)
                    self._log(key, name, "permanent", e)
                    continue
                self.fails[name] = 0
                if served != lane.model:
                    out["mismatch"] += 1
                    self._log(key, name, "mismatch", f"asked {lane.model} got {served}")
                    break  # not scored; falls through to the re-queue below
                self.db.execute("UPDATE jobs SET status='done', served_lane=?, served_model=?, reply=?, err=NULL WHERE key=?",
                                (name, served, reply, key))
                out["done"] += 1
                finished = True
                break
            if not finished:
                attempts += 1
                if attempts >= MAX_ATTEMPTS:
                    self.db.execute("UPDATE jobs SET status='failed', attempts=?, err='gave up' WHERE key=?", (attempts, key))
                    out["failed"] += 1
                else:
                    usable = [n for n in allowed if n in self.lanes and n not in self.dead]
                    capped = bool(usable) and all(self._used(n) >= self.lanes[n].daily_cap for n in usable)
                    nxt = self._tomorrow() if capped else self.now() + 60 * attempts
                    self.db.execute("UPDATE jobs SET attempts=?, next_ts=? WHERE key=?", (attempts, nxt, key))
                    out["buffered"] += 1
        self.db.commit()
        return out

    def status(self):
        return dict(self.db.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall())
