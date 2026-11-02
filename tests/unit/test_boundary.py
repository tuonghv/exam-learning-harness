"""Phase 50 (REQ-0053): AI boundary hints for rule-uncertain lines. Synthetic text, mock replies,
no network, no real exam text. Plus the rule fixes D1 (arabic PHẦN / PART heading) and D2
(select_pages keeps the furniture filter and the hints)."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.ingest import boundary, parts, replycache, segment  # noqa: E402


def q(n, marker="Câu %d.", stem="Tính nhanh giá trị số %d.", tail=None):
    out = [marker % n + " " + stem % n]
    out += ["A. một", "B. hai", "C. ba", "D. bốn"]
    return out + (tail or [])


def exam(n=10):
    out = []
    for i in range(1, n + 1):
        out += q(i)
    return out


def reply(*wins):
    """wins: (window_id, [(line, label, conf)])."""
    return json.dumps({"windows": [
        {"window_id": w, "items": [{"line": ln, "label": lab, "confidence": c} for ln, lab, c in it]}
        for w, it in wins]})


class Ask:
    """Mock model: replies in order; counts calls; cost 0."""

    def __init__(self, *replies, cost=0.0):
        self.replies, self.calls, self.prompts, self.cost = list(replies), 0, [], cost

    def __call__(self, prompt):
        self.prompts.append(prompt)
        self.calls += 1
        if not self.replies:
            return claude.Call(False, "", 0.0, "other", "no reply", 0.0)
        return claude.Call(True, self.replies.pop(0), self.cost, "", "", 0.0)


def hinted(lines, ask, **kw):
    """-> (questions, warnings codes, reviewer) with the reviewer wired like an adapter."""
    rv = boundary.Reviewer(ask, **kw)
    _i, qs, _ok, warns = boundary.segment_reviewed({"boundary": rv}, lines)
    return qs, [w["code"] for w in warns], rv, warns


def line_of(lines, text):
    return [i for i, ln in enumerate(lines) if text in ln][0]


class RuleFixes(unittest.TestCase):
    def test_d1_arabic_part_and_part_en_not_glued_into_d(self):
        for head in ("PHẦN 1: TƯ DUY", "PART 1", "Phần I", "PHẦN 2"):
            qs = segment.segment(q(1) + [head] + q(2))[1]
            self.assertEqual(qs[0]["options"][3]["text"], "bốn", head)
            self.assertEqual(qs[1]["context"], head)

    def test_d1_part_re_parity_with_refine_kept(self):
        self.assertTrue(segment._PART.match("PHẦN II"))
        self.assertFalse(segment._PART.match("PHẦN 1"))

    def test_d2_select_pages_applies_furniture_filter_for_pdf(self):
        pages = []
        for n in (1, 2, 3):
            lines = ["Đề thi mẫu"] + q(n) + ["Trang %d" % n]
            pages.append({"n": n, "blocks": [{"type": "paragraph", "text": "\n".join(lines)}]})
        doc = {"source": {"format": "pdf"}, "pages": pages, "assets": [], "warnings": []}
        out = parts.select_pages(doc, "1-3")
        self.assertEqual(out["questions"][0]["options"][3]["text"], "bốn")
        self.assertEqual(out["questions"][1]["text"], "Tính nhanh giá trị số 2.")
        self.assertEqual(len(out["questions"]), 3)


class SubNumber(unittest.TestCase):
    def test_def2_sub_number_is_not_a_question(self):
        for ln, want in (("3.1. text", False), ("3.5 m/s", False), ("33.1. t", False), ("3. text", True),
                         ("3) text", True), ("Câu 3.", True), ("Câu 3.1 x", True), ("3 . text", True)):
            self.assertEqual(bool(segment._Q.match(ln)), want, ln)
        qs = segment.segment(q(1, tail=["3.1. Phần tiếp"]) + q(2))[1]
        self.assertEqual([x["n"] for x in qs], [1, 2])

    def test_def1_deep_nesting_is_a_bad_reply(self):
        self.assertEqual(claude.extract_json("[" * 5000 + "]" * 5000)[0], None)


class Plain(unittest.TestCase):
    def test_1_hints_none_is_plain_rules(self):
        lines = exam(4) + ["Bài 5: x"]
        self.assertEqual(segment.segment(lines), segment.segment(lines, None, []))
        self.assertEqual(segment.segment(lines), segment.segment(lines, {}, []))
        self.assertEqual(boundary.segment_reviewed({}, lines)[3], [])

    def test_2_normal_exam_zero_suspects_and_windows(self):
        self.assertEqual(boundary.suspects(exam(10)), [])
        rv = boundary.Reviewer(None, dry_run=True)
        rv(exam(10))
        self.assertEqual((rv.stats["windows"], rv.stats["est_calls"]), (0, 0))


class QS1(unittest.TestCase):
    def three(self, marker):
        return q(1) + q(2) + q(3, marker) + q(4)

    def test_3_unknown_marker_split_with_ai_origin(self):
        for marker in ("Bài %d:", "Item %d)", "Q%d."):
            lines = self.three(marker)
            at = line_of(lines, "số 3")
            sus = boundary.suspects(lines)
            self.assertEqual([(s["line"], s["kind"]) for s in sus][:1], [(at, "QS1")], marker)
            ask = Ask(reply(("w1", [(at, "question_start", 0.9)])))
            qs, codes, _rv, warns = hinted(lines, ask)
            self.assertEqual([x["n"] for x in qs], [1, 2, 3, 4], marker)
            self.assertIn("boundary_ai_applied", codes)
            self.assertTrue(all(w["origin"] == "ai" for w in warns if w["code"] == "boundary_ai_applied"))
            self.assertEqual(ask.calls, 1)

    def test_4_token_promotion_two_exemplars_one_call(self):
        lines = q(1) + q(2)
        for i in range(3, 9):
            lines += q(i, "Bài %d:")
        ats = [line_of(lines, "số %d" % i) for i in range(3, 9)]
        wins, _skipped = boundary.windows(lines, boundary.suspects(lines))
        self.assertTrue(len(wins) >= 1)
        qs, codes, rv, _w = hinted(lines, Ask(reply(("w1", [(ats[0], "question_start", 0.9),
                                                            (ats[1], "question_start", 0.9)]))))
        self.assertEqual([x["n"] for x in qs], list(range(1, 9)))
        self.assertIn("boundary_ai_marker", codes)
        self.assertEqual(rv.stats["calls"], 1)

    def test_5_wrong_number_no_suspect_forced_hint_rejected(self):
        lines = q(1) + q(2) + q(7, "Bài %d:")
        self.assertEqual(boundary.suspects(lines), [])
        at = line_of(lines, "số 7")
        rep = []
        _i, qs, _ok = segment.segment(lines, {at: ("question_start", 0.9)}, rep)
        self.assertEqual([x["n"] for x in qs], [1, 2])
        self.assertEqual([r["code"] for r in rep], ["boundary_ai_rejected"])


class Others(unittest.TestCase):
    def test_6_qs2_unmarked_stem_gap_closing_only(self):
        lines = q(1) + ["Cho hình vuông cạnh 2."] + ["A. một", "B. hai", "C. ba", "D. bốn"] + q(3)
        at = line_of(lines, "hình vuông")
        sus = [s for s in boundary.suspects(lines) if s["kind"] != "NB"]  # Câu 3 after 1 is a gap
        self.assertEqual([(s["line"], s["kind"]) for s in sus], [(at, "QS2")])
        qs = hinted(lines, Ask(reply(("w1", [(at, "question_start", 0.9)]))))[0]
        self.assertEqual([x["n"] for x in qs], [1, 2, 3])
        bad = q(1) + ["Cho hình vuông cạnh 2."] + ["A. một", "B. hai", "C. ba", "D. bốn"] + q(5)
        qs, codes, _rv, _w = hinted(bad, Ask(reply(("w1", [(at, "question_start", 0.9)]))))
        self.assertEqual([x["n"] for x in qs], [1, 5])
        self.assertIn("boundary_ai_rejected", codes)

    def test_7_heading_section_and_subject(self):
        lines = q(1) + ["PHẦN 1: TƯ DUY LOGIC"] + ["Câu 2. Tính"] + ["A. một", "B. hai", "C. ba", "D. bốn"]
        # the arabic heading is a rule now (D1); an unknown title is the suspect
        lines = q(1) + ["Tư Duy Logic"] + q(2)
        at = line_of(lines, "Tư Duy")
        self.assertEqual([(s["line"], s["kind"]) for s in boundary.suspects(lines)], [(at, "SH")])
        qs = hinted(lines, Ask(reply(("w1", [(at, "section_start", 0.9)]))))[0]
        self.assertEqual(qs[0]["options"][3]["text"], "bốn")
        self.assertEqual(qs[1]["context"], "Tư Duy Logic")
        qs, codes, _rv, _w = hinted(lines, Ask(reply(("w1", [(at, "subject_start", 0.9)]))))
        self.assertIn("boundary_ai_subject", codes)
        self.assertNotIn("subject", qs[0])

    def test_8_passage_after_d(self):
        lines = q(1, tail=["Nhân vật chính của câu chuyện sống ở một làng quê nghèo ven biển."]) + q(2)
        at = line_of(lines, "Nhân vật")
        self.assertEqual([s["kind"] for s in boundary.suspects(lines)], ["QE"])
        qs = hinted(lines, Ask(reply(("w1", [(at, "passage", 0.9)]))))[0]
        self.assertEqual(qs[1]["context"].startswith("Nhân vật"), True)
        qs = hinted(lines, Ask(reply(("w1", [(at, "option_continuation", 0.9)]))))[0]
        self.assertTrue(qs[0]["options"][3]["text"].endswith("ven biển."))

    def test_7b_weak_number_heading_after_d_not_glued(self):
        lines = q(1) + ["3) SUY LUẬN"] + q(2) + q(3) + q(4)
        sus = boundary.suspects(lines)
        self.assertEqual([s["kind"] for s in sus], ["NB"])
        qs = hinted(lines, Ask(reply(("w1", [(sus[0]["line"], "section_start", 0.9)]))))[0]
        self.assertEqual([x["n"] for x in qs], [1, 2, 3, 4])
        self.assertEqual(qs[0]["options"][3]["text"], "bốn")
        self.assertEqual(qs[1]["context"], "3) SUY LUẬN")

    def test_7c_range_or_decimal_is_not_a_marker(self):
        lines = q(1) + q(2) + ["Dành 03-05 phút để kiểm tra"] + q(3)
        self.assertEqual(boundary.suspects(lines), [])

    def test_9_invalid_replies_leave_rules(self):
        lines = q(1) + q(2) + q(3, "Bài %d:")
        at = line_of(lines, "số 3")
        plain = segment.segment(lines)[1]
        many = reply(("w1", [(at + i, "other", 0.9) for i in range(41)]))
        for bad, why in (("not json", "json"),
                         (reply(("w1", [(at, "dance", 0.9)])), "label"),
                         (reply(("w1", [(at + 99, "question_start", 0.9)])), "index"),
                         (reply(("w1", [(at, "question_start", 1.5)])), "confidence"),
                         (reply(("w1", [(at, "question_start", 0.9), (at, "other", 0.9)])), "duplicate"),
                         (many, "too_many")):
            qs, _c, rv, warns = hinted(lines, Ask(bad))
            self.assertEqual(qs, plain, why)
            self.assertEqual([w["reason"] for w in warns if w["code"] == "boundary_ai_invalid"], [why])

    def test_10_low_confidence_ignored(self):
        lines = q(1) + q(2) + q(3, "Bài %d:")
        at = line_of(lines, "số 3")
        qs, _c, rv, _w = hinted(lines, Ask(reply(("w1", [(at, "question_start", 0.4)]))))
        self.assertEqual([x["n"] for x in qs], [1, 2])
        self.assertEqual(rv.stats["low_confidence"], 1)

    def test_11_rule_wins(self):
        lines = exam(3)
        at = line_of(lines, "Câu 3")
        rep = []
        qs = segment.segment(lines, {at: ("other", 0.99)}, rep)[1]
        self.assertEqual([x["n"] for x in qs], [1, 2, 3])
        self.assertEqual([r["code"] for r in rep], ["boundary_ai_overruled"])
        self.assertEqual(boundary.report_warnings(rep)[0]["code"], "boundary_ai_overruled")

    def test_12_budget_cap_zero(self):
        lines = q(1) + q(2) + q(3, "Bài %d:") + q(4) + q(5)
        for _ in range(60):
            lines += q(6, "Bài %d:")  # many windows -> more than one batch
        ask = Ask()
        rv = boundary.Reviewer(ask, max_cost=0.0)
        _i, _q, _ok, warns = boundary.segment_reviewed({"boundary": rv}, lines)
        self.assertEqual(ask.calls, 0)
        self.assertIn("boundary_ai_budget", [w["code"] for w in warns])

    def test_13_cache_second_run_zero_calls_prompt_change_misses(self):
        lines = q(1) + q(2) + q(3, "Bài %d:") + q(4)
        at = line_of(lines, "số 3")
        d = tempfile.mkdtemp(prefix="bc_")
        self.addCleanup(shutil.rmtree, d, True)
        a1 = Ask(reply(("w1", [(at, "question_start", 0.9)])))
        hinted(lines, a1, cache=replycache.ReplyCache(d))
        a2 = Ask()
        qs = hinted(lines, a2, cache=replycache.ReplyCache(d))[0]
        self.assertEqual((a1.calls, a2.calls), (1, 0))
        self.assertEqual([x["n"] for x in qs], [1, 2, 3, 4])
        orig = boundary.template
        boundary.template = lambda: orig() + "\nextra rule\n"
        self.addCleanup(setattr, boundary, "template", orig)
        a3 = Ask(reply(("w1", [(at, "question_start", 0.9)])))
        hinted(lines, a3, cache=replycache.ReplyCache(d))
        self.assertEqual(a3.calls, 1)

    def test_14_answer_key_never_sent(self):
        lines = q(1) + q(2) + q(3, "Bài %d:") + ["Đáp án", "1. A  2. B  SECRET-KEY-LINE"]
        ask = Ask(reply(("w1", [(line_of(lines, "số 3"), "question_start", 0.9)])))
        hinted(lines, ask)
        self.assertTrue(ask.prompts)
        self.assertTrue(all("SECRET-KEY-LINE" not in p and "Đáp án" not in p for p in ask.prompts))
        tail = lines + ["Bài 5: x"]  # a suspect after the key line is never reported
        self.assertEqual([s["line"] for s in boundary.suspects(tail)],
                         [s["line"] for s in boundary.suspects(lines)])

    def test_15_cli_needs_a_mode_and_pages_keep_hints(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(["ingest", "x.docx", "--boundary-ai", "haiku"]), 2)
            self.assertEqual(cli.main(["ingest", "x.docx", "--dry-run"]), 2)
        self.assertIn("never defaults to real", err.getvalue())
        lines = q(1) + q(2) + q(3, "Bài %d:") + q(4)
        at = line_of(lines, "số 3")
        doc = {"source": {"format": "docx"}, "assets": [], "warnings": [],
               "pages": [{"n": 1, "blocks": [{"type": "paragraph", "text": "\n".join(lines)}]}]}
        rv = boundary.Reviewer(Ask(reply(("w1", [(at, "question_start", 0.9)]))))
        out = parts.select_pages(doc, "1", rv)
        self.assertEqual([x["n"] for x in out["questions"]], [1, 2, 3, 4])
        self.assertEqual(parts.select_pages(doc, "1")["questions"][1]["n"], 2)


if __name__ == "__main__":
    unittest.main()
