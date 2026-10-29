"""Phase 18 (REQ-0022): question schema extras (latex, source trace, verification); $0, no model."""
import copy
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from exam_engine.ingest import api, schema  # noqa: E402


def base():
    return {"schema_version": "1",
            "source": {"path": "a.pdf", "name": "a.pdf", "format": "pdf", "sha256": "ab" * 32,
                       "size": 1},
            "status": "native_text", "extraction": {"method": "native", "tool": "t"},
            "meta": {k: "x" for k in api.REQUIRED},
            "pages": [{"n": 1, "blocks": []}],
            "assets": [{"id": "a1", "path": "assets/a1.png", "mime": "image/png", "sha256": "cd"}],
            "questions": [{"n": 1, "text": "Cho x^2 = 4", "options": [{"key": "A", "text": "2"}]}],
            "warnings": []}


def traced():
    d = base()
    d["questions"][0].update({
        "latex": {"text": "Cho $x^2 = 4$", "origin": "ai"},
        "source": {"page": 1, "bbox": [0, 0, 10, 10], "crop": "a1",
                   "route": {"text": "ocr", "math": "ai"}},
        "figures": [{"asset": "a1", "page": 1, "bbox": None}],
        "verification": {"status": "unverified", "checks": [], "reasons": []}})
    return d


class QuestionSchema(unittest.TestCase):
    def test_old_document_valid(self):
        self.assertEqual(schema.validate_document(base()), [])

    def test_full_item_valid(self):
        self.assertEqual(schema.validate_document(traced()), [])

    def test_bad_enum_and_origin(self):
        d = traced()
        d["questions"][0]["verification"]["status"] = "maybe"
        d["questions"][0]["latex"]["origin"] = "code"
        errs = schema.validate_document(d)
        self.assertGreaterEqual(len(errs), 2, errs)

    def test_missing_source_is_error(self):
        for key, val in (("verification", {"status": "verified"}),
                         ("latex", {"text": "$x$", "origin": "ai"}),
                         ("figures", [{"asset": "a1"}])):
            d = base()
            d["questions"][0][key] = val
            errs = schema.validate_document(d)
            self.assertTrue(any("source trace required" in e for e in errs), (key, errs))

    def test_unknown_page_crop_figure_sha(self):
        d = traced()
        d["questions"][0]["source"].update({"page": 9, "crop": "zz"})
        d["questions"][0]["figures"][0]["asset"] = "yy"
        d["source"]["sha256"] = ""
        text = " | ".join(schema.validate_document(d))
        for part in ("source page 9", "crop asset zz", "figure asset yy", "sha256 missing"):
            self.assertIn(part, text)

    def test_exam_text_unchanged(self):
        self.assertEqual(api.to_exam_text(traced()), api.to_exam_text(base()))

    def test_mutation_trace_check_bites(self):
        d = base()
        d["questions"][0]["verification"] = {"status": "verified"}
        with mock.patch.object(schema, "validate_questions", return_value=[]):
            self.assertEqual(schema.validate_document(d), [])
        self.assertNotEqual(schema.validate_document(d), [])


if __name__ == "__main__":
    unittest.main()
