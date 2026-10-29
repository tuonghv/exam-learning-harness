# Phase 18: question schema with LaTeX, source trace, verification record (REQ-0022, TASK-018; EPIC-006)

## Goal
Additive, optional fields on each `questions[]` item of the canonical document; old documents stay valid, `to_exam_text` and `solve` unchanged. The original file + `source.sha256` stay the source of truth; code never invents LaTeX.

## Fields (all optional; schema_version stays "1")
- `latex`: `{"text": "<question text with $...$>", "options": {"A": "..."}, "origin": "ai|recognizer"}`. The plain `text` stays as the solver twin.
- `source`: `{"page": int, "bbox": [x0,y0,x1,y1]|null, "crop": "<asset id>"|null, "route": {"text": "native|ocr|ai", "math": "none|ai|recognizer", "figures": "extracted|none"}}`.
- `verification`: `{"status": "unverified|verified|needs_review|rejected", "checks": [{"name","result":"pass|fail|skip","detail"}], "reasons": [str]}`.
- `figures`: `[{"asset": "<asset id>", "page": int, "bbox": [..]|null}]`.

## Code (`ingest/schema.py`, new `validate_questions(doc)` called from `validate_document`)
- Types/enums checked via the existing `core.schema.validate`.
- Trace integrity (only for items that carry `latex`, `verification` or `figures`): `source` required; `source.page` is a page of the doc; `source.crop` and each figure `asset` exist in `assets`; `doc["source"]["sha256"]` present. Missing trace -> validation error.
- A `latex` with origin outside `ai|recognizer` is rejected (AC3: never code-made). A question flagged `math_possible` stays plain with `verification.status` unverified.
- No change to adapters, `to_exam_text`, `solve`.

## Tests ($0) `tests/unit/test_ingest_schema_q.py`
Old doc valid; full new item valid; bad enum; missing `source` with `verification`; unknown page; missing crop asset; latex origin "code" rejected; `to_exam_text` output identical with and without new fields; mutation: drop the trace check -> a test fails.

## Open questions
None (REQ-0022 Q1 accepted).
