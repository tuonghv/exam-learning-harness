# Phase 117 – Code-review triage report, batch 3 (TASK-117, REQ-0124)

**Verdict: adopted** (priority set by the coordinator, RAW-00342). Fixes run as separate tasks, Fix-H first.

## Results
- 19 findings from review batch 3 (`docs/report/phase-117-ingest-api-parts-b3.md`, `phase-118-ingest-boundary-b3.md`):
  **12 BUG, 6 IMPROVEMENT, 1 NOT-A-DEFECT**, plus D1 (solve NaN cost cap) found by a designer.
- All 12 BUG rows reproduced at $0 (`work/TASK-117/repro_{api,boundary}.out`).
- Real inputs: the 4 PDFs detect exam/key parts correctly today; the key-leak bug (117-F001) needs a DOCX/MD with an
  appended key. Four review Fixes adjusted before adoption (117-F001/F005/F009, 118-F009).
- No src/ or tests/ change.

## Spend
2 reviewer + 2 designer runs, no paid exam run.

## Next
Fix-H parts (117-F001/F009/F010/F002/F003) -> Fix-I api (117-F008/F004/F005/F007) -> Fix-J boundary + cost cap
(118-F001/F007/F009, D1) -> P3 hardening.
