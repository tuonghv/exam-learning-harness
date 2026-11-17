# Phase 143 – PDF text placement fixes from review batch 4 report (TASK-143, REQ-0150)

**Verdict: done.** 4 batch-4 pdf findings fixed (BUG), 138-F006 waived.

## Results
- On two-column pages a table is attached to the nearest block on its own side (138-F001, + D1 block order).
- Table lines come from the cell rows: a multi-line cell stays one row and `|` inside a boxed passage is no longer a
  column split; `select_pages` passes the rows too (138-F002).
- A page of short questions with options laid out in a row is no longer read as two columns (138-F003).
- Group intro lines ("Dựa vào ... các câu từ N đến M") are no longer stripped as repeated headers (138-F004).
- 138-F006 waived: not reproduced on real input; the fix needs line boxes the adapter does not return.
- 6 tests (all fail on old code); `--fast` KNOWN 4, NEW 0.

## Real input (native ingest, OCR off, before/after)
2 of 4 input PDFs unchanged; the two DGNL exams changed in 3 fields each, all 138-F002: table headers such as
`Tổng số (người)` and the Q109 tables now read as one row instead of being split over lines (diff:
`docs/report/evidence/TASK-143/ingest_diff_words.txt`). Re-ingest these exams to pick it up.

## Spend
$0. One coder run.
