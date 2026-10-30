---
name: workflow
description: Manage the TODO, DESIGN, IMPLEMENTING, UNIT_TESTED, VERIFIED, DONE lifecycle in .claude/state (task.json, backlog.json, phase-log.md). Use when starting, continuing or resuming a task, changing its state, recording evidence, handling a failed check, blocker or rollback, or claiming a phase or task is done.
---

# Workflow

Read `.claude/state/task.json`. States: TODO → DESIGN → IMPLEMENTING → UNIT_TESTED → VERIFIED → DONE.
Never skip a state. Never mark DONE without verification evidence.

## At each transition
Verify the current state's criteria first, then make the move with `advance.sh` (skill `advance`: fields, phase-log
entry, REQ steps, `workflow-check.sh`, gated commit; DONE also needs the report from the `report` skill). Never
hand-edit `backlog.json`; abandon a task with `backlog.sh complete <id> --force "<reason>"`. Not committed = not transitioned.

Status vocab: `design`, `implementation`, `report`: pending → completed; `unit_test`, `verification`:
pending → passed | failed. Each phase needs the prior phase's status. `design.path` is
`docs/design/phase-<N>-<slug>.md`, `report.path` is `docs/report/` + the same basename; both must exist.
`workflow-check.sh` is the authority, not this text.

## Fields each transition must hold (set them in the same edit as `state`)
| Reaching | Fields |
|---|---|
| DESIGN | `design.{status:"completed", path, summary}`, `acceptance_criteria` |
| IMPLEMENTING | `implementation.{status:"completed", summary, files:[...]}` |
| UNIT_TESTED | `unit_test.{status:"passed", command, result}` |
| VERIFIED | `verification.{status:"passed", command, result, evidence:[paths]}` |
| DONE | `report.{status:"completed", path}`, `next: ""` |

## Skills and roles per state
| State | Load | Role |
|---|---|---|
| TODO / DESIGN | `design` | `designer` drafts; coordinator writes `docs/design/` |
| IMPLEMENTING, UNIT_TESTED | `coding`, brief's `Load:` skills | `coder`; `tester` re-runs the checks |
| UNIT_TESTED → VERIFIED | `verify` | `verifier` (save the evidence first) |
| VERIFIED → DONE | `report` | coordinator |
| every transition | `commit`, `coordinator` | coordinator |

Roles are required; a skipped role needs a recorded waiver. `task.json` `roles.<role>` = the handoff path under
`work/<T>/handoff/` (line 1 `PROGRESS: COMPLETE`, line 2 `SKILLS: ...`) or `{"waiver": "<reason>"}`.
Set it in the spec `set.roles` (skill `advance`).

## Requirement ledger (`docs/req/`)
The ledger holds WHAT was asked (skill `req-intake`); the TASK holds HOW and the evidence. Link with
`req.py task REQ-00NN TASK-0NN`. `advance.sh` steps the linked REQs with the TASK (a lagging REQ: `advance.sh req-catchup`;
skill `advance`). A "continue" prompt is not a requirement: `req.py raw ignore <RAW> --reason ...`.

"What is left": `bash .claude/scripts/status.sh` (rc 0 = nothing pending), not a hand-read of the json.

## Momentum
A passed, committed phase is evidence, not a stopping point: go to the next phase in the same turn.
Stop and ask only when the next step needs information only the user has, is irreversible outside git,
or a non-trivial change has no design yet.

More: `references/tasks.md`, `references/resume-and-failure.md`.
