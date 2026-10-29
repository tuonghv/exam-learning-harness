---
description: Design role - write or revise the active task's design doc and reach DESIGN
argument-hint: "[task id to pick, or design question to resolve]"
---
Role: designer. Only design work in this turn: no implementation code.

1. Load skills `workflow`, `design`, `token-efficiency`.
2. `bash .claude/scripts/task-state.sh`. If there is no active task, or $ARGUMENTS names a queued
   task, commit any leftover state first, then `bash .claude/scripts/backlog.sh pick <id>`.
3. Prove the defect on HEAD (design skill "Premise first"), then write
   `docs/design/phase-<N>-<slug>.md`: acceptance criteria, reuse, unit tests, and a Verification table.
4. Record `design.*` in task.json, add the `## DESIGN - <id> - <ts>` log entry, run
   `workflow-check.sh`, and commit via the `commit` skill (`State: DESIGN`).
5. Stop at DESIGN. Put open product questions in a numbered `Decisions:` list.

Input: $ARGUMENTS
