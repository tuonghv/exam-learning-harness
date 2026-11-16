# Phase 133 – Review leftovers fix A: cli + Claude adapter report (TASK-133, REQ-0140)

**Verdict: done.** 9 batch-1 findings re-triaged in TASK-131, all IMPROVEMENT.

## Results
- solve: a report-build failure after a finished run is a WARN; the run keeps its exit code, summary and history (107-F003).
- ingest-refine: a missing `--out` dir fails with exit 2 before any paid call; the trace write is guarded (107-F004).
- Clean exit 2 instead of a traceback: `ingest --refined` without a refined block (107-F005), benchmark missing
  `--inputs` (107-F006), lessons unwritable output or non-object summary (107-F007 + D1/D2), run-list corrupt foreign
  plan.json via `runlayout._jload` (107-F010).
- run-stats backfill: WARN per skipped ref, exit 2 only when no ref is valid; the review's exit-2-on-any-skip was
  not adopted (it breaks glob backfill) (107-F009).
- Claude adapter: UTF-8 decoding with replacement (110-F004); unparseable stdout is class `other` with its text, not
  `empty result` (110-F005); test_exam_llm's expected class updated with the user's approval (RAW-00351).
- 9 tests, all failing on old code; `--fast` KNOWN 4, NEW 0. Ledger: 9 rows `fixed TASK-133`.

User instructions honoured: RAW-00351 (update the test).

## Spend
$0. One coder run.
