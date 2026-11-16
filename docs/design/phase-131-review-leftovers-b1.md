# Phase 131 – Re-triage of the 22 never-designed batch-1 review findings (TASK-131, REQ-0138)

## Premise
TASK-130's ledger showed 22 batch-1 findings (phase-107..111 reviews, model Fable) parked as "P3 / later" since
2026-11-15. Two designers re-traced them on the current code (work/TASK-131/handoff/design-{cli,ingest}.md); the
coordinator ran the $0 repros (work/TASK-131/evidence/repro_{cli,ingest}.txt). Reviews are advisory (RAW-00330).
Report line numbers are stale; the handoffs give current lines. No src/tests change in this phase.

## Plan modes
None: triage only. Fix A touches the solve/refine CLI paths (exit codes only), fix B the refine path used by
single-source and pipeline plans (no prompt or cache-key change), fix C reporting/metrics/review pack.

## Result: 1 BUG (cosmetic), 20 IMPROVEMENT, 1 NOT-A-DEFECT, 0 already fixed; + 1 new defect (D1, P2)
| ID | Class | Repro on HEAD | Fix task |
|---|---|---|---|
| 107-F003 | IMPROVEMENT P2 | solve exit 2, no summary after a finished run (`2 False`) | TASK-133 |
| 107-F004 | IMPROVEMENT P2 | refine `--out` missing dir: paid output lost, trace write raises (code) | TASK-133 |
| 107-F005, F006 | IMPROVEMENT P3 | KeyError / FileNotFoundError traceback | TASK-133 |
| 107-F007, F010 | IMPROVEMENT P3 | traceback on bad `--out` / corrupt foreign plan.json (code) | TASK-133 |
| 107-F009 | IMPROVEMENT P3 | backfill of no valid ref prints `added 0` exit 0; review fix wrong (breaks globs) | TASK-133 |
| 110-F004 | IMPROVEMENT P3 | UnicodeDecodeError escapes the adapter | TASK-133 |
| 110-F005 | IMPROVEMENT P3 | unparseable stdout reported as `empty result` | TASK-133 |
| 108-F003 | IMPROVEMENT | multi-line numbered continuation not caught (`False True`) | TASK-134 |
| 108-F006 | IMPROVEMENT | continuation options replace the owner's (`owner_has_options ['A','B']`) | TASK-134 |
| 108-F007, F008 | IMPROVEMENT | carried passage dropped / consumed by a skipped entry (code; test in fix) | TASK-134 |
| 108-F009 | IMPROVEMENT | false `gap` over earlier pages (`{(None,'20')} set()`) | TASK-134 |
| 109-F003 | IMPROVEMENT (label) | `better` instead of `better (proxy)`; use a proxy flag, not `mixed` | TASK-135 |
| 109-F005 | IMPROVEMENT | TypeError on a row without `primary` | TASK-135 |
| 109-F006 | IMPROVEMENT | backfill aborts on one unreadable result.json (code) | TASK-135 |
| 111-F001 | IMPROVEMENT | null supersede note -> None -> AttributeError | TASK-135 |
| 111-F002 | BUG (cosmetic) | `_has_text` False on a wrapped option A (INDEX count) | TASK-135 |
| 111-F008 | IMPROVEMENT | exam text `QA: ...` line not guarded (`True`) | TASK-135 |
| 111-F009 | IMPROVEMENT | reserved subject names accepted; compare case-insensitively | TASK-135 |
| 111-F003 | NOT-A-DEFECT | only caller passes an already-validated subject | closed |

Minimal fixes per id: the handoffs' tables (one or two lines each).

## Decisions
- One fix task per area (A cli+adapter, B refine, C metrics/report_kinds/review), all P3 except the two P2 rows in A.
- D1 (found by the part-B designer, confirmed): `reporter.default_names` falls back to subject `all` for a subject
  with no Latin letters (`数学`) or none; `report_kinds.name(..., "answer-sheet")` raises ValueError -> TASK-132 (P2,
  first): reports of such exams are not written at all.
- Ledger: 21 rows `open` on TASK-133/134/135, 111-F003 `not-a-defect`; `review_ledger.py` 0 problems.
