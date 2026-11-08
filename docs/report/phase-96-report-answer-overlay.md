# Phase 96 report - labelled answer overlay for the DHQG 2024 report (REQ-0103)

Format change (cross-check this):
| Where | Before | After |
|---|---|---|
| DHQG 2024 published report (main), printed questions 64, 65, 66, 67 | declined (`chưa có đáp án (solver từ chối)`) | D, A, D, B, each with a source line naming plan run 20261107-014525 of line t82 and showing the fixed fare table passage |
| answered / declined (120 questions) | 111 / 9 | 115 / 5 |
| other 116 question blocks | - | byte-identical to the previous t81 report |

- Result: `exam report-pack ... --overlay PLAN_DIR:64,65,66,67 --overlay-reason "..."` (and `exam publish`, which inherits the overlay) takes the answer, solution, status and doubt of listed questions from another plan run at render time on an in-memory copy; no `result.json` or `plan.json` is ever written. Validation (exit 2, no output folder): same exam, stem+options hash equal (the passage is excluded because the table fix changed it), the base question must be declined or unresolved, known printed number, a reason. `run.json` records `overlays` (plan run, printed numbers, base and overlay ids, `text_sha256`, reason); `run-list` sees the overlay plan run through `plan_runs`; `check_report_pack` recounts from base + overlay and fails when the overlay result is tampered.
- Current runs: dev `reports/dhqg2024/t81/run-20261108-082400/` and published `reports/dhqg2024/main/run-20261108-083026/` (built at $0; earlier main runs `run-20261105-110545` and `run-20261108-072402` kept, byte-unchanged). `run-list`: the t82 plan run is `published`; Lines table main -> run-20261108-083026.
- Measured: 0 `none` words; pack checker 60 checks 0 failed (both runs); text identity equal for the 4 questions (own independent normalisation); `plans/` 1599 files unchanged (same sha256); reports 362 -> 395 files (the publish step changed only the two INDEX.md); tests `test_overlay` 26 (text-hash off fails 2, base-answered off fails 1, marker everywhere fails 4); gate `--full` ran 1920, new=[], known=4.
- Open (low): the checker's usage when the overlay plan dir is passed as a plan dir (17 spurious failures; the overlay is read from `run.json`) deserves a clearer message; the merged answers of 64-67 come from a different run than the other 116 (stated in each block and in `run.json`); the exam-level index still lists 7 superseded files as `unregistered` (REQ-0102 D1).
- Undo: delete the two new run folders (dev in `t81`, published in `main`) and run `report-index` on `reports/dhqg2024`.
- Evidence: `work/TASK-096/evidence/` (untracked).
