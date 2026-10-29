# Report: TASK-013 PDF adapter (REQ-0017, EPIC-005)

**Verdict: adopted on synthetic fixtures; not yet proven on real exam PDFs.**

## What exists
- `ingest/optional.py`: loads `fitz`, `docx`, `PIL` under `python3 -I` by appending only the user site-packages to the END of `sys.path` (never the current folder); else `missing_dependency` with the pip command.
- `ingest/adapters/pdf.py` (`.pdf`): inspect (encrypted, corrupt, empty), native text with bbox and Unicode, conservative 2-column order, tables, image and drawing crops (capped), math-font page render, per-page heuristics, selective OCR (`--ocr auto|off`), statuses native_text|ocr|mixed|needs_review.
- `ingest/segment.py`: shared question and option splitter; skips when numbering is not consecutive; `to_exam_text` raises `no_questions` instead of guessing.
- CLI: `ingest --assets DIR --ocr auto|off --check`; setup guide `docs/guide/ingest-setup.md`.

## Verification
Suite 301 unit (1 skip) + 2 integration OK; mutation checks (encrypted, keep-native-text) make tests fail; a Vietnamese PDF built with PyMuPDF ingests as native_text with diacritics intact, 2 questions, and the exam text passes `solve --dry-run`. Verifier: AC1, AC3-AC5 verified, no major defects.

## Limits (honest)
- Vietnamese OCR is unverified: `vie.traineddata` is not installed (English only); that test skips.
- No real exam PDF was tried; fidelity on real layouts, fonts and formulas is unmeasured. Send 1-2 samples.
- On a flagged page, OCR text replaces that page's native text (design); good pages are never replaced.
- Math stays text plus a page image, not LaTeX.

## Next
REQ-0018 DOCX, REQ-0019 images; then real PDFs.
