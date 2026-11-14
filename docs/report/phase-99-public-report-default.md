# Phase 99 report: default student report and all-only pack

Task: TASK-099 · REQ-0106 (RAW-00300..313) · design `docs/design/phase-99-public-report-default.md`

## Action → Result → Decision → Next
- Action: renamed kind `public` to `solution_public-report`; name parsing now accepts `_` in a kind; registry flag
  `pack_subject:false` on answer-sheet, solution-report, solution_public-report; `build_pack` drops those per-subject files.
- Result: every report writes `<exam>_<subject|all>_solution_public-report_<run>.md/.pdf` by default. A multi-subject pack
  holds only `all` reports plus per-subject metrics/result-data/run-log. Unit suite NEW 0. Three real packs rebuilt at $0;
  the independent checker passes on each (62/52/59 checks, 0 failed); public md 120/120 answers, 0 AI-note lines.
- Decision: per-subject data files kept (provenance for publish/overlay); learning-report unchanged (only `--view learn`).
- Next: none. Earlier main runs stay on disk (publish keeps history).

## Evidence
`docs/report/evidence/TASK-099/verify.md`
