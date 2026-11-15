# Phase 107 – Code-review triage report (TASK-107, REQ-0114)

**Verdict: adopted.** The user approved the fix plan (RAW-00332); fixes run as separate tasks, Fix-A first.

## Results
- 41 findings from the Fable code-review trial (`docs/report/phase-107..111-*.md`) triaged against the code:
  **17 BUG, 21 IMPROVEMENT, 3 NOT-A-DEFECT** (table and plan: `docs/design/phase-107-review-triage.md`).
- 12 BUG rows reproduced at $0 (`python3 -I work/TASK-107/repro.py`, observed by the coordinator,
  2026-11-15); 5 code-traced by the designers.
- Two review Fixes were wrong and are not adopted (107-F009 breaks glob backfill; 108-F010 still eats line 1).
- No src/ or tests/ change (git diff 2d09c8f..HEAD -- src tests = 0 files).

## Spend
3 designer runs + 5 reviewer runs, no paid exam run. Roles coder/tester/verifier waived: triage only.

## What changed for the user
Nothing in behaviour. Designer rule added: review reports are advisory (RAW-00330, `.claude/agents/designer.md`).

## Needs your go
- Fix-A ingest boundaries (P1) as the next REQ/TASK; then Fix-B adapter, Fix-C review pack, Fix-D cli, Fix-E metrics.
- Optional second review batch for `cli.py` and `ingest/` (both hit the 10-finding cap).
