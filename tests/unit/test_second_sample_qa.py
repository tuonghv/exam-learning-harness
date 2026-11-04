"""TASK-075 QA of 75.2: permutation mapping, comparison in the original letter space, caps, scope.
Fake llm only. A mock answers by option TEXT (must agree on every sampled id) or by LETTER (must differ)."""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "..", "src"))
sys.path.insert(0, HERE)
from exam_engine import engine as eng  # noqa: E402
from exam_engine.pipeline import solver  # noqa: E402
import test_exam_run as t  # noqa: E402

N = 35
FIRST = {i: "ABCD"[i % 4] for i in range(1, N + 1)}  # first answers, all four letters used


def opt(i, k):
    return "T%d%s" % (i, k)


def build():
    """Labelled exam: group 1-5 (passage ALPHA), 6-10 (passage BETA), 11-20 ungrouped.
    Shapes: 'Both A and B' option (7), stem naming a letter (8),
    all/none-of-the-above (9, 10), dependent stem 'cau 1' (12)."""
    body = t.HEAD % ("English", "Multiple Choice") + "## Instructions\n\nChoose.\n\n"
    shape = {}  # the parser accepts exactly A-D, so other option counts are tested on permuted() directly
    for i in range(1, N + 1):
        keys = shape.get(i, "ABCD")
        texts = dict((k, opt(i, k)) for k in keys)
        stem = "Stem %d." % i
        if i == 7:
            texts["D"] = "Both A and B"
        if i == 8:
            stem = "Stem 8: phuong an A is wrong, pick the best of the rest."
        if i == 9:
            texts["D"] = "All of the above"
        if i == 10:
            texts["D"] = "None of the above"
        if i == 12:
            stem = "Stem 12 uses the result of cau 1."
        grp = ("### Instruction for this group\n\nQuestions 1-5.\n\n### Passage\n\nPASSAGE-ALPHA\n\n" if i <= 5 else
               "### Instruction for this group\n\nQuestions 6-10.\n\n### Passage\n\nPASSAGE-BETA\n\n" if i <= 10 else
               "### Instruction for this group\n\nSingle.\n\n")
        body += "## Question %d\n\n%s### Question text\n\n%s\n%s\n\n" % (
            i, grp, stem, "\n".join("%s. %s" % (k, v) for k, v in sorted(texts.items())))
    return body, shape


def first_replies(first):
    return [t.solve(*[t.a(i, first[i], expr=None) for i in range(1, N + 1)]),
            t.qa(*[(i, "agree") for i in range(1, N + 1)])]


def second_reply(prompt, policy, first, cost=0.0, shape=None):
    """policy 'text': answer the letter whose text is the original text of the first answer;
    'letter': answer the first answer's letter; 'plain': answer A."""
    out = []
    for n in re.findall(r"## Question (\d+)", prompt):
        i = int(n)
        if policy == "text":
            m = re.search(r"\n([A-E])\. %s\b" % re.escape(opt(i, first[i])), prompt)
            ans = m.group(1) if m else "A"
        else:
            ans = first[i]
        out.append(t.a(n, ans, expr=None))
    return t.exam_llm.Call(True, t.solve(*out), cost, "", "", 0.0)


class Base(t.Base):
    def run_policy(self, policy, **kw):
        exam, shape = build()
        llm = t.Script(*first_replies(FIRST))
        orig = llm.__call__

        def both(prompt):
            if "Solve independently" in prompt:
                llm.items.append(second_reply(prompt, policy, FIRST, kw.get("second_cost", 0.0)))
            return orig(prompt)
        self.go(exam, both, second_sample=True, confidence=True,
                **dict((k, v) for k, v in kw.items() if k != "second_cost"))
        self.llm = llm
        return dict((int(q["id"]), q) for q in self.result_file()["questions"])

    @staticmethod
    def codes(q):
        return [f["code"] for f in q["qa_findings"]]


NOT_PERMUTED = (7, 8, 9, 10, 12)  # letter ref in option/stem, all/none of the above, dependent stem


class Mapping(Base):
    def test_text_policy_every_sampled_id_agrees_in_original_letters(self):
        qs = self.run_policy("text")
        for i, q in qs.items():
            if i in NOT_PERMUTED:
                self.assertIn("second_skipped", self.codes(q), i)
                continue
            self.assertIn("second_agrees", self.codes(q), i)
            self.assertEqual(q["second_answer"], FIRST[i], i)
            self.assertNotIn("second_differs", self.codes(q), i)

    def test_letter_policy_every_sampled_id_differs(self):
        qs = self.run_policy("letter")
        for i, q in qs.items():
            if i in NOT_PERMUTED:
                continue
            self.assertIn("second_differs", self.codes(q), i)
            self.assertEqual(q["confidence"], "likely_wrong", i)
            self.assertNotEqual(q["second_answer"], FIRST[i], i)

    def test_reply_never_touches_first_answer_or_status(self):
        for pol in ("text", "letter"):
            qs = self.run_policy(pol)
            for i, q in qs.items():
                self.assertEqual((q["answer"], q["verification_status"], q["status_reason"]),
                                 (FIRST[i], "UNCERTAIN", "no_independent_check"), (pol, i))

    def test_batches_of_15_one_call_each_total_calls(self):
        self.run_policy("text")
        self.assertEqual(len(self.llm.prompts), 2 + 2)  # solve, review, 2 second batches (30 sampled ids)
        sp = [p for p in self.llm.prompts if "Solve independently" in p]
        self.assertEqual(len(sp), 2)
        self.assertEqual(len(re.findall(r"## Question \d+", sp[0])), 15)

    def test_passage_groups_kept_intact_and_questions_reordered(self):
        self.run_policy("text")
        sp = [p for p in self.llm.prompts if "Solve independently" in p][0]
        order = [int(n) for n in re.findall(r"## Question (\d+)", sp)]
        self.assertNotEqual(order, sorted(order))  # reordered (groups reversed)
        self.assertEqual(sp.count("PASSAGE-ALPHA"), 1)  # shown once, before its members
        self.assertEqual(sp.count("PASSAGE-BETA"), 1)
        for grp, ids in (("PASSAGE-BETA", (6,)), ("PASSAGE-ALPHA", (1, 2, 3, 4, 5))):
            pos = sp.index(grp)
            for i in ids:
                self.assertGreater(sp.index("## Question %d\n" % i), pos, (grp, i))
            idx = [order.index(i) for i in ids]
            self.assertEqual(max(idx) - min(idx), len(ids) - 1, grp)  # contiguous block

    def test_option_counts_2_to_5_permute_and_back_is_a_bijection(self):
        qs = []
        for i, keys in ((1, "AB"), (2, "ABC"), (3, "ABCD"), (4, "ABCDE"), (5, "ABCDE"), (6, "ABC")):
            qs.append({"id": i, "options": dict((k, "x%d%s" % (i, k)) for k in keys), "stem": "s"})
        e2, back = solver.permuted({"questions": qs}, [q["id"] for q in qs])
        self.assertEqual(sorted(back), [1, 2, 3, 4, 5, 6])
        orig = dict((q["id"], q["options"]) for q in qs)
        for q2 in e2["questions"]:
            i, b = q2["id"], back[q2["id"]]
            self.assertEqual(sorted(b), sorted(orig[i]))
            self.assertEqual(sorted(b.values()), sorted(orig[i]))
            self.assertTrue(all(b[k] != k for k in b), i)  # every position moves
            for k in b:  # new letter k holds the text of original letter b[k]
                self.assertEqual(q2["options"][k], orig[i][b[k]])
        self.assertEqual([q["id"] for q in e2["questions"]], [6, 5, 4, 3, 2, 1])

    def test_one_option_or_letter_reference_in_option_left_out(self):
        qs = [{"id": 1, "options": {"A": "x"}, "stem": "s"},
              {"id": 2, "options": {"A": "Both A and B", "B": "y"}, "stem": "s"}]
        e2, back = solver.permuted({"questions": qs}, [1, 2])
        self.assertEqual((back, e2["questions"]), ({}, []))

    def test_stem_naming_a_letter_is_not_permuted(self):
        """Defect probe: stem 'phuong an A' would point at a different text after rotation."""
        qs = self.run_policy("text")
        self.assertIn("second_skipped", self.codes(qs[8]))

    def test_all_or_none_of_the_above_not_permuted(self):
        """Defect probe: 'All of the above' loses its meaning when rotated away from the last slot."""
        qs = self.run_policy("text")
        for i in (9, 10):
            self.assertIn("second_skipped", self.codes(qs[i]), i)


    def test_dependent_stem_prompt_has_no_sibling_answer_context(self):
        """Info (QA D3): exam2 holds only sampled ids, so the 'Sibling answers' block cannot appear; the
        second solve of a stem that refers to another question sees no sibling context. Must not crash."""
        self.run_policy("text")
        qs = self.run_policy("text")
        qs = self.run_policy("text")
        sp = [p for p in self.llm.prompts if "Solve independently" in p][0]
        self.assertNotIn("## Question 12", sp)  # D6: dependent stem left out
        self.assertIn("permutation_unsafe", [f["message"] for f in qs[12]["qa_findings"]])


class Caps(Base):
    def test_call_cap_is_base_plus_10_only_with_flag(self):
        c = t.cfg()
        self.assertEqual(eng.call_cap(dict(c, second_sample=True)) - eng.call_cap(c), 10)
        self.assertEqual(eng.call_cap(c), 1 + 2 * c["max_attempts"])

    def test_call_cap_hit_mid_sample_skips_rest(self):
        import tempfile
        from exam_engine.pipeline import parser
        exam, _ = build()
        path = os.path.join(tempfile.mkdtemp(), "e.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(exam)
        ex = parser.parse_exam(path)
        recs = dict((i, {"ans": t.a(i, FIRST[i]), "findings": [], "status": "UNCERTAIN",
                         "reason": "no_independent_check"}) for i in range(1, N + 1))
        llm = t.Script(second_reply("## Question " + "\n## Question ".join(str(i) for i in range(1, 7)),
                                    "letter", FIRST).text)
        c = t.cfg(second_sample=True)
        rn = eng.Runner(c, llm, [])
        rn.calls = eng.call_cap(c) - 1  # one call left: batch 1 runs, batch 2 hits the call cap
        ids = [i for i in range(1, N + 1) if i not in NOT_PERMUTED]
        eng.second_sample(ex, recs, rn, ids)
        codes = lambda i: [f["code"] for f in recs[i]["findings"]]  # noqa: E731
        self.assertEqual(rn.calls, eng.call_cap(c))
        self.assertTrue(any("second_skipped" in codes(i) for i in ids[15:]))
        self.assertFalse(any("second_differs" in codes(i) for i in ids[15:]))
        self.assertEqual(recs[1]["ans"]["answer"], FIRST[1])

    def test_cost_stop_mid_way_gives_skipped_never_differs(self):
        qs = self.run_policy("letter", second_cost=5.0, max_cost_usd=1.0)
        first_batch = [i for i in sorted(qs) if i not in NOT_PERMUTED][:15]  # batches are ascending ids
        for i in first_batch:
            self.assertIn("second_differs", self.codes(qs[i]), i)
        rest = [i for i in qs if i not in first_batch and i not in NOT_PERMUTED]
        self.assertTrue(rest)
        for i in rest:
            self.assertIn("second_skipped", self.codes(qs[i]), i)
            self.assertNotIn("second_differs", self.codes(qs[i]), i)

    def test_default_off_no_second_call_and_no_keys(self):
        exam, _ = build()
        llm = t.Script(*first_replies(FIRST))
        self.go(exam, llm)
        self.assertEqual(len(llm.prompts), 2)
        text = json.dumps(self.result_file())
        self.assertNotIn("second", text)
        self.assertNotIn("confidence", text)


if __name__ == "__main__":
    unittest.main()
