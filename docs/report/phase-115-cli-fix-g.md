# Phase 115 – Fix-G cli report (TASK-115, REQ-0122)

**Verdict: done.** Four triaged CLI bugs fixed (113-F001, F002, F003, F005) plus `run-stats explain <run_id>` (AC6, same
root cause as F003, added by the user); verifier PASS.

## Results
- **F001** `solve --line` failing before start removes the plan run dir it claimed; the next `publish --from` works.
- **F002** a failed `report` / `report-pack` build removes only the fresh run dir it claimed, then empty line/exam dirs
  (never the reports root, `--out`, a `--report-id` reuse, or a sibling run). Supersedes the phase-87 row "build fails ->
  run-list incomplete" for fresh dirs only; `incomplete` remains for kill/crash and reuse.
- **F003 / AC6** `run-stats stats|explain <run_id>` use the dir `_rs_resolve` already found: same output as by dir.
- **F005** `rebuild-reports --write-recipe --dry-run` is a usage error (exit 2); the tracked recipe is never rewritten.
- Only `src/exam_engine/cli.py` changed (+30 -8); solve paths untouched (diff). 10 tests in
  `tests/unit/test_cli_fix_g_115.py` (8 bite on old code, 2 guards); test_87_3 updated. `--fast` 2048 ran, KNOWN 4, NEW 0.

## Evidence ($0)
`work/TASK-115/evidence/summary.md`: repro_cli.py old vs new: F001 1 -> 0 dirs left, F003b DIFFERS -> same, F005 rc 0
recipe changed -> rc 2 unchanged.

## Spend
designer, coder, tester, verifier runs; no paid exam run.

## Notes
- The main session added `_drop_fresh_report_dir` after the phase-87 test update showed an empty line dir listed as `legacy`.
- Accepted residuals: an empty pre-existing line dir is removed; a kill or an unexpected exception type still leaves a dir.

## Next
P3 hardening (12 IMPROVEMENTs of batch 2) is optional; F002 follow-up from TASK-114 (`api.py` GROUP_RE case) open.
