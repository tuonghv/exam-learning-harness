# Phase 84 report - solve cache follow-ups (REQ-0090)

- Result: (AC1) the "already solved" line now shows the original paid run (`cost=$0.046096 calls=3`, was `$0.0` from the newer cached run); (AC2) `build_result` tolerates a runner without `cache`; (AC3) a cached `cost_usd` that is negative, NaN, inf, bool or str is a miss; (AC4) `claude.resolve` maps aliases through `model_pins` for `--real` refine/ingest, unresolved aliases are refused (exit 2, before any call), mock/dry-run unchanged; (AC5) a direct `metrics.block` test replaces the always-true assertion.
- Verification: verifier AC1-AC5 PASS; AC1 checked against the paid run's result.json; free real check on the cacheproof-en exam (no paid call this task).
- Tests: 19 new in `tests/unit/test_cache_followups.py`; full suite 1647 run, only the 4 known pre-existing failures. Bite check: removing the cost range check fails 4 tests.
- Open (low): no real-run proof of the refine/boundary alias path (unit tests only); pages/windows cached under the old `sonnet`/`haiku` keys are re-paid once (D1(a)); other `--real` commands without a cache (cross, benchmark, genexam) still accept aliases.
- Evidence: `work/TASK-084/evidence/` (real-proof, unit, full; untracked).
