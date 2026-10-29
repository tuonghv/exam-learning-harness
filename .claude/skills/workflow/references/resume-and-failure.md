# Workflow: resume, failure and rollback

**Resume.** The SessionStart output names the task, state, blocker and `next`. Act in order: finish an
uncommitted `.claude/state` transition; fix any workflow-check FAIL/WARN; then do `next`. Read only the
last phase-log entry if `next` is unclear, never the whole log.

**A check fails.** Stay in the current state, set the failing sub-status (`unit_test.status=failed` or
`verification.status=failed`) with the real output in `result`/`evidence`, fix, rerun. Never advance `state`.

**Verification fails after UNIT_TESTED.** Roll back: `state=IMPLEMENTING`, `unit_test.status=pending`,
`verification.status=failed` (keep the evidence), log `## IMPLEMENTING - <id> - <ts>` with the reason,
commit it before the fix, then redo UNIT_TESTED → VERIFIED.

**Blocked.** Add `"blocked": {"reason": "...", "attempts": n}` to `task.json`, keep `state`, set `next` to what
unblocks it, commit. Raise `attempts` per distinct fix-and-rerun; at 3 stop and ask the user. Remove the key
when unblocked (DONE with `blocked` set fails the gate).

Never commit a half-recorded transition: complete it, or discard the edits and redo it.
