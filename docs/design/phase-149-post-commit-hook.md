# Phase 149 – Advisory post-commit git hook (TASK-149, REQ-0155)

Source: REQ-0155 (RAW-00371 hook like code-security-scanner's; RAW-00372 own design from the idea, the file is not
on disk).

## Plan modes
No change to single-source or pipeline plans; git tooling only.

## Design
- 149.1 `.githooks/post-commit` (tracked, Bash 3.2): `exec python3 -I tools/post_commit_check.py`, always exit 0;
  `POST_COMMIT_CHECK=0` turns it off. Enabled per clone with `git config core.hooksPath .githooks`
  (no hooks were active before, so nothing is shadowed).
- 149.2 `tools/post_commit_check.py` (stdlib), checks HEAD only, prints `post-commit: WARN <check>: ...` lines or
  `post-commit: OK <sha>`. Advisory only: post-commit cannot block, and blocking is opt-in (user, 2026-09-28).
  - `left-behind`: tracked files still modified/deleted/staged after the commit (first 5 + count); `.claude/state`
    named first (the Stop hook blocks on it). Today's case: 13 report deletions left out of an advance commit.
  - `big-file`: a file added/changed by HEAD larger than 1 MiB (`git diff-tree` + `cat-file -s`). Today's case: a
    3.4 MB PDF rode along in a prompt-edit commit.
  - `no-task`: HEAD changes `src/`, `tools/`, `tests/` or `.claude/` code but has no `Task:` trailer (one task per
    commit, CLAUDE.md).
  - `ledger`: HEAD touched `docs/report/fable-review/` or `docs/review/` -> run `review_ledger.check`, show its
    problems.
  Every git call has a timeout; any exception prints one `post-commit: skipped (<error>)` line.
- 149.3 Setup line in README and workflow-roles §9.

## Verification
Unit tests on temp git repos per check + opt-out; real commit in this clone shows the hook output.
