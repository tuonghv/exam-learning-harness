# Phase 113 – Code-review triage, batch 2 (TASK-113, REQ-0120)

## Premise
Second review batch (`docs/report/phase-113-cli-logic-b2.md`, `phase-114-ingest-segment-refine-b2.md`, 20 findings,
model Fable) deep-dived against the current source by two designers (`work/TASK-113/handoff/design-{cli,ingest}.md`).
Reviews are advisory, not requirements (RAW-00330). Classes and evidence tags as in `phase-107-review-triage.md`.
No source or test file is changed in this phase.

## Plan modes
None: triage only. Fix-F (ingest) touches the single-source and pipeline ingest paths; Fix-G (cli) touches neither solve path.

## Result: 7 BUG, 13 IMPROVEMENT, 0 NOT-A-DEFECT
R = reproduced by the coordinator ($0, 2026-11-16, `work/TASK-113/repro_{cli,ingest}.out`); T = code-traced.

| ID | Class | Impact | Ev |
|---|---|---|---|
| 114-F001 | BUG | option-less question swallows the next part heading / group intro; next question loses its context | R |
| 114-F002 | BUG | `CÂU 31 - 35: ...` (upper case / `Cau`) read as question 31 with text `- 35: ...` | R |
| 114-F004 | BUG | failed backward re-run (call_failed / invalid_reply / cost_cap) aborts a finished refine; paid first pass lost | T |
| 114-F010 | BUG | window result overwrites the passage carried from a question-less page | T |
| 114-F003, F005..F009 | IMPROVEMENT | prompt-violating replies, opt-in boundary AI only, table safety net, advice text, reason code | T |
| 113-F001 | BUG | `solve --line` failing before start leaves an empty plan run dir; next `publish --from` refuses | R |
| 113-F003 | BUG | `run-stats stats <run_id>` drops the plan run's exam copy: fewer metrics, exit 0 | R |
| 113-F005 | BUG | `rebuild-reports --write-recipe --dry-run` rewrites the tracked recipe (git restores) | R |
| 113-F002, F004, F006..F010 | IMPROVEMENT | clutter dir, missing guards, usage slips, wrong reason in a loud exit | T |

Review Fixes not to adopt as written (designer notes):
- 114-F001: open the pending context only for `_PART_ANY`, or an `_INTRO` whose span starts at n+1; guard `options[-1]` at end of input.
- 114-F002: add re.I and `Cau` to `_INTRO` only; GROUP_RE stays byte-identical (phase-108).
- 114-F004: report the run's call/cost totals, not only the failing call's.
- 114-F010: reuse `_dedupe` for the carried + window context.
- 113-F002: clean only a dir this call created (never a `--report-id` reuse), in the build excepts (cli.py:468-470, :523-525).
- 113-F005: `--write-recipe --dry-run` is a usage error (exit 2); a preview mode would be a new feature.

## Priority plan
**P1 – wrong exam content or aborted run on real inputs**
- **Fix-F ingest** (`ingest/segment.py`, `ingest/refine.py`): 114-F001, F002, F010, F004. F001/F002 need segment fixtures
  (option-less part, upper-case intro); oracle = stored refined docs + examples unchanged, as in Fix-A.

**P2 – lost or misleading state from the CLI**
- **Fix-G cli** (`cli.py`): 113-F001, F003, F005; take 113-F002 in the same task (same shape, size S).

**P3 – hardening (optional)**: the remaining 12 IMPROVEMENTs plus the open P3 items of phase 107.

Order: Fix-F → Fix-G. Each gets its own REQ, regression tests from the repros, and the normal workflow.

## Not done
- 114-F004 and F010 are traced, not executed; Fix-F starts by turning them into failing tests.
- Both reports hit the 10-finding cap again; `ingest/api.py`, `boundary.py`, `parts.py` are still unreviewed.
