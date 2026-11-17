# Phase 143 – PDF text placement fixes from review batch 4 (TASK-143, REQ-0150)

Source: triage `docs/design/phase-137-review-triage-b4.md`, rows in `work/TASK-137/handoff/design-b.md`, repro
`work/TASK-137/evidence/repro_b.txt` (F001-F004, F006 lines).

## Plan modes
Native-text ingest of every PDF exam (`_text_lines`, `_strip_furniture`, `_order_page`, `parts.select_pages`).
Question text of real exams can change: checked by a before/after native ingest of the 4 input/ PDFs (OCR off,
`work/TASK-143/dump_ingest.py`, baseline from HEAD in `work/TASK-143/ingest/before/`). No prompt or cache-key change.

## Design
- 143.1 138-F001 (+D1): `_text_lines(items, mid=None)`; only when `mid` is given, filter the `above` blocks to the
  table's side (table right edge <= mid -> blocks with right edge <= mid; left edge >= mid -> left edge >= mid;
  straddling -> no filter), keep `above[-1]`. The caller passes `pw / 2.0` when the page is two-column and native.
  Same side rule for placing table/image blocks in `pages[].blocks` (~640/673) on two-column pages (D1).
- 143.2 138-F002: `_text_lines` builds table lines from `extra["rows"]` when present: every row with <= 1 non-empty
  cell -> that cell's `split("\n")` (box); else one `| a | b |` line per row with `\n` in cells replaced by a space.
  `parts.select_pages` (parts.py:98) passes `{"rows": b["rows"]}` when the block has rows. Items without rows keep
  `segment.table_lines(text)`.
- 143.3 138-F003: in the `_order_page` line retry (~193-196) only, do not treat the page as two-column when every
  right-side item's first line matches `segment._OPT` (options laid out in a row).
- 143.4 138-F004: `_strip_furniture.content()` also protects lines matching `segment._INTRO` or `segment._READ`.
- 143.5 138-F006: only if the before/after ingest (or a fixture) shows a stem line lost next to a table; otherwise
  close as not reproduced on real input with the trace in the report (the fix needs line bboxes `_page_blocks` does
  not return).

## Verification ($0)
`tests/unit/test_pdf_text_placement_143.py`, one test per fixed id failing on old code (repro_b lines flip);
existing pdf/table/boundary tests green; `--fast` NEW 0. Before/after dump of the 4 input/ PDFs: every changed
question text listed and judged (expected: only F001-F004 shapes). Ledger rows fixed (F006 fixed or not-a-defect).
