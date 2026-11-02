# Report phase 57: standard crosscheck paths (TASK-057; REQ-0061)

Verdict: adopted. `work/` is the agents' scratch (git-ignored). What you check lives in committed paths: designs in `docs/design/`, reports in `docs/report/`, evidence summaries in `docs/report/evidence/TASK-NNN/`, one generated index `docs/report/INDEX.md` (`.claude/scripts/_evidence.py index`, run at DONE; `index --check` fails when stale). Rule text: `docs/guide/workflow-roles.md` §9 and CLAUDE.md item 11.

## What changed
- Evidence is published only for BIG changes: a task flagged `evidence_required` (set by the coordinator for engine, prompt, format or metrics changes) must publish scanned text evidence at VERIFIED and cite it in the report at DONE; unflagged tasks keep today's behaviour (WARN only).
- `_evidence.py scan` refuses exam-like content (question headings, option lines, answer lines/JSON/TSV), URLs, secrets, binaries, oversize files and anything under `plans/` or `reports/`; `publish` takes only files under `work/<TASK>/`, refuses symlinks, redacts `/home/<user>` paths, and is idempotent.
- `commit-check` accepts a task's own evidence dir and INDEX.md and flags another task's evidence dir as foreign.
- Solve output without `--out` goes to git-ignored `reports/<exam>/<run>/` (run history `reports/run-history.jsonl`); a test proves `git status` stays clean. REQ-0062 will move this into the plans/reports split.

## Evidence (docs/report/evidence/TASK-057/)
- e2e57.txt (13 flagged/unflagged gate checks), scope57.txt (6), suite-final.txt and head-failures.txt vs baseline-failures.txt (same 4 known failures as baseline 083d0e4), test.md, verify.md.
- Backfilled by hand: TASK-054, 055, 056 evidence folders.

## Limits
Verified on fixtures and script checks only (tooling, no real run). A symlink test for publish was not added (fix verified by hand). The `reports/` default dir is provisional until REQ-0062.

User instructions honoured: RAW-00171, RAW-00172, RAW-00173, RAW-00174.
Evidence files for crosscheck: docs/report/evidence/TASK-057/e2e57.txt, docs/report/evidence/TASK-057/verify.md (index: docs/report/INDEX.md).
