"""TASK-076 QA round 2: 76.4 group figure sharing must not share falsely; 76.5 adjudication prompt options."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import test_exam_run as T  # noqa: E402
import test_image_check as TI  # noqa: E402
from test_engine_fixes_2025 import gq  # noqa: E402
from exam_engine import engine as er  # noqa: E402
from exam_engine.ingest import api  # noqa: E402
from exam_engine.pipeline import cross, parser, solver  # noqa: E402

META = {"Subject": "X", "Level": "L", "Exam type": "E", "Task": "T", "Mode": "M"}


def figs(q):
    return q["figures"]


class FalseSharing(unittest.TestCase):
    """76.4: only the carrier's figures travel, only to members of its own range."""

    def test_two_groups_two_tables_do_not_cross(self):
        qs = [gq(1, 5, "Questions 1-2: Read A.", ["tableA"]), gq(2, 5),
              gq(3, 6, "Questions 3-4: Read B.", ["tableB"]), gq(4, 6)]
        sh = api._share_context(qs)
        self.assertEqual([figs(q) for q in sh], [["tableA"], ["tableA"], ["tableB"], ["tableB"]])
        self.assertEqual([q.get("continued_pages") for q in sh], [None, None, None, None])

    def test_group_without_table_after_group_with_table(self):
        qs = [gq(1, 5, "Questions 1-2: Read A.", ["tableA"]), gq(2, 5),
              gq(3, 6, "Questions 3-4: Read B."), gq(4, 7)]
        sh = api._share_context(qs)
        self.assertEqual([figs(q) for q in sh[2:]], [[], []])
        self.assertEqual(sh[3].get("continued_pages"), [6])  # carrier page only (no figure needed)

    def test_non_first_member_figure_not_shared(self):
        qs = [gq(1, 5, "Questions 1-3: Read."), gq(2, 5, figs=["own2"]), gq(3, 5)]
        sh = api._share_context(qs)
        self.assertEqual([figs(q) for q in sh], [[], ["own2"], []])

    def test_question_after_range_gets_nothing(self):
        qs = [gq(1, 5, "Questions 1-2: Read.", ["tableA"]), gq(2, 5), gq(3, 5), gq(4, 6, figs=["f4"])]
        sh = api._share_context(qs)
        self.assertEqual((figs(sh[2]), figs(sh[3])), ([], ["f4"]))
        self.assertNotIn("continued_pages", sh[2])

    def test_carrier_figure_then_member_own_figure_keep_order_no_dup(self):
        qs = [gq(1, 5, "Questions 1-3: Read.", ["tab"]), gq(2, 5, figs=["own"]), gq(3, 5, figs=["tab"])]
        sh = api._share_context(qs)
        self.assertEqual(figs(sh[1]), ["tab", "own"])
        self.assertEqual(figs(sh[2]), ["tab"])

    def test_two_tables_on_carrier_both_shared(self):
        qs = [gq(1, 5, "Questions 1-2: Read.", ["t1", "t2"]), gq(2, 5)]
        self.assertEqual(figs(api._share_context(qs)[1]), ["t1", "t2"])

    def test_overlapping_range_new_carrier_not_old_table(self):
        qs = [gq(1, 5, "Questions 1-5: Read.", ["tabOld"]), gq(2, 5),
              gq(3, 6, "Questions 3-6: New.", ["tabNew"]), gq(4, 6), gq(5, 6), gq(6, 6)]
        sh = api._share_context(qs)
        self.assertEqual([figs(q) for q in sh], [["tabOld"], ["tabOld"], ["tabNew"], ["tabNew"], ["tabNew"], ["tabNew"]])

    def test_nested_range_inner_members_use_inner_carrier(self):
        qs = [gq(1, 5, "Questions 1-6: Read.", ["outer"]), gq(2, 5),
              gq(3, 6, "Questions 3-4: Inner.", ["inner"]), gq(4, 6), gq(5, 6), gq(6, 6)]
        sh = api._share_context(qs)
        self.assertEqual([figs(q) for q in sh[:4]], [["outer"], ["outer"], ["inner"], ["inner"]])
        for q in sh[4:]:  # after the inner range: no figure of the inner group leaks
            self.assertNotIn("inner", figs(q))

    def test_member_id_not_numeric_or_below_range_untouched(self):
        qs2 = [gq(1, 5, "Questions 2-3: Read.", ["t"]), gq(1, 5)]
        qs2[1]["id"] = "x"
        self.assertEqual(figs(api._share_context(qs2)[1]), [])

    def test_unlabelled_context_member_gets_figure_line_and_pages(self):
        qs = [gq(1, 5, "Questions 1-2: Read.", ["tab"]), gq(2, 6)]
        sh = api._share_context(qs)
        ln = "\n".join(api.question_lines(sh[1]))
        self.assertEqual(ln.count("[Figure/table: tab]"), 1)
        self.assertIn("Source pages: 5-6", ln)

    def test_multiline_table_shared_intact(self):
        tab = "Table with columns A, B; rows: 1 2; 3 4\nsecond line of the table"
        sh = api._share_context([gq(1, 5, "Questions 1-2: Read.", [tab]), gq(2, 5)])
        self.assertEqual(figs(sh[1]), [tab])

    def test_input_not_mutated(self):
        qs = [gq(1, 5, "Questions 1-2: Read.", ["tab"]), gq(2, 6)]
        api._share_context(qs)
        self.assertEqual((qs[1]["figures"], "continued_pages" in qs[1]), ([], False))


def doc_of(qs):
    return {"meta": dict(META), "source": {"name": "x"}, "refined": {"questions": [
        dict(q, options={"A": "a", "B": "b", "C": "c", "D": "d"}) for q in qs]}}


class SliceAndPages(unittest.TestCase):
    def setUp(self):
        self.qs = [gq(1, 5, "Questions 1-3: Read.", ["tab"]), gq(2, 6), gq(3, 6), gq(4, 7, figs=["f4"])]

    def test_slice_with_only_carrier(self):
        qs, lines, _ = api._selected_refined(doc_of(self.qs), "1")
        self.assertEqual(len(qs), 1)
        self.assertEqual("\n".join(lines[0]).count("[Figure/table: tab]"), 1)

    def test_slice_members_only_still_get_table_and_carrier_page(self):
        qs, lines, why = api._selected_refined(doc_of(self.qs), "2-3")
        self.assertEqual([q["id"] for q in qs], ["2", "3"])
        for ln in lines:
            t = "\n".join(ln)
            self.assertIn("[Figure/table: tab]", t)
            self.assertIn("Source pages: 5-6", t)
        self.assertEqual(why, [[], []])

    def test_slice_outside_member_has_no_group_table(self):
        qs, lines, _ = api._selected_refined(doc_of(self.qs), "4")
        self.assertNotIn("tab]", "\n".join(lines[0]))

    def test_member_pages_reach_parsed_exam_and_page_cap_holds(self):
        # carrier on p16, members on p17..p20: each member alone fits; the union must stay <= 4 pages
        qs = [gq(1, 16, "Questions 1-5: Read.", ["tab"]), gq(2, 17), gq(3, 18), gq(4, 19), gq(5, 20)]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(api._from_refined(doc_of(qs)))
            ex = parser.parse_exam(p)
        by = {q["id"]: q for q in ex["questions"]}
        self.assertEqual(by[2]["pages"], [16, 17])
        self.assertEqual(by[5]["pages"], [16, 20])
        flags = {i: ["figure/table"] for i in by}
        tg, pages, skipped = er.image_targets(ex, flags, set(), 4, None, None)
        self.assertLessEqual(len(pages), 4)
        self.assertEqual(sorted(tg + list(skipped)), [1, 2, 3, 4, 5])
        self.assertTrue(all(v == "page_cap" for v in skipped.values()))
        self.assertEqual(skipped.keys() and sorted(skipped), [5])  # p16,17,18,19 fill the cap; 5 needs p20

    def test_default_cap_is_four(self):
        with open(os.path.join(os.path.dirname(HERE), "..", "src", "exam_engine", "cli.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("max_image_pages=4 if a.max_image_pages is None", src)


class LabelledPrompt(unittest.TestCase):
    def prompt(self, spec):
        qs = [gq(1, 16, "Dựa vào thông tin dưới đây để trả lời các câu từ 1 đến 4", ["TABLE-X"]),
              gq(2, 16), gq(3, 17), gq(4, 17)]
        txt = api._from_refined(doc_of(qs), spec)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(txt)
            ex = parser.parse_exam(p)
        ids = {q["id"] for q in ex["questions"]}
        return solver.solve_prompt(ex, txt, None, ids)

    def test_group_members_are_one_group_and_table_overhead_is_bounded(self):
        pr = self.prompt(None)
        # design intent (76.4): the shared table is a small overhead, not more than passage + one per member
        self.assertLessEqual(pr.count("[Figure/table: TABLE-X]"), 5)  # group Passage + 4 stems today
        self.assertGreaterEqual(pr.count("[Figure/table: TABLE-X]"), 1)

    def test_gap_table_emitted_once_per_group(self):
        # D4: the figure line sits in each member's `### Question text` (after the stem), so the labelled
        # render repeats it per member instead of once in the group's Passage.
        self.assertEqual(self.prompt(None).count("[Figure/table: TABLE-X]"), 1)


class AdjudicatePromptOptions(unittest.TestCase):
    def setUp(self):
        qs = ["Q-one\n\nA. o1a\nB. o1b\nC. o1c\nD. o1d", "Q-two\n\nA. o2a\nB. o2b\nC. o2c\nD. o2d",
              "Q-three\n[Figure/table: tab3]\n\nA. o3a\nB. o3b\nC. o3c\nD. o3d", "Q-four\n\nA. o4a\nB. o4b\nC. o4c\nD. o4d"]
        with tempfile.TemporaryDirectory() as d:
            self.ex = TI.load(d, TI.exam(*qs))

    def test_every_conflict_item_has_all_options_and_no_other_question(self):
        items = [(1, T.a(1, "A"), T.a(1, "B")), (3, T.a(3, "C"), T.a(3, "D"))]
        pr = cross.adjudicate_prompt(self.ex, items)
        for n in (1, 3):
            for k in "abcd":
                self.assertIn("%s. o%d%s" % (k.upper(), n, k), pr)
        self.assertIn("[Figure/table: tab3]", pr)
        for n in (2, 4):
            self.assertNotIn("o%d" % n, pr)
            self.assertNotIn("Q-%s" % ("two", "", "four")[n - 2], pr)
        self.assertEqual(pr.count("o1a"), 1)
        self.assertEqual(pr.count("o3d"), 1)

    def test_option_block_follows_its_own_question(self):
        pr = cross.adjudicate_prompt(self.ex, [(3, T.a(3, "C"), T.a(3, "D")), (1, T.a(1, "A"), T.a(1, "B"))])
        self.assertLess(pr.index("Q-three"), pr.index("o3a"))
        self.assertLess(pr.index("o3d"), pr.index("id 1:"))
        self.assertLess(pr.index("id 1:"), pr.index("o1a"))

    def test_question_without_options_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            ex = TI.load(d, TI.exam("Compute 2+2. Answer: number."))
        pr = cross.adjudicate_prompt(ex, [(1, T.a(1, "4"), T.a(1, "5"))])
        self.assertIn("id 1: Compute 2+2", pr)
        self.assertNotIn("\nA. ", pr)


if __name__ == "__main__":
    unittest.main()
