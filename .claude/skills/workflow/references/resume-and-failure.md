# Workflow — resume, failure and rollback

Part of skill workflow; core rules in ../SKILL.md.

## Resuming an in-progress task

The SessionStart hook already printed the resume point (task, state, blocker,
`next`, last phase-log heading, uncommitted state, gate warnings). Act on it:
1. Uncommitted `.claude/state` listed → finish and commit that transition first.
2. workflow-check FAIL/WARN listed → fix the bookkeeping before new work.
3. Otherwise do `next`. Read the last phase-log entry only if `next` is unclear
   (`awk '/^## /{b=""} {b=b $0 "\n"} END{printf "%s", b}' .claude/state/phase-log.md`),
   never the whole log.
With several active tasks: the start-up `Recovery:` block (`tasks.sh recover`) gives one resume line per task; relaunch each
task's lead with `tasks.sh lead T` (coordinator §2d), which reads `tasks.sh show T` first and resumes from `checkpoint.next`.
Mid-session: `bash .claude/scripts/task-state.sh` / `status.sh` give the same view.

## Failure, blocker and rollback

- **A check fails (test, verify, gate, commit):** stay in the current state,
  set the failing sub-status (`unit_test.status=failed` /
  `verification.status=failed`) with the real output in `result`/`evidence`,
  fix, rerun. Never advance `state` on a failure.
- **Verification fails after UNIT_TESTED → roll back:** `state=IMPLEMENTING`,
  `unit_test.status=pending`, `verification.status=failed` (keep the failing
  evidence), append `## IMPLEMENTING - <id> - <ts>` saying why, commit it
  (`State: IMPLEMENTING`) before the fix, then redo UNIT_TESTED → VERIFIED.
- **Cannot proceed (repeated failure, missing input, external outage):** add
  `"blocked": {"reason": "<exact blocker>", "attempts": <n>}` to `task.json`,
  keep `state` where it is, set `next` to what unblocks it, commit. Increment
  `attempts` per distinct fix-and-rerun, across sessions. At `attempts >= 3`
  (`workflow-check.sh` warns) stop retrying and ask the user. Remove the key
  when unblocked; DONE with `blocked` set fails the gate.
- **Waiting on a user-only question (paid, permission, block):** do not block the slot; after
  `TASK_CHECKPOINT_TIMEOUT_MIN` the task is auto-held and the next workable task picked (skill
  `coordinator` §6 recipe, `tasks.sh autohold`); it resumes from its checkpoint on the answer.
- **Interrupted mid-transition** (session killed, compaction, timeout): the
  next session sees the uncommitted files in the SessionStart output; either
  complete steps 1-4 above or `git checkout -- .claude/state` and redo the
  transition. Never commit a half-recorded transition.
- **Abandon a task:** `backlog.sh complete <id> --force "<reason>"`, commit.
