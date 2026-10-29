# Phase 19: part-aware refine and Part II/III format checks (REQ-0026, TASK-019; EPIC-006)

## Goal
Deterministic, model-free fixes found on the real run: the model merges the part heading ("PHẦN II: ...") into the first question's text, and the verifier has no format check for true/false sets (Part II) or short numeric answers (Part III). Solver prompt and output schema unchanged.

## refine (`ingest/refine.py`)
- `split_part(text)`: a first line matching `^\s*PHẦN\s+(I|II|III|IV|V)\b` (case-insensitive) is removed from the text; returns (part, rest). Heading-only items (empty rest) are dropped.
- `part` carried forward in page and question order (persists across pages); stored as `part` on each refined question (None before the first heading). Similarity uses the stripped text.
- `_gaps` is computed per part (a restart at 1 on a new part is not a gap).

## verifier (`pipeline/verifier.py::_format`)
- Part II shape (no options, lines `a)`..`d)` all present in the question text, subject math/physics): answer must hold exactly 4 verdict tokens (Đúng/Sai/Đ/S/True/False/T/F as words), letters optional.
- Part III shape (no options, no a-d lines, subject math/physics, not Open): the answer must contain a number.
- Other types unchanged; failure = `fail` format check (existing retry path). Tolerant on purpose: only clearly wrong shapes fail.

## Tests ($0)
Heading stripped and part set; heading-only item dropped; part carried across pages; restart not a gap; Part II 4 verdicts pass / 3 fail; Part III number pass / text fail; MCQ and English unchanged; mutation per rule.

## Open questions
None.
