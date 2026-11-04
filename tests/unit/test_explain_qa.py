"""TASK-077 QA: priority chain, thresholds, key leak over every output form, rate-limit shapes. Free, synthetic."""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exam_engine import cli  # noqa: E402
from exam_engine.adapters import claude as L  # noqa: E402
from exam_engine.pipeline import explain, metrics  # noqa: E402
import test_explain as TE  # noqa: E402

ALL_SIGNALS = {"outcome": "wrong", "call_failed": 1, "unresolved": 1, "ext": "fail", "ctx_pages": 0,
               "text_agrees_key": 1, "final_agrees_key": 0, "marker": 1, "_key_oddity": True, "src": "image"}


class Priority(unittest.TestCase):
    # 77.6 every adjacent pair of the documented order: the earlier cause wins while later signals stay set
    def test_77_6_full_chain_in_order(self):
        row = dict(ALL_SIGNALS, text_agrees_key=1)
        want = ["infrastructure", "extraction", "context_not_delivered", "reply_path"]
        drop = [("call_failed", 0), ("ext", "ok"), ("ctx_pages", 1)]
        got = [explain.primary(dict(row))]
        for k, v in drop:
            row[k] = v
            got.append(explain.primary(dict(row)))
        self.assertEqual(got, want)

    def test_77_6_tail_of_chain(self):
        base = {"outcome": "wrong", "ext": "ok", "text_agrees_key": "na", "final_agrees_key": 0, "marker": 0,
                "src": "image"}
        self.assertEqual(explain.primary(dict(base, _key_oddity=True)), "key_oddity_candidate")
        self.assertEqual(explain.primary(dict(base)), "image_only")
        self.assertEqual(explain.primary(dict(base, src="text")), "solver_reasoning")
        self.assertEqual(explain.primary(dict(base, src="text", ext="na")), "unknown")
        self.assertEqual(explain.primary(dict(base, src="text", ext="na_ocr")), "unknown")

    def test_77_6_reply_path_beats_key_oddity_and_image_only(self):
        row = dict(ALL_SIGNALS, call_failed=0, ext="ok", ctx_pages=1)
        self.assertEqual(explain.primary(row), "reply_path")

    def test_77_2_threshold_boundaries(self):
        ok = {"fwd": explain.EXTRACT_FWD_MIN, "rev": explain.EXTRACT_REV_MIN, "opt_prompt": 4, "opt_mode": 4,
              "ocr_page": 0}
        self.assertEqual(explain.ext_status(dict(ok)), "ok")
        self.assertEqual(explain.ext_status(dict(ok, fwd=explain.EXTRACT_FWD_MIN - 0.001)), "fail")
        self.assertEqual(explain.ext_status(dict(ok, rev=explain.EXTRACT_REV_MIN - 0.001)), "fail")
        # literal values: moving a constant must break this (calibrated 0.85 / 0.63)
        self.assertEqual(explain.ext_status(dict(ok, fwd=0.84)), "fail")
        self.assertEqual(explain.ext_status(dict(ok, fwd=0.86)), "ok")
        self.assertEqual(explain.ext_status(dict(ok, rev=0.62)), "fail")
        self.assertEqual(explain.ext_status(dict(ok, rev=0.64)), "ok")
        self.assertEqual(explain.ext_status(dict(ok, opt_prompt=3)), "fail")
        self.assertEqual(explain.ext_status(dict(ok, rev=None)), "ok")

    def test_77_2_unreliable_pdf_never_blames_extraction(self):
        good = {"fwd": 1.0, "rev": 1.0, "opt_prompt": 4, "opt_mode": 4, "ocr_page": 0}
        bad = dict(good, rev=0.2)
        rows = [dict(bad) for _ in range(5)] + [dict(good)]
        self.assertFalse(explain.set_ext(rows))
        self.assertEqual({r["ext"] for r in rows[:5]}, {"na"})
        self.assertEqual(rows[5]["ext"], "ok")
        rows = [dict(bad)] + [dict(good) for _ in range(5)]
        self.assertTrue(explain.set_ext(rows))  # 5/6 >= 0.8
        self.assertEqual(rows[0]["ext"], "fail")
        edge = [dict(bad)] + [dict(good) for _ in range(4)]  # exactly 0.8 reliable
        self.assertTrue(explain.set_ext(edge))
        edge = [dict(bad), dict(bad)] + [dict(good) for _ in range(7)]  # 7/9 < 0.8
        self.assertFalse(explain.set_ext(edge))


class Leak(unittest.TestCase):
    """The key reaches only score_rows; no output form shows a letter next to a number or exam text."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_77_7_every_output_form(self):
        d = os.path.join(self.tmp, "run")
        os.makedirs(d)
        recs = [TE.rec(1, "B"), TE.rec(2, "D", status_reason="needs_review: x"), TE.rec(3, None, unresolved=True,
                status_reason="solver_declined: x")]
        with open(d + "/result.json", "w") as fh:
            json.dump({"questions": recs, "exam": {"subject": "Physics"}}, fh)
        exp = os.path.join(self.tmp, "exam.md")
        body = "".join("\n## Question %d\n\n### Question text\n\n%s\n\n%s\n" % (
            i + 1, TE.STEMS[i], "\n".join("%s. %s" % kv for kv in zip("ABCD", TE.OPTS[i]))) for i in range(3))
        with open(exp, "w") as fh:
            fh.write("# Exam Input\n\nSubject: Physics\nLevel: x\nExam type: t\nTask: Multiple Choice\n"
                     "Mode: Solve\nLanguage: en\n\n## Instructions\n\n" + TE.INSTR + "\n" + body)
        ans = os.path.join(self.tmp, "a.txt")
        with open(ans, "w") as fh:
            fh.write("11 A\n12 C\n13 D\n")
        outs = []
        for extra in ([], ["--json"]):
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                self.assertEqual(cli.run_stats_main(["explain", d, "--exam", exp, "--key", ans] + extra), 0)
            outs += [o.getvalue(), e.getvalue()]
        tsv = os.path.join(self.tmp, "e.tsv")
        with open(tsv, "w") as fh:
            fh.write(outs[0])
        outs.append(metrics.causes_text([tsv]))
        txt = "\n".join(outs)
        self.assertIn("flagged_right", txt)  # the run produced rows
        for n, v in (("11", "A"), ("12", "C"), ("13", "D"), ("1", "A"), ("2", "C"), ("3", "D")):
            self.assertNotRegex(txt, r"(?<!\d)%s\s*[.:)=\-]?\s*\(?%s\)?(?![A-Za-z0-9])" % (n, v))
        for t in TE.STEMS + [o for g in TE.OPTS for o in g]:
            self.assertNotIn(t, txt)
        for ln in outs[0].splitlines():
            if not ln.startswith("#") and "\t" in ln:
                self.assertFalse([c for c in ln.split("\t") if re.fullmatch(r"[A-Da-d]", c)], ln)

    def test_77_6_leak_guard_bites_on_a_printed_letter(self):
        # the cell whitelist of test_explain would reject a letter cell; prove the matcher used here catches one
        bad = "59\t29\tEnglish\twrong\treply_path\tB"
        self.assertTrue([c for c in bad.split("\t") if re.fullmatch(r"[A-Da-d]", c)])
        self.assertTrue(re.search(r"(?<!\d)59\s*[.:)=\-]?\s*\(?B\)?(?![A-Za-z0-9])", "59: B"))


class Fake(object):
    def __init__(self, rc=0, out="", err=""):
        self.rc, self.out, self.err = rc, out, err

    def __call__(self, argv, **kw):
        return type("P", (), {"returncode": self.rc, "stdout": self.out, "stderr": self.err})()


class RateLimit(unittest.TestCase):
    # 77.11
    def test_77_11_usage_limit_shapes_stop_the_run(self):
        for msg in ("You've hit your 5-hour limit · resets 2pm (Asia/Ho_Chi_Minh)",
                    "You've hit your 5-hour limit. Resets 2pm",
                    "Claude AI usage limit reached|1760000000",
                    "5-hour limit reached - resets 2pm"):
            for f in (Fake(rc=1, err=msg), Fake(out=json.dumps({"is_error": True, "result": msg}))):
                c = L.run_claude("p", model="m", timeout_s=3, runner=f)
                self.assertEqual((c.ok, c.cls), (False, "rate_limit"), msg)
                self.assertIn(c.cls, __import__("exam_engine.engine", fromlist=["x"]).BLOCKING)

    def test_77_11_normal_answer_about_limits_is_not_an_error(self):
        txt = "The limit of a function as x tends to 0 is 1; we hit your 5-hour limit-style case: usage limit n/a"
        c = L.run_claude("p", model="m", timeout_s=3, runner=Fake(out=json.dumps({"result": txt})))
        self.assertEqual((c.ok, c.cls, c.text), (True, "", txt))

    def test_77_11_classifier_not_too_broad(self):
        for msg in ("could not compute the limit of a function", "limit exceeded in loop", "something hit you",
                    "the hour hand", "boom"):
            self.assertEqual(L._classify(msg), "other", msg)


if __name__ == "__main__":
    unittest.main()
