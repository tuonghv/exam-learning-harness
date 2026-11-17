"""TASK-140 / REQ-0147 (140.1-140.3): runlayout fixes 139-F001..F003. $0, tmp trees only."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import runlayout  # noqa: E402

STAMP = "20260101-000000"


class RunlayoutFixes140(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.plans = os.path.join(self.tmp, "plans")
        self.reports = os.path.join(self.tmp, "reports")
        p = mock.patch.object(runlayout, "PROTECTED_ROOTS", (self.plans, self.reports))
        p.start()
        self.addCleanup(p.stop)

    def test_140_1_out_without_line_needs_publish(self):
        for root in (os.path.join(self.reports, "ex", "run-" + STAMP),
                     os.path.join(self.plans, "ex", "runs", STAMP)):
            with self.assertRaises(runlayout.PublishRequired):
                runlayout.require_publish(None, False, "x", root)
            runlayout.require_publish(None, True, "x", root)  # --publish passes
        # a dev line stays free
        runlayout.require_publish(None, False, "x", os.path.join(self.reports, "ex", "v3", "run-a"))

    def test_140_2_reserved_line_names(self):
        for name in ("reports", "plans"):
            with self.assertRaises(ValueError):
                runlayout.safe_line(name)
        self.assertEqual(runlayout.safe_line("v3"), "v3")

    def test_140_3_report_run_suffix_sorts_numerically(self):
        ex = os.path.join(self.reports, "ex")
        for n in range(1, 12):
            os.makedirs(os.path.join(ex, "run-" + (STAMP if n == 1 else "%s-%d" % (STAMP, n))))
        ids = [r["id"] for r in runlayout.scan_report_runs(ex)]
        self.assertEqual(ids[-3:], [STAMP + "-9", STAMP + "-10", STAMP + "-11"])


if __name__ == "__main__":
    unittest.main()
