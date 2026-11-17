# Phase 140 – Runlayout fixes from review batch 4 (TASK-140, REQ-0147)

Source: triage `docs/design/phase-137-review-triage-b4.md`, rows in `work/TASK-137/handoff/design-b.md`, repro
`work/TASK-137/evidence/repro_b.txt` (139 lines).

## Plan modes
Run/report folder layout: the `--out` publish guard (solve, report, report-pack), line-name validation, report-run
ordering. No solve, prompt or cache change.

## Design
- 140.1 139-F001: in `require_publish`, after the line is taken from `parts[1]` (runlayout.py ~112), set
  `line = None` when `parts[1] == RUNS` or `parts[1].startswith(REPORT_PREFIX)`: `--out reports/<ex>/run-<id>` and
  `plans/<ex>/runs/<id>` without `--publish` raise `PublishRequired` like `main/run-a`.
- 140.2 139-F002: `safe_line` refuses `reports` (and `plans`, for symmetry) as a line name. Exam id `reports`
  (planrun.safe_id) stays out of scope.
- 140.3 139-F003: `scan_report_runs` sorts non-legacy rows by `(id_time, _suffix, id)` with a numeric suffix, legacy
  rows by `("", 1, id)`: `-10`, `-11` sort after `-9`.

## Verification ($0)
`tests/unit/test_runlayout_fixes_140.py`, one test per id failing on old code (repro_b 139 lines flip);
`test_publish.py`, `test_runlayout.py`, `test_plansmigrate.py` green; `--fast` NEW 0; 3 ledger rows fixed.
