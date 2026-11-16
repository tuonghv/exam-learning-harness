"""TASK-125 (REQ-0132): boundary + api hardening, one test per design item 125.1-125.7.
Fake `ask`, temp cache, no network, no paid call."""
import json
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.ingest import api, boundary, replycache, segment  # noqa: E402


def q(n):
    return ["Câu %d. Tính số %d." % (n, n), "A. a", "B. b", "C. c", "D. d"]


# two windows: w1 suspects {15}, w2 suspects {46}
LINES = (q(1) + q(2) + q(3) + ["Bài 4: x"] + q(5) + q(6) + q(7) + q(8) + q(9) + q(10) + ["Bài 11: x"])


def item(line, label="other", conf=0.9):
    return {"line": line, "label": label, "confidence": conf}


def reply(*wins):
    return json.dumps({"windows": [{"window_id": w, "items": it} for w, it in wins]})


class Ask:
    def __init__(self, text, cost=0.003):
        self.text, self.cost, self.calls = text, cost, 0

    def __call__(self, prompt):
        self.calls += 1
        return types.SimpleNamespace(ok=True, text=self.text, cost_usd=self.cost, reason="")


def wins():
    return boundary.windows(LINES, boundary.suspects(LINES))[0]


def rv_cached(ask, **kw):
    return boundary.Reviewer(ask, cache=replycache.ReplyCache(tempfile.mkdtemp()), **kw)


class Hardening(unittest.TestCase):
    def test_125_1_missing_suspect_is_invalid(self):
        w = wins()
        obj = json.loads(reply(("w1", []), ("w2", [item(46)])))
        hints, warns = boundary.validate(obj, w)
        self.assertEqual([x["reason"] for x in warns], ["missing"])
        self.assertEqual(sorted(hints), [46])

    def test_125_2_bad_cache_entry_is_miss(self):
        for bad in ([1], "0.9", {"a": 1}, [[1]], [["x", "other", 0.9]], []):
            ask = Ask(reply(("w1", [item(15)]), ("w2", [item(46)])))
            rv = rv_cached(ask)
            sha = boundary.prompt_sha256()
            rv.cache.put(boundary.NS, rv._key(wins()[0], sha), bad)
            hints = rv(LINES)  # no traceback
            self.assertEqual(ask.calls, 1, bad)
            self.assertIn(15, hints, bad)

    def test_125_3_duplicate_window_id_invalid(self):
        obj = json.loads(reply(("w1", [item(15)]), ("w1", [item(15, "passage")]), ("w2", [item(46)])))
        hints, warns = boundary.validate(obj, wins())
        self.assertEqual([(x["window"], x["reason"]) for x in warns], [("w1", "duplicate")])
        self.assertEqual(sorted(hints), [46])

    def test_125_4_dry_run_counts_window_once(self):
        rv = boundary.Reviewer(None, dry_run=True)
        rv(LINES)
        first = rv.stats["est_calls"]
        rv(LINES)
        self.assertEqual((first, rv.stats["est_calls"]), (1, 1))

    def test_125_5_trace_rows_carry_call_index(self):
        rv = rv_cached(Ask(reply(("w1", [item(15)]), ("w2", [item(46)]))))
        rv(LINES)
        self.assertEqual([r.get("call") for r in rv.trace], [1, 1])

    def test_125_6_context_line_not_glued_to_option(self):
        lines = ["Câu 5. q", "A. a", "B. b", "C. c", "D. d", "Read the following passage", "Para one.",
                 "Câu 6. y", "A. a", "B. b", "C. c", "D. d"]
        _i, qs, _ok = segment.segment(lines, hints={6: ("question_end", 0.9)})
        self.assertEqual(qs[0]["options"][-1]["text"], "d")
        self.assertEqual(qs[1]["context"], "Read the following passage\nPara one.")

    def test_125_7_gate_active_for_slice_without_keys(self):
        qs = [{"id": str(i), "text": "t", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}}
              for i in (1, 2, 3, 4)]
        for x in qs[:2]:
            x["verification"] = {"status": "verified"}
        got, skipped = api._pick_refined({"refined": {"questions": qs}}, "3-4",
                                         {"min_verification": "verified"})
        self.assertEqual(got, [])
        self.assertEqual(len(skipped), 2)


if __name__ == "__main__":
    unittest.main()
