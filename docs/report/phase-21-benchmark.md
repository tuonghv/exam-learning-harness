# Report: TASK-021 benchmark (REQ-0009, EPIC-003)

**Verdict: command built and mock-verified; the real measurement (REQ-0009 AC1, AC4) waits for the user's go.**

## What exists
`scripts/exam.py benchmark --out DIR (--dry-run | --mock FILE | --real) [--budget-usd 3.00] [--subject S] [--previous summary.json]` runs the unchanged engine over the 15 `evals/inputs` items with `evals/keys` read only by the scorer. It writes `summary.json` and `report.md`: per-subject and total pass/fail/uncertain/unresolved, per question answer, verdict, reason, attempts, points, checked-by (`key match`, `code oracle`, `claude review only`), a failure list, skipped items, and a regression flag against a previous summary. Never defaults to real; prints items, the call bound (<= 75) and the budget first; one shared budget stops the remaining items (exit 3).

## Verification
463 unit tests OK (5 new); fake-llm tests prove pass/fail counting, key text absent from every prompt, budget stop, regression flag, CLI modes. Dry run lists the 15 pairs and calls <= 75. Evidence: `work/TASK-021/evidence/`.

## Limits
No real run yet, so no score is claimed. Estimated cost about $2-3 (cap $3.00). Few-shot examples are not in `evals/inputs`.

## Next
Real run with the user's go; then fix only measured failing items (AC4).

User instructions honoured: cost gate kept, no engine or prompt change, key never exposed to the solver, short replies.
