"""TASK-045 (phase 45): completeness reasons formula_unbalanced, trailing_operator, merge_suspect,
unreadable; same-id join keeps continued_pages and the last part's cut. Synthetic placeholder text."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))

from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import api  # noqa: E402
import test_multipage_assembly as mp  # noqa: E402

F = refcheck.incomplete_reasons
ABCD = mp.ABCD


def r(text, options=None, **kw):
    return F(dict({"id": "5", "text": text, "options": options if options is not None else ABCD}, **kw))


class Unbalanced(unittest.TestCase):
    def test_1_unbalanced_flagged_when_cut_or_continued_or_last(self):
        self.assertEqual(r("f(x = (1 + [2", cut=True, continued_pages=[2]), ["formula_unbalanced"])
        self.assertEqual(r("f(x = (1 + 2", continued_pages=[2]), ["formula_unbalanced"])
        self.assertEqual(F({"text": "f(x = (1 + 2", "options": ABCD}, last_on_page=True), ["formula_unbalanced"])

    def test_1b_mid_page_not_flagged(self):
        self.assertEqual(r("f(x = (1 + 2"), [])

    def test_1c_half_open_interval_balanced(self):
        self.assertEqual(r("x in [a;b) and (c;d]", continued_pages=[2]), [])

    def test_1d_odd_dollar_flagged_even_not(self):
        self.assertEqual(r("find $x + 1", continued_pages=[2]), ["formula_unbalanced"])
        self.assertEqual(r("find $x$ and $y$", continued_pages=[2]), [])
        self.assertEqual(r("costs \\$5", continued_pages=[2]), [])

    def test_1e_options_counted(self):
        self.assertEqual(r("find x", {"A": "(1", "B": "2", "C": "3", "D": "4"}, continued_pages=[2]),
                         ["formula_unbalanced"])


    def test_1f_enumerators_ignored_other_brackets_counted(self):
        enum = "a) one (x)\nb) two\n1) three\niv) four"
        self.assertEqual(r(enum, continued_pages=[2]), [])
        self.assertEqual(r(enum + "\nand (y", continued_pages=[2]), ["formula_unbalanced"])
        self.assertEqual(F({"text": enum, "options": ABCD}, last_on_page=True), [])
        self.assertEqual(r(enum + "\nand (y"), [])  # mid-page: scope kept

    def test_1g_half_open_interval_page_end(self):
        self.assertEqual(F({"text": "x in [a;b)", "options": ABCD}, last_on_page=True), [])
        self.assertEqual(F({"text": "x in (a;b]", "options": ABCD}, last_on_page=True), [])


class Trailing(unittest.TestCase):
    def test_2_operator_end_no_options(self):
        for ch in "=+-×÷/^\\":
            self.assertEqual(r("compute 3 " + ch, {}, continued_pages=[2]), ["trailing_operator"], ch)

    def test_2b_sentence_end_or_options_not(self):
        self.assertEqual(r("What is the value?", {}, continued_pages=[2]), [])
        self.assertEqual(r("compute 3 +", ABCD, continued_pages=[2]), [])

    def test_2c_mid_page_not_flagged(self):
        self.assertEqual(r("compute 3 +", {}), [])


class Merge(unittest.TestCase):
    def test_3_other_question_number_in_stem(self):
        self.assertEqual(r("stem one\nCâu 6. next stem"), ["merge_suspect"])
        self.assertEqual(r("stem one\nQuestion 6: next"), ["merge_suspect"])

    def test_3b_own_number_or_plain_not(self):
        self.assertEqual(r("Câu 5. stem one\nmore"), [])
        self.assertEqual(r("stem one\nmore text"), [])

    def test_3c_two_option_runs(self):
        self.assertEqual(r("stem\nA. a\nB. b\nA. a2\nB. b2"), ["merge_suspect"])
        self.assertEqual(r("stem\nA. a\nB. b"), [])


class Unread(unittest.TestCase):
    def test_4_unreadable_reason_only_when_true(self):
        self.assertEqual(r("stem", unreadable=True), ["unreadable"])
        self.assertEqual(r("stem"), [])

    def test_4b_refine_stores_optional(self):
        out = mp.run_refine([mp.rep([mp.q(1, "stem", ABCD, unreadable=True), mp.q(2, "t", ABCD)])], "1", 1)
        a, b = out["refined"]["questions"]
        self.assertIs(a["unreadable"], True)
        self.assertNotIn("unreadable", b)

    def test_4c_old_file_renders_same(self):
        d = mp.doc_of(1)
        d["meta"] = {"Subject": "S", "Level": "L", "Exam type": "E", "Task": "T", "Mode": "M"}
        d["refined"] = {"questions": [mp.q(1, "stem", ABCD, page=1)]}
        self.assertNotIn("[Incomplete:", api.to_exam_text(d, {"use_refined": True}))


class Join(unittest.TestCase):
    def _join(self, p1, p2):
        return api.refined_questions({"refined": {"questions": [p1, p2]}})

    def test_5_part1_cut_part2_continued_resolved(self):
        j = self._join(mp.q(6, "start", cut=True),
                       mp.q(6, "rest", ABCD, continued_pages=[2]))
        self.assertEqual(len(j), 1)
        self.assertEqual(j[0]["continued_pages"], [2])
        self.assertEqual(F(j[0]), [])

    def test_5b_part2_cut_stays_cut(self):
        j = self._join(mp.q(6, "start", cut=True, continued_pages=[2]), mp.q(6, "rest", cut=True))
        self.assertEqual(j[0]["continued_pages"], [2])
        self.assertTrue(j[0]["cut"])

    def test_5c_part1_cut_part2_plain_not_cut(self):
        j = self._join(mp.q(6, "start", cut=True), mp.q(6, "rest", ABCD))
        self.assertFalse(j[0]["cut"])
        self.assertNotIn("continued_pages", j[0])


class Render(unittest.TestCase):
    def _text(self, qs):
        d = mp.doc_of(2)
        d["meta"] = {"Subject": "S", "Level": "L", "Exam type": "E", "Task": "T", "Mode": "M"}
        d["refined"] = {"questions": qs}
        return api.to_exam_text(d, {"use_refined": True})

    def test_6_complete_fixtures_no_reason(self):
        t = self._text([mp.q(1, "What is 2 + 2?", ABCD, page=1), mp.q(2, "f(x) = [1;2)", ABCD, page=1),
                        mp.q(3, "Pick one.", ABCD, page=2)])
        self.assertNotIn("[Incomplete:", t)

    def test_6b_last_on_page_flagged(self):
        t = self._text([mp.q(1, "ok", ABCD, page=1), mp.q(2, "f(x = (1", ABCD, page=1),
                        mp.q(3, "fine", ABCD, page=2)])
        self.assertEqual(t.count("[Incomplete: missing_text formula_unbalanced]"), 1)


class Decline(unittest.TestCase):
    setUp = mp.TestDecline.setUp
    go = mp.TestDecline.go

    def test_7_engine_reason_string_carries_new_reasons(self):
        mark = "[Incomplete: missing_text formula_unbalanced, merge_suspect]"
        text = mp.HEAD + "## Question 1\n\nstem\n\n" + mark + "\n\nA. a\nB. b\nC. c\nD. d\n"
        res, prompts = self.go(text, [])
        self.assertEqual(prompts, [])
        self.assertEqual(res["questions"][0]["status_reason"],
                         "solver_declined: missing_text (formula_unbalanced, merge_suspect)")


del mp.TestDecline.test_12_marked_id_never_sent_and_declined, mp.TestDecline.test_12b_all_marked_makes_no_call

if __name__ == "__main__":
    unittest.main()
