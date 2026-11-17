# Phase 142 – PDF OCR route fixes from review batch 4 report (TASK-142, REQ-0149)

**Verdict: done.** 5 batch-4 pdf OCR findings fixed (4 BUG, 1 IMPROVEMENT).

## Results
- A page with garbled native text that is OCR'd now takes its table area from OCR too; the garbled native cells are
  dropped (138-F005). A page whose native text is only missing keeps its native tables and adds OCR text outside
  them (refined in review: a coder guard that skipped OCR would have lost a scanned stem next to a table).
- Clean OCR text replaces garbled native text even when it is not longer (138-F007).
- `ocr_doubt: chars` marks questions on pages whose OCR text is suspect, not pages whose native text was (138-F008).
- The page-cut warning no longer reads OCR pages (138-F009).
- A PDF with a broken page fails as `ERROR: ingest corrupt`, not a traceback (138-F010).
- 6 tests (5 fail on old code, 1 guards the kept behaviour); `--fast` KNOWN 4, NEW 0; ledger 5 rows fixed.
- No real OCR run: tests use fake pages. Ingest output of OCR'd exams can change on the next re-ingest.

## Spend
$0. One coder run, 2 rounds.
