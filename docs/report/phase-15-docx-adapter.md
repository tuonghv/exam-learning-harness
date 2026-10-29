# Report: TASK-015 DOCX adapter, spec tests, usage docs (REQ-0018, EPIC-005)

**Verdict: adopted on synthetic fixtures; no real exam DOCX tried yet.**

## What exists
- `ingest/adapters/docx.py` (`.docx`): body-order paragraphs, heading levels, lists, tables (merged cells deduped), images saved unchanged to `--assets` with sha256, math/unsupported-content warnings; errors corrupt/empty/encrypted/missing_dependency. Loads `python-docx` via the user-site loader.
- `tests/unit/test_ingest_docx.py` (22) and `test_ingest_spec.py` (10 cases of the spec section 8; OCR/library cases skip with a reason).
- Docs: `docs/guide/ingest-usage.md` (usage, limits, risks); `ingest-setup.md` (setup, self-check).

## Verification
356 unit tests OK; 5 mutations (table, merge dedupe, asset sha, image bytes, image-in-table warning) each fail a test. Verifier: AC1, AC2, AC3, AC3b verified; D1/D2 low (D2 fixed).

## Schema / interface / dependencies
Canonical document v1 unchanged; `ingest <file.docx> [--assets DIR --out --exam-out --meta]`; deps pymupdf, python-docx, pillow optional, tesseract + `vie` optional.

## Limits
Math in Word equations is plain text with a warning; headers, footers, text boxes and footnotes are not read; one logical page; no real DOCX fidelity measure.

## Next
TASK-016 images (REQ-0019), TASK-017 refine (REQ-0021).

User instructions honoured: auto your task, comment less, document setup.
