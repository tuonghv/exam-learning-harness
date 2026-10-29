# Phase 13: PDF adapter, optional-lib loader, setup doc (REQ-0017, TASK-013; EPIC-005)

## Goal
`ingest <file>.pdf` -> the same canonical document v1 (phase 12). PyMuPDF native text first, OCR only on bad pages, page images/crops only where text cannot carry the content. No Claude call, no network. Spec: `tmp/input-exam-format.md` section 4.1 and 7.

## Optional-lib loader (user decision RAW-00055, option A)
`ingest/optional.py: load(module, pip)`: `importlib.import_module`; on ImportError append `site.getusersitepackages()` (if the folder exists) to the END of `sys.path` and retry; still failing -> `IngestError("missing_dependency", "pip install <pip>")`. Used only for `fitz` (pip `pymupdf`), `docx` (`python-docx`), `PIL` (`pillow`). The current folder is never added; `-I` stays.

## PDF adapter `ingest/adapters/pdf.py` (register `.pdf`)
- Inspect: open read-only (original never written); `needs_pass` -> `encrypted`; open/parse failure -> `corrupt`; 0 pages or no text and no images -> `empty`. Record per page: size, char count, image count, drawing count.
- Native text: `page.get_text("dict")`; one block per PDF text block with `bbox`, `origin: "extracted"`, `order` per page; Unicode kept (NFC). Reading order conservative: keep PyMuPDF order, except a clear 2-column page (>=2 blocks in each half, none spanning the middle gap) reads left column top-down then right. No guessing beyond that; otherwise a `reading_order_uncertain` warning when blocks overlap.
- Tables: `page.find_tables()` (if present) -> `table` block with `rows` and bbox; text inside a table bbox is not repeated as paragraphs.
- Suspicion heuristics per page (warnings, not proof): chars < 20 (`missing_text`), U+FFFD or control chars > 1% (`bad_encoding`), no letters but many glyphs, doc-level `no_question_numbering` when no `Câu N` / `Question N` / `N.` line exists.
- OCR (`config.ocr`: `auto` default | `off`): only pages flagged above. `page.get_textpage_ocr(language, dpi=200, full=True, tessdata=...)`; language `vie+eng` if both traineddata exist in `config.tessdata` / `$TESSDATA_PREFIX` / known dirs, else the available one with warning `ocr_language_missing`, else no OCR and page status `needs_review` (never an exception for a missing language). OCR text goes in blocks with `origin: "extracted"`, `method: "ocr"`; it never replaces native text of a good page.
- Visual preservation: embedded images and clustered vector drawings -> PNG crop at 150 dpi of the bbox into `config.asset_dir` (default `work/ingest/<sha8>/`), `assets[]` entry (relative path, sha256, page, bbox) and an `image` block; a page with math fonts (font name contains Math, CMSY, CMMI, CMEX, Symbol) gets one page render plus warning `math_possible`. Cap: at most 6 crops per page, 200 dpi max; nothing else is rendered.
- Status: `native_text` (no OCR, no flagged page), `ocr` (all text pages OCR), `mixed`, `needs_review` (any flagged page still unreliable). Page-level `status` and `warnings` too.

## Question segmentation (shared, `ingest/segment.py`, used by PDF, optional for others)
Line-start `Câu N` / `Question N` / `N.` begins a question; `A.`/`A)` to `D.` lines are options. Fills optional `questions` only when numbering is consecutive and every question has text; otherwise leaves it empty with warning `segmentation_skipped`. `to_exam_text` for non-exam sources uses `questions` + `meta` (instructions/passage = text before the first question); no questions -> `IngestError("no_questions")` that names the saved document so it can be fixed by hand. Never auto-corrects source text.

## CLI
`ingest` gains `--assets DIR` and `--ocr auto|off`; nothing else changes.

## Setup doc `docs/guide/ingest-setup.md`
`pip install pymupdf python-docx pillow`; why `python3 -I` needs the loader; tesseract install and `vie.traineddata` (`TESSDATA_PREFIX`); self-check `python3 -I scripts/exam.py ingest --check` printing fitz/docx/PIL versions, tesseract binary and languages found, and the user-site path used.

## Tests ($0)
Fixtures are built in the test with fitz (skip with a reason if fitz is absent): digital PDF; Vietnamese text (needs a TTF with diacritics, e.g. DejaVu; skip if none); 2-column page; table; image + vector diagram; math-font page; image-only "scanned" page (OCR test uses English text and skips if tesseract/eng is absent; the vie test skips if vie data is absent); encrypted, corrupt, empty PDF; loader unit test with a fake user site folder; original PDF sha unchanged after ingest; segmenter cases; `ingest --check` smoke. Backward compat: all earlier ingest tests still pass.

## Limits
Math in PDFs is kept as text plus a page image, not LaTeX. OCR quality for Vietnamese depends on the installed data. Scanned two-column layouts are not reordered. pymupdf4llm not used.

## Open questions
None: REQ-0017 Q1-Q3 and the loader option accepted (RAW-00050, RAW-00055).
