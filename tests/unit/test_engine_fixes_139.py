"""TASK-139 (REQ-0146): 136-F001/F002/F003/F005 engine fixes. Fakes only, no LLM."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import test_exam_run as T  # noqa: E402
import test_image_check as TI  # noqa: E402
from test_engine_fixes_2025 import FakeRn, rec  # noqa: E402
from exam_engine import engine as er  # noqa: E402

MCQ = (T.HEAD % ("Mathematics", "Multiple Choice") + "## Instructions\n\nPick one.\n\n"
       "## Question 1\n\nWhich is 3+4 or 5+7?\n\nA. 7\nB. 12\nC. 9\nD. 1\n")


class EngineFixes139(TI.Base):
    def setUp(self):
        super().setUp()
        self.mc = TI.load(self.tmp, MCQ)

    def test_f003_image_value_maps_to_letter(self):
        r = rec(T.a(1, "B"), "UNCERTAIN", "x")
        er.apply_image(self.mc, {1: r}, {"1": T.a(1, "12")}, [1], {}, None, "flagged")
        self.assertNotIn("image_differs", [f["code"] for f in r["findings"]])
        self.assertIsNone(r.get("image_ans"))
        self.assertIn("answer_mapped", [f["code"] for f in r["findings"]])

    def test_f002_adjudicated_resets_review_and_checks(self):
        r = rec(T.a(1, "A"), "FAIL", "reviewer_disagrees", review={"verdict": "disagree", "findings": []},
                image_ans=T.a(1, "C"))
        er.adjudicate(self.mc, {1: r}, FakeRn(T.solve(T.a(1, "C"))), [1])
        self.assertEqual(r["ans"]["answer"], "C")
        self.assertIsNone(r["review"])
        self.assertTrue(all(k["kind"] != "ai_review" for k in r["checks"]))

    def test_f001_failed_retry_gets_no_second_qa(self):
        llm = T.Script(T.solve(T.a(1, "A")), T.qa((1, "disagree")), "prose, no json")
        res, _ = self.go(MCQ, llm, max_attempts=2)
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(res["questions"][0]["attempts"], 2)

    def test_f005_marker_reason_kept_after_image_miss(self):
        text = TI.exam("Source pages: 3\n\n[Incomplete: missing_text (options cut)]\n\n" + TI.FIG)
        ex = TI.load(self.tmp, text)
        skip = er.incomplete_ids(ex)
        self.assertEqual(list(skip), [1])
        recs = {1: rec(None, "UNCERTAIN", "solver_declined: missing_text (%s)" % skip[1])}
        image = {"llm": None, "render": lambda n: TI.png(n), "key_pages": set(), "have_pages": None}
        rn = FakeRn(T.solve())
        er.image_check(ex, recs, rn, er.visual_flags(ex), skip, {"image_scope": "declined"}, image)
        self.assertIn("options cut", recs[1]["reason"])


if __name__ == "__main__":
    unittest.main()
