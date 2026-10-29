---
name: workflow
description: Manage the TODO, DESIGN, IMPLEMENTING, UNIT_TESTED, VERIFIED, DONE lifecycle in .claude/state (task.json, backlog.json, phase-log.md). Use when starting, continuing or resuming a task, changing its state, recording evidence, handling a failed check, blocker or rollback, or claiming a phase or task is done.
---

# Workflow

Read `.claude/state/task.json`.

States:
TODO → DESIGN → IMPLEMENTING → UNIT_TESTED → VERIFIED → DONE

At each transition:
- verify the current state criteria
- run the relevant deterministic check
- update task state/evidence **and stamp `updated_at` + `updated_by`**
- append an entry to `.claude/state/phase-log.md` (never edit prior entries)
  headed `## <STATE> - <TASK-ID> - <ISO8601Z>` and recording
  Action → Result → Decision → Next for this transition. The task id is
  required: the log is shared by every task, and only entries tagged with the
  active `task_id` count toward its audit trail
- set `next` to the concrete next action (empty only when state is DONE)
- run `.claude/scripts/workflow-check.sh` and confirm PASS before moving on
- commit the transition through the gate — `.claude/scripts/commit-check.sh`
  (`commit` skill) — so git records the state alongside `task.json`. Not
  committed = not transitioned (see "Definition of a finished transition")
- **reaching DONE:** also run `.claude/scripts/backlog.sh complete <task_id>` —
  do not hand-edit `backlog.json`'s status. It is gated on `task.json` really
  being `DONE`, so it can't be run early, and `workflow-check.sh` now fails
  (not just warns) if `state=DONE` and the backlog entry isn't `done` — a
  hand-edit is the failure mode that check exists to catch, not a substitute
  for the script. `complete` records `completed_at` and `report`;
  `workflow-check.sh` audits **every** `done` item and fails one that has
  neither an existing report file plus a `## DONE - <id> - ...` log entry nor
  a `waiver`. Closing a task that never reached DONE is
  `backlog.sh complete <id> --force "<reason>"` — the reason becomes the
  `waiver`, so the shortcut is visible in history instead of silent.

Status vocab (enforced by `workflow-check.sh`):
- `design`, `implementation`, `report`: `pending` → `completed`
- `unit_test`, `verification`: `pending` → `passed` | `failed`
- `security`: `pending` → `completed` | `not_applicable`

Gating (each requires the prior phase's status, not just the final one):
IMPLEMENTING needs design.status=completed. UNIT_TESTED needs
implementation.status=completed and unit_test.status=passed. VERIFIED needs
verification.status=passed and security.status=completed|not_applicable with
a non-empty security.result. DONE needs report.status=completed.
Paths (`design` skill convention): once `design.status=completed`,
`design.path` must be `docs/design/phase-<N>-<slug>.md` with `<N>` = the
number in `task_id` and the file must exist; once `report.status=completed`,
`report.path` must be `docs/report/` + the same basename and exist.
`workflow-check.sh` rejects state jumps that skip this evidence — it is the
authority, not this description.

task.json fields each transition must hold (`workflow-check.sh` fails the commit otherwise; set
them in the same jq edit as `state`, not after a failed `commit-check`):

| Reaching | Fields |
|---|---|
| DESIGN (done) | `design.{status:"completed", path, summary}`, `acceptance_criteria` |
| IMPLEMENTING | `implementation.{status:"completed", summary, files:[...]}` |
| UNIT_TESTED | `unit_test.{status:"passed", command, result}` |
| VERIFIED | `verification.{status:"passed", command, result, evidence:[paths/observables]}`, `security.{status, result}` |
| DONE | `report.{status:"completed", path}`, `next: ""`; the report file is created in this step (keep a draft outside `docs/report` until then: the gate rejects unstaged workflow files) |
| every one | `state`, `updated_at`, `updated_by`, `next` + a `## <STATE> - <id> - <ts>` phase-log entry |

Never silently skip a state.
Never mark DONE without verification evidence.


## Skills per phase (load only these)

| State you are working in | Load | Required role (skill `coordinator`, REQ-0018) |
|---|---|---|
| TODO / DESIGN | `design` (+ `api-platform-security` if `security_prompt.md` is touched) | `designer` drafts; the coordinator writes `docs/design/` |
| IMPLEMENTING | `coding` + the brief's `Load:` skills (the coordinator loads them only to write the brief) | `coder` |
| UNIT_TESTED | same | `coder` writes the tests; `tester` re-runs every check as independent QA (`--changed` per round, `run_all.sh --fast` plus mapped heavy suites at the gate, complete run weekly or before a release; max 2 coder↔tester rounds) and saves the evidence |
| UNIT_TESTED → VERIFIED | `verify`, `security` | `verifier` (save the evidence first, see `verify`) |
| VERIFIED → DONE | `report` | coordinator |
| every transition | `commit`, `coordinator` | coordinator |



## Definition of a finished transition (and of DONE)

A transition is finished only when **all** hold, in this order:
1. evidence recorded in `task.json` (status + command/result/evidence/path),
   `state` advanced, `updated_at`/`updated_by` stamped, `next` set;
2. `## <STATE> - <TASK-ID> - <ts>` entry appended to `phase-log.md`;
3. `workflow-check.sh` PASS;
4. every changed file staged, `commit-check.sh <msg>` OK, `git commit` succeeded
   (`git status --porcelain -- .claude/state` empty afterwards).

DONE additionally needs, before its commit: the report (`report` skill),
`backlog.sh complete <id>`, and `backlog.json` staged with the report,
`task.json` and `phase-log.md`. If the commit fails, the task is **not** done:
fix and re-commit; never end the turn claiming DONE on an uncommitted state
(the Stop hook blocks it).


## More detail (references/, read on demand)

| Section | File | When |
|---|---|---|
| Plan checklist (multi-task plans) | references/tasks.md | a plan with several tasks; at DONE: `L:` lessons + `lessons.py collect` |
| Requirement ledger (req-kit, `docs/req/`) | references/ledger-and-status.md | a task serves a REQ, moving REQ status |
| Status hygiene across sessions and roles | references/ledger-and-status.md | after compaction, new session, handoffs |
| "Is anything not done yet?" | references/ledger-and-status.md | asked what is left or open |
| Skills per phase — roles | references/roles-per-phase.md | handing a step to a role, role entry points |
| Resuming an in-progress task | references/resume-and-failure.md | resume after a stop or compaction |
| Failure, blocker and rollback | references/resume-and-failure.md | a check fails, rollback, blocked, waiting on user |
| Task selection (one active task, or several after `tasks.sh migrate`) | references/tasks.md | picking the next task |
| Several active tasks (REQ-0060, `.claude/scripts/tasks.sh`) | references/tasks.md | two or more active tasks, hold/resume |
| Picking an old queued task (RAW-00476/00477) | references/tasks.md | pulling an older queued task |

## Momentum — a passed phase is evidence, not a stopping point

`workflow-check.sh` and `commit-check.sh` are the actual gates. Once a phase
passes them and is committed, move into the next phase in the same turn —
don't pause to ask for go-ahead on top of that. This repo's own history has
a concrete case of the failure mode to avoid: a session recorded
`design.status=completed` with a clear `next`, then stopped and wrote
"await go-ahead for IMPLEMENTING" with no actual blocker on record — twice.
That's wasted turns, not caution.

Only stop and ask when one of these actually holds:
- The next step needs information only the user has (an ambiguous
  requirement, a real tradeoff between two designs, an explicit
  design-only request).
- The action is irreversible outside git's safety net (deleting data,
  force-push, spending money, a paid/remote call) — see `token-efficiency`.
- CLAUDE.md rule 1 requires a design and none exists yet for non-trivial
  work — that's a real gate, not a courtesy pause.

Recording a passing check and then continuing in the same turn is the
default; treat every other pause as something to justify, not the norm.
