# Phase 131 – Re-triage of batch-1 review leftovers report (TASK-131, REQ-0138)

**Verdict: done.** The 22 findings that TASK-130's ledger showed as never designed were re-traced on the current code.

## Results
- 21 still valid (20 IMPROVEMENT, 1 cosmetic BUG), 1 NOT-A-DEFECT (111-F003), 0 fixed in passing.
- 14 rows reproduced with $0 snippets on HEAD; the rest have current file:line evidence (tests come with the fixes).
- Two review fixes are wrong and are not adopted: 107-F009 (exit 2 would break glob backfill) and 109-F003 (a `mixed`
  basis breaks the verdict; a proxy flag instead); 111-F009 must compare names case-insensitively.
- New defect D1 (P2, confirmed): an exam whose subject has no Latin letters (e.g. `数学`) or no subject cannot write
  its reports (`subject 'all'` ValueError) -> TASK-132, first.
- Queued: TASK-132 (D1), TASK-133 (cli + adapter, 9 ids), TASK-134 (refine, 5), TASK-135 (metrics/report_kinds/review, 7).
  Ledger: 21 `open` on those tasks, 0 problems.

User instructions honoured: RAW-00350 (plan for the never-designed findings).

## Spend
$0. Two designer runs.
