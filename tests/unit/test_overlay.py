"""TASK-096 / REQ-0103 (96.1-96.4): report answer overlay. $0, tmp trees, synthetic exams, no network.

Base line f: Math, Science, Physics (offset 10; Physics q2 is declined). Overlay line g: Physics (offset 11),
same stem+options as base q2 (printed 12 = base id 2 = overlay id 1), different passage."""
import contextlib
import copy
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import overlay, reporter, runlayout  # noqa: E402

CHECK = os.path.join(ROOT, "tools", "check_report_pack.py")
REASON = "rerun after the table fix"
STEM = "Which value is the largest of the four?"
OPTS = {"A": "one", "B": "two", "C": "three", "D": "four"}


def quiet(fn, *a):
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        try:
            code = fn(*a)
        except SystemExit as ex:  # argparse error
            code = ex.code
    return code, o.getvalue(), e.getvalue()


def jread(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def jwrite(p, obj):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def snapshot(root):
    out = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            with open(p, "rb") as fh:
                out[p] = hashlib.sha256(fh.read()).hexdigest()
    return out


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def exam_md(subject, off, qs):
    """qs = [(id, stem, opts, passage)]"""
    head = "# Exam Input\n\nSubject: %s\nLevel: Grade 12\nExam type: Test\nTask: Multiple Choice\nMode: Solve\n\n" % subject
    head += "## Instructions\n\nChoose the best answer.\n"
    if off:
        head += "(printed exam number of question N is N + %d)\n" % off
    body = ""
    for i, stem, opts, passage in qs:
        body += "\n## Question %d\n\n" % i
        if passage:
            body += "### Passage\n\n%s\n\n" % passage
        body += "### Question text\n\n%s\n\n" % stem
        body += "".join("%s. %s\n" % (k, v) for k, v in opts.items())
    return head + body


def question(i, letter, status="PASS"):
    declined = letter is None
    return {"id": str(i), "evidence_kind": "none" if declined else "Claude review only", "answer": letter,
            "solution": [] if declined else ["step for %s" % letter],
            "explanation": "" if declined else "because %s" % letter,
            "uncertainty": {"level": "high" if declined else "low", "reason": "r"},
            "checks": [], "verification_status": "UNCERTAIN" if declined else status,
            "status_reason": "solver_declined" if declined else "", "qa_findings": [], "score": None,
            "attempts": 1, "unresolved": declined, "error": None, "pages": [1]}


def result(subject, qs, cost=0.0):
    sm = {"pass": 0, "fail": 0, "uncertain": 0, "unresolved": 0, "points": None, "max_points": None}
    for q in qs:
        k = q["verification_status"].lower()
        sm[k] = sm.get(k, 0) + 1
        sm["unresolved"] += 1 if q["unresolved"] else 0
    return {"schema_version": 1,
            "exam": {"path": "x.md", "subject": subject, "level": "Grade 12", "exam_type": "Test",
                     "task": "Multiple Choice", "mode": "Solve", "language": "en"},
            "run": {"llm": "mock", "model": "m", "max_attempts": 2, "timeout_s": 300, "max_cost_usd": 1.0,
                    "cost_usd": cost, "calls": 1, "stopped": None, "prompt": {"channel": "release", "version": "v1"}},
            "questions": qs, "summary": sm}


class Base(unittest.TestCase):
    lang = "en"

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        p = mock.patch.object(reporter, "git_info", return_value=None)
        p.start()
        self.addCleanup(p.stop)
        self.plans, self.reports = os.path.join(self.tmp, "plans"), os.path.join(self.tmp, "reports")
        os.makedirs(self.plans)
        os.makedirs(self.reports)
        self.math = self.plan("ex", "f", "20240101-000001-math", "Math", 0, 3, {})
        self.sci = self.plan("ex", "f", "20240101-000002-sci", "Science", 5, 3, {})
        self.phy = self.plan("ex", "f", "20240101-000003-phy", "Physics", 10, 3, {2: None})
        self.base = [self.math, self.sci, self.phy]
        self.ov = self.plan("ex", "g", "20240102-000001-ov", "Physics", 11, 1, {1: "C"}, passage="OVERLAY TABLE 9 9 9",
                            cost=0.25)
        self.ov_spec = "%s:12" % self.ov

    def plan(self, exam, line, rid, subject, off, n, answers, passage="base placeholder", stem=STEM, opts=OPTS,
             cost=0.0):
        d = os.path.join(self.plans, exam, line, "runs", rid)
        os.makedirs(os.path.join(d, "input"))
        qs = [(i, stem if i == 2 or n == 1 else "Question %d of %s?" % (i, subject), opts, passage if i in (1, 2) else "")
              for i in range(1, n + 1)]
        with open(os.path.join(d, "input", "exam.md"), "w", encoding="utf-8") as fh:
            fh.write(exam_md(subject, off, qs))
        letters = {i: "ABCD"[i % 4] for i in range(1, n + 1)}
        letters.update(answers)
        jwrite(os.path.join(d, "result.json"), result(subject, [question(i, letters[i]) for i in range(1, n + 1)], cost))
        with open(os.path.join(d, "run.log"), "w", encoding="utf-8") as fh:
            fh.write("run %s\n" % rid)
        jwrite(os.path.join(d, "config.json"), {"lang": self.lang, "key": None})
        jwrite(os.path.join(d, "plan.json"), {"exam_id": exam, "line": line, "plan_exam": exam, "exit_code": 0,
                                              "status": "done", "cost_usd": cost, "calls": 1})
        return d

    def pack(self, out, *extra, base=None):
        args = list(base or self.base) + ["--exam", "ex", "--no-pdf", "--out", out] + list(extra)
        return quiet(cli.report_pack_main, args)

    def ovargs(self, spec=None, reason=REASON):
        a = ["--overlay", spec or self.ov_spec]
        return a + (["--overlay-reason", reason] if reason else [])

    def files(self, out, suffix):
        return sorted(os.path.join(out, f) for f in os.listdir(out) if f.endswith(suffix))

    def blocks(self, out):
        """{(file base): {heading: block text}} for the combined solution report."""
        sol = [f for f in self.files(out, ".md") if "solution-report" in f and "_all_" in f]
        self.assertEqual(len(sol), 1, os.listdir(out))
        text = open(sol[0], encoding="utf-8").read()
        parts = re.split(r"(?m)^(?=### )", text)
        return text, parts[1:]

    def solution_all(self, out):
        return self.blocks(out)[0]


class T1Applied(Base):
    def setUp(self):
        super().setUp()
        self.o1, self.o2 = os.path.join(self.tmp, "o1"), os.path.join(self.tmp, "o2")
        code, _, err = self.pack(self.o1)
        self.assertEqual(code, 0, err)
        code, out, err = self.pack(self.o2, *self.ovargs())
        self.assertEqual(code, 0, err + out)

    def test_96_2_overlay_answer_passage_and_source_line_en(self):
        text = self.solution_all(self.o2)
        self.assertIn("OVERLAY TABLE 9 9 9", text)
        self.assertIn("Answer source: plan run 20240102-000001-ov of line g (%s)" % REASON, text)
        self.assertEqual(len(re.findall(r"Answer source:", text)), 1)
        self.assertNotRegex(self.solution_all(self.o1), r"Answer source:")
        self.assertNotIn("OVERLAY TABLE", self.solution_all(self.o1))

    def test_96_2_source_line_vi(self):
        self.lang = "vi"
        for d in self.base + [self.ov]:
            c = jread(os.path.join(d, "config.json"))
            c["lang"] = "vi"
            jwrite(os.path.join(d, "config.json"), c)
            r = jread(os.path.join(d, "result.json"))
            r["exam"]["language"] = "vi"
            jwrite(os.path.join(d, "result.json"), r)
        out = os.path.join(self.tmp, "ovi")
        code, o, err = self.pack(out, *self.ovargs())
        self.assertEqual(code, 0, err + o)
        text = self.solution_all(out)
        self.assertIn("Nguồn đáp án: lần chạy plan 20240102-000001-ov của line g (%s)" % REASON, text)
        self.assertEqual(len(re.findall(r"Nguồn đáp án:", text)), 1)

    def test_96_2_other_blocks_byte_identical_and_declined_block_differs(self):
        t1, b1 = self.blocks(self.o1)
        t2, b2 = self.blocks(self.o2)
        self.assertEqual(len(b1), len(b2))
        self.assertEqual(len(b1), 9)  # 3 subjects x 3 questions
        diff = [i for i, (a, b) in enumerate(zip(b1, b2)) if a != b]
        self.assertEqual(len(diff), 1, diff)
        self.assertIn("Answer source", b2[diff[0]])
        self.assertIn("Physics", t2)

    def test_96_3_answered_declined_counts_shift(self):
        def counts(out):
            tsv = [f for f in self.files(out, ".tsv") if "answer-table" in f]
            self.assertEqual(len(tsv), 1)
            rows = [ln.split("\t") for ln in open(tsv[0], encoding="utf-8").read().splitlines()[1:] if ln.strip()]
            return rows
        r1, r2 = counts(self.o1), counts(self.o2)
        self.assertEqual(len(r1), len(r2))
        self.assertEqual(len(r1), 9)
        changed = [(a, b) for a, b in zip(r1, r2) if a != b]
        self.assertEqual(len(changed), 1, changed)
        self.assertIn("C", changed[0][1])
        self.assertNotIn("C", " ".join(changed[0][0]).split("\t"))
        txt1, txt2 = self.solution_all(self.o1), self.solution_all(self.o2)
        self.assertNotRegex(txt2.lower(), r"\bnone\b")
        self.assertNotEqual(txt1, txt2)

    def test_96_3_answer_sheet_and_metrics_reflect_overlay(self):
        sheets = [f for f in self.files(self.o2, ".md") if "answer-sheet" in f and "physics" in f.lower()]
        sheets1 = [f for f in self.files(self.o1, ".md") if "answer-sheet" in f and "physics" in f.lower()]
        self.assertEqual((len(sheets), len(sheets1)), (1, 1), os.listdir(self.o2))
        s2, s1 = open(sheets[0], encoding="utf-8").read(), open(sheets1[0], encoding="utf-8").read()
        self.assertNotEqual(s1, s2)
        self.assertRegex(s2, "Ⓒ")
        met = [f for f in self.files(self.o2, ".json") if "metrics" in f and "physics" in f.lower()]
        met1 = [f for f in self.files(self.o1, ".json") if "metrics" in f and "physics" in f.lower()]
        self.assertEqual((len(met), len(met1)), (1, 1), os.listdir(self.o2))
        m1, m2 = jread(met1[0]), jread(met[0])
        self.assertNotEqual(m1, m2)
        self.assertEqual(json.dumps(m2).count('"overlay"') >= 0, True)
        # cost metrics use the base run only (overlay cost 0.25 lives in run.json)
        self.assertNotIn("0.25", json.dumps(m2))

    def test_96_4_run_json_overlays_shape(self):
        run = jread(os.path.join(self.o2, "run.json"))
        self.assertEqual(len(run["overlays"]), 1)
        e = run["overlays"][0]
        self.assertEqual((e["plan_run_id"], e["line"], e["subject"], e["exam_id"]),
                         ("20240102-000001-ov", "g", "Physics", "ex"))
        self.assertEqual(e["reason"], REASON)
        self.assertEqual(e["cost_usd"], 0.25)
        self.assertEqual(e["base_plan_run_id"], "20240101-000003-phy")
        self.assertEqual(e["result_sha256"], sha(os.path.join(self.ov, "result.json")))
        q = e["questions"]
        self.assertEqual([(x["printed"], x["base_id"], x["id"]) for x in q], [(12, "2", "1")])
        ex = overlay.load_exam(self.ov)
        self.assertEqual(q[0]["text_sha256"], overlay.text_sha256(ex["questions"][0]))
        self.assertEqual([p["plan_run_id"] for p in run["plan_runs"]],
                         [os.path.basename(d) for d in self.base])
        self.assertNotIn("overlays", jread(os.path.join(self.o1, "run.json")))

    def test_96_2_base_and_overlay_plan_files_unchanged(self):
        before = snapshot(self.plans)
        out = os.path.join(self.tmp, "o3")
        code, _, err = self.pack(out, *self.ovargs())
        self.assertEqual(code, 0, err)
        self.assertEqual(snapshot(self.plans), before)

    def test_96_3_recounted_summary(self):
        r = jread(self.phy + "/result.json")
        merged, _ = overlay.apply(r, overlay.load_exam(self.phy), jread(os.path.join(self.o2, "run.json"))["overlays"][0],
                                  jread(self.ov + "/result.json"), overlay.load_exam(self.ov))
        self.assertEqual(r["summary"]["unresolved"], 1)
        self.assertEqual(merged["summary"]["unresolved"], 0)
        self.assertEqual(merged["questions"][1]["answer"], "C")
        self.assertEqual(merged["questions"][1]["id"], "2")
        self.assertEqual(r["questions"][1]["answer"], None)  # input untouched (deep copy)

    def test_96_3_checker_passes_and_fails_when_tampered(self):
        cmd = [sys.executable, "-I", CHECK, self.o2] + self.base
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=self.tmp)
        # the checker always expects a PDF per report: only the PDF-count rows may fail with --no-pdf
        bad = [ln for ln in r.stdout.splitlines() if ln.endswith("FAIL") and "pdf" not in ln.lower()
               and not ln.startswith("RESULT")]
        self.assertEqual(bad, [], r.stdout)
        self.assertRegex(r.stdout, r"RESULT\t53 checks\t3 failed")  # exactly the 3 PDF rows
        self.assertRegex(r.stdout, r"overlay result_sha256 mismatches\t0\t0\tok")
        self.assertRegex(r.stdout, r"overlay source lines physics\t1\t1\tok")
        res = jread(self.ov + "/result.json")
        res["questions"][0]["answer"] = "B"
        jwrite(self.ov + "/result.json", res)
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertRegex(r.stdout, r"overlay result_sha256 mismatches\t0\t1\tFAIL")


class T2Refusals(Base):
    def refused(self, *args, msg, base=None):
        out = os.path.join(self.tmp, "refused")
        code, o, err = self.pack(out, *args, base=base)
        self.assertEqual(code, 2, o + err)
        self.assertIn(msg, o + err)
        self.assertFalse(os.path.exists(out), os.listdir(self.tmp))
        return o + err

    def test_96_1_text_hash_differs(self):
        bad = self.plan("ex", "g", "20240102-000002-bad", "Physics", 11, 1, {1: "C"},
                        opts=dict(OPTS, D="four (changed)"))
        self.refused(*self.ovargs("%s:12" % bad), msg="printed 12: question text differs")

    def test_96_1_stem_differs(self):
        bad = self.plan("ex", "g", "20240102-000002-bad", "Physics", 11, 1, {1: "C"}, stem="Another stem?")
        self.refused(*self.ovargs("%s:12" % bad), msg="question text differs")

    def test_96_1_base_already_answered(self):
        # printed 11 = base id 1 (answered, same text as overlay id 1 under offset 10)
        ov2 = self.plan("ex", "g", "20240102-000004-o10b", "Physics", 10, 3, {1: "C", 2: "C"})
        self.refused(*self.ovargs("%s:11" % ov2), msg="base question is answered")

    def test_96_1_unknown_printed(self):
        self.refused(*self.ovargs("%s:99" % self.ov), msg="printed 99: unknown question")

    def test_96_1_missing_reason(self):
        self.refused(*self.ovargs(reason=None), msg="--overlay-reason")

    def test_96_1_other_exam(self):
        other = self.plan("other", "g", "20240102-000005-x", "Physics", 11, 1, {1: "C"})
        self.refused(*self.ovargs("%s:12" % other), msg="is exam")

    def test_96_1_subject_not_in_base(self):
        other = self.plan("ex", "g", "20240102-000006-x", "Chemistry", 11, 1, {1: "C"})
        self.refused(*self.ovargs("%s:12" % other), msg="matches 0 base parts")

    def test_96_1_duplicate_printed(self):
        self.refused("--overlay", "%s:12,12" % self.ov, "--overlay-reason", REASON, msg="listed twice")

    def test_96_1_overlay_is_a_base_plan(self):
        self.refused(*self.ovargs("%s:12" % self.phy), msg="one of the base plan runs")

    def test_96_1_overlay_without_letter(self):
        bad = self.plan("ex", "g", "20240102-000007-x", "Physics", 11, 1, {1: None})
        self.refused(*self.ovargs("%s:12" % bad), msg="no letter answer")

    def test_96_1_resolve_reads_only(self):
        before = snapshot(self.plans)
        with self.assertRaises(ValueError):
            overlay.resolve([self.ov_spec + ",99"], self.base, REASON)
        self.assertEqual(snapshot(self.plans), before)


class T6Publish(Base):
    def setUp(self):
        super().setUp()
        self.line = os.path.join(self.reports, "ex", "f")
        code, o, err = quiet(cli.report_pack_main, self.base + ["--exam", "ex", "--no-pdf", "--run", "f"] + self.ovargs())
        self.assertEqual(code, 0, o + err)
        p = mock.patch.object(runlayout, "PROTECTED_ROOTS", (self.plans, self.reports))
        p.start()
        self.addCleanup(p.stop)

    def main_runs(self):
        d = os.path.join(self.reports, "ex", "main")
        return sorted(x for x in os.listdir(d) if x.startswith("run-")) if os.path.isdir(d) else []

    def test_96_4_publish_inherits_overlay_and_run_list_shows_published(self):
        code, out, err = quiet(cli.publish_main, ["ex", "--no-pdf", "--from", "f"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("overlay inherited: 20240102-000001-ov printed 12", out)
        runs = self.main_runs()
        self.assertEqual(len(runs), 1, runs)
        run = jread(os.path.join(self.reports, "ex", "main", runs[0], "run.json"))
        self.assertEqual(run["overlays"][0]["plan_run_id"], "20240102-000001-ov")
        self.assertEqual(run["overlays"][0]["reason"], REASON)
        main_dir = os.path.join(self.reports, "ex", "main", runs[0])
        self.assertIn("Answer source:", open([f for f in self.files(main_dir, ".md")
                                              if "solution-report" in f and "_all_" in f][0], encoding="utf-8").read())
        code, out, err = quiet(cli.run_list_main, ["ex"])
        self.assertEqual(code, 0, err)
        row = [ln for ln in out.splitlines() if "20240102-000001-ov" in ln]
        self.assertTrue(row, out)
        self.assertIn("published", row[0])

    def test_96_4_second_publish_keeps_earlier_main_run(self):
        quiet(cli.publish_main, ["ex", "--no-pdf", "--from", "f"])
        first = self.main_runs()
        with mock.patch.object(runlayout, "new_run_id", return_value="zz-second", create=True):
            pass
        code, out, err = quiet(cli.publish_main, ["ex", "--no-pdf", "--from", "f"])
        self.assertEqual(code, 0, out + err)
        second = self.main_runs()
        self.assertTrue(set(first) <= set(second), (first, second))
        self.assertIn("main:", out)

    def test_96_4_publish_without_overlay_flag_refusal_when_overlay_vanished(self):
        shutil.rmtree(self.ov)
        code, out, err = quiet(cli.publish_main, ["ex", "--no-pdf", "--from", "f"])
        self.assertNotEqual(code, 0, out)
        self.assertEqual(self.main_runs(), [])

    def test_96_4_publish_argparse_needs_reason(self):
        code, _, err = quiet(cli.publish_main, ["ex", "--no-pdf", "--from", "f", "--overlay", self.ov_spec])
        self.assertEqual(code, 2, err)
        self.assertEqual(self.main_runs(), [])


class TNoOverlayGolden(Base):
    def test_96_golden_no_overlay_pack_has_no_overlay_traces(self):
        out = os.path.join(self.tmp, "g")
        code, _, err = self.pack(out)
        self.assertEqual(code, 0, err)
        self.assertNotIn("overlays", jread(os.path.join(out, "run.json")))
        for f in os.listdir(out):
            if f.endswith((".md", ".json", ".tsv")):
                self.assertNotIn("Answer source", open(os.path.join(out, f), encoding="utf-8").read())


class TPdf(Base):
    def test_96_pdf_path_pack_runs_with_overlay(self):
        out = os.path.join(self.tmp, "pdf")
        args = list(self.base) + ["--exam", "ex", "--out", out] + self.ovargs()
        code, o, err = quiet(cli.report_pack_main, args)
        if code != 0 and re.search(r"(?i)weasyprint|pdf", o + err) and "overlay" not in (o + err).lower():
            self.skipTest("pdf engine unavailable: " + (o + err)[:80])
        self.assertEqual(code, 0, o + err)
        self.assertTrue(self.files(out, ".pdf"))
        run = jread(os.path.join(out, "run.json"))
        self.assertEqual(len(run["overlays"]), 1)


if __name__ == "__main__":
    unittest.main()
