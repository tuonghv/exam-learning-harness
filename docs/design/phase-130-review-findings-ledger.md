# Phase 130 – Review findings ledger + check (TASK-130, REQ-0137)

## Finding (RAW-00350)
Of 80 findings in the 9 code-review reports (model Fable), 17 batch-1 IMPROVEMENTs were parked as "P3, later"
in the phase-107 triage and never designed; batches 2/3 said they carried them, the P3 tasks 123-125 took only their
own batch. Nothing tied finding ids to fix tasks.

## Plan modes
Workflow tooling only: no engine, prompt or solve path change; single-source and pipeline plans unaffected.

## Design
- 130.1 `docs/review/findings.tsv` (header `id report class disposition ref note`): one row per finding id
  `<phase>-Fnnn` (phase = number in the report file name). disposition: `fixed` (ref = TASK-NNN that fixed it),
  `not-a-defect` (ref = triage TASK), `waived` (note = reason), `open` (ref = queued/active TASK). Seeded from the
  triage docs (class) and the fix design/report docs that name the id (incl. ranges `F003..F007`, `F006-F009`):
  63 fixed / not-a-defect, 17 open -> TASK-131.
- 130.2 `tools/review_ledger.py [--root R]` (stdlib, `python3 -I`): review reports = docs/report/*.md with a
  `### Fnnn – [SEV]` heading; errors: id without a row, unknown disposition, `fixed`/`not-a-defect` without a TASK
  ref, `open` whose task is not queued/active in backlog.json, row whose report/id does not exist. Prints
  `LEDGER: <n> ids, <k> open, <e> problem(s)` + one line per problem; exit 1 on problems, else 0.
- 130.3 workflow-check: run the checker; each problem line becomes a `WARN:` (non-blocking; a blocking rule needs
  the user's confirmation, CLAUDE.md).
- 130.4 coordinator skill: a review batch is done only when its ids are in the ledger; "P3, later" needs an `open`
  row with a queued task.

## Verification ($0)
tests/unit/test_review_ledger.py (missing id, dangling open task, bad disposition, clean pass) in a temp root; real
repo: checker exit 0 with 17 open; `--fast` NEW 0.
