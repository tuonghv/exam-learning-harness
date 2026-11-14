# TASK-103 evidence

Real move ($0): backup of reports/MIGRATION.json + reports/MIGRATION.index/ (23 tar members) in the session scratchpad.
`scripts/exam.py report-manifests-migrate --apply` -> 12 moved (map + 11 stashed INDEX.md), 23 manifests already migrated, 0 problems, rc 0.
Second run -> 0 to move, rc 0 (idempotent; leftover check clean).
Now: plans/MIGRATION.reports.json, plans/MIGRATION.reports.index/ (11 files).
`find reports -type f ! -name '*.md' ! -name '*.pdf' ! -name '*.tsv' ! -name '*.html'` -> 0.

plans-migrate --verify (plans side): 15 checks, 5 failed (file count 1596/1713, bytes, plan.json 50/55, history 158/163 x2).
Same 5 failures with the pre-TASK-103 code (worktree of e3b7feb on the same tree): growth of plans/ since the
TASK-090 apply, not this change; MIGRATION.reports.* are skipped (count unchanged after the move).

plans-migrate --root reports --verify: 8 checks, 8 failed. The pre-TASK-103 code on a scratch copy of today's reports/
with the old map restored also gives 8 checks, 8 failed: the TASK-090 reports migration record is stale (runs deleted,
re-published, INDEX re-rendered, json/log removed since by TASK-100..102). Not caused by this change; the map is
found at its new place (no legacy guard error).

## Clean rebuild (user RAW-00320..322: reports regenerate from plan data, no migration of old reports)
Backup (362 entries) of reports/, every plans/*/*/report-runs/ and plans/MIGRATION.reports.* in the session scratchpad, then all deleted.
Rebuilt at $0 (report-pack/publish from stored plan runs, no model call):
- dgnl2025 main run-20261114-140907 (main plan runs, key 2025): score 113/120; check_report_pack 57 checks 0 failed (--expect-correct 113)
- dgnl2026 main run-20261114-140950 (publish --from f; pack f/run-20261114-140925, key 2026): 113/120; 57 checks 0 failed
- dhqg2024 main run-20261114-140941 (publish --from t81; pack t81/run-20261114-140916, key 2024, overlay t82 64-67): 105/119;
  64 checks 2 failed: key file gives printed 65 = "I" (not A-D). The engine excludes it (Key issues: 65 bad_letter I) -> 119 scorable;
  the checker counts it -> 120 and 10 WRONG. Content defect in the key file, not the engine; same 105/119 as the old key runs.
Files under reports/ other than md/pdf/tsv/html: 0. No run.json, no MIGRATION.* under reports/ or plans/.
