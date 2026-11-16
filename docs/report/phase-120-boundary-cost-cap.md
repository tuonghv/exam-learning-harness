# Phase 120 – Fix-J boundary accounting and NaN cost caps report (TASK-120, REQ-0127)

**Verdict: done.** Three boundary bugs (118-F001, F007, F009) and the NaN cost-cap hole on every paid entry fixed.

## Results
- **F001** the boundary AI windows no longer merge past 40 lines, so every suspect line is asked (or counted skipped
  with a warning when max_windows is hit).
- **F007** the `boundary_ai_summary` line reports this pass's windows, calls, cached and cost (was cumulative).
- **F009 / D1 / D2** `--max-cost-usd nan` (and benchmark `--budget-usd nan`) is a usage error (exit 2) for ingest
  --boundary-ai, solve, refine, cross, benchmark and genexam; the boundary cap test also stops on NaN.
- 10 tests in `tests/unit/test_boundary_cap_120.py` (11 item failures on old code, 4 guards). `--fast` 2081, NEW 0.

## Evidence ($0, no network)
Repro script now shows all three fixed; dry-run boundary estimate on the math PDF unchanged
(`work/TASK-120/evidence/summary.md`). Cache keys unchanged except windows that used to be cut (miss once).

## Spend
designer + coder runs; tester/verifier waived (small change, coordinator bite + oracle). No paid run.
