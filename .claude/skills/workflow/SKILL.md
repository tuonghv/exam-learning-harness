---
name: workflow
description: Manage the TODO, DESIGN, IMPLEMENTING, UNIT_TESTED, VERIFIED, DONE lifecycle in .claude/state (task.json, backlog.json, phase-log.md). Use when starting, continuing or resuming a task, changing its state, recording evidence, handling a failed check, blocker or rollback, or claiming a phase or task is done.
---

# Workflow

Read `.claude/state/task.json`. States: TODO → DESIGN → IMPLEMENTING → UNIT_TESTED → VERIFIED → DONE.
Never skip a state. Never mark DONE without verification evidence.

## At each transition
1. Verify the current state's criteria and run its deterministic check.
2. Update task state and evidence; stamp `updated_at` (`date -u +%Y-%m-%dT%H:%M:%SZ`) and `updated_by`; set `next`
   to the concrete next action (empty only at DONE). Keep `state` and the sub-statuses in agreement.
3. Append `## <STATE> - <TASK-ID> - <ISO8601Z>` to `.claude/state/phase-log.md` (never edit old entries):
   Action → Result → Decision → Next. The task id is required.
4. `.claude/scripts/workflow-check.sh` must PASS.
5. Commit through the gate (`commit` skill). Not committed = not transitioned.
6. DONE also needs the report (`report` skill), `.claude/scripts/backlog.sh complete <id>` (never hand-edit
   `backlog.json`; abandon with `complete <id> --force "<reason>"`) and `backlog.json` staged with the rest.

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

## Requirement ledger (`docs/req/`)
The ledger holds WHAT was asked (skill `req-intake`); the TASK holds HOW and the evidence. Link with
`req.py task REQ-00NN TASK-0NN`. After a TASK transition, move the REQ in the same turn:
`req.py status REQ-00NN <STATE> --evidence "..." --next "..."`; tick acceptance items with `req.py ac`
(no second verification). Stage changed `docs/req` files in the transition commit. A "continue" prompt is
not a requirement: `req.py raw ignore <RAW> --reason ...`.

"What is left": `bash .claude/scripts/status.sh` (rc 0 = nothing pending), not a hand-read of the json.

## Momentum
A passed, committed phase is evidence, not a stopping point: go to the next phase in the same turn.
Stop and ask only when the next step needs information only the user has, is irreversible outside git,
or a non-trivial change has no design yet.

More: `references/tasks.md`, `references/resume-and-failure.md`.
