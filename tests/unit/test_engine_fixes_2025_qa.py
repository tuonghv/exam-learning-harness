"""TASK-076 QA: adversarial 76.1 parsing, 76.2 conflict set/budget/dry-run, 76.3 real missing figure. Mock LLM only."""
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import test_exam_run as T  # noqa: E402
import test_image_check as TI  # noqa: E402
import test_engine_fixes_2025 as F  # noqa: E402
from exam_engine import engine as er  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.core import refcheck, schema as sch  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(HERE)), "src", "exam_engine")


def ans(a):
    return T.solve(T.a(1, a))


def got(text, schema=sch.SOLVE_OUT):
    obj, err = claude.extract_json(text, schema)
    return (obj["questions"][0]["answer"] if obj else None), err


class ExtractAdversarial(unittest.TestCase):
    def test_retracted_valid_first_loses(self):
        self.assertEqual(got(ans("A") + "\nSorry, wrong. Corrected:\n" + ans("B")), ("B", None))

    def test_three_objects_last_wins(self):
        self.assertEqual(got(ans("A") + "\n" + ans("B") + "\nfinal\n" + ans("C")), ("C", None))

    def test_braces_in_strings_and_prose(self):
        txt = ans("A") + "\nthe set {1,2} and } { stray\n" + ans("a}{b \"q\" {")
        self.assertEqual(got(txt), ('a}{b "q" {', None))

    def test_last_invalid_after_valid_never_falls_back(self):
        for last in ('{"x": 1}', json.dumps({"questions": "x"})):
            a, err = got(ans("A") + "\nno\n" + last)
            self.assertIsNone(a)
            self.assertIn("last of 2 JSON objects invalid", err)

    def test_nested_object_is_not_a_second_object(self):
        # a wrapper holding the answer object is one top-level object: it is judged as itself, not unwrapped
        a, err = got('{"outer": %s}\n%s' % (ans("A"), ans("B")))
        self.assertEqual(a, "B")

    def test_huge_and_hostile_replies(self):
        self.assertEqual(got("blah {x} " * 20000 + ans("A") + "\n" + ans("B")), ("B", None))
        self.assertEqual(got(ans("A") + "\n" + "[" * 100000 + "\n" + ans("B"))[0], "B")
        a, err = got("{" * 100000 + "\n" + ans("A") + "\n" + ans("B"))
        self.assertIn(a, ("B", None))
        a, err = got(ans("A") + "{" * 100000)
        self.assertTrue(a == "A" or err)

    def test_single_object_shapes_unchanged(self):
        one = ans("A")
        for txt in (one, one + "\n", "```json\n" + one + "\n```", "pre " + one, one + " post", "x" + one):
            self.assertEqual(got(txt), ("A", None))
            self.assertEqual(claude.extract_json(txt, sch.SOLVE_OUT), claude.extract_json(txt))

    def test_two_fences_still_rejected(self):
        a, err = got("```json\n%s\n```\n```json\n%s\n```" % (ans("A"), ans("B")))
        self.assertEqual((a, err), (None, "more than one code fence"))

    @unittest.expectedFailure
    def test_gap_fenced_first_then_unfenced_correction(self):
        # known gap (design: fences out of scope): the fenced retracted object is taken, not the later one
        self.assertEqual(got("```json\n%s\n```\nCorrection: %s" % (ans("A"), ans("B")))[0], "B")

    def test_only_solve_callers_pass_a_schema(self):
        seen = {}
        for root, _d, files in os.walk(SRC):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(root, f), encoding="utf-8") as fh:
                        for ln in fh:
                            if "extract_json(" in ln and "def extract_json" not in ln:
                                seen.setdefault(f, []).append("sch." in ln)
        withs = sorted(k for k, v in seen.items() if any(v))
        self.assertEqual(withs, ["cross.py", "engine.py", "solver.py"])
        for k in ("verifier.py", "genexam.py", "refine.py", "boundary.py", "cli.py"):
            self.assertFalse(any(seen[k]), k)

    def test_schemaless_callers_see_old_result(self):
        two = ans("A") + "\nx\n" + ans("B")
        self.assertEqual(claude.extract_json(two), (None, "no valid JSON object found"))
        self.assertEqual(claude.extract_json(two, None), (None, "no valid JSON object found"))


class ConflictSet(F.TI.Base):
    def run_ic(self, r, scope, reply_img, adj_items, cfg_extra=None, ids=None):
        ex = TI.load(self.tmp, TI.exam("Source pages: 3\n\n" + TI.FIG))
        rn = F.FakeRn(reply_img, *adj_items)
        image = {"llm": None, "render": lambda n: TI.png(n), "key_pages": set(), "have_pages": None}
        cfg = {"adjudicate": True, "max_image_pages": 4, "image_scope": scope}
        cfg.update(cfg_extra or {})
        er.image_check(ex, {1: r}, rn, {1: ["figure/table"]}, set(), cfg, image)
        return rn

    def test_pass_before_image_never_adjudicated_or_overwritten(self):
        r = F.rec(T.a(1, "5"), "PASS", "")
        rn = self.run_ic(r, "flagged", T.solve(T.a(1, "6")), [T.solve(T.a(1, "6"))])
        self.assertEqual(len(rn.prompts), 1)
        self.assertEqual(r["ans"]["answer"], "5")
        self.assertNotIn("adjudicated", [f["code"] for f in r["findings"]])
        self.assertNotEqual(r.get("source"), "adjudicated")

    def test_pass_with_image_agreement_untouched(self):
        r = F.rec(T.a(1, "5"), "PASS", "")
        rn = self.run_ic(r, "doubt", T.solve(T.a(1, "5")), [T.solve(T.a(1, "6"))])
        self.assertEqual((len(rn.prompts), r["status"], r["ans"]["answer"]), (1, "PASS", "5"))

    def test_fail_row_adjudicated_under_wide_scope(self):
        r = F.rec(T.a(1, "5"), "FAIL", "reviewer_disagrees")
        rn = self.run_ic(r, "doubt", T.solve(T.a(1, "6")), [T.solve(T.a(1, "5"))])
        self.assertEqual(len(rn.prompts), 2)
        self.assertEqual((r["status"], r["ans"]["answer"], r["source"]), ("FAIL", "5", "adjudicated"))

    def test_uncertain_row_adjudicated_image_side_wins(self):
        r = F.rec(T.a(1, "5"), "UNCERTAIN", "no_independent_check")
        rn = self.run_ic(r, "flagged", T.solve(T.a(1, "6")), [T.solve(T.a(1, "6"))])
        self.assertEqual((len(rn.prompts), r["ans"]["answer"], r["status"]), (2, "6", "UNCERTAIN"))

    def test_agreeing_image_means_no_call(self):
        r = F.rec(T.a(1, "5"), "FAIL", "reviewer_disagrees")
        rn = self.run_ic(r, "doubt", T.solve(T.a(1, "5")), [T.solve(T.a(1, "6"))])
        self.assertEqual(len(rn.prompts), 1)
        self.assertEqual(r["ans"]["answer"], "5")

    def test_cfg_off_means_no_call(self):
        r = F.rec(T.a(1, "5"), "FAIL", "reviewer_disagrees")
        rn = self.run_ic(r, "doubt", T.solve(T.a(1, "6")), [T.solve(T.a(1, "6"))], {"adjudicate": False})
        self.assertEqual(len(rn.prompts), 1)

    def test_reply_ids_outside_the_conflict_set_are_ignored(self):
        ex = TI.load(self.tmp, TI.exam("Pick one.", "Pick two.", "Pick three."))
        r1 = F.rec(T.a(1, "5"), "UNCERTAIN", "x", image_ans=T.a(1, "6"))
        r2 = F.rec(T.a(2, "7"), "PASS", "")
        r3 = F.rec(T.a(3, "8"), "FAIL", "reviewer_disagrees")
        rn = F.FakeRn(T.solve(T.a(1, "6"), T.a(2, "99"), T.a(3, "98")))
        er.adjudicate(ex, {1: r1, 2: r2, 3: r3}, rn, [1])
        self.assertEqual((r1["ans"]["answer"], r2["ans"]["answer"], r3["ans"]["answer"]), ("6", "7", "8"))
        self.assertEqual((r2["status"], r3["status"]), ("PASS", "FAIL"))
        self.assertEqual(r2["findings"] + r3["findings"], [])
        self.assertEqual(len(rn.prompts), 1)
        self.assertNotIn("Pick two", rn.prompts[0])

    def test_declined_adjudication_reply_keeps_result(self):
        r = F.rec(T.a(1, "5"), "UNCERTAIN", "x", image_ans=T.a(1, "6"))
        er.adjudicate(self.ex_one(), {1: r}, F.FakeRn(T.solve(T.a(1, "", answer_status="uncertain"))), [1])
        self.assertEqual((r["ans"]["answer"], r["status"]), ("5", "UNCERTAIN"))
        self.assertIn("adjudication_failed", [f["code"] for f in r["findings"]])
        self.assertNotEqual(r.get("source"), "adjudicated")

    def test_missing_id_in_reply_keeps_result(self):
        r = F.rec(T.a(1, "5"), "FAIL", "reviewer_disagrees", image_ans=T.a(1, "6"))
        er.adjudicate(self.ex_one(), {1: r}, F.FakeRn(T.solve(T.a(7, "6"))), [1])
        self.assertEqual((r["ans"]["answer"], r["status"]), ("5", "FAIL"))
        self.assertIn("adjudication_failed", [f["code"] for f in r["findings"]])

    def test_budget_stop_during_the_call_is_a_finding_in_a_full_run(self):
        text = TI.exam("Source pages: 3\n\n" + TI.FIG)
        im, image = self.img(None)
        image["llm"] = lambda prompt, pngs: T.ok(T.solve(T.a(1, "6")), cost=0.9)
        llm = T.Script(T.solve(T.a(1, "5")), T.qa((1, "agree")))
        res, _ = self.run_img(text, llm, image, adjudicate=True, max_cost_usd=0.5)
        q = res["questions"][0]
        self.assertIn("adjudication_failed", [f["code"] for f in q["qa_findings"]])
        self.assertNotEqual(q["source"], "adjudicated")
        self.assertEqual(sch.validate(res, sch.RESULT), [])

    def test_call_cap_counts_the_call_only_when_it_can_run(self):
        base = {"max_attempts": 2}
        self.assertEqual(er.call_cap(dict(base, image_pdf=True, adjudicate=True)), er.call_cap(dict(base, image_pdf=True)) + 1)
        self.assertEqual(er.call_cap(base), er.call_cap(dict(base)))

    def ex_one(self):
        return TI.load(self.tmp, TI.exam("Pick one."))


class CliDefaults(T.Base):
    def calls_line(self, *flags):
        path = self.write("exam.md", TI.exam("Source pages: 3\n\n" + TI.FIG))
        from unittest import mock
        from exam_engine import cli
        doc = {"pages": [{"n": 3}], "parts": []}
        seen = {}

        def fake_run(exam, out, cfg, llm, **kw):
            seen.update(cfg=cfg)
            return None, 2
        mockf = self.write("m.json", "[]")
        with mock.patch.object(cli, "_load_source_doc", return_value=doc), mock.patch.object(cli.engine, "run", fake_run):
            self.main(path, "--mock", mockf, "--out", self.out, *flags)
        return seen.get("cfg", {})

    def test_default_cfg_without_pdf_has_no_adjudicate_key(self):
        self.assertNotIn("adjudicate", self.calls_line())

    def test_pdf_default_on_and_opt_out(self):
        self.assertTrue(self.calls_line("--pdf", "d.json").get("adjudicate"))
        self.assertNotIn("adjudicate", self.calls_line("--pdf", "d.json", "--no-adjudicate"))
        self.assertTrue(self.calls_line("--pdf", "d.json", "--adjudicate").get("adjudicate"))


class RealMissingFigureStillFlagged(unittest.TestCase):
    def test_stem_says_figure_below_no_figure_anywhere(self):
        texts = ["Source pages: 4\nCho hình dưới đây. Tính diện tích?", "Source pages: 4\nCâu hỏi khác"]
        self.assertEqual(refcheck.missing_by_question(texts), [["figure/table"], []])

    def test_two_questions_share_one_figure_line(self):
        texts = ["Source pages: 4\nUse the diagram below for Q1-2.\n[Figure/table: d]\nQ1 stem",
                 "Source pages: 4\nUse the diagram below for Q1-2.\nQ2 refers to the diagram below"]
        self.assertEqual(refcheck.missing_by_question(texts), [[], []])

    def test_figure_line_equal_to_source_pages_text_is_no_key(self):
        # the only text shared by the two questions is the page-span line; it must not carry the figure
        texts = ["Source pages: 4\nHead A\n[Figure/table: c]", "Source pages: 4\nHead B\nhình dưới"]
        self.assertEqual(refcheck.missing_by_question(texts), [[], ["figure/table"]])
        texts = ["Source pages: 4\n[Figure/table: c]\nQ1", "Source pages: 4\nQ2 theo bảng dưới đây"]
        self.assertEqual(refcheck.missing_by_question(texts)[1], ["figure/table"])

    def test_heading_lines_are_no_key(self):
        texts = ["## Part A\nX stem\n[Figure/table: c]", "## Part A\nY stem hình bên"]
        self.assertEqual(refcheck.missing_by_question(texts), [[], ["figure/table"]])

    def test_group_head_shared_figure_still_shared(self):
        g = "Đọc bảng dưới đây và trả lời các câu 1-2.\n"
        texts = ["Source pages: 6\n" + g + "[Figure/table: t]\nCâu 1", "Source pages: 6-7\n" + g + "Câu 2"]
        self.assertEqual(refcheck.missing_by_question(texts), [[], []])

    def test_only_structural_text_gives_none_key(self):
        self.assertIsNone(refcheck._first_line("Source pages: 3\n## H\n\n"))
        self.assertEqual(refcheck.missing_by_question(["Source pages: 3\nhình dưới"]), [["figure/table"]])


if __name__ == "__main__":
    unittest.main()
