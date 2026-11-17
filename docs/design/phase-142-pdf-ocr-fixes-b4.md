# Phase 142 – PDF OCR route fixes from review batch 4 (TASK-142, REQ-0149)

Source: triage `docs/design/phase-137-review-triage-b4.md`, rows in `work/TASK-137/handoff/design-b.md`, repro
`work/TASK-137/evidence/repro_b.txt` (F008, F009 lines).

## Plan modes
Ingest of PDFs whose native text is missing or garbled (OCR branch of `pdf._extract`), the ocr_doubt marks and the
page-cut warning. Native-text pages are unchanged. Local OCR only, $0; no prompt or cache-key change.

## Design
- 142.1 138-F005: when OCR is chosen for a page, set `tables = []` and use the OCR blocks unfiltered by `tbbox`;
  keep `tbbox` only for the crop filter (~655) so table rulings do not become crops.
- 142.2 138-F007: accept OCR also when `len(ocr_text.strip()) >= MIN_CHARS and flags != ["missing_text"] and not
  _suspect(ocr_text)` (garbled native text loses to clean OCR even when OCR is not longer).
- 142.3 138-F008: the `sus` set passed to `_ocr_doubt` is the pages with `method == "ocr"` and status
  `needs_review` (the suspect OCR text), not native `bad_encoding` warnings.
- 142.4 138-F009: `_cut_boundaries.ok(p)` also requires `p.get("method", "native") != "ocr"`.
- 142.5 138-F010: in `ingest`, around `_extract`: `except IngestError: raise`, then `except Exception as exc: raise
  IngestError("corrupt", "cannot read PDF %s: %s: %s" % (basename, type(exc).__name__, exc))`.

## Verification ($0)
`tests/unit/test_pdf_ocr_fixes_142.py` with a fake fitz page/document (no real OCR), one test per id failing on old
code; existing pdf/ocr/refine-window tests green; `--fast` NEW 0; 5 ledger rows fixed.
