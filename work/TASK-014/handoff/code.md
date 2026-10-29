PROGRESS: COMPLETE
SKILLS: coding, token-efficiency
Files: src/exam_engine/ingest/parts.py (new), ingest/inspect.py (new), ingest/schema.py (parts, codes invalid_pages/answer_key_present), ingest/api.py (parts for non-md, config pages, to_exam_text(doc, config) guard), cli.py (ingest --pages/--allow-key-pages, ingest-inspect), tests/unit/test_ingest_inspect.py (12 tests), docs/guide/ingest-setup.md (section).
Tests: full suite 313 OK. New file 12 (5 need fitz, ran).
Mutation: guard disabled in api.to_exam_text -> 3 failures; restored -> OK.
Notes: markdown docs get no `parts`; toolkit-reference.md has no ingest rows, untouched. A key followed by numbered answers breaks segmentation (no_questions) unless --pages used; expected.
## Defects
none
