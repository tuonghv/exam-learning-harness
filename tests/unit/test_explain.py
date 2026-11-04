"""TASK-077 (77.1-77.9): answer-driven cause table and held-out gain on synthetic fixtures. Free, temp dirs only."""
import contextlib
import inspect
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import explain, metrics  # noqa: E402

STEMS = ["A cart of mass two kilograms is pushed along a frictionless track by a constant horizontal force "
         "of six newtons for four seconds; what is its final speed in metres per second?",
         "A copper wire carries a steady current through a resistor connected to a battery of twelve volts; "
         "which statement about the power dissipated in the resistor is correct for this circuit?",
         "A lens forms a real inverted image of an object placed beyond its focal length on the optical axis; "
         "what kind of lens is described by this observation in the laboratory?"]
OPTS = [["four metres per second", "eight metres per second", "twelve metres per second", "sixteen metres per second"],
        ["it equals voltage times current", "it equals current over voltage", "it is always zero in a wire",
         "it depends only on the colour"],
        ["a converging lens", "a diverging lens", "a flat mirror", "a plain window"]]
INSTR = "Questions are numbered from 1 here; the printed exam number of question N is N + 10 (x)."


def exam(n=3, over=None):
    qs = []
    for i in range(n):
        q = {"id": i + 1, "text": STEMS[i], "stem": STEMS[i], "options": dict(zip("ABCD", OPTS[i])),
             "passage": "", "instruction": "", "section": "", "pages": [1]}
        qs.append(dict(q, **(over or {}).get(i + 1, {})))
    return {"instructions": INSTR, "questions": qs}


def pdf_pages(ex):
    body = "\n".join("%s\n%s" % (q["stem"], "\n".join("%s. %s" % kv for kv in q["options"].items()))
                     for q in ex["questions"])
    return [body, ""]


def rec(i, ans, **over):
    r = {"id": str(i), "answer": ans, "source": "text", "qa_findings": [], "checks": [], "attempts": 1,
         "uncertainty": {"level": "low", "reason": ""}, "status_reason": "", "unresolved": False, "error": None}
    r.update(over)
    return r


def write_calls(d, calls):
    os.makedirs(d)
    with open(os.path.join(d, "index.jsonl"), "w") as fh:
        for n, (tag, prompt, reply_text, pages) in enumerate(calls, 1):
            fh.write(json.dumps({"n": n, "tag": tag, "pages": pages}) + "\n")
            with open(os.path.join(d, "%03d-prompt.txt" % n), "w") as p:
                p.write(prompt)
            with open(os.path.join(d, "%03d-reply.txt" % n), "w") as p:
                p.write(reply_text)


def prompt_of(ex):
    return "\n".join("## Question %d\n\n%s\n\n%s\n" % (q["id"], q["text"], "\n".join(
        "%s. %s" % kv for kv in q["options"].items())) for q in ex["questions"])


def reply(*answers):
    return json.dumps({"questions": [{"id": str(i), "answer": a, "answer_status": "answered"}
                                     for i, a in answers]})


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ex = exam()
        self.kmap = {"11": "A", "12": "B", "13": "C"}  # printed = id + 10

    def run_ex(self, recs, calls=None, ex=None, kmap=None, pages="auto"):
        ex = ex or self.ex
        cdir = None
        if calls:
            cdir = os.path.join(self.tmp, "calls%d" % len(os.listdir(self.tmp)))
            write_calls(cdir, calls)
        pg = pdf_pages(ex) if pages == "auto" else pages
        return explain.explain({"questions": recs}, ex, cdir, pg, kmap or self.kmap, "Physics")

    # 77.2
    def test_stem_truncated_is_extraction(self):
        cut = STEMS[0][:60]
        ex = exam(1, over={1: {"text": cut, "stem": cut}})
        row = {"stem": STEMS[0], "text": cut, "options": OPTS[0], "passage": "", "opt_mode": 4, "n_source": 1}
        out = explain.extract_check(row, pdf_pages(self.ex), [])
        self.assertLess(out["rev"], explain.EXTRACT_REV_MIN)
        self.assertEqual(out["fwd"], 1.0)  # a prefix scores fwd 1.0: only rev catches it
        with mock.patch.object(explain, "RELIABLE_SHARE", 0.0):  # one-question exam: the exam-level guard is off
            kept = self.run_ex([rec(1, "B")], ex=ex, pages=pdf_pages(self.ex))[0]
        self.assertEqual((kept[0]["ext"], kept[0]["primary"]), ("fail", "extraction"))
        kept = self.run_ex([rec(1, "B")], ex=ex, pages=pdf_pages(self.ex))[0]
        self.assertEqual((kept[0]["ext"], kept[0]["primary"]), ("na", "unknown"))  # PDF text is the weak side

    def test_option_missing(self):
        row = {"stem": STEMS[0], "text": STEMS[0], "options": OPTS[0][:3], "passage": "", "opt_mode": 4, "n_source": 1}
        out = explain.extract_check(row, pdf_pages(self.ex), [])
        self.assertLess(out["opt_prompt"], out["opt_mode"])
        self.assertEqual(explain.ext_status(dict(out)), "fail")

    def test_ocr_page_is_na_ocr(self):
        row = {"stem": STEMS[0], "text": STEMS[0], "options": OPTS[0], "passage": "", "opt_mode": 4, "n_source": 1}
        out = explain.extract_check(row, [" ", ""], [])
        self.assertEqual(out["ocr_page"], 1)
        self.assertEqual(explain.ext_status(out), "na_ocr")

    def test_garbled_text_fwd_low(self):
        row = {"stem": STEMS[0][::-1], "text": STEMS[0][::-1], "options": [o[::-1] for o in OPTS[0]],
               "passage": "", "opt_mode": 4, "n_source": 1}
        self.assertLess(explain.extract_check(row, pdf_pages(self.ex), [])["fwd"], explain.EXTRACT_FWD_MIN)

    # 77.3
    def row(self, prompt, deps=(), passage="", img_pages=None, q_pages=(1,)):
        ex = exam(2, over={1: {"passage": passage, "pages": list(q_pages)}})
        return {"_q": ex["questions"][0], "_exam": ex, "_deps": list(deps), "_carrier": "1", "prompt_src": "calls",
                "_text": {"prompt": prompt}, "_image": None if img_pages is None else {"pages": img_pages}}

    def test_passage_absent_from_prompt(self):
        r = self.row("## Question 1\n\nnothing here at all", passage="The long shared passage about a pendulum "
                     "swinging in a vacuum chamber with negligible damping.")
        self.assertEqual(explain.context_check(r)["ctx_passage"], 0)
        r["_q"]["passage"] = ""
        self.assertEqual(explain.context_check(r)["ctx_passage"], "na")

    def test_sibling_block_absent(self):
        out = explain.context_check(self.row("## Question 1\n\nx\n\n## Question 3\n\ny", deps=["1", "2"]))
        self.assertEqual((out["ctx_deps_k"], out["ctx_deps_n"]), (1, 2))

    def test_image_call_missing_carrier_page(self):
        r = self.row("p", img_pages=[3], q_pages=(3,))
        r["_carrier"] = "2"
        r["_exam"]["questions"][1]["pages"] = [4]
        self.assertEqual(explain.context_check(r)["ctx_pages"], 0)
        r["_image"]["pages"] = [3, 4]
        self.assertEqual(explain.context_check(r)["ctx_pages"], 1)

    def test_context_not_delivered_cause(self):
        ex = exam(2, over={1: {"passage": "A shared passage about a long pendulum swinging in vacuum with no damping."}})
        calls = [("solve", prompt_of(self.ex), reply((1, "B"), (2, "B")), None)]
        kept = self.run_ex([rec(1, "B")], calls, ex=ex)[0]
        self.assertEqual(kept[0]["ctx_passage"], 0)
        self.assertEqual(kept[0]["primary"], "context_not_delivered")

    # 77.4 / 77.6
    def test_two_json_objects_text_agrees_is_reply_path(self):
        obj = json.dumps({"questions": [{"id": "1", "answer": "A", "answer_status": "answered"}]})
        calls = [("retry", prompt_of(self.ex), obj + "\nwait, again:\n" + obj, None)]
        kept, multi, _n, _ok = self.run_ex([rec(1, "B", unresolved=True)], calls)
        self.assertEqual((kept[0]["multi_json"], multi), (2, 1))
        self.assertEqual(kept[0]["text_agrees_key"], 1)
        self.assertEqual(kept[0]["primary"], "reply_path")

    def test_image_only(self):
        r = rec(1, "B", source="image", qa_findings=[{"source": "image", "code": "image_answer", "message": "x"}])
        kept = self.run_ex([r])[0]
        self.assertEqual(kept[0]["src"], "image")
        self.assertEqual(kept[0]["primary"], "image_only")

    def test_image_agrees_key_text_kept_is_reply_path(self):
        r = rec(1, "B", source="text+image", qa_findings=[
            {"source": "image", "code": "image_differs", "message": "image answer: A"}],
            status_reason="needs_review: text/image differ")
        kept = self.run_ex([r])[0]
        self.assertEqual((kept[0]["text_image_differ"], kept[0]["image_agrees_key"]), (1, 1))
        self.assertEqual(kept[0]["primary"], "reply_path")

    def test_marker_with_full_text_is_reply_path(self):
        ex = exam(over={1: {"text": STEMS[0] + "\n[Incomplete: missing_text figure]"}})
        r = rec(1, None, status_reason="solver_declined: missing_text")
        kept = self.run_ex([r], ex=ex, pages=pdf_pages(self.ex))[0]
        self.assertEqual(kept[0]["marker"], 1)
        self.assertEqual(kept[0]["primary"], "reply_path")

    def test_call_failed_is_infrastructure(self):
        r = rec(1, "B", unresolved=True, error={"cls": "rate_limit", "message": "x"},
                qa_findings=[{"source": "deterministic", "code": "call_failed", "message": "limit"}])
        self.assertEqual(self.run_ex([r])[0][0]["primary"], "infrastructure")

    def test_recompute_matching_final_is_key_oddity_candidate(self):
        ex = exam(over={1: {"options": {"A": "4", "B": "8", "C": "12", "D": "16"}}})
        chk = {"kind": "computed", "independent": True, "result": "pass",
               "detail": "arithmetic only: 2*4 = 8, answer 8"}
        kept = self.run_ex([rec(1, "B", checks=[chk])], ex=ex, pages=pdf_pages(ex))[0]
        self.assertEqual((kept[0]["recompute"], kept[0]["recompute_is_final"]), ("pass", 1))
        self.assertEqual(kept[0]["primary"], "key_oddity_candidate")
        kept = self.run_ex([rec(1, "B")], ex=ex, pages=pdf_pages(ex))[0]
        self.assertEqual((kept[0]["recompute"], kept[0]["primary"]), ("na", "solver_reasoning"))

    def test_quote_not_in_prompt(self):
        chk = {"kind": "quote", "detail": "verbatim in passage/question: a sentence the prompt never held"}
        calls = [("solve", prompt_of(self.ex), reply((1, "B")), None)]
        kept = self.run_ex([rec(1, "B", checks=[chk])], calls)[0]
        self.assertEqual((kept[0]["quotes_n"], kept[0]["quotes_in_prompt"]), (1, 0))

    def test_priority_earlier_cause_wins(self):
        base = {"outcome": "wrong", "call_failed": 1, "unresolved": 1, "ext": "fail", "marker": 0}
        self.assertEqual(explain.primary(dict(base)), "infrastructure")
        self.assertEqual(explain.primary(dict(base, call_failed=0)), "extraction")
        self.assertEqual(explain.primary(dict(base, call_failed=0, ext="ok", ctx_pages=0)), "context_not_delivered")

    def test_flagged_right_uses_none(self):
        r = rec(1, "A", status_reason="needs_review: x")
        self.assertEqual(self.run_ex([r])[0][0]["primary"], "none")
        self.assertEqual(self.run_ex([rec(1, "A")])[0], [])  # right and not flagged: no row

    # AC2: no key letter, exam text or message in any output
    def test_tsv_cells_never_hold_a_letter_or_text(self):
        recs = [rec(1, "C", source="text+image", qa_findings=[
                {"source": "image", "code": "image_differs", "message": "image answer: A"}]),
                rec(2, "D", uncertainty={"level": "low", "reason": "option B also fits; " + STEMS[1]}),
                rec(3, None, status_reason="solver_declined: missing_text", unresolved=True)]
        calls = [("solve", prompt_of(self.ex), reply((1, "C"), (2, "D")), None)]
        kept = self.run_ex(recs, calls)[0]
        self.assertEqual(len(kept), 3)
        out = explain.tsv(kept) + "\n" + explain.footer(kept, 0, True)
        enum = set(explain.CAUSES) | set(explain.SRC) | {"wrong", "not_answered", "flagged_right", "calls", "exam",
                                                          "ok", "fail", "pass", "Physics"}
        for ln in out.splitlines()[1:]:
            if ln.startswith("#"):
                continue
            for cell in ln.split("\t"):
                self.assertTrue(re.fullmatch(r"-?[0-9.]+|na|na_ocr", cell) or cell in enum, cell)
        self.assertNotIn("cart of mass", out)
        js = json.dumps([{c: r.get(c) for c in explain.COLUMNS} for r in kept])
        self.assertNotRegex(js, r'": "[A-D]"')

    def test_checks_take_no_key(self):
        for fn in (explain.extract_check, explain.context_check, explain.path_check, explain.solver_check,
                   explain.primary, explain.join, explain.run_extract):
            self.assertNotIn("key", inspect.signature(fn).parameters, fn.__name__)
        self.assertIn("key", inspect.signature(explain.score_rows).parameters)

    def test_key_loader_pairs_numbers_and_letters(self):
        p = os.path.join(self.tmp, "k.txt")
        with open(p, "w") as fh:
            fh.write("Dap an 2026\nCau Dap an\n1\nD\n2\nB\nCau 3\tA\n31. c\n")
        self.assertEqual(explain.load_key(p), {"1": "D", "2": "B", "3": "A", "31": "C"})

    # 77.7 / 77.9 cli
    def test_cli_explain_and_board_helpers(self):
        d = os.path.join(self.tmp, "run")
        os.makedirs(d)
        with open(d + "/result.json", "w") as fh:
            json.dump({"questions": [rec(1, "B")], "exam": {"subject": "Physics"}}, fh)
        exp = os.path.join(self.tmp, "exam.md")
        with open(exp, "w") as fh:
            fh.write("# Exam Input\n\nSubject: Physics\nLevel: x\nExam type: t\nTask: Multiple Choice\n"
                     "Mode: Solve\nLanguage: en\n\n## Instructions\n\n" + INSTR + "\n\n## Question 1\n\n"
                     "### Question text\n\n" + STEMS[0] + "\n\nA. one\nB. two\nC. three\nD. four\n")
        ans = os.path.join(self.tmp, "answers.txt")
        with open(ans, "w") as fh:
            fh.write("11 A\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.run_stats_main(["explain", d, "--exam", exp, "--key", ans])
        self.assertEqual(code, 0)
        self.assertIn("n_wrong=1", buf.getvalue())
        tsv = os.path.join(self.tmp, "e.tsv")
        with open(tsv, "w") as fh:
            fh.write(buf.getvalue())
        bad = os.path.join(self.tmp, "bad.txt")
        with open(bad, "w") as fh:
            fh.write("99 A\n")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(cli.run_stats_main(["explain", d, "--exam", exp, "--key", bad]), 2)
        self.assertIn("key matches 0 of 1 ids", err.getvalue())
        self.assertIn("(wrong 1, flagged-right 0)", metrics.causes_text([tsv]))

    def test_board_without_new_flags_prints_neither_table(self):
        hist = os.path.join(self.tmp, "h.jsonl")
        with open(hist, "w") as fh:
            fh.write("")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.run_stats_main(["board", "--history", hist])
        self.assertNotIn("causes", buf.getvalue())
        self.assertNotIn("gain", buf.getvalue())

    # 77.8 gain
    def gain_spec(self, before, after, learn="L", name="H", n=40):
        keyf = os.path.join(self.tmp, "gold%d.txt" % len(os.listdir(self.tmp)))
        with open(keyf, "w") as fh:
            fh.write("\n".join("%d A" % (i + 1) for i in range(n)))
        runs = {}
        for tag, correct in (("b", before), ("a", after)):
            d = os.path.join(self.tmp, "g%s%d" % (tag, len(os.listdir(self.tmp))))
            os.makedirs(d)
            qs = [{"id": str(i + 1), "answer": "A" if i in correct else "B"} for i in range(n)]
            with open(d + "/result.json", "w") as fh:
                json.dump({"questions": qs}, fh)
            runs[tag] = [d]
        return {"exams": {name: {"key": keyf}}, "changes": [{"change": "C1", "learn": learn, "runs": [
            {"exam": name, "before": runs["b"], "after": runs["a"]}]}]}

    def test_gain_numbers_and_verdicts(self):
        spec = self.gain_spec(set(range(0, 20)), set(range(0, 34)))  # 14 fixed, 0 regressed, n 40
        row = metrics.gain_rows(spec)[0]
        self.assertEqual((row["n"], row["before_k"], row["after_k"], row["fixed"], row["regressed"]),
                         (40, 20, 34, 14, 0))
        self.assertAlmostEqual(row["before_lo"], 0.352, places=3)  # Wilson 95% of 20/40, by hand
        self.assertAlmostEqual(row["before_hi"], 0.648, places=3)
        self.assertEqual((row["noise_flips"], row["noise_src"], row["flag"]), (2, "assumed_5pct", "-"))
        self.assertEqual((row["role"], row["verdict"]), ("heldout", "heldout_gain"))
        learn = metrics.gain_rows(self.gain_spec(set(range(0, 20)), set(range(0, 34)), learn="H"))[0]
        self.assertEqual((learn["role"], learn["verdict"]), ("learn", "learn_only"))

    def test_gain_small_n_and_not_decisive(self):
        row = metrics.gain_rows(self.gain_spec(set(range(0, 20)), set(range(0, 24))))[0]  # 4 fixed
        self.assertEqual(row["flag"], "small_n")
        self.assertEqual(row["verdict"], "no_measurable_change")  # 4 flips < MIN_FLIPS: not decisive
        self.assertIn("# a learn-exam gain is not evidence; claim only heldout_gain", metrics.gain_tsv([row]))

    def test_gain_loss(self):
        row = metrics.gain_rows(self.gain_spec(set(range(0, 34)), set(range(0, 20))))[0]
        self.assertEqual(row["verdict"], "heldout_loss")

    def test_english_physics_fixture_end_to_end(self):
        calls = [("solve", prompt_of(self.ex), reply((1, "B"), (2, "B"), (3, "A")), None)]
        kept, multi, matched, ok = self.run_ex([rec(1, "B"), rec(2, "B"), rec(3, "A")], calls)
        self.assertEqual((len(kept), multi, matched, ok), (2, 0, 3, True))
        self.assertEqual({r["printed"]: r["primary"] for r in kept}, {11: "solver_reasoning", 13: "solver_reasoning"})


if __name__ == "__main__":
    unittest.main()
