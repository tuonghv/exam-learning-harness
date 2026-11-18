"""TASK-130 (REQ-0137): review findings ledger check. Temp repo roots, $0."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import review_ledger as L  # noqa: E402

HDR = "\t".join(L.COLUMNS)
REVIEW = "# Review\n\n## Findings\n\n### F001 – [HIGH] a\n\n### F002 – [LOW] b\n"


class Ledger(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        for d in ("docs/report", "docs/review", ".claude/state"):
            os.makedirs(os.path.join(self.root, d))
        self.write("docs/report/phase-140-x-review.md", REVIEW)
        self.write("docs/report/phase-141-fix.md", "# fix report\n\n### Notes\n")  # no finding headings
        self.write(".claude/state/backlog.json", json.dumps(
            [{"task_id": "TASK-141", "status": "done"}, {"task_id": "TASK-150", "status": "queued"},
             {"task_id": "TASK-151", "status": "done"}]))

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def ledger(self, *rows):
        self.write("docs/review/findings.tsv", "\n".join((HDR,) + rows) + "\n")
        return L.check(self.root)

    def row(self, fid, disp, ref, note=""):
        return "\t".join([fid, "phase-140-x-review.md", "BUG", disp, ref, note])

    def test_ids_from_headings_only(self):
        self.assertEqual(L.review_ids(self.root), {"140-F001": "phase-140-x-review.md",
                                                    "140-F002": "phase-140-x-review.md"})

    def test_fable_review_folder_dated_names(self):
        # TASK-147 (RAW-00368/00369): docs/report/fable-review/<date>-phase<N>-<slug>.md
        os.makedirs(os.path.join(self.root, "docs/report/fable-review"))
        self.write("docs/report/fable-review/2026-11-17-phase142-y-b4.md", REVIEW)
        self.write("docs/report/fable-review/notes.md", REVIEW)  # no phase id -> ignored
        ids = L.review_ids(self.root)
        self.assertEqual(ids["142-F001"], "2026-11-17-phase142-y-b4.md")
        self.assertEqual(len(ids), 4)

    def test_clean(self):
        n, n_open, probs = self.ledger(self.row("140-F001", "fixed", "TASK-141"),
                                       self.row("140-F002", "open", "TASK-150"))
        self.assertEqual((n, n_open, probs), (2, 1, []))

    def test_missing_row_reported(self):
        _, _, probs = self.ledger(self.row("140-F001", "fixed", "TASK-141"))
        self.assertEqual(probs, ["140-F002 (phase-140-x-review.md): no ledger row"])

    def test_open_on_closed_task_reported(self):
        _, _, probs = self.ledger(self.row("140-F001", "fixed", "TASK-141"), self.row("140-F002", "open", "TASK-151"))
        self.assertEqual(len(probs), 1)
        self.assertIn("open on TASK-151, which is done", probs[0])

    def test_bad_disposition_ref_waiver_and_unknown_id(self):
        _, _, probs = self.ledger(self.row("140-F001", "later", "TASK-141"), self.row("140-F002", "waived", "-"),
                                  self.row("140-F009", "fixed", "nope"))
        text = " | ".join(probs)
        self.assertIn("disposition 'later'", text)
        self.assertIn("waived without a reason", text)
        self.assertIn("140-F009): no such finding", text)
        self.assertIn("needs a TASK-NNN ref", text)

    def test_main_exit_codes(self):
        self.ledger(self.row("140-F001", "fixed", "TASK-141"))
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(L.main(["--root", self.root]), 1)
        self.assertIn("LEDGER: 2 ids, 0 open, 1 problem(s)", out.getvalue())
        self.ledger(self.row("140-F001", "fixed", "TASK-141"), self.row("140-F002", "not-a-defect", "TASK-141"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(L.main(["--root", self.root]), 0)

    def test_real_repo_ledger_complete(self):
        n, _, probs = L.check(ROOT)
        self.assertGreaterEqual(n, 80)
        self.assertEqual(probs, [])


if __name__ == "__main__":
    unittest.main()
