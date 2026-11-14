# Phase 101 report: report runs hold only human-readable files

Task: TASK-101 · REQ-0108 (RAW-00316, RAW-00317) · design `docs/design/phase-101-report-runs-readable-only.md`

- Action: report_build / report_pack stop writing per-subject metrics and result-data `.json`, the score-summary
  `.json` and the run-log `.log` copy into report runs. The kinds stay in the registry as `needs: retired` so old runs
  still index; score moves into run.json (`exam run-list` reads it first, old json as fallback); the pack checker
  fails on any stray json/log. Tests test_101_* (report_kinds, runlayout), bite-checked.
- Result: dgnl2026 → `run-20261114-085003`, dhqg2024 → `run-20261114-085010`: only tsv, md, pdf, INDEX.md, run.json;
  checker 46/53 checks, 0 failed; suite KNOWN 4 NEW 0; old main runs deleted, INDEX.md rebuilt.
- Decision: standing user rule (RAW-00317): report folders are for human reading only; machine data stays in plans/.
  `prev_report_run` in run.json still names the deleted run (history record, as in TASK-100). Next: none.

Evidence: `docs/report/evidence/TASK-101/verify.md`
