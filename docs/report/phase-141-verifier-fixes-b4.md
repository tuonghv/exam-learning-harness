# Phase 141 – Verifier fixes from review batch 4 report (TASK-141, REQ-0148)

**Verdict: done.** 3 batch-4 verifier findings (BUG) plus the triage extra D4 fixed.

## Results
- Computed check strips a leading label: `x = 1/2` and `v2 = 10` are read as 1/2 and 10, not 1 and 2 (137-F005).
- A root sign without parentheses (`√3/2`) and an implicit product (`2√3`) are evaluated, in verifier and scorer (137-F006).
- The ordering format check accepts letters beyond e (6+ sentences) (137-F007).
- A quote that is only an option label (`"B. "`) no longer passes as verbatim (D4).
- Each was a false `fail` that cost a paid retry and could end FAIL.
- 4 tests (all fail on old code); `--fast` KNOWN 4, NEW 0; ledger 3 rows fixed.

## Spend
$0. One coder run.
