# Phase 97 report: small fixes (REQ-0104, TASK-097)

**Action:** exam-level `INDEX.md` now honours the `superseded` globs of each run's own `run.json`; `tools/check_report_pack.py` refuses an overlay plan dir given as PLAN_DIR.
**Result:**
- dgnl2026 and dhqg2024 exam INDEX: 0 unregistered (before 3 and 4). dgnl2026 `f/run-20261107-133501` now shows all 16 files superseded (its run.json says `glob: "*"`; 13 of them were listed `standard` before, a visible change). dhqg2024 `main/run-20261105-110545/solutions*` 4 files superseded.
- Checker: overlay dir as PLAN_DIR -> exit 2 and one line; the published DHQG run still passes 60 checks, 0 failed.
- Tests: 2 new; full gate ran in a worktree, new=[], known=4. plans/ unchanged (1599 files). No model call, cost 0.
**Waivers:** designer, coder, tester, verifier roles waived (about 30 lines, coordinator wrote them); evidence is the gate and a grep recount (`work/TASK-097/evidence/recount.txt`).
**Still listed unregistered (out of scope):** frozen `reports/MIGRATION.index/*` copies and `input-001/main/run-20261102-103714` (result.json).
**Decision / Next:** done; undo = revert the commits and run `report-index` on both exam folders.
