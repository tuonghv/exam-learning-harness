# Phase 130 – Review findings ledger report (TASK-130, REQ-0137)

**Verdict: done.** User question (RAW-00350): which Fable review findings never reached design, and how to stop that.

## Results
- All 9 Fable review reports (80 findings) went through a triage task (TASK-107, 113, 117), but 22 batch-1 findings
  were parked as "P3 / later" and never designed: 107-F003..F007, F009, F010; 108-F003, F006..F009; 109-F003, F005,
  F006; 110-F004, F005; 111-F001..F003, F008, F009 (21 IMPROVEMENT + the cosmetic BUG 111-F002). Batches 2 and 3 are
  fully closed. The coordinator's earlier "all review findings handled" was true for batches 2/3 only.
- `docs/review/findings.tsv`: one row per finding (54 fixed with the fixing TASK, 4 not-a-defect, 22 open -> TASK-131).
- `tools/review_ledger.py`: finds review reports by their `### Fnnn – [SEV]` headings and reports ids without a row,
  bad dispositions, missing TASK refs and `open` rows whose task is not queued/active; exit 1 on problems.
- workflow-check shows each problem as a WARN (non-blocking; a blocking rule needs the user's confirmation).
- Coordinator skill: a review batch is done only when its ids are in the ledger; no "P3, later" without an open row.
- 7 tests; `--fast` KNOWN 4, NEW 0.

User instructions honoured: RAW-00350 (list of undesigned reports, prevention, plan).

## Next
TASK-131: re-triage the 22 open findings against the current code, fix the still-valid ones per file, close the rows.

## Spend
$0.
