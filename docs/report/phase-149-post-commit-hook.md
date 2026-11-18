# Phase 149 – Post-commit git hook (TASK-149, REQ-0155)

**Verdict: done.** `.githooks/post-commit` is live in this clone (`core.hooksPath=.githooks`).

## Results
- Advisory checks on every commit (`tools/post_commit_check.py`, stderr, never blocks, `POST_COMMIT_CHECK=0` off):
  `left-behind` tracked changes, `big-file` > 1 MiB, `no-task` code without a `Task:` trailer, `ledger` problems
  when review reports change.
- Auto-push from the user's sample `tmp/post-commit` (RAW-00373): each commit on a non-main branch is pushed to
  `origin` in the background; log `.git/autopush.log`; `AUTO_PUSH=0` off; `main`/`master` never pushed by the hook.
- Real run: first hook run caught a real left-behind (exec bit of the new tool: 755 in git, 644 on disk), fixed;
  on the old commit a069e6a it flags the 3.4 MiB and 2.2 MiB PDFs. Evidence `work/TASK-149/real.txt`.
- 10 unit tests (temp repos; auto-push against a local bare origin). Setup line in README.

## Issues
- `--fast` showed `NEW: 1` once in two runs (also once in TASK-147); 4 re-runs gave NEW 0. A flaky test not yet
  identified.

## Spend
$0.
