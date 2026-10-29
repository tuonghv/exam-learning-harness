# Report: TASK-014 ingest-inspect and key-leak guard (REQ-0020, EPIC-005)

**Verdict: adopted; guard proven on the real trial PDF, heading detection is heuristic.**

## What exists
- `ingest/parts.py`: `find_parts` (exam vs answer_key by vi/en headings in the first 6 blocks of a page; key runs to the end), `select_pages`, `parse_pages`, `has_key` (computes parts if absent).
- `ingest/inspect.py`: `suspicious` (split formula, option without text, stray chars, numbering gap) and `report` (summary header, per-page blocks, warnings, "heuristics, not proof" note).
- Guard: `to_exam_text` raises `answer_key_present` unless `--pages` leaves no key page or `--allow-key-pages`.
- CLI: `ingest --pages --allow-key-pages`; `ingest-inspect <doc.json|file> [--out] [--pages]`. Local, read-only, $0. Guide: `docs/guide/ingest-setup.md`.

## Verification
324 unit tests OK; mutations (find_parts, select_pages, parse_pages, guard) each fail tests. Real PDF: parts exam p1-4, answer_key p5-12; `ingest` without `--pages` is refused. Verifier: AC1-AC5 PASS. D1 (window 3->6) and D2 fixed.

## Limits
- An unlabelled key, or a heading after block 6, is not found.
- The guard is at `ingest --exam-out`; `solve` on a hand-made exam file is not checked.
- `--pages 1-4` on the trial PDF needs OCR (scanned) to yield questions; not re-run with OCR here.

## Next
TASK-015: REQ-0018 DOCX, REQ-0019 images.

User instructions honoured: auto your task, comment less, nothing run at cost.
