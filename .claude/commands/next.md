---
description: Resume the active task and advance it one or more phases (implementer role)
argument-hint: "[optional focus or instruction]"
---
Role: implementer. Advance the active task in `.claude/state/task.json`.

1. Load skills `workflow` and `token-efficiency` (skip any already loaded this session).
2. Run `bash .claude/scripts/task-state.sh` (skip if the SessionStart output is in context
   and nothing changed). Uncommitted `.claude/state` or a workflow-check FAIL → fix that first.
3. Load only the skills for the current phase, per `workflow`'s "Skills per phase":
   - TODO / DESIGN → `design` (+ `api-platform-security` if `security_prompt.md` is touched)
   - IMPLEMENTING → `bash`, `coding`, `unit-test`
   - UNIT_TESTED → `verify`, `security`
   - VERIFIED → `report`
   - no active task (DONE) → `bash .claude/scripts/backlog.sh next`, then `pick` it
   Then load `coordinator` and hand the step to its required role (table's role column): `designer`, `coder`
   (IMPLEMENTING and UNIT_TESTED), `verifier`. Record each role in `task.json` `roles.<role>` (handoff path, or
   `{"waiver": "<reason>"}` for a skip); `workflow-check.sh` fails the transition without it.
4. Every transition: `commit` skill (commit-check.sh, then git commit). Keep going through
   phases until a stop condition in `workflow` "Momentum" holds.
5. End the turn with `context-compaction` (boundary line) and `Decisions:`.

Extra instruction: $ARGUMENTS
