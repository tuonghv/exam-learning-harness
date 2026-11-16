"""TASK-132 (REQ-0139): a subject without Latin letters or none still gets valid report names. $0."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from exam_engine.pipeline import report_kinds as rk  # noqa: E402
from exam_engine.pipeline import reporter  # noqa: E402
from test_exam_report import result  # noqa: E402


class SubjectSlug(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, True)

    def test_non_latin_missing_and_reserved_subjects(self):
        for subj in ("数学", "", None, "All", "---"):
            n = reporter.default_names(result(subject=subj), self.out)
            self.assertEqual(n["subject"], "subject", subj)
            rk.name(n["exam"], n["subject"], "answer-sheet", n["run"], "md")  # no ValueError

    def test_latin_subject_unchanged(self):
        self.assertEqual(reporter.default_names(result(subject="Math"), self.out)["subject"], "math")
        self.assertEqual(reporter.default_names(result(subject="Tư duy khoa học"), self.out)["subject"],
                         rk.slug("Tư duy khoa học"))

    def test_reports_written_for_non_latin_subject(self):
        rep = reporter.write_reports(result(subject="数学"), self.out, pdf=False)
        self.assertTrue(os.path.isfile(rep["md"]))
        self.assertTrue(os.path.isfile(rep["answers"]))
        self.assertIn("_subject_answer-sheet_", os.path.basename(rep["answers"]))


if __name__ == "__main__":
    unittest.main()
