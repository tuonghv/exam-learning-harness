# TASK-105 evidence (real rebuild, $0, no model call)

Backup first: reports/ + every plans/*/*/report-runs/ (58 files) copied to the session scratchpad.
`python3 scripts/exam.py rebuild-reports --dry-run` (before): exit 0, find+md5 of reports/ and manifests unchanged (coder).
`python3 scripts/exam.py rebuild-reports` -> rc 0:
- dgnl2025 main run-20261114-143538 score 113/120
- dgnl2026 f pack run-20261114-143547, main run-20261114-143556 score 113/120
- dhqg2024 t81 pack run-20261114-143606 (overlay t82 64-67), main run-20261114-143615 score 105/119

Byte compare vs the backup, old/new run id replaced by X (work/TASK-105/evidence/t105-compare.tsv):
25 report files (md/tsv) SAME, 0 DIFF; 15 pdf skipped (renderer timestamps); 5 INDEX.md differ only in the
line `engine: <git commit>` (438ab4b -> 2c2bfc5), as designed.

Independent checker (tools/check_report_pack.py --key --expect-correct):
- dgnl2025 main: 58 checks 0 failed
- dgnl2026 main: 58 checks 0 failed
- dhqg2024 main: 65 checks 0 failed, KEYISSUE 65 bad_letter I
Files under reports/ other than md/pdf/tsv/html: 0.
