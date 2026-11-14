# TASK-101 evidence

Unit: python3 -I tools/run_tests.py --fast -> KNOWN 4 NEW 0 (test_101_* in test_report_kinds, test_runlayout U101RlScore; bite-checked)

Real re-publish ($0, no model call):
- `scripts/exam.py publish dgnl2026 --from f` -> reports/dgnl2026/main/run-20261114-085003
- `scripts/exam.py publish dhqg2024 --from t81` -> reports/dhqg2024/main/run-20261114-085010

Files in each new run: answer-table .tsv, solution-report .md/.pdf, solution_public-report .md/.pdf, INDEX.md, run.json.
`find RUN -name '*.json' ! -name run.json -o -name '*.log'` -> 0 in both.
INDEX.md lines naming metrics/result-data/run-log: 0 in both.

tools/check_report_pack.py (independent, imports no engine code):
- dgnl2026 run-20261114-085003 + 4 plan runs (f): RESULT 46 checks 0 failed ok (json/log files in pack 0; plan_run_id in run.json x4)
- dhqg2024 run-20261114-085010 + 4 plan runs (t81): RESULT 53 checks 0 failed ok

Provenance in run.json plan_runs (plan_run_id, result_sha256): 4 per exam.
score: absent (publish had no answer key, so no score-summary is built; same as before).

AC2: old main runs run-20261114-082249 (dgnl2026) and run-20261114-082256 (dhqg2024) deleted after the checker passed;
report-index rebuilt for reports/{dgnl2026,dhqg2024}{,/main}: main lists 1 run, 0 references to the old ids.
