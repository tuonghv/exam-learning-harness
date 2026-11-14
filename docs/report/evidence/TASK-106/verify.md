# TASK-106 evidence (real run, $0, local only)

Raw log: work/TASK-106/evidence/t106-real.txt
- AC1 `python3 scripts/exam.py backup` -> rc 0: ~/exam-harness-backup/exam-inputs-20261114T144810Z.tar.gz (12,990,870 B)
  + .sha256.json (217,668 B); 1706 files, 31,027,663 B (plans/, input/, config/published_reports.json).
  `backup --dest ./tmpb` (inside repo) -> rc 2 `ERROR: dest ./tmpb inside repo`, nothing created.
- AC2 `backup --check <archive>` -> `OK 1706 files` rc 0; a copy with one flipped byte -> rc 1
  `FAIL: archive sha mismatch` + the damaged member named.
- AC3 `backup --check <archive> --restore-to <scratch>/er2` -> OK; `rebuild-reports --dry-run --root <scratch>/er2
  --recipe <scratch>/er2/config/published_reports.json` -> rc 0, all 3 exams planned, no ERROR (every recipe input found).
- AC4 docs/guide/report-kinds.md "How to rebuild reports" backup lines (copy to another disk/cloud you own, keep private);
  toolkit-reference.md `exam.py backup` line.

Verifier: VERDICT PASS AC1-AC5, security clean (work/TASK-106/handoff/verify.md). Low findings left open: no test for a
hardlink member or a symlinked dest; a crash between archive and manifest write can leave an archive without manifest
(`--check` then exits 2, so it is never trusted). Fast suite KNOWN 4 NEW 0; test_backup 18 OK.
