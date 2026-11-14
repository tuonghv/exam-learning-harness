"""TASK-105 / REQ-0111 (105.1-105.5): tracked recipe + `exam rebuild-reports`. $0, synthetic tmp tree, no network.

Fixture (test_overlay.Base): exam `ex`, base line f (Math, Science, Physics; Physics printed 12 declined),
overlay line g fixes printed 12. The first publish is built with a fixed run id so old/new runs are told apart."""
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
import test_overlay as to  # noqa: E402
from exam_engine import cli  # noqa: E402
from exam_engine.pipeline import reporter, runlayout  # noqa: E402

TRACKED = os.path.join(ROOT, "config", "published_reports.json")
OLD_ID = "20200101-000000"
PACK_ID = "20200101-000001"


def recipe_for(key_sha):
    return {"version": 1, "exams": {"ex": {
        "line": "f", "view": "sheet", "pdf": False,
        "plan_runs": ["plans/ex/f/runs/20240101-000001-math", "plans/ex/f/runs/20240101-000002-sci",
                      "plans/ex/f/runs/20240101-000003-phy"],
        "key": "input/key.txt", "key_sha256": key_sha,
        "overlays": [{"dir": "plans/ex/g/runs/20240102-000001-ov", "printed": [12], "reason": to.REASON}]}}}


class RebuildBase(to.Base):
    def setUp(self):
        super().setUp()
        os.makedirs("input")
        with open("input/key.txt", "w", encoding="utf-8") as fh:
            fh.write("\t".join("Câu %d. %s" % (i, "ABCD"[i % 4]) for i in range(1, 14)) + "\n")
        self.recipe_path = os.path.join(self.tmp, "recipe.json")
        self.recipe = recipe_for(to.sha("input/key.txt"))
        self.save_recipe()
        # a published state to rebuild: pack on line f (with overlay), then publish --from f
        with mock.patch.object(runlayout, "new_run_id", return_value=OLD_ID):
            code, _, err = to.quiet(cli.report_pack_main, [
                "plans/ex/f/runs/20240101-000001-math", "plans/ex/f/runs/20240101-000002-sci",
                "plans/ex/f/runs/20240101-000003-phy", "--exam", "ex", "--no-pdf", "--key", "input/key.txt",
                "--out", os.path.join(self.reports, "ex", "f", "run-" + PACK_ID),
                "--overlay", "plans/ex/g/runs/20240102-000001-ov:12", "--overlay-reason", to.REASON])
            self.assertEqual(code, 0, err)
            code, _, err = to.quiet(cli.publish_main, ["ex", "--from", "f", "--key", "input/key.txt", "--no-pdf",
                                                        "--plans", self.plans, "--reports", self.reports])
            self.assertEqual(code, 0, err)

    def save_recipe(self):
        to.jwrite(self.recipe_path, self.recipe)

    def run_rb(self, *args):
        return to.quiet(cli.rebuild_reports_main, ["--recipe", self.recipe_path] + list(args))

    def state(self):
        return to.snapshot(self.reports), to.snapshot(self.plans)

    def runs(self, line):
        return sorted(n for n in os.listdir(os.path.join(self.reports, "ex", line)) if n.startswith("run-"))

    def main_runs(self):
        return self.runs("main")


class T1Recipe(RebuildBase):
    def test_105_1_tracked_recipe_schema(self):
        rec = cli._load_recipe(TRACKED)
        self.assertEqual(len(rec["exams"]), 3)
        dh = [c for c in rec["exams"].values() if len(c["overlays"]) == 1]
        self.assertEqual(len(dh), 1)
        self.assertEqual(dh[0]["overlays"][0]["printed"], [64, 65, 66, 67])
        self.assertTrue(dh[0]["overlays"][0]["reason"].strip())

    def test_105_1_loader_refuses_bad_recipes(self):
        for name, mut in (("version", lambda r: r.update(version=2)),
                          ("field", lambda r: r["exams"]["ex"].pop("key_sha256")),
                          ("type", lambda r: r["exams"]["ex"].update(pdf="yes")),
                          ("line", lambda r: r["exams"]["ex"].update(line="../x")),
                          ("exam id", lambda r: r["exams"].update({"../e": r["exams"]["ex"]})),
                          ("reason", lambda r: r["exams"]["ex"]["overlays"][0].update(reason=" "))):
            rec = json.loads(json.dumps(self.recipe))
            mut(rec)
            to.jwrite(self.recipe_path, rec)
            with self.assertRaises(ValueError, msg=name):
                cli._load_recipe(self.recipe_path)


class T2WriteRecipe(RebuildBase):
    def test_105_2_seed_equals_expected(self):
        os.remove(self.recipe_path)
        code, out, err = to.quiet(cli.rebuild_reports_main, ["--recipe", self.recipe_path, "--write-recipe"])
        self.assertEqual(code, 0, err)
        self.assertEqual(to.jread(self.recipe_path), self.recipe)
        with open(self.recipe_path, encoding="utf-8") as fh:
            self.assertTrue(fh.read().endswith("}\n"))


class T3DryRunAndPrechecks(RebuildBase):
    def test_105_4_dry_run_lists_and_writes_nothing(self):
        before = self.state()
        code, out, err = self.run_rb("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.state(), before)
        self.assertIn("delete", out)
        self.assertIn("run-" + OLD_ID, out)
        self.assertIn("call report-pack", out)
        self.assertIn("call publish ex --from f", out)

    def test_105_3_missing_plan_run_refused_nothing_deleted(self):
        os.remove("plans/ex/f/runs/20240101-000002-sci/result.json")
        before = self.state()
        code, _, err = self.run_rb()
        self.assertEqual(code, 2)
        self.assertIn("ERROR: ex:", err)
        self.assertEqual(self.state(), before)

    def test_105_3_changed_key_refused_nothing_deleted(self):
        with open("input/key.txt", "a", encoding="utf-8") as fh:
            fh.write("x")
        before = self.state()
        code, _, err = self.run_rb()
        self.assertEqual((code, "key_sha256" in err), (2, True))
        self.assertEqual(self.state(), before)

    def test_105_3_missing_overlay_unknown_exam_and_no_renderer(self):
        before = self.state()
        self.assertEqual(self.run_rb("nope")[0], 2)
        self.recipe["exams"]["ex"]["pdf"] = True
        self.save_recipe()
        with mock.patch.object(reporter, "find_pdf_renderer", return_value=None):
            code, _, err = self.run_rb()
        self.assertEqual(code, 2)
        self.assertIn("PDF renderer", err)
        self.recipe["exams"]["ex"]["pdf"] = False
        self.save_recipe()
        shutil.rmtree("plans/ex/g/runs/20240102-000001-ov")
        code, _, err = self.run_rb()
        self.assertEqual((code, "overlay dir" in err), (2, True))
        self.assertEqual(to.snapshot(self.reports), before[0])

    def test_105_5_root_resolves_recipe_paths(self):
        other = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, other, True)
        os.chdir(other)
        code, out, err = self.run_rb("--root", self.tmp, "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("run-" + OLD_ID, out)
        self.assertEqual(os.listdir(other), [])


class T5Rebuild(RebuildBase):
    def test_105_5_rebuild_replaces_main_and_source_pack(self):
        self.assertEqual(self.main_runs(), ["run-" + OLD_ID])
        code, out, err = self.run_rb()
        self.assertEqual(code, 0, err)
        mains = self.main_runs()
        self.assertEqual(len(mains), 1)
        self.assertNotIn("run-" + OLD_ID, mains)
        self.assertEqual(len(self.runs("f")), 1)
        self.assertNotIn("run-" + PACK_ID, self.runs("f"))
        self.assertFalse(os.path.exists(os.path.join(self.plans, "ex", "f", "report-runs", "run-%s.json" % PACK_ID)))
        man = runlayout.read_report_manifest(os.path.join(self.reports, "ex", "main", mains[0]))
        self.assertEqual([p["plan_run_id"] for p in man["plan_runs"]],
                         [os.path.basename(p) for p in self.recipe["exams"]["ex"]["plan_runs"]])
        self.assertEqual(man["published_from"], "f")
        self.assertEqual(len(man["overlays"]), 1)
        self.assertRegex(out, r"rebuilt ex main run-\S+ score \d+/9")

    def test_105_5_main_line_recipe_packs_straight_into_main(self):
        self.recipe["exams"]["ex"]["line"] = "main"
        self.save_recipe()
        code, out, err = self.run_rb()
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.main_runs()), 1)
        self.assertIn("rebuilt ex main", out)
        self.assertEqual(self.runs("f"), ["run-" + PACK_ID])  # dev pack untouched


if __name__ == "__main__":
    unittest.main()
