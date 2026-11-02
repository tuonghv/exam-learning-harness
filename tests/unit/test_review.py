"""TASK-052 / REQ-0055: human review path (synthetic data only, no real exam text)."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import review  # noqa: E402


def q(i, ans="A", status="PASS", level="low", checks=None):
    return {"id": str(i), "answer": ans, "solution": ["step one", "step two"], "explanation": "why",
            "uncertainty": {"level": level, "reason": "r"}, "checks": checks or [],
            "verification_status": status, "status_reason": "x"}


def exam_md(n, extra=None):
    out = ["# Exam Input", ""]
    for i in range(1, n + 1):
        body = (extra or {}).get(i, "Synthetic stem %d?\n\nA. a\nB. b\nC. c\nD. d" % i)
        out += ["## Question %d" % i, "", body, ""]
    return "\n".join(out)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.t = self.tmp.name
        self.out = os.path.join(self.t, "review")

    def w(self, name, text):
        p = os.path.join(self.t, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def result(self, qs, name="r.json"):
        return self.w(name, json.dumps({"questions": qs}))

    def pack(self, sub, qs, n=3, offset=0, refined=None, extra=None, *more):
        r = self.result(qs, sub + ".json")
        e = self.w(sub + ".md", exam_md(n, extra))
        return review.pack("X1", sub, r, e, refined, offset, self.out, *more)

    def read(self, *p):
        with open(os.path.join(self.out, "X1", *p), encoding="utf-8") as fh:
            return fh.read()

    def run_cli(self, *argv):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            rc = cli.main(list(argv))
        return rc, o.getvalue(), e.getvalue()

    def fill(self, sub, n, line):
        txt = self.read(sub + ".md").split("\n")
        i = next(k for k, ln in enumerate(txt) if ln.startswith("## Q%d " % n))
        j = next(k for k in range(i, len(txt)) if txt[k].startswith("Your review:"))
        txt[j] = line
        with open(os.path.join(self.out, "X1", sub + ".md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(txt))


def tick(w, correct="_", kind="extraction|solution|flawed|other", note=""):
    b = {k: "[x]" if k == w else "[ ]" for k in ("agree", "disagree", "unsure")}
    return "Your review: %(agree)s agree %(disagree)s disagree %(unsure)s unsure | correct: %(c)s | kind: %(k)s | note: %(n)s" % dict(
        b, c=correct, k=kind, n=note)


class PackTests(Base):
    def test_1_counts_numbers_flags(self):
        ref = self.w("ref.json", json.dumps({"refined": {"questions": [
            {"id": "32", "page": 7, "needs_review": True, "text": "t", "options": {}}]}}))
        self.pack("Eng", [q(1), q(2, "C", "UNCERTAIN", "high"), q(3)], offset=30, refined=ref)
        t = self.read("Eng.md")
        self.assertEqual(t.count("\n## Q"), 3)
        self.assertIn("## Q31  p.-  PASS  answer A  conf high", t)
        self.assertIn("## Q32  p.7  UNCERTAIN  answer C  conf low", t)
        self.assertIn("Flags: needs_review", t)
        self.assertIn("Synthetic stem 2?", t)

    def test_1b_missing_refined_ok(self):
        self.pack("Eng", [q(1)], n=1)
        self.assertIn("p.-", self.read("Eng.md"))

    def test_2_declined_and_incomplete(self):
        self.pack("M", [q(1, None, "UNCERTAIN", "high"), q(2)], n=2,
                  extra={2: "Stem\n[Incomplete: missing_text table]"})
        t = self.read("M.md")
        self.assertIn("## Q1  p.-  UNCERTAIN  answer -  conf low", t)
        self.assertIn("Flags: declined", t)
        self.assertIn("Flags: incomplete", t)

    def test_3_index_and_overwrite_scope(self):
        self.pack("A", [q(1), q(2)], n=2)
        self.pack("B", [q(1)], n=1, offset=30)
        idx = self.read("INDEX.md")
        self.assertEqual(idx.count("\n| A |"), 2)
        self.assertEqual(idx.count("\n| B |"), 1)
        self.assertIn("How to review", idx)
        before = self.read("A.md")
        self.pack("B", [q(1, "B")], n=1, offset=30)
        self.assertEqual(self.read("A.md"), before)
        self.assertIn("answer B", self.read("B.md"))

    def test_6_scope_guards(self):
        r = self.result([q(1)])
        e = self.w("e.md", exam_md(1))
        for bad in ("examples", "evals", "tests"):
            with self.assertRaises(ValueError):
                review.pack("X1", "A", r, e, None, 0, os.path.join(ROOT, bad, "sub"))
        with self.assertRaises(ValueError):
            review.pack("../x", "A", r, e, None, 0, self.out)
        self.pack("A", [q(1)], n=1)
        files = [os.path.relpath(os.path.join(dp, f), self.t) for dp, _, fs in os.walk(self.t) for f in fs]
        self.assertTrue(all(f.startswith(("review", "A.", "e.")) or f.endswith((".json", ".md")) for f in files))
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, "X1"))), ["A.md", "INDEX.md"])
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            self.assertIn("/review/", fh.read().split("\n"))

    def test_7_idempotent_and_marks_kept(self):
        self.pack("A", [q(1), q(2)], n=2)
        first = self.read("A.md")
        self.pack("A", [q(1), q(2)], n=2)
        self.assertEqual(self.read("A.md"), first)
        mark = tick("disagree", "B", "solution", "mine")
        self.fill("A", 2, mark)
        _, msg = self.pack("A", [q(1), q(2, "C")], n=2)
        self.assertIn("merged 1", msg)
        t = self.read("A.md")
        self.assertIn(mark, t)
        self.assertIn("answer C", t)
        _, msg = self.pack("A", [q(1)], n=1)
        self.assertIn("A.new.md", msg)
        self.assertIn(mark, self.read("A.md"))
        review.pack("X1", "A", self.result([q(1), q(2)]), self.w("e2.md", exam_md(2)), None, 0, self.out, True)
        self.assertNotIn(mark, self.read("A.md"))


class ApplyTests(Base):
    def test_4_round_trip(self):
        self.pack("A", [q(i) for i in (1, 2, 3, 4)], n=4, extra={4: "S\n[Incomplete: missing_text t]"})
        self.fill("A", 1, tick("agree"))
        self.fill("A", 2, tick("disagree", "B", "solution", "secret note"))
        self.fill("A", 3, tick("unsure"))
        self.fill("A", 4, tick("agree"))
        rc, out, _ = self.run_cli("review-apply", "--exam-id", "X1", "--out", self.out)
        self.assertEqual(rc, 0)
        self.assertIn("agree 2, disagree 1, unsure 1, blank 0, unparsed 0", out)
        self.assertIn("Wilson", out)
        self.assertIn("Q2 (solution, correct B)", out)
        self.assertIn("agreed but engine doubtful: Q4", out)
        imp = self.read("improvements.md")
        self.assertIn("solution: A Q2", imp)
        self.assertNotIn("secret", imp)
        self.assertNotIn("Synthetic", imp)

    def test_5_malformed_unparsed(self):
        self.pack("A", [q(1), q(2), q(3), q(4)], n=4)
        self.fill("A", 1, tick("agree").replace("[ ] disagree", "[x] disagree"))
        self.fill("A", 2, tick("agree", correct="Z"))
        self.fill("A", 3, tick("agree", kind="banana"))
        self.fill("A", 4, "Your review: garbage")
        rc, out, _ = self.run_cli("review-apply", "--exam-id", "X1", "--out", self.out)
        self.assertEqual(rc, 0)
        self.assertIn("unparsed 4", out)
        self.assertIn("agree 0", out)

    def test_blank_pack_counts_zero(self):
        self.pack("A", [q(1), q(2)], n=2)
        rc, out, _ = self.run_cli("review-apply", "--exam-id", "X1", "--out", self.out)
        self.assertIn("agree 0, disagree 0, unsure 0, blank 2, unparsed 0; agreement n/a", out)

    def test_cli_pack_and_errors(self):
        r = self.result([q(1)])
        e = self.w("e.md", exam_md(1))
        rc, out, _ = self.run_cli("review-pack", "--exam-id", "X1", "--subject", "A", "--result", r,
                                  "--exam", e, "--out", self.out)
        self.assertEqual(rc, 0)
        rc, _, err = self.run_cli("review-apply", "--exam-id", "nope", "--out", self.out)
        self.assertEqual(rc, 2)
        self.assertIn("ERROR", err)


if __name__ == "__main__":
    unittest.main()
