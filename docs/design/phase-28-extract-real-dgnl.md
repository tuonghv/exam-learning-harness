# Phase 28: extract and solve a whole real DGNL PDF (REQ-0033)

## Goal
Real PDF -> solvable per-section exams -> unchanged engine, so the engine can be learned from on real exams.

## Design
- Reuse: `ingest`, `ingest-refine` (vision), `to_exam_text`, `solve`. Nothing in the solver changes.
- `refine.pick_pages(..., all_pages)` + `--all-pages`: unflagged pages (math) are sent too.
- Refine reply gains `context` (shared passage) and `carry` (passage printed on the previous page); a stem-less option fragment joins the previous question.
- `api._from_refined` (`ingest --refined DOC --questions A-B`): sorts options, joins split questions, repeats a group passage (`Questions N-M`, `câu từ N đến M`) in every question, prints figures as text, renumbers from 1 with an offset note.
- Config subject `science` (no subject prompt, like `vietnamese`).
- Tests at $0 with injected replies. Real run: 22 pages in batches, 4 sections, caps per call.

## Risks
Vision text may differ from the print (needs_review marks it); no key, so accuracy is not measured; copyrighted text stays untracked.
