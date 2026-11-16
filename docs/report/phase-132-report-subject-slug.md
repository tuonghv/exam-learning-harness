# Phase 132 – Report names for a non-Latin or missing subject report (TASK-132, REQ-0139)

**Verdict: done.** TASK-131's new defect D1: an exam whose subject has no Latin letters (e.g. `数学`), no subject,
or the subject `All` wrote no report at all (`ValueError: kind answer-sheet has scope subject, subject 'all'`).

## Results
- `reporter.default_names` uses `subject` when the slug is empty or the reserved `all`; Latin subjects keep their
  names (`math`, `t-duy-khoa-h-c`, unchanged).
- 3 tests (2 fail on old code); `--fast` KNOWN 4, NEW 0.

## Spend
$0.
