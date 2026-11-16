# Phase 118 – Fix-H answer-key detection report (TASK-118, REQ-0125)

**Verdict: done.** Five triaged parts/api bugs fixed (117-F001, F009, F010, F002, F003).

## Results
- **F001** an answer-key heading anywhere on a page now starts the key part (was: first 6 blocks only), so a DOCX/MD
  with a key appended after the questions no longer leaks it into the exam text.
- **F009** a page whose first block is a sentence starting with a key word (`Solutions to ...`, `Lời giải thích ...?`)
  stays exam. Two-tier guard: first 6 blocks keep today's prefix match minus `?` and long sentences ending `.` (so a long
  mixed-case title such as `Đáp án và hướng dẫn chấm ...` is still caught); deeper blocks need a heading-like line.
- **F010** a Markdown key is refused with `answer_key_present` instead of a KeyError traceback.
- **F002** `--pages` past the first key page keeps the key guard (key pages taken from the full document).
- **F003** re-segmentation under `--pages` keeps DOCX list/heading option lines.
- Coordinator decision: a one-page DOCX/MD holding a key is all `answer_key` (export refuses; never leak a key).
- Tests: 11 in `tests/unit/test_ingest_key_parts_118.py` (6 bite, 5 guards); test_ingest_inspect assertion that encoded
  F001 flipped. `--fast` 2058 ran, KNOWN 4, NEW 0.

## Real data ($0, `work/TASK-118/evidence/summary.md`)
4 input PDFs + 22 examples: parts and segment output identical old vs new. The fix closes a leak path for files we do
not have yet (DOCX/MD with an appended key).

## Spend
designer, coder, tester runs; verifier waived (coordinator oracles + tester bite). No paid run.

## Next
TASK-119 Fix-I api (117-F008, F004, F005, F007).
