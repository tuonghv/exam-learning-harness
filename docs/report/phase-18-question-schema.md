# Report: TASK-018 question schema: LaTeX, source trace, verification (REQ-0022, EPIC-006)

**Verdict: built and verified; schema only, nothing fills the new fields yet.**

## What exists
- `ingest/schema.py`: optional `latex{text,origin ai|recognizer}`, `source{page,bbox,crop,route}`, `figures[]`, `verification{status,checks,reasons}` on `questions[]`; `validate_questions` requires a source trace (page in document, crop and figure assets present, document sha256) whenever latex, figures or verification is present.
- Old documents stay valid; `to_exam_text` and `solve` unchanged (test: identical output with and without the fields).

## Verification
432 unit tests OK (7 new); mutation (trace check disabled) is caught. Real refined document from TASK-017 still validates; an untraced verification record is rejected; a traced one passes. Evidence: `work/TASK-018/evidence/`.

## Limits
- Nothing writes `latex`, `source` or `verification` yet: REQ-0023 (independent verification) fills them.
- `bbox` and `crop` come from the producer; the validator checks existence, not geometry.

## Next
REQ-0023.

User instructions honoured: auto your task, comment less, no engine change.
