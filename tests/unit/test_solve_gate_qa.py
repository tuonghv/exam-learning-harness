"""TASK-078 QA (REQ-0024): adversarial cases beyond test_solve_gate.py. $0, no subprocess."""
import contextlib
import hashlib
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
from exam_engine.ingest import api  # noqa: E402
from test_solve_gate import doc_of, q, rdoc  # noqa: E402


class Qa(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sg_qa_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def cli_ingest(self, doc, level=None, name="e"):
        src = os.path.join(self.tmp, "a.pdf")
        open(src, "wb").write(b"%PDF")
        exam = os.path.join(self.tmp, name + ".md")
        argv = [src, "--exam-out", exam] + (["--min-verification", level] if level else [])
        with mock.patch("exam_engine.ingest.api.ingest_document", return_value=doc), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.ingest_main(argv)
        return code, exam, err.getvalue()

    def test_mixed_missing_keys(self):
        d = doc_of([q(1, "verified"), q(2), q(3, "unverified"), q(4, "verified")])
        text = api.to_exam_text(d, {"min_verification": "verified"})
        self.assertIn("printed numbers: 1=1, 2=4", text)
        self.assertNotIn("BETA-TWO", text)
        sk = api.skipped(d, {"min_verification": "verified"})
        self.assertEqual([(s["printed"], s["status"]) for s in sk], [("2", "unverified"), ("3", "unverified")])
        a = api.to_exam_text(d, {"min_verification": "any"})  # any keeps unverified (incl. missing key)
        self.assertIn("BETA-TWO", a)

    def test_all_skipped_exit_2_clear_error(self):
        d = doc_of([q(1, "rejected"), q(2, "needs_review")])
        code, exam, err = self.cli_ingest(d, "verified")
        self.assertEqual(code, 2)
        self.assertIn("min_verification=verified", err)
        self.assertFalse(os.path.exists(exam))

    def test_any_with_only_rejected_exit_2(self):
        code, exam, err = self.cli_ingest(doc_of([q(1, "rejected")]), "any")
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(exam))

    def test_any_drops_rejected_keeps_rest(self):
        d = doc_of([q(1, "rejected"), q(2, "unverified"), q(3, "needs_review")])
        code, exam, err = self.cli_ingest(d, "any")
        self.assertEqual(code, 0)
        side = json.load(open(exam + ".assembly.json"))
        self.assertEqual([s["printed"] for s in side["skipped"]], ["1"])
        self.assertEqual([r["printed"] for r in side["rows"]] if "rows" in side else ["2", "3"], ["2", "3"])
        self.assertIn("printed numbers: 1=2, 2=3", open(exam).read())

    def test_refined_gap_in_ids(self):
        d = rdoc([61, 62, 63], {61: "rejected", 62: "verified", 63: "verified"})  # first dropped
        t = api._from_refined(d, None, {"min_verification": "verified"})
        self.assertIn("1=62, 2=63", t)
        self.assertNotIn("refined 61", t)

    @unittest.expectedFailure  # DEFECT QA-1 (pre-existing): ungated ids 61,63,64 still get "N + 60"
    def test_refined_source_gap_no_offset_line(self):
        t = api._from_refined(rdoc([61, 63, 64]), None, {"min_verification": "verified"})
        self.assertNotIn("N + ", t)

    def test_refined_all_skipped_raises(self):
        d = rdoc([61], {61: "rejected"})
        with self.assertRaises(api.IngestError):
            api._from_refined(d, None, {"min_verification": "any"})

    def test_carrier_skipped_rejected_at_any(self):
        qs = [q(1, "rejected", context="Questions 1-2: read the PASSAGE-Y text."), q(2, "verified")]
        for lvl in ("verified", "any"):
            t = api.to_exam_text(doc_of(qs), {"min_verification": lvl})
            self.assertIn("PASSAGE-Y", t, lvl)
            self.assertNotIn("ALPHA-ONE", t, lvl)

    def test_stale_or_corrupt_sidecar(self):
        p = os.path.join(self.tmp, "x.md")
        for body in ('{"skipped": "abc"}', '{"skipped": {"a": 1}}', '{"skipped": [1, 2]}',
                     '{"skipped": [{"status": "rejected"}]}', '[1]', '{"skipped": null}', '', '{"rows": []}'):
            open(p + ".assembly.json", "w").write(body)
            self.assertEqual(er._skipped_unverified(p), [], body)
        open(p + ".assembly.json", "w").write('{"skipped": [{"printed": 3, "status": "rejected", "reasons": null}]}')
        self.assertEqual(er._skipped_unverified(p), [{"printed": "3", "status": "rejected", "reasons": []}])

    def test_solve_corrupt_sidecar_does_not_crash_result(self):
        p = os.path.join(self.tmp, "x.md")
        open(p + ".assembly.json", "wb").write(b"\xff\xfe\x00")
        self.assertEqual(er._skipped_unverified(p), [])

    def test_byte_identical_without_verification(self):
        d1 = doc_of([q(1), q(2), q(3)])
        out = {}
        for lvl in ("verified", "any"):
            self.tmp = tempfile.mkdtemp(prefix="sg_qa_" + lvl)  # same file name: the sidecar records it
            self.addCleanup(shutil.rmtree, self.tmp, True)
            code, exam, _ = self.cli_ingest(d1, lvl, name="n")
            self.assertEqual(code, 0)
            out[lvl] = (open(exam, "rb").read(), open(exam + ".assembly.json", "rb").read())
        self.assertEqual(out["verified"], out["any"])
        self.assertNotIn(b"skipped", out["any"][1])

    def test_plain_exam_md_byte_identical(self):
        with open(os.path.join(ROOT, "examples", "english", "input-001.md"), encoding="utf-8") as fh:
            text = fh.read()
        d = {"source": {"name": "i.md", "format": "md", "text": text,
                        "sha256": hashlib.sha256(text.encode()).hexdigest()}, "meta": {}, "pages": [], "questions": []}
        for lvl in ("verified", "any"):
            self.assertEqual(api.to_exam_text(d, {"min_verification": lvl}), text)


if __name__ == "__main__":
    unittest.main()
