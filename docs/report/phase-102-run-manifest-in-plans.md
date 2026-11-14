# Phase 102 report: run manifest under plans, no run.json in report runs

Task: TASK-102 · REQ-0109 (RAW-00318) · design `docs/design/phase-102-run-manifest-in-plans.md`

- Action: the report-run manifest (plan runs, view, key, score, status, ...) moves to
  `plans/<exam>[/<line>]/report-runs/run-<id>.json` behind runlayout helpers; writers, readers (publish, run-list,
  run-compare, report-index, plans-migrate) and the checker use it; new `exam report-manifests-migrate` (dry-run
  default, `--apply`, idempotent); an unmigrated in-folder run.json warns and publish refuses. 13 test_102_* tests.
- Result: 23 run.json migrated, 0 left under reports/; dgnl2026 → `run-20261114-091454`, dhqg2024 →
  `run-20261114-091501` hold only 5 reports + INDEX.md; checker 47/54 checks, 0 failed; suite KNOWN 4 NEW 0.
  User choice: 117 old json/log copies in pre-TASK-101 runs deleted (backup in the session scratchpad); 5 old scores
  carried into their manifests so run-list still shows them.
- Decision: the html solution-report fallback counts as human-readable. Next: REQ-0110 moves reports/MIGRATION.json
  (the last non-report file under reports/) into plans/.

Evidence: `docs/report/evidence/TASK-102/verify.md`
