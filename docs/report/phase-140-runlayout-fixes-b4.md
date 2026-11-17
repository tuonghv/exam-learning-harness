# Phase 140 – Runlayout fixes from review batch 4 report (TASK-140, REQ-0147)

**Verdict: done.** 3 batch-4 runlayout findings fixed (all BUG).

## Results
- `--out reports/<ex>/run-<id>` or `plans/<ex>/runs/<id>` without `--publish` now raises PublishRequired: a published
  report run can no longer be overwritten by accident (139-F001).
- `reports` and `plans` are reserved line names: the report manifest can no longer land inside the reports tree (139-F002).
- Report runs sort by numeric suffix: `-10`, `-11` come after `-9`, so prev_report_run and Latest are right (139-F003).
- 3 tests (all fail on old code); existing publish/runlayout/plansmigrate tests unchanged; `--fast` KNOWN 4, NEW 0;
  ledger 3 rows fixed.

## Spend
$0. One coder run.
