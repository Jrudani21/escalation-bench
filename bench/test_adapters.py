# Copyright (c) 2026 Janak Rudani
import json
import unittest

from adapters import SPECS, build_lanes, make_lane
from runner import Permanent, Transient

ENV = {"MISTRAL_API_KEY": "k-secret-1", "GROQ_API_KEY": "k-secret-2"}


def reply(content="ok", model="ministral-8b-latest", reasoning=None, finish="stop"):
    msg = {"content": content}
    if reasoning:
        msg["reasoning_content"] = reasoning
    return 200, json.dumps({"model": model, "choices": [{"message": msg, "finish_reason": finish}]})


class AdapterTests(unittest.TestCase):
    def lane(self, post, name="mistral"):
        return make_lane(name, ENV, post=post)

    def test_reads_reply_and_served_model(self):
        text, served = self.lane(lambda *a: reply("hello", "ministral-8b-latest")).call("hi")
        self.assertEqual((text, served), ("hello", "ministral-8b-latest"))

    def test_falls_back_to_reasoning_content(self):
        text, _ = self.lane(lambda *a: reply(content=None, reasoning="thinking out loud")).call("hi")
        self.assertEqual(text, "thinking out loud")

    def test_empty_reply_is_transient_not_scored_as_answer(self):
        with self.assertRaises(Transient):
            self.lane(lambda *a: reply(content="", finish="length")).call("hi")

    def test_status_mapping(self):
        for code in (429, 503, 500):
            with self.assertRaises(Transient):
                self.lane(lambda *a, c=code: (c, "x")).call("hi")
        for code in (401, 403, 404):
            with self.assertRaises(Permanent):
                self.lane(lambda *a, c=code: (c, "nope")).call("hi")

    def test_garbage_body_is_transient(self):
        with self.assertRaises(Transient):
            self.lane(lambda *a: (200, "<html>")).call("hi")

    def test_missing_key_gives_no_lane(self):
        lanes, missing = build_lanes(ENV, ["mistral", "nvidia"])
        self.assertEqual([lane.name for lane in lanes], ["mistral"])
        self.assertEqual(missing, ["nvidia"])

    def test_request_has_bearer_header_and_honest_user_agent_and_temperature_zero(self):
        seen = {}

        def post(url, headers, body, timeout):
            seen.update(url=url, headers=headers, body=json.loads(body))
            return reply()
        self.lane(post).call("hi")
        self.assertTrue(seen["url"].endswith("/chat/completions"))
        self.assertEqual(seen["headers"]["Authorization"], "Bearer k-secret-1")
        self.assertTrue(seen["headers"]["User-Agent"].startswith("bench-runner"))
        self.assertEqual(seen["body"]["temperature"], 0)
        self.assertGreaterEqual(seen["body"]["max_tokens"], 256)

    def test_error_text_never_contains_the_key(self):
        with self.assertRaises(Permanent) as cm:
            self.lane(lambda *a: (403, "forbidden")).call("hi")
        self.assertNotIn("k-secret", str(cm.exception))

    def test_specs_are_complete(self):
        for name, (base, model, key_env) in SPECS.items():
            self.assertTrue(base.startswith("https://") and model and key_env.endswith("KEY"), name)


if __name__ == "__main__":
    unittest.main()
