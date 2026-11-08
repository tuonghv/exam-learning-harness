# Phase 95 report - publish badge from report links, quieter exam index (REQ-0102)

Display change (cross-check this):
| Where | Before | After |
|---|---|---|
| `run-list` `publish` column, dgnl2026 line f plan runs (vietnamese, english, math, science2) | `dev` | `published` (a complete `main` report run links them in `plan_runs`) |
| `run-list` `publish` column, dhqg2024 line t81 plan runs (4) | `dev` | `published` |
| `run-list` `publish` column, the 5 old dhqg2024 line `main` plan runs | `published` (by line name) | `dev` (no main report links them) |
| exam-level `INDEX.md`, rows with Status `unregistered` | dgnl2026 18, dhqg2024 19 | dgnl2026 3, dhqg2024 4 (generated `INDEX.md` and `run.json` files are no longer flagged) |

- Result: a plan run is `published` iff some complete report run in `reports/<exam>/main` lists it in `run.json` `plan_runs` (the existing `linked()` also resolves aliases); everything else is `dev`. The Lines table and the report-runs column are unchanged. The exam-level index skips generated `INDEX.md` (first line `# Reports index: `) and `run.json`; a truly unknown file is still flagged.
- Checked: all 22 `run-list` rows equal the verifier's recomputation from the real `run.json` files (8 published, 14 dev, 0 diffs); `plans/` 1599 files with identical sha256; only `cli.py` and `report_kinds.py` changed; tests `test_publish_badge` 11 (8 fail on the previous code); gate `--full` ran 1894, new=[], known=4.
- Open (low, cosmetic, D1): the 7 remaining `unregistered` rows are real old files that the run-level index already marks superseded: `dgnl2026/f/run-20261107-133501/dgnl2026_all_score-*` (3) and `dhqg2024/main/run-20261105-110545/solutions*` (4); the exam-level index could show them as superseded from the run's `run.json` `superseded` list.
- Evidence: `work/TASK-095/evidence/` (untracked).
