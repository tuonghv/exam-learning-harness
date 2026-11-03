"""TASK-062 62.G: freeze the language/verdict/refcheck/genexam behaviour of the default config ($0).

Every pattern below is the byte string of today's code; the default config/lang.json must reproduce it.
The two part-heading patterns carry the D2 fix (PART accepted beside PHẦN), the only intended change.
"""
import hashlib
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

from exam_engine.core import refcheck  # noqa: E402
from exam_engine.ingest import refine, segment  # noqa: E402
from exam_engine.ingest.adapters import pdf  # noqa: E402
from exam_engine.pipeline import cross, genexam, verifier  # noqa: E402

PATTERNS = [
    (segment._Q, r'^\s*(?:(?:Câu|Cau|Question)\s*(\d+)\s*[.:)]?|(\d+)(?!\.\d)\s*[.)])\s*(.*)$'),
    (segment.GROUP_RE, r'(?:Questions?|[Cc]âu(?:\s*hỏi)?)\s*(?:từ\s*)?(\d+)(?:\s*(?:-|–|đến|to)\s*(?:[Cc]âu\s*)?(\d+)|\s+and\s+(\d+)|((?:\s*,\s*\d+)+))'),
    (segment._INTRO, r'^\s*(?:(?:Dựa vào|Đọc|Hãy đọc|Based on|Read|Use|Study)\b[^\n]{0,120}?)?(?:Questions?|[Cc]âu(?:\s*hỏi)?)\s*(?:từ\s*)?\d+\s*(?:-|–|đến|to)\s*\d+'),
    (segment._READ, r'^\s*(?:Read|Study|Use)\s+the\s+(?:following\s+)?(?:passage|text|article)\b'),
    (segment._PART, r'^\s*(?:PH[ẦA]N|PART)\s+(IV|V|I{1,3})\b'),  # D2: was PH[ẦA]N only
    (segment._PART_ANY, r'^\s*(?:PH[ẦA]N|PART)\s+(?:IV|V|I{1,3}|\d{1,2})\b'),
    (refine.PART_RE, r'^\s*(?:PH[ẦA]N|PART)\s+(IV|V|I{1,3})\b[^\n]*(?:\n|$)'),  # D2
    (pdf._PAGE_NO, r'^\s*(?:(?:Trang|Page)\s*\d+(?:\s*(?:/|of)\s*\d+)?|-\s*\d+\s*-)\s*$'),
    (verifier._VERDICT, r'(?<!\w)(đúng|sai|true|false|đ|s|t|f)(?!\w)'),
    (refcheck._PAR_VI, r'\bđoạn(?:\s+(?:văn|thơ|trích))?\s*(?:(\()(\d{1,2})\)|(?<=\s)(\d{1,2})\b)'),
    (refcheck._PAR_EN, r'\bparagraph\s*(?:(\()(\d{1,2})\)?|(\d{1,2})\b)'),
    (refcheck._FIG, r'\b(?:hình|bảng|biểu đồ|đồ thị|sơ đồ)(?:\s+vẽ)?\s+(?:bên|dưới|trên|sau|\d+)\b|\bbảng số liệu\b|\b(?:figure|table|chart|graph|diagram)\s+(?:above|below|\d+)\b|\b(?:following|above|below)\s+(?:figure|table|chart|graph|diagram)\b'),
    (refcheck._NEEDS_TEXT, r'(?i)\bread\s+(?:the\s+)?(?:following\s+)?(?:passage|text)|đọc\s+(?:đoạn|bài|văn bản)|bảng số liệu sau|use the following data|dữ kiện sau'),
]
TF = {"đúng": "T", "true": "T", "t": "T", "đ": "T", "sai": "F", "false": "F", "f": "F", "s": "F"}
OBJ = {"question": "Q?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "final_answer": "B",
       "solution": "s", "skill": "sk", "check": "c1", "passage": "p"}
SHAS = {"hs": ("e6b21d0bfbf50aed", "00784f8f203f0d2d"), "dgnl": ("5c2f99a2fdd5d7f9", "00784f8f203f0d2d"),
        "dgnl-en": ("efb7bf4be2740028", "b7c850b52909e826"), "dgnl-vi": ("fa3f1e8b7b222bd5", "935cdfd240e6652c")}
KEY_SHA = "66d38e76471e8666"
EXAM = """Intro line
PHẦN I
Câu 1. First
A. a
B. b
Questions 3-4 read the passage
Question 2: Second
3) third
Câu 4: x
""".split("\n")


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


class Golden(unittest.TestCase):
    def test_patterns_frozen(self):
        for rx, pat in PATTERNS:
            self.assertEqual(rx.pattern, pat)

    def test_tf_dict(self):
        self.assertEqual(cross._TF, TF)

    def test_genexam_hashes(self):
        for p, (prompt, inp) in SHAS.items():
            sub = genexam.PROFILE_SUBJECT[p]
            self.assertEqual(sha(genexam.build_prompt(sub, 7, 1, "hard", p)), prompt, p)
            self.assertEqual(sha(genexam.input_md(sub, OBJ)), inp, p)
            self.assertEqual(sha(genexam.key_md(OBJ)), KEY_SHA, p)

    def test_segment_and_part(self):
        intro, qs, ok = segment.segment(EXAM)
        self.assertEqual((intro, [q["n"] for q in qs], ok), (["Intro line", "PHẦN I"], [1, 2, 3, 4], True))
        self.assertEqual(refine.split_part("PHẦN II. x\nbody"), ("II", "body"))
        self.assertEqual(refine.split_part("PART II\nbody"), ("II", "body"))  # D2
        self.assertEqual(refine.split_part("Part 2\nbody"), (None, "Part 2\nbody"))
        self.assertEqual(segment.group_span(segment.GROUP_RE.search("câu 103 đến 105")), (103, 105))

    def test_verdicts(self):
        for a in ("a) Đ b) S c) T d) F", "a) true b) false c) đúng d) sai"):
            self.assertEqual(cross.canon(a), "V:TFTF")
        self.assertEqual(len(verifier._VERDICT.findall("a) Đ b) S c) T d) F")), 4)

    def test_refcheck(self):
        r = refcheck.referenced_parts
        self.assertEqual(r("Đọc đoạn (3) sau"), ["paragraph (3)"])
        self.assertEqual(r("paragraph 2 here\n(2) m"), [])
        self.assertEqual(r("Cho hình bên"), ["figure/table"])
        self.assertTrue(refcheck._NEEDS_TEXT.search("Read the following passage"))


if __name__ == "__main__":
    unittest.main()
