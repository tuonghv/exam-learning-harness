# Phase 147 – Fable review reports folder + 138-F006 (TASK-147, REQ-0153)

**Verdict: done.** The 13 Fable code-review reports now live in `docs/report/fable-review/` with a follow-up
status header; the only finding that was not fixed (138-F006, waived) was a true positive and is now fixed.

## Results
- `git mv` of 13 reports to `docs/report/fable-review/<YYYY-MM-DD>-phase<N>-<slug>.md` (date = first commit,
  RAW-00369), e.g. `2026-11-17-phase138-pdf-adapter-b4.md`.
- Each starts with a `<!-- fable-status -->` block: Status line (findings, fixed-by TASKs, false positives with
  their reasons, what is still open) and the Action rule (RAW-00368). Built from `docs/review/findings.tsv`.
- Re-check of every not-fixed finding: 138-F006 true positive (the TASK-143 waiver said line boxes were missing;
  `_line_blocks` already returns them) -> `pdf._drop_table_blocks` keeps a straddling block's lines outside the
  table. The 5 not-a-defect rows are false positives: marked with their triage reason and skipped
  (109-F001, 110-F003, 110-F006, 111-F003, 118-F005).
- `tools/review_ledger.py` scans `docs/report/fable-review/` (and old `docs/report/phase-*`); code-reviewer agent
  and review prompt write new reports there. Ledger: 108 ids, 0 open.
- Tests: 4 new (fail on old code), 1 ledger test. Real ingest of 4 PDFs (DGNL 2024/2025/2026, math 2026)
  identical old vs new.

## Issues
- Not changed: the OCR path filter (`pdf.py` ~697) uses the same centre rule; out of the finding's scope.
- Pre-existing `--fast` failure `test_check_examples.test_12b` (`examples/dgnl: unknown subject dir`, a tracked
  PDF), also failing without this change.

## Spend
$0.
