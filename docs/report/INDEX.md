# Where to crosscheck (user-facing paths)

`work/` is the agents' scratch area (git-ignored). Everything you need to check a result is in these committed paths.

| Kind | Path |
|---|---|
| Plans / designs | `docs/design/phase-N-*.md` |
| Reports (verdict, limits) | `docs/report/phase-N-*.md` |
| Evidence summaries (test output, recount TSV, metrics, verify/test handoffs) | `docs/report/evidence/TASK-NNN/` |
| Requirements and their status | `docs/req/items/REQ-NNNN.md` |
| Run history (git-ignored, answer letters) | `reports/run-history.jsonl` via `exam.py run-stats trend` |

| Task | Design | Report | Evidence |
|---|---|---|---|
| TASK-054 clean four-level format | docs/design/phase-54-clean-exam-levels.md | docs/report/phase-54-clean-exam-levels.md | docs/report/evidence/TASK-054/ |
| TASK-055 group-aware solving | docs/design/phase-55-group-aware-solving.md | docs/report/phase-55-group-aware-solving.md | docs/report/evidence/TASK-055/ |
| TASK-056 run metrics | docs/design/phase-56-run-metrics.md | docs/report/phase-56-run-metrics.md | docs/report/evidence/TASK-056/ |

Rule (RAW-00171, REQ-0061): evidence summaries are small text with no exam content or answer keys; heavy artifacts stay in `work/` and are only referenced.
