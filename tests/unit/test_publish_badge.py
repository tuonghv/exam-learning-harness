"""TASK-095 / REQ-0102 (95.1, 95.2): run-list plan-run `publish` from main report links; generated files not `unregistered`.

$0: tmp trees, no network. Reuses the TASK-094 fixtures."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_publish import Base, cli, jwrite, jread, quiet, runlayout  # noqa: E402
from exam_engine.pipeline import report_kinds  # noqa: E402


def man(rid_list, status="complete", link=None, exam="ex"):
    m = {"cmd": "report", "status": status, "exam_id": exam, "created_utc": "2024-01-01T00:00:00Z",
         "plan_runs": [{"exam_id": exam, "line": ln, "plan_run_id": pid} for ln, pid in rid_list]}
    if link:
        m["link"] = link
    return m


class Badge(Base):
    def report_run(self, line, manifest, name="run-20240102-000000"):
        d = os.path.join(self.reports, "ex", line, name)
        os.makedirs(d)
        jwrite(os.path.join(d, "run.json"), manifest)
        return d

    def pub(self, *extra):
        code, out, err = quiet(cli.run_list_main, ["ex"] + list(extra))
        self.assertEqual(code, 0, err)
        sec = out.split("## Report runs")[0]
        rows = [[c.strip() for c in ln.split("|")[1:-1]] for ln in sec.splitlines()
                if ln.startswith("| ") and "---" not in ln]
        h = rows[0]
        return {r[0].split(" ")[0]: r[h.index("publish")] for r in rows[1:]}, out

    def setUp(self):
        super().setUp()
        self.plan("ex", "main", "20240101-000001-a", "A")
        self.plan("ex", "f", "20240101-000002-b", "B")

    def test_95_1a_linked_by_complete_main_report_is_published_unlinked_main_is_dev(self):
        self.report_run("main", man([("f", "20240101-000002-b")]))
        got, _ = self.pub()
        self.assertEqual(got, {"20240101-000001-a": "dev", "20240101-000002-b": "published"})

    def test_95_1a_lines_table_and_report_publish_column_unchanged(self):
        self.report_run("main", man([("f", "20240101-000002-b")]))
        self.report_run("f", man([("f", "20240101-000002-b")]))
        before = runlayout.lines_table(os.path.join(self.reports, "ex"))
        _, out = self.pub()
        rep = [ln for ln in out.split("## Report runs")[1].splitlines() if ln.startswith("| run-")]
        self.assertEqual(sorted(c.split("|")[-2].strip() for c in rep), ["dev", "published"])  # by line
        self.assertEqual(runlayout.lines_table(os.path.join(self.reports, "ex")), before)

    def test_95_1_dev_line_dev_until_published_then_published(self):
        d = self.plan("ex", "f", "20240101-000003-c", "C")
        quiet(cli.report_pack_main, [d, "--exam", "ex", "--no-pdf", "--run", "f"])
        self.protect()
        got, _ = self.pub()
        self.assertEqual(got["20240101-000003-c"], "dev")
        code, _, err = quiet(cli.publish_main, ["ex", "--no-pdf", "--from", "f"])
        self.assertEqual(code, 0, err)
        got, _ = self.pub()
        self.assertEqual(got["20240101-000003-c"], "published")
        self.assertEqual(got["20240101-000001-a"], "dev")

    def test_95_1b_legacy_link_line_links_nothing(self):
        self.report_run("main", man([], link="line"))
        self.report_run("main", man([], link="unknown"), "run-20240103-000000")
        got, _ = self.pub()
        self.assertEqual(set(got.values()), {"dev"})

    def test_95_1c_incomplete_or_unreadable_main_report_does_not_publish(self):
        d = self.report_run("main", man([("f", "20240101-000002-b")], status="running"))
        got, _ = self.pub()
        self.assertEqual(got["20240101-000002-b"], "dev")
        with open(os.path.join(d, "run.json"), "w") as fh:
            fh.write("{not json")
        got, _ = self.pub()
        self.assertEqual(got["20240101-000002-b"], "dev")

    def test_95_1c_dev_line_report_alone_does_not_publish(self):
        self.report_run("f", man([("f", "20240101-000002-b")]))
        got, _ = self.pub()
        self.assertEqual(got["20240101-000002-b"], "dev")

    def test_95_1d_line_filter_still_sees_main_publications(self):
        self.report_run("main", man([("f", "20240101-000002-b")]))
        got, _ = self.pub("--line", "f")
        self.assertEqual(got, {"20240101-000002-b": "published"})

    def test_95_1e_alias_plan_run_id_still_links(self):
        d = os.path.join(self.plans, "ex", "f", "runs", "20240101-000002-b")
        meta = jread(os.path.join(d, "plan.json"))
        meta["plan_run_id"] = "OLD-ID"
        jwrite(os.path.join(d, "plan.json"), meta)
        self.report_run("main", man([("f", "OLD-ID")]))
        got, _ = self.pub()
        self.assertEqual(got["20240101-000002-b"], "published")


class IndexScan(Base):
    def unreg(self, folder):
        md = report_kinds.render_index(folder)
        return [ln for ln in md.splitlines() if "unregistered" in ln and ln.startswith("|")], md

    def build(self):
        ex = os.path.join(self.reports, "ex")
        run = os.path.join(ex, "f", "run-20240101-000000")
        os.makedirs(run)
        jwrite(os.path.join(run, "run.json"), man([("f", "x")]))
        for p in (os.path.join(ex, "f"), run):
            with open(os.path.join(p, "INDEX.md"), "w") as fh:
                fh.write("# Reports index: f\n\nbody\n")
        return ex

    def test_95_2a_generated_index_and_run_json_not_unregistered(self):
        ex = self.build()
        rows, md = self.unreg(ex)
        self.assertEqual(rows, [], md)
        self.assertIn("- unregistered: 0", md)

    def test_95_2a_unknown_files_still_flagged(self):
        ex = self.build()
        for rel in ("notes.txt", "stray.dat", os.path.join("f", "notes.txt")):
            with open(os.path.join(ex, rel), "w") as fh:
                fh.write("x\n")
        rows, md = self.unreg(ex)
        self.assertEqual(len(rows), 3, md)
        self.assertIn("- unregistered: 3", md)

    def test_95_2a_index_md_without_generated_header_still_flagged(self):
        ex = self.build()
        os.makedirs(os.path.join(ex, "f", "x"))
        with open(os.path.join(ex, "f", "x", "INDEX.md"), "w") as fh:
            fh.write("my notes\n")
        with open(os.path.join(ex, "f", "run-20240101-000000", "run.json"), "w") as fh:
            fh.write("{}")  # not an engine manifest (no plan_runs list)
        rows, md = self.unreg(ex)
        self.assertEqual(len(rows), 2, md)


if __name__ == "__main__":
    unittest.main()
