"""TASK-118 / REQ-0125: answer-key detection and page selection (118.1-118.4)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(HERE, "..", "..")), "src"))
from exam_engine.ingest import api, parts  # noqa: E402
from exam_engine.ingest.schema import IngestError  # noqa: E402


def blk(i, text, typ="paragraph"):
    return {"id": "b%d" % i, "order": i, "type": typ, "text": text, "level": None,
            "bbox": [0, 0, 1, 1], "origin": "extracted", "asset": None}


def page(n, texts, typ="paragraph"):
    return {"n": n, "blocks": [blk(10 * n + j, t, typ) for j, t in enumerate(texts)],
            "status": "native_text"}


def doc(pages, fmt="pdf"):
    return {"pages": pages, "assets": [], "warnings": [],
            "source": {"format": fmt, "name": "t." + fmt}}


class KeyGuard(unittest.TestCase):  # 118.1
    def test_key_deep_in_page(self):
        pg = page(1, ["Câu %d: x" % i for i in range(1, 8)] + ["ĐÁP ÁN", "1.A 2.B"])
        self.assertEqual(parts.find_parts(doc([pg])), [{"kind": "answer_key", "pages": [1, 1]}])

    def test_sentence_not_flip(self):
        d = doc([page(1, ["Câu 1: x"]), page(2, ["Solutions to climate change require money.", "b"])])
        self.assertEqual(parts.find_parts(d), [{"kind": "exam", "pages": [1, 2]}])

    def test_question_not_flip(self):
        d = doc([page(1, ["Câu 1: x"]), page(2, ["Lời giải thích nào sau đây đúng?", "b"])])
        self.assertEqual(parts.find_parts(d), [{"kind": "exam", "pages": [1, 2]}])

    def test_long_mixed_case_title_guard(self):  # passes on old and new
        d = doc([page(1, ["Câu 1: x"]), page(2, ["Đáp án và hướng dẫn chấm đề thi môn Toán", "b"])])
        self.assertEqual(parts.find_parts(d), [{"kind": "exam", "pages": [1, 1]},
                                               {"kind": "answer_key", "pages": [2, 2]}])


class MdRefusal(unittest.TestCase):  # 118.2
    def test_md_key_refused(self):
        d = doc([page(1, ["Đáp án đề 01"], "heading")], fmt="md")
        with self.assertRaises(IngestError) as cm:
            api.to_exam_text(d)
        self.assertEqual(cm.exception.code, "answer_key_present")
        self.assertIn("1-1", str(cm.exception))


class PagesKeyGuard(unittest.TestCase):  # 118.3
    def setUp(self):
        self.d = doc([page(1, ["Câu 1: x"]), page(2, ["ĐÁP ÁN"]), page(3, ["1.A 2.B"])], fmt="image")
        self.d["parts"] = parts.find_parts(self.d)

    def test_key_page_selected(self):
        new = parts.select_pages(self.d, "3")
        self.assertEqual(new["parts"], [{"kind": "answer_key", "pages": [3, 3]}])
        self.assertTrue(parts.has_key(new))

    def test_exam_page_selected(self):
        new = parts.select_pages(self.d, "1")
        self.assertEqual(new["parts"], [{"kind": "exam", "pages": [1, 1]}])
        self.assertFalse(parts.has_key(new))


class DocxResegment(unittest.TestCase):  # 118.4
    def test_list_lines_kept(self):
        b = [blk(0, "Câu 1: x")] + [blk(i + 1, k + ". 1", "list") for i, k in enumerate("ABCD")] \
            + [blk(9, "Câu 2: y\nA. 1\nB. 2\nC. 3\nD. 4")]
        d = doc([{"n": 1, "blocks": b}], fmt="docx")
        new = parts.select_pages(d, "1")
        self.assertEqual([len(q["options"]) for q in new["questions"]], [4, 4])


if __name__ == "__main__":
    unittest.main()
