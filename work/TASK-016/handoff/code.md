PROGRESS: COMPLETE
SKILLS: coding, token-efficiency

## Files
- src/exam_engine/ingest/adapters/image.py (new): sniff/size parsers, copy original, PIL resize, opt-in OCR via fitz
- src/exam_engine/ingest/adapters/__init__.py: register .png .jpg .jpeg .webp
- src/exam_engine/ingest/schema.py: CODES + format_mismatch, no_text
- src/exam_engine/ingest/api.py: to_exam_text -> no_text for image-only doc
- src/exam_engine/cli.py: --ocr gains `on` (default auto = off for images)
- src/exam_engine/adapters/claude.py: run_claude_images; run_claude now delegates to _run (same argv/behaviour, tested)
- tests/unit/test_ingest_image.py (19 tests); docs/guide/ingest-usage.md, ingest-setup.md

## Tests
Full suite 375 OK (356 + 19). Image tests need PIL for jpeg/webp/resize (present here).

## Mutation
sniff PNG magic disabled -> 4 failures + 7 errors; extension/format check disabled -> 1 failure. Restored; green.

## Notes / risks
- OCR uses PyMuPDF get_textpage_ocr, NOT a tesseract subprocess: test_guards allows only claude.py/reporter.py to start processes. OCR path itself only tested with mocks (no tesseract run; bad input returns a warning-style error).
- `--input-format stream-json` with `--output-format json` is unverified against the real CLI (no real call made); main should check in the paid run.
- JPEG/PNG/WEBP truncation detection relies on end markers (IEND, FFD9, RIFF size).

## Defects
None.
