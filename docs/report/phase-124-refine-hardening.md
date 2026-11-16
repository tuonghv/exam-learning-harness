# Phase 124 – P3-b refine hardening report (TASK-124, REQ-0131)

**Verdict: done.** Five batch-2 refine improvements (114-F003, F006-F009) fixed.

## Results
- A reply with non-string `figures` is now `invalid_reply` (retried) instead of being cached as valid and crashing
  the run after all paid calls; `_native_tables` can no longer raise.
- Table cells match as whole tokens (`1` is no longer "present" because `13` contains it).
- A label-less numeric table goes to the single question on its page that refers to a table; otherwise the
  `native_table_unplaced` warning stays.
- Orphan advice names `p-1` only when that page can be added; otherwise "check page(s) N" (no more "add page 0").
- An out-of-order window reply gets the review reason `order`.

## Evidence ($0)
All 41 real cached page replies in `plans/*/cache` still validate (no extra paid calls). 6 tests (5 bite, 1 guard);
`--fast` 2111, NEW 0. A flaky unrelated test (`test_plan_qa` test_58_4) failed once and passed on re-run: follow-up.

## Spend
1 coder run; designer/tester/verifier waived (rows pre-designed; coordinator bite + cache check).
