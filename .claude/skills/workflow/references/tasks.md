# Workflow — tasks

Part of skill workflow; core rules in ../SKILL.md.

## Plan checklist (multi-task plans)

A design doc may hold a `| # | Item | Task / doc | Done |` table spanning
several tasks. `bash .claude/scripts/checklist.sh` lists the active task's open
rows (SessionStart prints it too); tick a row (`[x]`) in the commit that
finishes it. `workflow-check.sh` fails DONE while the task still owns an open
row (owner = highest task number in the row). Before each commit, re-read the
list so no item is dropped.
At DONE, write what saved or wasted a turn as `L:` lines (`## Lessons` in `work/<T>/handoff/main-lessons.md`);
after VERIFIED and before the DONE commit, `lessons.py drift --task <T> --sweep-every 5 --emit work/<T>`, then `lessons.py collect work/<T>` and, with 1+ new, run the skill-curator (coordinator §2).

## Task selection (one active task, or several after `tasks.sh migrate`)

`task.json` holds the single active task; `backlog.json` holds queued work. Use
`.claude/scripts/backlog.sh` (`list` / `next` / `pick <id>` / `complete <id>`)
to move a task into `task.json` rather than hand-editing `task_id` — that keeps
`task.json` and `backlog.json` from disagreeing (the check warns when they do).
`pick` carries the item's `user_notes` and stamps `picked_at`; `complete` merges them back. Before
acting, honour every `User notes` line that `task-state.sh` prints (REQ-0059); add new ones with
`backlog.sh note` (skill `req-intake`).

## Several active tasks (REQ-0060, `.claude/scripts/tasks.sh`)

After `tasks.sh migrate`, each active task lives in `.claude/state/task.<TASK>.json`, which is the
authority; `task.json` becomes a read-only view rewritten by `tasks.sh sync`. Up to `max_active`
(`.claude/workflow.json`, default 3; env `WORKFLOW_MAX_ACTIVE` overrides one run) tasks are active.
- `pick` needs a file scope (`--scope g1,g2`, later `tasks.sh scope`); a scope that overlaps an active
  task's scope keeps the new task queued with `blocked_by`. Held tasks keep their scope.
- Every commit names one task: `Task: TASK-N` trailer (or `commit-check.sh --task`), stages that
  task's file only; the phase-log stays one file, tagged by task id.
- Resume view: `tasks.sh status` (≤25 lines, needs you / blocked / stale / running / queued);
  detail: `tasks.sh show T` (checkpoint, open questions, handoffs). Every role brief says "read
  `tasks.sh show T` first"; the coordinator copies a role's done/next into `checkpoint` at the wip commit.
- Hold: `tasks.sh hold T --reason R --next N`, later `resume T` (refused at max_active).
- User decisions are asked at DESIGN (`tasks.sh question T --set N`, then `--answer`); workflow-check
  fails IMPLEMENTING+ while any is open. After DESIGN the coordinator decides
  (`tasks.sh question T --decide TEXT --reason R`, `decided_by: coordinator`). Cost, a new block or a
  permission still go to the user via `task_checkpoint.sh ask`; `due`/`brief` name the task to switch
  to after 10 min, and the waiting task stays active.
- Stale inputs: `tasks.sh inputs T --set ...` at DESIGN; `tasks.sh stale T` (rc 4) fails the gate at
  IMPLEMENTING+ until a designer delta review `--rehash --reason "NOT AFFECTED|updated"`.
- Guard: a role bound to T cannot write `work/<U>/` (B1) or another active task's scope (B2, "send
  CLAIM REQUEST"); writes outside every scope are logged only. A role stops only after its
  `work/T/handoff/<role>*.md` has `PROGRESS:` (and `next:` when PARTIAL); asked once.
- New readers of task state go through `_tasks.py`, or get an allow row with a reason in
  `checks/task_readers.allow`; `checks/task_readers.sh` (in `checks/shell.sh`) fails otherwise.

**Picking an old queued task (user, RAW-00476/00477):** an older requirement must never undo,
override or narrow a newer feature. Before DESIGN of any task queued before the latest DONE tasks:
1. Inspector staleness review: each part marked STILL-NEEDED / DONE-BY <task> / OBSOLETE /
   CHANGED-BASE (current file:line), and every draft ref checked against HEAD.
2. Close or narrow the task first: drop parts a newer task did (`--force` with the reason if the
   whole task is superseded), split off large parts, and refresh the draft's refs and premise.
3. The design states `## Newer features kept`: each newer task/REQ whose code or behaviour it
   touches, and how that behaviour stays unchanged (tests from those tasks stay green). Where the old
   requirement conflicts with a newer one, the newer one wins; a real conflict goes to the user.
