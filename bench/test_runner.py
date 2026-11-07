# Copyright (c) 2026 Janak Rudani
import unittest

from runner import Lane, Permanent, Runner, Transient


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def ok(model):
    return lambda p: (f"reply:{p}", model)


def boom(exc):
    def f(p):
        raise exc
    return f


def make(lanes, **kw):
    c = Clock()
    return Runner(":memory:", lanes, now=c.now, sleep=c.sleep, **kw), c


class RunnerTests(unittest.TestCase):
    def test_happy_path_logs_served_lane(self):
        r, _ = make([Lane("a", "m-a", ok("m-a"))])
        r.add("j1", ["a"], "hi")
        self.assertEqual(r.run()["done"], 1)
        self.assertEqual(r.db.execute("SELECT served_lane, served_model FROM jobs").fetchone(), ("a", "m-a"))

    def test_critic_redirects_to_next_lane_on_transient_failure(self):
        r, _ = make([Lane("a", "m-a", boom(Transient("503"))), Lane("b", "m-b", ok("m-b"))])
        r.add("c1", ["a", "b"], "x")
        out = r.run()
        self.assertEqual((out["done"], out["redirected"]), (1, 1))
        self.assertEqual(r.db.execute("SELECT served_lane FROM jobs").fetchone()[0], "b")

    def test_producer_job_never_leaves_its_lane_it_is_buffered(self):
        r, _ = make([Lane("a", "m-a", boom(Transient("429"))), Lane("b", "m-b", ok("m-b"))])
        r.add("p1", ["a"], "x")
        out = r.run()
        self.assertEqual((out["done"], out["buffered"]), (0, 1))
        self.assertEqual(r.status(), {"pending": 1})
        self.assertEqual(r.db.execute("SELECT COUNT(*) FROM events WHERE lane='b'").fetchone()[0], 0)

    def test_buffered_job_runs_after_the_wait(self):
        calls = {"n": 0}

        def flaky(p):
            calls["n"] += 1
            if calls["n"] == 1:
                raise Transient("503")
            return ("fine", "m-a")
        r, c = make([Lane("a", "m-a", flaky)])
        r.add("p1", ["a"], "x")
        r.run()
        self.assertEqual(r.run()["done"], 0)  # not due yet
        c.t += 120
        self.assertEqual(r.run()["done"], 1)

    def test_permanent_failure_disables_lane_for_the_run(self):
        r, _ = make([Lane("a", "m-a", boom(Permanent("403"))), Lane("b", "m-b", ok("m-b"))])
        r.add("c1", ["a", "b"], "x")
        r.add("c2", ["a", "b"], "y")
        self.assertEqual(r.run()["done"], 2)
        self.assertEqual(r.db.execute("SELECT COUNT(*) FROM events WHERE lane='a' AND kind='permanent'").fetchone()[0], 1)

    def test_served_model_mismatch_is_not_scored(self):
        r, _ = make([Lane("a", "m-a", ok("some-other-model"))])
        r.add("p1", ["a"], "x")
        out = r.run()
        self.assertEqual((out["done"], out["mismatch"], out["buffered"]), (0, 1, 1))
        self.assertEqual(r.status(), {"pending": 1})

    def test_daily_cap_buffers_until_tomorrow_and_resets(self):
        r, c = make([Lane("a", "m-a", ok("m-a"), daily_cap=2)])
        for i in range(4):
            r.add(f"j{i}", ["a"], "x")
        out = r.run()
        self.assertEqual((out["done"], out["buffered"]), (2, 2))
        c.t += 3600
        self.assertEqual(r.run()["done"], 0)   # still today
        c.t += 24 * 3600
        self.assertEqual(r.run()["done"], 2)   # next day, cap reset

    def test_paid_lane_refused_by_default(self):
        with self.assertRaises(ValueError):
            Runner(":memory:", [Lane("p", "m", ok("m"), paid=True)])
        Runner(":memory:", [Lane("p", "m", ok("m"), paid=True)], allow_paid=True)

    def test_gives_up_after_max_attempts(self):
        r, c = make([Lane("a", "m-a", boom(Transient("503")))])
        r.add("p1", ["a"], "x")
        for _ in range(8):
            r.run()
            c.t += 3600
        self.assertEqual(r.status(), {"failed": 1})

    def test_unknown_lane_in_job_is_skipped_not_fatal(self):
        r, _ = make([Lane("b", "m-b", ok("m-b"))])
        r.add("c1", ["ghost", "b"], "x")
        self.assertEqual(r.run()["done"], 1)

    def test_rpm_spacing_sleeps(self):
        r, c = make([Lane("a", "m-a", ok("m-a"), rpm=6)])  # one call per 10 s
        r.add("j1", ["a"], "x")
        r.add("j2", ["a"], "y")
        t0 = c.t
        r.run()
        self.assertGreaterEqual(c.t - t0, 10)


if __name__ == "__main__":
    unittest.main()
