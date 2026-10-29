---
description: Verifier role - run real verification and the security pass for a UNIT_TESTED task
argument-hint: "[optional: which acceptance criteria to focus on]"
---
Role: verifier. Prove the real execution path; never reuse unit-test output as evidence.

1. Load skills `workflow`, `verify`, `security`, `token-efficiency`.
2. `bash .claude/scripts/task-state.sh`. Require state=UNIT_TESTED; otherwise report the
   state and stop.
3. Run every row of the design doc's Verification table on a scratch kit with a fake `claude`
   (never the real manifest, never real tokens). Paste the real outputs.
4. Pass → record `verification.evidence` and `security.*`, set state=VERIFIED, add the log
   entry, and commit (`commit` skill, `Verified-by:` trailer). Then load `report` and finish DONE
   (report, `backlog.sh complete`, commit including backlog.json).
   Fail → follow the rollback in `workflow` "Failure, blocker and rollback" (`references/resume-and-failure.md`): commit the rollback
   before any fix.
5. End with `Decisions:`.

Focus: $ARGUMENTS
