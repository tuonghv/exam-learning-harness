"""Tests 3 (and validate_exam) of docs/design/phase-4-engine-core.md; REQ-0010 AC2. No model call."""
import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import exam_parse as ep  # noqa: E402
import exam_schema as sch  # noqa: E402


def good_q(**kw):
    q = {"id": "1", "type": "multiple_choice", "answer": "A", "answer_status": "answered",
         "solution": ["s"], "explanation": "e", "checks": [], "expr": None,
         "evidence": ["x"], "uncertainty": {"level": "low", "reason": "r"},
         "reasoning_status": "not_independently_verified", "issues": []}
    q.update(kw)
    return q


def good_out(*qs):
    return {"schema_version": "1.0", "questions": list(qs) or [good_q()], "input_issues": []}


class SchemaTests(unittest.TestCase):
    def test_3_valid_reply_has_no_errors(self):
        self.assertEqual(sch.validate(good_out(), sch.SOLVE_OUT), [])

    def test_3_missing_question_field_and_missing_list(self):
        q = good_q()
        del q["answer"]
        errs = sch.validate(good_out(q), sch.SOLVE_OUT)
        self.assertTrue(any("missing answer" in e for e in errs), errs)
        errs = sch.validate({"schema_version": "1.0"}, sch.SOLVE_OUT)
        self.assertTrue(any("missing questions" in e for e in errs), errs)

    def test_3_wrong_types(self):
        self.assertTrue(sch.validate(good_out(good_q(id=1)), sch.SOLVE_OUT))
        self.assertTrue(sch.validate(good_out(good_q(solution="text")), sch.SOLVE_OUT))
        self.assertTrue(sch.validate([], sch.SOLVE_OUT))
        self.assertTrue(sch.validate(good_out(good_q(answer_status="maybe")), sch.SOLVE_OUT))
        self.assertTrue(sch.validate(
            good_out(good_q(uncertainty={"level": "none", "reason": "r"})), sch.SOLVE_OUT))

    def test_3_reasoning_status_verified_is_rejected(self):
        errs = sch.validate(good_out(good_q(reasoning_status="verified")), sch.SOLVE_OUT)
        self.assertTrue(errs and "reasoning_status" in errs[0], errs)

    def test_3_extra_keys_tolerated_but_nullable_answer_ok(self):
        self.assertEqual(sch.validate(good_out(good_q(extra_id=7, answer=None,
                                                      answer_status="unanswerable")),
                                      sch.SOLVE_OUT), [])

    def test_3_qa_schema(self):
        ok = {"reviews": [{"id": "1", "verdict": "agree", "findings": []}]}
        self.assertEqual(sch.validate(ok, sch.QA_OUT), [])
        bad = copy.deepcopy(ok)
        bad["reviews"][0]["verdict"] = "great"
        self.assertTrue(sch.validate(bad, sch.QA_OUT))
        self.assertTrue(sch.validate({"reviews": [{"id": "1", "verdict": "agree"}]}, sch.QA_OUT))

    def test_3_validator_subset_rules(self):
        s = {"type": "object", "required": ["a"], "additionalProperties": False,
             "properties": {"a": {"type": "number", "minimum": 1}}}
        self.assertEqual(sch.validate({"a": 2}, s), [])
        self.assertTrue(sch.validate({"a": 0}, s))
        self.assertTrue(sch.validate({"a": 2, "b": 1}, s))
        self.assertTrue(sch.validate({}, s))


class ValidateExamTests(unittest.TestCase):
    def exam(self, **over):
        e = {"fields": {"Subject": "English", "Level": "Grade 12", "Exam type": "X",
                        "Task": "Multiple Choice", "Mode": "Solve"},
             "instructions": "i", "passage": "",
             "questions": [{"id": 1, "text": "t", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}}]}
        e.update(over)
        return e

    def test_valid_and_real_example(self):
        self.assertEqual(ep.validate_exam(self.exam()), [])
        root = os.path.join(HERE, "..", "..", "..")
        ex = ep.parse_exam(os.path.join(root, "examples", "english", "input-001.md"))
        self.assertEqual(ep.validate_exam(ex), [])

    def test_errors_are_listed_not_raised(self):
        e = self.exam()
        e["fields"] = {"Subject": "Chemistry", "Mode": "Teach"}
        errs = ep.validate_exam(e)
        self.assertTrue(any("missing header" in x for x in errs))
        self.assertTrue(any("unsupported Subject" in x for x in errs))
        self.assertTrue(any("unsupported Mode" in x for x in errs))
        self.assertTrue(any("no questions" in x for x in ep.validate_exam(self.exam(questions=[]))))
        q = self.exam()["questions"][0]
        self.assertTrue(any("numbering" in x for x in ep.validate_exam(
            self.exam(questions=[dict(q, id=2)]))))
        self.assertTrue(any("options must be exactly" in x for x in ep.validate_exam(
            self.exam(questions=[dict(q, options={"A": "a"})]))))
        self.assertIsInstance(ep.validate_exam({}), list)


if __name__ == "__main__":
    unittest.main()
