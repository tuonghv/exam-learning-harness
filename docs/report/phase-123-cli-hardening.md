# Phase 123 – P3-a CLI hardening report (TASK-123, REQ-0130)

**Verdict: done.** Six batch-2 CLI improvements (113-F004, F006-F010) fixed; two of them were silent wrong results.

## Results
- `run-stats compare A B --exam X` now notices A and B came from different exams (per-ref history sha).
- `rebuild-reports --write-recipe` skips a reports sub-folder that is not an exam id (e.g. `.ipynb_checkpoints`) with a note.
- `ingest --boundary-trace` with a missing parent dir fails before any work (`ERROR:`, exit 2), no traceback.
- `run-stats trend --last -3` is a usage error (was: dropped the 3 oldest rows, exit 0); `--last 0` = no limit.
- `run-stats board --baseline DIR` with no known exam sha says "exam sha unknown; pass --exam".
- `ingest --questions` without `--refined`, or `--refined` without `--exam-out`, is a usage error (was: silently
  wrote every question / no effect). The documented DGNL command is unaffected.
- 7 tests in `tests/unit/test_cli_hardening_123.py`, all fail on old code; `--fast` 2105, NEW 0.

## Spend
1 coder run; designer/tester/verifier waived (rows pre-designed in the batch-2 triage; coordinator bite + docs check).
