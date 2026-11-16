# Phase 113 – Code-review triage report, batch 2 (TASK-113, REQ-0120)

**Verdict: adopted.** The user approved the fix plan (2026-11-16); fixes run as separate tasks, Fix-F first.

## Results
- 20 findings from review batch 2 (`docs/report/phase-113-cli-logic-b2.md`, `phase-114-ingest-segment-refine-b2.md`)
  triaged against the code: **7 BUG, 13 IMPROVEMENT, 0 NOT-A-DEFECT** (table and plan: `docs/design/phase-113-review-triage-b2.md`).
- 5 BUG rows reproduced at $0 (`work/TASK-113/repro_cli.out`, `repro_ingest.out`, observed by the coordinator,
  2026-11-16); 114-F004 and F010 code-traced by the designer.
- Six review Fixes adjusted before adoption (114-F001/F002/F004/F010, 113-F002/F005; see the design doc).
- No src/ or tests/ change (git diff baa5054..HEAD -- src tests = 0 files).

## Spend
2 designer runs + 2 reviewer runs, no paid exam run. Roles coder/tester/verifier waived: triage only.

## What changed for the user
Nothing in behaviour.

## Next
- Fix-F ingest (P1: 114-F001, F002, F010, F004) as the next REQ/TASK; then Fix-G cli (P2: 113-F001, F003, F005, F002).
- P3 hardening (12 IMPROVEMENTs) stays optional; `ingest/api.py`, `boundary.py`, `parts.py` still unreviewed.
