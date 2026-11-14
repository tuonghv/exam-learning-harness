# Phase 106 report: verified local backup of the rebuild inputs

Task: TASK-106 · REQ-0113 (RAW-00323, RAW-00325) · design `docs/design/phase-106-exam-backup.md`

- Action: `exam backup` writes `plans/`, `input/` and `config/published_reports.json` as a dated tar.gz + per-file
  sha256 manifest to `~/exam-harness-backup/` (outside the repo, verified after writing, newest 5 kept);
  `backup --check ARCHIVE [--restore-to DIR]` re-hashes and safely restores. Tar helpers now shared with plans-migrate
  (`pipeline/tarbackup.py`). Keys stay out of git (user rule); nothing leaves the machine.
- Result: real backup 1706 files 31.0 MB -> 13.0 MB archive; check OK; a one-byte change fails and names the file;
  a restored copy passes `rebuild-reports --dry-run` for all 3 exams; in-repo dest refused. 18 unit tests, fast KNOWN 4 NEW 0.
- Decision: the best fit for "keys never tracked" is a verified local archive the user copies to another disk/cloud they own.
  Next: low findings (hardlink-member and symlinked-dest tests; archive left without manifest after a crash) as a small follow-up if wanted.

## Defects
- none

Evidence: `docs/report/evidence/TASK-106/verify.md`
