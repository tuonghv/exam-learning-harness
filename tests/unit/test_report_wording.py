"""TASK-093 / REQ-0100: readable no-answer wording in the solution report; data stays raw (design phase 93)."""
import contextlib
import copy
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import (metrics, report_kinds as rk, report_pack, reporter as rp)  # noqa: E402

EXAM = os.path.join(ROOT, "examples", "english", "input-001.md")
MOCK = os.path.join(HERE, "fixtures", "mock_english_001.json")
NONE_RE = re.compile(r"\bnone\b", re.I)
ANS_RE = re.compile(r"^\*\*(Đáp án|Answer): (.+)\*\*$", re.M)


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **kw)


def answered(i):
    return {"id": str(i), "answer": "A", "verification_status": "PASS", "status_reason": "ok",
            "score": {"points": 1, "max": 1, "basis": "key"}, "evidence_kind": "key_match",
            "checks": [], "solution": ["s"], "explanation": "e", "uncertainty": {"level": "low", "reason": "r"}}


def declined(i):
    return {"id": str(i), "answer": None, "verification_status": "UNCERTAIN", "status_reason": "declined",
            "score": {"points": None, "max": None, "basis": "none"}, "evidence_kind": "none",
            "checks": [], "uncertainty": {"level": "high", "reason": "r"}}


def result(lang, qs=None):
    qs = qs if qs is not None else [answered(1), declined(2)]
    return {"exam": {"subject": "Math", "level": "G12", "exam_type": "T", "task": "MC", "mode": "Solve",
                     "path": "x.md", "language": lang},
            "run": {"llm": "mock", "model": "m", "calls": 1, "cost_usd": 0.0},
            "summary": {"pass": 1, "fail": 0, "uncertain": 1, "unresolved": 0, "points": 1, "max_points": 1},
            "questions": qs}


def metrics_for(res):
    return metrics.compute(res)


class Wording(unittest.TestCase):
    def md(self, lang, with_metrics=True):
        res = result(lang)
        return rp.build_markdown(res, metrics_for(res) if with_metrics else None)

    def test_93_1_vi_declined_uses_localized_phrases_and_no_none_token(self):
        md = self.md("vi")
        L = rp.LABELS["vi"]
        self.assertIn("**Đáp án: %s**" % L["no_answer"], md)
        self.assertIn("- Bằng chứng: " + L["no_evidence"], md)
        self.assertIn("- Điểm: " + L["no_score"], md)
        self.assertEqual(NONE_RE.findall(md), [])

    def test_93_1_en_declined_uses_localized_phrases_and_no_none_token(self):
        md = self.md("en")
        L = rp.LABELS["en"]
        self.assertIn("**Answer: %s**" % L["no_answer"], md)
        self.assertIn("- Evidence: " + L["no_evidence"], md)
        self.assertIn("- Score: " + L["no_score"], md)
        self.assertEqual(NONE_RE.findall(md), [])
        for k in ("no_answer", "no_evidence", "no_score"):
            self.assertFalse(NONE_RE.search(L[k]), k)

    def test_93_2_answered_block_unchanged(self):
        md = self.md("en", with_metrics=False)
        self.assertIn("- Evidence: key_match", md)
        self.assertIn("- Score: 1 / 1 (key)", md)
        self.assertIn("**Answer: A**", md)

    def test_93_2_missing_evidence_kind_falls_back_to_computed_kind(self):
        q = declined(2)
        del q["evidence_kind"]
        md = rp.build_markdown(result("en", [q]))
        self.assertIn("- Evidence: " + rp.LABELS["en"]["no_evidence"], md)

    def test_93_2_partial_score_keeps_old_format(self):
        q = answered(1)
        q["score"] = {"points": 0, "max": 1, "basis": "computed"}
        self.assertIn("- Score: 0 / 1 (computed)", rp.build_markdown(result("en", [q])))

    def test_93_5_answer_line_regex_and_has_text_counts(self):
        for lang in ("vi", "en"):
            md = self.md(lang, with_metrics=False)
            lines = [m.group(2) for m in ANS_RE.finditer(md)]
            self.assertEqual(lines, ["A", rp.LABELS[lang]["no_answer"]], lang)
        # _has_text looks at the Đáp án prefix only: same verdict whatever follows it
        blk = lambda a: "Stem\n\nA. x  \nB. y  \n\n**Đáp án: %s**\n" % a
        self.assertTrue(rk._has_text(blk("A")))
        self.assertEqual(rk._has_text(blk(rp.LABELS["vi"]["no_answer"])), rk._has_text(blk("A")))
        self.assertFalse(rk._has_text("**Đáp án: x**\n"))

    def test_93_5_with_text_counts_unchanged_for_mix(self):
        exam = {"questions": [{"id": str(i), "stem": "Stem %d" % i, "options": {"A": "x", "B": "y"}} for i in (1, 2)]}
        md = rp.build_markdown(result("vi"), None, exam)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, rk.name("e", "math", "solution-report", "run-t", "md"))
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(md)
            total, with_text = rk.count_of(p, "solution-report")
        self.assertEqual((total, with_text), (2, 2))

    def test_93_3_metrics_accuracy_no_key_and_keyed_unchanged(self):
        res = result("en", [dict(answered(1), score={"points": None, "max": None, "basis": "none"}), declined(2)])
        self.assertIn("accuracy: no key", metrics.block(metrics.compute(res)))
        res = result("en")
        keyed = metrics.block(metrics.compute(res, key={"1": "A", "2": "B"}))
        line = [x for x in keyed if x.startswith("accuracy:")][0]
        self.assertTrue(line.startswith("accuracy: key"), line)
        self.assertNotIn("no key", line)

    def test_93_2_combined_subject_and_learn_use_same_block(self):
        res = result("vi")
        sec = "\n".join(rp._subject_section(res))
        self.assertIn(sec, rp.build_combined_markdown([(res, None, None), (copy.deepcopy(res), None, None)]))
        self.assertIn(sec, rp.build_markdown(res))
        self.assertEqual(NONE_RE.findall(rp.build_combined_markdown([(res, metrics_for(res), None)])), [])
        # learn view and answer sheet print the em dash, no wording, no none
        self.assertEqual(NONE_RE.findall(rp.build_learning_view(res)), [])
        self.assertNotIn(rp.LABELS["vi"]["no_answer"], rp.build_answer_sheet(res))

    def test_93_4_data_stays_raw_and_pdf_path_unaffected(self):
        res = result("vi")
        before = copy.deepcopy(res)
        sheet_before = rp.build_answer_sheet(res)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rp, "git_info", return_value=None):
            seen = {}

            def fake_pdf(md_path, pdf_path, **kw):
                with open(md_path, encoding="utf-8") as fh:
                    seen["md"] = fh.read()
                return True, "fake"
            with mock.patch.object(rp, "md_to_pdf", side_effect=fake_pdf):
                info = rp.write_reports(res, d, pdf=True, metrics=metrics_for(res))
            with open(info["md"], encoding="utf-8") as fh:
                on_disk = fh.read()
            with open(info["answers"], encoding="utf-8") as fh:
                sheet = fh.read()
        self.assertEqual(res, before)  # reporter never rewrites the result
        self.assertEqual(res["questions"][1]["evidence_kind"], "none")
        self.assertEqual(res["questions"][1]["score"]["basis"], "none")
        self.assertEqual(seen["md"], on_disk)  # pdf renders the same md
        self.assertEqual(NONE_RE.findall(on_disk), [])
        self.assertEqual(sheet.rstrip("\n"), sheet_before.rstrip("\n"))


class Pack(unittest.TestCase):
    """report-pack on a real mock run with one question declined: tsv columns keep the raw basis `none`."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="rw_test_")
        cwd = os.getcwd()
        os.chdir(cls.tmp)
        try:
            with mock.patch.object(rp, "git_info", return_value=None):
                quiet(cli.solve_main, [EXAM, "--mock", MOCK, "--no-pdf"])
        finally:
            os.chdir(cwd)
        base = os.path.join(cls.tmp, "plans", "input-001", "main", "runs")
        d = os.path.join(cls.tmp, "p", "out-Alpha")
        shutil.copytree(os.path.join(base, os.listdir(base)[0]), d)
        rpath = os.path.join(d, "result.json")
        with open(rpath, encoding="utf-8") as fh:
            r = json.load(fh)
        r["exam"]["subject"] = "Alpha"
        q = r["questions"][0]
        q.update(answer=None, evidence_kind="none", score={"points": None, "max": None, "basis": "none"},
                 status_reason="declined", verification_status="UNCERTAIN")
        with open(rpath, "w", encoding="utf-8") as fh:
            json.dump(r, fh)
        cls.out = os.path.join(cls.tmp, "pack")
        with mock.patch.object(rp, "git_info", return_value=None):
            report_pack.build_pack([d], cls.out, "ex", "run-t", pdf=False)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def read(self, kind, ext, subject="all"):
        with open(os.path.join(self.out, rk.name("ex", subject, kind, "run-t", ext)), encoding="utf-8") as fh:
            return fh.read()

    def test_93_4_answer_table_keeps_raw_none_basis_and_dash_answer(self):
        rows = [ln.split("\t") for ln in self.read("answer-table", "tsv").splitlines()]
        self.assertEqual(rows[0][-1], "score")
        first = rows[1]
        self.assertEqual((first[3], first[-1]), ("-", "none"))

    def test_93_1_pack_reports_have_no_none_token_and_show_phrases(self):
        for subject in ("all",):  # a pack keeps only the `all` report
            md = self.read("solution-report", "md", subject)
            self.assertEqual(NONE_RE.findall(md), [], subject)
            self.assertIn(rp.LABELS["vi"]["no_answer"], md)
            self.assertIn(rp.LABELS["vi"]["no_score"], md)


if __name__ == "__main__":
    unittest.main()
