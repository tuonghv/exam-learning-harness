"""TASK-109 (docs/design/phase-109-claude-adapter.md): _classify narrowing, extract_json brace-in-prose."""
import json
import os
import sys
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import engine  # noqa: E402
from exam_engine.adapters import claude as L  # noqa: E402


class Classify(unittest.TestCase):
    def test_109_1_prompt_too_long_is_other(self):
        self.assertEqual(L._classify("Prompt is too long: 215003 tokens > 200000 maximum"), "other")

    def test_109_1_digits_and_words_not_blocking(self):
        for t in ("processed 5000 rows", 'duration_ms": 401',
                  '{"service_tier":"standard","is_error":true}', "uuid 1a2b-5029-cafe",
                  "login form question", "network of roads", "connection between A and B",
                  "image unavailable"):
            self.assertEqual(L._classify(t), "other", t)

    def test_109_1_real_errors_keep_class(self):
        for t, cls in (('API Error: 401 {"type":"authentication_error"}', "auth"),
                       ('API Error: 429 {"type":"rate_limit_error"}', "rate_limit"),
                       ('API Error: 500 {"type":"api_error"}', "service"),
                       ("API Error: 529 Overloaded", "rate_limit"),
                       ("Connection error.", "service"),
                       ("Invalid API key · Please run /login", "auth"),
                       ("status code 503", "service"),
                       ("429 rate limit hit", "rate_limit")):
            self.assertEqual(L._classify(t), cls, t)

    def test_109_1_run_with_prompt_too_long_not_blocking(self):
        out = json.dumps({"type": "result", "is_error": True, "total_cost_usd": 0.0,
                          "result": "Prompt is too long: 215003 tokens > 200000 maximum"})
        run = lambda argv, **kw: types.SimpleNamespace(returncode=0, stdout=out, stderr="")
        c = L.run_claude("p", model="sonnet", timeout_s=5, runner=run)
        self.assertFalse(c.ok)
        self.assertNotIn(c.cls, engine.BLOCKING)


class Extract(unittest.TestCase):
    def test_109_2_brace_in_prose_before(self):
        self.assertEqual(L.extract_json('Since \\frac{1}{2} > 0. {"answer": "A"}'), ({"answer": "A"}, None))
        self.assertEqual(L.extract_json('Since \\frac{1}{2} > 0. {"answer": "A"}', {"type": "object"})[0],
                         {"answer": "A"})

    def test_109_2_brace_in_prose_after(self):
        self.assertEqual(L.extract_json('{"a": 1} then the set {x}'), ({"a": 1}, None))

    def test_109_2_inner_fragment_not_returned(self):
        for t in ('{"answers": [{"q": 1}', '{"a": {"b": 1}, broken}'):
            self.assertEqual(L.extract_json(t), (None, "no valid JSON object found"), t)

    def test_109_2_two_objects_still_rejected(self):
        self.assertEqual(L.extract_json('{"a":1} x {"a":2}'), (None, "no valid JSON object found"))

    def test_109_2_objects_unchanged(self):
        self.assertEqual(L._objects('x {"a":1} y {"b":[1,{"c":2}]} z'), [{"a": 1}, {"b": [1, {"c": 2}]}])
        self.assertEqual(L._objects('{bad} {"a":1}'), [{"a": 1}])
        self.assertEqual(L._objects("no json {"), [])


if __name__ == "__main__":
    unittest.main()
