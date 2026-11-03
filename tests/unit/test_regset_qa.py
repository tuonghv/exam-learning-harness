"""TASK-066 QA (66.1-66.4): budget skip, board tier + key labels, tier filter. Fake llm, $0."""
import contextlib
import io
import json
import os
import unittest

import test_regset as base
from exam_engine import cli
from exam_engine.pipeline import benchmark, metrics


class RegSetQA(base.RegSet):
    def setUp(self):
        super().setUp()
        with open(self.items[1]["input"], "a", encoding="utf-8") as fh:
            fh.write("\n")  # distinct exam hash: same hash would pair the two runs as baseline/current

    def board(self, hist):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["run-stats", "board", "--history", hist, "--json"])
        return code, json.loads(out.getvalue())["kinds"]

    def run_set(self, bases=("official", "generated: test")):
        for it, b in zip(self.items, bases):
            it["key_basis"] = b
        sf = self.write({"v": 1, "set_id": "s1", "items": self.items}, "set2.json")
        code, _, err = self.run_cli(["--set", sf, "--mock", self.mock(), "--out", os.path.join(self.root, "o"),
                                     "--history", self.hist])
        self.assertEqual(code, 0, err)

    def test_66_3_budget_reached_skips_the_rest(self):
        _, items, _ = benchmark.load_set(self.setfile)
        cfg = {"max_attempts": 2, "max_cost_usd": 1.0, "timeout": 5, "model": "m", "llm_name": "mock", "pdf": False}
        rows = benchmark.run_all(items, os.path.join(self.root, "o"), cfg, None, 0.0)
        self.assertEqual([r.get("skipped") for r in rows], ["budget_reached"] * 2)
        self.assertFalse(os.path.exists(self.hist))

    def test_66_3_budget_zero_cli_writes_no_history(self):
        code, out, _ = self.run_cli(["--set", self.setfile, "--mock", self.mock(), "--budget-usd", "0",
                                     "--out", os.path.join(self.root, "o"), "--history", self.hist])
        self.assertEqual(code, 3)
        self.assertFalse(os.path.exists(self.hist))
        with open(os.path.join(self.root, "o", "summary.json")) as fh:
            self.assertEqual([s[2] for s in json.load(fh)["skipped"]], ["budget_reached"] * 2)

    def test_66_3_skipped_item_in_a_subject_is_not_a_regression(self):
        def ok(n):
            return {"subject": "a", "item": n, "summary": {"pass": 1, "fail": 0, "uncertain": 0, "unresolved": 0,
                                                            "points": 0, "max_points": 0},
                    "calls": 1, "cost_usd": 0.0, "questions": []}
        meta = {"date": "d", "model": "m", "prompt": "p"}
        prev = benchmark.summarize([ok("1"), ok("2")], meta)
        cur = benchmark.summarize([ok("1"), {"subject": "a", "item": "2", "skipped": "missing"}], meta)
        self.assertEqual(benchmark.regression(prev, cur), [])  # pass count fell 2 -> 1 only because item 2 did not run

    def test_66_2_regset_lines_are_tier_official_others_exploratory(self):
        self.run_set(("official", "official"))
        lines = metrics.read_history(self.hist)[0]
        for i, ln in enumerate(list(lines)):  # same results re-labelled as plain solve runs, other exam hash
            ln = dict(ln, source="solve", run_id="x%d" % i, exam_sha256="f%d" % i)
            metrics.append(self.hist, ln)
        code, kinds = self.board(self.hist)
        tiers = sorted(k.split("|")[0] for k in kinds)
        self.assertIn("official", tiers)
        self.assertIn("exploratory", tiers)
        for k, blk in kinds.items():
            self.assertEqual(blk["tier"], k.split("|")[0])
        off = [b for k, b in kinds.items() if k.startswith("official|")]
        self.assertEqual(sum(b["exams"] for b in off), 2)  # the exploratory copies never pool into official

    def test_66_2_generated_only_kind_labelled_human_only_kind_plain(self):
        self.run_set(("official", "official"))
        _, kinds = self.board(self.hist)
        self.assertFalse(any(b["generated"] for b in kinds.values()))
        os.remove(self.hist)
        self.run_set(("generated: test", "generated: test"))
        _, kinds = self.board(self.hist)
        self.assertTrue(all(b["generated"] for b in kinds.values()))
        txt = "\n".join(metrics.board_text("K", b)[0] for b in kinds.values())
        self.assertIn("key (generated)", txt)

    def test_66_4_mixed_key_bases_split_into_two_rows(self):
        self.run_set()  # default: one official and one generated item of the same kind
        _, kinds = self.board(self.hist)
        tiers = sorted(k.split("|")[0] for k in kinds)
        self.assertEqual(tiers, ["generated", "official"])
        for k, blk in kinds.items():
            self.assertEqual(blk["generated"], k.startswith("generated|"))
        text = "\n".join("\n".join(metrics.board_text(k.split("|", 1)[1], b)) for k, b in kinds.items())
        self.assertIn("key (generated)", text)
        self.assertIn("tier official", text)


for _n in ("test_history_lines_carry_regset_fields", "test_key_text_never_in_history",
           "test_key_text_never_in_prompts", "test_bad_set_file_fails_by_name",
           "test_missing_file_is_skipped_and_run_continues", "test_skipped_item_is_not_a_regression",
           "test_no_set_keeps_discover", "test_example_set_loads_and_paths_exist"):
    setattr(RegSetQA, _n, None)  # inherited cases already run in test_regset

if __name__ == "__main__":
    unittest.main()
