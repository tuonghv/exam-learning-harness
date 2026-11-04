"""TASK-078 (REQ-0024): verified solve gate at the ingest bridge. $0: mock llm, Popen patched."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
from exam_engine import cli, engine as er  # noqa: E402
from exam_engine.core import schema as sch  # noqa: E402
from exam_engine.ingest import api  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402
from test_exam_run import Script, a, qa, solve  # noqa: E402

META = {k: "x" for k in api.REQUIRED}
META.update({"Subject": "Mathematics", "Level": "Grade 12", "Exam type": "Test",
             "Task": "Short Answer", "Mode": "Solve"})
TEXTS = {1: "ALPHA-ONE compute", 2: "BETA-TWO compute", 3: "GAMMA-THREE compute"}


def q(n, status=None, reasons=None, **kw):
    d = {"n": n, "text": TEXTS.get(n, "text %d" % n), "options": []}
    if status:
        d["verification"] = {"status": status, "checks": [], "reasons": reasons or []}
    d.update(kw)
    return d


def doc_of(qs):
    return {"source": {"name": "a.pdf", "format": "pdf"}, "meta": dict(META), "questions": qs}


def rdoc(ids, status=None):
    qs = []
    for i in ids:
        r = {"id": str(i), "text": "refined %s" % i, "options": {}}
        if i in (status or {}):
            r["verification"] = {"status": status[i], "checks": []}
        qs.append(r)
    return {"source": {"name": "a.pdf", "format": "pdf"}, "meta": dict(META), "refined": {"questions": qs}}


class GateTable(unittest.TestCase):
    def test_t1_statuses_by_level(self):
        sts = ["unverified", "verified", "needs_review", "rejected"]
        qs = [q(i, s) for i, s in enumerate(sts, 1)]
        want = {"verified": [1], "any": [0, 1, 2]}
        for lvl, keep in want.items():
            k, sk = api._gate(qs, {"min_verification": lvl})
            self.assertEqual(k, keep, lvl)
            self.assertEqual([x["status"] for x in sk], [sts[i] for i in range(4) if i not in keep])
        self.assertEqual(api._gate(qs, {})[0], [0, 1, 2])  # api default any

    def test_reasons_and_bad_level(self):
        k, sk = api._gate([q(1, "rejected", ["bad ocr"]), q(2, "verified")], {"min_verification": "verified"})
        self.assertEqual(sk, [{"printed": "1", "status": "rejected", "reasons": ["bad ocr"]}])
        with self.assertRaisesRegex(ValueError, "min_verification"):
            api._gate([q(1)], {"min_verification": "all"})

    def test_missing_key_inside_active_list_is_unverified(self):
        k, sk = api._gate([q(1, "verified"), q(2)], {"min_verification": "verified"})
        self.assertEqual((k, sk[0]["status"], sk[0]["printed"]), ([0], "unverified", "2"))

    def test_all_skipped_is_no_questions(self):
        with self.assertRaisesRegex(IngestError, "all 1 question.*min_verification=verified"):
            api.to_exam_text(doc_of([q(1, "rejected")]), {"min_verification": "verified"})


class Carrier(unittest.TestCase):
    def test_t5_skipped_carrier_still_shares_passage(self):
        qs = [q(1, "needs_review", context="Questions 1-2: read the PASSAGE-X text."),
              q(2, "verified")]
        text = api.to_exam_text(doc_of(qs), {"min_verification": "verified"})
        self.assertIn("PASSAGE-X", text)
        self.assertNotIn(TEXTS[1], text)
        self.assertIn("printed numbers: 1=2", text)


class Compat(unittest.TestCase):
    def test_t6_no_verification_identical(self):
        d = doc_of([q(1), q(2), q(3)])
        base = api.to_exam_text(d, {})
        for lvl in ("verified", "any"):
            c = {"min_verification": lvl}
            self.assertEqual(api.to_exam_text(d, c), base)
            self.assertEqual(api.assembly(d, c), api.assembly(d, {}))
            self.assertEqual(api.skipped(d, c), [])
        r = rdoc([61, 62, 63])
        base = api._from_refined(r)
        self.assertIn("N + 60", base)
        self.assertEqual(api._from_refined(r, None, {"min_verification": "verified"}), base)

    def test_t6_exam_format_md_unchanged(self):
        path = os.path.join(ROOT, "examples", "english", "input-001.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        d = {"source": {"name": "i.md", "format": "md", "text": text,
                        "sha256": __import__("hashlib").sha256(text.encode()).hexdigest()},
             "meta": {}, "pages": [], "questions": [q(1, "rejected")]}
        self.assertEqual(api.to_exam_text(d, {"min_verification": "verified"}), text)

    def test_assembly_rows_align_with_kept(self):
        d = doc_of([q(1, "verified"), q(2, "rejected"), q(3, "verified")])
        rows = api.assembly(d, {"min_verification": "verified"})
        self.assertEqual([(r["id"], r["printed"]) for r in rows], [("1", "1"), ("2", "3")])
        self.assertIn("printed numbers: 1=1, 2=3", api.to_exam_text(d, {"min_verification": "verified"}))

    def test_t9_refined_gap(self):
        d = rdoc([61, 62, 63], {61: "verified", 62: "needs_review", 63: "verified"})
        text = api._from_refined(d, None, {"min_verification": "verified"})
        self.assertIn("printed numbers: 1=61, 2=63", text)
        self.assertNotIn("N + ", text)
        self.assertNotIn("refined 62", text)
        self.assertEqual([r["printed"] for r in api.assembly(d, {"use_refined": True, "min_verification": "verified"})],
                         ["61", "63"])


class Pipeline(unittest.TestCase):
    """ingest --exam-out then solve with a fake llm."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="solve_gate_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for p in (mock.patch("subprocess.Popen", side_effect=AssertionError("real subprocess")),
                  mock.patch("exam_engine.pipeline.reporter.git_info", return_value=None)):
            p.start()
            self.addCleanup(p.stop)
        self.doc = doc_of([q(1, "verified"), q(2, "needs_review", ["blurry"]), q(3, "rejected")])

    def ingest(self, level, doc=None, engine_level=None):
        doc = doc or self.doc
        src = os.path.join(self.tmp, "a.pdf")
        open(src, "wb").write(b"%PDF")
        exam = os.path.join(self.tmp, "exam-%s.md" % (level or "default"))
        argv = [src, "--exam-out", exam] + (["--min-verification", level] if level else [])
        cfg = dict(cli.settings.load_config("engine"), **({"min_verification": engine_level} if engine_level else {}))
        with mock.patch("exam_engine.ingest.api.ingest_document", return_value=doc), \
                mock.patch.object(cli.settings, "load_config", return_value=cfg), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.ingest_main(argv)
        return code, exam, err.getvalue()

    def solve(self, exam, nq):
        llm = Script(solve(*[a(i, "A") for i in range(1, nq + 1)]), qa(*[(i, "agree") for i in range(1, nq + 1)]))
        out = os.path.join(self.tmp, "out-" + os.path.basename(exam))
        cfg = {"max_attempts": 2, "max_cost_usd": 1.0, "timeout": 5, "model": "sonnet", "key": None, "llm_name": "mock"}
        with contextlib.redirect_stderr(io.StringIO()):
            res, code = er.run(exam, out, cfg, llm)
        return res, code, llm, out

    def test_t2_t4_default_verified_only(self):
        code, exam, err = self.ingest(None)
        self.assertEqual(code, 0)
        self.assertIn("WARN: skipped_unverified: q2 needs_review", err)
        self.assertIn("WARN: skipped_unverified: q3 rejected", err)
        text = open(exam).read()
        self.assertIn("ALPHA-ONE", text)
        self.assertNotIn("BETA-TWO", text)
        res, rc, llm, out = self.solve(exam, 1)
        self.assertTrue(all("BETA-TWO" not in p and "GAMMA-THREE" not in p for p in llm.prompts))
        self.assertEqual(res["summary"]["skipped_unverified"], 2)
        self.assertEqual([x["status"] for x in res["skipped_unverified"]], ["needs_review", "rejected"])
        self.assertEqual(res["skipped_unverified"][0]["reasons"], ["blurry"])
        self.assertIn("Skipped (unverified): 2", open(os.path.join(out, "report.md")).read())
        s = res["summary"]
        self.assertEqual((s["pass"] + s["fail"] + s["uncertain"], len(res["questions"])), (1, 1))
        self.assertEqual(sch.validate(res, sch.RESULT), [])
        # exit code equals a plain 1-question run
        one = doc_of([q(1)])
        _, ex1, _ = self.ingest("any", one)
        res1, rc1, _, _ = self.solve(ex1, 1)
        self.assertEqual(rc, rc1)
        self.assertEqual(res["summary"]["fail"], res1["summary"]["fail"])

    def test_t3_any_restores_needs_review(self):
        for kw in ({"level": "any"}, {"level": None, "engine_level": "any"}):
            code, exam, err = self.ingest(**kw)
            self.assertEqual(code, 0)
            text = open(exam).read()
            self.assertIn("BETA-TWO", text)
            self.assertNotIn("GAMMA-THREE", text)
            res, _, _, _ = self.solve(exam, 2)
            self.assertEqual(res["summary"]["skipped_unverified"], 1)
            self.assertEqual(res["skipped_unverified"][0]["status"], "rejected")

    def test_t6_no_skip_no_keys(self):
        _, exam, err = self.ingest("verified", doc_of([q(1), q(2)]))
        side = json.load(open(exam + ".assembly.json"))
        self.assertNotIn("skipped", side)
        self.assertNotIn("WARN: skipped", err)
        res, _, _, _ = self.solve(exam, 2)
        self.assertNotIn("skipped_unverified", res)
        self.assertNotIn("skipped_unverified", res["summary"])

    def test_missing_sidecar_is_tolerated(self):
        self.assertEqual(er._skipped_unverified(os.path.join(self.tmp, "nope.md")), [])
        bad = os.path.join(self.tmp, "bad.md")
        open(bad + ".assembly.json", "w").write("{not json")
        self.assertEqual(er._skipped_unverified(bad), [])

    def test_bad_level_refused(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.ingest_main(["x.pdf", "--min-verification", "all"]), 2)


if __name__ == "__main__":
    unittest.main()
