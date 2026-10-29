PROGRESS: COMPLETE
SKILLS: python
Files: src/exam_engine/ingest/{optional.py,segment.py,adapters/pdf.py (new); adapters/__init__.py, api.py (to_exam_text via questions for non-md), schema.py (CODES + encrypted, no_questions)}; src/exam_engine/cli.py (--assets, --ocr, --check; --out now written before --exam-out so a no_questions failure keeps the doc); tests/unit/test_ingest_pdf.py; docs/guide/ingest-setup.md.
Tests: unit 301 run, OK, 1 skipped (vie OCR test: vie.traineddata not installed); integration 2 OK. New file: 22 tests.
Mutations: encrypted check disabled -> test_encrypted errors; "keep native text" (OCR on every page / replace) -> 4 tests fail; restored, all pass.
Deviations: 2-column detection also retries at line level (MuPDF merges same-baseline columns into one block). Extra top-level doc key "intro" (text before Q1) for to_exam_text. toolkit-reference.md has no ingest rows, not edited. Page dicts carry extra keys (chars, images, drawings, status, method, warnings).
Caveats (no real PDFs tried): table detection and drawing clustering are heuristic; table-like vector grids may also yield crops; OCR needs tesseract (eng only here); absolute --assets paths are recorded relative to cwd or by folder name.
