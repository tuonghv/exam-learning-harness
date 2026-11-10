# Phase 98 report: dgnl2024 official key score and richer report (REQ-0105, TASK-098)

**Action:** `explain.parse_key` now reports key problems (bad letter, duplicate, missing) while `load_key` is unchanged; `report-pack --key` summary gains accuracy over scorable rows, per-question table, doubt calibration, mismatch list with the engine's reasoning and a key-issues section. Free baseline on the stored runs, then a fresh paid re-solve (user approved, `plans/dhqg2024/t98/run-all.sh`, `--fresh --model claude-sonnet-5-5`).
**Result:**
- Key `input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt`: 119 keys; Cau 65 "I" is flagged `bad_letter`, scored `keybad`, excluded from accuracy (not guessed).
- Baseline (old t81 + t82 overlay): 105/119 = 88.2% (wrong 9, declined 5). Fresh t98 re-solve: 104/119 = 87.4% (wrong 9, declined 6). Differences: Q10 correct->declined, Q20 wrong->correct, Q95 correct->wrong, Q119 wrong C->B (engine drift).
- Calibration (t98): doubt low 97.0% correct (n 100), medium 58.3% (n 12), high 0% (n 7, 6 declined).
- Cost: 1.5318 USD (5 solves). Key never reached the engine: grep in t98 script and logs 0, e-*.md sha256 equal to t81/t82.
- Tests: 13 new (11 fail on pre-change code); full gate 1935 ran, known 4, new 0 (the 4 also fail on a clean tree).
**Reports (dev line, not published):** `reports/dhqg2024/dev/run-key-baseline/`, `reports/dhqg2024/dev/run-key-t98/` (`*_score-summary_*.md/.pdf`, `*_score-vs-key_*.tsv`). Evidence: `work/TASK-098/evidence/`.
**Deferred:** a key line inside the learner solution report (design 98.4). Publishing into `main` waits for the user.
**Open for the user:** fix key line 65 ("I") to score that question; choose which run to publish (`exam publish dhqg2024 --from dev --key FILE --publish`).
**Decision / Next:** done; undo = revert the commits.
