# Phase 128 – Stale TASK-048 real-doc golden report (TASK-128, REQ-0135)

**Verdict: done.** `test_assembly_qa.Golden.test_48_golden_refined_real_doc` (outside `--fast`) compared HEAD's
doc.json/e.md for the DGNL 2026 PDF with code from before TASK-048; the intended ingest changes of TASK-114..126
(0 -> 120 native questions, source pages, group figures, continued pages, section labels) made it fail.

## Results
- The test now checks the TASK-048 invariants on HEAD: sidecar written, one row per question, source pages on every
  row, failed rows = `[Incomplete:` markers, identical output on a second run.
- Bite: forcing every sidecar row to `passed` fails the test. Synthetic goldens keep their 63a5299 byte comparison.
- `test_assembly_qa` all pass; `--fast` KNOWN 4, NEW 0.

## Spend
$0. Roles waived (test-only).
