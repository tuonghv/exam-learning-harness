# TASK-102 evidence

Unit: python3 -I tools/run_tests.py --fast -> KNOWN 4 NEW 0; 13 test_102_* fail on pre-TASK-102 code (tester bite check).

Migration ($0): `scripts/exam.py report-manifests-migrate` dry-run 23 to move, 0 problems; `--apply` 23 moved;
second run 0 to move, 23 already migrated (idempotent). `find reports -name run.json` -> 0; manifests under
plans/*/*/report-runs/ -> 23 (backup of the 23 run.json kept in the session scratchpad).

Re-publish: dgnl2026 --from f -> reports/dgnl2026/main/run-20261114-091454; dhqg2024 --from t81 -> run-20261114-091501.
Each holds 5 reports (tsv, 2 md, 2 pdf) + INDEX.md only. Manifests plans/<exam>/main/report-runs/run-<id>.json status complete, 4 plan_runs each.
tools/check_report_pack.py: dgnl2026 47 checks 0 failed; dhqg2024 54 checks 0 failed (run manifest present, manifest plan_runs 4, result_sha256 mismatches 0).
run-list dgnl2026 reads the manifests (published column, report runs, score 113/120).

Old main runs run-20261114-085003 / -085010 and their manifests deleted; report-index rebuilt for every reports/ folder; 0 references left.

User decision (RAW-00318 follow-up): delete old json/log copies in pre-TASK-101 runs: 117 files (84 json, 33 log) backed up
(scratchpad tar) and deleted. Scores of 5 old runs carried from their score-summary json into the manifest `score`
(1 file without `total` skipped; run-list could not read it before either). After: files under reports/ other than
md/pdf/tsv/html = 1 (reports/MIGRATION.json, moved by a follow-up task).

## Coordinator re-runs after the verifier (no Bash there)
- report-manifests-migrate (dry-run): 0 to move, 23 already migrated, 0 problems
- run-list dgnl2026: the 4 f plan runs are published, linked to main run-20261114-091454
- run-list dhqg2024: the 4 t81 plan runs + t82 overlay run published, linked to main run-20261114-091501
- verifier D1: reports/input-001/main/run-20261102-103714/*.html is the solution-report html fallback (human-readable), kept
- verifier D2: plansmigrate routes its run.json target to runlayout.manifest_path (plansmigrate.py:90-92, 771), nothing written into reports/
